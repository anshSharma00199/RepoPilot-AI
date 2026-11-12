import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.execution_job import ExecutionJob
from app.models.diagnostic_report import DiagnosticReport
from app.services.retriever import retrieve_diagnostic_context
from app.services.patch_validator import validate_proposed_patch
from app.services.llm.interface import DiagnosticPromptInput, RawLLMDiagnosticOutput, LLMError
from app.services.llm.factory import get_llm_provider


def utc_now():
    return datetime.now(timezone.utc)


async def run_diagnosis_and_propose_patch(
    db: Session,
    job_id: str,
    allow_exploratory: bool = False,
    custom_instruction: Optional[str] = None,
    force_llm_provider: Optional[str] = None,
) -> DiagnosticReport:
    """
    Core pipeline:
    1. Verify baseline test execution failure.
    2. Retrieve relevant evidence & AST context.
    3. Invoke LLM diagnostic provider.
    4. Perform multi-layer patch security & syntax validation.
    5. Persist diagnostic report and proposal.
    """
    # 1. Verify Job and Repository
    job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
    if not job:
        raise ValueError(f"Execution job '{job_id}' not found.")

    repo = db.query(Repository).filter(Repository.id == job.repository_id).first()
    if not repo:
        raise ValueError(f"Repository for job '{job_id}' not found.")

    # Guard: Require failure evidence unless exploratory analysis explicitly allowed
    has_failures = (job.tests_failed > 0) or (job.tests_errors > 0) or (job.status in ("failed", "timed_out"))
    if not has_failures and not allow_exploratory:
        raise ValueError(
            "Baseline test execution passed with 0 failures. "
            "Diagnosis cannot be initiated without an observed failure record unless exploratory analysis is enabled."
        )

    # 2. Source & Evidence Retrieval
    diagnostic_context = retrieve_diagnostic_context(
        db=db,
        repository=repo,
        execution_job=job,
    )

    failure_summary = (
        f"Execution Job {job.id} failed with exit code {job.exit_code}. "
        f"Tests total: {job.tests_total}, Failed: {job.tests_failed}, Errors: {job.tests_errors}."
    )

    prompt_input = DiagnosticPromptInput(
        failure_summary=failure_summary,
        context_text=diagnostic_context.formatted_prompt,
        custom_instruction=custom_instruction,
    )

    # 3. LLM Diagnostic Invocation
    provider = get_llm_provider(force_provider=force_llm_provider)
    llm_output, duration = await provider.diagnose(prompt_input)

    # 4. Patch Validation (if diff proposed)
    patch_status = "valid"
    patch_errors: List[str] = []
    patch_hash = None
    affected_files: List[str] = []

    repo_root = Path(repo.storage_path).resolve()

    if llm_output.unified_diff and not llm_output.is_insufficient_evidence:
        # Retrieve list of eligible inventoried files for validation
        db_files = db.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repo.id,
            RepositoryFile.entry_type == "file",
        ).all()
        eligible_paths = [f.relative_path for f in db_files]

        val_result = validate_proposed_patch(
            repo_root=repo_root,
            unified_diff=llm_output.unified_diff,
            eligible_files=eligible_paths,
        )

        print(
            "PATCH VALIDATION DEBUG:",
            "status =", val_result.status,
            "errors =", val_result.errors,
            "affected_files =", val_result.affected_files,
            "repo_root =", repo_root,
            "eligible_files =", eligible_paths,
        )

        patch_status = val_result.status
        patch_errors = val_result.errors
        patch_hash = val_result.patch_hash
        affected_files = val_result.affected_files
    else:
        patch_status = "not_proposed" if llm_output.is_insufficient_evidence else "invalid"
        if not llm_output.unified_diff and not llm_output.is_insufficient_evidence:
            patch_errors.append("Model did not return a unified diff patch.")

    # 5. Persist Diagnostic Report
    report = DiagnosticReport(
        id=str(uuid.uuid4()),
        job_id=job.id,
        repository_id=repo.id,
        status="proposed",
        failure_summary=llm_output.failure_summary,
        root_cause_hypothesis=llm_output.root_cause_hypothesis,
        confidence_score=llm_output.confidence_score,
        confidence_explanation=llm_output.confidence_explanation,
        is_insufficient_evidence=llm_output.is_insufficient_evidence,
        insufficient_evidence_reason=llm_output.insufficient_evidence_reason,
        supporting_evidence=diagnostic_context.snippets and [
            {
                "file_path": s.file_path,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "description": s.reason,
                "snippet": s.content[:500],
            }
            for s in diagnostic_context.snippets
        ] or [],
        files_inspected=diagnostic_context.files_inspected,
        unified_diff=llm_output.unified_diff or "",
        patch_hash=patch_hash,
        affected_files=affected_files,
        patch_validation_status=patch_status,
        patch_validation_errors=patch_errors,
        potential_regression_risks=llm_output.potential_regression_risks,
        recommended_tests=llm_output.recommended_tests,
        known_limitations=llm_output.known_limitations,
        llm_provider=(
            f"groq/{provider.model}" if provider.__class__.__name__ == "GroqProvider"
            else (f"gemini/{provider.model}" if provider.__class__.__name__ == "GeminiProvider"
                  else "fake-provider")
        ),
        llm_duration_seconds=duration,
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return report


def approve_diagnostic_patch(
    db: Session,
    report_id: str,
    notes: Optional[str] = None,
) -> DiagnosticReport:
    """
    Idempotently marks a proposed patch as approved following human review.
    Enforces that invalid or security-rejected patches cannot be approved.
    """
    report = db.query(DiagnosticReport).filter(DiagnosticReport.id == report_id).first()
    if not report:
        raise ValueError(f"Diagnostic report '{report_id}' not found.")

    # Idempotent: already approved
    if report.status == "approved":
        return report

    if report.patch_validation_status != "valid":
        raise ValueError(
            f"Cannot approve patch with validation status '{report.patch_validation_status}'. "
            f"Errors: {', '.join(report.patch_validation_errors or [])}"
        )

    report.status = "approved"
    report.reviewed_at = utc_now()
    if notes:
        report.review_notes = notes
    db.commit()
    db.refresh(report)

    return report


def reject_diagnostic_patch(
    db: Session,
    report_id: str,
    reason: Optional[str] = None,
) -> DiagnosticReport:
    """
    Marks a proposed patch as rejected following human review.
    """
    report = db.query(DiagnosticReport).filter(DiagnosticReport.id == report_id).first()
    if not report:
        raise ValueError(f"Diagnostic report '{report_id}' not found.")

    report.status = "rejected"
    report.reviewed_at = utc_now()
    if reason:
        report.review_notes = reason
    db.commit()
    db.refresh(report)

    return report

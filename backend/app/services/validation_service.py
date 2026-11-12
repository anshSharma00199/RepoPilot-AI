import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.execution_job import ExecutionJob
from app.models.diagnostic_report import DiagnosticReport
from app.models.validation_run import ValidationRun
from app.services.patch_applier import (
    create_isolated_snapshot,
    apply_approved_patch_to_snapshot,
    compute_workspace_hash,
    cleanup_snapshot,
    PatchApplicationError,
)
from app.services.verdict_engine import (
    Verdict,
    VerdictReason,
    VerdictEvaluationResult,
    evaluate_verdict,
    extract_executed_test_names,
)
from app.services.test_discovery import discover_test_setup
from app.worker.interface import ExecutionConfig, ExecutionResult
from app.worker.factory import get_worker


def utc_now():
    return datetime.now(timezone.utc)


async def trigger_patch_validation(
    db: Session,
    diagnostic_id: str,
    custom_command: Optional[List[str]] = None,
) -> ValidationRun:
    """
    Main Day 4 Pipeline:
    1. Verifies patch ownership, approval status, and patch hash.
    2. Enforces baseline failure reproduction invariant.
    3. Manages bounded retry budget (max 2 attempts).
    4. Creates an isolated working snapshot and applies approved patch.
    5. Executes patched tests in an isolated, fresh sandbox container.
    6. Evaluates execution evidence via central Verdict Engine.
    7. Generates and persists complete final evidence report.
    """
    # 1. Fetch Diagnostic Report and verify approval
    report = db.query(DiagnosticReport).filter(DiagnosticReport.id == diagnostic_id).first()
    if not report:
        raise ValueError(f"Diagnostic report '{diagnostic_id}' not found.")

    if report.status != "approved":
        raise ValueError(
            f"Cannot validate patch with review status '{report.status}'. "
            f"A patch must be explicitly approved by human review before execution."
        )

    if report.patch_validation_status != "valid":
        raise ValueError(
            f"Cannot validate patch with validation status '{report.patch_validation_status}'. "
            f"Errors: {', '.join(report.patch_validation_errors or [])}"
        )

    # 2. Fetch Baseline Job & Repository
    baseline_job = db.query(ExecutionJob).filter(ExecutionJob.id == report.job_id).first()
    if not baseline_job:
        raise ValueError(f"Baseline execution job '{report.job_id}' not found.")

    repo = db.query(Repository).filter(Repository.id == report.repository_id).first()
    if not repo:
        raise ValueError(f"Repository for diagnostic report '{diagnostic_id}' not found.")

    # Invariant: Confirm that baseline evidence contains a reproduced failure
    baseline_had_failures = (
        (baseline_job.tests_failed > 0)
        or (baseline_job.tests_errors > 0)
        or (baseline_job.status in ("failed", "timed_out"))
    )
    if settings.REQUIRE_REPRODUCED_FAILURE and not baseline_had_failures:
        # Scenario D: Baseline passed before patch -> no reproduced bug -> no validated-fix claim
        # We record an unvalidated run immediately
        verdict_res = evaluate_verdict(
            baseline_job=baseline_job,
            patched_job=None,
            diagnostic=report,
            patch_applied_successfully=True,
        )
        val_run = ValidationRun(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            baseline_job_id=baseline_job.id,
            diagnostic_report_id=report.id,
            patched_job_id=None,
            completed_at=utc_now(),
            patch_version=1,
            patch_hash=report.patch_hash or "none",
            workspace_hash="none",
            affected_files=report.affected_files or [],
            verdict=verdict_res.verdict.value,
            verdict_reason_code=verdict_res.reason_code.value,
            verdict_explanation=verdict_res.explanation,
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
            baseline_tests_total=baseline_job.tests_total,
            baseline_tests_passed=baseline_job.tests_passed,
            baseline_tests_failed=baseline_job.tests_failed,
            attempt_number=1,
            max_attempts=settings.MAX_PATCH_ATTEMPTS,
            is_retry_budget_exhausted=False,
            final_evidence_report=_build_final_report_dict(
                repo=repo,
                baseline_job=baseline_job,
                patched_job=None,
                diagnostic=report,
                verdict_res=verdict_res,
                patch_version=1,
                workspace_hash="none",
                attempt_number=1,
                max_attempts=settings.MAX_PATCH_ATTEMPTS,
            ),
        )
        db.add(val_run)
        db.commit()
        db.refresh(val_run)
        return val_run

    # 3. Bounded Retry Budget Check
    prior_runs = (
        db.query(ValidationRun)
        .filter(ValidationRun.baseline_job_id == baseline_job.id)
        .order_by(ValidationRun.attempt_number)
        .all()
    )
    attempt_number = len(prior_runs) + 1
    max_attempts = settings.MAX_PATCH_ATTEMPTS

    if attempt_number > max_attempts:
        raise ValueError(
            f"Retry budget exhausted: maximum of {max_attempts} validation attempts reached for baseline job '{baseline_job.id}'."
        )

    is_retry_budget_exhausted = (attempt_number >= max_attempts)

    # 4. Create Isolated Working Snapshot & Apply Patch
    snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
    repo_storage = Path(repo.storage_path).resolve()
    snapshot_dir = create_isolated_snapshot(repo_storage, snapshot_id)

    # Eligible files check
    db_files = db.query(RepositoryFile).filter(
        RepositoryFile.repository_id == repo.id,
        RepositoryFile.entry_type == "file",
    ).all()
    eligible_paths = [f.relative_path for f in db_files]

    patch_applied = False
    patch_app_err = None
    workspace_hash = ""
    written_files = []

    try:
        patch_applied, written_files, workspace_hash = apply_approved_patch_to_snapshot(
            snapshot_dir=snapshot_dir,
            unified_diff=report.unified_diff,
            eligible_files=eligible_paths,
            expected_patch_hash=report.patch_hash,
        )
    except PatchApplicationError as pae:
        patch_applied = False
        patch_app_err = str(pae)

    # If patch application failed, evaluate immediately
    if not patch_applied:
        cleanup_snapshot(snapshot_id)
        verdict_res = evaluate_verdict(
            baseline_job=baseline_job,
            patched_job=None,
            diagnostic=report,
            patch_applied_successfully=False,
            patch_application_error=patch_app_err,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
        )
        val_run = ValidationRun(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            baseline_job_id=baseline_job.id,
            diagnostic_report_id=report.id,
            patched_job_id=None,
            completed_at=utc_now(),
            patch_version=attempt_number,
            patch_hash=report.patch_hash or "none",
            workspace_hash="none",
            affected_files=report.affected_files or [],
            verdict=verdict_res.verdict.value,
            verdict_reason_code=verdict_res.reason_code.value,
            verdict_explanation=verdict_res.explanation,
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
            baseline_tests_total=baseline_job.tests_total,
            baseline_tests_passed=baseline_job.tests_passed,
            baseline_tests_failed=baseline_job.tests_failed,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            is_retry_budget_exhausted=is_retry_budget_exhausted,
            final_evidence_report=_build_final_report_dict(
                repo=repo,
                baseline_job=baseline_job,
                patched_job=None,
                diagnostic=report,
                verdict_res=verdict_res,
                patch_version=attempt_number,
                workspace_hash="none",
                attempt_number=attempt_number,
                max_attempts=max_attempts,
            ),
        )
        db.add(val_run)
        db.commit()
        db.refresh(val_run)
        return val_run

    # 5. Create fresh ExecutionJob for Patched Run
    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        status="pending",
        stage="preparing",
        command=custom_command or baseline_job.command or [],
        image_version=baseline_job.image_version,
        timeout_seconds=settings.VALIDATION_TIMEOUT_SECONDS,
        cpu_limit=baseline_job.cpu_limit,
        memory_limit=baseline_job.memory_limit,
    )
    db.add(patched_job)
    db.commit()
    db.refresh(patched_job)

    # 6. Run Worker in fresh isolated environment from snapshot
    worker = get_worker()
    test_discovery = discover_test_setup(snapshot_dir)
    final_cmd = patched_job.command if patched_job.command else test_discovery.command
    patched_job.command = final_cmd

    config = ExecutionConfig(
        job_id=patched_job.id,
        repository_id=repo.id,
        workspace_dir=snapshot_dir,
        command=final_cmd,
        setup_command=test_discovery.setup_command,
        timeout_seconds=patched_job.timeout_seconds,
        setup_timeout_seconds=settings.SETUP_TIMEOUT_SECONDS,
        cpu_limit=patched_job.cpu_limit,
        memory_limit=patched_job.memory_limit,
        pids_limit=settings.EXECUTION_PIDS_LIMIT,
        base_image=patched_job.image_version,
        network_enabled_for_tests=False,
    )

    patched_job.started_at = utc_now()
    patched_job.stage = "executing_tests"
    patched_job.status = "running"
    db.commit()

    exec_result: ExecutionResult = await worker.execute(config)

    # Update patched job with execution results
    patched_job.status = exec_result.status
    patched_job.completed_at = utc_now()
    patched_job.stage = "finished"
    patched_job.duration_seconds = exec_result.duration_seconds
    patched_job.exit_code = exec_result.exit_code
    patched_job.timed_out = exec_result.timed_out
    patched_job.error_type = exec_result.error_type
    patched_job.error_message = exec_result.error_message
    patched_job.tests_total = exec_result.tests_total
    patched_job.tests_passed = exec_result.tests_passed
    patched_job.tests_failed = exec_result.tests_failed
    patched_job.tests_skipped = exec_result.tests_skipped
    patched_job.tests_errors = exec_result.tests_errors
    patched_job.failures = exec_result.failures
    patched_job.stdout = exec_result.stdout
    patched_job.stderr = exec_result.stderr
    patched_job.setup_logs = exec_result.setup_logs
    db.commit()

    # Clean up candidate working snapshot
    cleanup_snapshot(snapshot_id)

    # 7. Central Verdict Evaluation
    verdict_res: VerdictEvaluationResult = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=report,
        patch_applied_successfully=True,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
    )

    # 8. Assemble Complete Final Evidence Report
    final_report = _build_final_report_dict(
        repo=repo,
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=report,
        verdict_res=verdict_res,
        patch_version=attempt_number,
        workspace_hash=workspace_hash,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
    )

    # 9. Persist ValidationRun Record
    val_run = ValidationRun(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        baseline_job_id=baseline_job.id,
        diagnostic_report_id=report.id,
        patched_job_id=patched_job.id,
        completed_at=utc_now(),
        patch_version=attempt_number,
        patch_hash=report.patch_hash or "none",
        workspace_hash=workspace_hash,
        affected_files=report.affected_files or written_files,
        verdict=verdict_res.verdict.value,
        verdict_reason_code=verdict_res.reason_code.value,
        verdict_explanation=verdict_res.explanation,
        target_test_name=verdict_res.target_test_name,
        target_test_passed=verdict_res.target_test_passed,
        regression_tests_passed=verdict_res.regression_tests_passed,
        baseline_tests_total=baseline_job.tests_total,
        baseline_tests_passed=baseline_job.tests_passed,
        baseline_tests_failed=baseline_job.tests_failed,
        patched_tests_total=patched_job.tests_total,
        patched_tests_passed=patched_job.tests_passed,
        patched_tests_failed=patched_job.tests_failed,
        patched_tests_errors=patched_job.tests_errors,
        patched_tests_skipped=patched_job.tests_skipped,
        duration_seconds=patched_job.duration_seconds or 0.0,
        tests_executed_before=verdict_res.tests_executed_before,
        tests_executed_after=verdict_res.tests_executed_after,
        target_tests_resolved=verdict_res.target_tests_resolved,
        new_regressions=verdict_res.new_regressions,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        is_retry_budget_exhausted=is_retry_budget_exhausted,
        final_evidence_report=final_report,
    )

    db.add(val_run)
    db.commit()
    db.refresh(val_run)

    return val_run


def _build_final_report_dict(
    repo: Repository,
    baseline_job: ExecutionJob,
    patched_job: Optional[ExecutionJob],
    diagnostic: DiagnosticReport,
    verdict_res: VerdictEvaluationResult,
    patch_version: int,
    workspace_hash: str,
    attempt_number: int,
    max_attempts: int,
) -> Dict[str, Any]:
    """
    Builds the structured final evidence report dictionary.
    Separates model-generated explanations from measured test metrics.
    """
    baseline_summary = {
        "job_id": baseline_job.id,
        "status": baseline_job.status,
        "exit_code": baseline_job.exit_code,
        "duration_seconds": baseline_job.duration_seconds,
        "tests_total": baseline_job.tests_total,
        "tests_passed": baseline_job.tests_passed,
        "tests_failed": baseline_job.tests_failed,
        "tests_errors": baseline_job.tests_errors,
        "failures": baseline_job.failures or [],
    }

    patched_summary = {}
    if patched_job:
        patched_summary = {
            "job_id": patched_job.id,
            "status": patched_job.status,
            "exit_code": patched_job.exit_code,
            "duration_seconds": patched_job.duration_seconds,
            "tests_total": patched_job.tests_total,
            "tests_passed": patched_job.tests_passed,
            "tests_failed": patched_job.tests_failed,
            "tests_errors": patched_job.tests_errors,
            "failures": patched_job.failures or [],
        }

    ai_diagnosis_summary = {
        "diagnostic_report_id": diagnostic.id,
        "llm_provider": diagnostic.llm_provider,
        "llm_duration_seconds": diagnostic.llm_duration_seconds,
        "hypothesis": diagnostic.root_cause_hypothesis,
        "confidence_score": diagnostic.confidence_score,
        "confidence_explanation": diagnostic.confidence_explanation,
        "files_inspected": diagnostic.files_inspected or [],
        "supporting_evidence": diagnostic.supporting_evidence or [],
        "label": "AI-Generated Explanation (Subject to Validation)",
    }

    patch_summary = {
        "patch_version": patch_version,
        "patch_hash": diagnostic.patch_hash,
        "workspace_hash": workspace_hash,
        "affected_files": diagnostic.affected_files or [],
        "unified_diff": diagnostic.unified_diff,
        "patch_validation_status": diagnostic.patch_validation_status,
        "review_status": diagnostic.status,
        "reviewer_notes": diagnostic.review_notes,
    }

    test_comparison = {
        "target_test_name": verdict_res.target_test_name,
        "target_test_passed": verdict_res.target_test_passed,
        "regression_tests_passed": verdict_res.regression_tests_passed,
        "tests_executed_before": verdict_res.tests_executed_before,
        "tests_executed_after": verdict_res.tests_executed_after,
        "target_tests_resolved": verdict_res.target_tests_resolved,
        "new_regressions": verdict_res.new_regressions,
    }

    environment_metadata = {
        "base_image": baseline_job.image_version,
        "cpu_limit": baseline_job.cpu_limit,
        "memory_limit": baseline_job.memory_limit,
        "timeout_seconds": settings.VALIDATION_TIMEOUT_SECONDS,
        "network_policy": "disabled (--network=none)",
        "isolation": "Non-root container with dropped capabilities and tmpfs",
    }

    limitations = [
        "Passing available regression tests demonstrates empirical fix stability but does not prove elimination of unexercised edge cases.",
        "Container isolation provides process boundary defense but does not replace formal verification.",
    ]
    if diagnostic.known_limitations:
        limitations.append(f"Model Limitation: {diagnostic.known_limitations}")

    retry_history = [
        {
            "attempt_number": attempt_number,
            "max_attempts": max_attempts,
            "is_retry_budget_exhausted": (attempt_number >= max_attempts),
        }
    ]

    return {
        "validation_run_id": "",  # Set by caller
        "repository_id": repo.id,
        "repository_name": repo.name,
        "baseline_job_id": baseline_job.id,
        "patched_job_id": patched_job.id if patched_job else None,
        "verdict": verdict_res.verdict.value,
        "verdict_reason_code": verdict_res.reason_code.value,
        "verdict_explanation": verdict_res.explanation,
        "baseline_summary": baseline_summary,
        "patched_summary": patched_summary,
        "ai_diagnosis_summary": ai_diagnosis_summary,
        "patch_summary": patch_summary,
        "test_comparison": test_comparison,
        "environment_metadata": environment_metadata,
        "limitations_and_caveats": limitations,
        "retry_history": retry_history,
    }

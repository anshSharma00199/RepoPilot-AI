from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.diagnostic_report import DiagnosticReport
from app.schemas.diagnostic import (
    DiagnosticRequest,
    DiagnosticApprovalRequest,
    DiagnosticRejectionRequest,
    DiagnosticResponse,
    DiagnosticListResponse,
    EvidenceReference,
)
from app.services.diagnostic_service import (
    run_diagnosis_and_propose_patch,
    approve_diagnostic_patch,
    reject_diagnostic_patch,
)
from app.services.llm.interface import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidOutputError,
)

router = APIRouter(tags=["Diagnostics"])


def _to_diagnostic_response(report: DiagnosticReport) -> DiagnosticResponse:
    ev_list = []
    if report.supporting_evidence:
        for ev in report.supporting_evidence:
            if isinstance(ev, dict):
                ev_list.append(
                    EvidenceReference(
                        file_path=ev.get("file_path", ""),
                        line_start=ev.get("line_start", 1),
                        line_end=ev.get("line_end", 1),
                        description=ev.get("description", ""),
                        snippet=ev.get("snippet", ""),
                    )
                )
            elif isinstance(ev, EvidenceReference):
                ev_list.append(ev)

    return DiagnosticResponse(
        id=report.id,
        job_id=report.job_id,
        repository_id=report.repository_id,
        created_at=report.created_at,
        updated_at=report.updated_at,
        reviewed_at=report.reviewed_at,
        status=report.status,
        review_notes=report.review_notes,
        failure_summary=report.failure_summary,
        root_cause_hypothesis=report.root_cause_hypothesis,
        confidence_score=report.confidence_score,
        confidence_explanation=report.confidence_explanation,
        is_insufficient_evidence=report.is_insufficient_evidence,
        insufficient_evidence_reason=report.insufficient_evidence_reason,
        supporting_evidence=ev_list,
        files_inspected=report.files_inspected or [],
        unified_diff=report.unified_diff or "",
        patch_hash=report.patch_hash,
        affected_files=report.affected_files or [],
        patch_validation_status=report.patch_validation_status,
        patch_validation_errors=report.patch_validation_errors or [],
        potential_regression_risks=report.potential_regression_risks,
        recommended_tests=report.recommended_tests,
        known_limitations=report.known_limitations,
        llm_provider=report.llm_provider,
        llm_duration_seconds=report.llm_duration_seconds or 0.0,
    )


@router.post("/jobs/{job_id}/diagnose", response_model=DiagnosticResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnosis(
    job_id: str,
    request: DiagnosticRequest = DiagnosticRequest(),
    db: Session = Depends(get_db),
):
    """
    Trigger automated AI diagnosis and safe patch generation for a failed execution job.
    Requires baseline test execution failures unless allow_exploratory is True.
    """
    try:
        report = await run_diagnosis_and_propose_patch(
            db=db,
            job_id=job_id,
            allow_exploratory=request.allow_exploratory,
            custom_instruction=request.custom_instruction,
        )
        return _to_diagnostic_response(report)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except LLMRateLimitError as rle:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI Provider Rate Limit: {str(rle)}",
        )
    except LLMTimeoutError as te:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"AI Provider Timeout: {str(te)}",
        )
    except (LLMInvalidOutputError, LLMError) as le:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Provider Error: {str(le)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic error: {str(e)}",
        )


@router.get("/diagnostics/{id}", response_model=DiagnosticResponse)
def get_diagnostic(
    id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve a diagnostic report by its unique ID.
    """
    report = db.query(DiagnosticReport).filter(DiagnosticReport.id == id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Diagnostic report '{id}' not found.")
    return _to_diagnostic_response(report)


@router.get("/jobs/{job_id}/diagnostics", response_model=DiagnosticListResponse)
def get_job_diagnostics(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    List all diagnostic reports generated for a specific execution job.
    """
    reports = (
        db.query(DiagnosticReport)
        .filter(DiagnosticReport.job_id == job_id)
        .order_by(desc(DiagnosticReport.created_at))
        .all()
    )
    return DiagnosticListResponse(
        total=len(reports),
        items=[_to_diagnostic_response(r) for r in reports],
    )


@router.get("/repositories/{repo_id}/diagnostics", response_model=DiagnosticListResponse)
def get_repository_diagnostics(
    repo_id: str,
    db: Session = Depends(get_db),
):
    """
    List all diagnostic reports generated across all jobs for a repository.
    """
    reports = (
        db.query(DiagnosticReport)
        .filter(DiagnosticReport.repository_id == repo_id)
        .order_by(desc(DiagnosticReport.created_at))
        .all()
    )
    return DiagnosticListResponse(
        total=len(reports),
        items=[_to_diagnostic_response(r) for r in reports],
    )


@router.post("/diagnostics/{id}/approve", response_model=DiagnosticResponse)
def approve_patch(
    id: str,
    req: DiagnosticApprovalRequest = DiagnosticApprovalRequest(),
    db: Session = Depends(get_db),
):
    """
    Human-in-the-loop: Approve a proposed patch.
    Only patches with status 'valid' can be approved.
    """
    try:
        report = approve_diagnostic_patch(db=db, report_id=id, notes=req.notes)
        return _to_diagnostic_response(report)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post("/diagnostics/{id}/reject", response_model=DiagnosticResponse)
def reject_patch(
    id: str,
    req: DiagnosticRejectionRequest = DiagnosticRejectionRequest(),
    db: Session = Depends(get_db),
):
    """
    Human-in-the-loop: Reject a proposed patch with optional reason.
    """
    try:
        report = reject_diagnostic_patch(db=db, report_id=id, reason=req.reason)
        return _to_diagnostic_response(report)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

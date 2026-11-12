from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.validation_run import ValidationRun
from app.schemas.validation import (
    ValidationRunRequest,
    ValidationRunResponse,
    ValidationListResponse,
    FinalEvidenceReportResponse,
)
from app.services.validation_service import trigger_patch_validation

router = APIRouter(tags=["Validations"])


def _to_validation_response(val: ValidationRun) -> ValidationRunResponse:
    return ValidationRunResponse(
        id=val.id,
        repository_id=val.repository_id,
        baseline_job_id=val.baseline_job_id,
        diagnostic_report_id=val.diagnostic_report_id,
        patched_job_id=val.patched_job_id,
        created_at=val.created_at,
        completed_at=val.completed_at,
        patch_version=val.patch_version,
        patch_hash=val.patch_hash,
        workspace_hash=val.workspace_hash,
        affected_files=val.affected_files or [],
        verdict=val.verdict,
        verdict_reason_code=val.verdict_reason_code,
        verdict_explanation=val.verdict_explanation,
        target_test_name=val.target_test_name,
        target_test_passed=val.target_test_passed,
        regression_tests_passed=val.regression_tests_passed,
        baseline_tests_total=val.baseline_tests_total,
        baseline_tests_passed=val.baseline_tests_passed,
        baseline_tests_failed=val.baseline_tests_failed,
        patched_tests_total=val.patched_tests_total,
        patched_tests_passed=val.patched_tests_passed,
        patched_tests_failed=val.patched_tests_failed,
        patched_tests_errors=val.patched_tests_errors,
        patched_tests_skipped=val.patched_tests_skipped,
        duration_seconds=val.duration_seconds or 0.0,
        tests_executed_before=val.tests_executed_before or [],
        tests_executed_after=val.tests_executed_after or [],
        target_tests_resolved=val.target_tests_resolved or [],
        new_regressions=val.new_regressions or [],
        attempt_number=val.attempt_number,
        max_attempts=val.max_attempts,
        is_retry_budget_exhausted=val.is_retry_budget_exhausted,
    )


@router.post(
    "/diagnostics/{diagnostic_id}/validate",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def validate_patch(
    diagnostic_id: str,
    request: ValidationRunRequest = ValidationRunRequest(),
    db: Session = Depends(get_db),
):
    """
    Triggers real isolated validation of an approved patch in a fresh sandbox container.
    Enforces baseline failure reproduction invariant and evaluates central Verdict.
    """
    try:
        val_run = await trigger_patch_validation(
            db=db,
            diagnostic_id=diagnostic_id,
            custom_command=request.custom_command,
        )
        return _to_validation_response(val_run)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation orchestration error: {str(e)}",
        )


@router.get("/validations/{id}", response_model=ValidationRunResponse)
def get_validation_run(
    id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve validation run record by its unique ID.
    """
    val = db.query(ValidationRun).filter(ValidationRun.id == id).first()
    if not val:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Validation run '{id}' not found.")
    return _to_validation_response(val)


@router.get("/jobs/{job_id}/validations", response_model=ValidationListResponse)
def get_job_validations(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    List all validation attempts and outcomes associated with a baseline execution job.
    """
    runs = (
        db.query(ValidationRun)
        .filter(ValidationRun.baseline_job_id == job_id)
        .order_by(desc(ValidationRun.created_at))
        .all()
    )
    return ValidationListResponse(
        total=len(runs),
        items=[_to_validation_response(r) for r in runs],
    )


@router.get("/repositories/{repo_id}/validations", response_model=ValidationListResponse)
def get_repository_validations(
    repo_id: str,
    db: Session = Depends(get_db),
):
    """
    List all validation runs across all jobs for a repository.
    """
    runs = (
        db.query(ValidationRun)
        .filter(ValidationRun.repository_id == repo_id)
        .order_by(desc(ValidationRun.created_at))
        .all()
    )
    return ValidationListResponse(
        total=len(runs),
        items=[_to_validation_response(r) for r in runs],
    )


@router.get("/validations/{id}/report", response_model=FinalEvidenceReportResponse)
def get_final_evidence_report(
    id: str,
    db: Session = Depends(get_db),
):
    """
    Generates and returns the complete final evidence report for a validation run.
    Contains segregated sections: measured test results, model hypotheses, diff, and environment metadata.
    """
    val = db.query(ValidationRun).filter(ValidationRun.id == id).first()
    if not val:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Validation run '{id}' not found.")

    report_dict = val.final_evidence_report or {}
    report_dict["validation_run_id"] = val.id

    return FinalEvidenceReportResponse(
        validation_run_id=val.id,
        repository_id=val.repository_id,
        repository_name=report_dict.get("repository_name", "unknown"),
        baseline_job_id=val.baseline_job_id,
        patched_job_id=val.patched_job_id,
        created_at=val.created_at,
        completed_at=val.completed_at,
        verdict=val.verdict,
        verdict_reason_code=val.verdict_reason_code,
        verdict_explanation=val.verdict_explanation,
        baseline_summary=report_dict.get("baseline_summary", {}),
        patched_summary=report_dict.get("patched_summary", {}),
        test_comparison=report_dict.get("test_comparison", {}),
        ai_diagnosis_summary=report_dict.get("ai_diagnosis_summary", {}),
        patch_summary=report_dict.get("patch_summary", {}),
        environment_metadata=report_dict.get("environment_metadata", {}),
        limitations_and_caveats=report_dict.get("limitations_and_caveats", []),
        retry_history=report_dict.get("retry_history", []),
    )

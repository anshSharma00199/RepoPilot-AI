import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.repository_file import RepositoryFile
from app.models.execution_job import ExecutionJob
from app.schemas.repository import RepositoryResponse, RepositoryDetailResponse, RepositoryListResponse
from app.schemas.scan_job import ScanJobResponse
from app.schemas.execution_job import ExecutionJobResponse, ExecutionJobListResponse, TestFailureDetail
from app.schemas.common import ErrorResponse
from app.services.security import SecurityValidationError
from app.services.archive import save_and_extract_upload, delete_repository_storage
from app.services.analyzer import RepositoryAnalyzer

from app.schemas.audit import AnalysisAuditSummary
from app.services.audit_service import generate_analysis_audit

router = APIRouter(prefix="/repositories", tags=["Repositories"])


def _to_scan_job_response(scan: Optional[ScanJob]) -> Optional[ScanJobResponse]:
    if not scan:
        return None
    return ScanJobResponse(
        id=scan.id,
        repository_id=scan.repository_id,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        status=scan.status,
        total_files=scan.total_files or 0,
        total_directories=scan.total_directories or 0,
        total_size_bytes=scan.total_size_bytes or 0,
        supported_source_files=scan.supported_source_files or 0,
        test_files=scan.test_files or 0,
        manifest_files=scan.manifest_files or 0,
        skipped_files=scan.skipped_files or 0,
        parse_errors=scan.parse_errors or 0,
        detected_frameworks=scan.detected_frameworks or [],
        detected_manifests=scan.detected_manifests or [],
        error_details=scan.error_details,
    )


def _to_repository_response(repo: Repository, latest_scan: Optional[ScanJob] = None) -> RepositoryResponse:
    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        original_filename=repo.original_filename,
        upload_size_bytes=repo.upload_size_bytes,
        status=repo.status,
        error_message=repo.error_message,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
        latest_scan=_to_scan_job_response(latest_scan),
    )


@router.post(
    "/upload",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation or security error (malformed zip, traversal, bomb, size exceeded)"},
        500: {"model": ErrorResponse, "description": "Internal server processing error"},
    },
)
async def upload_repository(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accepts a ZIP repository upload, validates archive safety (traversal, bomb limits, symlinks),
    persists repository metadata, and runs an immediate recursive scan and inventory.
    """
    filename = file.filename or "unknown.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_FILE_TYPE",
                "message": "Only ZIP archives are supported.",
                "details": {"filename": filename},
            },
        )

    repo_id = str(uuid.uuid4())
    repo_name = os.path.splitext(filename)[0]

    try:
        # Step 1: Save upload safely & extract with security checks
        zip_path, extracted_dir, upload_size = await save_and_extract_upload(file, repo_id)
    except SecurityValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": e.error_code,
                "message": e.message,
                "details": e.details,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "EXTRACTION_FAILED",
                "message": f"Failed to extract archive: {str(e)}",
                "details": {},
            },
        )

    # Step 2: Create Repository record
    repo = Repository(
        id=repo_id,
        name=repo_name,
        original_filename=filename,
        storage_path=str(extracted_dir),
        upload_size_bytes=upload_size,
        status="analyzing",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Step 3: Run Repository Analyzer
    scan_job = ScanJob(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        status="running",
    )
    db.add(scan_job)
    db.commit()

    try:
        analyzer = RepositoryAnalyzer(extracted_dir)
        db_file_objects = []

        for entry in analyzer.scan_generator():
            file_rec = RepositoryFile(
                id=str(uuid.uuid4()),
                repository_id=repo.id,
                scan_job_id=scan_job.id,
                relative_path=entry["relative_path"],
                entry_type=entry["entry_type"],
                language=entry["language"],
                file_size_bytes=entry["file_size_bytes"],
                file_hash=entry["file_hash"],
                classification=entry["classification"],
                status=entry["status"],
                skip_reason=entry["skip_reason"],
                is_test=entry["is_test"],
                is_manifest=entry["is_manifest"],
                ast_metadata=entry["ast_metadata"],
            )
            db_file_objects.append(file_rec)

        # Bulk save repository file records
        db.bulk_save_objects(db_file_objects)

        # Update ScanJob metrics
        m = analyzer.metrics
        scan_job.status = "completed"
        scan_job.completed_at = datetime.now(timezone.utc)
        scan_job.total_files = m["total_files"]
        scan_job.total_directories = m["total_directories"]
        scan_job.total_size_bytes = m["total_size_bytes"]
        scan_job.supported_source_files = m["supported_source_files"]
        scan_job.test_files = m["test_files"]
        scan_job.manifest_files = m["manifest_files"]
        scan_job.skipped_files = m["skipped_files"]
        scan_job.parse_errors = m["parse_errors"]
        scan_job.detected_frameworks = sorted(list(m["detected_frameworks"]))
        scan_job.detected_manifests = sorted(list(m["detected_manifests"]))

        repo.status = "completed"
        db.commit()
        db.refresh(repo)
        db.refresh(scan_job)

        return _to_repository_response(repo, scan_job)

    except Exception as e:
        db.rollback()
        repo.status = "failed"
        repo.error_message = str(e)
        scan_job.status = "failed"
        scan_job.error_details = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "ANALYSIS_FAILED",
                "message": f"Repository analysis failed: {str(e)}",
                "details": {},
            },
        )


@router.get("", response_model=RepositoryListResponse)
def list_repositories(db: Session = Depends(get_db)):
    """Lists all repositories with their latest scan job summary."""
    repos = db.query(Repository).order_by(desc(Repository.created_at)).all()
    results = []
    for r in repos:
        latest_scan = (
            db.query(ScanJob)
            .filter(ScanJob.repository_id == r.id)
            .order_by(desc(ScanJob.started_at))
            .first()
        )
        results.append(_to_repository_response(r, latest_scan))
    return RepositoryListResponse(total=len(results), items=results)


@router.get("/{repo_id}", response_model=RepositoryDetailResponse)
def get_repository(repo_id: str, db: Session = Depends(get_db)):
    """Gets details for a specific repository including its scan history."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    scans = (
        db.query(ScanJob)
        .filter(ScanJob.repository_id == repo.id)
        .order_by(desc(ScanJob.started_at))
        .all()
    )
    latest_scan = scans[0] if scans else None
    resp = _to_repository_response(repo, latest_scan)

    return RepositoryDetailResponse(
        id=resp.id,
        name=resp.name,
        original_filename=resp.original_filename,
        upload_size_bytes=resp.upload_size_bytes,
        status=resp.status,
        error_message=resp.error_message,
        created_at=resp.created_at,
        updated_at=resp.updated_at,
        latest_scan=resp.latest_scan,
        recent_scans=[_to_scan_job_response(s) for s in scans if s],
    )


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(repo_id: str, db: Session = Depends(get_db)):
    """Deletes repository metadata and clears stored files on disk."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    delete_repository_storage(repo.id)
    db.delete(repo)
    db.commit()
    return None


@router.get("/{repo_id}/jobs", response_model=ExecutionJobListResponse)
def list_repository_jobs(repo_id: str, db: Session = Depends(get_db)):
    """Lists all baseline test execution jobs for a specific repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    jobs = (
        db.query(ExecutionJob)
        .filter(ExecutionJob.repository_id == repo_id)
        .order_by(desc(ExecutionJob.created_at))
        .all()
    )

    items = []
    for job in jobs:
        failures_list = []
        if job.failures:
            for f in job.failures:
                failures_list.append(
                    TestFailureDetail(
                        test_name=f.get("test_name", "unknown"),
                        file=f.get("file"),
                        line=f.get("line"),
                        traceback=f.get("traceback", ""),
                    )
                )

        items.append(
            ExecutionJobResponse(
                id=job.id,
                repository_id=job.repository_id,
                status=job.status,
                stage=job.stage,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
                error_type=job.error_type,
                error_message=job.error_message,
                command=job.command or [],
                image_version=job.image_version,
                exit_code=job.exit_code,
                timed_out=job.timed_out,
                tests_total=job.tests_total,
                tests_passed=job.tests_passed,
                tests_failed=job.tests_failed,
                tests_skipped=job.tests_skipped,
                tests_errors=job.tests_errors,
                failures=failures_list,
                cpu_limit=job.cpu_limit,
                memory_limit=job.memory_limit,
                timeout_seconds=job.timeout_seconds,
            )
        )

    return ExecutionJobListResponse(total=len(items), items=items)


@router.get("/{repo_id}/analysis-audit", response_model=AnalysisAuditSummary)
def get_repository_analysis_audit(repo_id: str, db: Session = Depends(get_db)):
    """
    Returns a comprehensive repository analysis coverage summary and audit report.
    Reports discovered files/dirs, AST successes/failures, policy exclusions,
    and enforces that coverage is never 100% if any files were skipped or unsupported.
    """
    try:
        return generate_analysis_audit(db, repo_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": str(e)},
        )



import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.repository import Repository
from app.models.execution_job import ExecutionJob
from app.schemas.execution_job import (
    JobCreateRequest,
    ExecutionJobResponse,
    ExecutionJobLogsResponse,
    ExecutionJobListResponse,
    TestFailureDetail,
)
from app.schemas.common import ErrorResponse
from app.services.executor import create_execution_job, run_job_in_background, cleanup_job_workspace
from app.worker.factory import get_worker

router = APIRouter(prefix="/jobs", tags=["Execution Jobs"])


def _to_job_response(job: ExecutionJob) -> ExecutionJobResponse:
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

    return ExecutionJobResponse(
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


_job_creation_lock = asyncio.Lock()


@router.post(
    "",
    response_model=ExecutionJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid parameters or command validation error"},
        404: {"model": ErrorResponse, "description": "Repository not found"},
    },
)
async def create_job(
    req: JobCreateRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submits a repository for baseline test execution.
    Creates an isolated execution record and dispatches background test worker.
    Never executes repository code directly in the FastAPI server process.
    """
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    # Concurrency-safe handling of duplicate requests: return existing active job if currently in-flight
    async with _job_creation_lock:
        active_job = (
            db.query(ExecutionJob)
            .filter(
                ExecutionJob.repository_id == req.repository_id,
                ExecutionJob.status.in_(["pending", "preparing", "running"]),
            )
            .order_by(desc(ExecutionJob.created_at))
            .first()
        )
        if active_job:
            response.status_code = status.HTTP_200_OK
            return _to_job_response(active_job)

        try:
            job = create_execution_job(
                db=db,
                repository=repo,
                command=req.command,
                timeout_seconds=req.timeout_seconds,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_COMMAND", "message": str(e)},
            )

        # Dispatch background task asynchronously so the active job is returned immediately
        asyncio.create_task(run_job_in_background(job.id))

        return _to_job_response(job)


@router.get("/{job_id}", response_model=ExecutionJobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieves current execution status, stage, test counts, and failure tracebacks."""
    job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "JOB_NOT_FOUND", "message": "Execution job not found."},
        )
    return _to_job_response(job)


@router.get("/{job_id}/logs", response_model=ExecutionJobLogsResponse)
def get_job_logs(job_id: str, db: Session = Depends(get_db)):
    """Returns bounded, sanitized stdout, stderr, and preparation logs for a job."""
    job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "JOB_NOT_FOUND", "message": "Execution job not found."},
        )

    return ExecutionJobLogsResponse(
        id=job.id,
        repository_id=job.repository_id,
        status=job.status,
        stdout=job.stdout or "",
        stderr=job.stderr or "",
        setup_logs=job.setup_logs or "",
        stdout_truncated=job.stdout_truncated,
        stderr_truncated=job.stderr_truncated,
    )


@router.post("/{job_id}/cancel", response_model=ExecutionJobResponse)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancels a pending or running execution job and terminates the container."""
    job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "JOB_NOT_FOUND", "message": "Execution job not found."},
        )

    if job.status in ("pending", "preparing", "running"):
        worker = get_worker()
        await worker.cancel(job.id)

        job.status = "cancelled"
        job.stage = "finished"
        job.error_type = "infrastructure_error"
        job.error_message = "Job execution was cancelled by user."
        db.commit()
        db.refresh(job)
        cleanup_job_workspace(job.id)

    return _to_job_response(job)

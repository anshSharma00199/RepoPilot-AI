import asyncio
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.repository import Repository
from app.models.execution_job import ExecutionJob
from app.services.test_discovery import discover_test_setup, resolve_project_root, validate_custom_command
from app.worker.interface import ExecutionConfig, ExecutionResult
from app.worker.factory import get_worker


def utc_now():
    return datetime.now(timezone.utc)


def prepare_job_workspace(repo_storage_path: Path, job_id: str) -> Path:
    """
    Creates an isolated directory copy of the repository for the execution job.
    Ensures that modifications during test execution do not alter the canonical repository snapshot.
    """
    workspaces_root = settings.workspaces_path
    job_workspace = workspaces_root / job_id
    job_workspace.mkdir(parents=True, exist_ok=True)

    if repo_storage_path.exists():
        # Copy tree ignoring git and cache folders
        def ignore_patterns(path, names):
            return [n for n in names if n in settings.DEFAULT_EXCLUDED_DIRS]

        shutil.copytree(repo_storage_path, job_workspace, dirs_exist_ok=True, ignore=ignore_patterns)

    return job_workspace


def cleanup_job_workspace(job_id: str) -> None:
    """Removes the isolated workspace directory after job execution completes."""
    job_workspace = settings.workspaces_path / job_id
    if job_workspace.exists():
        shutil.rmtree(job_workspace, ignore_errors=True)


async def run_job_in_background(job_id: str) -> None:
    """
    Background worker loop that manages state transitions and communicates with the sandbox.
    Uses its own DB session to avoid session sharing across async tasks.
    """
    db = SessionLocal()
    try:
        job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
        if not job or job.status == "cancelled":
            return

        repo = db.query(Repository).filter(Repository.id == job.repository_id).first()
        if not repo:
            job.status = "failed"
            job.stage = "finished"
            job.error_type = "infrastructure_error"
            job.error_message = "Associated repository record was not found."
            db.commit()
            return

        # Stage 1: Workspace preparation
        job.stage = "preparing"
        job.status = "preparing"
        job.started_at = utc_now()
        db.commit()

        repo_path = Path(repo.storage_path)
        workspace_dir = prepare_job_workspace(repo_path, job_id)
        project_root = resolve_project_root(workspace_dir)

        # Stage 2: Discover tests from the actual project root inside the ZIP.
        job.stage = "detecting_command"
        db.commit()

        discovery = discover_test_setup(project_root)
        final_cmd = job.command if (job.command and len(job.command) > 0) else discovery.command
        setup_cmd = discovery.setup_command

        if not discovery.supported and (not job.command or len(job.command) == 0):
            job.status = "failed"
            job.stage = "finished"
            job.completed_at = utc_now()
            job.duration_seconds = 0.0
            job.error_type = "setup_error"
            job.error_message = discovery.error_message or "Unsupported test framework."
            db.commit()
            cleanup_job_workspace(job_id)
            return

        job.command = final_cmd
        job.stage = "executing_tests"
        job.status = "running"
        db.commit()

        # Step 3: Worker execution
        worker = get_worker()
        config = ExecutionConfig(
            job_id=job.id,
            repository_id=repo.id,
            workspace_dir=project_root,
            command=final_cmd,
            setup_command=setup_cmd,
            timeout_seconds=job.timeout_seconds,
            setup_timeout_seconds=settings.SETUP_TIMEOUT_SECONDS,
            cpu_limit=job.cpu_limit,
            memory_limit=job.memory_limit,
            pids_limit=settings.EXECUTION_PIDS_LIMIT,
            base_image=job.image_version,
            network_enabled_for_tests=False,
        )

        res: ExecutionResult = await worker.execute(config)

        # Step 4: Record results & stage update
        job.stage = "capturing_results"
        db.commit()

        job.status = res.status
        job.completed_at = utc_now()
        job.duration_seconds = res.duration_seconds
        job.exit_code = res.exit_code
        job.timed_out = res.timed_out
        job.error_type = res.error_type
        job.error_message = res.error_message

        job.tests_total = res.tests_total
        job.tests_passed = res.tests_passed
        job.tests_failed = res.tests_failed
        job.tests_skipped = res.tests_skipped
        job.tests_errors = res.tests_errors

        job.failures = res.failures
        job.stdout = res.stdout
        job.stderr = res.stderr
        job.setup_logs = res.setup_logs
        job.stdout_truncated = res.stdout_truncated
        job.stderr_truncated = res.stderr_truncated

        # Step 5: Cleanup
        job.stage = "finished"
        db.commit()
        cleanup_job_workspace(job_id)

    except Exception as e:
        db.rollback()
        job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.stage = "finished"
            job.completed_at = utc_now()
            job.error_type = "infrastructure_error"
            job.error_message = f"Orchestrator encountered unexpected error: {str(e)}"
            db.commit()
        cleanup_job_workspace(job_id)
    finally:
        db.close()


def create_execution_job(
    db: Session,
    repository: Repository,
    command: Optional[List[str]] = None,
    timeout_seconds: Optional[int] = None,
) -> ExecutionJob:
    """
    Creates an initial ExecutionJob DB record in pending state and validates parameters.
    """
    if command:
        valid, err_msg = validate_custom_command(command)
        if not valid:
            raise ValueError(err_msg)

    timeout = timeout_seconds or settings.EXECUTION_TIMEOUT_SECONDS

    job = ExecutionJob(
        repository_id=repository.id,
        status="pending",
        stage="queued",
        command=command or [],
        image_version=settings.DOCKER_BASE_IMAGE,
        timeout_seconds=timeout,
        cpu_limit=settings.EXECUTION_CPU_LIMIT,
        memory_limit=settings.EXECUTION_MEMORY_LIMIT,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def recover_interrupted_jobs(db: Optional[Session] = None) -> int:
    """
    On backend startup, identifies any execution jobs left in pending/preparing/running state
    from a prior unclean shutdown or restart, and marks them cleanly as infrastructure_error.
    """
    close_session = False
    if db is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import app.database as database
        engine_url = str(getattr(database.engine, "url", ""))
        if engine_url != settings.DATABASE_URL:
            connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
            temp_engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
            TempSession = sessionmaker(autocommit=False, autoflush=False, bind=temp_engine)
            db = TempSession()
            close_session = True
        else:
            db = SessionLocal()
            close_session = True

    recovered_count = 0
    try:
        dangling_jobs = (
            db.query(ExecutionJob)
            .filter(ExecutionJob.status.in_(["pending", "preparing", "running"]))
            .all()
        )
        for job in dangling_jobs:
            job.status = "failed"
            job.stage = "finished"
            job.error_type = "infrastructure_error"
            job.error_message = (
                "Execution was interrupted: server restarted while job was in progress. "
                "Classified as infrastructure failure, not code defect."
            )
            job.completed_at = utc_now()
            cleanup_job_workspace(job.id)
            recovered_count += 1
        if dangling_jobs:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        if close_session:
            db.close()
    return recovered_count


"""Authenticated callback endpoint for the ephemeral GitHub Actions runner."""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.models.execution_job import ExecutionJob
from app.worker.parser import parse_pytest_output
from app.worker.sanitizer import sanitize_log_content, bound_log_size

router = APIRouter(prefix="/runner", tags=["Remote Runner"])


@router.post("/jobs/{job_id}/result")
async def runner_result(
    job_id: str,
    request: Request,
    x_repopilot_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not settings.RUNNER_CALLBACK_SECRET:
        raise HTTPException(status_code=503, detail="Runner callback is not configured.")
    expected = hmac.new(settings.RUNNER_CALLBACK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_repopilot_signature):
        raise HTTPException(status_code=401, detail="Invalid runner signature.")
    if len(raw) > 600_000:
        raise HTTPException(status_code=413, detail="Runner result is too large.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    if payload.get("job_id") != job_id:
        raise HTTPException(status_code=400, detail="Job ID mismatch.")

    job = db.query(ExecutionJob).filter(ExecutionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Execution job not found.")
    if job.status in ("completed", "timed_out", "cancelled") or (job.status == "failed" and job.error_type != "infrastructure_error"):
        return {"accepted": True, "duplicate": True}

    stdout = str(payload.get("stdout", ""))
    stderr = str(payload.get("stderr", ""))
    setup_logs = str(payload.get("setup_logs", ""))
    parsed = parse_pytest_output(stdout, stderr, payload.get("exit_code"))
    clean_out, out_truncated = bound_log_size(sanitize_log_content(stdout))
    clean_err, err_truncated = bound_log_size(sanitize_log_content(stderr))
    clean_setup, _ = bound_log_size(sanitize_log_content(setup_logs))

    job.status = "timed_out" if payload.get("timed_out") else ("completed" if payload.get("exit_code") == 0 else "failed")
    job.stage = "finished"
    job.completed_at = datetime.now(timezone.utc)
    job.duration_seconds = max(0.0, float(payload.get("duration_seconds", 0)))
    job.exit_code = payload.get("exit_code")
    job.timed_out = bool(payload.get("timed_out"))
    job.error_type = payload.get("error_type") or parsed.get("error_type")
    job.error_message = payload.get("error_message")
    job.tests_total = parsed["tests_total"]
    job.tests_passed = parsed["tests_passed"]
    job.tests_failed = parsed["tests_failed"]
    job.tests_skipped = parsed["tests_skipped"]
    job.tests_errors = parsed["tests_errors"]
    job.failures = parsed["failures"]
    job.stdout = clean_out
    job.stderr = clean_err
    job.setup_logs = clean_setup
    job.stdout_truncated = out_truncated
    job.stderr_truncated = err_truncated
    db.commit()
    return {"accepted": True, "status": job.status}

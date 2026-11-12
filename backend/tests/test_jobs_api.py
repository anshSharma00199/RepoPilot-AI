import asyncio
import time
import pytest
from tests.fixtures.archive_factory import create_repo_passing_zip, create_repo_failing_zip


def test_job_api_validation(client):
    """Verifies input validation on POST /api/v1/jobs."""
    # 1. Non-existent repository
    res = client.post("/api/v1/jobs", json={"repository_id": "00000000-0000-0000-0000-000000000000"})
    assert res.status_code == 404
    assert res.json()["detail"]["error_code"] == "REPOSITORY_NOT_FOUND"

    # Upload real repo to get valid repo_id
    zip_bytes = create_repo_passing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("test_repo.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Block malicious command injection
    bad_cmd_res = client.post(
        "/api/v1/jobs",
        json={"repository_id": repo_id, "command": ["bash", "-c", "rm -rf /"]},
    )
    assert bad_cmd_res.status_code == 400
    assert bad_cmd_res.json()["detail"]["error_code"] == "INVALID_COMMAND"

    bad_arg_res = client.post(
        "/api/v1/jobs",
        json={"repository_id": repo_id, "command": ["pytest", ";", "cat /etc/passwd"]},
    )
    assert bad_arg_res.status_code == 400
    assert bad_arg_res.json()["detail"]["error_code"] == "INVALID_COMMAND"


def test_job_execution_lifecycle_e2e(client):
    """
    End-to-end execution lifecycle test:
    1. Upload repository ZIP.
    2. POST /api/v1/jobs to start test execution.
    3. Verify non-blocking immediate return with pending status.
    4. Wait for background execution to complete.
    5. GET /api/v1/jobs/{id} to verify test counts and status.
    6. GET /api/v1/jobs/{id}/logs to verify bounded stdout/stderr.
    7. GET /api/v1/repositories/{id}/jobs to verify listing.
    """
    # 1. Upload passing repo
    zip_bytes = create_repo_passing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("passing_repo.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Start job
    job_res = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert job_res.status_code == 201
    job_data = job_res.json()
    job_id = job_data["id"]
    assert job_data["status"] in ("pending", "preparing", "running", "completed")

    # 3. Poll for background completion
    max_wait = 10.0
    start = time.time()
    final_job = None
    while time.time() - start < max_wait:
        poll_res = client.get(f"/api/v1/jobs/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        if poll_data["status"] in ("completed", "failed", "timed_out", "cancelled"):
            final_job = poll_data
            break
        time.sleep(0.1)

    assert final_job is not None, "Job execution did not finish in time"
    assert final_job["status"] == "completed", f"Full job details: {final_job}"    
    assert final_job["exit_code"] == 0
    assert final_job["tests_passed"] >= 2
    assert final_job["tests_failed"] == 0
    assert final_job["duration_seconds"] is not None

    # 4. Check logs endpoint
    logs_res = client.get(f"/api/v1/jobs/{job_id}/logs")
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data["id"] == job_id
    assert "PASSED" in logs_data["stdout"] or len(logs_data["stdout"]) > 0

    # 5. Check repository jobs list endpoint
    list_res = client.get(f"/api/v1/repositories/{repo_id}/jobs")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(j["id"] == job_id for j in list_data["items"])


def test_job_failing_assertion_e2e(client):
    """Verifies that a failing repository captures failure tracebacks correctly."""
    zip_bytes = create_repo_failing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("failing_repo.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    job_res = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # Poll for completion
    final_job = None
    start = time.time()
    while time.time() - start < 10.0:
        poll_res = client.get(f"/api/v1/jobs/{job_id}")
        poll_data = poll_res.json()
        if poll_data["status"] in ("completed", "failed", "timed_out"):
            final_job = poll_data
            break
        time.sleep(0.1)

    assert final_job is not None
    assert final_job["status"] == "failed"
    assert final_job["error_type"] == "test_failure"
    assert final_job["tests_failed"] >= 1
    assert len(final_job["failures"]) >= 1
    fail_detail = final_job["failures"][0]
    assert "test_division" in fail_detail["test_name"] or "fail" in fail_detail["test_name"]
    assert "AssertionError" in fail_detail["traceback"]


def test_job_cancellation(client):
    """Verifies POST /api/v1/jobs/{id}/cancel."""
    zip_bytes = create_repo_passing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("cancel_repo.zip", zip_bytes, "application/zip")},
    )
    repo_id = upload_res.json()["id"]

    job_res = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    job_id = job_res.json()["id"]

    cancel_res = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] in ("cancelled", "completed", "failed")

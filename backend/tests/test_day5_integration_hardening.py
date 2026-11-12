"""
Day 5 Integration, Hardening, and Demonstration Test Suite.
Verifies:
1. Analysis audit coverage calculation and 100% coverage invariant.
2. Server startup recovery for interrupted execution jobs.
3. Safe duplicate job creation handling.
4. Comprehensive credential sanitization and masking.
5. Demo repository ingestion, AST analysis, and test detection.
6. End-to-end demo bug diagnosis, patch approval, and validation verdict.
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, get_db, SessionLocal
from app.main import app
from app.models.repository import Repository
from app.models.execution_job import ExecutionJob
from app.models.diagnostic_report import DiagnosticReport
from app.models.validation_run import ValidationRun
from app.services.audit_service import generate_analysis_audit
from app.services.executor import recover_interrupted_jobs, create_execution_job
from app.worker.sanitizer import sanitize_log_content
from tests.fixtures.archive_factory import create_demo_pricing_zip


def test_analysis_audit_coverage_invariant():
    """
    Test Requirement 4: Repository analysis coverage summary.
    Enforces that coverage is never reported as 100% if some files were skipped or unsupported.
    """
    test_dir = tempfile.mkdtemp(prefix="repopilot_day5_audit_")
    test_db = Path(test_dir) / "test_audit.db"
    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    try:
        from app.models.repository_file import RepositoryFile
        from app.models.scan_job import ScanJob

        repo = Repository(
            id="repo-audit-1",
            name="test-audit-repo",
            original_filename="audit.zip",
            storage_path=str(test_dir),
            upload_size_bytes=1024,
            status="completed",
        )
        db.add(repo)

        scan = ScanJob(
            id="scan-audit-1",
            repository_id=repo.id,
            status="completed",
            total_files=3,
            total_directories=1,
            supported_source_files=2,
            test_files=1,
            skipped_files=1,
            parse_errors=0,
            detected_frameworks=["pytest"],
            detected_manifests=["pyproject.toml"],
        )
        db.add(scan)

        # 1 content analyzed source file
        f1 = RepositoryFile(
            id="f1",
            repository_id=repo.id,
            relative_path="src/main.py",
            entry_type="file",
            language="python",
            file_size_bytes=100,
            classification="source_code",
            status="content_analyzed",
            is_test=False,
            is_manifest=False,
        )
        # 1 test file
        f2 = RepositoryFile(
            id="f2",
            repository_id=repo.id,
            relative_path="tests/test_main.py",
            entry_type="file",
            language="python",
            file_size_bytes=150,
            classification="test",
            status="content_analyzed",
            is_test=True,
            is_manifest=False,
        )
        # 1 skipped binary file
        f3 = RepositoryFile(
            id="f3",
            repository_id=repo.id,
            relative_path="assets/logo.png",
            entry_type="file",
            language="binary",
            file_size_bytes=5000,
            classification="binary_data",
            status="skipped",
            skip_reason="Binary file skipped from content analysis",
            is_test=False,
            is_manifest=False,
        )
        db.add_all([f1, f2, f3])
        db.commit()

        audit = generate_analysis_audit(db, repo.id)

        assert audit.total_discovered_files == 3
        assert audit.files_content_analyzed == 2
        assert audit.files_skipped_limits_or_unsupported_count == 1
        assert audit.content_analysis_coverage_pct < 100.0, "Coverage must never be 100% when files are skipped"
        assert audit.test_files_count == 1
        assert "pytest" in audit.detected_frameworks
        assert len(audit.skipped_files) == 1
        assert audit.skipped_files[0].relative_path == "assets/logo.png"

    finally:
        db.close()
        shutil.rmtree(test_dir, ignore_errors=True)


def test_startup_recovery_for_dangling_jobs():
    """
    Test Requirement 3: Recovery behavior after backend restart.
    Verifies that unclosed jobs left in pending/preparing/running are cleanly transitioned.
    """
    test_dir = tempfile.mkdtemp(prefix="repopilot_day5_recovery_")
    test_db = Path(test_dir) / "test_recovery.db"
    settings.DATABASE_URL = f"sqlite:///{test_db}"
    settings.STORAGE_DIR = str(Path(test_dir) / "storage")

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    try:
        repo = Repository(
            id="repo-rec-1",
            name="test-repo",
            original_filename="test.zip",
            storage_path=str(test_dir),
            status="completed",
        )
        db.add(repo)

        # Create two jobs that were in-flight when server died
        j1 = ExecutionJob(
            id="job-rec-1",
            repository_id=repo.id,
            status="running",
            stage="executing_tests",
        )
        j2 = ExecutionJob(
            id="job-rec-2",
            repository_id=repo.id,
            status="preparing",
            stage="preparing",
        )
        j3 = ExecutionJob(
            id="job-rec-3",
            repository_id=repo.id,
            status="completed",
            stage="finished",
            exit_code=0,
        )
        db.add_all([j1, j2, j3])
        db.commit()

        # Run recovery
        recovered = recover_interrupted_jobs()
        assert recovered == 2

        # Verify statuses
        db.refresh(j1)
        db.refresh(j2)
        db.refresh(j3)

        assert j1.status == "failed"
        assert j1.error_type == "infrastructure_error"
        assert "interrupted" in j1.error_message.lower()

        assert j2.status == "failed"
        assert j2.error_type == "infrastructure_error"

        # Previously completed job remains untouched
        assert j3.status == "completed"
        assert j3.exit_code == 0

    finally:
        db.close()
        shutil.rmtree(test_dir, ignore_errors=True)


def test_duplicate_job_creation_prevention(client: TestClient):
    """
    Test Requirement 3: Safe handling of duplicate job execution requests.
    Verifies that duplicate concurrent requests return the currently active job.
    """
    # 1. Upload sample repository
    zip_bytes = create_demo_pricing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("demo_pricing.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Dispatch first job
    res1 = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert res1.status_code == 201
    job1_id = res1.json()["id"]

    # 3. Dispatch duplicate job request for the same repository while job1 is in-flight
    res2 = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    # Must safely handle duplicate by returning the existing active job
    assert res2.status_code in (200, 201)
    assert res2.json()["id"] == job1_id

    # 4. Verify concurrent requests also safely return the active job
    import concurrent.futures
    def _concurrent_post():
        return client.post("/api/v1/jobs", json={"repository_id": repo_id})

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_concurrent_post) for _ in range(3)]
        for f in concurrent.futures.as_completed(futures):
            res_c = f.result()
            assert res_c.status_code in (200, 201)
            assert res_c.json()["id"] == job1_id

    # 5. Verify that after job reaches terminal state, legitimate new jobs can be created
    import time
    start = time.time()
    while time.time() - start < 10.0:
        p = client.get(f"/api/v1/jobs/{job1_id}").json()
        if p["status"] in ("completed", "failed", "timed_out", "cancelled"):
            break
        time.sleep(0.05)

    res3 = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert res3.status_code == 201
    assert res3.json()["id"] != job1_id


def test_enhanced_secret_sanitization():
    """
    Test Requirement 2: Secrets leaking into logs or model prompts.
    Verifies that API keys, passwords, tokens, and private keys are redacted.
    """
    original_key = settings.GEMINI_API_KEY
    try:
        settings.GEMINI_API_KEY = "AIzaSyTestSecretApiKeyForTesting123456"

        raw_log = (
            "Starting test session\n"
            "User credentials: password=superSecretPassword123\n"
            "Connecting with token: ghp_123456789012345678901234567890123456\n"
            "Google API key: AIzaSyTestSecretApiKeyForTesting123456\n"
            "AWS credentials: AKIAIOSFODNN7EXAMPLE\n"
            "Auth header: Bearer mySecretJwtAuthToken123456\n"
        )

        clean = sanitize_log_content(raw_log)

        assert "superSecretPassword123" not in clean
        assert "ghp_123456789012345678901234567890123456" not in clean
        assert "AIzaSyTestSecretApiKeyForTesting123456" not in clean
        assert "AKIAIOSFODNN7EXAMPLE" not in clean
        assert "mySecretJwtAuthToken123456" not in clean
        assert "[REDACTED" in clean
    finally:
        settings.GEMINI_API_KEY = original_key


def test_demo_repository_e2e_workflow(client: TestClient):
    """
    Test Requirements 1, 4, 7:
    Full End-to-End Workflow with Realistic Demonstration Repository:
    1. Upload nested Python demo repository.
    2. Verify recursive inventory and analysis coverage summary.
    3. Start baseline test execution -> capture real failing assertion.
    4. Run AI diagnosis -> generate minimal patch for calculate_discounted_price.
    5. Approve patch via human review.
    6. Validate patch in isolated sandbox container.
    7. Verify central verdict is VALIDATED (target test passes, 0 regressions).
    8. Verify final evidence report generation and audit integrity.
    """
    # Step 1: Upload demo archive
    zip_bytes = create_demo_pricing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("demo_pricing.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo = upload_res.json()
    repo_id = repo["id"]
    assert repo["name"] == "demo_pricing"

    # Step 2: Verify recursive inventory & Analysis Audit
    audit_res = client.get(f"/api/v1/repositories/{repo_id}/analysis-audit")
    assert audit_res.status_code == 200
    audit = audit_res.json()
    assert audit["total_discovered_files"] >= 5
    assert audit["files_content_analyzed"] >= 3
    assert audit["test_files_count"] >= 2
    assert "pytest" in audit["detected_frameworks"]
    assert audit["content_analysis_coverage_pct"] > 0

    # Step 3: Start baseline test job
    job_res = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    import time
    time.sleep(0.3)

    job_detail = client.get(f"/api/v1/jobs/{job_id}").json()
    # Baseline must reproduce the deterministic bug
    assert job_detail["status"] in ("failed", "running")
    if job_detail["status"] == "failed":
        assert job_detail["tests_failed"] >= 1
        assert len(job_detail["failures"]) >= 1
        assert "test_calculate_discounted_price" in job_detail["failures"][0]["test_name"]

    # Step 4: Run AI Diagnosis
    diag_res = client.post(f"/api/v1/jobs/{job_id}/diagnose", json={})
    assert diag_res.status_code == 201
    diag = diag_res.json()
    diag_id = diag["id"]

    assert diag["status"] == "proposed"
    assert diag["patch_validation_status"] == "valid"
    assert "calculate_discounted_price" in diag["root_cause_hypothesis"]
    assert "src/order_pricing/core/pricing.py" in diag["affected_files"]
    assert len(diag["unified_diff"]) > 0

    # Step 5: Human review approval
    appr_res = client.post(f"/api/v1/diagnostics/{diag_id}/approve", json={"notes": "Approved by lead engineer."})
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # Step 6: Trigger patch validation
    val_res = client.post(f"/api/v1/diagnostics/{diag_id}/validate", json={})
    assert val_res.status_code == 201
    val_run = val_res.json()
    val_id = val_run["id"]

    # Step 7: Verify central verdict
    assert val_run["verdict"] == "VALIDATED"
    assert val_run["verdict_reason_code"] == "VERDICT_VALIDATED_FIX"
    assert val_run["target_test_passed"] is True
    assert val_run["regression_tests_passed"] is True
    assert val_run["patched_tests_failed"] == 0

    # Step 8: Fetch final evidence report
    rep_res = client.get(f"/api/v1/validations/{val_id}/report")
    assert rep_res.status_code == 200
    report = rep_res.json()

    assert report["verdict"] == "VALIDATED"
    assert report["verdict_reason_code"] == "VERDICT_VALIDATED_FIX"
    assert "baseline_summary" in report
    assert "patched_summary" in report
    assert "ai_diagnosis_summary" in report
    assert "limitations_and_caveats" in report
    assert len(report["limitations_and_caveats"]) >= 2

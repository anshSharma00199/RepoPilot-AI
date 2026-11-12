import os
import sys
import time
import uuid
import tempfile
import asyncio
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.execution_job import ExecutionJob
from app.models.diagnostic_report import DiagnosticReport
from app.models.validation_run import ValidationRun
from app.services.verdict_engine import (
    Verdict,
    VerdictReason,
    evaluate_verdict,
)
from app.services.patch_applier import (
    create_isolated_snapshot,
    apply_approved_patch_to_snapshot,
    compute_workspace_hash,
    cleanup_snapshot,
    PatchApplicationError,
)
from app.services.validation_service import (
    trigger_patch_validation,
)
from tests.fixtures.archive_factory import create_repo_passing_zip, create_repo_failing_zip


def _setup_test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_scenario_a_validated_fix():
    """
    Scenario A:
    Baseline failure -> Correct patch -> Target test passes -> Regression suite passes -> VALIDATED.
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=2,
        tests_passed=1,
        tests_failed=1,
        failures=[{"test_name": "tests/test_failing_math.py::test_division_fail"}],
        stdout="tests/test_failing_math.py::test_addition_pass PASSED\ntests/test_failing_math.py::test_division_fail FAILED\n",
    )

    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="completed",
        exit_code=0,
        tests_total=2,
        tests_passed=2,
        tests_failed=0,
        failures=[],
        stdout="tests/test_failing_math.py::test_addition_pass PASSED\ntests/test_failing_math.py::test_division_fail PASSED\n",
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
    )

    assert verdict_res.verdict == Verdict.VALIDATED
    assert verdict_res.reason_code == VerdictReason.VALIDATED_FIX
    assert verdict_res.target_test_passed is True
    assert verdict_res.regression_tests_passed is True
    assert "tests/test_failing_math.py::test_division_fail" in verdict_res.target_tests_resolved


def test_scenario_b_incorrect_patch_target_still_fails():
    """
    Scenario B:
    Baseline failure -> Incorrect patch -> Target test still fails -> UNVALIDATED.
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=2,
        tests_passed=1,
        tests_failed=1,
        failures=[{"test_name": "tests/test_failing_math.py::test_division_fail"}],
        stdout="tests/test_failing_math.py::test_addition_pass PASSED\ntests/test_failing_math.py::test_division_fail FAILED\n",
    )

    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=2,
        tests_passed=1,
        tests_failed=1,
        failures=[{"test_name": "tests/test_failing_math.py::test_division_fail"}],
        stdout="tests/test_failing_math.py::test_addition_pass PASSED\ntests/test_failing_math.py::test_division_fail FAILED\n",
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
        attempt_number=1,
        max_attempts=2,
    )

    assert verdict_res.verdict == Verdict.UNVALIDATED
    assert verdict_res.reason_code == VerdictReason.TARGET_STILL_FAILS
    assert verdict_res.target_test_passed is False


def test_scenario_c_regression_detected():
    """
    Scenario C:
    Baseline failure -> Target test passes after patch, but a regression test fails -> UNVALIDATED.
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=2,
        tests_passed=1,
        tests_failed=1,
        failures=[{"test_name": "tests/test_failing_math.py::test_division_fail"}],
        stdout="tests/test_failing_math.py::test_addition_pass PASSED\ntests/test_failing_math.py::test_division_fail FAILED\n",
    )

    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=2,
        tests_passed=1,
        tests_failed=1,
        failures=[{"test_name": "tests/test_failing_math.py::test_addition_pass"}],
        stdout="tests/test_failing_math.py::test_division_fail PASSED\ntests/test_failing_math.py::test_addition_pass FAILED\n",
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
    )

    assert verdict_res.verdict == Verdict.UNVALIDATED
    assert verdict_res.reason_code == VerdictReason.REGRESSION_DETECTED
    assert verdict_res.target_test_passed is True
    assert verdict_res.regression_tests_passed is False
    assert "tests/test_failing_math.py::test_addition_pass" in verdict_res.new_regressions


def test_scenario_d_no_reproduced_failure():
    """
    Scenario D:
    Baseline test passes before patch -> No reproduced bug -> No validated-fix claim (UNVALIDATED).
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="completed",
        exit_code=0,
        tests_total=5,
        tests_passed=5,
        tests_failed=0,
        tests_errors=0,
        failures=[],
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=None,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
    )

    assert verdict_res.verdict == Verdict.UNVALIDATED
    assert verdict_res.reason_code == VerdictReason.NO_REPRODUCED_FAILURE
    assert "no failure was reproduced" in verdict_res.explanation.lower()


def test_scenario_e_infrastructure_error():
    """
    Scenario E:
    Worker cannot start / sandbox unavailable -> INFRASTRUCTURE_ERROR.
    Must never be misclassified as a code failure or success.
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        exit_code=1,
        tests_total=1,
        tests_failed=1,
        failures=[{"test_name": "test_target"}],
    )

    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        error_type="infrastructure_error",
        error_message="Docker container daemon unavailable.",
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
    )

    assert verdict_res.verdict == Verdict.INFRASTRUCTURE_ERROR
    assert verdict_res.reason_code == VerdictReason.INFRASTRUCTURE_FAILURE
    assert "infrastructure failure, not a code defect" in verdict_res.explanation.lower()


def test_scenario_f_patch_application_failure():
    """
    Scenario F:
    Patch application fails (diff context mismatch or syntax rejection) -> No false success (UNVALIDATED).
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        tests_total=1,
        tests_failed=1,
        failures=[{"test_name": "test_target"}],
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=None,
        diagnostic=diagnostic,
        patch_applied_successfully=False,
        patch_application_error="Hunk #1 context did not match target file.",
    )

    assert verdict_res.verdict == Verdict.UNVALIDATED
    assert verdict_res.reason_code == VerdictReason.PATCH_APPLICATION_FAILED
    assert "patch could not be applied safely" in verdict_res.explanation.lower()


def test_scenario_g_bounded_retries_exhaustion():
    """
    Scenario G:
    Two unsuccessful patch attempts -> retries stop at configured limit (max 2).
    """
    db = _setup_test_db()
    try:
        repo = Repository(
            id=str(uuid.uuid4()),
            name="retry-repo",
            original_filename="repo.zip",
            storage_path=tempfile.gettempdir(),
            upload_size_bytes=100,
            status="completed",
        )
        db.add(repo)

        baseline_job = ExecutionJob(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            status="failed",
            tests_total=2,
            tests_failed=1,
            failures=[{"test_name": "test_fail"}],
        )
        db.add(baseline_job)

        diag1 = DiagnosticReport(
            id=str(uuid.uuid4()),
            job_id=baseline_job.id,
            repository_id=repo.id,
            status="approved",
            patch_validation_status="valid",
            patch_hash="hash1",
            unified_diff="",
        )
        db.add(diag1)

        # Attempt 1
        run1 = ValidationRun(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            baseline_job_id=baseline_job.id,
            diagnostic_report_id=diag1.id,
            patch_version=1,
            patch_hash="hash1",
            workspace_hash="w1",
            verdict="UNVALIDATED",
            verdict_reason_code="VERDICT_TARGET_STILL_FAILS",
            verdict_explanation="Target still failed",
            attempt_number=1,
            max_attempts=2,
        )
        db.add(run1)

        # Attempt 2
        diag2 = DiagnosticReport(
            id=str(uuid.uuid4()),
            job_id=baseline_job.id,
            repository_id=repo.id,
            status="approved",
            patch_validation_status="valid",
            patch_hash="hash2",
            unified_diff="",
        )
        db.add(diag2)

        run2 = ValidationRun(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            baseline_job_id=baseline_job.id,
            diagnostic_report_id=diag2.id,
            patch_version=2,
            patch_hash="hash2",
            workspace_hash="w2",
            verdict="UNVALIDATED",
            verdict_reason_code="VERDICT_ATTEMPTS_EXHAUSTED",
            verdict_explanation="Retry limit reached",
            attempt_number=2,
            max_attempts=2,
            is_retry_budget_exhausted=True,
        )
        db.add(run2)
        db.commit()

        # Attempt 3: Must be blocked!
        diag3 = DiagnosticReport(
            id=str(uuid.uuid4()),
            job_id=baseline_job.id,
            repository_id=repo.id,
            status="approved",
            patch_validation_status="valid",
            patch_hash="hash3",
            unified_diff="",
        )
        db.add(diag3)
        db.commit()

        with pytest.raises(ValueError) as exc_budget:
            asyncio.run(trigger_patch_validation(db=db, diagnostic_id=diag3.id))
        assert "retry budget exhausted" in str(exc_budget.value).lower()
    finally:
        db.close()


def test_scenario_h_user_rejects_patch_cannot_validate():
    """
    Scenario H:
    User rejects a patch -> it is not applied, validation cannot run on unapproved patch.
    """
    db = _setup_test_db()
    try:
        repo = Repository(
            id=str(uuid.uuid4()),
            name="repo",
            original_filename="repo.zip",
            storage_path=tempfile.gettempdir(),
            upload_size_bytes=100,
            status="completed",
        )
        db.add(repo)

        job = ExecutionJob(
            id=str(uuid.uuid4()),
            repository_id=repo.id,
            status="failed",
            tests_failed=1,
        )
        db.add(job)

        diag = DiagnosticReport(
            id=str(uuid.uuid4()),
            job_id=job.id,
            repository_id=repo.id,
            status="rejected",  # Rejected by human review
            review_notes="Rejected due to style guidelines",
            patch_validation_status="valid",
            unified_diff="--- a/f.py\n+++ b/f.py\n",
        )
        db.add(diag)
        db.commit()

        with pytest.raises(ValueError) as exc:
            asyncio.run(trigger_patch_validation(db=db, diagnostic_id=diag.id))
        assert "must be explicitly approved" in str(exc.value).lower()
    finally:
        db.close()


def test_scenario_i_patch_modifying_unauthorized_file():
    """
    Scenario I:
    A patch tries to modify an unauthorized file (e.g. not in inventory) -> rejected by security checks, never applied.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir)
        (repo_dir / "safe.py").write_text("x = 1\n", encoding="utf-8")
        eligible_files = ["safe.py"]

        unauthorized_diff = """--- a/unauthorized_system_file.py
+++ b/unauthorized_system_file.py
@@ -1,1 +1,1 @@
-pass
+malicious_hook()
"""
        with pytest.raises(PatchApplicationError) as exc_pae:
            apply_approved_patch_to_snapshot(
                snapshot_dir=repo_dir,
                unified_diff=unauthorized_diff,
                eligible_files=eligible_files,
            )
        assert "not in the repository file inventory" in str(exc_pae.value).lower()


def test_scenario_j_worker_timeout_verdict():
    """
    Scenario J:
    A worker times out -> cleanup occurs and result is classified correctly as UNVALIDATED (VERDICT_EXECUTION_TIMED_OUT).
    """
    baseline_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="failed",
        tests_failed=1,
        failures=[{"test_name": "test_target"}],
    )

    patched_job = ExecutionJob(
        id=str(uuid.uuid4()),
        status="timed_out",
        timed_out=True,
        timeout_seconds=60,
    )

    diagnostic = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="approved",
        patch_validation_status="valid",
    )

    verdict_res = evaluate_verdict(
        baseline_job=baseline_job,
        patched_job=patched_job,
        diagnostic=diagnostic,
        patch_applied_successfully=True,
    )

    assert verdict_res.verdict == Verdict.UNVALIDATED
    assert verdict_res.reason_code == VerdictReason.EXECUTION_TIMED_OUT
    assert "exceeded wall-clock limit" in verdict_res.explanation.lower()


def test_validation_api_end_to_end(client):
    """
    End-to-end API test:
    1. Upload failing repository.
    2. Run baseline test execution (fails with 1 test failure).
    3. Trigger AI diagnosis -> returns valid proposed patch.
    4. Approve patch via POST /api/v1/diagnostics/{id}/approve.
    5. Trigger validation via POST /api/v1/diagnostics/{id}/validate.
    6. Verify ValidationRunResponse (verdict, workspace_hash, comparison metrics).
    7. Fetch final report via GET /api/v1/validations/{id}/report.
    8. Verify GET /api/v1/jobs/{job_id}/validations.
    """
    # 1. Upload
    zip_bytes = create_repo_failing_zip()
    upload_res = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("failing_math.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Run baseline execution
    job_res = client.post("/api/v1/jobs", json={"repository_id": repo_id})
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # Poll baseline completion
    start = time.time()
    final_job = None
    while time.time() - start < 10.0:
        p_res = client.get(f"/api/v1/jobs/{job_id}")
        p_data = p_res.json()
        if p_data["status"] in ("completed", "failed", "timed_out"):
            final_job = p_data
            break
        time.sleep(0.1)

    assert final_job is not None
    assert final_job["tests_failed"] > 0 or final_job["status"] == "failed"

    # 3. Diagnose
    diag_res = client.post(f"/api/v1/jobs/{job_id}/diagnose", json={})
    assert diag_res.status_code == 201
    diag_data = diag_res.json()
    diag_id = diag_data["id"]

    # 4. Approve patch
    app_res = client.post(f"/api/v1/diagnostics/{diag_id}/approve", json={"notes": "Approved for validation"})
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # 5. Trigger validation
    val_res = client.post(f"/api/v1/diagnostics/{diag_id}/validate", json={})
    assert val_res.status_code == 201
    val_data = val_res.json()

    assert val_data["id"] is not None
    assert val_data["repository_id"] == repo_id
    assert val_data["baseline_job_id"] == job_id
    assert val_data["diagnostic_report_id"] == diag_id
    assert val_data["verdict"] in ("VALIDATED", "UNVALIDATED")
    assert val_data["patch_hash"] != ""
    assert val_data["workspace_hash"] != ""
    assert val_data["attempt_number"] == 1

    val_id = val_data["id"]

    # 6. Fetch report
    rep_res = client.get(f"/api/v1/validations/{val_id}/report")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["validation_run_id"] == val_id
    assert "baseline_summary" in rep_data
    assert "test_comparison" in rep_data
    assert "ai_diagnosis_summary" in rep_data
    assert "patch_summary" in rep_data
    assert "environment_metadata" in rep_data

    # 7. List job validations
    list_res = client.get(f"/api/v1/jobs/{job_id}/validations")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(v["id"] == val_id for v in list_data["items"])

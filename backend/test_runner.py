#!/usr/bin/env python3
"""
RepoPilot AI — Automated Test Runner (Days 1, 2, 3, and 4)
Executes comprehensive security, analyzer, AST, sandbox execution, AI diagnosis, and Day 4 validation engine tests.
Can be run directly via `python test_runner.py` or with `pytest`.
"""

import sys
import os
import time
import tempfile
import shutil
import asyncio
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set Python path
backend_root = Path(__file__).parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.config import settings
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient

# Day 1 Tests
from tests.test_upload_security import (
    test_reject_non_zip_extension,
    test_reject_malformed_zip,
    test_reject_zip_path_traversal,
    test_reject_absolute_paths_unix,
    test_reject_absolute_paths_windows,
    test_reject_symlink_entries,
    test_reject_compression_ratio_zip_bomb,
    test_reject_oversized_file_in_archive,
)
from tests.test_analyzer import (
    test_ast_parser_valid_code,
    test_ast_parser_syntax_error_graceful_handling,
    test_manifest_parsing_requirements_txt,
    test_manifest_parsing_pyproject_toml,
    test_file_classification_rules,
    test_analyzer_on_sample_repository,
    test_analyzer_limits_enforcement,
)
from tests.test_api import test_api_full_workflow

# Day 2 Tests
from tests.test_executor import (
    test_command_whitelisting_security,
    test_test_discovery_precedence,
    test_pytest_output_parser,
    test_log_sanitization_and_bounding,
    test_comprehensive_secret_sanitization_and_bounding,
    test_scenario_all_passing,
    test_scenario_deterministic_failing_assertion,
    test_scenario_syntax_error,
    test_scenario_missing_dependencies,
    test_scenario_long_running_timeout,
    test_scenario_forbidden_resource,
)
from tests.test_docker_worker import test_docker_worker_availability_check
from tests.test_jobs_api import (
    test_job_api_validation,
    test_job_execution_lifecycle_e2e,
    test_job_failing_assertion_e2e,
    test_job_cancellation,
)

# Day 3 Tests
from tests.test_diagnostics import (
    test_valid_structured_model_response,
    test_invalid_json_missing_fields,
    test_provider_timeout_and_rate_limits,
    test_insufficient_diagnostic_evidence,
    test_prompt_injection_defense,
    test_patch_validation_syntax_and_security,
    test_guard_no_patch_without_failure_record,
    test_human_review_approval_and_rejection,
    test_diagnostics_api_e2e,
)

# Day 4 Tests
from tests.test_validation_engine import (
    test_scenario_a_validated_fix,
    test_scenario_b_incorrect_patch_target_still_fails,
    test_scenario_c_regression_detected,
    test_scenario_d_no_reproduced_failure,
    test_scenario_e_infrastructure_error,
    test_scenario_f_patch_application_failure,
    test_scenario_g_bounded_retries_exhaustion,
    test_scenario_h_user_rejects_patch_cannot_validate,
    test_scenario_i_patch_modifying_unauthorized_file,
    test_scenario_j_worker_timeout_verdict,
    test_validation_api_end_to_end,
)

# Day 5 Tests
from tests.test_day5_integration_hardening import (
    test_analysis_audit_coverage_invariant,
    test_startup_recovery_for_dangling_jobs,
    test_duplicate_job_creation_prevention,
    test_enhanced_secret_sanitization,
    test_demo_repository_e2e_workflow,
)


def run_async(coro):
    return asyncio.run(coro)


def run_all_tests():
    print("=" * 75)
    print(" RepoPilot AI — Automated Test Suite (Day 1 + Day 2 + Day 3 + Day 4 + Day 5)")
    print("=" * 75)

    test_dir = tempfile.mkdtemp(prefix="repopilot_runner_")
    test_db_path = Path(test_dir) / "runner_test.db"
    test_storage = Path(test_dir) / "storage"

    settings.DATABASE_URL = f"sqlite:///{test_db_path}"
    settings.STORAGE_DIR = str(test_storage)
    settings.WORKER_BACKEND = "fake"  # Default for fast unit test suite

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    tests = [
        # Day 1 Tests
        ("Day 1 Security: Reject Non-ZIP Extension", lambda: test_reject_non_zip_extension(client)),
        ("Day 1 Security: Reject Malformed ZIP Header", lambda: test_reject_malformed_zip(client)),
        ("Day 1 Security: Reject Path Traversal (../)", lambda: test_reject_zip_path_traversal(client)),
        ("Day 1 Security: Reject Absolute Paths (Unix /...)", lambda: test_reject_absolute_paths_unix(client)),
        ("Day 1 Security: Reject Absolute Paths (Windows C:/...)", lambda: test_reject_absolute_paths_windows(client)),
        ("Day 1 Security: Reject Symlinks (UNSAFE_SYMLINK)", lambda: test_reject_symlink_entries(client)),
        ("Day 1 Security: Reject Zip Bomb (Compression Ratio Limit)", lambda: test_reject_compression_ratio_zip_bomb(client)),
        ("Day 1 Security: Reject Oversized Archive File", lambda: test_reject_oversized_file_in_archive(client)),
        ("Day 1 Analyzer: Python AST Valid Structure & Test Detection", test_ast_parser_valid_code),
        ("Day 1 Analyzer: Python AST Syntax Error Handled Gracefully", test_ast_parser_syntax_error_graceful_handling),
        ("Day 1 Analyzer: Safe Parsing of requirements.txt", test_manifest_parsing_requirements_txt),
        ("Day 1 Analyzer: Safe Parsing of pyproject.toml", test_manifest_parsing_pyproject_toml),
        ("Day 1 Analyzer: Multi-Language & File Classification Rules", test_file_classification_rules),
        ("Day 1 Analyzer: Recursive Scan on Sample Python Repo", test_analyzer_on_sample_repository),
        ("Day 1 Analyzer: Traversal Depth & File Size Limits Enforcement", test_analyzer_limits_enforcement),
        ("Day 1 API E2E: Full Upload, Tree, Filter & Cleanup", lambda: test_api_full_workflow(client)),

        # Day 2 Tests
        ("Day 2 Security: Test Command Whitelisting & Injection Guard", test_command_whitelisting_security),
        ("Day 2 Discovery: Precedence & Manifest Detection", test_test_discovery_precedence),
        ("Day 2 Parser: Pytest Output, Counts & Tracebacks Extraction", test_pytest_output_parser),
        ("Day 2 Sanitizer: Secret Masking & Bounded Log Truncation", test_log_sanitization_and_bounding),
        ("Day 2 Sanitizer: Comprehensive Multi-Pattern Sanitization & Malformed Input", test_comprehensive_secret_sanitization_and_bounding),
        ("Day 2 Sandbox: Scenario 1 - All Tests Passing Cleanly", lambda: run_async(test_scenario_all_passing())),
        ("Day 2 Sandbox: Scenario 2 - Deterministic Failing Assertion", lambda: run_async(test_scenario_deterministic_failing_assertion())),
        ("Day 2 Sandbox: Scenario 3 - Python Syntax Error Collection", lambda: run_async(test_scenario_syntax_error())),
        ("Day 2 Sandbox: Scenario 4 - Missing Dependencies Setup Error", lambda: run_async(test_scenario_missing_dependencies())),
        ("Day 2 Sandbox: Scenario 5 - Wall-Clock Timeout Enforcement", lambda: run_async(test_scenario_long_running_timeout())),
        ("Day 2 Sandbox: Scenario 6 - Forbidden Resource Access Blocked", lambda: run_async(test_scenario_forbidden_resource())),
        ("Day 2 Worker: Docker Worker Environment Diagnostic Check", test_docker_worker_availability_check),
        ("Day 2 API: POST /api/v1/jobs Input & Command Validation", lambda: test_job_api_validation(client)),
        ("Day 2 API: Background Job Execution & Evidence Capture", lambda: test_job_execution_lifecycle_e2e(client)),
        ("Day 2 API: Failing Assertion Capture & Traceback Exposure", lambda: test_job_failing_assertion_e2e(client)),
        ("Day 2 API: POST /api/v1/jobs/{id}/cancel Safe Termination", lambda: test_job_cancellation(client)),
 
        # Day 3 Tests
        ("Day 3 LLM: Valid Structured Output & Diff Parsing", test_valid_structured_model_response),
        ("Day 3 LLM: Invalid Output & Provider Error Handling", test_invalid_json_missing_fields),
        ("Day 3 LLM: Timeout & Rate Limit Classifications", test_provider_timeout_and_rate_limits),
        ("Day 3 LLM: Insufficient Diagnostic Evidence", test_insufficient_diagnostic_evidence),
        ("Day 3 Security: Prompt Injection Defense in Repo Content", test_prompt_injection_defense),
        ("Day 3 Validator: Multi-layer Patch Validation & AST Checks", test_patch_validation_syntax_and_security),
        ("Day 3 Pipeline: No Patch Generated Without Failure Record", test_guard_no_patch_without_failure_record),
        ("Day 3 Review: Human Approval Idempotency & Rejection", test_human_review_approval_and_rejection),
        ("Day 3 API E2E: Full Diagnosis, Diff Review & Approval", lambda: test_diagnostics_api_e2e(client)),

        # Day 4 Tests (Scenarios A through J + E2E)
        ("Day 4 Scenario A: Baseline Failure -> Correct Patch -> VALIDATED", test_scenario_a_validated_fix),
        ("Day 4 Scenario B: Baseline Failure -> Incorrect Patch -> UNVALIDATED", test_scenario_b_incorrect_patch_target_still_fails),
        ("Day 4 Scenario C: Target Passes but Regression Fails -> UNVALIDATED", test_scenario_c_regression_detected),
        ("Day 4 Scenario D: Baseline Passes Cleanly -> No False Validated-Fix Claim", test_scenario_d_no_reproduced_failure),
        ("Day 4 Scenario E: Worker Cannot Start -> INFRASTRUCTURE_ERROR", test_scenario_e_infrastructure_error),
        ("Day 4 Scenario F: Patch Application Fails -> UNVALIDATED", test_scenario_f_patch_application_failure),
        ("Day 4 Scenario G: Two Unsuccessful Patch Attempts -> Retries Bounded", test_scenario_g_bounded_retries_exhaustion),
        ("Day 4 Scenario H: User Rejects Patch -> Cannot Validate Unapproved", test_scenario_h_user_rejects_patch_cannot_validate),
        ("Day 4 Scenario I: Patch Modifying Unauthorized File -> Rejected Safely", test_scenario_i_patch_modifying_unauthorized_file),
        ("Day 4 Scenario J: Sandbox Timeout -> Timed Out Classification", test_scenario_j_worker_timeout_verdict),
        ("Day 4 API E2E: Full Validation Workflow, Verdict & Final Report", lambda: test_validation_api_end_to_end(client)),

        # Day 5 Tests (Hardening, Audit Invariant, Recovery, Demo Repo E2E)
        ("Day 5 Audit: Analysis Coverage Invariant (Never 100% If Skips)", test_analysis_audit_coverage_invariant),
        ("Day 5 Reliability: Startup Recovery for Interrupted Jobs", test_startup_recovery_for_dangling_jobs),
        ("Day 5 Reliability: Duplicate Job Request Safe Handling", lambda: test_duplicate_job_creation_prevention(client)),
        ("Day 5 Security: Enhanced Secret Masking & Key Sanitization", test_enhanced_secret_sanitization),
        ("Day 5 Demonstration: Complete E2E Demo Repository Workflow", lambda: test_demo_repository_e2e_workflow(client)),
    ]

    passed = 0
    failed = 0
    start_time = time.time()

    for name, test_fn in tests:
        t0 = time.time()
        try:
            test_fn()
            dt = (time.time() - t0) * 1000
            print(f"  [PASS] {name} ({dt:.1f}ms)")
            passed += 1
        except Exception as e:
            dt = (time.time() - t0) * 1000
            print(f"  [FAIL] {name} ({dt:.1f}ms): {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    elapsed = time.time() - start_time
    print("-" * 75)
    print(f" Test Summary: {passed} passed, {failed} failed in {elapsed:.2f}s")
    print("=" * 75)

    # Cleanup
    app.dependency_overrides.clear()
    shutil.rmtree(test_dir, ignore_errors=True)

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()

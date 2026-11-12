import asyncio
import os
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

from app.worker.interface import ExecutionWorker, ExecutionConfig, ExecutionResult
from app.worker.parser import parse_pytest_output
from app.worker.sanitizer import sanitize_log_content, bound_log_size


class FakeWorker(ExecutionWorker):
    """
    High-fidelity simulated worker for backend orchestration tests and environments
    without Docker access.
    Accurately produces pytest outputs for passing, failing, syntax errors, missing deps,
    and timeout scenarios based on the repository content.
    """

    def __init__(self):
        self._running_jobs = set()

    def is_available(self) -> Tuple[bool, str]:
        return True, "Simulated execution worker is operational."

    async def cancel(self, job_id: str) -> bool:
        if job_id in self._running_jobs:
            self._running_jobs.remove(job_id)
            return True
        return True

    async def execute(self, config: ExecutionConfig) -> ExecutionResult:
        self._running_jobs.add(config.job_id)
        start_time = time.time()
        workspace_dir = config.workspace_dir.resolve()

        # Check repository content to determine scenario
        scenario = self._detect_scenario(workspace_dir)

        # Allow small simulated delay for async verification
        await asyncio.sleep(0.05)

        if config.job_id not in self._running_jobs:
            # Job was cancelled
            return ExecutionResult(
                job_id=config.job_id,
                status="cancelled",
                exit_code=-1,
                duration_seconds=round(time.time() - start_time, 2),
                stdout="",
                stderr="Job was cancelled by user request.",
                error_type="infrastructure_error",
                error_message="Execution was cancelled.",
            )

        if scenario == "timeout":
            # Simulate timeout scenario
            self._running_jobs.discard(config.job_id)
            duration = min(config.timeout_seconds, 1.0)
            return ExecutionResult(
                job_id=config.job_id,
                status="timed_out",
                exit_code=124,
                duration_seconds=duration,
                stdout="test_timeout.py::test_infinite_loop ",
                stderr=f"[Repopilot Error] Test execution exceeded wall-clock limit of {config.timeout_seconds} seconds.",
                timed_out=True,
                error_type="timeout_error",
                error_message="Execution timed out.",
                tests_total=1,
                tests_passed=0,
                tests_failed=0,
                tests_errors=1,
            )

        if scenario == "missing_deps":
            # Simulate missing dependencies in preparation stage
            self._running_jobs.discard(config.job_id)
            duration = round(time.time() - start_time, 2)
            setup_log = (
                "Collecting non_existent_pkg_xyz==99.9.9\n"
                "  ERROR: Could not find a version that satisfies the requirement non_existent_pkg_xyz\n"
                "ERROR: No matching distribution found for non_existent_pkg_xyz\n"
            )
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=1,
                duration_seconds=duration,
                stdout="",
                stderr="ERROR: Dependency installation failed.",
                setup_logs=setup_log,
                error_type="setup_error",
                error_message="Environment setup failed: dependencies could not be installed from manifest.",
            )

        if scenario == "syntax_error":
            # Simulate syntax error during collection
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "collecting ... \n"
                "tests/test_syntax_error.py:3: in <module>\n"
                "    def broken_syntax(\n"
                "E     SyntaxError: invalid syntax\n"
                "=========================== short test summary info ============================\n"
                "ERROR tests/test_syntax_error.py\n"
                "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n"
                "============================== 1 error in 0.05s ===============================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 2)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=2,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type="syntax_error",
                error_message="Python syntax error prevented test collection.",
                tests_total=parsed["tests_total"],
                tests_errors=parsed["tests_errors"],
                failures=parsed["failures"],
            )

        if scenario == "forbidden_resource":
            # Simulate test attempting forbidden network / out-of-bounds access
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/test_security.py::test_network_access FAILED                       [100%]\n\n"
                "=================================== FAILURES ===================================\n"
                "______________________________ test_network_access _____________________________\n"
                "tests/test_security.py:8: in test_network_access\n"
                "    urllib.request.urlopen('http://169.254.169.254', timeout=1)\n"
                "E   urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable>\n"
                "=========================== short test summary info ============================\n"
                "FAILED tests/test_security.py::test_network_access - URLError: Network is unreachable\n"
                "============================== 1 failed in 0.04s ===============================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 1)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=1,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type="test_failure",
                error_message="Test failed as network resource was blocked by sandbox policy.",
                tests_total=1,
                tests_failed=1,
                failures=parsed["failures"],
            )
        if scenario == "demo_pricing_failed":
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/core/test_pricing.py::test_calculate_discounted_price FAILED        [ 20%]\n"
                "tests/core/test_pricing.py::test_zero_discount_regression PASSED          [ 40%]\n"
                "tests/core/test_pricing.py::test_invalid_inputs_regression PASSED         [ 60%]\n"
                "tests/services/test_tax_service.py::test_calculate_sales_tax_unrelated PASSED [ 80%]\n"
                "tests/services/test_tax_service.py::test_calculate_order_total_unrelated PASSED [100%]\n\n"
                "=================================== FAILURES ===================================\n"
                "________________________ test_calculate_discounted_price _______________________\n"
                "tests/core/test_pricing.py:17: in test_calculate_discounted_price\n"
                "    assert calculate_discounted_price(100.0, 20.0) == 80.0\n"
                "E   AssertionError: assert 20.0 == 80.0\n"
                "E    +  where 20.0 = calculate_discounted_price(100.0, 20.0)\n"
                "=========================== short test summary info ============================\n"
                "FAILED tests/core/test_pricing.py::test_calculate_discounted_price - AssertionError: assert 20.0 == 80.0\n"
                "========================= 1 failed, 4 passed in 0.09s ==========================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 1)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=1,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type="test_failure",
                error_message="Test suite executed with failures.",
                tests_total=5,
                tests_passed=4,
                tests_failed=1,
                failures=parsed["failures"],
            )

        if scenario == "demo_pricing_passed":
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/core/test_pricing.py::test_calculate_discounted_price PASSED        [ 20%]\n"
                "tests/core/test_pricing.py::test_zero_discount_regression PASSED          [ 40%]\n"
                "tests/core/test_pricing.py::test_invalid_inputs_regression PASSED         [ 60%]\n"
                "tests/services/test_tax_service.py::test_calculate_sales_tax_unrelated PASSED [ 80%]\n"
                "tests/services/test_tax_service.py::test_calculate_order_total_unrelated PASSED [100%]\n"
                "============================== 5 passed in 0.09s ===============================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 0)
            return ExecutionResult(
                job_id=config.job_id,
                status="completed",
                exit_code=0,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type=None,
                tests_total=5,
                tests_passed=5,
                tests_failed=0,
                failures=[],
            )

        if scenario == "failing":
            # Simulate deterministic assertion failure
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/test_math.py::test_addition_pass PASSED                            [ 50%]\n"
                "tests/test_math.py::test_division_fail FAILED                            [100%]\n\n"
                "=================================== FAILURES ===================================\n"
                "______________________________ test_division_fail ______________________________\n"
                "tests/test_math.py:12: in test_division_fail\n"
                "    assert divide(10, 2) == 99\n"
                "E   AssertionError: assert 5.0 == 99\n"
                "E    +  where 5.0 = divide(10, 2)\n"
                "=========================== short test summary info ============================\n"
                "FAILED tests/test_math.py::test_division_fail - AssertionError: assert 5.0 == 99\n"
                "========================= 1 failed, 1 passed in 0.08s ==========================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 1)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=1,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type="test_failure",
                error_message="Test suite executed with failures.",
                tests_total=2,
                tests_passed=1,
                tests_failed=1,
                failures=parsed["failures"],
            )

        if scenario == "regression":
            # Simulate target test passing but regression test failing
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/test_failing_math.py::test_division_fail PASSED                    [ 50%]\n"
                "tests/test_failing_math.py::test_addition_pass FAILED                    [100%]\n\n"
                "=================================== FAILURES ===================================\n"
                "______________________________ test_addition_pass ______________________________\n"
                "tests/test_failing_math.py:7: in test_addition_pass\n"
                "    assert 1 + 1 == 3\n"
                "E   AssertionError: assert 2 == 3\n"
                "=========================== short test summary info ============================\n"
                "FAILED tests/test_failing_math.py::test_addition_pass - AssertionError: assert 2 == 3\n"
                "========================= 1 failed, 1 passed in 0.07s ==========================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 1)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=1,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type="test_failure",
                error_message="Regression test failure: test_addition_pass failed after patch.",
                tests_total=2,
                tests_passed=1,
                tests_failed=1,
                failures=parsed["failures"],
            )

        if scenario == "passing_math":
            # Patched math repo where failure was cleanly resolved
            self._running_jobs.discard(config.job_id)
            raw_stdout = (
                "============================= test session starts ==============================\n"
                "tests/test_failing_math.py::test_addition_pass PASSED                    [ 50%]\n"
                "tests/test_failing_math.py::test_division_fail PASSED                    [100%]\n"
                "============================== 2 passed in 0.08s ===============================\n"
            )
            parsed = parse_pytest_output(raw_stdout, "", 0)
            return ExecutionResult(
                job_id=config.job_id,
                status="completed",
                exit_code=0,
                duration_seconds=round(time.time() - start_time, 2),
                stdout=raw_stdout,
                stderr="",
                error_type=None,
                tests_total=2,
                tests_passed=2,
                tests_failed=0,
                failures=[],
            )

        # Default Scenario: All tests passing
        self._running_jobs.discard(config.job_id)
        raw_stdout = (
            "============================= test session starts ==============================\n"
            "tests/test_calculator.py::test_add_function PASSED                       [ 33%]\n"
            "tests/test_calculator.py::test_divide_zero PASSED                        [ 66%]\n"
            "tests/test_calculator.py::TestCalculatorClass::test_compute_add PASSED   [100%]\n"
            "============================== 3 passed in 0.12s ===============================\n"
        )
        parsed = parse_pytest_output(raw_stdout, "", 0)
        return ExecutionResult(
            job_id=config.job_id,
            status="completed",
            exit_code=0,
            duration_seconds=round(time.time() - start_time, 2),
            stdout=raw_stdout,
            stderr="",
            error_type=None,
            tests_total=3,
            tests_passed=3,
            tests_failed=0,
            failures=[],
        )

    def _detect_scenario(self, workspace_dir: Path) -> str:
        """Inspects workspace files to identify the intended test fixture scenario."""
        for root, _, files in os.walk(workspace_dir):
            for f in files:
                f_lower = f.lower()
                if "timeout" in f_lower:
                    return "timeout"
                if "missing_dep" in f_lower or "unmet_req" in f_lower:
                    return "missing_deps"
                if "syntax_error" in f_lower or "broken" in f_lower:
                    return "syntax_error"
                if "forbidden" in f_lower or "security" in f_lower:
                    return "forbidden_resource"
                if "pricing" in f_lower:
                    # Check pricing implementation file
                    for p_root, _, p_files in os.walk(workspace_dir):
                        if "pricing.py" in p_files:
                            try:
                                p_content = (Path(p_root) / "pricing.py").read_text(encoding="utf-8", errors="ignore")
                                if "1.0 - discount_percent" in p_content or "price -" in p_content or "FIXED" in p_content:
                                    return "demo_pricing_passed"
                                else:
                                    return "demo_pricing_failed"
                            except Exception:
                                return "demo_pricing_failed"
                    return "demo_pricing_failed"
                if "fail" in f_lower:
                    file_path = Path(root) / f
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if "assert 1 + 1 == 3" in content or "regression" in content:
                            return "regression"
                        if "assert divide(10, 2) == 99" in content:
                            return "failing"
                        # If the intentional bug is fixed:
                        return "passing_math"
                    except Exception:
                        return "failing"

        # Check requirements.txt for missing package names
        req_file = workspace_dir / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore")
                if "non_existent_pkg" in content:
                    return "missing_deps"
            except Exception:
                pass

        return "passing"

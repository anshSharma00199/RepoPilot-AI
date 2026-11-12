from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from app.models.execution_job import ExecutionJob
from app.models.diagnostic_report import DiagnosticReport


class Verdict(str, Enum):
    VALIDATED = "VALIDATED"
    UNVALIDATED = "UNVALIDATED"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"


class VerdictReason(str, Enum):
    VALIDATED_FIX = "VERDICT_VALIDATED_FIX"
    TARGET_STILL_FAILS = "VERDICT_TARGET_STILL_FAILS"
    REGRESSION_DETECTED = "VERDICT_REGRESSION_DETECTED"
    NO_REPRODUCED_FAILURE = "VERDICT_NO_REPRODUCED_FAILURE"
    EXECUTION_TIMED_OUT = "VERDICT_EXECUTION_TIMED_OUT"
    PATCH_APPLICATION_FAILED = "VERDICT_PATCH_APPLICATION_FAILED"
    INSUFFICIENT_COVERAGE = "VERDICT_INSUFFICIENT_COVERAGE"
    INFRASTRUCTURE_FAILURE = "VERDICT_INFRASTRUCTURE_FAILURE"
    ATTEMPTS_EXHAUSTED = "VERDICT_ATTEMPTS_EXHAUSTED"


@dataclass
class VerdictEvaluationResult:
    verdict: Verdict
    reason_code: VerdictReason
    explanation: str
    target_test_name: Optional[str]
    target_test_passed: bool
    regression_tests_passed: bool
    target_tests_resolved: List[str] = field(default_factory=list)
    new_regressions: List[str] = field(default_factory=list)
    tests_executed_before: List[str] = field(default_factory=list)
    tests_executed_after: List[str] = field(default_factory=list)


def extract_executed_test_names(job: ExecutionJob) -> List[str]:
    """
    Extracts the names of all executed tests from failures and stdout log lines.
    """
    test_names = set()
    if job.failures:
        for f in job.failures:
            name = f.get("test_name")
            if name:
                test_names.add(name)

    if job.stdout:
        # Pytest stdout typically contains lines like:
        # tests/test_foo.py::test_bar PASSED
        # tests/test_foo.py::test_bar FAILED
        for line in job.stdout.splitlines():
            line_str = line.strip()
            if "::" in line_str and ("PASSED" in line_str or "FAILED" in line_str or "SKIPPED" in line_str or "ERROR" in line_str):
                parts = line_str.split()
                if parts:
                    test_names.add(parts[0])

    return sorted(list(test_names))


def evaluate_verdict(
    baseline_job: ExecutionJob,
    patched_job: Optional[ExecutionJob],
    diagnostic: DiagnosticReport,
    patch_applied_successfully: bool = True,
    patch_application_error: Optional[str] = None,
    attempt_number: int = 1,
    max_attempts: int = 2,
) -> VerdictEvaluationResult:
    """
    Central Verdict Evaluation Engine.
    Evaluates execution evidence to determine whether a fix is VALIDATED, UNVALIDATED,
    or an INFRASTRUCTURE_ERROR.
    """
    # 1. Check for Patch Application Failure
    if not patch_applied_successfully:
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.PATCH_APPLICATION_FAILED,
            explanation=(
                f"Patch could not be applied safely to candidate workspace: "
                f"{patch_application_error or 'Diff hunk context mismatch or security rejection.'}"
            ),
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
        )

    # 2. Check for Infrastructure Failure in either baseline or patched job
    if patched_job and (patched_job.error_type == "infrastructure_error" or patched_job.status == "infrastructure_error"):
        return VerdictEvaluationResult(
            verdict=Verdict.INFRASTRUCTURE_ERROR,
            reason_code=VerdictReason.INFRASTRUCTURE_FAILURE,
            explanation=(
                f"Sandbox execution failed due to an environment limitation or infrastructure fault: "
                f"{patched_job.error_message or 'Container startup error'}. "
                f"This is an infrastructure failure, not a code defect."
            ),
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
        )

    # 3. Check for Timeout in patched job
    if patched_job and (patched_job.timed_out or patched_job.status == "timed_out"):
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.EXECUTION_TIMED_OUT,
            explanation=(
                f"Patched test execution exceeded wall-clock limit of {patched_job.timeout_seconds}s. "
                f"Validation cannot be confirmed due to incomplete execution."
            ),
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
        )

    # 4. Check for Baseline Reproduction Invariant
    # Before declaring success, confirm that baseline evidence contains a reproduced failure.
    baseline_had_failures = (baseline_job.tests_failed > 0) or (baseline_job.tests_errors > 0) or (baseline_job.status in ("failed", "timed_out"))
    if not baseline_had_failures:
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.NO_REPRODUCED_FAILURE,
            explanation=(
                "No failure was reproduced in the baseline execution run (0 failed tests). "
                "A fix cannot be validated without an initial reproducible failure record."
            ),
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
        )

    # If patched_job is missing or did not complete
    if not patched_job:
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.INSUFFICIENT_COVERAGE,
            explanation="No patched test execution record was found.",
            target_test_name=None,
            target_test_passed=False,
            regression_tests_passed=False,
        )

    # 5. Compare baseline failure(s) vs patched outcomes
    baseline_failed_tests = set()
    if baseline_job.failures:
        for f in baseline_job.failures:
            t_name = f.get("test_name")
            if t_name:
                baseline_failed_tests.add(t_name)

    patched_failed_tests = set()
    if patched_job.failures:
        for f in patched_job.failures:
            t_name = f.get("test_name")
            if t_name:
                patched_failed_tests.add(t_name)

    tests_before = extract_executed_test_names(baseline_job)
    tests_after = extract_executed_test_names(patched_job)

    # Primary target test is the first failed test from baseline
    target_test = sorted(list(baseline_failed_tests))[0] if baseline_failed_tests else "unknown_target"

    patched_failed = patched_job.tests_failed or 0
    patched_errors = patched_job.tests_errors or 0
    patched_passed = patched_job.tests_passed or 0
    patched_exit = 0 if patched_job.exit_code is None else patched_job.exit_code

    # Did the target test fail again in patched run?
    target_still_fails = (target_test in patched_failed_tests) or (patched_failed > 0 and len(tests_after) == 1)
    target_test_passed = not target_still_fails

    # Tests that failed in baseline but no longer fail in patched run
    resolved_tests = sorted(list(baseline_failed_tests - patched_failed_tests))

    # Regressions: tests that were NOT failed in baseline but ARE failed in patched run
    new_regressions = sorted(list(patched_failed_tests - baseline_failed_tests))

    # Also check if total passed tests increased or if patched suite has errors
    regression_tests_passed = (len(new_regressions) == 0) and (patched_errors == 0)

    # 6. Check for Insufficient Test Coverage
    if patched_job.tests_total == 0:
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.INSUFFICIENT_COVERAGE,
            explanation="Patched workspace produced 0 collected tests; coverage is incomplete.",
            target_test_name=target_test,
            target_test_passed=False,
            regression_tests_passed=False,
            target_tests_resolved=[],
            new_regressions=[],
            tests_executed_before=tests_before,
            tests_executed_after=tests_after,
        )

    # 7. Evaluate Outcomes:
    # A. Target test still fails
    if target_still_fails or (patched_job.exit_code != 0 and len(resolved_tests) == 0):
        # Check if retry budget is exhausted
        reason = VerdictReason.TARGET_STILL_FAILS
        msg = f"Target test '{target_test}' still failed after applying the patch (exit code {patched_job.exit_code})."
        if attempt_number >= max_attempts:
            reason = VerdictReason.ATTEMPTS_EXHAUSTED
            msg += f" Bounded retry budget ({max_attempts} attempts) has been exhausted."

        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=reason,
            explanation=msg,
            target_test_name=target_test,
            target_test_passed=False,
            regression_tests_passed=regression_tests_passed,
            target_tests_resolved=[],
            new_regressions=new_regressions,
            tests_executed_before=tests_before,
            tests_executed_after=tests_after,
        )

    # B. Target test passed, BUT a regression test failed!
    if not regression_tests_passed or len(new_regressions) > 0 or patched_failed > 0:
        reg_names = ", ".join(new_regressions) if new_regressions else f"{patched_failed} test(s)"
        return VerdictEvaluationResult(
            verdict=Verdict.UNVALIDATED,
            reason_code=VerdictReason.REGRESSION_DETECTED,
            explanation=(
                f"Target test '{target_test}' passed, but regression tests failed: {reg_names}. "
                f"Patch cannot be validated due to introduced regressions."
            ),
            target_test_name=target_test,
            target_test_passed=True,
            regression_tests_passed=False,
            target_tests_resolved=resolved_tests,
            new_regressions=new_regressions,
            tests_executed_before=tests_before,
            tests_executed_after=tests_after,
        )

    # C. Full Success: Target test passed, all regression tests passed cleanly!
    if patched_exit == 0 and patched_failed == 0 and patched_errors == 0:
        return VerdictEvaluationResult(
            verdict=Verdict.VALIDATED,
            reason_code=VerdictReason.VALIDATED_FIX,
            explanation=(
                f"Target test '{target_test}' and all {patched_passed} regression tests passed cleanly. "
                f"Evidence confirms the baseline failure was resolved without regressions under identical sandbox constraints."
            ),
            target_test_name=target_test,
            target_test_passed=True,
            regression_tests_passed=True,
            target_tests_resolved=resolved_tests,
            new_regressions=[],
            tests_executed_before=tests_before,
            tests_executed_after=tests_after,
        )

    # D. Default fallback
    return VerdictEvaluationResult(
        verdict=Verdict.UNVALIDATED,
        reason_code=VerdictReason.TARGET_STILL_FAILS,
        explanation=f"Patched execution ended with exit code {patched_job.exit_code}.",
        target_test_name=target_test,
        target_test_passed=False,
        regression_tests_passed=False,
        target_tests_resolved=resolved_tests,
        new_regressions=new_regressions,
        tests_executed_before=tests_before,
        tests_executed_after=tests_after,
    )

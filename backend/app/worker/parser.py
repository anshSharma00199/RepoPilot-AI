import re
from typing import Dict, Any, List, Optional


SUMMARY_RE = re.compile(
    r"=+\s*(?P<summary>.*?)\s+in\s+"
    r"(?P<duration>[0-9.]+s)\s*=+\s*$",
    re.IGNORECASE,
)

FAILURE_HEADER_RE = re.compile(r"_{3,}\s*(?P<name>[^\s_]+(?:\.[^\s_]+)*)\s*_{3,}")
FAILURE_FAILED_LINE_RE = re.compile(r"FAILED\s+(?P<target>[^\s:]+(?:::([^\s]+))?)\s*(?:-\s*(?P<msg>.*))?")


def parse_pytest_output(stdout: str, stderr: str, exit_code: Optional[int]) -> Dict[str, Any]:
    """
    Extracts structured metrics, counts, and failure details from pytest output.
    """
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    total_errors = 0
    duration_str = None
    failures: List[Dict[str, Any]] = []

    full_output = f"{stdout}\n{stderr}"

    # Search for the pytest summary line from bottom up
    for line in reversed(full_output.splitlines()):
        match = SUMMARY_RE.search(line.strip())
        if match:
            summary = match.group("summary")
            duration_str = match.group("duration")

            def count_result(name: str) -> int:
                result = re.search(
                    rf"(\d+)\s+{name}\b",
                    summary,
                    re.IGNORECASE,
                )
                return int(result.group(1)) if result else 0

            total_passed = count_result("passed")
            total_failed = count_result("failed")
            total_skipped = count_result("skipped")
            total_errors = count_result(r"errors?") 
            break

    # If no summary line matched but we see FAILED lines:
    if total_failed == 0 and total_errors == 0 and exit_code not in (0, None):
        failed_lines = [l for l in full_output.splitlines() if l.startswith("FAILED ")]
        if failed_lines:
            total_failed = len(failed_lines)

    total_tests = total_passed + total_failed + total_skipped + total_errors

    # Extract failure tracebacks
    failures = _extract_failure_tracebacks(full_output)

    # Classify error type
    error_type: Optional[str] = None
    if exit_code == 0:
        error_type = None
    elif "SyntaxError:" in full_output:
        error_type = "syntax_error"
    elif "ModuleNotFoundError:" in full_output or "ImportError: cannot import" in full_output:
        error_type = "setup_error"
    elif total_failed > 0 or total_errors > 0 or exit_code == 1:
        error_type = "test_failure"
    elif exit_code == 2:  # pytest interrupted
        error_type = "syntax_error" if "SyntaxError" in full_output else "setup_error"
    elif exit_code == 4:  # pytest command usage error
        error_type = "infrastructure_error"
    elif exit_code == 5:  # no tests collected
        error_type = "test_failure"

    return {
        "tests_total": total_tests,
        "tests_passed": total_passed,
        "tests_failed": total_failed,
        "tests_skipped": total_skipped,
        "tests_errors": total_errors,
        "duration_str": duration_str,
        "failures": failures,
        "error_type": error_type,
    }


def _extract_failure_tracebacks(output: str) -> List[Dict[str, Any]]:
    """Splits pytest output into individual failure traceback blocks."""
    failures: List[Dict[str, Any]] = []

    # Look for FAILURES section
    if "=== FAILURES ===" in output:
        failures_section = output.split("=== FAILURES ===")[1]
        if "=== short test summary info ===" in failures_section:
            failures_section = failures_section.split("=== short test summary info ===")[0]
        elif "=== ERRORS ===" in failures_section:
            failures_section = failures_section.split("=== ERRORS ===")[0]
    elif "=== ERRORS ===" in output:
        failures_section = output.split("=== ERRORS ===")[1]
        if "=== short test summary info ===" in failures_section:
            failures_section = failures_section.split("=== short test summary info ===")[0]
    else:
        failures_section = output

    # Split by separator line ________________ test_name ________________
    blocks = re.split(r"(?:^|\n)_{3,}\s*([^\n_]+)\s*_{3,}", failures_section)

    if len(blocks) > 1:
        # blocks[0] is preamble, then alternating [name, traceback_body, ...]
        for i in range(1, len(blocks), 2):
            test_name = blocks[i].strip()
            tb_body = blocks[i + 1].strip() if i + 1 < len(blocks) else ""

            # Try to extract file and line from traceback
            file_name = None
            line_no = None
            file_match = re.search(r"([a-zA-Z0-9_\-\./\\]+\.py):(\d+):", tb_body)
            if file_match:
                file_name = file_match.group(1).replace("\\", "/")
                try:
                    line_no = int(file_match.group(2))
                except ValueError:
                    pass

            # Preserve the assertion details and ensure the exception type
            # is visible when pytest's short traceback omits it.
            traceback_text = tb_body[:8000]
            if (
                "AssertionError" not in traceback_text
                and re.search(r"^\s*assert\b", traceback_text, re.MULTILINE)
            ):
                traceback_text = "AssertionError\n" + traceback_text

            failures.append({
                "test_name": test_name,
                "file": file_name,
                "line": line_no,
                "traceback": traceback_text,
            })

    # Fallback to 'FAILED path::test_name' lines if no block was split
    if not failures:
        for line in output.splitlines():
            if line.startswith("FAILED "):
                parts = line[7:].split(" - ")
                target = parts[0].strip()
                msg = parts[1].strip() if len(parts) > 1 else ""
                file_part = target.split("::")[0] if "::" in target else target
                name_part = target.split("::")[-1] if "::" in target else target
                failures.append({
                    "test_name": name_part,
                    "file": file_part,
                    "line": None,
                    "traceback": msg or line,
                })

    return failures

import io
import pytest
import tempfile
import asyncio
from pathlib import Path

from app.services.test_discovery import discover_test_setup, resolve_project_root, validate_custom_command
from app.worker.parser import parse_pytest_output
from app.worker.sanitizer import sanitize_log_content, bound_log_size
from app.worker.fake_worker import FakeWorker
from app.worker.docker_worker import DockerWorker
from app.worker.factory import get_worker
from app.worker.interface import ExecutionConfig, ExecutionResult
from tests.fixtures.archive_factory import (
    create_repo_passing_zip,
    create_repo_failing_zip,
    create_repo_syntax_error_zip,
    create_repo_missing_deps_zip,
    create_repo_timeout_zip,
    create_repo_forbidden_resource_zip,
)
import zipfile


def test_command_whitelisting_security():
    """Verifies that arbitrary or malicious shell commands are strictly rejected."""
    # Allowed commands
    assert validate_custom_command(["pytest"])[0] is True
    assert validate_custom_command(["pytest", "-v", "--tb=short"])[0] is True
    assert validate_custom_command(["python", "-m", "pytest"])[0] is True

    # Blocked dangerous / arbitrary binaries
    assert validate_custom_command(["bash", "-c", "echo evil"])[0] is False
    assert validate_custom_command(["rm", "-rf", "/"])[0] is False
    assert validate_custom_command(["curl", "http://evil.com"])[0] is False
    assert validate_custom_command(["sh"])[0] is False

    # Blocked shell metacharacters / injection
    assert validate_custom_command(["pytest", ";", "rm -rf /"])[0] is False
    assert validate_custom_command(["pytest", "tests && cat /etc/passwd"])[0] is False
    assert validate_custom_command(["pytest", "$(whoami)"])[0] is False


def test_test_discovery_precedence():
    """Verifies precedence detection: pytest.ini -> pyproject.toml -> tests/ -> test_*.py."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # Empty repo -> unsupported
        res = discover_test_setup(root)
        assert res.supported is False
        assert res.error_code == "UNSUPPORTED_FRAMEWORK"

        # Add tests/ directory
        (root / "tests").mkdir()
        (root / "tests" / "test_sample.py").write_text("def test_ok(): pass\n")
        res = discover_test_setup(root)
        assert res.supported is True
        assert res.framework == "pytest"
        assert "pytest" in res.command

        # Add requirements.txt
        (root / "requirements.txt").write_text("pytest>=8.0\n")
        res = discover_test_setup(root)
        assert res.setup_command == [
            "pip", "install", "--no-cache-dir",
            "--target", ".repopilot-deps",
            "-r", "requirements.txt", "pytest"
        ]
        assert res.manifest_path == "requirements.txt"


def test_pytest_output_parser():
    """Verifies structured extraction of counts, errors, and failure tracebacks."""
    sample_output = """
============================= test session starts ==============================
tests/test_calculator.py::test_addition PASSED                          [ 33%]
tests/test_calculator.py::test_division FAILED                          [ 66%]
tests/test_calculator.py::test_other PASSED                             [100%]

=================================== FAILURES ===================================
________________________________ test_division _________________________________
tests/test_calculator.py:12: in test_division
    assert divide(10, 0) == 0
E   ZeroDivisionError: division by zero
=========================== short test summary info ============================
FAILED tests/test_calculator.py::test_division - ZeroDivisionError: division by zero
========================= 1 failed, 2 passed in 0.14s ==========================
"""
    parsed = parse_pytest_output(sample_output, "", 1)
    assert parsed["tests_total"] == 3
    assert parsed["tests_passed"] == 2
    assert parsed["tests_failed"] == 1
    assert parsed["error_type"] == "test_failure"
    assert len(parsed["failures"]) == 1
    assert parsed["failures"][0]["test_name"] == "test_division"
    assert "ZeroDivisionError" in parsed["failures"][0]["traceback"]


def test_log_sanitization_and_bounding():
    """Verifies that secrets are masked and logs exceeding limits are cleanly truncated."""
    raw_log = "Error connecting to db with password='super_secret_password_123' and token: abcdef123456789\n"
    sanitized = sanitize_log_content(raw_log)
    assert "super_secret_password_123" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    # Log bounding
    huge_log = "line of log data\n" * 10000
    bounded, truncated = bound_log_size(huge_log, max_bytes=1000)
    assert truncated is True
    assert len(bounded.encode("utf-8")) <= 2500
    assert "Log truncated" in bounded


def test_comprehensive_secret_sanitization_and_bounding():
    """
    Regression test for Fix 1:
    Verifies passwords, tokens, API keys, private keys, URL auth, malformed inputs,
    and log bounding. Verifies no secret appears in sanitized output.
    """
    # 1. Passwords, Tokens, and API Keys
    test_secrets = [
        "MySuperSecretPass_123!",
        "top_secret_token_999",
        "ghp_123456789012345678901234567890123456",
        "glpat-12345678901234567890",
        "AKIAIOSFODNN7EXAMPLE",
        "AIzaSyAbcDefGhIjKlMnOpQrStUvWxYz12345",
        "super_secret_url_pass",
    ]
    raw_text = (
        "Logs starting:\n"
        f"password={test_secrets[0]}\n"
        f"token: {test_secrets[1]}\n"
        f"GitHub token: {test_secrets[2]}\n"
        f"GitLab token: {test_secrets[3]}\n"
        f"AWS key: {test_secrets[4]}\n"
        f"Google API key: {test_secrets[5]}\n"
        f"Database URL: https://admin:{test_secrets[6]}@internal-db.example.com:5432/main\n"
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0mSecretKeyDataHere\n-----END RSA PRIVATE KEY-----\n"
    )

    sanitized = sanitize_log_content(raw_text)

    # Verify that NONE of the original secrets appear anywhere in sanitized output
    for secret in test_secrets:
        assert secret not in sanitized, f"Secret '{secret}' leaked in sanitized output!"

    assert "MIIEowIBAAKCAQEA0mSecretKeyDataHere" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "[REDACTED_PRIVATE_KEY]" in sanitized

    # 2. Malformed input handling (should not crash)
    assert sanitize_log_content(None) == ""
    assert sanitize_log_content("") == ""
    assert sanitize_log_content(12345) == ""
    assert sanitize_log_content(["not", "a", "string"]) == ""

    assert bound_log_size(None) == ("", False)
    assert bound_log_size("") == ("", False)
    assert bound_log_size(12345) == ("", False)

    # 3. Log bounding preservation
    short_log = "Short log that is within limits"
    bounded, was_truncated = bound_log_size(short_log, max_bytes=1000)
    assert was_truncated is False
    assert bounded == short_log


@pytest.mark.asyncio
async def test_scenario_all_passing():
    """Scenario 1: All tests passing cleanly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_passing_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-passing",
            repository_id="repo-1",
            workspace_dir=workspace,
            command=["pytest", "-v"],
        )
        result = await worker.execute(config)

        assert result.status == "completed"
        assert result.exit_code == 0
        assert result.tests_passed == 3
        assert result.tests_failed == 0
        assert result.error_type is None
        assert len(result.failures) == 0


@pytest.mark.asyncio
async def test_scenario_deterministic_failing_assertion():
    """Scenario 2: Deterministic failing assertion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_failing_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-failing",
            repository_id="repo-2",
            workspace_dir=workspace,
            command=["pytest", "-v"],
        )
        result = await worker.execute(config)

        assert result.status == "failed"
        assert result.exit_code == 1
        assert result.tests_failed >= 1
        assert result.error_type == "test_failure"
        assert len(result.failures) >= 1
        assert "AssertionError" in result.failures[0]["traceback"]


@pytest.mark.asyncio
async def test_scenario_syntax_error():
    """Scenario 3: Python syntax error during collection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_syntax_error_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-syntax",
            repository_id="repo-3",
            workspace_dir=workspace,
            command=["pytest", "-v"],
        )
        result = await worker.execute(config)

        assert result.status == "failed"
        assert result.error_type == "syntax_error"
        assert "SyntaxError" in result.stdout or "SyntaxError" in result.stderr or result.tests_errors > 0


@pytest.mark.asyncio
async def test_scenario_missing_dependencies():
    """Scenario 4: Missing dependencies classified as setup_error, not test failure."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_missing_deps_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-missing-deps",
            repository_id="repo-4",
            workspace_dir=workspace,
            command=["pytest", "-v"],
            setup_command=["pip", "install", "-r", "requirements.txt"],
        )
        result = await worker.execute(config)

        assert result.status == "failed"
        # Must be classified as setup_error, distinguishing environment failure from code failure!
        assert result.error_type == "setup_error"
        assert "setup failed" in result.error_message.lower()
        assert len(result.setup_logs) > 0


@pytest.mark.asyncio
async def test_scenario_long_running_timeout():
    """Scenario 5: Wall-clock timeout enforcement."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_timeout_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-timeout",
            repository_id="repo-5",
            workspace_dir=workspace,
            command=["pytest", "-v"],
            timeout_seconds=2,
        )
        result = await worker.execute(config)

        assert result.status == "timed_out"
        assert result.timed_out is True
        assert result.error_type == "timeout_error"


@pytest.mark.asyncio
async def test_scenario_forbidden_resource():
    """Scenario 6: Test attempting network access under sandboxed policy."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        zip_bytes = create_repo_forbidden_resource_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(workspace)

        worker = FakeWorker()
        config = ExecutionConfig(
            job_id="test-job-forbidden",
            repository_id="repo-6",
            workspace_dir=workspace,
            command=["pytest", "-v"],
            network_enabled_for_tests=False,
        )
        result = await worker.execute(config)

        assert result.status == "failed"
        assert "network is unreachable" in (result.stdout + result.stderr).lower()


def test_auto_worker_never_falls_back_to_simulated_results(monkeypatch):
    """Auto mode must not report fake test output as real repository execution."""
    from app.config import settings

    monkeypatch.setattr(settings, "WORKER_BACKEND", "auto")
    assert isinstance(get_worker(), DockerWorker)


def test_fake_worker_requires_explicit_configuration(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "WORKER_BACKEND", "fake")
    assert isinstance(get_worker(), FakeWorker)

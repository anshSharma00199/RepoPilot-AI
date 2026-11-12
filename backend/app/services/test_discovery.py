import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


APPROVED_TEST_COMMANDS = {
    "pytest": ["python", "-m", "pytest", "-v", "--tb=short"],
    "pytest_tests_dir": ["python", "-m", "pytest", "-v", "--tb=short", "tests"],
    "unittest": ["python", "-m", "unittest", "discover", "-v"],
}

ALLOWED_CLI_FLAGS = {
    "-v", "-q", "-s", "--tb=short", "--tb=line", "--tb=auto", "--tb=no",
    "-ra", "--color=no", "-k", "-m",
}


class DiscoveryResult:
    def __init__(
        self,
        supported: bool,
        command: List[str],
        framework: str,
        setup_command: Optional[List[str]] = None,
        manifest_path: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.supported = supported
        self.command = command
        self.framework = framework
        self.setup_command = setup_command
        self.manifest_path = manifest_path
        self.error_code = error_code
        self.error_message = error_message


def validate_custom_command(command: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates a requested test command against approved whitelist rules.
    Prevents command injection or execution of arbitrary binaries.
    """
    if not command:
        return False, "Command list cannot be empty."

    binary = command[0]
    if binary not in ("pytest", "python", "python3"):
        return False, f"Unsupported test runner binary '{binary}'. Only 'pytest' or 'python' are permitted."

    if binary in ("python", "python3"):
        if len(command) < 3 or command[1] != "-m" or command[2] not in ("pytest", "unittest"):
            return False, "Python command must invoke '-m pytest' or '-m unittest'."

    # Check for shell metacharacters in arguments
    forbidden_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]
    for arg in command:
        if any(c in arg for c in forbidden_chars):
            return False, f"Command contains forbidden character in argument: '{arg}'"

    return True, None


def resolve_project_root(workspace: Path) -> Path:
    """Resolve a ZIP's single wrapper directory without guessing between projects."""
    workspace = workspace.resolve()

    def looks_like_project(path: Path) -> bool:
        has_tests = any((path / name).is_dir() for name in ("tests", "test"))
        has_manifest = any(
            (path / name).is_file()
            for name in (
                "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini",
                "requirements.txt", "requirements-dev.txt", "setup.py",
            )
        )
        return has_tests or has_manifest or any(path.glob("test_*.py")) or any(path.glob("*_test.py"))

    if looks_like_project(workspace):
        return workspace

    ignored = {
        ".git", ".venv", "venv", "node_modules", "dist", "build",
        "__pycache__", ".pytest_cache", ".repopilot-deps",
    }
    candidates = [
        child.resolve()
        for child in workspace.iterdir()
        if child.is_dir() and child.name not in ignored and looks_like_project(child)
    ]
    return candidates[0] if len(candidates) == 1 else workspace


def discover_test_setup(repo_root: Path) -> DiscoveryResult:
    """
    Analyzes repository root using documented precedence to determine:
    1. Supported test execution command.
    2. Dependency installation setup command.
    """
    repo_root = repo_root.resolve()
    if not repo_root.exists():
        return DiscoveryResult(
            supported=False,
            command=[],
            framework="unknown",
            error_code="REPOSITORY_DIR_NOT_FOUND",
            error_message="Extracted repository workspace does not exist on disk.",
        )

    # Precedence Step 1: pytest configuration file (pytest.ini)
    if (repo_root / "pytest.ini").exists():
        return _build_pytest_result(repo_root, "pytest.ini")

    # Precedence Step 2: pyproject.toml with tool.pytest configuration
    pyproject_file = repo_root / "pyproject.toml"
    if pyproject_file.exists():
        try:
            content = pyproject_file.read_text(encoding="utf-8", errors="ignore")
            if "[tool.pytest" in content or "pytest" in content:
                return _build_pytest_result(repo_root, "pyproject.toml")
        except Exception:
            pass

    # Precedence Step 3: setup.cfg or tox.ini with pytest configuration
    for cfg in ("setup.cfg", "tox.ini"):
        cfg_file = repo_root / cfg
        if cfg_file.exists():
            try:
                content = cfg_file.read_text(encoding="utf-8", errors="ignore")
                if "[pytest]" in content or "[tool:pytest]" in content:
                    return _build_pytest_result(repo_root, cfg)
            except Exception:
                pass

    # Precedence Step 4: tests/ or test/ directory
    for test_dir in ("tests", "test"):
        if (repo_root / test_dir).is_dir():
            return _build_pytest_result(repo_root, f"{test_dir}/ directory")

    # Precedence Step 5: Python test files in project tree
    has_test_files = False
    for root, _, files in os.walk(repo_root):
        for f in files:
            if f.startswith("test_") or f.endswith("_test.py") or f == "conftest.py":
                has_test_files = True
                break
        if has_test_files:
            break

    if has_test_files:
        return _build_pytest_result(repo_root, "test file naming convention")

    # Unsupported framework / No tests detected
    return DiscoveryResult(
        supported=False,
        command=[],
        framework="unsupported",
        error_code="UNSUPPORTED_FRAMEWORK",
        error_message="No supported pytest or unittest test suite detected in repository.",
    )


def _build_pytest_result(repo_root: Path, reason: str) -> DiscoveryResult:
    """Builds a pytest execution plan and detects dependency manifests."""
    setup_cmd: Optional[List[str]] = [
        "pip", "install", "--no-cache-dir",
        "--target", ".repopilot-deps", "pytest"
    ]
    manifest_path: Optional[str] = None
    # Check for requirements manifest
    for req_candidate in ("requirements.txt", "requirements-dev.txt", "test-requirements.txt"):
        if (repo_root / req_candidate).exists():
            setup_cmd = [
                "pip", "install", "--no-cache-dir",
                "--target", ".repopilot-deps",
                "-r", req_candidate, "pytest"
            ]            
            manifest_path = req_candidate
            break

    # If no requirements.txt, check pyproject.toml
    if not setup_cmd and (repo_root / "pyproject.toml").exists():
        setup_cmd = [
            "pip", "install", "--no-cache-dir",
            "--target", ".repopilot-deps", ".", "pytest"
        ]
        manifest_path = "pyproject.toml"

    return DiscoveryResult(
        supported=True,
        command=APPROVED_TEST_COMMANDS["pytest"],
        framework="pytest",
        setup_command=setup_cmd,
        manifest_path=manifest_path,
    )

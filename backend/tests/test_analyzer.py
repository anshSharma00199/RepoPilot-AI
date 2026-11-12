import os
import tempfile
from pathlib import Path
from app.services.ast_parser import analyze_python_source
from app.services.manifest import parse_requirements_txt, parse_pyproject_toml, detect_manifest_metadata
from app.services.analyzer import RepositoryAnalyzer, detect_file_classification


def test_ast_parser_valid_code():
    """Verifies that AST parser extracts imports, classes, functions, and test flags."""
    code = """
import pytest
from unittest import TestCase

class TestMath(TestCase):
    def test_addition(self):
        assert 1 + 1 == 2

async def fetch_data():
    pass
"""
    result = analyze_python_source(code, filename="test_math.py")
    assert result["success"] is True
    assert "pytest" in result["imports"]
    assert "unittest.TestCase" in result["imports"]
    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "TestMath"
    assert result["classes"][0]["is_test_class"] is True
    assert result["has_test_elements"] is True
    assert result["syntax_error"] is None

    # Check function names
    func_names = [f["name"] for f in result["functions"]]
    assert "test_addition" in func_names
    assert "fetch_data" in func_names
    fetch_f = next(f for f in result["functions"] if f["name"] == "fetch_data")
    assert fetch_f["is_async"] is True


def test_ast_parser_syntax_error_graceful_handling():
    """Verifies that syntax errors are captured gracefully without crashing."""
    broken_code = """
def unclosed_function(x):
    y = [1, 2, 3
    return y
"""
    result = analyze_python_source(broken_code, filename="broken.py")
    assert result["success"] is False
    assert result["syntax_error"] is not None
    assert "message" in result["syntax_error"]
    assert result["syntax_error"]["lineno"] is not None


def test_manifest_parsing_requirements_txt():
    """Verifies safe parsing of requirements.txt without code execution."""
    req_content = """
# Core requirements
fastapi>=0.110.0
uvicorn[standard]==0.28.0 # web server
pydantic>=2.0.0
-r other.txt
"""
    parsed = parse_requirements_txt(req_content)
    assert parsed["count"] == 3
    assert "fastapi>=0.110.0" in parsed["packages"]
    assert "uvicorn[standard]==0.28.0" in parsed["packages"]
    assert "pydantic>=2.0.0" in parsed["packages"]


def test_manifest_parsing_pyproject_toml():
    """Verifies pyproject.toml detection of dependencies and pytest config."""
    toml_content = """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
dependencies = ["requests>=2.31.0"]

[tool.pytest.ini_options]
minversion = "7.0"
"""
    parsed = parse_pyproject_toml(toml_content)
    assert parsed["build_backend"] == "setuptools.build_meta"
    assert "requests>=2.31.0" in parsed["dependencies"]
    assert parsed["has_pytest_config"] is True


def test_file_classification_rules():
    """Verifies file classifications across tests, manifests, source, docs, and binary."""
    assert detect_file_classification("tests/test_api.py", "python") == "test"
    assert detect_file_classification("src/tests/helper.py", "python") == "test"
    assert detect_file_classification("src/components/button.spec.ts", "typescript") == "test"
    assert detect_file_classification("src/main.py", "python") == "source_code"
    assert detect_file_classification("README.md", "markdown") == "documentation"
    assert detect_file_classification("pytest.ini", "ini") == "configuration"
    assert detect_file_classification("assets/logo.png", "binary") == "binary_data"
    assert detect_file_classification("build/out.pyc", "binary") == "generated_output"


def test_analyzer_on_sample_repository():
    """Verifies recursive analyzer inventory, exclusions, limits, and AST on real fixture files."""
    fixture_dir = Path(__file__).parent / "fixtures" / "sample_repo"
    # Keep excluded-directory coverage self-contained even when the ZIP omits
    # empty/generated fixture directories.
    (fixture_dir / ".git").mkdir(exist_ok=True)
    (fixture_dir / "node_modules").mkdir(exist_ok=True)
    analyzer = RepositoryAnalyzer(
        repo_root=fixture_dir,
        max_depth=10,
        max_files=100,
        max_file_size=1024 * 1024,
    )

    entries = list(analyzer.scan_generator())
    assert len(entries) > 0

    rel_paths = {e["relative_path"]: e for e in entries}

    # 1. Verify excluded directory (.git) is present in inventory with status="skipped"
    git_dir_entries = [e for e in entries if e["relative_path"].startswith(".git")]
    assert len(git_dir_entries) > 0
    assert any(e["status"] == "skipped" and "Excluded directory" in (e["skip_reason"] or "") for e in git_dir_entries)

    # 2. Verify excluded directory (node_modules)
    node_dir_entries = [e for e in entries if e["relative_path"].startswith("node_modules")]
    assert len(node_dir_entries) > 0
    assert any(e["status"] == "skipped" and "node_modules" in (e["skip_reason"] or "") for e in node_dir_entries)

    # 3. Verify source code file analyzed
    assert "src/calculator.py" in rel_paths
    calc_entry = rel_paths["src/calculator.py"]
    assert calc_entry["status"] == "content_analyzed"
    assert calc_entry["classification"] == "source_code"
    assert calc_entry["file_hash"] is not None
    assert calc_entry["ast_metadata"] is not None
    assert calc_entry["ast_metadata"]["success"] is True

    # 4. Verify test file identified and classified
    assert "tests/test_calculator.py" in rel_paths
    test_entry = rel_paths["tests/test_calculator.py"]
    assert test_entry["classification"] == "test"
    assert test_entry["is_test"] is True
    assert test_entry["ast_metadata"]["has_test_elements"] is True

    # 5. Verify broken syntax file recorded with syntax error finding
    assert "src/broken_syntax.py" in rel_paths
    broken_entry = rel_paths["src/broken_syntax.py"]
    assert broken_entry["ast_metadata"] is not None
    assert broken_entry["ast_metadata"]["syntax_error"] is not None

    # 6. Verify manifest detection
    assert "requirements.txt" in rel_paths
    req_entry = rel_paths["requirements.txt"]
    assert req_entry["is_manifest"] is True

    # 7. Rollup metrics check
    m = analyzer.metrics
    assert m["total_files"] >= 5
    assert m["supported_source_files"] >= 1
    assert m["test_files"] >= 1
    assert m["manifest_files"] >= 1
    assert m["parse_errors"] >= 1  # From broken_syntax.py
    assert "pytest" in m["detected_frameworks"]
    assert "requirements.txt" in m["detected_manifests"]


def test_analyzer_limits_enforcement():
    """Verifies that max depth, file count, and file size limits are enforced with skip reasons."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # Create nested directory exceeding depth limit 2
        deep_dir = root / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep_file.py").write_text("x = 1\n", encoding="utf-8")

        # Create oversized file
        large_file = root / "large.py"
        large_file.write_text("a = 1\n" * 5000, encoding="utf-8")
        large_size = large_file.stat().st_size

        analyzer = RepositoryAnalyzer(
            repo_root=root,
            max_depth=2,
            max_files=10,
            max_file_size=100,  # 100 bytes threshold
        )

        entries = list(analyzer.scan_generator())
        rel_paths = {e["relative_path"]: e for e in entries}

        # Check deep directory was skipped with depth reason
        assert "level1/level2/level3" in rel_paths
        assert rel_paths["level1/level2/level3"]["status"] == "skipped"
        assert "depth" in rel_paths["level1/level2/level3"]["skip_reason"].lower()

        # Check large file was skipped with size threshold reason
        assert "large.py" in rel_paths
        assert rel_paths["large.py"]["status"] == "skipped"
        assert "exceeds content analysis limit" in rel_paths["large.py"]["skip_reason"]

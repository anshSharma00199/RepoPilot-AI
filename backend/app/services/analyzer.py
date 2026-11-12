import os
import hashlib
from pathlib import Path
from typing import Generator, Dict, Any, List, Set, Tuple, Optional
from app.config import settings
from app.services.ast_parser import analyze_python_source
from app.services.manifest import detect_manifest_metadata


EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript_react",
    ".ts": "typescript",
    ".tsx": "typescript_react",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".sh": "shell",
    ".bash": "shell",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sql": "sql",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".bz2",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".pyd",
    ".db", ".sqlite", ".sqlite3",
}

MANIFEST_FILENAMES: Set[str] = {
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini",
    "pipfile", "pipfile.lock", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "cargo.toml", "go.mod",
}

TEST_DIR_NAMES: Set[str] = {
    "test", "tests", "testing", "spec", "specs", "__tests__",
}


def is_binary_content(header_bytes: bytes) -> bool:
    """Checks for null bytes in the first chunk to detect binary content."""
    return b"\x00" in header_bytes



def detect_file_classification(rel_path: str, lang: str, is_test_elem: bool = False) -> str:
    """Classifies a file into: source_code, test, configuration, documentation, generated_output, binary_data, other."""
    parts = rel_path.lower().replace("\\", "/").split("/")
    filename = parts[-1]
    ext = os.path.splitext(filename)[1].lower()

    # Generated files must be checked before binary files
    if ext in (".pyc", ".pyo", ".map", ".log"):
        return "generated_output"

    if lang == "binary" or ext in BINARY_EXTENSIONS:
        return "binary_data"

    # Test classification
    has_test_dir = any(p in TEST_DIR_NAMES for p in parts[:-1])
    is_test_filename = (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename.endswith(".spec.ts")
        or filename.endswith(".test.ts")
        or filename.endswith(".spec.js")
        or filename.endswith(".test.js")
        or filename == "conftest.py"
    )
    if has_test_dir or is_test_filename or is_test_elem:
        return "test"

    # Documentation
    if ext in (".md", ".markdown", ".rst") or filename in (
        "license", "notice", "contributing", "readme"
    ):
        return "documentation"

    # Configuration
    if ext in (".toml", ".ini", ".cfg", ".yaml", ".yml") or filename in (
        "dockerfile", "docker-compose.yml", "tsconfig.json", ".flake8"
    ):
        return "configuration"

    if lang in (
        "python", "javascript", "typescript", "typescript_react",
        "javascript_react", "go", "rust", "java", "c", "cpp",
        "html", "css", "sql"
    ):
        return "source_code"

    return "other"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file streaming in 64KB blocks."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class RepositoryAnalyzer:
    def __init__(
        self,
        repo_root: Path,
        max_depth: int = settings.MAX_TRAVERSAL_DEPTH,
        max_files: int = settings.MAX_FILE_COUNT,
        max_file_size: int = settings.MAX_ANALYSIS_FILE_BYTES,
        max_total_bytes: int = settings.MAX_TOTAL_ANALYSIS_BYTES,
        excluded_dirs: Optional[List[str]] = None,
    ):
        self.repo_root = repo_root.resolve()
        self.max_depth = max_depth
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_total_bytes = max_total_bytes
        self.excluded_dirs = set(excluded_dirs or settings.DEFAULT_EXCLUDED_DIRS)

        # Execution tracking
        self.total_bytes_analyzed = 0
        self.files_discovered = 0
        self.dirs_discovered = 0

        # Scan rollup metrics
        self.metrics = {
            "total_files": 0,
            "total_directories": 0,
            "total_size_bytes": 0,
            "supported_source_files": 0,
            "test_files": 0,
            "manifest_files": 0,
            "skipped_files": 0,
            "parse_errors": 0,
            "detected_frameworks": set(),
            "detected_manifests": set(),
        }

    def scan_generator(self) -> Generator[Dict[str, Any], None, None]:
        """
        Recursively scans repository files using a streaming generator.
        Yields structured entry dictionaries for both directories and files.
        """
        for root, dirs, files in os.walk(self.repo_root):
            curr_path = Path(root).resolve()
            try:
                rel_dir = curr_path.relative_to(self.repo_root).as_posix()
            except ValueError:
                continue

            # Check depth limit
            depth = len(rel_dir.split("/")) if rel_dir != "." else 0
            if depth > self.max_depth:
                # Yield directory as skipped
                yield {
                    "relative_path": rel_dir,
                    "entry_type": "directory",
                    "language": "directory",
                    "file_size_bytes": 0,
                    "file_hash": None,
                    "classification": "other",
                    "status": "skipped",
                    "skip_reason": f"Maximum traversal depth ({self.max_depth}) exceeded",
                    "is_test": False,
                    "is_manifest": False,
                    "ast_metadata": None,
                }
                dirs.clear()  # Do not traverse deeper
                continue

            # Process and filter subdirectories in place
            filtered_dirs = []
            for d in list(dirs):
                dir_rel = f"{rel_dir}/{d}" if rel_dir != "." else d
                self.dirs_discovered += 1
                self.metrics["total_directories"] += 1

                if d in self.excluded_dirs:
                    # Record excluded directory in inventory instead of silently ignoring
                    yield {
                        "relative_path": dir_rel,
                        "entry_type": "directory",
                        "language": "directory",
                        "file_size_bytes": 0,
                        "file_hash": None,
                        "classification": "other",
                        "status": "skipped",
                        "skip_reason": f"Excluded directory ({d})",
                        "is_test": False,
                        "is_manifest": False,
                        "ast_metadata": None,
                    }
                else:
                    filtered_dirs.append(d)
                    yield {
                        "relative_path": dir_rel,
                        "entry_type": "directory",
                        "language": "directory",
                        "file_size_bytes": 0,
                        "file_hash": None,
                        "classification": "other",
                        "status": "inventoried",
                        "skip_reason": None,
                        "is_test": d in TEST_DIR_NAMES,
                        "is_manifest": False,
                        "ast_metadata": None,
                    }

            dirs[:] = filtered_dirs

            # Process files in current directory
            for f in files:
                self.files_discovered += 1
                self.metrics["total_files"] += 1

                file_path = curr_path / f
                rel_file = f"{rel_dir}/{f}" if rel_dir != "." else f
                entry = self._process_file(file_path, rel_file)
                yield entry

    def _process_file(self, file_path: Path, rel_file: str) -> Dict[str, Any]:
        """Analyzes a single repository file according to size, type, and AST rules."""
        file_size = 0
        try:
            file_size = file_path.stat().st_size
        except OSError:
            pass

        self.metrics["total_size_bytes"] += file_size

        # File count limit enforcement
        if self.files_discovered > self.max_files:
            self.metrics["skipped_files"] += 1
            return {
                "relative_path": rel_file,
                "entry_type": "file",
                "language": "unknown",
                "file_size_bytes": file_size,
                "file_hash": None,
                "classification": "other",
                "status": "skipped",
                "skip_reason": f"Maximum file count ({self.max_files}) limit reached",
                "is_test": False,
                "is_manifest": False,
                "ast_metadata": None,
            }

        filename = file_path.name
        ext = file_path.suffix.lower()
        lower_name = filename.lower()

        # Language detection
        if ext in BINARY_EXTENSIONS:
            lang = "binary"
        else:
            lang = EXTENSION_LANGUAGE_MAP.get(ext, "unknown")

        is_manifest = (
            lower_name in MANIFEST_FILENAMES
            or (lower_name.startswith("requirements") and lower_name.endswith(".txt"))
        )
        if is_manifest:
            self.metrics["manifest_files"] += 1
            self.metrics["detected_manifests"].add(filename)

        # Quick binary check by content
        is_binary = lang == "binary"
        if not is_binary and file_size > 0:
            try:
                with open(file_path, "rb") as bf:
                    head = bf.read(1024)
                    if is_binary_content(head):
                        is_binary = True
                        lang = "binary"
            except Exception:
                is_binary = True

        classification = detect_file_classification(rel_file, lang)
        is_test = classification == "test"
        if is_test:
            self.metrics["test_files"] += 1

        # Check skip conditions
        if is_binary:
            self.metrics["skipped_files"] += 1
            return {
                "relative_path": rel_file,
                "entry_type": "file",
                "language": "binary",
                "file_size_bytes": file_size,
                "file_hash": compute_sha256(file_path) if file_size <= self.max_file_size else None,
                "classification": "binary_data",
                "status": "skipped",
                "skip_reason": "Binary file skipped from content analysis",
                "is_test": False,
                "is_manifest": False,
                "ast_metadata": None,
            }

        if file_size > self.max_file_size:
            self.metrics["skipped_files"] += 1
            return {
                "relative_path": rel_file,
                "entry_type": "file",
                "language": lang,
                "file_size_bytes": file_size,
                "file_hash": compute_sha256(file_path),
                "classification": classification,
                "status": "skipped",
                "skip_reason": f"File size ({file_size} bytes) exceeds content analysis limit ({self.max_file_size} bytes)",
                "is_test": is_test,
                "is_manifest": is_manifest,
                "ast_metadata": None,
            }

        if (self.total_bytes_analyzed + file_size) > self.max_total_bytes:
            self.metrics["skipped_files"] += 1
            return {
                "relative_path": rel_file,
                "entry_type": "file",
                "language": lang,
                "file_size_bytes": file_size,
                "file_hash": compute_sha256(file_path),
                "classification": classification,
                "status": "skipped",
                "skip_reason": "Total repository content analysis byte limit reached",
                "is_test": is_test,
                "is_manifest": is_manifest,
                "ast_metadata": None,
            }

        # Content Analysis
        content = ""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.total_bytes_analyzed += len(content.encode("utf-8"))
        except Exception as e:
            self.metrics["skipped_files"] += 1
            return {
                "relative_path": rel_file,
                "entry_type": "file",
                "language": lang,
                "file_size_bytes": file_size,
                "file_hash": None,
                "classification": classification,
                "status": "failed",
                "skip_reason": f"Failed to read file: {str(e)}",
                "is_test": is_test,
                "is_manifest": is_manifest,
                "ast_metadata": None,
            }

        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ast_metadata = None

        # Track source files
        if classification == "source_code":
            self.metrics["supported_source_files"] += 1

        # Manifest metadata inspection
        if is_manifest:
            manifest_info = detect_manifest_metadata(filename, content)
            if manifest_info:
                ast_metadata = {"manifest_info": manifest_info}
                # Check for test framework hints in manifest
                m_data = manifest_info.get("data", {})
                if m_data.get("has_pytest_config") or m_data.get("has_pytest"):
                    self.metrics["detected_frameworks"].add("pytest")
                if m_data.get("has_tox"):
                    self.metrics["detected_frameworks"].add("tox")

        # Python AST parsing
        if lang == "python":
            ast_result = analyze_python_source(content, filename=rel_file)
            ast_metadata = ast_result

            if ast_result.get("syntax_error"):
                self.metrics["parse_errors"] += 1

            if ast_result.get("has_test_elements"):
                is_test = True
                if classification != "test":
                    classification = "test"
                    self.metrics["test_files"] += 1

            # Framework detection from Python imports & AST
            for ind in ast_result.get("test_indicators", []):
                if "pytest" in ind:
                    self.metrics["detected_frameworks"].add("pytest")
                if "unittest" in ind:
                    self.metrics["detected_frameworks"].add("unittest")

        # Fallback check for test configuration files
        if filename == "pytest.ini" or filename == "conftest.py":
            self.metrics["detected_frameworks"].add("pytest")
        elif filename == "tox.ini":
            self.metrics["detected_frameworks"].add("tox")

        return {
            "relative_path": rel_file,
            "entry_type": "file",
            "language": lang,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "classification": classification,
            "status": "content_analyzed",
            "skip_reason": None,
            "is_test": is_test,
            "is_manifest": is_manifest,
            "ast_metadata": ast_metadata,
        }

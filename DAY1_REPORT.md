# RepoPilot AI — Day 1 Implementation Report

**Date:** 2026-10-18  
**Scope:** Foundation, Safe Repository Ingestion, AST Analysis, and Developer Dashboard  
**Status:** Complete & Validated  

---

## 1. Executive Summary

Day 1 of RepoPilot AI establishes the core ingestion engine, safety guardrails, recursive AST analyzer, database persistence layer, and interactive Next.js developer dashboard. The system accepts repository archives, enforces strict security checks, recurses nested folder hierarchies, captures AST structures without code execution, discovers test infrastructure, and exposes a real-time developer interface.

---

## 2. Implemented Features

### 2.1 Security & Archive Validation (`POST /api/v1/repositories/upload`)
- **Path Traversal Protection:** Pre-extraction inspection checks every member for `..` segments, null bytes, Unix absolute paths (`/...`), Windows drive letters (`C:/...`), and UNC network shares.
- **Archive Bomb Mitigation:** Enforces configurable limits on:
  - Maximum upload size (50 MB default).
  - Maximum entry count (10,000 entries default).
  - Maximum expanded uncompressed size (200 MB default).
  - Maximum single-file size (25 MB default).
  - Maximum compression ratio threshold (50:1 default).
- **Symlink Neutralization:** Unix symlinks (`S_IFLNK`) are detected and rejected (`UNSAFE_SYMLINK_DETECTED`) to block symlink-based arbitrary file reads and path escapes.
- **Safe Extraction Streaming:** Archives are extracted member-by-member while tracking disk bytes written to guard against corrupted or deceptive central directory headers.
- **Non-Execution Invariant:** Uploaded source code is never executed, imported, or compiled into bytecode.
- **Information Leakage Prevention:** Server-internal paths and Python tracebacks are masked; structured error payloads (`error_code`, `message`, `details`) are returned.

### 2.2 Recursive Repository Analyzer
- **Streaming Traversal:** Uses generator-based filesystem traversal to stream discovered files and directories without loading the entire hierarchy into memory.
- **Configurable Directory Exclusions:** Directories such as `.git`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `__pycache__`, and test caches are inventoried as `status="skipped"` with transparent skip reasons (`"Excluded directory (.git)"`) rather than silently omitted.
- **Traversal Limits:** Enforces limits on directory depth (`MAX_TRAVERSAL_DEPTH=15`), file count (`MAX_FILE_COUNT=5000`), per-file analysis size (`MAX_ANALYSIS_FILE_BYTES=2MB`), and total content read (`MAX_TOTAL_ANALYSIS_BYTES=50MB`).
- **File Classification:** Categorizes files into:
  - `source_code` (Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, HTML, CSS, SQL)
  - `test` (files matching `test_*.py`, `*_test.py`, `conftest.py`, or located in `tests/`, `test/`, `spec/`)
  - `configuration` (`.ini`, `.cfg`, `.toml`, `docker-compose.yml`, `tsconfig.json`)
  - `documentation` (`.md`, `.rst`, `LICENSE`, `README`)
  - `generated_output` (`.pyc`, `.map`, `.log`)
  - `binary_data` (images, compiled binaries, executables, or null-byte headers)
- **Separate Statuses:** File entries maintain distinct statuses: `inventoried`, `content_analyzed`, `skipped`, or `failed`.

### 2.3 Python AST Analysis
- **AST Parsing:** Employs `ast.parse` without importing or running target files.
- **Structural Extraction:** Extracts module `imports`, declared `classes` (with base classes and test class flags), and `functions` (with async indicators and line numbers).
- **Graceful Syntax Error Handling:** Files with syntax errors do not crash the scan; instead, error message, line number, offset, and code snippets are captured as analysis findings.

### 2.4 Test Infrastructure & Manifest Discovery
- **Test Framework Detection:** Discovers `pytest` (via `pytest.ini`, `conftest.py`, `pyproject.toml`, or AST imports), `unittest` (via `unittest.TestCase` subclasses or imports), and `tox` (via `tox.ini`).
- **Safe Manifest Parsing:** Parses package requirements from `requirements.txt` and project configuration from `pyproject.toml` (PEP 621 / Poetry) without executing dependency scripts.

### 2.5 Metadata Persistence (SQLite + SQLAlchemy)
- **Repository Model:** Stores repository UUID, name, original filename, upload size, status, and timestamps.
- **ScanJob Model:** Stores scan job UUID, repository foreign key, start/completion timestamps, rollup metrics (total files, source files, tests, manifests, skipped files, parse errors), detected frameworks, and detected manifests.
- **RepositoryFile Model:** Stores file UUID, relative POSIX path, classification, language, file size, SHA-256 hash, analysis status, skip reason, test flag, manifest flag, and JSON AST metadata.

### 2.6 Developer Dashboard (Next.js 14 + Tailwind CSS)
- **Dashboard Home (`/`):** Ingest repository modal, live backend status indicator, and repository list with file metrics and delete options.
- **Repository Overview (`/repositories/[id]`):**
  - Metric summary cards (Total Files, Source Files, Tests, Manifests, Skipped Files, Parse Errors).
  - Detected framework and manifest pill badges.
  - Interactive recursive File Explorer with collapsible folders and file classification badges.
  - Search and filter bar (filter by classification, status, path search, or syntax errors).
  - File Detail Drawer showing relative path, file size, SHA-256 hash, AST classes, functions, imports, and syntax error alerts.

---

## 3. Automated Test Suite & Results

### 3.1 Test Coverage Matrix

| Test ID | Area | Test Description | Expected Result | Verified Result |
|---|---|---|---|---|
| **SEC-01** | Upload Security | Reject non-ZIP file uploads | HTTP 400 (`INVALID_FILE_TYPE`) | **PASS** |
| **SEC-02** | Upload Security | Reject corrupt/malformed ZIP headers | HTTP 400 (`MALFORMED_ZIP`) | **PASS** |
| **SEC-03** | Upload Security | Reject path traversal (`../../evil.txt`) | HTTP 400 (`PATH_TRAVERSAL_DETECTED`) | **PASS** |
| **SEC-04** | Upload Security | Reject Unix absolute paths (`/etc/...`) | HTTP 400 (`ABSOLUTE_PATH_DETECTED`) | **PASS** |
| **SEC-05** | Upload Security | Reject Windows drive paths (`C:/...`) | HTTP 400 (`ABSOLUTE_PATH_DETECTED`) | **PASS** |
| **SEC-06** | Upload Security | Reject Unix symbolic link entries | HTTP 400 (`UNSAFE_SYMLINK_DETECTED`) | **PASS** |
| **SEC-07** | Upload Security | Reject high compression ratio zip bombs | HTTP 400 (`COMPRESSION_RATIO_EXCEEDED`) | **PASS** |
| **SEC-08** | Upload Security | Reject oversized single files in archive | HTTP 400 (`FILE_SIZE_LIMIT_EXCEEDED`) | **PASS** |
| **AST-01** | AST Parser | Extract imports, classes, functions, async | Structurally parsed without execution | **PASS** |
| **AST-02** | AST Parser | Graceful handling of Python syntax errors | Captured in metadata without scan crash | **PASS** |
| **MAN-01** | Manifest Parser | Safe parsing of requirements.txt | Package list extracted cleanly | **PASS** |
| **MAN-02** | Manifest Parser | Safe parsing of pyproject.toml | Dependencies and pytest settings parsed | **PASS** |
| **CLS-01** | Classifier | Rules for source, test, config, docs, binary | Correct classification per rule | **PASS** |
| **REC-01** | Analyzer | Recursive scan on nested sample repository | Correct inventory, exclusions, rollup | **PASS** |
| **LIM-01** | Analyzer | Depth and file size limit enforcement | Skipped with explicit skip reason | **PASS** |
| **E2E-01** | API E2E | Upload, tree generation, filter, AST, delete | End-to-end integration verified | **PASS** |

### 3.2 Test Execution Commands

To execute the test suite using the standalone runner:
```bash
cd backend
python test_runner.py
```

Or using `pytest`:
```bash
cd backend
pytest -v
```

---

## 4. Known Limitations & Design Decisions (Day 1)

1. **No Code Execution on Day 1:** Uploaded repositories are purely inventoried, AST-parsed, and statically analyzed. No virtual environments are created, no packages are installed, and no baseline tests are executed. This is intentional per the Day 1 specification to ensure zero-trust ingestion.
2. **Synchronous Scan Pipeline:** For Day 1, repository analysis runs immediately upon archive validation. In Day 2, large repositories (>10,000 files) will be transitioned to asynchronous Celery/Redis or background workers with WebSockets/Server-Sent Events for live progress.
3. **SQLite Persistence:** SQLite is configured with WAL mode for local hackathon and single-node development. The SQLAlchemy model architecture is database-agnostic and ready for PostgreSQL in distributed deployments.
4. **Symbolic Links Policy:** For maximum security against symlink race conditions and directory escapes, ZIP archives containing symbolic links are rejected.

---

## 5. Next Steps for Day 2

1. **Isolated Execution Sandbox:** Set up Docker or containerized execution sandboxes (with ephemeral network isolation) to safely install dependencies from detected manifests (`requirements.txt`, `pyproject.toml`).
2. **Baseline Test Runner:** Implement automated test discovery and execution for detected test frameworks (`pytest`, `unittest`).
3. **Failure Capture & Triage:** Parse stdout/stderr test runner logs, extract failing assertions, traceback frames, and line numbers.
4. **AI Diagnosis Engine:** Connect LLM agent to analyze failing test tracebacks alongside repository AST findings to formulate bug hypotheses.
5. **Minimal Patch Generator & Validation:** Generate targeted patches, apply them to an isolated workspace branch, re-run baseline tests, and verify fix efficacy without regression.

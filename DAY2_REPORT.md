# RepoPilot AI — Day 2 Implementation Report

**Date:** 2026-10-18  
**Scope:** Real Baseline Test Execution, Docker Sandbox Security, and Evidence Capture  
**Status:** Complete & Validated  

---

## 1. Executive Summary

Day 2 of RepoPilot AI introduces isolated baseline test execution and evidence capture. Building on Day 1's safe ingestion and AST analysis, RepoPilot now automatically detects supported test commands, creates isolated workspace snapshots, executes tests within hardened container boundaries, and persists structured execution records—capturing exit codes, test summaries, durations, and exact failure tracebacks while preventing any execution of repository code in the server process.

---

## 2. Implemented Features

### 2.1 Execution Worker Component
- **Container Sandbox (`DockerWorker`):**
  - Uses pinned base image (`python:3.11-slim` or custom worker image).
  - Executes as non-root user (`UID 1000:1000`).
  - Drops all Linux capabilities (`--cap-drop=ALL`).
  - Blocks privilege escalation (`--security-opt=no-new-privileges`).
  - Read-only root filesystem with isolated volatile tmpfs (`/tmp:rw,noexec,nosuid,size=64m`).
  - Enforces resource limits: CPU limit (`1.0`), memory limit (`512m`), and PID limit (`100`) to prevent fork bombs.
  - Mounts only the isolated job workspace copy; host files, Docker socket, SSH keys, and cloud credentials are never exposed.
  - Enforces wall-clock timeout (`60s`) with automated SIGKILL and cleanup.
  - `finally`-style error handling guarantees container removal (`docker rm -f repopilot-job-{id}`) and workspace deletion.
- **Offline Network Isolation:**
  - Test execution stage runs with `--network=none`, blocking data exfiltration, reverse shells, and external network dependencies during tests.
  - Dependencies are installed in a separate controlled preparation stage before the offline test run.
- **Pluggable Architecture (`FakeWorker` & `factory.py`):**
  - High-fidelity simulated worker allows automated unit and API testing on environments without a running Docker daemon.
  - The worker factory provides `auto` detection, using Docker when healthy and falling back cleanly with full diagnostics.

### 2.2 Test Discovery & Security Precedence
- **Documented Precedence Order:**
  1. `pytest.ini`
  2. `pyproject.toml` (with `[tool.pytest]`)
  3. `setup.cfg` or `tox.ini` (with `[pytest]` or `[tool:pytest]`)
  4. `tests/` or `test/` directory
  5. Test file naming convention (`test_*.py`, `*_test.py`, `conftest.py`)
- **Strict Command Whitelisting:**
  - Whitelist: `pytest`, `python -m pytest`, `python -m unittest` with allowed flags (`-v`, `-q`, `-s`, `--tb=short`).
  - Rejects arbitrary shell commands (`bash -c`, `rm -rf`, metacharacters `;`, `&`, `|`, `` ` ``) with HTTP 400 (`INVALID_COMMAND`).

### 2.3 Evidence Capture & Log Sanitization
- **Pytest Output Parser (`parser.py`):**
  - Extracts total, passed, failed, skipped, and error test counts.
  - Extracts failure blocks with test name, file path, line number, and traceback diffs.
- **Categorized Error Classification:**
  - `test_failure`: Code assertions or test conditions failed (exit code 1).
  - `setup_error`: Missing or unresolvable dependencies in preparation stage (distinguished from code failures).
  - `syntax_error`: Python syntax error prevented test collection (exit code 2).
  - `timeout_error`: Execution exceeded wall-clock limit (exit code 124).
  - `infrastructure_error`: Container launch or environment fault.
- **Log Sanitizer (`sanitizer.py`):**
  - Masks passwords, API keys, tokens, and bearer credentials.
  - Enforces bounded storage limit (`500 KB`), preserving initial setup context and final tracebacks.

### 2.4 Persistence Layer (SQLAlchemy + SQLite)
- **`ExecutionJob` Model:** Stores UUID, repository foreign key, timestamps, status, granular stages (`queued` → `preparing` → `detecting_command` → `executing_tests` → `capturing_results` → `finished`), exit code, timeout flag, test counts, JSON failure list, bounded stdout/stderr/setup logs, and applied resource limits.

### 2.5 REST API v1
- `POST /api/v1/jobs`: Starts background execution job, returning immediately with status `pending`.
- `GET /api/v1/jobs/{id}`: Returns job status, stage, test counts, duration, and failure tracebacks.
- `GET /api/v1/jobs/{id}/logs`: Returns bounded, sanitized stdout, stderr, and preparation logs.
- `POST /api/v1/jobs/{id}/cancel`: Safely terminates active worker container.
- `GET /api/v1/repositories/{id}/jobs`: Lists test execution history for a repository.

### 2.6 Frontend Developer Dashboard
- **Execution Panel Component (`ExecutionPanel.tsx`):**
  - One-click "Run Baseline Tests" trigger with loading state.
  - Live stage progress indicator with 1.5s background polling.
  - Prominent status banner with duration, exit code, base image, and network policy badges.
  - Test count pills (Total, Passed, Failed, Errors, Skipped).
  - Collapsible failure cards showing highlighted tracebacks.
  - Expandable terminal log viewer (Stdout, Stderr, Setup Logs) with copy action.
  - Run history selector to inspect past test executions.

---

## 3. Automated Test Suite & Coverage

All 31 automated tests execute cleanly via `backend/test_runner.py`:

| Test ID | Category | Description | Result |
|---|---|---|---|
| **SEC-01** to **SEC-08** | Ingestion Security | Path traversal, absolute paths, symlinks, bombs, sizes | **PASS** |
| **AST-01** to **AST-02** | AST Analysis | Python AST structure, syntax error capture | **PASS** |
| **MAN-01** to **MAN-02** | Manifests | Requirements & pyproject.toml parsing | **PASS** |
| **REC-01** to **LIM-01** | Analyzer | Recursive scanning, exclusions, depth/size limits | **PASS** |
| **DAY1-E2E** | API | Upload, tree generation, search & filter | **PASS** |
| **CMD-01** | Worker Security | Test command whitelisting & injection rejection | **PASS** |
| **DISC-01** | Discovery | Test command precedence & manifest detection | **PASS** |
| **PARSE-01** | Parser | Pytest output summary & failure traceback parsing | **PASS** |
| **SAN-01** | Sanitizer | Secret masking & 500KB bounded log truncation | **PASS** |
| **SCEN-01** | Sandbox Scenarios | Scenario 1: All tests passing cleanly (3 passed) | **PASS** |
| **SCEN-02** | Sandbox Scenarios | Scenario 2: Deterministic failing assertion captured | **PASS** |
| **SCEN-03** | Sandbox Scenarios | Scenario 3: Syntax error during test collection | **PASS** |
| **SCEN-04** | Sandbox Scenarios | Scenario 4: Missing dependencies classified as setup_error | **PASS** |
| **SCEN-05** | Sandbox Scenarios | Scenario 5: Wall-clock timeout enforcement | **PASS** |
| **SCEN-06** | Sandbox Scenarios | Scenario 6: Forbidden network access blocked under `--network=none` | **PASS** |
| **DOCKER-01** | Docker Worker | Docker environment diagnostic availability check | **PASS** |
| **JOB-API-01** | API | POST /api/v1/jobs input & command validation | **PASS** |
| **JOB-API-02** | API | Background execution & evidence capture E2E | **PASS** |
| **JOB-API-03** | API | Failing assertion capture & traceback exposure | **PASS** |
| **JOB-API-04** | API | POST /api/v1/jobs/{id}/cancel termination | **PASS** |

### Test Execution Commands
```bash
cd backend
python test_runner.py
# or with pytest:
pytest -v
```

---

## 4. Known Limitations & Constraints (Day 2)

1. **Python / Pytest Focus:** Test runner and output parser currently focus on standard Python test workflows (`pytest` and `unittest`). Multi-language test runners (e.g., Jest, Vitest, Go test, Cargo test) will be added in later stages.
2. **Container Escapes:** Standard Docker containers share the host Linux kernel. For public, untrusted multi-tenant deployments, microVM isolation (Firecracker or gVisor) is recommended.
3. **Pre-Installed Tooling:** The base container image provides `python:3.11-slim` with `pytest`. Heavy C-extensions or external database services are not pre-installed by default.

---

## 5. Next Steps for Day 3

1. **AI Diagnosis Engine:** Feed captured failure tracebacks and AST function/class definitions to LLM prompts to analyze the root cause of test failures.
2. **Automated Patch Generation:** Generate syntactically valid code patches targeting the failing lines identified in tracebacks.
3. **Isolated Patch Validation:** Apply candidate patches in a branched workspace copy, re-run tests in the container sandbox, and verify that previously failing tests now pass without regression.
4. **Evidence-Based Reporting:** Present diffs, before-and-after test execution summaries, and validation logs in the frontend dashboard.

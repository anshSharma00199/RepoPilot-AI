# RepoPilot AI — Autonomous Software Debugging & Verification Platform

RepoPilot AI is an AI-assisted software debugging platform. It accepts a software repository, recursively analyzes its directory tree and files, identifies test infrastructure, parses Python AST structures, prepares an inventory, and executes baseline tests in an isolated, non-root sandbox to capture real test evidence and failure tracebacks.

The complete workflow is:
```
Repository Upload → Recursive Analysis → Isolated Baseline Test Execution → AI Diagnosis → Minimal Patch → Isolated Validation → Evidence-Based Report
```

---

## Architecture Overview

```
RepoPilot AI
├── backend/                  # Python FastAPI Backend Service
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint, lifespan startup recovery, CORS & error handlers
│   │   ├── config.py         # Pydantic Settings with security, worker & validation limits
│   │   ├── database.py       # SQLAlchemy engine & SQLite schema initialization
│   │   ├── models/           # DB Models: Repository, ScanJob, RepositoryFile, ExecutionJob, DiagnosticReport, ValidationRun
│   │   ├── schemas/          # Pydantic V2 schemas: Repository, Job, Diagnostic, Validation, Audit
│   │   ├── services/
│   │   │   ├── security.py   # Safe archive extraction, bomb & traversal checks
│   │   │   ├── analyzer.py   # Recursive repository analyzer & streaming generator
│   │   │   ├── ast_parser.py # Safe Python AST parsing & syntax error capture
│   │   │   ├── manifest.py   # Requirements & pyproject.toml detection & parsing
│   │   │   ├── test_discovery.py # Command precedence & whitelist enforcement
│   │   │   ├── executor.py   # Background execution orchestrator & workspace manager
│   │   │   ├── retriever.py  # Evidence-based AST & traceback context retriever
│   │   │   ├── patch_validator.py # Multi-layer patch validation & AST syntax check
│   │   │   ├── diagnostic_service.py # Core diagnosis orchestration & human review
│   │   │   ├── patch_applier.py # Isolated snapshot cloning & patch application engine
│   │   │   ├── verdict_engine.py # Evidence-based central verdict evaluation & reason codes
│   │   │   ├── validation_service.py # Orchestrator for sandboxed validation & bounded retries
│   │   │   ├── audit_service.py # Repository analysis audit & coverage invariant calculator
│   │   │   ├── llm/          # LLM Provider Abstraction (Gemini & FakeProvider)
│   │   │   │   ├── interface.py
│   │   │   │   ├── gemini_provider.py
│   │   │   │   ├── fake_provider.py
│   │   │   │   └── factory.py
│   │   │   └── archive.py    # Upload chunk streaming & file storage management
│   │   ├── worker/           # Dedicated Execution Worker Component
│   │   │   ├── interface.py  # Abstract ExecutionWorker interface & data contracts
│   │   │   ├── docker_worker.py # Docker sandbox runner (non-root, --network=none, limits)
│   │   │   ├── fake_worker.py# High-fidelity simulated worker for tests/offline
│   │   │   ├── factory.py    # Worker factory managing auto-detection
│   │   │   ├── parser.py     # Structured pytest summary & traceback parser
│   │   │   └── sanitizer.py  # Credential masking & bounded log truncation
│   │   └── api/v1/           # REST endpoints: /repositories, /files, /jobs, /diagnostics, /validations
│   ├── docker/
│   │   └── Dockerfile.worker # Pinned sandboxed container image definition
│   ├── tests/                # Automated pytest suite (49 tests covering Days 1-5)
│   └── test_runner.py        # Standalone zero-dependency test runner
├── sample_repositories/      # Realistic Python demonstration repositories
│   ├── demo_order_pricing/   # Active e-commerce pricing demo project
│   ├── demo_order_pricing_buggy/ # Reference buggy copy for reproducible runs
│   └── demo_order_pricing_fixed/ # Reference verified fixed copy
├── sample_archives/          # Pre-generated test repos & attack archives
├── generate_sample_archive.py# Test archive generator script
├── DEMO_SCRIPT.md            # 5-minute repeatable demonstration script
└── frontend/                 # Next.js 14 Developer Dashboard
    └── src/
        ├── app/              # App Router (Dashboard & Repository Detail Views)
        ├── components/       # ExecutionPanel, DiagnosticReviewModal, FinalReportModal, AnalysisAuditModal
        └── lib/              # TypeScript types & API client
```

---

## Key Features Implemented

### Day 1: Foundation & Safe Repository Ingestion
1. **Security-First Repository Ingestion (`POST /api/v1/repositories/upload`)**:
   - Rejects `../` traversal, null bytes, Unix absolute paths (`/...`), Windows drive letters (`C:/...`), and UNC paths.
   - Enforces limits on entry count (10,000), total expanded size (200MB), single file size (25MB), and compression ratio (50:1).
   - Rejects Unix symlinks (`UNSAFE_SYMLINK_DETECTED`).
   - Server paths are private; no code is executed in the API process.
2. **Recursive Repository Analyzer**:
   - Streaming generator with limits on traversal depth (`15`), file count (`5,000`), and file size (`2MB`).
   - Excluded directories (`.git`, `node_modules`, `venv`, etc.) are transparently recorded as `status="skipped"`.
   - File classification (`source_code`, `test`, `configuration`, `documentation`, `generated_output`, `binary_data`).
3. **Python AST Analysis**:
   - Non-executing AST parsing extracting imports, classes, functions, and async methods.
   - Syntax errors captured as analysis findings without crashing ingestion.
4. **Test Infrastructure & Manifest Discovery**:
   - Detects `pytest`, `unittest`, `tox`, `requirements.txt`, and `pyproject.toml`.

### Day 2: Real Baseline Test Execution & Evidence Capture
1. **Dedicated Execution Worker & Sandbox**:
   - **Isolation Boundary:** Tests execute in dedicated Docker containers with non-root user (`1000:1000`), all Linux capabilities dropped (`--cap-drop=ALL`), privilege escalation blocked (`--security-opt=no-new-privileges`), and read-only root with temporary tmpfs.
   - **Zero Network Access During Tests:** Test execution runs with `--network=none` to prevent data exfiltration, reverse shells, or remote resource tampering.
   - **Two-Stage Execution:** Controlled preparation stage for dependency installation, followed by isolated offline test run.
   - **Resource & Timeout Limits:** Strict limits on CPU (`1.0`), memory (`512m`), processes (`100 PIDs`), and wall-clock timeout (`60s`).
   - **Guaranteed Cleanup:** `finally`-style error handling ensures containers and temporary workspace copies are always deleted.
2. **Test Command Precedence & Security Whitelisting**:
   - Follows documented precedence: `pytest.ini` → `pyproject.toml` → `setup.cfg/tox.ini` → `tests/` directory → `test_*.py` files.
   - Strictly validates commands against a whitelist (`pytest`, `python -m pytest`, `python -m unittest`). Arbitrary shell strings (`bash -c`, `rm -rf`, metacharacters `;`, `&`, `|`, `` ` ``) are rejected immediately.
3. **Structured Evidence & Error Classification**:
   - Distinguishes between `test_failure`, `setup_error`, `syntax_error`, `timeout_error`, and `infrastructure_error`.
   - Extracts individual failure items with test name, file, line number, and full failure traceback.
   - Masked credentials and bounded log output (max 500 KB) with head/tail preservation.
4. **Interactive Execution Panel (Frontend)**:
   - "Run Baseline Tests" one-click action.
   - Live stage progression (`queued` → `preparing` → `installing_dependencies` → `executing_tests` → `finished`).
   - Test count pills (Total, Passed, Failed, Errors, Skipped) and execution duration.
   - Expandable failure cards displaying highlighted tracebacks and assertion diffs.
   - Expandable log viewer (Stdout, Stderr, Setup Logs) with copy functionality.

### Day 3: LLM Diagnosis & Safe Patch Proposals
1. **Core Evidence Pipeline**:
   - Requires actual baseline failure evidence (`tests_failed > 0` or `status="failed"`) before proposing a patch, preventing hallucinated fixes without reproducible failures.
   - Evidence-based source retrieval builds bounded context (up to 64k chars) from original failing assertions, traceback frames, 20-line source windows, AST import maps, and related module definitions.
2. **Untrusted Repository Content & Prompt Injection Defense**:
   - Treats all uploaded files, comments, docstrings, and test logs as untrusted subject data.
   - Encases all retrieved source code in `<untrusted_repo_content>` XML fences with system directives instructing the model that code contents cannot override system instructions, security boundaries, or approval rules.
3. **Pluggable LLM Provider Abstraction**:
   - Provider interface supporting Google Gemini (structured JSON output, timeout bounds, and retries) and an explicitly selected deterministic `FakeLLMProvider` for tests/demo fixtures. In `LLM_PROVIDER=auto`, the backend now fails clearly when real provider credentials are missing rather than silently showing simulated output as an external-repository diagnosis.
   - API keys are strictly configured via server environment variables (`GEMINI_API_KEY`) and are never exposed to the frontend, logs, reports, or repo artifacts.
   - Provider failures (timeouts, rate limits, malformed JSON) are transparently categorized as AI Provider Errors, clearly distinguished from repository test failures.
4. **Multi-Layer Patch Security & Syntax Validation Engine**:
   - Parses unified diff hunks and enforces security bounds: rejects path traversal (`../`) and absolute paths, verifies all modified files exist in the repository inventory, enforces limits on diff size (50KB) and modified files (max 5).
   - In-memory dry-run patch application against temporary file copies.
   - Non-executing AST syntax verification (`ast.parse`) on patched Python files to prevent syntax regressions before human review.
5. **Human-in-the-Loop Review Workflow**:
   - Proposed patches remain in `status="proposed"` until explicitly reviewed.
   - Review endpoints (`POST /api/v1/diagnostics/{id}/approve` and `/reject`) enforce that only patches with `patch_validation_status="valid"` can be approved.
6. **Frontend Diagnostic Review Modal**:
   - Displays root cause hypothesis, confidence score, and explanation.
   - Unified diff viewer with syntax-highlighted additions and deletions.
   - Inspected evidence references with file path, line numbers, and snippets.
   - Impact and risk analysis with potential regression warnings and recommended tests.
   - Interactive Approve and Reject review controls with optional reviewer notes.

### Day 4: Real Isolated Test Execution & Central Verdict Engine
1. **Isolated Snapshot & Safe Patch Application (`patch_applier.py`)**:
   - **Canonical Storage Immutability:** Never applies patches directly to the original upload or baseline storage.
   - **Isolated Snapshot Creation:** Clones the original repository to an isolated, dedicated snapshot directory (`storage/snapshots/{snapshot_id}`).
   - **Path Containment & Traversal Defense:** Verifies all modified file paths are within the snapshot boundary, rejecting directory traversal (`../`) and absolute paths.
   - **Deterministic Audit Trail:** Computes SHA-256 workspace hash before and after patch application for immutable provenance tracking.
2. **Central Evidence-Based Verdict Engine (`verdict_engine.py`)**:
   - **Three Mutually Exclusive Top-Level Verdicts:** `VALIDATED`, `UNVALIDATED`, `INFRASTRUCTURE_ERROR`.
   - **9 Granular Machine-Readable Reason Codes:**
     - `VERDICT_VALIDATED_FIX`: Target failure resolved, regression suite green.
     - `VERDICT_TARGET_STILL_FAILS`: Patched code still fails target assertion.
     - `VERDICT_REGRESSION_DETECTED`: Previously passing tests now fail after patch.
     - `VERDICT_NO_REPRODUCED_FAILURE`: Baseline had 0 failures (Scenario D reproduction invariant).
     - `VERDICT_EXECUTION_TIMED_OUT`: Test execution exceeded wall-clock limit.
     - `VERDICT_PATCH_APPLICATION_FAILED`: Malformed diff or patch reject.
     - `VERDICT_INSUFFICIENT_COVERAGE`: Project lacks identifiable test suite.
     - `VERDICT_INFRASTRUCTURE_FAILURE`: Container runner or worker daemon failure.
     - `VERDICT_ATTEMPTS_EXHAUSTED`: Maximum retry attempts reached.
   - **Reproduction Invariant:** Requires baseline evidence to have confirmed failures; baseline passing cannot yield a validated-fix claim.
3. **Bounded Patch Validation & Retry Orchestrator (`validation_service.py`)**:
   - Maximum 2 AI patch attempts per job (`MAX_PATCH_ATTEMPTS = 2`) to prevent runaway API spend or unbounded loops.
   - Retries must never bypass human review. Only patches with review status `approved` and validation status `valid` can be validated.
   - Fresh isolated execution in a clean container under `--network=none` with the patched snapshot.
4. **Segregated Evidence-Based Audit Reporting (`FinalEvidenceReport`)**:
   - Measurement vs Prediction Segregation: Measured test execution data are strictly segregated from AI-generated hypotheses.
   - Full Audit Lineage: Tracks original repo hash, baseline job ID, diagnostic report ID, patch hash, workspace hash, and reviewer notes.
   - Honest Limitations Caveat: Explicitly notes that a `VALIDATED` verdict only certifies that executed tests passed; it cannot guarantee the absence of latent bugs outside test coverage.
5. **Interactive Final Evidence Report Modal (`FinalReportModal.tsx`)**:
   - Central Verdict Banner with dynamic color-coding and machine reason codes.
   - Side-by-side Before vs After test metrics comparison.
   - Target test resolution indicator and regression test badges.
   - Approved patch diff viewer with highlighted changes.
   - One-click JSON Audit Report export for compliance and CI/CD integration.

### Day 5: Integration, Correctness, Security Hardening & Complete Demonstration
1. **Repository Analysis Coverage Summary & Invariant (`audit_service.py`)**:
   - `GET /api/v1/repositories/{id}/analysis-audit` calculates complete repository analysis metrics: total files/dirs, inventoried files, content-analyzed files, AST successes/failures, test and config files, policy-excluded files, and format/size skipped files.
   - **Enforced Coverage Invariant:** Never reports 100% content analysis if any files were skipped, excluded by policy, or unsupported.
   - Analysis Audit Modal (`AnalysisAuditModal.tsx`) provides transparent visibility with category breakdowns and specific skipped file reasons.
2. **Enhanced Credential Sanitization & Key Masking (`sanitizer.py`)**:
   - Scrubs configured API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`).
   - Deep regex scanning masks GitHub tokens (`ghp_...`, `github_pat_...`), GitLab tokens (`glpat-...`), AWS access keys (`AKIA...`), Google API keys (`AIza...`), PEM private key blocks (`BEGIN PRIVATE KEY`), and HTTP Basic Authentication headers.
   - Logs are truncated with 500KB cap preserving head and tail diagnostic context.
3. **Graceful Backend Startup Recovery (`executor.py`)**:
   - On backend startup (FastAPI lifespan), `recover_interrupted_jobs()` sweeps the database for jobs left in `pending`, `preparing`, or `running` state.
   - Safely transitions abandoned jobs to `failed` with explicit reason `SYSTEM_RESTARTED`, preventing stale zombie states.
4. **Duplicate Request Prevention & Job Idempotency (`jobs.py`)**:
   - Re-requesting a baseline test job for a repository that already has an active running job idempotently returns the existing job instead of spawning duplicate resource-intensive sandboxes.
5. **Realistic Demonstration Repository (`sample_repositories/demo_order_pricing`)**:
   - Realistic multi-module Python e-commerce pricing engine.
   - Deterministic mathematical bug in `calculate_discounted_price` (discount amount returned instead of deducted).
   - Targeted unit test reproducing the failure (`assert 20.0 == 80.0`).
   - Complete regression suite (`test_tax_service.py` and zero-discount edge cases).
   - Pyproject/pytest manifest and documentation.

---

## Feature Matrix

| Feature / Capability | Component | Scope / Layer | Status | Notes |
|---|---|---|---|---|
| **Archive Ingestion & Traversal Defense** | `backend/app/services/security.py` | Security / Backend | **Implemented & Tested** | Rejects `../`, null bytes, symlinks, absolute paths, zip bombs. |
| **Recursive Repository Inventory** | `backend/app/services/analyzer.py` | Ingestion / Backend | **Implemented & Tested** | Streaming traversal; depth, file count, and size bounds enforced. |
| **Python AST Symbol Analysis** | `backend/app/services/ast_parser.py` | Analysis / Backend | **Implemented & Tested** | Non-executing AST parse; captures functions, classes, imports, errors. |
| **Analysis Coverage Audit & Invariant** | `backend/app/services/audit_service.py` | Audit / Backend & UI | **Implemented & Tested** | Invariant: never reports 100% if skips exist; audit modal included. |
| **Docker Isolated Sandbox Worker** | `backend/app/worker/docker_worker.py` | Worker / Security | **Implemented & Tested** | Non-root `1000:1000`, `--network=none`, `--cap-drop=ALL`, tmpfs root. |
| **Simulated Fake Worker (Fallback)** | `backend/app/worker/fake_worker.py` | Worker / Dev | **Implemented & Tested** | Fast deterministic test execution for offline/CI environments. |
| **Test Discovery & Command Whitelist** | `backend/app/services/test_discovery.py` | Execution / Backend | **Implemented & Tested** | Precedence rules strictly enforced; command injection rejected. |
| **Credential Masking & Log Truncation** | `backend/app/worker/sanitizer.py` | Security / Worker | **Implemented & Tested** | Scrubs Gemini/OpenAI keys, GitHub/GitLab tokens, AWS keys, PEMs. |
| **Crash Recovery on Startup** | `backend/app/services/executor.py` | Reliability / Backend | **Implemented & Tested** | Sweeps dangling jobs on restart and marks as `SYSTEM_RESTARTED`. |
| **Duplicate Job Idempotency** | `backend/app/api/v1/jobs.py` | API / Reliability | **Implemented & Tested** | Returns existing active job rather than launching duplicate worker. |
| **Prompt Injection Boundary Fencing** | `backend/app/services/retriever.py` | LLM / Security | **Implemented & Tested** | `<untrusted_repo_content>` XML encapsulation with system defense. |
| **Pluggable LLM Provider (Gemini/Fake)** | `backend/app/services/llm/` | LLM / Backend | **Implemented & Tested** | Structured schema, timeout bounds, exponential backoff, fake mode. |
| **Multi-Layer Patch AST Validation** | `backend/app/services/patch_validator.py` | Patch / Security | **Implemented & Tested** | Path bounds, AST syntax verification before human review. |
| **Human-in-the-Loop Review** | `backend/app/services/diagnostic_service.py` | Review / Backend & UI | **Implemented & Tested** | Patches cannot be validated or merged without explicit user approval. |
| **Isolated Snapshot Workspace** | `backend/app/services/patch_applier.py` | Validation / Backend | **Implemented & Tested** | Canonical storage immutable; clones snapshot before patch. |
| **Central Evidence-Based Verdict Engine** | `backend/app/services/verdict_engine.py` | Validation / Backend | **Implemented & Tested** | `VALIDATED`, `UNVALIDATED`, `INFRASTRUCTURE_ERROR` + 9 reason codes. |
| **Bounded Validation Retries (Max 2)** | `backend/app/services/validation_service.py` | Validation / Backend | **Implemented & Tested** | Strictly bounded retry loops; human approval required per iteration. |
| **Segregated Audit Reporting** | `backend/app/models/validation.py` | Audit / Compliance | **Implemented & Tested** | Measured test metrics segregated from AI hypotheses; JSON export. |
| **Interactive Next.js Dashboard** | `frontend/src/` | Frontend / UI | **Implemented & Tested** | Tree view, logs, diff viewer, review modal, audit modal, report modal. |
| **Realistic Demo Repository** | `sample_repositories/demo_order_pricing` | Demo / Ingestion | **Implemented & Tested** | Deterministic discount bug with unit & regression test suites. |
| **Hypervisor MicroVM Isolation** | Infrastructure | Host Security | **Partial / Not Implemented** | Docker container sandbox implemented; Firecracker/gVisor documented for multi-tenant production. |
| **Multi-Language AST Parsing** | AST / Ingestion | Analysis | **Partial** | Full Python AST implemented; JavaScript/TypeScript identified as future phase. |

---

## Realistic Demonstration Repository

The repository includes a realistic Python demonstration project located in `sample_repositories/demo_order_pricing/` (with reference copies in `demo_order_pricing_buggy/` and `demo_order_pricing_fixed/`).

### Project Structure:
```
sample_repositories/demo_order_pricing/
├── src/
│   └── order_pricing/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── pricing.py         # Business logic: contains discount bug
│       └── services/
│           ├── __init__.py
│           └── tax_service.py     # Tax logic: 3 passing unit tests
├── tests/
│   ├── core/
│   │   └── test_pricing.py        # Target test reproducing failure & regression tests
│   └── services/
│       └── test_tax_service.py    # Regression test suite
├── pyproject.toml                 # Package metadata & pytest configuration
├── requirements.txt               # Pinned dependencies
├── pytest.ini                     # Pytest runner settings
└── README.md                      # Specification & expected pricing math
```

### Deterministic Bug Description:
In `src/order_pricing/core/pricing.py`, the function `calculate_discounted_price(price, discount_percent)` computes the discount amount but returns the discount amount itself instead of deducting it from the base price:
```python
# BUGGY (Original):
discount_amount = price * (discount_percent / 100.0)
return discount_amount  # Returns $20.00 instead of $80.00!

# FIXED (Corrected):
discount_amount = price * (discount_percent / 100.0)
return round(price - discount_amount, 2)  # Returns $80.00
```

### Reproducible Baseline Failure:
Running `pytest` produces 1 failing test and 5 passing tests:
```text
FAILED tests/core/test_pricing.py::test_calculate_discounted_price - assert 20.0 == 80.0
====== 1 failed, 5 passed in 0.12s ======
```

---

## Setup Instructions

### Prerequisites & Supported Platforms
- **Supported Operating Systems:** Linux (Ubuntu 20.04+), macOS (12+), Windows 10/11 (with PowerShell or WSL2).
- **Python:** Version 3.10 or 3.11.
- **Node.js:** Version 18.x or 20.x (with npm).
- **Docker (Optional):** Docker Desktop or Docker Engine (if running real isolated container sandboxes). If Docker is not installed or running, RepoPilot automatically falls back to its internal simulated worker.

---

### Step 1: Backend Installation & Setup

```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Initialize database schema (SQLite database is created automatically)
# To manually initialize or run migrations:
python -c "from app.database import init_db; init_db()"

# Run the complete automated test suite (Days 1–5: 49 tests)
python test_runner.py

# Start the FastAPI backend server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```
*Backend is accessible at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`. The reload watcher is deliberately restricted to `backend/app`; do not use broad `--reload` watching the whole backend directory, because uploaded repositories contain Python files under `backend/storage` and can trigger a restart while a job is running.*

---

### Step 2: Frontend Installation & Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Configure frontend environment variables
cp .env.example .env.local

# Run Next.js development server
npm run dev
```
*Frontend is accessible at `http://localhost:3000`.*

---

### Step 3: Docker Sandbox Container Setup (Optional)

If running with real Docker isolation:
```bash
# From the repository root, build the pinned execution sandbox image:
docker build -t repopilot-worker:python3.11 -f backend/docker/Dockerfile.worker backend/docker/

# Verify image is present:
docker images | grep repopilot-worker
```
Ensure your `backend/.env` has `WORKER_BACKEND=docker` (or `auto`).

---

## Generating Test Archives

To generate the demonstration archive and all 10 security test archives, run:
```bash
python generate_sample_archive.py
```
This generates the following archives in `sample_archives/`:
1. `demo_pricing.zip`: The realistic e-commerce pricing demo repository with deterministic failure.
2. `sample_repository.zip`: Valid nested Python repo with pytest & unittest suites.
3. `attack_path_traversal.zip`: Traversal attack (`../../evil.txt`) blocked by ingestion.
4. `attack_absolute_path.zip`: Absolute path attack (`/etc/...`) blocked by ingestion.
5. `attack_zip_bomb.zip`: Compression ratio bomb blocked by ingestion.
6. `repo_passing.zip`: 100% passing pytest suite.
7. `repo_failing.zip`: Deterministic assertion failure with captured traceback.
8. `repo_syntax_error.zip`: Syntax error during pytest test collection.
9. `repo_missing_deps.zip`: Unmet dependency manifest classified as `setup_error`.
10. `repo_timeout.zip`: Deliberate infinite sleep triggering 60s wall-clock timeout.
11. `repo_forbidden_resource.zip`: Outbound network access blocked under `--network=none`.

---

## Complete API Reference (REST API v1)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status and readiness check |
| `POST` | `/api/v1/repositories/upload` | Ingest repository ZIP, validate safety, run initial scan |
| `GET` | `/api/v1/repositories` | List all repositories with summary scan metrics |
| `GET` | `/api/v1/repositories/{id}` | Get repository details and scan history |
| `DELETE` | `/api/v1/repositories/{id}` | Delete repository metadata, snapshots, and files |
| `GET` | `/api/v1/repositories/{id}/tree` | Get hierarchical nested directory tree |
| `GET` | `/api/v1/repositories/{id}/files` | List repository files with filtering & search |
| `GET` | `/api/v1/repositories/{id}/files/{file_id}` | Get single file metadata & AST findings |
| `GET` | `/api/v1/repositories/{id}/analysis-audit` | Get comprehensive repository analysis coverage audit & skipped file details |
| `POST` | `/api/v1/jobs` | Start isolated baseline test execution job (idempotent for active jobs) |
| `GET` | `/api/v1/jobs/{id}` | Get job stage, exit code, test counts & tracebacks |
| `GET` | `/api/v1/jobs/{id}/logs` | Get bounded stdout, stderr, and preparation logs with masked secrets |
| `POST` | `/api/v1/jobs/{id}/cancel` | Safely cancel and terminate running container |
| `GET` | `/api/v1/repositories/{id}/jobs` | List all test execution jobs for a repository |
| `POST` | `/api/v1/jobs/{job_id}/diagnose` | Trigger AI diagnosis and safe patch proposal for a failed job |
| `GET` | `/api/v1/diagnostics/{id}` | Get diagnostic report details, diff, validation status, and evidence |
| `GET` | `/api/v1/jobs/{job_id}/diagnostics` | List all diagnostic reports generated for a job |
| `GET` | `/api/v1/repositories/{repo_id}/diagnostics` | List all diagnostic reports generated for a repository |
| `POST` | `/api/v1/diagnostics/{id}/approve` | Human review: approve proposed patch (requires valid status) |
| `POST` | `/api/v1/diagnostics/{id}/reject` | Human review: reject proposed patch with optional reason |
| `POST` | `/api/v1/diagnostics/{id}/validate` | Trigger isolated sandbox re-execution and verdict evaluation for approved patch |
| `GET` | `/api/v1/validations/{id}` | Get validation run details, target test status, regressions, and verdict |
| `GET` | `/api/v1/jobs/{job_id}/validations` | List all validation runs for an execution job |
| `GET` | `/api/v1/repositories/{repo_id}/validations` | List all validation runs for a repository |
| `GET` | `/api/v1/validations/{id}/report` | Get segregated final evidence-based audit report (measurement vs prediction) |

---

## Troubleshooting Guidance

1. **"Failed to connect to backend (Network Error)" in Frontend**:
   - Ensure backend is running at `http://127.0.0.1:8000`.
   - Verify `NEXT_PUBLIC_API_URL` in `frontend/.env.local` points to `http://127.0.0.1:8000`.
   - Check CORS settings in `backend/.env` (`CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`).

2. **Docker Worker Unavailable / "docker daemon not running"**:
   - RepoPilot is designed to run gracefully even without Docker. Set `WORKER_BACKEND=fake` (or keep `auto`) in `backend/.env`. The simulated worker executes deterministic tests without requiring Docker.
   - If using Docker, ensure Docker Desktop is started and the user has rights to run docker commands.

3. **Gemini API Rate Limits or Timeout**:
   - For repository-specific diagnosis of arbitrary uploaded projects, configure a valid `GEMINI_API_KEY` in `backend/.env` and set `LLM_PROVIDER=auto` (or `gemini`). Keep the key private and never commit it.
   - `LLM_PROVIDER=fake` is only a deterministic test/demo provider, not a general AI model. It may answer only for explicitly recognized bundled fixtures. For an unknown repository it now returns an insufficient-evidence result instead of inventing a math diagnosis or proposing a patch to a file that is not in the uploaded project.
   - After changing the provider configuration, restart the backend and generate a **new diagnosis**. Existing diagnostic reports are historical records and are not rewritten automatically.

4. **Stale Jobs After Server Restart**:
   - On backend startup, RepoPilot automatically sweeps dangling jobs in `pending`, `preparing`, or `running` state and updates them to `failed` with reason `SYSTEM_RESTARTED`. Check terminal startup logs for recovery messages.

---

## Workspace & Storage Cleanup Commands

To clean up all local databases, test artifacts, extracted repositories, and isolated snapshots:

```bash
# Windows (PowerShell):
Remove-Item -Recurse -Force backend\storage\* -ErrorAction SilentlyContinue
Remove-Item -Force backend\repopilot.db -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force backend\__pycache__ -ErrorAction SilentlyContinue

# Linux / macOS:
# rm -rf backend/storage/*
# rm -f backend/repopilot.db
# find backend -name "__pycache__" -exec rm -rf {} +
```

---

## Explicit Security Limitations & Deployment Boundaries

> [!WARNING]
> **Prototype Deployment Scope**:
> 1. **Local Prototype Binding:** RepoPilot AI binds exclusively to localhost (`127.0.0.1`) by default. It is designed as an internal engineering assistant and **must not be exposed unauthenticated to the public internet**.
> 2. **Arbitrary Code Sandbox Bounds:** Docker container isolation (`--network=none`, non-root, read-only root, dropped capabilities) provides defense-in-depth against accidental damage or script-level escape. However, standard containers share the host Linux/WSL kernel. For hostile, multi-tenant public cloud execution, hypervisor-level isolation (e.g., AWS Firecracker microVMs or Google gVisor) must be implemented.
> 3. **AI Verdict Caveat:** A `VALIDATED` verdict strictly certifies that the targeted failure was resolved and executed regression tests passed. It does not provide formal mathematical verification or guarantee the complete absence of latent bugs outside the test suite.

---

## 5-Minute Demonstration Script

For complete step-by-step instructions on presenting RepoPilot AI in 5 minutes, see [DEMO_SCRIPT.md](file:///c:/Users/HP/OneDrive/Documents/RepoPilot%20Hackathon%20Project/DEMO_SCRIPT.md).

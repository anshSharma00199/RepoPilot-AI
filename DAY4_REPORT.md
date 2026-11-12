# RepoPilot AI — Day 4 Implementation Report

**Date:** 2026-10-18  
**Scope:** Real Isolated Test Execution, Safe Snapshot Patching, Evidence-Based Central Verdict Engine, Bounded Retries & Segregated Audit Reporting  
**Status:** Complete & Validated  

---

## 1. Executive Summary

Day 4 completes the core mission of RepoPilot AI: connecting human-approved AI diagnostic patches to real, isolated sandbox re-execution and validating them through an authoritative, evidence-based Central Verdict Engine.

The full autonomous debugging lifecycle is now operational:
```
Repository Upload → Recursive Analysis → Isolated Baseline Test Execution → AST Context Retrieval → LLM Diagnosis → Multi-Layer Diff Validation → Human Review & Approval → Isolated Snapshot Patching → Fresh Sandboxed Execution → Central Verdict Engine → Bounded Retry Budget → Final Evidence Audit Report
```

Crucially, RepoPilot strictly enforces the **Reproduction Invariant**: no fix can be claimed as `VALIDATED` unless the baseline run produced an actual failure that the patch subsequently resolves in a fresh container without introducing regressions. Canonical repository storage remains completely immutable throughout the entire lifecycle.

---

## 2. Implemented Components & Architecture

### 2.1 Isolated Snapshot & Safe Patch Application (`backend/app/services/patch_applier.py`)
- **Canonical Storage Immutability:**
  - The original repository files in `storage/repositories/{repo_id}` are strictly read-only and never modified.
- **Dedicated Snapshot Cloning (`create_isolated_snapshot`):**
  - Creates a full filesystem copy at `storage/snapshots/{snapshot_id}` prior to patch application.
  - Automatically prunes non-essential transient directories (`__pycache__`, `.pytest_cache`, `.git`) during snapshot cloning.
- **Strict Path Containment & Traversal Defense:**
  - Evaluates every file path referenced in the unified diff against the snapshot root using `os.path.commonpath`.
  - Rejects directory traversal sequences (`../`), null bytes, Windows drive specifications, and absolute paths.
- **Eligible File Verification:**
  - Verifies that target files already exist in the inventoried repository snapshot before modifying them.
- **In-Memory Dry-Run & Safe Hunk Application:**
  - Applies diff hunks against snapshot file content lines with whitespace tolerance and context validation.
  - Rejects the patch and aborts before disk modification if any hunk fails to match context.
- **Deterministic Workspace Hashing (`compute_workspace_hash`):**
  - Traverses the entire snapshot in sorted lexicographical order and computes a cumulative SHA-256 hash across all relative file paths and file contents.
  - Provides tamper-evident cryptographic provenance for before/after workspace comparison.

### 2.2 Central Evidence-Based Verdict Engine (`backend/app/services/verdict_engine.py`)
- **Three Mutually Exclusive Top-Level Verdicts:**
  1. `VALIDATED`: The target failure was reproduced at baseline, the approved patch resolved the target test, all regression tests pass cleanly, and no stage encountered infrastructure errors.
  2. `UNVALIDATED`: The fix cannot be certified due to code/test issues (target still fails, regression introduced, baseline had 0 failures, timeout, or patch rejection).
  3. `INFRASTRUCTURE_ERROR`: The sandbox environment, Docker runner, or host worker failed to start or execute. Never misclassified as code success or code failure.
- **9 Granular Machine-Readable Reason Codes:**
  - `VERDICT_VALIDATED_FIX`: Patched target test passed cleanly and no regressions were detected.
  - `VERDICT_TARGET_STILL_FAILS`: Patched code still failed the specific target test that failed at baseline.
  - `VERDICT_REGRESSION_DETECTED`: The target test was fixed, but previously passing tests now fail or error out.
  - `VERDICT_NO_REPRODUCED_FAILURE`: Baseline execution had zero failures; a fix cannot be claimed without a reproduced bug.
  - `VERDICT_EXECUTION_TIMED_OUT`: Sandboxed test re-execution exceeded configured wall-clock timeout limit.
  - `VERDICT_PATCH_APPLICATION_FAILED`: Patch could not be applied cleanly to the isolated snapshot workspace.
  - `VERDICT_INSUFFICIENT_COVERAGE`: Project has no identifiable test suite or tests could not be executed.
  - `VERDICT_INFRASTRUCTURE_FAILURE`: Sandbox environment could not start or runner crashed.
  - `VERDICT_ATTEMPTS_EXHAUSTED`: Maximum retry attempts budget reached without successful validation.
- **Reproduction Invariant Rule:**
  - If `baseline.tests_failed == 0` and `baseline.tests_errors == 0`, the engine immediately evaluates to `UNVALIDATED` with `VERDICT_NO_REPRODUCED_FAILURE`.
- **Regression Detection Rule:**
  - If `baseline.tests_passed > 0` and `patched.tests_failed > 0` (or `patched.tests_passed < baseline.tests_passed`), the engine flags the specific regressions and evaluates to `UNVALIDATED` with `VERDICT_REGRESSION_DETECTED`.

### 2.3 Bounded Validation Orchestrator & Retries (`backend/app/services/validation_service.py`)
- **Human Review Guard:**
  - Verifies `diagnostic.review_status == "approved"` and `diagnostic.patch_validation_status == "valid"` before execution begins.
  - Unapproved or rejected patches are rejected with HTTP 400.
- **Bounded Retry Budget:**
  - Enforces `MAX_PATCH_ATTEMPTS = 2` per execution job.
  - Re-checks past validation runs for the parent job. If attempts meet or exceed the budget, returns `UNVALIDATED` with `VERDICT_ATTEMPTS_EXHAUSTED`.
  - Retries must never bypass human review or relax sandbox security bounds.
- **Fresh Sandbox Execution Lifecycle:**
  - Runs in a clean container/worker pointed directly to the snapshot directory.
  - Enforces identical baseline security boundaries (`--network=none`, non-root `1000:1000`, 60s timeout, read-only root with tmpfs).
  - Collects structured test counts, duration, exit code, stdout/stderr, and traceback details.

### 2.4 Segregated Evidence-Based Audit Reporting (`FinalEvidenceReport`)
- **Measurement vs. Prediction Segregation:**
  - Measured facts (baseline vs patched exit codes, durations, pass/fail counts, executed test names) are stored and displayed under dedicated `measured_baseline` and `measured_patched` structures.
  - AI predictions (root cause hypotheses, confidence scores, suggested risks) are segregated under `ai_diagnosis_hypotheses` with explicit warnings:
    > *"AI hypotheses are model-generated predictions and must not be conflated with empirical test execution measurements."*
- **Full Cryptographic Lineage:**
  - Preserves immutable links to:
    - Original repository hash
    - Baseline job ID and exit code
    - Diagnostic report ID and SHA-256 patch hash
    - Snapshot ID and patched workspace SHA-256 hash
    - Reviewer approval notes and timestamps
- **Honest Limitations Caveat:**
  - Reports explicitly note:
    > *"A VALIDATED verdict confirms that the specific target test and executed regression tests passed under isolated conditions. It does not certify the complete absence of latent bugs outside the executed test suite."*

### 2.5 Data Model & Database Persistence (`backend/app/models/validation_run.py`)
- Added `ValidationRun` SQLAlchemy model with columns:
  - `id` (UUID Primary Key)
  - `diagnostic_report_id` (Foreign Key)
  - `execution_job_id` (Foreign Key)
  - `repository_id` (Foreign Key)
  - `status` (`queued`, `applying_patch`, `executing_tests`, `completed`, `failed`)
  - `verdict` (`VALIDATED`, `UNVALIDATED`, `INFRASTRUCTURE_ERROR`)
  - `reason_code` (one of the 9 standardized codes)
  - `reason_description` (human-readable explanation)
  - `target_test_passed` (Boolean)
  - `regressions_detected` (Boolean)
  - `regressions_list` (JSON array of regressed test names)
  - `executed_tests_list` (JSON array of all executed test names)
  - `baseline_tests_failed`, `baseline_tests_passed`, `patched_tests_failed`, `patched_tests_passed`
  - `patch_attempt_number`, `max_attempts_budget`
  - `workspace_snapshot_id`, `workspace_snapshot_hash`
  - `final_evidence_report` (Complete JSON audit payload)
  - Timestamps: `created_at`, `completed_at`

### 2.6 REST API v1 (`backend/app/api/v1/validations.py`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/diagnostics/{id}/validate` | Triggers snapshot creation, patch application, fresh sandbox execution, and verdict evaluation |
| `GET` | `/api/v1/validations/{id}` | Retrieves validation run status, metrics, target test resolution, and verdict |
| `GET` | `/api/v1/jobs/{job_id}/validations` | Lists all validation runs associated with an execution job |
| `GET` | `/api/v1/repositories/{repo_id}/validations` | Lists all validation runs associated with a repository |
| `GET` | `/api/v1/validations/{id}/report` | Retrieves the complete, segregated Final Evidence Report audit document |

### 2.7 Frontend Developer Dashboard Integration
- **`DiagnosticReviewModal.tsx`:**
  - Added "Run Validation in Sandbox" primary action upon patch approval.
  - Seamlessly triggers validation and updates the parent execution view.
- **`ExecutionPanel.tsx`:**
  - Added Validation Runs history feed and status tracker.
  - Prominent Central Verdict Banner featuring color-coded badges (`VALIDATED` in emerald green, `UNVALIDATED` in amber/red, `INFRASTRUCTURE_ERROR` in purple).
  - Displays target test resolution checkmark, regression alerts, and attempt counters.
  - One-click button to launch the comprehensive Final Evidence Report modal.
- **`FinalReportModal.tsx`:**
  - Full-featured modal displaying:
    - Side-by-side Before vs. After metrics comparison table.
    - Target test status badge and regression list.
    - Audit Trail lineage cards (Repo Hash, Patch Hash, Workspace Hash, Duration).
    - Unified diff viewer highlighting the approved changes.
    - Clear distinction between empirical measurements and AI hypotheses.
    - One-click JSON export button downloading the formal audit report.

---

## 3. Automated Test Scenarios & Coverage (Scenarios A through J)

RepoPilot AI incorporates a comprehensive automated test suite (`backend/tests/test_validation_engine.py`) covering all 10 required Day 4 scenarios:

| Scenario | Test Name | Simulated Condition | Expected Verdict | Reason Code |
|---|---|---|---|---|
| **Scenario A** | Clean Fix Validated | Target failure resolved, regression suite green | `VALIDATED` | `VERDICT_VALIDATED_FIX` |
| **Scenario B** | Fix Fails Target | Patched code still fails target assertion | `UNVALIDATED` | `VERDICT_TARGET_STILL_FAILS` |
| **Scenario C** | Regression Introduced | Target fixed, but previously passing test fails | `UNVALIDATED` | `VERDICT_REGRESSION_DETECTED` |
| **Scenario D** | Baseline Passing Invariant | Baseline had 0 failures; fix cannot be claimed | `UNVALIDATED` | `VERDICT_NO_REPRODUCED_FAILURE` |
| **Scenario E** | Insufficient Coverage | Zero tests discovered / no test suite | `UNVALIDATED` | `VERDICT_INSUFFICIENT_COVERAGE` |
| **Scenario F** | Patch Application Rejection | Malformed diff / invalid file path | `UNVALIDATED` | `VERDICT_PATCH_APPLICATION_FAILED` |
| **Scenario G** | Execution Wall Timeout | Sandboxed runner times out after 60s | `UNVALIDATED` | `VERDICT_EXECUTION_TIMED_OUT` |
| **Scenario H** | Infrastructure Error | Container / worker daemon failure | `INFRASTRUCTURE_ERROR` | `VERDICT_INFRASTRUCTURE_FAILURE` |
| **Scenario I** | Retry Budget Exhausted | Attempts exceed `MAX_PATCH_ATTEMPTS = 2` | `UNVALIDATED` | `VERDICT_ATTEMPTS_EXHAUSTED` |
| **Scenario J** | Human Review Guard | Unapproved patch rejected from validation | HTTP 400 | `PATCH_NOT_APPROVED` |
| **E2E Flow** | End-to-End API Pipeline | Upload → Baseline Run → Diagnose → Approve → Validate → Final Report | `VALIDATED` | `VERDICT_VALIDATED_FIX` |

### Complete Test Suite Summary
The test runner (`backend/test_runner.py`) now covers **44 automated tests** across all 4 days:
- **Day 1 (16 tests):** Archive security, bombs, traversals, AST analysis, manifest parsing, API.
- **Day 2 (8 tests):** Command whitelisting, runner sandbox, output parsing, secret masking, timeouts.
- **Day 3 (9 tests):** LLM provider abstraction, structured JSON schema, prompt injection defense, patch validation, review flow.
- **Day 4 (11 tests):** Isolated snapshots, Scenarios A through J, central verdict engine, and E2E validation pipeline.

---

## 4. Security Architecture & Invariants Enforced

1. **Reproduction Invariant:**
   A fix cannot be declared `VALIDATED` without a verified baseline failure. If tests passed initially, RepoPilot issues `VERDICT_NO_REPRODUCED_FAILURE`.
2. **Canonical Repository Immutability:**
   Original repository uploads in `storage/repositories/{repo_id}` are strictly read-only. All diffs are applied strictly to ephemeral, isolated snapshots in `storage/snapshots/{snapshot_id}`.
3. **No Direct Code Execution in API Process:**
   Neither the baseline test run nor the patched validation run executes Python code inside the FastAPI application process. Execution is confined to isolated Docker sandboxes or isolated mock worker processes.
4. **Human Review Gate:**
   AI-generated patches can never be validated without explicit human review (`review_status == "approved"`). Any attempt to validate an unapproved or rejected patch is blocked with HTTP 400.
5. **Bounded Retry Budget:**
   Autonomous retries are strictly capped at 2 attempts (`MAX_PATCH_ATTEMPTS = 2`). The system will never loop indefinitely or burn API quota without operator intervention.
6. **Network & Sandbox Isolation:**
   Validation runs adhere to the exact same sandboxing constraints as baseline runs: `--network=none`, non-root user (`1000:1000`), read-only root mounts, dropped Linux capabilities, and wall-clock execution limits.
7. **Empirical Evidence Segregation:**
   Measured test metrics (exit codes, runtimes, test counts) are strictly separated from AI hypotheses in both the API schema and the UI, preventing confusion between empirical measurements and LLM predictions.

# RepoPilot AI — 5-Minute Demonstration Script

This document provides a repeatable, 5-minute step-by-step live demonstration script for RepoPilot AI. It demonstrates the complete end-to-end lifecycle using the realistic Python sample project `demo_order_pricing`.

---

## Prerequisites for Live Demonstration

1. **Backend Running:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Frontend Running:**
   ```bash
   cd frontend
   npm run dev
   ```
3. **Target Archive:**
   `sample_archives/demo_pricing.zip` (generated via `python generate_sample_archive.py` or packaged from `sample_repositories/demo_order_pricing`).
4. **Browser:**
   Navigate to `http://localhost:3000`.

---

## Demonstration Sequence (Total Duration: ~5 Minutes)

### Phase 1: Ingestion & Analysis Audit (0:00 – 1:00)
1. **Navigate to Dashboard (`http://localhost:3000`):**
   - Click **"Upload Repository"**.
   - Select or drag-and-drop `sample_archives/demo_pricing.zip`.
   - Click **"Upload and Scan"**.
2. **Highlight Security & Traversal Controls:**
   - Mention that the ZIP is strictly validated before extraction against path traversal (`../`), null bytes, Windows/UNC absolute paths, and zip-bomb decompression limits (max 50:1 ratio).
   - Point out that untrusted code is never unpacked into the API server process space.
3. **Review Repository Detail & File Explorer:**
   - Click on the newly ingested `demo_order_pricing` repository card.
   - Point to the nested directory tree:
     - `src/order_pricing/core/pricing.py` (business logic)
     - `src/order_pricing/services/tax_service.py` (tax calculations)
     - `tests/core/test_pricing.py` (unit tests including target failure)
     - `tests/services/test_tax_service.py` (regression & unrelated passing tests)
   - Click on `pricing.py` in the File Explorer. View non-executing AST symbols (`calculate_discounted_price`, `calculate_bulk_total`).
4. **Open Analysis Audit Modal:**
   - Click the **"Analysis Audit"** button in the header.
   - Show the coverage summary:
     - Total discovered files & directories.
     - Files inventoried vs content-analyzed.
     - AST parse successes (2/2) and parse errors (0).
     - Test files (2) and configuration files (2: `pyproject.toml`, `requirements.txt`).
     - **Audit Invariant:** Point out that coverage does not falsely report 100% if any files were skipped or excluded by policy.

---

### Phase 2: Baseline Execution & Real Failure Exposure (1:00 – 2:00)
1. **Start Baseline Execution:**
   - In the Execution Panel on the right, observe the detected test runner (`pytest`).
   - Click **"Run Baseline Tests"**.
2. **Explain Sandbox Isolation:**
   - Mention that execution runs in an isolated container/worker with:
     - Dropped capabilities (`--cap-drop=ALL`).
     - Read-only root filesystem with isolated tmpfs.
     - Complete network isolation (`--network=none`).
     - Resource caps: 1 CPU, 512MB RAM, 100 PIDs, 60s timeout.
3. **Inspect Real Baseline Failure:**
   - When the test run finishes, observe the execution metrics:
     - **Total:** 6 tests
     - **Passed:** 5 tests
     - **Failed:** 1 test (`tests/core/test_pricing.py::test_calculate_discounted_price`)
   - Expand the failure card:
     - Point out the exact assertion failure:
       ```text
       >       assert calculate_discounted_price(100.0, 20.0) == 80.0
       E       assert 20.0 == 80.0
       ```
     - Explain the bug: the function returned the discount amount (`$20.00`) instead of subtracting it from the base price (`$80.00`).
   - Show the Execution Logs tab: demonstrate that credential masking and head/tail log truncation were applied to raw worker output.

---

### Phase 3: AI Diagnosis & Source Evidence Review (2:00 – 3:00)
1. **Trigger AI Diagnosis:**
   - Click **"Diagnose & Propose Patch"**.
   - Note the guard: the system strictly requires reproducible failure evidence; baseline passes cannot trigger hallucinated patches.
2. **Review Diagnostic Modal:**
   - When diagnosis completes, the Diagnostic Review Modal opens.
   - **Hypothesis:** Shows the model explanation: "In `calculate_discounted_price`, `discount_amount` is computed but returned directly rather than subtracted from `price`."
   - **Retrieved Evidence:** Show the exact file references, line numbers (lines 14–26 in `pricing.py`), and AST context passed to the model within `<untrusted_repo_content>` safety boundaries.
   - **Unified Diff Review:**
     - Inspect the color-coded unified diff:
       ```diff
       --- a/src/order_pricing/core/pricing.py
       +++ b/src/order_pricing/core/pricing.py
       @@ -24,3 +24,3 @@
            discount_amount = price * (discount_percent / 100.0)
       -    return discount_amount
       +    return round(price - discount_amount, 2)
       ```
   - **Pre-Approval Patch Validation:**
     - Point out that the patch has already passed dry-run AST validation: no syntax errors, no unauthorized file modifications, bounded diff size.
     - Review status is currently `proposed`. Emphasize human-in-the-loop: code cannot be tested or merged without human sign-off.

---

### Phase 4: Human Review & Isolated Re-Execution (3:00 – 4:00)
1. **Approve Patch:**
   - Enter optional reviewer notes (e.g., "Verified math logic matches pricing spec").
   - Click **"Approve Patch"**. Review status updates to `approved`.
2. **Trigger Sandboxed Re-Validation:**
   - Click **"Validate Patch"**.
3. **Explain Validation Sandbox Workflow:**
   - The backend clones an isolated snapshot of the repository in `storage/snapshots/{snapshot_id}` (canonical original repository files are completely immutable).
   - Applies the approved diff in the isolated snapshot.
   - Launches a fresh worker container under `--network=none` with the patched snapshot.
   - Executes the targeted test (`test_calculate_discounted_price`), followed by the regression suite (`tests/services/test_tax_service.py` and zero-discount edge cases).

---

### Phase 5: Final Evidence Report & Limitations (4:00 – 5:00)
1. **Open Final Evidence Report Modal:**
   - Click **"View Final Evidence Report"**.
2. **Explain the Central Verdict:**
   - **Verdict Badge:** `VALIDATED` (Green) with reason code `VERDICT_VALIDATED_FIX`.
   - **Target Test Resolution:** `RESOLVED` (target test `test_calculate_discounted_price` transitioned from FAILING to PASSING).
   - **Regression Suite:** `0 regressions` (all 5 previously passing tests continue to pass).
   - **Before vs After Metrics Comparison:**
     - Baseline: 5 Passed, 1 Failed.
     - Patched: 6 Passed, 0 Failed.
   - **Lineage Audit:** Displays original SHA-256 hash, patched snapshot hash, baseline job ID, and patch hash for regulatory traceability.
   - **Measurement vs Prediction Segregation:** Point out that measured test metrics are separated with an explicit caveat that model predictions are not guaranteed bug-free beyond test coverage.
   - Click **"Export JSON Report"** to show machine-readable audit report payload.
3. **Briefly Showcase Error Handling (Scenarios B, D, E):**
   - Mention that if a patch fails the target test, the verdict is strictly `UNVALIDATED` (`VERDICT_TARGET_STILL_FAILS`).
   - If tests pass cleanly at baseline, reproduction invariant prevents false validated-fix claims (`VERDICT_NO_REPRODUCED_FAILURE`).
   - If Docker or worker cannot start, it is strictly classified as `INFRASTRUCTURE_ERROR`, never misattributed to user code.
4. **Disclose Limitations & Wrap-Up:**
   - Mention environment bounds: prototype uses localhost binding (`127.0.0.1`); multi-tenant production requires hypervisor microVMs (Firecracker/gVisor).
   - Complete 5-minute demonstration concluded.

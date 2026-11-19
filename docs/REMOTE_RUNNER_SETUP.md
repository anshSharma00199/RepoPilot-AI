# GitHub Actions remote execution runner

RepoPilot can run baseline and patch-validation jobs on an ephemeral GitHub-hosted
runner instead of requiring Docker on the Render web service.

## Required configuration

1. Push `.github/workflows/repopilot-runner.yml`, `.github/scripts/`, and the backend
   changes to the `main` branch of `anshSharma00199/RepoPilot-AI`.
2. Create a fine-grained GitHub token restricted to that repository with **Actions:
   Read and write** permission. Store it only in Render as `GITHUB_ACTIONS_TOKEN`.
3. Add these Render environment variables:

   - `WORKER_BACKEND=github_actions`
   - `GITHUB_ACTIONS_TOKEN=<fine-grained token>`
   - `GITHUB_ACTIONS_REPOSITORY=anshSharma00199/RepoPilot-AI`
   - `GITHUB_ACTIONS_REF=main`
   - `RUNNER_CALLBACK_SECRET=<long random secret>`
   - `PUBLIC_API_BASE_URL=https://repopilot-ai-6vjg.onrender.com`
   - `GITHUB_RUNNER_WAIT_SECONDS=360`

4. In GitHub repository **Settings → Secrets and variables → Actions**, create
   `RUNNER_CALLBACK_SECRET` with exactly the same random value as Render.
5. Redeploy Render after adding the variables. The workflow must exist on the
   selected ref before dispatch will work.

Generate a callback secret locally in PowerShell with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Do not paste the secret into chat, source control, workflow inputs, or logs.

## Current demo limits

- This implementation transports the compressed workspace in `workflow_dispatch`
  inputs. It intentionally rejects archives larger than 30 KiB compressed because
  GitHub limits the total workflow-dispatch input payload. Larger repositories need
  private object storage (for example, an R2/S3 bucket with short-lived signed URLs).
- The runner currently supports the project's Python 3.11 image and the discovered
  argv-based test/setup commands. It does not execute arbitrary shell strings.
- Test execution runs in Docker with no network, non-root UID, dropped capabilities,
  no-new-privileges, read-only container root, CPU/memory/PID/time limits. Dependency
  preparation has network access but is also non-root and receives no app/GitHub secrets.
- The callback runs in a separate fresh GitHub job. The execution job has no callback
  secret and no write-capable GitHub token.
- GitHub-hosted runner minutes and repository limits still apply.

Docker is a useful isolation layer, not a formally hardened multi-tenant sandbox.
Do not expose this as an unrestricted public code-execution service. For hostile
public workloads, use stronger isolation (for example, dedicated microVM sandboxes),
per-user quotas, abuse controls, and private object storage.

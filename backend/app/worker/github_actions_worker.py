"""Remote execution worker backed by an ephemeral GitHub-hosted Actions runner.

Only small demo archives are transported through workflow_dispatch inputs. The
uploaded repository is executed inside a constrained Docker container on the
hosted runner; no application or GitHub credentials enter that container.
"""
import asyncio
import base64
import json
import shutil
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Tuple

from app.config import settings
from app.database import SessionLocal
from app.models.execution_job import ExecutionJob
from app.worker.interface import ExecutionConfig, ExecutionResult, ExecutionWorker


class GitHubActionsWorker(ExecutionWorker):
    MAX_ARCHIVE_BYTES = 30 * 1024  # workflow_dispatch has a 65,535-character input budget

    def is_available(self) -> Tuple[bool, str]:
        missing = [name for name, value in (
            ("GITHUB_ACTIONS_TOKEN", settings.GITHUB_ACTIONS_TOKEN),
            ("GITHUB_ACTIONS_REPOSITORY", settings.GITHUB_ACTIONS_REPOSITORY),
            ("RUNNER_CALLBACK_SECRET", settings.RUNNER_CALLBACK_SECRET),
            ("PUBLIC_API_BASE_URL", settings.PUBLIC_API_BASE_URL),
        ) if not value]
        if missing:
            return False, "Missing Render environment variables: " + ", ".join(missing)
        return True, "GitHub Actions runner configuration is present."

    async def cancel(self, job_id: str) -> bool:
        # Cancellation is deliberately not advertised until workflow-run IDs are
        # persisted and the Actions cancel API is wired end-to-end.
        return False

    async def execute(self, config: ExecutionConfig) -> ExecutionResult:
        available, reason = self.is_available()
        if not available:
            return self._infra(config.job_id, reason)

        archive_path = settings.workspaces_path / f"{config.job_id}.runner.zip"
        try:
            size = await asyncio.to_thread(self._make_archive, config.workspace_dir, archive_path)
            if size > self.MAX_ARCHIVE_BYTES:
                return self._infra(
                    config.job_id,
                    f"Repository archive is {size} bytes; GitHub demo runner currently accepts at most {self.MAX_ARCHIVE_BYTES} compressed bytes. Use a smaller ZIP or configure object storage for larger repositories.",
                )
            archive_b64 = base64.b64encode(archive_path.read_bytes()).decode("ascii")
            owner_repo = settings.GITHUB_ACTIONS_REPOSITORY.strip()
            dispatch = {
                "ref": settings.GITHUB_ACTIONS_REF,
                "inputs": {
                    "job_id": config.job_id,
                    "archive_b64": archive_b64,
                    "command_json": json.dumps(config.command),
                    "setup_json": json.dumps(config.setup_command or []),
                    "timeout_seconds": str(min(max(config.timeout_seconds, 5), 300)),
                    "image": "python:3.11-slim",
                    "api_base_url": settings.PUBLIC_API_BASE_URL.rstrip("/"),
                },
            }
            url = f"https://api.github.com/repos/{owner_repo}/actions/workflows/repopilot-runner.yml/dispatches"
            request = urllib.request.Request(
                url,
                data=json.dumps(dispatch).encode(),
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {settings.GITHUB_ACTIONS_TOKEN}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Content-Type": "application/json",
                    "User-Agent": "RepoPilot-AI",
                },
                method="POST",
            )
            await asyncio.to_thread(self._send, request)

            # The runner callback updates this job row. Polling the database keeps
            # the existing executor/validation orchestration contract intact.
            deadline = time.monotonic() + settings.GITHUB_RUNNER_WAIT_SECONDS
            while time.monotonic() < deadline:
                await asyncio.sleep(3)
                db = SessionLocal()
                try:
                    job = db.query(ExecutionJob).filter(ExecutionJob.id == config.job_id).first()
                    if job and job.status in ("completed", "failed", "timed_out", "cancelled"):
                        return ExecutionResult(
                            job_id=config.job_id,
                            status=job.status,
                            exit_code=job.exit_code,
                            duration_seconds=job.duration_seconds or 0.0,
                            stdout=job.stdout or "",
                            stderr=job.stderr or "",
                            setup_logs=job.setup_logs or "",
                            timed_out=bool(job.timed_out),
                            error_type=job.error_type,
                            error_message=job.error_message,
                            tests_total=job.tests_total or 0,
                            tests_passed=job.tests_passed or 0,
                            tests_failed=job.tests_failed or 0,
                            tests_skipped=job.tests_skipped or 0,
                            tests_errors=job.tests_errors or 0,
                            failures=job.failures or [],
                        )
                finally:
                    db.close()
            return self._infra(config.job_id, "GitHub Actions runner did not report a result before the configured wait timeout.")
        except Exception as exc:
            return self._infra(config.job_id, f"GitHub Actions dispatch/execution failed: {exc}")
        finally:
            archive_path.unlink(missing_ok=True)

    @staticmethod
    def _make_archive(source: Path, destination: Path) -> int:
        source = source.resolve()
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in source.rglob("*"):
                if any(part in {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".repopilot-home"} for part in path.parts):
                    continue
                if path.is_symlink():
                    raise ValueError(f"Symlinks are not allowed in runner workspaces: {path}")
                if path.is_file():
                    zf.write(path, path.relative_to(source).as_posix())
        return destination.stat().st_size

    @staticmethod
    def _send(request: urllib.request.Request) -> bytes:
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", "replace")
            raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail}") from exc

    @staticmethod
    def _infra(job_id: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            job_id=job_id, status="failed", exit_code=None, duration_seconds=0.0,
            stdout="", stderr="", error_type="infrastructure_error", error_message=message,
        )

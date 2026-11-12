import asyncio
import os
import shutil
import time
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

from app.config import settings
from app.worker.interface import ExecutionWorker, ExecutionConfig, ExecutionResult
from app.worker.parser import parse_pytest_output
from app.worker.sanitizer import sanitize_log_content, bound_log_size


class DockerWorker(ExecutionWorker):
    """
    Production-grade containerized execution worker.
    Enforces non-root execution, dropped Linux capabilities, CPU/memory limits,
    network disabling (--network none) during tests, and guaranteed container cleanup.
    """

    def is_available(self) -> Tuple[bool, str]:
        """Checks if Docker daemon is running and accessible via CLI."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            if res.returncode == 0:
                return True, "Docker daemon is healthy and accessible."
            return False, f"Docker command returned error code {res.returncode}: {res.stderr.decode('utf-8', errors='ignore')}"
        except FileNotFoundError:
            return False, "Docker CLI executable not found in system PATH."
        except subprocess.TimeoutExpired:
            return False, "Docker daemon response timed out (daemon may be unresponsive)."
        except Exception as e:
            return False, f"Docker availability check failed: {str(e)}"


    async def cancel(self, job_id: str) -> bool:
        """Kills and cleans up the running Docker container."""
        container_name = f"repopilot-job-{job_id}"

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["docker", "rm", "-f", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False


    async def execute(self, config: ExecutionConfig) -> ExecutionResult:
        container_name = f"repopilot-job-{config.job_id}"
        workspace_dir = config.workspace_dir.resolve()
        start_time = time.time()
        setup_logs = ""

        # Step 1: Verify Docker availability
        available, reason = self.is_available()
        if not available:
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=None,
                duration_seconds=0.0,
                stdout="",
                stderr="",
                setup_logs="",
                error_type="infrastructure_error",
                error_message=f"Docker container sandbox unavailable: {reason}",
            )

        try:
            # Step 2: Controlled Preparation Stage (Dependency Installation)
            if config.setup_command:
                setup_success, setup_logs, setup_err = await self._run_preparation_stage(
                    container_name=f"{container_name}-prep",
                    workspace_dir=workspace_dir,
                    setup_cmd=config.setup_command,
                    timeout=config.setup_timeout_seconds,
                    image=config.base_image,
                )
                if not setup_success:
                    duration = time.time() - start_time
                    clean_setup_logs, truncated = bound_log_size(sanitize_log_content(setup_logs))
                    return ExecutionResult(
                        job_id=config.job_id,
                        status="failed",
                        exit_code=1,
                        duration_seconds=duration,
                        stdout="",
                        stderr=setup_err,
                        setup_logs=clean_setup_logs,
                        stdout_truncated=False,
                        stderr_truncated=truncated,
                        error_type="setup_error",
                        error_message="Environment setup failed: dependencies could not be installed from manifest.",
                    )

            # Step 3: Isolated Test Execution Stage
            # Strictly sandboxed: non-root, dropped capabilities, no network, resource limits
            docker_cmd = [
                "docker", "run",
                "--name", container_name,
                "--rm",
                "--network=none",                             # Zero network access during test run
                "--cpus", str(config.cpu_limit),               # CPU limit
                "--memory", config.memory_limit,               # Memory limit (e.g. 512m)
                "--pids-limit", str(config.pids_limit),         # PID limit against fork bombs
                "--cap-drop=ALL",                              # Drop all Linux capabilities
                "--security-opt=no-new-privileges",            # Block privilege escalation
                "--user", "1000:1000",                         # Non-root execution
                "--workdir", "/workspace",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",   # Volatile isolated tmpfs
                "-v", f"{workspace_dir}:/workspace:rw",        # Workspace mount
                "-e", "PYTHONPATH=/workspace/.repopilot-deps",
                config.base_image,
            ] + config.command

            # Run container with wall-clock timeout enforcement
            timed_out = False
            raw_stdout = ""
            raw_stderr = ""
            exit_code: Optional[int] = None


            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=config.timeout_seconds,
                    check=False,
                )

                exit_code = result.returncode
                raw_stdout = result.stdout.decode("utf-8", errors="replace")
                raw_stderr = result.stderr.decode("utf-8", errors="replace")

            except subprocess.TimeoutExpired as e:
                timed_out = True
                await self.cancel(config.job_id)

                stdout = e.stdout or b""
                stderr = e.stderr or b""

                if isinstance(stdout, bytes):
                    raw_stdout = stdout.decode("utf-8", errors="replace")
                else:
                    raw_stdout = str(stdout)

                if isinstance(stderr, bytes):
                    raw_stderr = stderr.decode("utf-8", errors="replace")
                else:
                    raw_stderr = str(stderr)

                raw_stderr += (
                    f"\n[RepoPilot Error] Test execution exceeded "
                    f"{config.timeout_seconds} seconds."
                )
                exit_code = 124


            duration = round(time.time() - start_time, 2)

            # Step 4: Sanitize & Bound Logs
            clean_stdout, stdout_trunc = bound_log_size(sanitize_log_content(raw_stdout))
            clean_stderr, stderr_trunc = bound_log_size(sanitize_log_content(raw_stderr))
            clean_setup, _ = bound_log_size(sanitize_log_content(setup_logs))

            # Step 5: Parse Structured Test Output
            parsed = parse_pytest_output(clean_stdout, clean_stderr, exit_code)

            status = "completed" if exit_code == 0 else "failed"
            error_type = parsed["error_type"]
            if timed_out:
                status = "timed_out"
                error_type = "timeout_error"

            return ExecutionResult(
                job_id=config.job_id,
                status=status,
                exit_code=exit_code,
                duration_seconds=duration,
                stdout=clean_stdout,
                stderr=clean_stderr,
                setup_logs=clean_setup,
                stdout_truncated=stdout_trunc,
                stderr_truncated=stderr_trunc,
                timed_out=timed_out,
                error_type=error_type,
                error_message="Test suite executed with failures." if error_type == "test_failure" else (
                    "Execution timed out." if timed_out else None
                ),
                tests_total=parsed["tests_total"],
                tests_passed=parsed["tests_passed"],
                tests_failed=parsed["tests_failed"],
                tests_skipped=parsed["tests_skipped"],
                tests_errors=parsed["tests_errors"],
                failures=parsed["failures"],
            )

        except Exception as e:
            await self.cancel(config.job_id)
            duration = round(time.time() - start_time, 2)
            return ExecutionResult(
                job_id=config.job_id,
                status="failed",
                exit_code=None,
                duration_seconds=duration,
                stdout="",
                stderr=str(e),
                setup_logs=setup_logs,
                error_type="infrastructure_error",
                error_message=f"Sandbox execution crashed: {str(e)}",
            )
        finally:
            # Guaranteed container cleanup
            await self.cancel(config.job_id)


    async def _run_preparation_stage(
        self,
        container_name: str,
        workspace_dir: Path,
        setup_cmd: List[str],
        timeout: int,
        image: str,
    ) -> Tuple[bool, str, str]:
        """Install repository dependencies without relying on async subprocess support."""
        prep_cmd = [
            "docker", "run",
            "--name", container_name,
            "--rm",
            "--cpus", "1.0",
            "--memory", "1024m",
            "--workdir", "/workspace",
            "-v", f"{workspace_dir}:/workspace:rw",
            image,
        ] + setup_cmd

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                prep_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )

            stdout_text = result.stdout.decode("utf-8", errors="replace")
            stderr_text = result.stderr.decode("utf-8", errors="replace")

            return result.returncode == 0, stdout_text, stderr_text

        except subprocess.TimeoutExpired as e:
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "rm", "-f", container_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
            except Exception:
                pass

            stdout = e.stdout or b""
            stderr = e.stderr or b""

            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            return (
                False,
                stdout,
                f"{stderr}\nDependency installation timed out after {timeout} seconds.",
            )

        except Exception as e:
            return (
                False,
                "",
                f"Preparation stage failed: {type(e).__name__}: {e!r}",
            )

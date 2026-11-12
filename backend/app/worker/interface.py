from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class ExecutionConfig:
    job_id: str
    repository_id: str
    workspace_dir: Path
    command: List[str]
    setup_command: Optional[List[str]] = None
    timeout_seconds: int = 60
    setup_timeout_seconds: int = 120
    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    pids_limit: int = 100
    base_image: str = "python:3.11-slim"
    network_enabled_for_tests: bool = False
    network_enabled_for_setup: bool = True


@dataclass
class ExecutionResult:
    job_id: str
    status: str  # completed, failed, timed_out, cancelled
    exit_code: Optional[int]
    duration_seconds: float
    stdout: str
    stderr: str
    setup_logs: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False
    error_type: Optional[str] = None  # test_failure, setup_error, syntax_error, timeout_error, infrastructure_error
    error_message: Optional[str] = None
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_errors: int = 0
    failures: List[Dict[str, Any]] = field(default_factory=list)


class ExecutionWorker(ABC):
    @abstractmethod
    async def execute(self, config: ExecutionConfig) -> ExecutionResult:
        """Executes test job in an isolated sandbox and returns structured results."""
        pass

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        """Safely terminates and cleans up running job container."""
        pass

    @abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        """Checks if the worker backend is healthy and available for execution."""
        pass

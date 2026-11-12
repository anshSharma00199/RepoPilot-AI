from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TestFailureDetail(BaseModel):
    test_name: str
    file: Optional[str] = None
    line: Optional[int] = None
    traceback: str


class JobCreateRequest(BaseModel):
    repository_id: str
    command: Optional[List[str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=5, le=300)


class ExecutionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    status: str
    stage: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    error_type: Optional[str] = None
    error_message: Optional[str] = None

    command: List[str] = []
    image_version: str
    exit_code: Optional[int] = None
    timed_out: bool = False

    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_errors: int = 0

    failures: List[TestFailureDetail] = []

    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    timeout_seconds: int = 60


class ExecutionJobLogsResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    stdout: str = ""
    stderr: str = ""
    setup_logs: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class ExecutionJobListResponse(BaseModel):
    total: int
    items: List[ExecutionJobResponse]

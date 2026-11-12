from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ValidationRunRequest(BaseModel):
    custom_command: Optional[List[str]] = None


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    baseline_job_id: str
    diagnostic_report_id: str
    patched_job_id: Optional[str] = None

    created_at: datetime
    completed_at: Optional[datetime] = None

    patch_version: int = 1
    patch_hash: str
    workspace_hash: str
    affected_files: List[str] = []

    verdict: str  # VALIDATED, UNVALIDATED, INFRASTRUCTURE_ERROR
    verdict_reason_code: str
    verdict_explanation: str

    target_test_name: Optional[str] = None
    target_test_passed: bool = False
    regression_tests_passed: bool = False

    baseline_tests_total: int = 0
    baseline_tests_passed: int = 0
    baseline_tests_failed: int = 0

    patched_tests_total: int = 0
    patched_tests_passed: int = 0
    patched_tests_failed: int = 0
    patched_tests_errors: int = 0
    patched_tests_skipped: int = 0
    duration_seconds: float = 0.0

    tests_executed_before: List[str] = []
    tests_executed_after: List[str] = []
    target_tests_resolved: List[str] = []
    new_regressions: List[str] = []

    attempt_number: int = 1
    max_attempts: int = 2
    is_retry_budget_exhausted: bool = False


class ValidationListResponse(BaseModel):
    total: int
    items: List[ValidationRunResponse]


class FinalEvidenceReportResponse(BaseModel):
    validation_run_id: str
    repository_id: str
    repository_name: str
    baseline_job_id: str
    patched_job_id: Optional[str] = None

    created_at: datetime
    completed_at: Optional[datetime] = None

    verdict: str
    verdict_reason_code: str
    verdict_explanation: str

    # Clearly segregated sections:
    # 1. Measured test results
    baseline_summary: Dict[str, Any]
    patched_summary: Dict[str, Any]
    test_comparison: Dict[str, Any]

    # 2. Model-generated hypotheses (explicitly labeled)
    ai_diagnosis_summary: Dict[str, Any]

    # 3. Patch details
    patch_summary: Dict[str, Any]

    # 4. Environment & audit trail
    environment_metadata: Dict[str, Any]
    limitations_and_caveats: List[str]
    retry_history: List[Dict[str, Any]]

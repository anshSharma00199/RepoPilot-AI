from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EvidenceReference(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    description: str
    snippet: str


class ProposedChange(BaseModel):
    file_path: str
    explanation: str


class DiagnosticRequest(BaseModel):
    allow_exploratory: bool = False
    custom_instruction: Optional[str] = None


class DiagnosticApprovalRequest(BaseModel):
    notes: Optional[str] = None


class DiagnosticRejectionRequest(BaseModel):
    reason: Optional[str] = None


class DiagnosticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    repository_id: str
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None

    status: str  # proposed, approved, rejected
    review_notes: Optional[str] = None

    failure_summary: str
    root_cause_hypothesis: str
    confidence_score: float
    confidence_explanation: str

    is_insufficient_evidence: bool = False
    insufficient_evidence_reason: Optional[str] = None

    supporting_evidence: List[EvidenceReference] = []
    files_inspected: List[str] = []

    unified_diff: str = ""
    patch_hash: Optional[str] = None
    affected_files: List[str] = []

    patch_validation_status: str = "valid"  # valid, invalid, rejected_security
    patch_validation_errors: List[str] = []

    potential_regression_risks: Optional[str] = None
    recommended_tests: Optional[str] = None
    known_limitations: Optional[str] = None

    llm_provider: str
    llm_duration_seconds: float = 0.0


class DiagnosticListResponse(BaseModel):
    total: int
    items: List[DiagnosticResponse]

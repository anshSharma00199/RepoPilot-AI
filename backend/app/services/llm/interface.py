from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field


class LLMError(Exception):
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMInvalidOutputError(LLMError):
    pass


class RawLLMDiagnosticOutput(BaseModel):
    failure_summary: str = Field(..., description="Concise summary of the observed failure")
    root_cause_hypothesis: str = Field(..., description="Hypothesized root cause explanation")
    confidence_score: float = Field(0.5, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    confidence_explanation: str = Field(..., description="Why the model is confident or uncertain")

    is_insufficient_evidence: bool = Field(False, description="Set to true if evidence is insufficient to diagnose safely")
    insufficient_evidence_reason: Optional[str] = Field(None, description="Reason why evidence is insufficient")

    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="List of file paths and line ranges")
    proposed_changes: List[Dict[str, Any]] = Field(default_factory=list, description="High level summary of proposed changes")

    unified_diff: str = Field("", description="Valid unified diff representation of the proposed fix")
    rationale: str = Field("", description="Why this patch should fix the failure")
    potential_regression_risks: Optional[str] = Field(None, description="Known regression risks")
    recommended_tests: Optional[str] = Field(None, description="Additional tests recommended")
    known_limitations: Optional[str] = Field(None, description="Known limitations of this diagnosis")


@dataclass
class DiagnosticPromptInput:
    failure_summary: str
    context_text: str
    custom_instruction: Optional[str] = None


class LLMProvider(ABC):
    @abstractmethod
    async def diagnose(self, input_data: DiagnosticPromptInput) -> Tuple[RawLLMDiagnosticOutput, float]:
        """
        Sends diagnostic evidence to the LLM and returns schema-validated findings.
        Returns: (RawLLMDiagnosticOutput, duration_seconds)
        """
        pass

    @abstractmethod
    def is_configured(self) -> Tuple[bool, str]:
        """Checks if the provider credentials and settings are configured."""
        pass

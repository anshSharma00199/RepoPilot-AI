import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class DiagnosticReport(Base):
    __tablename__ = "diagnostic_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("execution_jobs.id", ondelete="CASCADE"), nullable=False)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Review status: proposed, approved, rejected
    status = Column(String(50), nullable=False, default="proposed")
    review_notes = Column(Text, nullable=True)

    # Diagnostic hypothesis & assessment
    failure_summary = Column(Text, nullable=False, default="Diagnostic evaluation of test execution.")
    root_cause_hypothesis = Column(Text, nullable=False, default="Automated root cause analysis.")
    confidence_score = Column(Float, nullable=False, default=0.5)
    confidence_explanation = Column(Text, nullable=False, default="Automated assessment.")

    def __init__(self, **kwargs):
        if not kwargs.get("failure_summary"):
            kwargs["failure_summary"] = "Diagnostic evaluation of test execution."
        if not kwargs.get("root_cause_hypothesis"):
            kwargs["root_cause_hypothesis"] = "Automated root cause analysis."
        if not kwargs.get("confidence_explanation"):
            kwargs["confidence_explanation"] = "Automated assessment."
        super().__init__(**kwargs)

    # Insufficient evidence indicator
    is_insufficient_evidence = Column(Boolean, default=False, nullable=False)
    insufficient_evidence_reason = Column(Text, nullable=True)

    # Retrieved Evidence References
    # List of: [{"file_path": str, "line_start": int, "line_end": int, "description": str, "snippet": str}]
    supporting_evidence = Column(JSON, default=list)
    files_inspected = Column(JSON, default=list)

    # Proposed Patch (Unified Diff)
    unified_diff = Column(Text, nullable=False, default="")
    patch_hash = Column(String(64), nullable=True)  # SHA-256
    affected_files = Column(JSON, default=list)

    # Patch Validation Engine Outcomes
    # patch_validation_status: valid, invalid, rejected_security
    patch_validation_status = Column(String(50), nullable=False, default="valid")
    patch_validation_errors = Column(JSON, default=list)

    # Impact & Risk Analysis
    potential_regression_risks = Column(Text, nullable=True)
    recommended_tests = Column(Text, nullable=True)
    known_limitations = Column(Text, nullable=True)

    # LLM Provider Metadata
    llm_provider = Column(String(100), nullable=False, default="fake")
    llm_duration_seconds = Column(Float, default=0.0)

    # Relationships
    repository = relationship("Repository", back_populates="diagnostic_reports")
    execution_job = relationship("ExecutionJob", back_populates="diagnostic_reports")
    validation_runs = relationship(
        "ValidationRun",
        back_populates="diagnostic_report",
        cascade="all, delete-orphan",
        order_by="desc(ValidationRun.created_at)",
    )

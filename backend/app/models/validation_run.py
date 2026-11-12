import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    baseline_job_id = Column(String(36), ForeignKey("execution_jobs.id", ondelete="CASCADE"), nullable=False)
    diagnostic_report_id = Column(String(36), ForeignKey("diagnostic_reports.id", ondelete="CASCADE"), nullable=False)
    patched_job_id = Column(String(36), ForeignKey("execution_jobs.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Patch & Workspace Metadata
    patch_version = Column(Integer, default=1, nullable=False)  # 1, 2, ...
    patch_hash = Column(String(64), nullable=False)             # SHA-256 of unified diff
    workspace_hash = Column(String(64), nullable=False)         # SHA-256 of patched workspace
    affected_files = Column(JSON, default=list)

    # Central Verdict Engine Outcomes
    # verdict: VALIDATED, UNVALIDATED, INFRASTRUCTURE_ERROR
    verdict = Column(String(50), nullable=False, default="UNVALIDATED")
    verdict_reason_code = Column(String(100), nullable=False)
    verdict_explanation = Column(Text, nullable=False)

    # Detailed Test Comparison Metrics
    target_test_name = Column(String(255), nullable=True)
    target_test_passed = Column(Boolean, default=False, nullable=False)
    regression_tests_passed = Column(Boolean, default=False, nullable=False)

    # Baseline vs Patched Counts
    baseline_tests_total = Column(Integer, default=0)
    baseline_tests_passed = Column(Integer, default=0)
    baseline_tests_failed = Column(Integer, default=0)

    patched_tests_total = Column(Integer, default=0)
    patched_tests_passed = Column(Integer, default=0)
    patched_tests_failed = Column(Integer, default=0)
    patched_tests_errors = Column(Integer, default=0)
    patched_tests_skipped = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)

    # Executed Test Sets
    tests_executed_before = Column(JSON, default=list)
    tests_executed_after = Column(JSON, default=list)
    target_tests_resolved = Column(JSON, default=list)
    new_regressions = Column(JSON, default=list)

    # Bounded Retry Budget Tracking
    attempt_number = Column(Integer, default=1, nullable=False)
    max_attempts = Column(Integer, default=2, nullable=False)
    is_retry_budget_exhausted = Column(Boolean, default=False, nullable=False)

    # Complete Final Evidence Report
    final_evidence_report = Column(JSON, default=dict)

    # Relationships
    repository = relationship("Repository", back_populates="validation_runs")
    baseline_job = relationship("ExecutionJob", foreign_keys=[baseline_job_id], back_populates="validation_runs_as_baseline")
    patched_job = relationship("ExecutionJob", foreign_keys=[patched_job_id], back_populates="validation_runs_as_patched")
    diagnostic_report = relationship("DiagnosticReport", back_populates="validation_runs")

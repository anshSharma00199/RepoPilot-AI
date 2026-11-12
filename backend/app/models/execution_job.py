import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Job lifecycle: pending, preparing, running, completed, failed, timed_out, cancelled
    status = Column(String(50), nullable=False, default="pending")

    # Granular stage: queued, detecting_command, installing_dependencies, executing_tests, capturing_results, cleanup, finished
    stage = Column(String(50), nullable=False, default="queued")

    # Error classification: test_failure, setup_error, syntax_error, timeout_error, infrastructure_error
    error_type = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Execution configuration & environment
    command = Column(JSON, default=list)  # ["pytest", "-v", "--tb=short"]
    image_version = Column(String(100), nullable=False, default="python:3.11-slim")
    exit_code = Column(Integer, nullable=True)
    timed_out = Column(Boolean, default=False, nullable=False)

    # Test Summary Counts
    tests_total = Column(Integer, default=0, nullable=False)
    tests_passed = Column(Integer, default=0, nullable=False)
    tests_failed = Column(Integer, default=0, nullable=False)
    tests_skipped = Column(Integer, default=0, nullable=False)
    tests_errors = Column(Integer, default=0, nullable=False)

    # Structured Failure Evidence
    # List of: [{"test_name": "...", "file": "...", "line": 42, "traceback": "..."}]
    failures = Column(JSON, default=list)

    # Bounded Logs
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    setup_logs = Column(Text, nullable=True)
    stdout_truncated = Column(Boolean, default=False, nullable=False)
    stderr_truncated = Column(Boolean, default=False, nullable=False)

    # Resource Limit Snapshot
    cpu_limit = Column(Float, default=1.0)
    memory_limit = Column(String(20), default="512m")
    timeout_seconds = Column(Integer, default=60)

    # Relationships
    repository = relationship("Repository", back_populates="execution_jobs")
    diagnostic_reports = relationship(
        "DiagnosticReport",
        back_populates="execution_job",
        cascade="all, delete-orphan",
        order_by="desc(DiagnosticReport.created_at)",
    )
    validation_runs_as_baseline = relationship(
        "ValidationRun",
        foreign_keys="[ValidationRun.baseline_job_id]",
        back_populates="baseline_job",
        cascade="all, delete-orphan",
    )
    validation_runs_as_patched = relationship(
        "ValidationRun",
        foreign_keys="[ValidationRun.patched_job_id]",
        back_populates="patched_job",
    )


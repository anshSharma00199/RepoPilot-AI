import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(Text, nullable=False)  # Internal directory on server, never exposed via API
    upload_size_bytes = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="pending")  # pending, analyzing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    scan_jobs = relationship(
        "ScanJob",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(ScanJob.started_at)",
    )
    files = relationship(
        "RepositoryFile",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="RepositoryFile.relative_path",
    )
    execution_jobs = relationship(
        "ExecutionJob",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(ExecutionJob.created_at)",
    )
    diagnostic_reports = relationship(
        "DiagnosticReport",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(DiagnosticReport.created_at)",
    )
    validation_runs = relationship(
        "ValidationRun",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(ValidationRun.created_at)",
    )



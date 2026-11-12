import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed

    # Metrics
    total_files = Column(Integer, default=0)
    total_directories = Column(Integer, default=0)
    total_size_bytes = Column(Integer, default=0)
    supported_source_files = Column(Integer, default=0)
    test_files = Column(Integer, default=0)
    manifest_files = Column(Integer, default=0)
    skipped_files = Column(Integer, default=0)
    parse_errors = Column(Integer, default=0)

    # Detected intelligence
    detected_frameworks = Column(JSON, default=list)  # ["pytest", "unittest"]
    detected_manifests = Column(JSON, default=list)   # ["requirements.txt", "pyproject.toml"]

    error_details = Column(Text, nullable=True)

    # Relationships
    repository = relationship("Repository", back_populates="scan_jobs")
    files = relationship(
        "RepositoryFile",
        back_populates="scan_job",
        cascade="all, delete-orphan",
    )

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=True)

    relative_path = Column(String(1024), nullable=False)  # Normalized relative path e.g. "src/main.py"
    entry_type = Column(String(50), nullable=False, default="file")  # file, directory
    language = Column(String(50), nullable=False, default="unknown")  # python, javascript, markdown, etc.
    file_size_bytes = Column(Integer, nullable=False, default=0)
    file_hash = Column(String(64), nullable=True)  # SHA-256

    classification = Column(String(50), nullable=False, default="other")
    # source_code, test, configuration, documentation, generated_output, binary_data, other

    status = Column(String(50), nullable=False, default="inventoried")
    # inventoried, content_analyzed, skipped, failed

    skip_reason = Column(Text, nullable=True)
    is_test = Column(Boolean, default=False, nullable=False)
    is_manifest = Column(Boolean, default=False, nullable=False)

    # AST findings & metadata
    # {
    #   "imports": ["pytest", "typing"],
    #   "classes": ["TestCalculator", "Base"],
    #   "functions": [{"name": "test_add", "lineno": 10, "is_async": false}],
    #   "syntax_error": {"message": "invalid syntax", "lineno": 15, "offset": 4}
    # }
    ast_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    repository = relationship("Repository", back_populates="files")
    scan_job = relationship("ScanJob", back_populates="files")

    __table_args__ = (
        Index("ix_repo_files_repo_id", "repository_id"),
        Index("ix_repo_files_classification", "classification"),
        Index("ix_repo_files_status", "status"),
        Index("ix_repo_files_is_test", "is_test"),
    )

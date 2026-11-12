from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SkippedFileDetail(BaseModel):
    relative_path: str
    entry_type: str
    language: str
    file_size_bytes: int
    classification: str
    skip_reason: str


class AstErrorDetail(BaseModel):
    relative_path: str
    error_message: str
    lineno: Optional[int] = None
    offset: Optional[int] = None


class CategoryBreakdown(BaseModel):
    source_code: int = 0
    test: int = 0
    configuration: int = 0
    documentation: int = 0
    generated_output: int = 0
    binary_data: int = 0
    other: int = 0


class AnalysisAuditSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repository_id: str
    repository_name: str
    scan_job_id: Optional[str] = None
    scanned_at: Optional[datetime] = None
    status: str

    # Discovered entries
    total_discovered_files: int
    total_discovered_directories: int
    total_discovered_entries: int
    files_inventoried: int
    files_content_analyzed: int
    content_analysis_coverage_pct: float  # Invariant: Never 100.0% if any files were skipped or unsupported

    # Python AST statistics
    python_files_total: int
    ast_parse_successes: int
    ast_parse_failures: int
    ast_syntax_errors: List[AstErrorDetail] = []

    # Category counts
    category_counts: CategoryBreakdown
    test_files_count: int
    configuration_files_count: int
    manifest_files_count: int
    detected_frameworks: List[str] = []
    detected_manifests: List[str] = []

    # Policy exclusions & skips
    files_excluded_by_policy_count: int
    excluded_directories: List[str] = []
    files_skipped_limits_or_unsupported_count: int
    skipped_files: List[SkippedFileDetail] = []

    # Explicit errors
    explicit_analysis_errors_count: int
    explicit_errors: List[str] = []

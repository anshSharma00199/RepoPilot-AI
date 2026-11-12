from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ScanJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str

    total_files: int
    total_directories: int
    total_size_bytes: int
    supported_source_files: int
    test_files: int
    manifest_files: int
    skipped_files: int
    parse_errors: int

    detected_frameworks: List[str] = []
    detected_manifests: List[str] = []
    error_details: Optional[str] = None

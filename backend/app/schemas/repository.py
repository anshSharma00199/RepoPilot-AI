from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.scan_job import ScanJobResponse


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    original_filename: str
    upload_size_bytes: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_scan: Optional[ScanJobResponse] = None


class RepositoryDetailResponse(RepositoryResponse):
    recent_scans: List[ScanJobResponse] = []


class RepositoryListResponse(BaseModel):
    total: int
    items: List[RepositoryResponse]

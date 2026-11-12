from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RepositoryFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    scan_job_id: Optional[str] = None
    relative_path: str
    entry_type: str
    language: str
    file_size_bytes: int
    file_hash: Optional[str] = None
    classification: str
    status: str
    skip_reason: Optional[str] = None
    is_test: bool
    is_manifest: bool
    ast_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class FileTreeNode(BaseModel):
    name: str
    relative_path: str
    entry_type: str  # "directory" or "file"
    file_id: Optional[str] = None
    language: Optional[str] = None
    classification: Optional[str] = None
    status: Optional[str] = None
    skip_reason: Optional[str] = None
    file_size_bytes: int = 0
    is_test: bool = False
    is_manifest: bool = False
    has_syntax_error: bool = False
    children: List["FileTreeNode"] = []


class RepositoryFileListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RepositoryFileResponse]

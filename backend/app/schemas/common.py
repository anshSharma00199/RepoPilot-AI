from typing import Any, Dict, Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail

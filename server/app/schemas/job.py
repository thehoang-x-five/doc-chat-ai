"""
Job Pydantic schemas.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel


class JobResponse(BaseModel):
    """Job response."""
    id: UUID
    workspace_id: UUID
    document_version_id: Optional[UUID] = None
    type: str
    status: str
    progress: int
    step: str
    error_message: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Job list response."""
    jobs: List[JobResponse]
    total: int


class JobCancelRequest(BaseModel):
    """Job cancel request."""
    pass

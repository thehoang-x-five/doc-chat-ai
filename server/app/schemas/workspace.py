"""
Workspace Pydantic schemas.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class CreateWorkspaceRequest(BaseModel):
    """Create workspace request."""
    name: str = Field(..., min_length=1, max_length=255)
    plan: str = Field(default="free", pattern="^(free|pro|enterprise)$")
    answer_policy: str = Field(default="balanced", pattern="^(strict|balanced|open)$")
    evidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class UpdateWorkspaceRequest(BaseModel):
    """Update workspace request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    answer_policy: Optional[str] = Field(None, pattern="^(strict|balanced|open)$")
    evidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


class AddMemberRequest(BaseModel):
    """Add member to workspace request."""
    email: EmailStr
    role: str = Field(default="VIEWER", pattern="^(EDITOR|VIEWER)$")


class UpdateMemberRoleRequest(BaseModel):
    """Update member role request."""
    role: str = Field(..., pattern="^(EDITOR|VIEWER)$")


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class MemberResponse(BaseModel):
    """Workspace member response."""
    user_id: UUID
    email: str
    full_name: Optional[str]
    role: str
    joined_at: datetime
    
    class Config:
        from_attributes = True


class WorkspaceResponse(BaseModel):
    """Workspace response."""
    id: UUID
    name: str
    owner_id: UUID
    plan: str
    answer_policy: str
    evidence_threshold: float
    created_at: datetime
    member_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class WorkspaceDetailResponse(WorkspaceResponse):
    """Workspace detail response with members."""
    members: List[MemberResponse] = []


class WorkspaceListResponse(BaseModel):
    """List of workspaces response."""
    workspaces: List[WorkspaceResponse]
    total: int

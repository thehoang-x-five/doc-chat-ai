"""
Document Pydantic schemas.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class UploadFromUrlRequest(BaseModel):
    """Upload from URL request."""
    url: HttpUrl
    title: Optional[str] = None
    tags: List[str] = Field(default=[])


class PresignedUploadRequest(BaseModel):
    """Request for direct browser presigned upload URL."""
    filename: str
    size: int
    mime_type: Optional[str] = None
    tags: List[str] = Field(default=[])


class UpdateDocumentRequest(BaseModel):
    """Update document request."""
    tags: List[str]


class DocumentFilters(BaseModel):
    """Document list filters."""
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class PresignedUploadResponse(BaseModel):
    """Response with presigned URL for direct upload."""
    document_id: UUID
    upload_url: str


class DocumentVersionResponse(BaseModel):
    """Document version response."""
    id: UUID
    version: int
    mime_type: Optional[str]
    size_bytes: Optional[int]
    page_count: Optional[int]
    language_detected: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    """Chunk response."""
    id: UUID
    chunk_index: int
    content: Optional[str]
    token_count: Optional[int]
    page_start: Optional[int]
    page_end: Optional[int]
    section_title: Optional[str]
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Document response."""
    id: UUID
    workspace_id: UUID
    title: str
    doc_type: str
    source: str
    tags: List[str]
    status: str
    category_id: Optional[UUID] = None
    content_summary: Optional[str] = None
    # Processing progress (0-100) for background processing UI
    processing_progress: int = 0
    # Current processing step description
    processing_step: Optional[str] = None
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    # Fields from latest version
    size: int = 0
    mime_type: Optional[str] = None
    chunk_count: int = 0
    version: int = 1
    
    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    """Document detail with versions."""
    versions: List[DocumentVersionResponse] = []
    latest_version: Optional[DocumentVersionResponse] = None


class DocumentListResponse(BaseModel):
    """Document list response."""
    documents: List[DocumentResponse]
    total: int

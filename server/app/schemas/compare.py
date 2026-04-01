"""
Schemas for Document Comparison feature.
Requirements: 21.1, 21.4
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class CompareSourceType(str, Enum):
    """Type of source for comparison"""
    UPLOAD = "upload"
    URL = "url"
    DOCUMENT = "document"
    VERSION = "version"


class ChangeType(str, Enum):
    """Type of change detected"""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ChangeCategory(str, Enum):
    """Category of change"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    STRUCTURAL = "structural"


class CompareSource(BaseModel):
    """Source for comparison - can be file upload, URL, or existing document"""
    type: CompareSourceType
    url: Optional[str] = None  # For URL type
    document_id: Optional[str] = None  # For document type
    version_id: Optional[str] = None  # For version type
    # Note: file upload handled separately in API endpoint


class DiffChange(BaseModel):
    """A single change between documents"""
    type: ChangeType
    category: ChangeCategory
    location_a: Optional[str] = None  # Page/section in doc A
    location_b: Optional[str] = None  # Page/section in doc B
    content_a: Optional[str] = None  # Original content
    content_b: Optional[str] = None  # New content
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CompareStatistics(BaseModel):
    """Statistics about changes"""
    added: int = 0
    removed: int = 0
    modified: int = 0
    total: int = 0


class SourceInfo(BaseModel):
    """Information about a comparison source"""
    type: CompareSourceType
    title: Optional[str] = None
    document_id: Optional[str] = None
    version_id: Optional[str] = None
    url: Optional[str] = None
    page_count: Optional[int] = None


class CompareResult(BaseModel):
    """Result of document comparison"""
    id: str
    workspace_id: str
    source_a: SourceInfo
    source_b: SourceInfo
    changes: List[DiffChange]
    statistics: CompareStatistics
    ai_summary: Optional[str] = None
    created_at: datetime
    created_by: str


# Request/Response schemas
class CompareRequest(BaseModel):
    """Request to compare two documents"""
    workspace_id: str
    source_a_type: CompareSourceType
    source_a_url: Optional[str] = None
    source_a_document_id: Optional[str] = None
    source_a_version_id: Optional[str] = None
    source_b_type: CompareSourceType
    source_b_url: Optional[str] = None
    source_b_document_id: Optional[str] = None
    source_b_version_id: Optional[str] = None
    include_ai_summary: bool = True


class CompareVersionsRequest(BaseModel):
    """Request to compare two versions of the same document"""
    document_id: str
    version_a: int
    version_b: int
    include_ai_summary: bool = True


class CompareResponse(BaseModel):
    """Response from comparison"""
    id: str
    workspace_id: str
    source_a: SourceInfo
    source_b: SourceInfo
    changes: List[DiffChange]
    statistics: CompareStatistics
    ai_summary: Optional[str] = None
    created_at: datetime

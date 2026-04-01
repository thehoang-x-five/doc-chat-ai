"""
Tools API - Direct access to tools without chat/LLM.

Provides REST endpoints to call tools directly for:
- Dashboard widgets
- Admin panels
- Analytics pages
- Batch operations
- External integrations

No LLM needed - just direct database queries.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.services.tools.tools_service_v2 import ToolsServiceV2, CountDocumentsInput, ListDocumentsInput

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================

class DocumentCountResponse(BaseModel):
    """Response for document count."""
    total: int
    status_filter: str
    tags_filter: List[str]
    workspace_id: str


class DocumentListItem(BaseModel):
    """Single document in list."""
    id: str
    title: str
    status: str
    tags: List[str]
    created_at: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]


class DocumentListResponse(BaseModel):
    """Response for document list."""
    documents: List[DocumentListItem]
    total: int
    limit: int


class DocumentStatsResponse(BaseModel):
    """Response for document statistics."""
    total_documents: int
    by_status: dict
    by_type: dict
    total_size_mb: float
    total_chunks: int
    all_tags: List[str]


class StorageUsageResponse(BaseModel):
    """Response for storage usage."""
    total_documents: int
    total_size_bytes: int
    total_size_mb: float
    total_size_gb: float
    average_size_mb: float


class ChatStatsResponse(BaseModel):
    """Response for chat statistics."""
    total_conversations: int
    total_messages: int
    days: int
    period_start: str


class MostCitedDocument(BaseModel):
    """Most cited document item."""
    id: str
    title: str
    citation_count: int


class MostCitedResponse(BaseModel):
    """Response for most cited documents."""
    documents: List[MostCitedDocument]
    total: int
    days: int


# =============================================================================
# METADATA ENDPOINTS
# =============================================================================

@router.get("/documents/count", response_model=DocumentCountResponse)
async def count_documents(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    status: str = Query("READY", description="Filter by status"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Count documents in workspace.
    
    Use cases:
    - Dashboard widget showing total documents
    - Admin panel statistics
    - Monitoring alerts
    """
    try:
        tools = ToolsServiceV2(db, workspace_id)
        input_data = CountDocumentsInput(status=status, tags=tags)
        result = await tools.count_documents(input_data)
        
        return DocumentCountResponse(
            total=result.total,
            status_filter=result.status_filter,
            tags_filter=result.tags_filter,
            workspace_id=result.workspace_id
        )
    except Exception as e:
        logger.error(f"Count documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/list", response_model=DocumentListResponse)
async def list_documents(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List documents with details.
    
    Use cases:
    - Document management page
    - File browser
    - Search results
    """
    try:
        tools = ToolsServiceV2(db, workspace_id)
        input_data = ListDocumentsInput(limit=limit, status=status, tags=tags)
        result = await tools.list_documents(input_data)
        
        documents = [
            DocumentListItem(
                id=doc.id,
                title=doc.title,
                status=doc.status,
                tags=doc.tags,
                created_at=doc.created_at.isoformat() if doc.created_at else None,
                file_size=None,
                mime_type=None
            )
            for doc in result.documents
        ]
        
        return DocumentListResponse(
            documents=documents,
            total=result.total,
            limit=result.limit
        )
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive document statistics.
    
    Use cases:
    - Dashboard overview
    - Analytics page
    - Admin reports
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_document_stats()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return DocumentStatsResponse(**result)


@router.get("/documents/search", response_model=DocumentListResponse)
async def search_documents_by_name(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    query: str = Query(..., min_length=1, description="Search query"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search documents by name/title.
    
    Use cases:
    - Search bar
    - Quick find
    - Autocomplete
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.search_documents_by_name(query)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    # Convert to DocumentListResponse format
    documents = [
        DocumentListItem(
            id=doc["id"],
            title=doc["title"],
            status=doc["status"],
            tags=doc["tags"],
            created_at=None,
            file_size=None,
            mime_type=None
        )
        for doc in result["matches"]
    ]
    
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=len(documents)
    )


# =============================================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/documents/recent", response_model=DocumentListResponse)
async def get_recent_uploads(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recently uploaded documents.
    
    Use cases:
    - "Recent uploads" widget
    - Activity feed
    - What's new section
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_recent_uploads(days=days, limit=limit)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [DocumentListItem(**doc) for doc in result["documents"]]
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=limit
    )


@router.get("/documents/largest", response_model=DocumentListResponse)
async def get_largest_documents(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get largest documents by file size.
    
    Use cases:
    - Storage optimization
    - Cleanup suggestions
    - Disk usage analysis
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_largest_documents(limit=limit)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [
        DocumentListItem(
            id=doc["id"],
            title=doc["title"],
            status=doc["status"],
            tags=[],
            created_at=None,
            file_size=doc["file_size"],
            mime_type=None
        )
        for doc in result["documents"]
    ]
    
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=limit
    )


@router.get("/documents/by-type", response_model=DocumentListResponse)
async def get_documents_by_type(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    file_type: str = Query(..., description="File type: pdf, docx, txt, etc."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get documents by file type.
    
    Use cases:
    - Filter by type
    - Type-specific operations
    - Format analysis
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_documents_by_type(file_type)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [DocumentListItem(**doc) for doc in result["documents"]]
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=len(documents)
    )


# =============================================================================
# SEARCH & FILTER ENDPOINTS
# =============================================================================

@router.get("/documents/by-date", response_model=DocumentListResponse)
async def search_by_date_range(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    days_ago: int = Query(..., ge=1, description="Days ago from now"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search documents by date range.
    
    Use cases:
    - Time-based filters
    - "This week" / "This month" views
    - Temporal analysis
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.search_by_date_range(days_ago=days_ago)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [DocumentListItem(**doc) for doc in result["documents"]]
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=len(documents)
    )


@router.get("/documents/without-tags", response_model=DocumentListResponse)
async def get_documents_without_tags(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get documents without tags.
    
    Use cases:
    - Cleanup tasks
    - Tagging reminders
    - Organization suggestions
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_documents_without_tags()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [DocumentListItem(**doc) for doc in result["documents"]]
    return DocumentListResponse(
        documents=documents,
        total=result["total"],
        limit=len(documents)
    )


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@router.get("/analytics/chat-stats", response_model=ChatStatsResponse)
async def get_chat_statistics(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get chat/conversation statistics.
    
    Use cases:
    - Usage analytics
    - Activity dashboard
    - Engagement metrics
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_chat_statistics(days=days)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return ChatStatsResponse(**result)


@router.get("/analytics/most-cited", response_model=MostCitedResponse)
async def get_most_cited_documents(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get most cited/used documents.
    
    Use cases:
    - Popular content
    - Usage insights
    - Content recommendations
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_most_cited_documents(limit=limit, days=days)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    documents = [MostCitedDocument(**doc) for doc in result["documents"]]
    return MostCitedResponse(
        documents=documents,
        total=result["total"],
        days=result["days"]
    )


# =============================================================================
# WORKSPACE ENDPOINTS
# =============================================================================

@router.get("/workspace/storage", response_model=StorageUsageResponse)
async def get_storage_usage(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get storage usage statistics.
    
    Use cases:
    - Storage dashboard
    - Quota monitoring
    - Billing calculations
    """
    tools = ToolsService(db, workspace_id)
    result = await tools.get_storage_usage()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return StorageUsageResponse(**result)

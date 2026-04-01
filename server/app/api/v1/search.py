"""
Progressive Disclosure API endpoints.

Implements 3-layer workflow pattern from claude-mem:
- Layer 1 (search/index): Compact index with IDs (~50-100 tokens/result)
- Layer 2 (search/timeline): Chronological context
- Layer 3 (search/details): Full content (~500-1000 tokens/result)

Token savings: ~10x by filtering before fetching full details

Production features:
- Redis caching for repeated queries
- Query validation and sanitization
- Rate limiting (30 requests/minute)
- Error handling with user-friendly messages
"""
import logging
import re
import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user, get_db
from app.db.models import User, Chunk, Document, DocumentVersion
from app.services.search.timeline_service import TimelineService, TimelineItem
from app.services.search.search_cache_service import get_search_cache

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# SCHEMAS WITH VALIDATION
# ============================================================================

class ChunkIndex(BaseModel):
    """Compact chunk index (Layer 1)."""
    id: UUID
    document_id: UUID
    document_title: str
    snippet: str = Field(description="First 200 characters")
    score: Optional[float] = None
    rerank_score: Optional[float] = None
    page_start: Optional[int] = None
    created_at: str
    
    class Config:
        from_attributes = True


class SearchQueryParams(BaseModel):
    """Validated search query parameters."""
    query: str
    workspace_id: UUID
    limit: int = Field(default=20, ge=1, le=50)
    
    @validator('query')
    def validate_query(cls, v):
        """Validate and sanitize search query."""
        # Remove leading/trailing whitespace
        v = v.strip()
        
        # Min length check
        if len(v) < 2:
            raise ValueError("Query must be at least 2 characters")
        
        # Max length check
        if len(v) > 200:
            raise ValueError("Query too long (max 200 characters)")
        
        # Allow Vietnamese characters, alphanumeric, spaces, and common punctuation
        # Vietnamese unicode ranges: \u00C0-\u1EF9
        if not re.match(r'^[\w\s\u00C0-\u1EF9.,!?-]+$', v, re.UNICODE):
            raise ValueError("Query contains invalid characters")
        
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        """Validate result limit."""
        if v < 1:
            return 1
        if v > 50:
            return 50
        return v


class TimelineItemSchema(BaseModel):
    """Timeline item (Layer 2)."""
    chunk_id: UUID
    document_title: str
    snippet: str = Field(description="First 150 characters")
    page_start: Optional[int] = None
    created_at: str
    is_anchor: bool
    
    class Config:
        from_attributes = True


class ChunkDetail(BaseModel):
    """Full chunk details (Layer 3)."""
    id: UUID
    document_id: UUID
    document_title: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


# ============================================================================
# LAYER 1: INDEX (COMPACT) - WITH CACHE & RATE LIMITING
# ============================================================================

@router.get("/search/index", response_model=List[ChunkIndex])
@limiter.limit("30/minute")  # Rate limit: 30 searches per minute
async def search_index(
    request: Request,  # Required by slowapi
    query: str = Query(..., description="Search query", min_length=2, max_length=200),
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Layer 1: Get compact search index.
    
    Returns lightweight results (~50-100 tokens each) for quick preview.
    Users can then select IDs to fetch full details.
    
    Features:
    - Redis caching for repeated queries (1 hour TTL)
    - Query validation and sanitization
    - Rate limiting (30 requests/minute)
    - Vector search with pgvector index
    - Singleton embedding service
    
    Performance:
    - Cache hit: <10ms
    - Cache miss: 200-300ms
    """
    start_time = time.time()
    
    try:
        # Validate query
        try:
            params = SearchQueryParams(
                query=query,
                workspace_id=workspace_id,
                limit=limit
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Check cache first
        cache = get_search_cache()
        cached_results = await cache.get(
            query=params.query,
            workspace_id=str(params.workspace_id),
            limit=params.limit
        )
        
        if cached_results is not None:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Search cache HIT: {params.query[:50]}... ({latency_ms}ms)")
            return cached_results
        
        # Cache miss - perform search
        from app.services.core.retriever_service import RetrieverService
        from app.services.core.embedding_service import get_embedding_service
        
        # Use singleton embedding service (cached model - FAST)
        embedding_service = get_embedding_service()
        
        # Use direct vector search (fastest - uses pgvector index)
        retriever = RetrieverService(session=db, embedding_service=embedding_service)
        
        # Vector search only (uses pgvector index - very fast)
        results = await retriever.search(
            query=params.query,
            workspace_id=params.workspace_id,
            top_k=params.limit,
        )
        
        # Convert to compact index
        index_results = []
        for result in results:
            index_results.append(ChunkIndex(
                id=result.chunk_id,
                document_id=result.document_id,
                document_title=result.document_title,
                snippet=result.content[:200] + "..." if len(result.content) > 200 else result.content,
                score=result.score,
                rerank_score=result.score,  # Use vector score
                page_start=result.page_start,
                created_at=str(result.chunk_id),  # Placeholder
            ))
        
        # Cache results for future requests
        await cache.set(
            query=params.query,
            workspace_id=str(params.workspace_id),
            limit=params.limit,
            results=[r.dict() for r in index_results]
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Search completed: {params.query[:50]}... "
            f"({len(index_results)} results, {latency_ms}ms)"
        )
        
        return index_results
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            f"Search failed: {query[:50]}... ({latency_ms}ms) - {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Search failed. Please try again later."
        )


# ============================================================================
# LAYER 2: TIMELINE (CHRONOLOGICAL CONTEXT)
# ============================================================================

@router.get("/search/timeline", response_model=List[TimelineItemSchema])
async def get_timeline(
    anchor_id: UUID = Query(..., description="Anchor chunk ID"),
    depth_before: int = Query(3, ge=0, le=10),
    depth_after: int = Query(3, ge=0, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Layer 2: Get chronological timeline around anchor chunk.
    
    Shows context before/after the anchor chunk to understand
    how content evolved over time.
    """
    timeline_service = TimelineService(db)
    
    timeline = await timeline_service.get_timeline(
        anchor_chunk_id=anchor_id,
        depth_before=depth_before,
        depth_after=depth_after,
        same_document=True,
    )
    
    # Convert to schema
    return [
        TimelineItemSchema(
            chunk_id=item.chunk_id,
            document_title=item.document_title,
            snippet=item.content[:150] + "..." if len(item.content) > 150 else item.content,
            page_start=item.page_start,
            created_at=item.created_at.isoformat(),
            is_anchor=item.is_anchor,
        )
        for item in timeline
    ]


# ============================================================================
# LAYER 3: DETAILS (FULL CONTENT)
# ============================================================================

class GetDetailsRequest(BaseModel):
    """Request for full chunk details."""
    chunk_ids: List[UUID] = Field(..., max_length=10, description="Chunk IDs to fetch")


@router.post("/search/details", response_model=List[ChunkDetail])
async def get_details(
    request: GetDetailsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Layer 3: Get full content for selected chunks.
    
    Fetches complete chunk content (~500-1000 tokens each).
    Should only be called for chunks user wants detailed view of.
    """
    if not request.chunk_ids:
        return []
    
    # Fetch chunks with documents
    result = await db.execute(
        select(Chunk, Document)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Chunk.id.in_(request.chunk_ids))
    )
    
    rows = result.all()
    
    return [
        ChunkDetail(
            id=chunk.id,
            document_id=doc.id,
            document_title=doc.title,
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_title=chunk.section_title,
            created_at=chunk.created_at.isoformat(),
        )
        for chunk, doc in rows
    ]

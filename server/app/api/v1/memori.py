"""
Memori API endpoints for memory management.
Provides endpoints for:
- Viewing recalled facts
- Manual fact management
- Knowledge graph queries
- Memory statistics
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.memori import MemoriManager, MemoriConfig
from app.services.memori.models import SemanticTriple, RecalledFact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memori", tags=["Memory"])


# =============================================================================
# SCHEMAS
# =============================================================================

class FactCreate(BaseModel):
    """Schema for creating a fact."""
    content: str = Field(..., description="Fact content")
    importance_score: float = Field(default=1.0, ge=0.0, le=10.0)


class FactResponse(BaseModel):
    """Schema for fact response."""
    id: int
    content: str
    similarity: float = 0.0
    lexical_score: float = 0.0
    rank_score: float = 0.0
    importance_score: float = 1.0


class TripleCreate(BaseModel):
    """Schema for creating a semantic triple."""
    subject_name: str
    subject_type: Optional[str] = None
    predicate: str
    object_name: str
    object_type: Optional[str] = None


class TripleResponse(BaseModel):
    """Schema for triple response."""
    subject_name: str
    subject_type: Optional[str]
    predicate: str
    object_name: str
    object_type: Optional[str]


class RecallRequest(BaseModel):
    """Schema for recall request."""
    query: str = Field(..., description="Query to search for relevant facts")
    limit: int = Field(default=5, ge=1, le=50)


class RecallResponse(BaseModel):
    """Schema for recall response."""
    facts: List[FactResponse]
    query: str
    total_found: int


class MemoryStatsResponse(BaseModel):
    """Schema for memory statistics."""
    entity_id: str
    total_facts: int
    total_triples: int
    avg_importance: float


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/recall",
    response_model=RecallResponse,
    summary="Recall relevant facts",
    description="Search for facts relevant to a query using semantic similarity"
)
async def recall_facts(
    request: RecallRequest,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    entity_id: Optional[str] = Query(None, description="Entity ID (user ID)"),
    conversation_id: Optional[UUID] = Query(None, description="Conversation ID"),
    db: AsyncSession = Depends(get_db),
):
    """Recall relevant facts for a query."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        facts = await manager.recall_for_query(
            query=request.query,
            entity_id=entity_id,
            conversation_id=conversation_id,
            limit=request.limit,
        )
        
        return RecallResponse(
            facts=[
                FactResponse(
                    id=f.id,
                    content=f.content,
                    similarity=f.similarity,
                    lexical_score=f.lexical_score,
                    rank_score=f.rank_score,
                )
                for f in facts
            ],
            query=request.query,
            total_found=len(facts),
        )
    except Exception as e:
        logger.error(f"Recall failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recall facts: {str(e)}"
        )


@router.get(
    "/facts/{entity_id}",
    response_model=List[FactResponse],
    summary="List all facts for an entity",
    description="Get all facts for an entity (no semantic search, just list)"
)
async def list_facts(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all facts for an entity."""
    from sqlalchemy import select, desc
    from app.db.models import MemoriEntity, MemoriEntityFact
    
    try:
        # Get entity internal ID
        result = await db.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        
        if not internal_id:
            return []
        
        # Get facts directly from MemoriEntityFact (which contains content)
        query = (
            select(MemoriEntityFact)
            .where(MemoriEntityFact.entity_id == internal_id)
            .order_by(desc(MemoriEntityFact.importance_score), desc(MemoriEntityFact.created_at))
            .limit(limit)
            .offset(offset)
        )
        
        result = await db.execute(query)
        facts = result.scalars().all()
        
        return [
            FactResponse(
                id=f.id,
                content=f.content,
                similarity=1.0,  # No similarity score for list
                lexical_score=0.0,
                rank_score=0.0,
                importance_score=f.importance_score or 1.0,
            )
            for f in facts
        ]
    except Exception as e:
        logger.error(f"Failed to list facts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list facts: {str(e)}"
        )


@router.post(
    "/facts/{entity_id}",
    response_model=List[int],
    summary="Add facts to an entity",
    description="Add new facts about an entity with embeddings for semantic search"
)
async def add_facts(
    entity_id: str,
    facts: List[FactCreate],
    workspace_id: UUID = Query(..., description="Workspace ID"),
    conversation_id: Optional[UUID] = Query(None, description="Source conversation"),
    db: AsyncSession = Depends(get_db),
):
    """Add facts to an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        fact_contents = [f.content for f in facts]
        importance = facts[0].importance_score if facts else 1.0
        
        created_ids = await manager.add_facts(
            entity_id=entity_id,
            facts=fact_contents,
            conversation_id=conversation_id,
            importance_score=importance,
        )
        
        await db.commit()
        return created_ids
    except Exception as e:
        logger.error(f"Failed to add facts: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add facts: {str(e)}"
        )


@router.post(
    "/triples/{entity_id}",
    response_model=List[int],
    summary="Add semantic triples",
    description="Add semantic triples (knowledge graph relationships) for an entity"
)
async def add_triples(
    entity_id: str,
    triples: List[TripleCreate],
    workspace_id: UUID = Query(..., description="Workspace ID"),
    conversation_id: Optional[UUID] = Query(None, description="Source conversation"),
    db: AsyncSession = Depends(get_db),
):
    """Add semantic triples to knowledge graph."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        semantic_triples = [
            SemanticTriple(
                subject_name=t.subject_name,
                subject_type=t.subject_type,
                predicate=t.predicate,
                object_name=t.object_name,
                object_type=t.object_type,
            )
            for t in triples
        ]
        
        created_ids = await manager.add_semantic_triples(
            entity_id=entity_id,
            triples=semantic_triples,
            conversation_id=conversation_id,
        )
        
        await db.commit()
        return created_ids
    except Exception as e:
        logger.error(f"Failed to add triples: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add triples: {str(e)}"
        )


@router.get(
    "/knowledge-graph/{entity_id}",
    response_model=List[TripleResponse],
    summary="Get knowledge graph",
    description="Get semantic triples (knowledge graph) for an entity"
)
async def get_knowledge_graph(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge graph triples for an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        triples = await manager.get_knowledge_graph(entity_id, limit=limit)
        
        return [
            TripleResponse(
                subject_name=t.subject_name,
                subject_type=t.subject_type,
                predicate=t.predicate,
                object_name=t.object_name,
                object_type=t.object_type,
            )
            for t in triples
        ]
    except Exception as e:
        logger.error(f"Failed to get knowledge graph: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get knowledge graph: {str(e)}"
        )


@router.get(
    "/stats/{entity_id}",
    response_model=MemoryStatsResponse,
    summary="Get memory statistics",
    description="Get statistics about stored memories for an entity"
)
async def get_memory_stats(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get memory statistics for an entity."""
    from sqlalchemy import select, func
    from app.db.models import MemoriEntity, MemoriEntityFact, MemoriKnowledgeGraph
    
    try:
        # Get entity
        result = await db.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        
        if not internal_id:
            return MemoryStatsResponse(
                entity_id=entity_id,
                total_facts=0,
                total_triples=0,
                avg_importance=0.0,
            )
        
        # Count facts
        facts_result = await db.execute(
            select(
                func.count(MemoriEntityFact.id),
                func.avg(MemoriEntityFact.importance_score),
            ).where(MemoriEntityFact.entity_id == internal_id)
        )
        facts_row = facts_result.one()
        total_facts = facts_row[0] or 0
        avg_importance = float(facts_row[1] or 0.0)
        
        # Count triples
        triples_result = await db.execute(
            select(func.count(MemoriKnowledgeGraph.id))
            .where(MemoriKnowledgeGraph.entity_id == internal_id)
        )
        total_triples = triples_result.scalar() or 0
        
        return MemoryStatsResponse(
            entity_id=entity_id,
            total_facts=total_facts,
            total_triples=total_triples,
            avg_importance=avg_importance,
        )
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory stats: {str(e)}"
        )


@router.delete(
    "/cleanup/{entity_id}",
    summary="Cleanup old facts",
    description="Remove old/low-importance facts to prevent unbounded growth"
)
async def cleanup_facts(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    max_facts: int = Query(default=1000, ge=100, le=10000),
    min_importance: float = Query(default=0.1, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Cleanup old/low-importance facts."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        deleted_count = await manager.cleanup_old_facts(
            entity_id=entity_id,
            max_facts=max_facts,
            min_importance=min_importance,
        )
        
        await db.commit()
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Failed to cleanup facts: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup facts: {str(e)}"
        )


# =============================================================================
# PREFERENCE ENDPOINTS (Phase 2)
# =============================================================================

class PreferenceCreate(BaseModel):
    """Schema for creating preferences."""
    preferences: dict = Field(..., description="Dict of preferences {key: value}")


class PreferenceResponse(BaseModel):
    """Schema for preference response."""
    entity_id: str
    preferences: dict


@router.post(
    "/preferences/{entity_id}",
    response_model=dict,
    summary="Add preferences",
    description="Add or update preferences for an entity (UI, language, format, etc.)"
)
async def add_preferences(
    entity_id: str,
    request: PreferenceCreate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Add preferences for an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        added = []
        for key, value in request.preferences.items():
            # Determine category
            if key.startswith('ui_'):
                category = 'ui'
            elif key == 'language':
                category = 'language'
            elif key.startswith('response_'):
                category = 'response'
            else:
                category = 'general'
            
            pref_id = await manager.add_preference(
                entity_id=entity_id,
                category=category,
                key=key,
                value=str(value),
                importance=8.0,  # High importance for preferences
            )
            added.append(pref_id)
        
        await db.commit()
        
        return {
            "entity_id": entity_id,
            "added": len(added),
            "preference_ids": added,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to add preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/preferences/{entity_id}",
    response_model=PreferenceResponse,
    summary="Get preferences",
    description="Get all preferences for an entity"
)
async def get_preferences(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
):
    """Get preferences for an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        preferences = await manager.get_preferences(
            entity_id=entity_id,
            category=category,
        )
        
        return PreferenceResponse(
            entity_id=entity_id,
            preferences=preferences,
        )
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/preferences/{entity_id}/{pref_id}",
    summary="Update preference",
    description="Update a specific preference"
)
async def update_preference(
    entity_id: str,
    pref_id: int,
    value: str,
    importance: float = 8.0,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update a preference."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        await manager.update_preference(
            pref_id=pref_id,
            value=value,
            importance=importance,
        )
        
        await db.commit()
        
        return {"success": True, "pref_id": pref_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/preferences/{entity_id}/{pref_id}",
    summary="Delete preference",
    description="Delete a specific preference"
)
async def delete_preference(
    entity_id: str,
    pref_id: int,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Delete a preference."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        await manager.delete_preference(pref_id)
        await db.commit()
        
        return {"success": True, "deleted": pref_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ATTRIBUTE ENDPOINTS (Phase 2)
# =============================================================================

class AttributeCreate(BaseModel):
    """Schema for creating attributes."""
    attributes: dict = Field(..., description="Dict of attributes {key: value}")


class AttributeResponse(BaseModel):
    """Schema for attribute response."""
    entity_id: str
    attributes: dict


@router.post(
    "/attributes/{entity_id}",
    response_model=dict,
    summary="Add attributes",
    description="Add or update attributes for an entity (role, skills, location, etc.)"
)
async def add_attributes(
    entity_id: str,
    request: AttributeCreate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Add attributes for an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        added = []
        for key, value in request.attributes.items():
            # Determine category
            if key in ['role', 'job_title', 'position']:
                category = 'role'
            elif key in ['skill', 'expertise', 'programming_language']:
                category = 'skill'
            elif key in ['location', 'city', 'country']:
                category = 'location'
            else:
                category = 'general'
            
            attr_id = await manager.add_attribute(
                entity_id=entity_id,
                category=category,
                key=key,
                value=str(value),
                importance=7.0,  # Medium-high importance for attributes
            )
            added.append(attr_id)
        
        await db.commit()
        
        return {
            "entity_id": entity_id,
            "added": len(added),
            "attribute_ids": added,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to add attributes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/attributes/{entity_id}",
    response_model=AttributeResponse,
    summary="Get attributes",
    description="Get all attributes for an entity"
)
async def get_attributes(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
):
    """Get attributes for an entity."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        attributes = await manager.get_attributes(
            entity_id=entity_id,
            category=category,
        )
        
        return AttributeResponse(
            entity_id=entity_id,
            attributes=attributes,
        )
    except Exception as e:
        logger.error(f"Failed to get attributes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/attributes/{entity_id}/{attr_id}",
    summary="Update attribute",
    description="Update a specific attribute"
)
async def update_attribute(
    entity_id: str,
    attr_id: int,
    value: str,
    importance: float = 7.0,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update an attribute."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        await manager.update_attribute(
            attr_id=attr_id,
            value=value,
            importance=importance,
        )
        
        await db.commit()
        
        return {"success": True, "attr_id": attr_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update attribute: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/attributes/{entity_id}/{attr_id}",
    summary="Delete attribute",
    description="Delete a specific attribute"
)
async def delete_attribute(
    entity_id: str,
    attr_id: int,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Delete an attribute."""
    try:
        config = MemoriConfig(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        manager = MemoriManager(db, config)
        
        await manager.delete_attribute(attr_id)
        await db.commit()
        
        return {"success": True, "deleted": attr_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete attribute: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ANALYTICS ENDPOINTS (Phase 4)
# =============================================================================

class HealthScoreResponse(BaseModel):
    """Schema for health score response."""
    entity_id: str
    health_score: float
    status: str
    breakdown: Optional[dict] = None
    recommendations: Optional[list] = None
    message: Optional[str] = None


class UsageAnalyticsResponse(BaseModel):
    """Schema for usage analytics response."""
    entity_id: str
    period_days: Optional[int] = None
    facts: Optional[dict] = None
    preferences: Optional[dict] = None
    attributes: Optional[dict] = None
    summary: Optional[dict] = None
    message: Optional[str] = None


@router.get(
    "/analytics/health/{entity_id}",
    response_model=HealthScoreResponse,
    summary="Get memory health score",
    description="Calculate comprehensive health score for entity's memory"
)
async def get_health_score(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get memory health score for an entity."""
    try:
        from app.services.memori.analytics_service import MemoriAnalytics
        
        analytics = MemoriAnalytics(db)
        health_data = await analytics.get_memory_health_score(
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        
        return HealthScoreResponse(**health_data)
    except Exception as e:
        logger.error(f"Failed to get health score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analytics/usage/{entity_id}",
    response_model=UsageAnalyticsResponse,
    summary="Get usage analytics",
    description="Get usage statistics for entity's memory over specified period"
)
async def get_usage_analytics(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Get usage analytics for an entity."""
    try:
        from app.services.memori.analytics_service import MemoriAnalytics
        
        analytics = MemoriAnalytics(db)
        usage_data = await analytics.get_usage_analytics(
            entity_id=entity_id,
            days=days,
        )
        
        return UsageAnalyticsResponse(**usage_data)
    except Exception as e:
        logger.error(f"Failed to get usage analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analytics/top-facts/{entity_id}",
    response_model=List[dict],
    summary="Get top facts",
    description="Get top facts for an entity sorted by importance, recency, or access"
)
async def get_top_facts(
    entity_id: str,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    limit: int = Query(default=10, ge=1, le=100, description="Number of facts to return"),
    sort_by: str = Query(default="importance", description="Sort by: importance, recent, accessed"),
    db: AsyncSession = Depends(get_db),
):
    """Get top facts for an entity."""
    try:
        from app.services.memori.analytics_service import MemoriAnalytics
        
        analytics = MemoriAnalytics(db)
        facts = await analytics.get_top_facts(
            entity_id=entity_id,
            limit=limit,
            sort_by=sort_by,
        )
        
        return facts
    except Exception as e:
        logger.error(f"Failed to get top facts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MEMORY INTELLIGENCE LAYER - User Control API
# =============================================================================

@router.patch(
    "/facts/{fact_id}/importance",
    summary="Update fact importance score",
    description="Manually update the importance score of a specific fact (Memory Intelligence Layer)"
)
async def update_fact_importance(
    fact_id: int,
    importance_score: float = Query(..., ge=0.0, le=10.0, description="New importance score"),
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update the importance score of a fact."""
    try:
        from app.db.models import MemoriEntityFact
        from sqlalchemy import update
        
        # Update the fact
        stmt = (
            update(MemoriEntityFact)
            .where(MemoriEntityFact.id == fact_id)
            .values(importance_score=importance_score)
            .returning(MemoriEntityFact)
        )
        
        result = await db.execute(stmt)
        updated_fact = result.scalar_one_or_none()
        
        if not updated_fact:
            raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
        
        await db.commit()
        
        logger.info(f"Updated fact {fact_id} importance to {importance_score}")
        
        return {
            "success": True,
            "fact_id": fact_id,
            "importance_score": importance_score,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update fact importance: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/facts/{fact_id}/pin",
    summary="Pin or unpin a fact",
    description="Pin a fact (set importance to 10) or unpin (reset to 1) for Memory Intelligence"
)
async def pin_fact(
    fact_id: int,
    pinned: bool = Query(..., description="True to pin, False to unpin"),
    workspace_id: UUID = Query(..., description="Workspace ID"),
    db: AsyncSession = Depends(get_db),
):
    """Pin or unpin a fact by setting importance score."""
    try:
        from app.db.models import MemoriEntityFact
        from sqlalchemy import update
        
        # Set importance: 10 if pinned, 1 if unpinned
        new_importance = 10.0 if pinned else 1.0
        
        stmt = (
            update(MemoriEntityFact)
            .where(MemoriEntityFact.id == fact_id)
            .values(importance_score=new_importance)
            .returning(MemoriEntityFact)
        )
        
        result = await db.execute(stmt)
        updated_fact = result.scalar_one_or_none()
        
        if not updated_fact:
            raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
        
        await db.commit()
        
        action = "pinned" if pinned else "unpinned"
        logger.info(f"Fact {fact_id} {action} (importance: {new_importance})")
        
        return {
            "success": True,
            "fact_id": fact_id,
            "pinned": pinned,
            "importance_score": new_importance,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pin fact: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

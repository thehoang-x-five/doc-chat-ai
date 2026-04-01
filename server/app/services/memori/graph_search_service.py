"""
Graph Search Service - Multi-strategy search combining graph and vector.

Hỗ trợ: Vector search, Triplet search, Graph traversal.

Search Types:
- AUTO: Tự động chọn strategy tốt nhất
- VECTOR: FAISS semantic similarity (existing)
- TRIPLET: Subject-Predicate-Object queries
- GRAPH_TRAVERSAL: Follow relationships từ entity
- COMBINED: Kết hợp vector + graph
"""

import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Multi-strategy search types."""
    AUTO = "auto"                    # Intelligent selection
    VECTOR = "vector"                # Existing FAISS/semantic search
    TRIPLET = "triplet"              # Subject-Predicate-Object
    GRAPH_TRAVERSAL = "graph"        # Follow relationships
    COMBINED = "combined"            # Vector + Graph fusion


@dataclass
class SearchResult:
    """Unified search result format."""
    content: str
    score: float
    source: str  # "vector", "triplet", "graph"
    metadata: Dict[str, Any] = field(default_factory=dict)
    related_entities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
            "related_entities": self.related_entities,
        }


class GraphSearchService:
    """
    Multi-strategy search service combining graph and vector approaches.
    
    Features:
    - Vector search (semantic similarity via FAISS)
    - Triplet search (Subject-Predicate-Object queries)
    - Graph traversal (follow relationships from entities)
    - Auto-detection of best search strategy
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._memori_recall = None
    
    async def _get_memori_recall(self):
        """Lazy load MemoriRecall service."""
        if self._memori_recall is None:
            try:
                from app.services.memori.recall_service import MemoriRecall, MemoriConfig
                config = MemoriConfig()
                self._memori_recall = MemoriRecall(self.session, config)
            except ImportError as e:
                logger.warning(f"MemoriRecall not available: {e}")
        return self._memori_recall
    
    async def search(
        self,
        query: str,
        entity_id: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
        search_type: SearchType = SearchType.AUTO,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Execute search with specified strategy.
        
        Args:
            query: Search query
            entity_id: Optional entity to scope search
            workspace_id: Optional workspace filter
            search_type: SearchType enum
            limit: Max results
            
        Returns:
            List of SearchResult objects
        """
        # Auto-detect best strategy
        if search_type == SearchType.AUTO:
            search_type = await self._detect_best_strategy(query)
            logger.info(f"🔍 Auto-detected search type: {search_type.value}")
        
        results = []
        
        if search_type == SearchType.TRIPLET:
            results = await self._triplet_search(query, entity_id, workspace_id, limit)
        elif search_type == SearchType.GRAPH_TRAVERSAL:
            results = await self._graph_traversal(query, entity_id, workspace_id, limit)
        elif search_type == SearchType.COMBINED:
            results = await self._combined_search(query, entity_id, workspace_id, limit)
        else:  # VECTOR (default)
            results = await self._vector_search(query, entity_id, workspace_id, limit)
        
        logger.info(f"🔍 Graph search ({search_type.value}): found {len(results)} results")
        return results
    
    async def _detect_best_strategy(self, query: str) -> SearchType:
        """
        Detect best search strategy based on query pattern.
        
        Heuristics:
        - Relationship words -> GRAPH_TRAVERSAL
        - Question about entity properties -> TRIPLET
        - General semantic query -> VECTOR
        """
        query_lower = query.lower()
        
        # Graph traversal patterns
        graph_patterns = [
            "liên quan", "related", "connected", "connection",
            "relationship", "mối quan hệ", "những gì về", "everything about",
            "tell me about", "nói về", "kể về",
        ]
        
        # Triplet patterns (specific entity attributes)
        triplet_patterns = [
            "làm gì", "what does", "works as", "làm việc",
            "ở đâu", "where", "lives in", "sống ở",
            "thích gì", "likes", "yêu thích", "prefers",
            "tuổi", "age", "old",
        ]
        
        if any(p in query_lower for p in graph_patterns):
            return SearchType.GRAPH_TRAVERSAL
        elif any(p in query_lower for p in triplet_patterns):
            return SearchType.TRIPLET
        else:
            return SearchType.COMBINED  # Default to combined for best coverage
    
    async def _vector_search(
        self,
        query: str,
        entity_id: Optional[str],
        workspace_id: Optional[UUID],
        limit: int,
    ) -> List[SearchResult]:
        """Vector similarity search using existing MemoriRecall."""
        try:
            recall = await self._get_memori_recall()
            if not recall:
                return []
            
            # Use existing MemoriRecall search
            if entity_id:
                facts = await recall.search_facts(
                    query=query,
                    entity_id=entity_id,
                    limit=limit,
                )
            elif workspace_id:
                facts = await recall.search_facts_in_workspace(
                    query=query,
                    workspace_id=workspace_id,
                    limit=limit,
                )
            else:
                facts = await recall.search_facts(
                    query=query,
                    limit=limit,
                )
            
            return [
                SearchResult(
                    content=f.content,
                    score=f.score if hasattr(f, 'score') else 0.8,
                    source="vector",
                    metadata={
                        "fact_id": f.id if hasattr(f, 'id') else None,
                        "importance": f.importance if hasattr(f, 'importance') else None,
                    }
                )
                for f in facts
            ]
            
        except Exception as e:
            logger.warning(f"Vector search error: {e}")
            return []
    
    async def _triplet_search(
        self,
        query: str,
        entity_id: Optional[str],
        workspace_id: Optional[UUID],
        limit: int,
    ) -> List[SearchResult]:
        """
        Search using semantic triples (Subject-Predicate-Object).
        
        Matches query against subject, predicate, or object fields.
        """
        try:
            from app.db.models import SemanticTriple, MemoriEntity
            
            # Build query
            stmt = select(SemanticTriple)
            
            if entity_id:
                stmt = stmt.join(MemoriEntity).where(
                    MemoriEntity.external_id == entity_id
                )
            
            # Search in subject, predicate, object
            search_terms = query.lower().split()
            search_conditions = []
            
            for term in search_terms[:5]:  # Limit search terms
                if len(term) > 2:
                    search_conditions.append(
                        or_(
                            SemanticTriple.subject.ilike(f"%{term}%"),
                            SemanticTriple.predicate.ilike(f"%{term}%"),
                            SemanticTriple.object.ilike(f"%{term}%"),
                        )
                    )
            
            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))
            
            stmt = stmt.order_by(SemanticTriple.created_at.desc()).limit(limit)
            
            result = await self.session.execute(stmt)
            triples = result.scalars().all()
            
            return [
                SearchResult(
                    content=f"{t.subject} {t.predicate} {t.object}",
                    score=0.9,  # Triplet matches are high confidence
                    source="triplet",
                    metadata={
                        "subject": t.subject,
                        "predicate": t.predicate,
                        "object": t.object,
                        "triple_id": t.id if hasattr(t, 'id') else None,
                    },
                    related_entities=[t.subject, t.object],
                )
                for t in triples
            ]
            
        except ImportError:
            logger.debug("SemanticTriple model not available")
            return []
        except Exception as e:
            logger.warning(f"Triplet search error: {e}")
            return []
    
    async def _graph_traversal(
        self,
        query: str,
        entity_id: Optional[str],
        workspace_id: Optional[UUID],
        limit: int,
    ) -> List[SearchResult]:
        """
        Graph traversal search - follow relationships from entities.
        
        1. Find starting entity matching query
        2. Get all triples where entity is subject or object
        3. Follow relationships (1-hop)
        4. Collect related facts
        """
        try:
            from app.db.models import SemanticTriple, MemoriEntity, MemoriEntityFact
            
            results = []
            
            # Step 1: Find entity matching query (or use provided entity_id)
            starting_entity = entity_id
            
            if not starting_entity:
                # Try to find entity from query
                entity_query = select(MemoriEntity).where(
                    or_(
                        MemoriEntity.external_id.ilike(f"%{query}%"),
                        MemoriEntity.name.ilike(f"%{query}%") if hasattr(MemoriEntity, 'name') else False,
                    )
                ).limit(1)
                entity_result = await self.session.execute(entity_query)
                entity = entity_result.scalar_one_or_none()
                if entity:
                    starting_entity = entity.external_id
            
            if not starting_entity:
                # Fallback to vector search if no entity found
                return await self._vector_search(query, entity_id, workspace_id, limit)
            
            # Step 2: Get all triples connected to this entity
            triples_query = select(SemanticTriple).join(MemoriEntity).where(
                MemoriEntity.external_id == starting_entity
            ).limit(limit * 2)
            
            triples_result = await self.session.execute(triples_query)
            triples = triples_result.scalars().all()
            
            for t in triples:
                results.append(SearchResult(
                    content=f"{t.subject} {t.predicate} {t.object}",
                    score=0.85,
                    source="graph",
                    metadata={
                        "relationship": t.predicate,
                        "direction": "outgoing" if t.subject == starting_entity else "incoming",
                    },
                    related_entities=[t.subject, t.object],
                ))
            
            # Step 3: Get facts for the entity
            facts_query = select(MemoriEntityFact).join(MemoriEntity).where(
                MemoriEntity.external_id == starting_entity
            ).order_by(MemoriEntityFact.importance.desc()).limit(limit)
            
            facts_result = await self.session.execute(facts_query)
            facts = facts_result.scalars().all()
            
            for f in facts:
                results.append(SearchResult(
                    content=f.content,
                    score=f.importance / 10.0 if f.importance else 0.5,
                    source="graph_fact",
                    metadata={
                        "fact_id": f.id,
                        "importance": f.importance,
                    },
                    related_entities=[starting_entity],
                ))
            
            # Sort by score and limit
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:limit]
            
        except ImportError as ie:
            logger.debug(f"Graph models not available: {ie}")
            return []
        except Exception as e:
            logger.warning(f"Graph traversal error: {e}")
            return []
    
    async def _combined_search(
        self,
        query: str,
        entity_id: Optional[str],
        workspace_id: Optional[UUID],
        limit: int,
    ) -> List[SearchResult]:
        """
        Combined search using both vector and graph.
        Fuses results with score normalization.
        """
        import asyncio
        
        # Run searches in parallel
        vector_task = asyncio.create_task(
            self._vector_search(query, entity_id, workspace_id, limit)
        )
        triplet_task = asyncio.create_task(
            self._triplet_search(query, entity_id, workspace_id, limit)
        )
        
        vector_results, triplet_results = await asyncio.gather(
            vector_task, triplet_task
        )
        
        # Merge and deduplicate
        all_results = []
        seen_contents = set()
        
        for r in vector_results + triplet_results:
            content_key = r.content[:100].lower()
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                all_results.append(r)
        
        # Sort by score
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results[:limit]
    
    def format_results_for_prompt(
        self,
        results: List[SearchResult],
        max_chars: int = 2000,
    ) -> str:
        """
        Format search results for injection into LLM prompt.
        
        Args:
            results: List of SearchResult objects
            max_chars: Maximum characters in output
            
        Returns:
            Formatted string for prompt
        """
        if not results:
            return ""
        
        lines = ["[Knowledge Graph Context]"]
        total_chars = len(lines[0])
        
        for r in results:
            line = f"• {r.content}"
            if r.source == "triplet" and r.metadata:
                line = f"• [{r.metadata.get('predicate', 'related_to')}] {r.content}"
            
            if total_chars + len(line) > max_chars:
                break
            
            lines.append(line)
            total_chars += len(line) + 1
        
        return "\n".join(lines)

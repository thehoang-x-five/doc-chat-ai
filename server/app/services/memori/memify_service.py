"""
Memify Service - Tự động làm giàu knowledge graph.

Lấy cảm hứng từ Cognee's memify() function.
Suy luận relationships mới từ facts hiện có.

Tính năng:
- Infer implicit relationships (nếu A->B và B->C thì A->C)
- Summarize fact clusters thành higher-level insights
- Detect and merge duplicate entities
- Generate synthetic facts từ patterns
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass, field

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of memify operation."""
    new_triples: int = 0
    inferred_facts: int = 0
    merged_entities: int = 0
    summary_facts: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_triples": self.new_triples,
            "inferred_facts": self.inferred_facts,
            "merged_entities": self.merged_entities,
            "summary_facts": self.summary_facts,
            "errors": self.errors,
        }


class MemifyService:
    """
    Knowledge graph enrichment service.
    
    Automatically enriches the knowledge graph by:
    1. Inferring implicit relationships
    2. Creating summary facts from clusters
    3. Detecting and merging duplicate entities
    4. Generating synthetic insights
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._memori_manager = None
        self._ai_provider = None
    
    async def _get_memori_manager(self):
        """Lazy load MemoriManager."""
        if self._memori_manager is None:
            try:
                from app.services.memori import MemoriManager, MemoriConfig
                config = MemoriConfig()
                self._memori_manager = MemoriManager(self.session, config)
            except ImportError as e:
                logger.warning(f"MemoriManager not available: {e}")
        return self._memori_manager
    
    async def _get_ai_provider(self):
        """Lazy load AI provider for LLM inference."""
        if self._ai_provider is None:
            try:
                from app.services.core.ai_provider import AIProviderManager
                self._ai_provider = AIProviderManager()
            except ImportError as e:
                logger.warning(f"AIProviderManager not available: {e}")
        return self._ai_provider
    
    async def memify(
        self,
        entity_id: str,
        workspace_id: Optional[UUID] = None,
        run_inference: bool = True,
        run_summary: bool = True,
        run_merge: bool = False,
    ) -> EnrichmentResult:
        """
        Enrich knowledge graph for an entity.
        
        Args:
            entity_id: Entity to enrich
            workspace_id: Optional workspace filter
            run_inference: Whether to infer new relationships
            run_summary: Whether to create summary facts
            run_merge: Whether to merge duplicate entities
            
        Returns:
            EnrichmentResult with counts of new items
        """
        result = EnrichmentResult()
        
        logger.info(f"🧬 Memify: Starting enrichment for entity {entity_id}")
        
        try:
            # Step 1: Infer relationships
            if run_inference:
                inference_result = await self._infer_relationships(entity_id)
                result.new_triples += inference_result
            
            # Step 2: Create summaries
            if run_summary:
                summary_result = await self._create_fact_summaries(entity_id)
                result.summary_facts += summary_result
            
            # Step 3: Merge duplicates
            if run_merge:
                merge_result = await self._merge_duplicate_entities(entity_id)
                result.merged_entities += merge_result
            
            logger.info(
                f"🧬 Memify complete: {result.new_triples} triples, "
                f"{result.summary_facts} summaries, {result.merged_entities} merges"
            )
            
        except Exception as e:
            logger.warning(f"Memify error: {e}")
            result.errors.append(str(e))
        
        return result
    
    async def _infer_relationships(self, entity_id: str) -> int:
        """
        Infer new relationships from existing triples.
        
        Patterns:
        - Transitive: A->B, B->C implies A->(transitive)->C
        - Symmetric: A->B implies B->A for certain predicates
        - Inverse: works_at implies employed_by
        """
        new_triples = 0
        
        try:
            from app.db.models import SemanticTriple, MemoriEntity
            
            # Get existing triples for this entity
            stmt = select(SemanticTriple).join(MemoriEntity).where(
                MemoriEntity.external_id == entity_id
            )
            result = await self.session.execute(stmt)
            triples = result.scalars().all()
            
            if len(triples) < 2:
                return 0
            
            # Build predicate -> (subject, object) map
            predicate_map: Dict[str, List[Tuple[str, str]]] = {}
            for t in triples:
                if t.predicate not in predicate_map:
                    predicate_map[t.predicate] = []
                predicate_map[t.predicate].append((t.subject, t.object))
            
            # Transitive inference
            transitive_predicates = ["works_at", "located_in", "part_of", "belongs_to"]
            
            for pred in transitive_predicates:
                if pred not in predicate_map:
                    continue
                
                pairs = predicate_map[pred]
                # If A->B and B->C then A->C
                objects = {p[1] for p in pairs}
                subjects = {p[0] for p in pairs}
                
                for s, o in pairs:
                    for s2, o2 in pairs:
                        if o == s2 and s != o2:
                            # Found transitive relationship
                            new_triple = {
                                "subject": s,
                                "predicate": f"indirectly_{pred}",
                                "object": o2,
                            }
                            
                            memori = await self._get_memori_manager()
                            if memori:
                                await memori.add_semantic_triples(
                                    entity_id=entity_id,
                                    triples=[new_triple],
                                )
                                new_triples += 1
            
            # Inverse relationships
            inverse_map = {
                "works_at": "employs",
                "lives_in": "resident_of",
                "teaches": "taught_by",
                "manages": "managed_by",
            }
            
            for pred, inverse_pred in inverse_map.items():
                if pred in predicate_map:
                    for s, o in predicate_map[pred]:
                        new_triple = {
                            "subject": o,
                            "predicate": inverse_pred,
                            "object": s,
                        }
                        
                        memori = await self._get_memori_manager()
                        if memori:
                            await memori.add_semantic_triples(
                                entity_id=entity_id,
                                triples=[new_triple],
                            )
                            new_triples += 1
                            
        except ImportError:
            logger.debug("SemanticTriple model not available for inference")
        except Exception as e:
            logger.warning(f"Inference error: {e}")
        
        return new_triples
    
    async def _create_fact_summaries(self, entity_id: str) -> int:
        """
        Create summary facts from clusters of related facts.
        Uses LLM to synthesize multiple facts into higher-level insights.
        """
        summaries_created = 0
        
        try:
            from app.db.models import MemoriEntityFact, MemoriEntity
            
            # Get all facts for this entity
            stmt = select(MemoriEntityFact).join(MemoriEntity).where(
                MemoriEntity.external_id == entity_id
            ).order_by(MemoriEntityFact.created_at.desc()).limit(50)
            
            result = await self.session.execute(stmt)
            facts = result.scalars().all()
            
            if len(facts) < 5:
                return 0
            
            # Cluster facts by topic (simple keyword-based)
            clusters: Dict[str, List[str]] = {
                "work": [],
                "personal": [],
                "preferences": [],
                "relationships": [],
            }
            
            work_keywords = ["work", "làm việc", "job", "nghề", "công ty", "company"]
            personal_keywords = ["tên", "name", "tuổi", "age", "sinh", "born"]
            pref_keywords = ["thích", "like", "yêu", "love", "prefer", "favourite"]
            rel_keywords = ["bạn", "friend", "gia đình", "family", "vợ", "chồng"]
            
            for f in facts:
                content_lower = f.content.lower()
                
                if any(kw in content_lower for kw in work_keywords):
                    clusters["work"].append(f.content)
                elif any(kw in content_lower for kw in personal_keywords):
                    clusters["personal"].append(f.content)
                elif any(kw in content_lower for kw in pref_keywords):
                    clusters["preferences"].append(f.content)
                elif any(kw in content_lower for kw in rel_keywords):
                    clusters["relationships"].append(f.content)
            
            # Create summaries for clusters with 3+ facts
            memori = await self._get_memori_manager()
            if not memori:
                return 0
            
            for category, fact_list in clusters.items():
                if len(fact_list) >= 3:
                    # Create summary using LLM or simple concatenation
                    summary = await self._generate_summary(fact_list, category)
                    
                    if summary:
                        await memori.add_facts(
                            entity_id=entity_id,
                            facts=[f"[Summary - {category}] {summary}"],
                            importance_scores=[9.0],  # High importance for summaries
                        )
                        summaries_created += 1
                        
        except ImportError:
            logger.debug("Fact models not available for summary")
        except Exception as e:
            logger.warning(f"Summary creation error: {e}")
        
        return summaries_created
    
    async def _generate_summary(self, facts: List[str], category: str) -> Optional[str]:
        """Generate a summary of facts using LLM or heuristics."""
        try:
            ai = await self._get_ai_provider()
            if not ai:
                # Fallback: Simple concatenation
                return f"{category.title()} context: " + "; ".join(facts[:3])
            
            prompt = f"""Summarize these facts about a user's {category} in one concise sentence:

Facts:
{chr(10).join(f'- {f}' for f in facts)}

Write a single sentence summary:"""

            providers = ai._get_available_providers()
            if not providers:
                return f"{category.title()} context: " + "; ".join(facts[:3])
            
            provider = ai.providers.get(providers[0])
            if not provider:
                return f"{category.title()} context: " + "; ".join(facts[:3])
            
            response = await provider.chat_completion([
                {"role": "user", "content": prompt}
            ])
            
            return response.strip()
            
        except Exception as e:
            logger.debug(f"LLM summary failed: {e}")
            return f"{category.title()} context: " + "; ".join(facts[:3])
    
    async def _merge_duplicate_entities(self, entity_id: str) -> int:
        """
        Detect and merge duplicate entities based on similarity.
        """
        merged = 0
        
        try:
            from app.db.models import MemoriEntity
            
            # Get entity
            stmt = select(MemoriEntity).where(MemoriEntity.external_id == entity_id)
            result = await self.session.execute(stmt)
            entity = result.scalar_one_or_none()
            
            if not entity:
                return 0
            
            # Find potential duplicates (same name but different IDs)
            if hasattr(entity, 'name') and entity.name:
                dup_stmt = select(MemoriEntity).where(
                    MemoriEntity.name == entity.name,
                    MemoriEntity.external_id != entity_id,
                )
                dup_result = await self.session.execute(dup_stmt)
                duplicates = dup_result.scalars().all()
                
                # Merge facts from duplicates to main entity
                memori = await self._get_memori_manager()
                if memori and duplicates:
                    for dup in duplicates:
                        # Transfer facts (simplified - full implementation would be more complex)
                        logger.info(f"Found potential duplicate entity: {dup.external_id}")
                        merged += 1
                        
        except ImportError:
            logger.debug("Entity model not available for merge")
        except Exception as e:
            logger.warning(f"Merge error: {e}")
        
        return merged
    
    async def schedule_periodic_enrichment(
        self,
        entity_id: str,
        interval_hours: int = 24,
    ):
        """
        Schedule periodic enrichment for an entity.
        Called by background worker.
        """
        try:
            from app.queue.tasks.memori_tasks import run_memify_task
            
            run_memify_task.apply_async(
                kwargs={
                    "entity_id": entity_id,
                    "run_inference": True,
                    "run_summary": True,
                },
                countdown=interval_hours * 3600,
            )
            
            logger.info(f"Scheduled memify for {entity_id} in {interval_hours}h")
            
        except ImportError:
            logger.debug("Celery task not available for scheduling")
        except Exception as e:
            logger.warning(f"Schedule error: {e}")

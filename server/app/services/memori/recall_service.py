"""
Hệ thống truy hồi dữ liệu Memory (Memory Recall System).
Sao chép từ project Memori: memori/memory/recall.py

Tính năng:
- Tìm kiếm facts dựa trên query embedding
- Độ tương đồng ngữ nghĩa (Semantic similarity) với FAISS
- Reranking theo từ vựng (Lexical reranking) để tăng độ chính xác
- Lọc theo ngưỡng độ liên quan (Relevance threshold)
- Giai đoạn 3 (Phase 3): Suy giảm độ quan trọng theo thời gian (Importance decay)
- Giai đoạn 3 (Phase 3): Tăng cường theo ngữ cảnh (Contextual boosting)
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memori.models import MemoriConfig, RecalledFact
from app.services.memori.extraction import embed_texts_sync, format_embedding_for_db
from app.services.memori.search import search_entity_facts

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.05

# Phase 3: Tham số cho decay và boosting
IMPORTANCE_DECAY_DAYS = 30  # Facts mất dần độ quan trọng sau 30 ngày
IMPORTANCE_DECAY_RATE = 0.5  # Giảm 50% sau mỗi chu kỳ IMPORTANCE_DECAY_DAYS
CONTEXTUAL_BOOST_FACTOR = 1.5  # Tăng 50% cho facts phù hợp ngữ cảnh
RECENCY_BOOST_DAYS = 7  # Ưu tiên facts trong 7 ngày gần nhất
RECENCY_BOOST_FACTOR = 1.2  # Tăng 20% cho facts mới


class MemoriRecall:
    """
    Hệ thống truy hồi bộ nhớ (Memory Recall System).
    Sao chép từ Memori: Tìm kiếm facts đã lưu trữ sử dụng tương đồng ngữ nghĩa.
    """
    
    def __init__(self, session: AsyncSession, config: Optional[MemoriConfig] = None):
        """
        Khởi tạo hệ thống recall.
        
        Args:
            session: Database session
            config: Cấu hình Memori
        """
        self.session = session
        self.config = config or MemoriConfig()
    
    async def search_facts(
        self,
        query: str,
        entity_id: Optional[str] = None,
        limit: Optional[int] = None,
        min_similarity: Optional[float] = None,
        context: Optional[str] = None,  # Phase 3: Context để boosting
        enable_decay: bool = True,  # Phase 3: Bật importance decay
        enable_boosting: bool = True,  # Phase 3: Bật contextual boosting
    ) -> List[RecalledFact]:
        """
        Tìm kiếm facts liên quan đến một thực thể (entity).
        Sao chép từ Memori: Hàm recall chính.
        
        Cải tiến giai đoạn 3 (Phase 3 Enhancements):
        - Importance decay: Facts giảm độ quan trọng theo thời gian
        - Contextual boosting: Tăng điểm cho facts liên quan ngữ cảnh hiện tại
        - Recency boosting: Tăng điểm cho facts vừa truy cập/tạo gần đây
        
        Args:
            query: Câu truy vấn
            entity_id: ID thực thể bên ngoài (ví dụ: user_id)
            limit: Số lượng facts tối đa trả về
            min_similarity: Ngưỡng tương đồng tối thiểu
            context: Ngữ cảnh tùy chọn để boosting (ví dụ: chủ đề hội thoại hiện tại)
            enable_decay: Áp dụng suy giảm theo thời gian
            enable_boosting: Áp dụng boosting theo ngữ cảnh và thời gian
            
        Returns:
            Danh sách RecalledFact kèm điểm tương đồng
        """
        if not query or not query.strip():
            logger.debug("Recall bị hủy - query rỗng")
            return []
        
        entity_id = entity_id or self.config.entity_id
        if not entity_id:
            logger.debug("Recall bị hủy - thiếu entity_id")
            return []
        
        limit = limit or self.config.recall_facts_limit
        min_similarity = min_similarity or self.config.recall_relevance_threshold
        
        logger.debug(
            "Bắt đầu Recall - query: %s (%d chars), entity: %s, limit: %d, decay: %s, boosting: %s",
            query[:50] + "..." if len(query) > 50 else query,
            len(query),
            entity_id,
            limit,
            enable_decay,
            enable_boosting,
        )
        
        # Lấy ID nội bộ của entity
        internal_entity_id = await self._get_entity_id(entity_id)
        if internal_entity_id is None:
            logger.debug("Recall bị hủy - không tìm thấy entity: %s", entity_id)
            return []
        
        # Tạo embedding cho query
        logger.debug("Đang tạo query embedding")
        embeddings = embed_texts_sync(query)
        if not embeddings:
            logger.warning("Không thể tạo query embedding")
            return []
        query_embedding = embeddings[0]
        
        # Phase 3: Lấy facts kèm metadata cho decay/boosting
        facts_data = await self._get_entity_facts_with_metadata(
            internal_entity_id,
            limit=self.config.recall_embeddings_limit,
        )
        
        if not facts_data:
            logger.debug("Không tìm thấy facts nào cho entity: %s", entity_id)
            return []
        
        logger.debug("Đã lấy %d facts từ database", len(facts_data))
        
        # Tìm kiếm bằng FAISS + lexical reranking
        results = search_entity_facts(
            facts_data=facts_data,
            query_embedding=query_embedding,
            limit=limit * 2,  # Lấy nhiều hơn để rerank
            query_text=query,
        )
        
        # Phase 3: Áp dụng importance decay và boosting
        if enable_decay or enable_boosting:
            results = self._apply_decay_and_boosting(
                results,
                facts_data,
                context=context,
                enable_decay=enable_decay,
                enable_boosting=enable_boosting,
            )
            
            # Sắp xếp lại theo adjusted rank_score
            results = sorted(results, key=lambda x: x.get("rank_score", 0), reverse=True)
            
            # Cắt limit sau khi rerank
            results = results[:limit]
        
        # Lọc theo độ tương đồng tối thiểu
        filtered = [
            r for r in results
            if r.get("similarity", 0) >= min_similarity
        ]
        
        logger.debug(
            "Recall hoàn tất - tìm thấy %d facts (đã lọc từ %d)",
            len(filtered),
            len(results),
        )
        
        # Chuyển đổi sang RecalledFact objects
        return [
            RecalledFact(
                id=r["id"],
                content=r["content"],
                similarity=r.get("similarity", 0.0),
                lexical_score=r.get("lexical_score", 0.0),
                rank_score=r.get("rank_score", 0.0),
            )
            for r in filtered
        ]
    
    async def _get_entity_id(self, external_id: str) -> Optional[int]:
        """Lấy internal entity ID từ external ID."""
        from app.db.models import MemoriEntity
        
        try:
            result = await self.session.execute(
                select(MemoriEntity.id).where(
                    MemoriEntity.external_id == external_id
                )
            )
            row = result.scalar_one_or_none()
            return row
        except Exception as e:
            logger.warning(f"Lỗi lấy entity ID: {e}")
            return None
    
    async def _get_entity_facts(
        self,
        entity_id: int,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Lấy facts kèm embeddings của một entity."""
        from app.db.models import MemoriEntityFact
        
        try:
            result = await self.session.execute(
                select(
                    MemoriEntityFact.id,
                    MemoriEntityFact.content,
                    MemoriEntityFact.content_embedding,
                )
                .where(MemoriEntityFact.entity_id == entity_id)
                .order_by(MemoriEntityFact.importance_score.desc())
                .limit(limit)
            )
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "content": row.content,
                    "content_embedding": row.content_embedding,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Lỗi lấy entity facts: {e}")
            return []
    
    async def _get_entity_facts_with_metadata(
        self,
        entity_id: int,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Lấy facts kèm embeddings VÀ metadata cho decay/boosting.
        Phase 3: Bao gồm importance_score, created_at, last_accessed_at.
        """
        from app.db.models import MemoriEntityFact
        
        try:
            result = await self.session.execute(
                select(
                    MemoriEntityFact.id,
                    MemoriEntityFact.content,
                    MemoriEntityFact.content_embedding,
                    MemoriEntityFact.importance_score,
                    MemoriEntityFact.created_at,
                    MemoriEntityFact.last_accessed_at,
                )
                .where(MemoriEntityFact.entity_id == entity_id)
                .order_by(MemoriEntityFact.importance_score.desc())
                .limit(limit)
            )
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "content": row.content,
                    "content_embedding": row.content_embedding,
                    "importance_score": row.importance_score or 1.0,
                    "created_at": row.created_at,
                    "last_accessed_at": row.last_accessed_at,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Lỗi lấy entity facts kèm metadata: {e}")
            return []
    
    def _apply_decay_and_boosting(
        self,
        results: List[Dict[str, Any]],
        facts_data: List[Dict[str, Any]],
        context: Optional[str] = None,
        enable_decay: bool = True,
        enable_boosting: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Áp dụng importance decay và contextual boosting cho kết quả tìm kiếm.
        Phase 3: Điều chỉnh rank_score dựa trên thời gian và ngữ cảnh.
        
        Args:
            results: Kết quả tìm kiếm từ FAISS
            facts_data: Dữ liệu facts gốc kèm metadata
            context: Ngữ cảnh tùy chọn để boosting
            enable_decay: Áp dụng suy giảm theo thời gian
            enable_boosting: Áp dụng boosting theo ngữ cảnh và thời gian
            
        Returns:
            Danh sách kết quả với rank_score đã điều chỉnh
        """
        if not results:
            return results
        
        # Xây dựng metadata map
        metadata_map = {f["id"]: f for f in facts_data}
        
        now = datetime.now(timezone.utc)  # Dùng timezone-aware datetime
        
        for result in results:
            fact_id = result["id"]
            metadata = metadata_map.get(fact_id)
            
            if not metadata:
                continue
            
            # Lấy điểm cơ sở
            similarity = result.get("similarity", 0.0)
            lexical_score = result.get("lexical_score", 0.0)
            base_rank_score = result.get("rank_score", similarity)
            
            # Lấy metadata
            importance = metadata.get("importance_score", 1.0)
            created_at = metadata.get("created_at")
            last_accessed_at = metadata.get("last_accessed_at")
            content = metadata.get("content", "")
            
            # Khởi tạo điểm điều chỉnh
            adjusted_score = base_rank_score
            
            # Phase 3.1: Importance Decay (Suy giảm theo thời gian)
            if enable_decay and created_at:
                age_days = (now - created_at).days
                if age_days > IMPORTANCE_DECAY_DAYS:
                    # Áp dụng suy giảm theo hàm mũ
                    decay_factor = IMPORTANCE_DECAY_RATE ** (age_days / IMPORTANCE_DECAY_DAYS)
                    adjusted_score *= decay_factor
                    logger.debug(
                        f"Applied decay to fact {fact_id}: age={age_days}d, factor={decay_factor:.3f}"
                    )
            
            # Phase 3.2: Recency Boost (Ưu tiên mới nhất)
            if enable_boosting and last_accessed_at:
                days_since_access = (now - last_accessed_at).days
                if days_since_access <= RECENCY_BOOST_DAYS:
                    adjusted_score *= RECENCY_BOOST_FACTOR
                    logger.debug(
                        f"Applied recency boost to fact {fact_id}: {days_since_access}d ago"
                    )
            
            # Phase 3.3: Contextual Boost (Ưu tiên theo ngữ cảnh)
            if enable_boosting and context and content:
                # So khớp từ khóa đơn giản để kiểm tra độ liên quan ngữ cảnh
                context_lower = context.lower()
                content_lower = content.lower()
                
                # Check trùng lặp tokens
                context_tokens = set(context_lower.split())
                content_tokens = set(content_lower.split())
                overlap = len(context_tokens & content_tokens)
                
                if overlap > 0:
                    # Boost dựa trên tỷ lệ trùng lặp
                    overlap_ratio = overlap / len(context_tokens) if context_tokens else 0
                    boost = 1.0 + (CONTEXTUAL_BOOST_FACTOR - 1.0) * overlap_ratio
                    adjusted_score *= boost
                    logger.debug(
                        f"Applied contextual boost to fact {fact_id}: "
                        f"overlap={overlap}, boost={boost:.3f}"
                    )
            
            # Phase 3.4: Tích hợp Importance Score
            # Nhân với importance đã chuẩn hóa (khoảng 0.1 đến 1.0)
            normalized_importance = min(1.0, importance / 10.0)
            adjusted_score *= (0.5 + 0.5 * normalized_importance)  # Hệ số nhân 0.5x đến 1.0x
            
            # Cập nhật kết quả
            result["rank_score"] = adjusted_score
            result["original_rank_score"] = base_rank_score
            result["importance_score"] = importance
        
        return results
    
    async def search_facts_for_conversation(
        self,
        query: str,
        conversation_id: UUID,
        limit: Optional[int] = None,
    ) -> List[RecalledFact]:
        """
        Tìm kiếm facts liên quan đến một cuộc hội thoại.
        Sử dụng entity liên kết với hội thoại nếu có.
        
        Args:
            query: Câu truy vấn
            conversation_id: UUID cuộc hội thoại
            limit: Số lượng tối đa
            
        Returns:
            Danh sách facts liên quan
        """
        # Cố gắng tìm entity liên kết với conversation
        entity_id = await self._get_entity_for_conversation(conversation_id)
        if entity_id:
            return await self.search_facts(query, entity_id=entity_id, limit=limit)
        
        # Fallback: tìm kiếm trên toàn bộ workspace
        if self.config.workspace_id:
            return await self.search_facts_in_workspace(
                query,
                workspace_id=self.config.workspace_id,
                limit=limit,
            )
        
        return []
    
    async def _get_entity_for_conversation(self, conversation_id: UUID) -> Optional[str]:
        """Lấy entity ID liên kết với một conversation."""
        from app.db.models import Conversation, MemoriEntity
        
        try:
            # Lấy người tạo cuộc hội thoại
            result = await self.session.execute(
                select(Conversation.created_by).where(
                    Conversation.id == conversation_id
                )
            )
            user_id = result.scalar_one_or_none()
            
            if user_id:
                # Kiểm tra nếu entity tồn tại cho user này
                entity_result = await self.session.execute(
                    select(MemoriEntity.external_id).where(
                        MemoriEntity.external_id == str(user_id)
                    )
                )
                entity_id = entity_result.scalar_one_or_none()
                return entity_id
            
            return None
        except Exception as e:
            logger.warning(f"Lỗi lấy entity cho conversation: {e}")
            return None
    
    async def search_facts_in_workspace(
        self,
        query: str,
        workspace_id: UUID,
        limit: Optional[int] = None,
    ) -> List[RecalledFact]:
        """
        Tìm kiếm facts trên tất cả entities trong một workspace.
        
        Args:
            query: Câu truy vấn
            workspace_id: UUID workspace
            limit: Số lượng tối đa
            
        Returns:
            Danh sách facts liên quan từ tất cả entities
        """
        from app.db.models import MemoriEntity, MemoriEntityFact
        
        limit = limit or self.config.recall_facts_limit
        
        try:
            # Tạo query embedding
            embeddings = embed_texts_sync(query)
            if not embeddings:
                return []
            query_embedding = embeddings[0]
            
            # Lấy tất cả facts trong workspace
            result = await self.session.execute(
                select(
                    MemoriEntityFact.id,
                    MemoriEntityFact.content,
                    MemoriEntityFact.content_embedding,
                )
                .join(MemoriEntity, MemoriEntityFact.entity_id == MemoriEntity.id)
                .where(MemoriEntity.workspace_id == workspace_id)
                .order_by(MemoriEntityFact.importance_score.desc())
                .limit(self.config.recall_embeddings_limit)
            )
            rows = result.fetchall()
            
            if not rows:
                return []
            
            facts_data = [
                {
                    "id": row.id,
                    "content": row.content,
                    "content_embedding": row.content_embedding,
                }
                for row in rows
            ]
            
            # Search
            results = search_entity_facts(
                facts_data=facts_data,
                query_embedding=query_embedding,
                limit=limit,
                query_text=query,
            )
            
            # Filter và convert
            filtered = [
                r for r in results
                if r.get("similarity", 0) >= self.config.recall_relevance_threshold
            ]
            
            return [
                RecalledFact(
                    id=r["id"],
                    content=r["content"],
                    similarity=r.get("similarity", 0.0),
                    lexical_score=r.get("lexical_score", 0.0),
                    rank_score=r.get("rank_score", 0.0),
                )
                for r in filtered
            ]
        except Exception as e:
            logger.warning(f"Lỗi tìm kiếm facts trong workspace: {e}")
            return []
    
    def format_facts_for_prompt(self, facts: List[RecalledFact]) -> str:
        """
        Định dạng facts đã recall để tiêm vào LLM prompt.
        Sao chép từ Memori: Tạo khối context cho prompt.
        
        Args:
            facts: Danh sách facts đã recall
            
        Returns:
            Chuỗi định dạng để tiêm vào prompt
        """
        if not facts:
            return ""
        
        fact_lines = [f"- {fact.content}" for fact in facts]
        
        return (
            "\n\n<memori_context>\n"
            "Relevant context about the user/topic:\n"
            + "\n".join(fact_lines)
            + "\n</memori_context>"
        )

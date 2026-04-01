"""
Memori Manager - Trình quản lý chính cho các hoạt động bộ nhớ.
Sao chép từ project Memori với các sửa đổi cho RAG-Anything.

Tính năng:
- Quản lý Thực thể/Fact (Entity/Fact management)
- Đồ thị tri thức (Knowledge graph - semantic triples)
- Quản lý phiên (Session management) với timeout
- Pipeline Augmentation bất đồng bộ
- Tích hợp với MemoryManager hiện có
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memori.models import (
    MemoriConfig,
    AugmentationInput,
    Entity,
    Memories,
    SemanticTriple,
    RecalledFact,
)
from app.services.memori.extraction import embed_texts_sync, format_embedding_for_db
from app.services.memori.recall_service import MemoriRecall

logger = logging.getLogger(__name__)


class MemoriManager:
    """
    Memori Manager chính.
    Điều phối tất cả các hoạt động bộ nhớ bao gồm:
    - Quản lý Entity và Fact
    - Các hoạt động Knowledge graph
    - Quản lý Session
    - Truy hồi bộ nhớ (Memory recall)
    - Augmentation (trính xuất facts từ hội thoại)
    """
    
    def __init__(
        self,
        session: AsyncSession,
        config: Optional[MemoriConfig] = None,
    ):
        """
        Khởi tạo Memori Manager.
        
        Args:
            session: Database session
            config: Cấu hình Memori
        """
        self.session = session
        self.config = config or MemoriConfig()
        self.recall = MemoriRecall(session, config)
    
    # =========================================================================
    # QUẢN LÝ ENTITY (ENTITY MANAGEMENT)
    # =========================================================================
    
    async def get_or_create_entity(
        self,
        external_id: str,
        workspace_id: Optional[UUID] = None,
    ) -> int:
        """
        Lấy hoặc tạo mới một entity theo external ID.
        Sao chép từ Memori: Đảm bảo entity tồn tại trước khi lưu facts.
        
        Args:
            external_id: Định danh bên ngoài (ví dụ: user_id)
            workspace_id: Tùy chọn liên kết workspace
            
        Returns:
            Internal entity ID
        """
        from app.db.models import MemoriEntity
        
        workspace_id = workspace_id or self.config.workspace_id
        
        # Cố gắng tìm entity hiện có
        result = await self.session.execute(
            select(MemoriEntity).where(
                MemoriEntity.external_id == external_id
            )
        )
        entity = result.scalar_one_or_none()
        
        if entity:
            return entity.id
        
        # Tạo mới
        entity = MemoriEntity(
            external_id=external_id,
            workspace_id=workspace_id,
        )
        self.session.add(entity)
        await self.session.flush()
        
        logger.info(f"Đã tạo entity mới: {external_id} (id={entity.id})")
        return entity.id
    
    # =========================================================================
    # QUẢN LÝ FACT (FACT MANAGEMENT)
    # =========================================================================
    
    async def add_facts(
        self,
        entity_id: str,
        facts: List[str],
        conversation_id: Optional[UUID] = None,
        importance_score: float = 1.0,
        importance_scores: Optional[List[float]] = None,
        extract_triples: bool = True,
    ) -> List[int]:
        """
        Thêm facts về một entity cùng với embeddings.
        Sao chép từ Memori: Lưu trữ facts với vector embeddings để recall.
        
        Args:
            entity_id: External entity ID
            facts: Danh sách các chuỗi fact
            conversation_id: Nguồn hội thoại
            importance_score: Trọng số importance mặc định (nếu importance_scores không được cung cấp)
            importance_scores: Điểm importance riêng cho từng fact (tùy chọn)
            extract_triples: Có trích xuất semantic triples từ facts hay không (mặc định: True)
            
        Returns:
            Danh sách ID của các facts đã tạo
        """
        from app.db.models import MemoriEntityFact
        
        if not facts:
            return []
        
        # Sử dụng scores riêng nếu có, nếu không dùng mặc định
        if importance_scores is None:
            importance_scores = [importance_score] * len(facts)
        elif len(importance_scores) != len(facts):
            logger.warning(
                f"Số lượng importance scores không khớp: {len(importance_scores)} vs {len(facts)}, "
                f"sử dụng điểm mặc định"
            )
            importance_scores = [importance_score] * len(facts)
        
        # Lấy internal entity ID
        internal_id = await self.get_or_create_entity(entity_id)
        
        # Tạo embeddings cho tất cả facts
        embeddings = embed_texts_sync(facts)
        if len(embeddings) != len(facts):
            logger.warning(f"Số lượng embedding không khớp: {len(embeddings)} vs {len(facts)}")
            # Pad thêm embedding rỗng nếu cần
            while len(embeddings) < len(facts):
                embeddings.append([0.0] * 768)
        
        created_ids = []
        new_facts = []
        for fact, embedding, importance in zip(facts, embeddings, importance_scores):
            # Kiểm tra trùng lặp
            existing = await self.session.execute(
                select(MemoriEntityFact.id).where(
                    and_(
                        MemoriEntityFact.entity_id == internal_id,
                        MemoriEntityFact.content == fact,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            # Tạo fact mới
            fact_record = MemoriEntityFact(
                entity_id=internal_id,
                content=fact,
                content_embedding=format_embedding_for_db(embedding),
                conversation_id=conversation_id,
                importance_score=importance,  # Dùng importance riêng
            )
            self.session.add(fact_record)
            await self.session.flush()
            created_ids.append(fact_record.id)
            new_facts.append(fact)
        
        if created_ids:
            logger.info(
                f"Đã thêm {len(created_ids)} facts cho entity {entity_id} "
                f"(avg importance: {sum(importance_scores) / len(importance_scores):.2f})"
            )
            
            # Trích xuất triples từ facts mới
            if extract_triples and new_facts:
                try:
                    triples = await self._extract_triples_from_facts(new_facts, entity_id)
                    if triples:
                        await self.add_semantic_triples(
                            entity_id=entity_id,
                            triples=triples,
                            conversation_id=conversation_id,
                        )
                        logger.info(f"Đã trích xuất {len(triples)} triples từ {len(new_facts)} facts")
                except Exception as e:
                    logger.warning(f"Lỗi trích xuất triples từ facts: {e}")
        
        return created_ids
    
    async def update_fact_importance(
        self,
        fact_id: int,
        importance_delta: float = 0.1,
    ) -> None:
        """
        Cập nhật điểm importance của fact (ví dụ: khi được recall).
        Importance cao hơn = khả năng được recall cao hơn.
        """
        from app.db.models import MemoriEntityFact
        
        result = await self.session.execute(
            select(MemoriEntityFact).where(MemoriEntityFact.id == fact_id)
        )
        fact = result.scalar_one_or_none()
        if fact:
            fact.importance_score = min(10.0, fact.importance_score + importance_delta)
            fact.last_accessed_at = datetime.utcnow()
    
    # =========================================================================
    # KNOWLEDGE GRAPH (SEMANTIC TRIPLES)
    # =========================================================================
    
    async def add_semantic_triples(
        self,
        entity_id: str,
        triples: List[SemanticTriple],
        conversation_id: Optional[UUID] = None,
    ) -> List[int]:
        """
        Thêm semantic triples vào knowledge graph với hỗ trợ thời gian và phát hiện mâu thuẫn.
        
        Tính năng lấy cảm hứng từ Graphiti:
        - Lưu valid_at/invalid_at cho mô hình bi-temporal
        - Phát hiện mâu thuẫn với các triples hiện có
        - Chính sách 'Latest wins' (Mới nhất thắng): triples bị mâu thuẫn sẽ có timestamp expired_at
        
        Args:
            entity_id: External entity ID
            triples: Danh sách SemanticTriple objects
            conversation_id: Nguồn hội thoại
            
        Returns:
            Danh sách ID của các triple đã tạo
        """
        from app.db.models import MemoriKnowledgeGraph
        from app.services.memori.temporal_operations import (
            get_edge_contradictions,
            invalidate_contradicted_edges,
        )
        from app.services.core.rag import RAGService
        
        if not triples:
            return []
        
        internal_id = await self.get_or_create_entity(entity_id)
        
        # Lấy các triples đang active để phát hiện mâu thuẫn
        existing_result = await self.session.execute(
            select(MemoriKnowledgeGraph).where(
                and_(
                    MemoriKnowledgeGraph.entity_id == internal_id,
                    MemoriKnowledgeGraph.expired_at.is_(None),  # Chỉ lấy active triples
                )
            )
        )
        existing_db_triples = existing_result.scalars().all()
        
        # Chuyển đổi sang SemanticTriple để phát hiện mâu thuẫn
        existing_triples = [
            SemanticTriple(
                subject_name=t.subject_name,
                subject_type=t.subject_type,
                predicate=t.predicate,
                object_name=t.object_name,
                object_type=t.object_type,
            )
            for t in existing_db_triples
        ]
        
        created_ids = []
        rag_service = None
        
        for triple in triples:
            if not all([triple.subject_name, triple.predicate, triple.object_name]):
                continue
            
            # Kiểm tra trùng lặp (triple giống hệt đã tồn tại và chưa hết hạn)
            existing = await self.session.execute(
                select(MemoriKnowledgeGraph.id).where(
                    and_(
                        MemoriKnowledgeGraph.entity_id == internal_id,
                        MemoriKnowledgeGraph.subject_name == triple.subject_name,
                        MemoriKnowledgeGraph.predicate == triple.predicate,
                        MemoriKnowledgeGraph.object_name == triple.object_name,
                        MemoriKnowledgeGraph.expired_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            # Phát hiện mâu thuẫn (chỉ cho triples không có invalid_at, tức là hiện đang đúng)
            if not triple.invalid_at and existing_triples:
                try:
                    if rag_service is None:
                        rag_service = await RAGService.get_instance(self.session)
                    
                    contradicted = await get_edge_contradictions(
                        rag_service, triple, existing_triples
                    )
                    
                    if contradicted:
                        # "Latest wins" - vô hiệu hóa các cạnh bị mâu thuẫn
                        await invalidate_contradicted_edges(
                            self.session, contradicted, datetime.utcnow()
                        )
                        logger.info(f"Đã vô hiệu hóa {len(contradicted)} triples bị mâu thuẫn")
                except Exception as e:
                    logger.warning(f"Phát hiện mâu thuẫn thất bại: {e}")
            
            # Tạo triple mới với các trường thời gian
            record = MemoriKnowledgeGraph(
                entity_id=internal_id,
                subject_name=triple.subject_name,
                subject_type=triple.subject_type,
                predicate=triple.predicate,
                object_name=triple.object_name,
                object_type=triple.object_type,
                conversation_id=conversation_id,
                confidence=triple.confidence if hasattr(triple, 'confidence') else 1.0,
                valid_at=triple.valid_at if hasattr(triple, 'valid_at') else None,
                invalid_at=triple.invalid_at if hasattr(triple, 'invalid_at') else None,
            )
            self.session.add(record)
            await self.session.flush()
            created_ids.append(record.id)
        
        if created_ids:
            logger.info(f"Đã thêm {len(created_ids)} triples cho entity {entity_id}")
        
        return created_ids

    
    async def get_knowledge_graph(
        self,
        entity_id: str,
        limit: int = 100,
        include_expired: bool = False,
    ) -> List[SemanticTriple]:
        """Lấy knowledge graph triples cho một entity.
        
        Args:
            entity_id: External entity ID
            limit: Số lượng triples tối đa trả về
            include_expired: Nếu True, bao gồm cả triples đã hết hạn; ngược lại chỉ lấy active ones
        """
        from app.db.models import MemoriEntity, MemoriKnowledgeGraph
        
        # Lấy internal ID
        result = await self.session.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        if not internal_id:
            return []
        
        # Build query - lọc triples hết hạn theo mặc định
        query = select(MemoriKnowledgeGraph).where(
            MemoriKnowledgeGraph.entity_id == internal_id
        )
        
        if not include_expired:
            query = query.where(MemoriKnowledgeGraph.expired_at.is_(None))
        
        query = query.order_by(MemoriKnowledgeGraph.created_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        rows = result.scalars().all()
        
        return [
            SemanticTriple(
                subject_name=r.subject_name,
                subject_type=r.subject_type,
                predicate=r.predicate,
                object_name=r.object_name,
                object_type=r.object_type,
                valid_at=r.valid_at,
                invalid_at=r.invalid_at,
                confidence=r.confidence or 1.0,
            )
            for r in rows
        ]

    
    async def _extract_triples_from_facts(
        self,
        facts: List[str],
        entity_id: str,
    ) -> List[SemanticTriple]:
        """
        Trích xuất semantic triples từ facts sử dụng LLM.
        
        Args:
            facts: Danh sách chuỗi fact
            entity_id: Entity ID cho context
            
        Returns:
            Danh sách đối tượng SemanticTriple đã trích xuất
        """
        if not facts:
            return []
        
        all_triples = []
        
        # Xử lý facts theo batch 3 để tránh giới hạn token
        batch_size = 3
        for i in range(0, len(facts), batch_size):
            batch = facts[i:i+batch_size]
            
            try:
                from app.services.core.rag_service import RAGService
                
                # Xây dựng prompt trích xuất
                facts_text = "\n".join([f"- {fact}" for fact in batch])
                
                extraction_prompt = f"""Extract semantic triples from facts with temporal and contextual awareness.

FACTS:
{facts_text}

INSTRUCTIONS:
1. PRONOUN RESOLUTION: Replace pronouns (tôi, mình, nó, ảnh, cậu ấy, I, me, he, she) with actual entity names
   - "tôi", "mình", "I", "me" → "user" (the speaker)

2. TEMPORAL EXTRACTION: Look for temporal indicators
   - "trước đây", "trước kia", "used to" → set invalid_at to "now"
   - "từ [date]", "since" → set valid_at to that date
   - "không ... nữa", "no longer" → set invalid_at to "now"

3. NEGATION: For "không X nữa", mark positive fact with invalid_at (fact ended)

4. SKIP: hypothetical (ước gì, nếu), sarcasm, greetings

Return JSON array:
[{{"s":"subject","st":"person|organization|concept|location|programming_language","p":"likes|prefers|works_at|lives_in|is_learning|knows|is","o":"object","ot":"type","valid_at":"ISO date or null","invalid_at":"ISO date or null","confidence":0.0-1.0}}]

Examples:
- "Trước đây tôi sống ở Hà Nội" → [{{"s":"user","st":"person","p":"lives_in","o":"Hà Nội","ot":"location","invalid_at":"now","confidence":0.9}}]
- "Từ tháng 6 tôi sống ở Huế" → [{{"s":"user","st":"person","p":"lives_in","o":"Huế","ot":"location","valid_at":"2024-06-01","confidence":0.9}}]

JSON:"""


                # Gọi LLM với max_tokens cao hơn cho triple extraction
                rag = await RAGService.get_instance(self.session)
                
                result = await rag._generate_answer_with_fallback(
                    question=extraction_prompt,
                    context="",
                    max_tokens=2048,  # Limit cao hơn
                )
                
                if result and result[0]:
                    response_text = result[0]
                    
                    # Lưu file debug
                    with open(f"triple_extraction_response_batch_{i}.txt", "w", encoding="utf-8") as f:
                        f.write(response_text)
                    logger.info(f"Đã lưu response LLM vào triple_extraction_response_batch_{i}.txt")
                    
                    # Parse JSON từ response
                    import json
                    import re
                    
                    # Loại bỏ markdown code blocks nếu có
                    cleaned_text = re.sub(r'```(?:json)?\s*', '', response_text)
                    cleaned_text = re.sub(r'```\s*$', '', cleaned_text).strip()
                    
                    # Cố gắng trích xuất mảng JSON
                    json_match = re.search(r'\[[\s\S]*\]', cleaned_text)
                    if json_match:
                        try:
                            data = json.loads(json_match.group())
                            
                            # Chuyển đổi sang SemanticTriple objects với hỗ trợ thời gian
                            # Hỗ trợ cả định dạng ngắn (s, p, o) và dài (subject, predicate, object)
                            for item in data:
                                if isinstance(item, dict):
                                    # Parse các trường thời gian
                                    valid_at = item.get('valid_at')
                                    invalid_at = item.get('invalid_at')
                                    confidence = item.get('confidence', 1.0)
                                    
                                    # Convert "now" sang datetime thực tế
                                    if valid_at == "now":
                                        valid_at = datetime.utcnow()
                                    elif valid_at and valid_at != "null":
                                        try:
                                            valid_at = datetime.fromisoformat(valid_at.replace('Z', '+00:00').replace('T00:00:00+00:00', 'T00:00:00'))
                                        except (ValueError, AttributeError):
                                            valid_at = None
                                    else:
                                        valid_at = None
                                        
                                    if invalid_at == "now":
                                        invalid_at = datetime.utcnow()
                                    elif invalid_at and invalid_at != "null":
                                        try:
                                            invalid_at = datetime.fromisoformat(invalid_at.replace('Z', '+00:00').replace('T00:00:00+00:00', 'T00:00:00'))
                                        except (ValueError, AttributeError):
                                            invalid_at = None
                                    else:
                                        invalid_at = None
                                    
                                    # Thử định dạng ngắn trước
                                    if all(k in item for k in ['s', 'p', 'o']):
                                        all_triples.append(SemanticTriple(
                                            subject_name=item['s'],
                                            subject_type=item.get('st'),
                                            predicate=item['p'],
                                            object_name=item['o'],
                                            object_type=item.get('ot'),
                                            valid_at=valid_at,
                                            invalid_at=invalid_at,
                                            confidence=float(confidence) if confidence else 1.0,
                                        ))
                                    # Thử định dạng dài
                                    elif all(k in item for k in ['subject', 'predicate', 'object']):
                                        all_triples.append(SemanticTriple(
                                            subject_name=item['subject'],
                                            subject_type=item.get('subject_type'),
                                            predicate=item['predicate'],
                                            object_name=item['object'],
                                            object_type=item.get('object_type'),
                                            valid_at=valid_at,
                                            invalid_at=invalid_at,
                                            confidence=float(confidence) if confidence else 1.0,
                                        ))

                            
                            logger.info(f"Đã trích xuất thành công {len(data)} triples từ batch {i//batch_size + 1}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Lỗi parse triple extraction response JSON: {e}")
                            logger.warning(f"JSON match: {json_match.group()}")
                    else:
                        logger.warning(f"Không tìm thấy mảng JSON trong cleaned response cho batch {i//batch_size + 1}")
            except Exception as e:
                logger.warning(f"Trích xuất Triple thất bại cho batch {i//batch_size + 1}: {e}")
        
        logger.info(f"Tổng số triples trích xuất được: {len(all_triples)}")
        
        # Validate và clean triples sử dụng TripleValidator
        if all_triples:
            try:
                from app.services.memori.triple_validator_service import TripleValidator
                validator = TripleValidator(self.session)
                
                # Xử lý triples (lọc, khử trùng lặp, validate)
                all_triples = await validator.process_triples(
                    triples=all_triples,
                    entity_name=entity_id,
                    facts=facts,
                    use_llm=True,  # Bật validate bằng LLM
                )
            except Exception as e:
                logger.warning(f"Triple validation thất bại: {e}, sử dụng triples chưa validated")
        
        return all_triples
    
    # =========================================================================
    # QUẢN LÝ PHIÊN (SESSION MANAGEMENT)
    # =========================================================================
    
    async def get_or_create_session(
        self,
        session_uuid: str,
        entity_id: Optional[str] = None,
        process_id: Optional[str] = None,
    ) -> int:
        """
        Lấy hoặc tạo mới một phiên (session).
        Sao chép từ Memori: Quản lý vòng đời session với timeout.
        """
        from app.db.models import MemoriSession
        
        # Cố gắng tìm session active hiện có
        result = await self.session.execute(
            select(MemoriSession).where(
                MemoriSession.uuid == session_uuid
            )
        )
        session_record = result.scalar_one_or_none()
        
        if session_record:
            # Kiểm tra timeout
            timeout = timedelta(minutes=self.config.session_timeout_minutes)
            if datetime.utcnow() - session_record.last_activity_at > timeout:
                # Session hết hạn, tạo mới
                session_record = None
            else:
                # Cập nhật activity cuối
                session_record.last_activity_at = datetime.utcnow()
                return session_record.id
        
        # Tạo session mới
        internal_entity_id = None
        internal_process_id = None
        
        if entity_id:
            internal_entity_id = await self.get_or_create_entity(entity_id)
        
        if process_id:
            internal_process_id = await self._get_or_create_process(process_id)
        
        session_record = MemoriSession(
            uuid=session_uuid,
            entity_id=internal_entity_id,
            process_id=internal_process_id,
            workspace_id=self.config.workspace_id,
        )
        self.session.add(session_record)
        await self.session.flush()
        
        logger.info(f"Đã tạo session mới: {session_uuid} (id={session_record.id})")
        return session_record.id
    
    async def _get_or_create_process(self, external_id: str) -> int:
        """Lấy hoặc tạo process theo external ID."""
        from app.db.models import MemoriProcess
        
        result = await self.session.execute(
            select(MemoriProcess).where(MemoriProcess.external_id == external_id)
        )
        process = result.scalar_one_or_none()
        
        if process:
            return process.id
        
        process = MemoriProcess(
            external_id=external_id,
            workspace_id=self.config.workspace_id,
        )
        self.session.add(process)
        await self.session.flush()
        
        return process.id
    
    # =========================================================================
    # AUGMENTATION (TRÍCH XUẤT FACT)
    # =========================================================================
    
    async def extract_facts_from_messages(
        self,
        messages: List[Dict[str, Any]],
        entity_id: str,
        conversation_id: Optional[UUID] = None,
    ) -> Memories:
        """
        Trích xuất facts và entities từ tin nhắn hội thoại.
        Sử dụng LLM để xác định thông tin quan trọng cần ghi nhớ.
        
        Args:
            messages: Danh sách dict tin nhắn với 'role' và 'content'
            entity_id: Entity để liên kết facts
            conversation_id: Nguồn hội thoại
            
        Returns:
            Memories object chứa facts đã trích xuất
        """
        if not messages:
            return Memories()
        
        # Xây dựng text hội thoại
        conversation_text = "\n".join([
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
            for m in messages
        ])
        
        # Dùng LLM để trích xuất facts
        extraction_prompt = f"""Analyze this conversation and extract important facts to remember about the user.

CONVERSATION:
{conversation_text}

Extract:
1. Facts about the user (preferences, background, interests)
2. Key decisions or statements made
3. Important context for future conversations

Return as JSON:
{{
    "facts": ["fact1", "fact2", ...],
    "entities": [
        {{"name": "entity_name", "type": "person/organization/concept", "relation": "relation_to_user"}}
    ]
}}

Only include genuinely useful facts, not trivial conversation details."""

        try:
            # Sử dụng RAG service hiện có để gọi LLM
            from app.services.core.rag import RAGService
            
            rag = await RAGService.get_instance(self.session)
            result = await rag._generate_answer_with_fallback(
                question=extraction_prompt,
                context="",
            )
            
            if result and result[0]:
                response_text = result[0]
                
                # Parse JSON từ response
                import json
                import re
                
                # Cố gắng trích xuất JSON từ text
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        
                        # Lưu facts đã trích xuất
                        facts = data.get("facts", [])
                        if facts:
                            await self.add_facts(
                                entity_id=entity_id,
                                facts=facts,
                                conversation_id=conversation_id,
                            )
                        
                        # Lưu entities dưới dạng semantic triples
                        entities = data.get("entities", [])
                        triples = []
                        for ent in entities:
                            if ent.get("name") and ent.get("relation"):
                                triples.append(SemanticTriple(
                                    subject_name="user",
                                    subject_type="person",
                                    predicate=ent.get("relation"),
                                    object_name=ent.get("name"),
                                    object_type=ent.get("type", "entity"),
                                ))
                        
                        if triples:
                            await self.add_semantic_triples(
                                entity_id=entity_id,
                                triples=triples,
                                conversation_id=conversation_id,
                            )
                        
                        # Build Memories object
                        memories = Memories()
                        memories.entity.facts = facts
                        memories.entity.semantic_triples = triples
                        
                        logger.info(
                            f"Đã trích xuất {len(facts)} facts và {len(triples)} triples "
                            f"cho entity {entity_id}"
                        )
                        
                        return memories
                    except json.JSONDecodeError:
                        logger.warning("Lỗi parse extraction response thành JSON")
        except Exception as e:
            logger.warning(f"Fact extraction thất bại: {e}")
        
        return Memories()
    
    # =========================================================================
    # PREFERENCE MANAGEMENT (Phase 2)
    # =========================================================================
    
    async def add_preference(
        self,
        entity_id: str,
        category: str,
        key: str,
        value: str,
        importance: float = 8.0,
    ) -> int:
        """
        Thêm một sở thích (preference) cho entity.
        
        Args:
            entity_id: External entity ID
            category: Danh mục sở thích (ui, language, response, etc.)
            key: Khóa sở thích
            value: Giá trị sở thích
            importance: Điểm quan trọng (mặc định 8.0 cho sở thích)
            
        Returns:
            ID của sở thích đã tạo
        """
        from app.db.models import MemoriEntityPreference
        
        # Lấy internal entity ID
        internal_id = await self.get_or_create_entity(entity_id)
        
        # Kiểm tra preference hiện có
        existing = await self.session.execute(
            select(MemoriEntityPreference).where(
                and_(
                    MemoriEntityPreference.entity_id == internal_id,
                    MemoriEntityPreference.category == category,
                    MemoriEntityPreference.preference_key == key,
                )
            )
        )
        existing_pref = existing.scalar_one_or_none()
        
        if existing_pref:
            # Cập nhật existing
            existing_pref.preference_value = value
            existing_pref.importance_score = importance
            existing_pref.updated_at = datetime.utcnow()
            await self.session.flush()
            logger.info(f"Đã cập nhật preference {key} cho entity {entity_id}")
            return existing_pref.id
        
        # Tạo mới
        pref = MemoriEntityPreference(
            entity_id=internal_id,
            category=category,
            preference_key=key,
            preference_value=value,
            importance_score=importance,
        )
        self.session.add(pref)
        await self.session.flush()
        
        logger.info(f"Đã thêm preference {key}={value} cho entity {entity_id}")
        return pref.id
    
    async def get_preferences(
        self,
        entity_id: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lấy danh sách sở thích của một entity.
        
        Args:
            entity_id: External entity ID
            category: Bộ lọc danh mục tùy chọn
            
        Returns:
            Dict các preference {key: {value, category, importance, updated_at}}
        """
        from app.db.models import MemoriEntity, MemoriEntityPreference
        
        # Lấy internal ID
        result = await self.session.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        if not internal_id:
            return {}
        
        # Build query
        query = select(MemoriEntityPreference).where(
            MemoriEntityPreference.entity_id == internal_id
        )
        
        if category:
            query = query.where(MemoriEntityPreference.category == category)
        
        # Thực thi
        result = await self.session.execute(query)
        prefs = result.scalars().all()
        
        # Convert sang dict
        return {
            pref.preference_key: {
                'value': pref.preference_value,
                'category': pref.category,
                'importance': pref.importance_score,
                'updated_at': pref.updated_at.isoformat() if pref.updated_at else None,
            }
            for pref in prefs
        }
    
    async def update_preference(
        self,
        pref_id: int,
        value: str,
        importance: float,
    ) -> None:
        """Cập nhật một sở thích."""
        from app.db.models import MemoriEntityPreference
        
        result = await self.session.execute(
            select(MemoriEntityPreference).where(MemoriEntityPreference.id == pref_id)
        )
        pref = result.scalar_one_or_none()
        
        if pref:
            pref.preference_value = value
            pref.importance_score = importance
            pref.updated_at = datetime.utcnow()
            logger.info(f"Đã cập nhật preference {pref_id}")
    
    async def delete_preference(self, pref_id: int) -> None:
        """Xóa một sở thích."""
        from app.db.models import MemoriEntityPreference
        from sqlalchemy import delete
        
        await self.session.execute(
            delete(MemoriEntityPreference).where(MemoriEntityPreference.id == pref_id)
        )
        logger.info(f"Đã xóa preference {pref_id}")
    
    # =========================================================================
    # QUẢN LÝ THUỘC TÍNH (ATTRIBUTE MANAGEMENT - Phase 2)
    # =========================================================================
    
    async def add_attribute(
        self,
        entity_id: str,
        category: str,
        key: str,
        value: str,
        importance: float = 7.0,
    ) -> int:
        """
        Thêm một thuộc tính cho entity.
        
        Args:
            entity_id: External entity ID
            category: Danh mục thuộc tính (role, skill, location, etc.)
            key: Tên thuộc tính
            value: Giá trị thuộc tính
            importance: Điểm quan trọng (mặc định 7.0 cho thuộc tính)
            
        Returns:
            ID của thuộc tính đã tạo
        """
        from app.db.models import MemoriEntityAttribute
        
        # Lấy internal entity ID
        internal_id = await self.get_or_create_entity(entity_id)
        
        # Kiểm tra thuộc tính hiện có
        existing = await self.session.execute(
            select(MemoriEntityAttribute).where(
                and_(
                    MemoriEntityAttribute.entity_id == internal_id,
                    MemoriEntityAttribute.category == category,
                    MemoriEntityAttribute.attribute_key == key,
                )
            )
        )
        existing_attr = existing.scalar_one_or_none()
        
        if existing_attr:
            # Cập nhật existing
            existing_attr.attribute_value = value
            existing_attr.importance_score = importance
            existing_attr.updated_at = datetime.utcnow()
            await self.session.flush()
            logger.info(f"Đã cập nhật attribute {key} cho entity {entity_id}")
            return existing_attr.id
        
        # Tạo mới
        attr = MemoriEntityAttribute(
            entity_id=internal_id,
            category=category,
            attribute_key=key,
            attribute_value=value,
            importance_score=importance,
        )
        self.session.add(attr)
        await self.session.flush()
        
        logger.info(f"Đã thêm attribute {key}={value} cho entity {entity_id}")
        return attr.id
    
    async def get_attributes(
        self,
        entity_id: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lấy danh sách thuộc tính của một entity.
        
        Args:
            entity_id: External entity ID
            category: Bộ lọc danh mục tùy chọn
            
        Returns:
            Dict các attributes {key: {value, category, importance, updated_at}}
        """
        from app.db.models import MemoriEntity, MemoriEntityAttribute
        
        # Lấy internal ID
        result = await self.session.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        if not internal_id:
            return {}
        
        # Build query
        query = select(MemoriEntityAttribute).where(
            MemoriEntityAttribute.entity_id == internal_id
        )
        
        if category:
            query = query.where(MemoriEntityAttribute.category == category)
        
        # Thực thi
        result = await self.session.execute(query)
        attrs = result.scalars().all()
        
        # Convert sang dict
        return {
            attr.attribute_key: {
                'value': attr.attribute_value,
                'category': attr.category,
                'importance': attr.importance_score,
                'updated_at': attr.updated_at.isoformat() if attr.updated_at else None,
            }
            for attr in attrs
        }
    
    async def update_attribute(
        self,
        attr_id: int,
        value: str,
        importance: float,
    ) -> None:
        """Cập nhật một thuộc tính."""
        from app.db.models import MemoriEntityAttribute
        
        result = await self.session.execute(
            select(MemoriEntityAttribute).where(MemoriEntityAttribute.id == attr_id)
        )
        attr = result.scalar_one_or_none()
        
        if attr:
            attr.attribute_value = value
            attr.importance_score = importance
            attr.updated_at = datetime.utcnow()
            logger.info(f"Đã cập nhật attribute {attr_id}")
    
    async def delete_attribute(self, attr_id: int) -> None:
        """Xóa một thuộc tính."""
        from app.db.models import MemoriEntityAttribute
        from sqlalchemy import delete
        
        await self.session.execute(
            delete(MemoriEntityAttribute).where(MemoriEntityAttribute.id == attr_id)
        )
        logger.info(f"Đã xóa attribute {attr_id}")
    
    # =========================================================================
    # TÍCH HỢP RECALL (RECALL INTEGRATION)
    # =========================================================================
    
    async def recall_for_query(
        self,
        query: str,
        entity_id: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[RecalledFact]:
        """
        Truy hồi (recall) facts liên quan cho một truy vấn.
        Bao bọc MemoriRecall với khả năng phân giải entity.
        
        Args:
            query: Truy vấn người dùng
            entity_id: Entity ID tùy chọn
            conversation_id: ID hội thoại tùy chọn
            limit: Số lượng facts tối đa
            
        Returns:
            Danh sách các facts liên quan
        """
        entity_id = entity_id or self.config.entity_id
        
        if entity_id:
            return await self.recall.search_facts(
                query=query,
                entity_id=entity_id,
                limit=limit,
            )
        elif conversation_id:
            return await self.recall.search_facts_for_conversation(
                query=query,
                conversation_id=conversation_id,
                limit=limit,
            )
        elif self.config.workspace_id:
            return await self.recall.search_facts_in_workspace(
                query=query,
                workspace_id=self.config.workspace_id,
                limit=limit,
            )
        
        return []
    
    def format_recalled_facts(self, facts: List[RecalledFact]) -> str:
        """Định dạng facts đã recall để tiêm vào prompt."""
        return self.recall.format_facts_for_prompt(facts)
    
    # =========================================================================
    # DỌN DẸP (CLEANUP)
    # =========================================================================
    
    async def cleanup_old_facts(
        self,
        entity_id: str,
        max_facts: int = 1000,
        min_importance: float = 0.1,
    ) -> int:
        """
        Dọn dẹp các facts cũ/kém quan trọng để ngăn chặn sự phát triển không giới hạn.
        
        Args:
            entity_id: Entity cần dọn dẹp
            max_facts: Số lượng facts tối đa giữ lại
            min_importance: Điểm importance tối thiểu giữ lại
            
        Returns:
            Số lượng facts đã xóa
        """
        from app.db.models import MemoriEntity, MemoriEntityFact
        
        # Lấy internal ID
        result = await self.session.execute(
            select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
        )
        internal_id = result.scalar_one_or_none()
        if not internal_id:
            return 0
        
        # Đếm facts
        count_result = await self.session.execute(
            select(MemoriEntityFact.id).where(
                MemoriEntityFact.entity_id == internal_id
            )
        )
        total_facts = len(count_result.fetchall())
        
        if total_facts <= max_facts:
            return 0
        
        # Xóa các facts có importance thấp
        to_delete = total_facts - max_facts
        
        result = await self.session.execute(
            select(MemoriEntityFact.id)
            .where(
                and_(
                    MemoriEntityFact.entity_id == internal_id,
                    MemoriEntityFact.importance_score < min_importance,
                )
            )
            .order_by(MemoriEntityFact.importance_score.asc())
            .limit(to_delete)
        )
        ids_to_delete = [r[0] for r in result.fetchall()]
        
        if ids_to_delete:
            from sqlalchemy import delete
            await self.session.execute(
                delete(MemoriEntityFact).where(
                    MemoriEntityFact.id.in_(ids_to_delete)
                )
            )
            logger.info(f"Đã dọn dẹp {len(ids_to_delete)} facts cho entity {entity_id}")
        
        return len(ids_to_delete)
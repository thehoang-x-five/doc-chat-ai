"""
Entity Resolution - Nhận diện và merge các entities giống nhau.

Giải quyết vấn đề:
- "tôi", "user", "thế", "Tài Thế" đều là cùng một người
- Tự động merge triples về cùng một entity
"""
import logging
from typing import List, Dict, Set, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoriKnowledgeGraph, MemoriEntity

logger = logging.getLogger(__name__)


class EntityResolver:
    """
    Resolve entity aliases và merge triples.
    
    Tính năng:
    - Phát hiện entity aliases (tôi, user, thế, Tài Thế)
    - Merge triples về canonical entity name
    - Sử dụng LLM để xác định mối quan hệ entity
    """
    
    # Common aliases cho "user" trong tiếng Việt
    USER_ALIASES = {
        "tôi", "mình", "user", "i", "me", "myself",
        "người dùng", "tao", "ta"
    }
    
    # Đại từ nhân xưng ngôi thứ ba cần giải quyết
    THIRD_PERSON_PRONOUNS = {
        "nó", "ảnh", "cậu ấy", "ông ấy", "bà ấy", "cô ấy",
        "anh ấy", "chị ấy", "họ", "he", "she", "they", "it", "him", "her"
    }
    
    def __init__(self, session: AsyncSession, rag_service=None):
        self.session = session
        self.rag_service = rag_service
    
    async def resolve_pronouns_with_llm(
        self,
        text: str,
        conversation_context: list[str],
        known_entities: list[str],
    ) -> dict[str, str]:
        """
        Sử dụng LLM để giải quyết các đại từ thành tên entity thực tế.
        
        Graphiti-inspired: Sử dụng ngữ cảnh hội thoại để xác định đại từ ám chỉ ai/cái gì.
        
        Args:
            text: Văn bản chứa đại từ cần giải quyết
            conversation_context: Danh sách các tin nhắn trước đó làm ngữ cảnh
            known_entities: Danh sách các tên entity đã biết
            
        Returns:
            Dict mapping đại từ -> tên entity đã giải quyết
        """
        if not self.rag_service:
            from app.services.core.rag import RAGService
            self.rag_service = await RAGService.get_instance(self.session)
        
        # Kiểm tra xem văn bản có chứa đại từ nào cần giải quyết không
        text_lower = text.lower()
        pronouns_found = [p for p in self.THIRD_PERSON_PRONOUNS if p in text_lower]
        
        if not pronouns_found:
            return {}
        
        context_text = "\n".join(conversation_context[-5:])  # 5 tin nhắn cuối cùng
        entities_text = ", ".join(known_entities) if known_entities else "unknown"
        
        prompt = f"""Resolve pronouns to actual entity names based on conversation context.

CONVERSATION CONTEXT:
{context_text}

CURRENT TEXT: "{text}"

KNOWN ENTITIES: {entities_text}

PRONOUNS TO RESOLVE: {pronouns_found}

For each pronoun, determine which entity it refers to based on context.
If uncertain, use "unknown".

Return JSON:
{{"pronoun": "resolved_entity_name", ...}}

Example:
Text: "Nó rất thông minh"
Context: "Tôi là Thế. Tôi thích programming."
→ {{"nó": "Thế"}}

JSON:"""

        try:
            result = await self.rag_service._generate_answer_with_fallback(
                question=prompt,
                context="",
                max_tokens=512,
            )
            
            if result and result[0]:
                import json
                import re
                
                response_text = result[0]
                cleaned = re.sub(r'```(?:json)?\s*', '', response_text)
                cleaned = re.sub(r'```\s*$', '', cleaned).strip()
                
                json_match = re.search(r'\{[^}]+\}', cleaned)
                if json_match:
                    try:
                        resolutions = json.loads(json_match.group())
                        logger.info(f"Đã giải quyết đại từ: {resolutions}")
                        return resolutions
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"LLM giải quyết đại từ thất bại: {e}")
        
        return {}

    
    async def resolve_entity_aliases(
        self,
        entity_id: int,
        canonical_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Tìm tất cả aliases của một entity và trả về mapping.
        
        Args:
            entity_id: Internal entity ID
            canonical_name: Tên chính thức (nếu biết)
            
        Returns:
            Dict mapping alias -> canonical_name
        """
        # Lấy tất cả triples cho entity này
        result = await self.session.execute(
            select(MemoriKnowledgeGraph).where(
                MemoriKnowledgeGraph.entity_id == entity_id
            )
        )
        triples = result.scalars().all()
        
        if not triples:
            return {}
        
        # Thu thập tất cả subject names
        subjects = set()
        for triple in triples:
            if triple.subject_type == "person":
                subjects.add(triple.subject_name.lower())
        
        # Tìm canonical name
        if not canonical_name:
            # Sử dụng tên cụ thể nhất (dài nhất, không nằm trong USER_ALIASES)
            non_generic = [s for s in subjects if s not in self.USER_ALIASES]
            if non_generic:
                canonical_name = max(non_generic, key=len)
            else:
                canonical_name = "user"
        
        # Xây dựng alias mapping
        alias_map = {}
        for subject in subjects:
            if subject != canonical_name.lower():
                alias_map[subject] = canonical_name
        
        logger.info(f"Tìm thấy {len(alias_map)} aliases cho {canonical_name}: {alias_map}")
        return alias_map
    
    async def merge_entity_triples(
        self,
        entity_id: int,
        canonical_name: str,
    ) -> int:
        """
        Merge tất cả triples về canonical entity name.
        
        Args:
            entity_id: Internal entity ID
            canonical_name: Tên chính thức để merge về
            
        Returns:
            Số lượng triples đã update
        """
        # Lấy alias mapping
        alias_map = await self.resolve_entity_aliases(entity_id, canonical_name)
        
        if not alias_map:
            logger.info("Không tìm thấy aliases để merge")
            return 0
        
        # Cập nhật tất cả triples có aliases
        updated_count = 0
        for alias, canonical in alias_map.items():
            result = await self.session.execute(
                select(MemoriKnowledgeGraph).where(
                    and_(
                        MemoriKnowledgeGraph.entity_id == entity_id,
                        MemoriKnowledgeGraph.subject_name.ilike(alias)
                    )
                )
            )
            triples_to_update = result.scalars().all()
            
            for triple in triples_to_update:
                triple.subject_name = canonical
                updated_count += 1
        
        await self.session.commit()
        logger.info(f"Đã merge {updated_count} triples về tên chính thức: {canonical_name}")
        return updated_count
    
    async def auto_detect_canonical_name(
        self,
        entity_id: int,
    ) -> Optional[str]:
        """
        Tự động phát hiện tên chính thức từ facts.
        
        Tìm trong facts các pattern:
        - "tôi là [Tên]"
        - "tôi tên [Tên]"
        - "my name is [Name]"
        """
        from app.db.models import MemoriEntityFact
        
        # Lấy tất cả facts
        result = await self.session.execute(
            select(MemoriEntityFact).where(
                MemoriEntityFact.entity_id == entity_id
            )
        )
        facts = result.scalars().all()
        
        # Tìm kiếm các mẫu name pattern
        import re
        name_patterns = [
            r"tôi là ([A-Za-zÀ-ỹ\s]+)",
            r"tôi tên ([A-Za-zÀ-ỹ\s]+)",
            r"my name is ([A-Za-z\s]+)",
            r"i am ([A-Za-z\s]+)",
        ]
        
        for fact in facts:
            content = fact.content.lower()
            for pattern in name_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Filter ra các từ thông dụng
                    if name not in self.USER_ALIASES and len(name) > 2:
                        logger.info(f"Tự động phát hiện tên chính thức: {name}")
                        return name.title()  # Viết hoa chữ cái đầu
        
        return None
    
    async def resolve_and_merge(
        self,
        entity_external_id: str,
        canonical_name: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Tự động resolve và merge entities.
        
        Args:
            entity_external_id: External entity ID
            canonical_name: Tên chính thức (optional, sẽ tự detect nếu không có)
            
        Returns:
            Dict với kết quả
        """
        # Lấy internal entity ID
        result = await self.session.execute(
            select(MemoriEntity).where(
                MemoriEntity.external_id == entity_external_id
            )
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return {"error": "Entity not found"}
        
        # Tự động detect canonical name nếu không được cung cấp
        if not canonical_name:
            canonical_name = await self.auto_detect_canonical_name(entity.id)
            if not canonical_name:
                canonical_name = "User"  # Default fallback
        
        # Lấy aliases trước khi merge
        alias_map = await self.resolve_entity_aliases(entity.id, canonical_name)
        
        # Merge triples
        updated_count = await self.merge_entity_triples(entity.id, canonical_name)
        
        return {
            "canonical_name": canonical_name,
            "aliases_found": list(alias_map.keys()),
            "triples_updated": updated_count,
        }

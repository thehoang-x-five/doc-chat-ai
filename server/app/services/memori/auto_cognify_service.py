"""
Auto Cognify Service - Tự động trích xuất knowledge từ conversations.

Tự động extract facts, entities, và semantic triples từ mỗi tin nhắn.

Tính năng:
- Extract facts quan trọng từ messages
- Xây dựng semantic triples (Subject-Predicate-Object)
- Lưu vào knowledge graph qua MemoriManager
- Chạy async (non-blocking) sau mỗi message
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AutoCognifyService:
    """
    Tự động trích xuất knowledge từ conversations.
    
    Pipeline:
    1. Extract facts từ message
    2. Extract entities (NER)
    3. Build semantic triples
    4. Store via MemoriManager
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
        """Lazy load AI provider for LLM extraction."""
        if self._ai_provider is None:
            try:
                from app.services.core.ai_provider import AIProviderManager
                self._ai_provider = AIProviderManager()
            except ImportError as e:
                logger.warning(f"AIProviderManager not available: {e}")
        return self._ai_provider
    
    async def cognify_message(
        self,
        message: str,
        role: str,
        conversation_id: UUID,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Process một message để extract knowledge.
        Được gọi async (non-blocking) sau mỗi message.
        
        Args:
            message: Nội dung tin nhắn
            role: "user" hoặc "assistant"
            conversation_id: ID cuộc hội thoại
            user_id: ID người dùng
            workspace_id: ID workspace (optional)
            
        Returns:
            Dict với số lượng facts và triples đã extract
        """
        if not message or len(message.strip()) < 10:
            return {"facts": 0, "triples": 0, "skipped": True}
        
        logger.info(f"🧠 Auto-cognify: Processing {role} message ({len(message)} chars)")
        
        result = {"facts": 0, "triples": 0, "errors": []}
        
        try:
            # 1. Extract facts từ message
            facts = await self._extract_facts(message, role)
            result["facts"] = len(facts)
            
            if not facts:
                logger.debug("No facts extracted from message")
                return result
            
            # 2. Lưu facts vào MemoriManager
            memori = await self._get_memori_manager()
            if memori:
                entity_id = str(user_id)
                
                # Thêm facts với importance scoring
                importance_scores = await self._score_facts_importance(facts)
                
                await memori.add_facts(
                    entity_id=entity_id,
                    facts=facts,
                    conversation_id=conversation_id,
                    importance_scores=importance_scores,
                    extract_triples=True,  # Auto extract triples
                )
                
                logger.info(f"✅ Auto-cognify: Saved {len(facts)} facts for user {entity_id}")
            else:
                result["errors"].append("MemoriManager not available")
                
        except Exception as e:
            logger.warning(f"Auto-cognify error: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def _extract_facts(self, message: str, role: str) -> List[str]:
        """
        Trích xuất facts quan trọng từ message.
        Sử dụng LLM hoặc rule-based extraction.
        
        Args:
            message: Nội dung tin nhắn
            role: "user" hoặc "assistant"
            
        Returns:
            List các facts đã trích xuất
        """
        # Thử LLM extraction trước
        llm_facts = await self._extract_facts_with_llm(message, role)
        if llm_facts:
            return llm_facts
        
        # Fallback: Rule-based extraction
        return self._extract_facts_rule_based(message, role)
    
    async def _extract_facts_with_llm(self, message: str, role: str) -> List[str]:
        """Sử dụng LLM để extract facts."""
        try:
            ai = await self._get_ai_provider()
            if not ai:
                return []
            
            prompt = f"""Analyze this {role} message and extract important facts that should be remembered.
Focus on:
- Personal information (name, age, job, location, preferences)
- Important statements about themselves or their work
- Specific details that would be useful to remember later

Message: "{message}"

Return ONLY the facts as a JSON array of strings, no explanation.
Example: ["User's name is John", "User works as a developer", "User prefers Python"]

If no important facts found, return: []"""

            # Get available provider
            providers = ai._get_available_providers()
            if not providers:
                return []
            
            provider = ai.providers.get(providers[0])
            if not provider:
                return []
            
            response = await provider.chat_completion([
                {"role": "system", "content": "You extract facts from messages. Return only JSON array."},
                {"role": "user", "content": prompt}
            ])
            
            # Parse JSON response
            import json
            # Clean response - extract JSON array
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            facts = json.loads(response)
            if isinstance(facts, list):
                return [f for f in facts if isinstance(f, str) and len(f) > 5]
            
        except Exception as e:
            logger.debug(f"LLM fact extraction failed: {e}")
        
        return []
    
    def _extract_facts_rule_based(self, message: str, role: str) -> List[str]:
        """Rule-based fact extraction (fallback)."""
        facts = []
        
        # Pattern matching cho các thông tin quan trọng
        patterns = [
            # Tên
            (r"(?:tên\s+(?:tôi|mình|em)\s+là|i(?:'?m| am)\s+called?)\s+([A-ZÀ-Ỹa-zà-ỹ]+)", "Tên là {}"),
            # Tuổi
            (r"(?:tôi|mình|em|i(?:'?m| am))\s+(\d{1,3})\s*(?:tuổi|years? old)", "Tuổi: {}"),
            # Nghề nghiệp
            (r"(?:tôi|mình|em)\s+(là\s+[a-zà-ỹ\s]+(?:developer|kỹ sư|bác sĩ|giáo viên|sinh viên))", "Nghề nghiệp: {}"),
            # Làm việc tại
            (r"(?:làm việc|work)\s+(?:tại|ở|at)\s+(.+?)(?:\.|,|$)", "Làm việc tại {}"),
            # Sở thích
            (r"(?:tôi|mình|em)\s+(?:thích|yêu thích|love|like)\s+(.+?)(?:\.|,|$)", "Sở thích: {}"),
        ]
        
        for pattern, template in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                fact = template.format(match.strip())
                if fact not in facts:
                    facts.append(fact)
        
        # Nếu là message dài và có dấu chấm, trích xuất câu quan trọng
        if len(message) > 100 and role == "user":
            sentences = re.split(r'[.!?]', message)
            important_keywords = ['tôi', 'tên', 'tuổi', 'làm việc', 'học', 'sống', 'yêu thích']
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and any(kw in sentence.lower() for kw in important_keywords):
                    if sentence not in facts:
                        facts.append(sentence)
        
        return facts[:5]  # Limit to 5 facts per message
    
    async def _score_facts_importance(self, facts: List[str]) -> List[float]:
        """
        Chấm điểm importance cho mỗi fact.
        
        Args:
            facts: List các facts
            
        Returns:
            List importance scores (0.0 - 10.0)
        """
        scores = []
        
        # Heuristic scoring
        high_importance_keywords = ['tên', 'name', 'tuổi', 'age', 'làm việc', 'work', 'sống', 'live']
        medium_importance_keywords = ['thích', 'like', 'yêu', 'love', 'học', 'study']
        
        for fact in facts:
            fact_lower = fact.lower()
            
            if any(kw in fact_lower for kw in high_importance_keywords):
                scores.append(8.5)
            elif any(kw in fact_lower for kw in medium_importance_keywords):
                scores.append(6.5)
            else:
                scores.append(5.0)
        
        return scores
    
    async def cognify_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Process toàn bộ conversation để extract knowledge.
        Dùng cho batch processing hoặc khi cần rebuild knowledge.
        
        Args:
            conversation_id: ID cuộc hội thoại
            user_id: ID người dùng
            messages: List các message dicts với 'role' và 'content'
            
        Returns:
            Dict với tổng số facts và triples
        """
        total_facts = 0
        total_triples = 0
        
        for msg in messages:
            result = await self.cognify_message(
                message=msg.get("content", ""),
                role=msg.get("role", "user"),
                conversation_id=conversation_id,
                user_id=user_id,
            )
            total_facts += result.get("facts", 0)
            total_triples += result.get("triples", 0)
        
        logger.info(
            f"🧠 Conversation cognify complete: {total_facts} facts, {total_triples} triples"
        )
        
        return {"facts": total_facts, "triples": total_triples}

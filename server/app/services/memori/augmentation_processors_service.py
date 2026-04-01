"""
Augmentation Processors - Xử lý các loại memory augmentation khác nhau.
Sao chép và điều chỉnh từ project Memori.

Tính năng:
- Trích xuất Fact từ hội thoại
- Phát hiện sở thích (Preference detection)
- Trích xuất thuộc tính (Attribute extraction)
- Theo dõi sự kiện (Event tracking)
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.services.memori.models import Memories, SemanticTriple
from app.services.memori.extraction import FactExtractor

logger = logging.getLogger(__name__)


class FactAugmentationProcessor:
    """
    Xử lý trích xuất fact từ hội thoại.
    Sử dụng FactExtractor để trích xuất fact chất lượng cao.
    """
    
    def __init__(self, fact_extractor: FactExtractor):
        self.extractor = fact_extractor
    
    async def process(
        self,
        messages: List[Dict[str, Any]],
        entity_id: str,
        conversation_id: Optional[UUID] = None,
    ) -> Memories:
        """
        Trích xuất facts từ tin nhắn hội thoại.
        
        Args:
            messages: Danh sách dict tin nhắn với 'role' và 'content'
            entity_id: Entity để liên kết facts
            conversation_id: Nguồn hội thoại
            
        Returns:
            Memories object chứa facts đã trích xuất
        """
        if not messages or len(messages) < 2:
            return Memories()
        
        memories = Memories()
        
        try:
            # Lấy tin nhắn người dùng cuối cùng và phản hồi của AI
            user_msg = None
            ai_msg = None
            
            for msg in reversed(messages):
                if msg.get('role') == 'user' and user_msg is None:
                    user_msg = msg.get('content', '')
                elif msg.get('role') == 'assistant' and ai_msg is None:
                    ai_msg = msg.get('content', '')
                
                if user_msg and ai_msg:
                    break
            
            if not user_msg or not ai_msg:
                logger.debug("Không tìm thấy cuộc trao đổi user-AI hoàn chỉnh")
                return memories
            
            # Trích xuất facts sử dụng FactExtractor
            facts = await self.extractor.extract_from_conversation(
                user_message=user_msg,
                ai_response=ai_msg,
                conversation_history=messages[:-2] if len(messages) > 2 else None,
            )
            
            if not facts:
                logger.debug("Không có facts nào được trích xuất")
                return memories
            
            # Tính toán importance cho mỗi fact
            facts_with_importance = []
            for fact in facts:
                importance = self.extractor.calculate_importance(fact, user_msg)
                facts_with_importance.append({
                    'content': fact,
                    'importance': importance,
                })
            
            # Lưu vào memories
            memories.entity.facts = [f['content'] for f in facts_with_importance]
            memories.entity.fact_importance_scores = [f['importance'] for f in facts_with_importance]
            
            logger.info(
                f"Đã trích xuất {len(facts)} facts cho entity {entity_id} "
                f"(avg importance: {sum(f['importance'] for f in facts_with_importance) / len(facts):.2f})"
            )
            
        except Exception as e:
            logger.error(f"Fact augmentation thất bại: {e}")
        
        return memories


class PreferenceAugmentationProcessor:
    """
    Xử lý phát hiện sở thích từ hội thoại.
    Phát hiện các sở thích của người dùng như cài đặt UI, ngôn ngữ, định dạng, etc.
    """
    
    async def process(
        self,
        messages: List[Dict[str, Any]],
        entity_id: str,
    ) -> Dict[str, Any]:
        """
        Phát hiện sở thích từ hội thoại.
        
        Returns:
            Dict chứa các sở thích được phát hiện
        """
        preferences = {}
        
        try:
            # Phân tích tin nhắn để tìm các dấu hiệu preference
            for msg in messages:
                if msg.get('role') != 'user':
                    continue
                
                content = msg.get('content', '').lower()
                
                # Sở thích UI
                if 'dark mode' in content or 'dark theme' in content:
                    preferences['ui_theme'] = 'dark'
                elif 'light mode' in content or 'light theme' in content:
                    preferences['ui_theme'] = 'light'
                
                # Sở thích ngôn ngữ
                if 'vietnamese' in content or 'tiếng việt' in content:
                    preferences['language'] = 'vi'
                elif 'english' in content:
                    preferences['language'] = 'en'
                
                # Sở thích định dạng phản hồi
                if 'concise' in content or 'brief' in content or 'short' in content:
                    preferences['response_format'] = 'concise'
                elif 'detailed' in content or 'verbose' in content:
                    preferences['response_format'] = 'detailed'
            
            if preferences:
                logger.info(f"Đã phát hiện {len(preferences)} preferences cho entity {entity_id}")
            
        except Exception as e:
            logger.error(f"Preference augmentation thất bại: {e}")
        
        return preferences


class AttributeAugmentationProcessor:
    """
    Xử lý trích xuất thuộc tính từ hội thoại.
    Trích xuất các thuộc tính người dùng như vai trò, kỹ năng, địa điểm, etc.
    """
    
    async def process(
        self,
        messages: List[Dict[str, Any]],
        entity_id: str,
    ) -> Dict[str, Any]:
        """
        Trích xuất thuộc tính từ hội thoại.
        
        Returns:
            Dict chứa các thuộc tính được phát hiện
        """
        attributes = {}
        
        try:
            # Phân tích tin nhắn để tìm các dấu hiệu attribute
            conversation_text = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in messages
            ])
            
            text_lower = conversation_text.lower()
            
            # Phát hiện Role
            if 'developer' in text_lower or 'programmer' in text_lower:
                attributes['role'] = 'developer'
            elif 'designer' in text_lower:
                attributes['role'] = 'designer'
            elif 'manager' in text_lower:
                attributes['role'] = 'manager'
            
            # Phát hiện Skill
            skills = []
            skill_keywords = ['python', 'javascript', 'react', 'vue', 'node', 'django', 'fastapi']
            for skill in skill_keywords:
                if skill in text_lower:
                    skills.append(skill)
            
            if skills:
                attributes['skills'] = skills
            
            # Phát hiện Location (đơn giản)
            if 'vietnam' in text_lower or 'việt nam' in text_lower:
                attributes['location'] = 'Vietnam'
            
            if attributes:
                logger.info(f"Đã phát hiện {len(attributes)} attributes cho entity {entity_id}")
            
        except Exception as e:
            logger.error(f"Attribute augmentation thất bại: {e}")
        
        return attributes


class AugmentationPipeline:
    """
    Điều phối tất cả các augmentation processors.
    Chạy các processors theo trình tự và gộp kết quả.
    """
    
    def __init__(self, fact_extractor: FactExtractor):
        self.fact_processor = FactAugmentationProcessor(fact_extractor)
        self.preference_processor = PreferenceAugmentationProcessor()
        self.attribute_processor = AttributeAugmentationProcessor()
    
    async def process_all(
        self,
        messages: List[Dict[str, Any]],
        entity_id: str,
        conversation_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Chạy tất cả augmentation processors.
        
        Returns:
            Dict chứa tất cả kết quả augmentation
        """
        results = {
            'memories': Memories(),
            'preferences': {},
            'attributes': {},
        }
        
        try:
            # Chạy processors song song
            import asyncio
            
            memories_task = self.fact_processor.process(messages, entity_id, conversation_id)
            preferences_task = self.preference_processor.process(messages, entity_id)
            attributes_task = self.attribute_processor.process(messages, entity_id)
            
            memories, preferences, attributes = await asyncio.gather(
                memories_task,
                preferences_task,
                attributes_task,
                return_exceptions=True,
            )
            
            # Xử lý kết quả
            if isinstance(memories, Memories):
                results['memories'] = memories
            else:
                logger.error(f"Xử lý Fact thất bại: {memories}")
            
            if isinstance(preferences, dict):
                results['preferences'] = preferences
            else:
                logger.error(f"Xử lý Preference thất bại: {preferences}")
            
            if isinstance(attributes, dict):
                results['attributes'] = attributes
            else:
                logger.error(f"Xử lý Attribute thất bại: {attributes}")
            
            logger.info(
                f"Augmentation hoàn tất - "
                f"Facts: {len(results['memories'].entity.facts)}, "
                f"Preferences: {len(results['preferences'])}, "
                f"Attributes: {len(results['attributes'])}"
            )
            
        except Exception as e:
            logger.error(f"Augmentation pipeline thất bại: {e}")
        
        return results


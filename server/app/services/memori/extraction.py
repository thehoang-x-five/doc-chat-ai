"""
Extraction Service cho Memori.

Gộp từ:
- fact_extractor_service.py: Trích xuất Fact từ hội thoại
- embeddings.py: Generat và format vector embeddings

Module này xử lý việc trích xuất thông tin có cấu trúc từ văn bản và tạo vector embeddings.
"""

import logging
import struct
import asyncio
from typing import Any, List, Optional, Union, Dict

from app.services.infrastructure.ai_providers.manager import manager as ai_manager

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM Service adapter đơn giản cho Memori extraction.
    Wrap app.core.ai.manager để generation.
    """
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
    ) -> str:
        """Generate text sử dụng AI provider có sẵn."""
        try:
            # Lấy provider đang active hoặc provider khả dụng đầu tiên
            provider_name = ai_manager.get_active_provider()
            if not provider_name:
                available = ai_manager._get_available_providers()
                if available:
                    provider_name = available[0]
            
            if not provider_name:
                logger.warning("Không có AI providers nào khả dụng cho Memori extraction")
                return "NONE"
            
            provider = ai_manager.providers.get(provider_name)
            if not provider:
                return "NONE"
                
            messages = [{"role": "user", "content": prompt}]
            
            # Gọi provider (giả định generic chat_completion interface)
            # Hầu hết providers trong hệ thống này có thể hỗ trợ kwargs như temperature/max_tokens
            # nhưng BaseAIProvider interface có thể thay đổi. 
            # Chúng ta sẽ giữ theo interface cơ bản thấy trong AIProviderManager.enhance_text
            
            response = await provider.chat_completion(messages)
            return response
            
        except Exception as e:
            logger.error(f"LLM generation thất bại: {e}")
            return "NONE"



# =============================================================================
# EMBEDDINGS (từ embeddings.py)
# =============================================================================

def format_embedding_for_db(embedding: List[float], dialect: str = "postgresql") -> bytes:
    """Format embedding để lưu database dạng binary."""
    binary_data = struct.pack(f"<{len(embedding)}f", *embedding)
    
    if dialect == "mongodb":
        try:
            import bson
            return bson.Binary(binary_data)
        except ImportError:
            return binary_data
    return binary_data


def parse_embedding_from_db(raw: Any) -> List[float]:
    """Parse embedding từ format database."""
    import numpy as np
    
    if raw is None:
        return []
    
    if isinstance(raw, (bytes, memoryview)):
        arr = np.frombuffer(raw, dtype="<f4")
        return arr.tolist()
    elif isinstance(raw, str):
        import json
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        if hasattr(raw, "__bytes__"):
            arr = np.frombuffer(bytes(raw), dtype="<f4")
            return arr.tolist()
        return list(raw) if raw else []


from app.services.core.embedding_service import get_embedding_service

def embed_texts_sync(texts: Union[str, List[str]]) -> List[List[float]]:
    """Generate embeddings sử dụng EmbeddingService hiện có (sync)."""
    if isinstance(texts, str):
        texts = [texts]
    
    if not texts:
        return []
    
    service = get_embedding_service()
    embeddings, _ = service.embed_batch(texts)
    return embeddings


async def embed_texts_async(texts: Union[str, List[str]]) -> List[List[float]]:
    """Generate embeddings sử dụng EmbeddingService hiện có (async wrapper)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_texts_sync, texts)


# =============================================================================
# FACT EXTRACTION (từ fact_extractor_service.py)
# =============================================================================

class FactExtractor:
    """Trích xuất thông tin thực tế (factual information) từ hội thoại."""
    
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
    
    async def extract_from_conversation(
        self,
        user_message: str,
        ai_response: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> List[str]:
        """Trích xuất facts từ một lượt hội thoại."""
        try:
            # Xây dựng context từ lịch sử
            context = ""
            if conversation_history:
                recent = conversation_history[-3:]  # 3 tin nhắn cuối cùng làm context
                context = "\n".join([
                    f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
                    for m in recent
                ])
            
            # Prompt để trích xuất fact
            prompt = f"""Extract clear, factual information about the user from this conversation.
Only extract statements that are:
1. Factual (not opinions or questions)
2. About the user (preferences, information, context)
3. Likely to be useful for future conversations

Previous context:
{context}

Current conversation:
User: {user_message}
Assistant: {ai_response}

Extract facts as a list. Each fact should be a complete sentence.
If no clear facts, return "NONE".

Facts:"""

            # Gọi LLM
            response = await self.llm.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3,
            )
            
            # Parse response
            facts_text = response.strip()
            
            if facts_text.upper() == "NONE" or not facts_text:
                return []
            
            # Tách theo dòng mới và làm sạch
            facts = [
                f.strip().lstrip('-').lstrip('•').lstrip('*').strip()
                for f in facts_text.split('\n')
                if f.strip() and not f.strip().upper().startswith('NONE')
            ]
            
            # Lọc bỏ các facts rỗng hoặc quá ngắn
            facts = [f for f in facts if len(f) > 10]
            
            logger.info(f"Đã trích xuất {len(facts)} facts từ hội thoại")
            return facts
            
        except Exception as e:
            logger.error(f"Trích xuất facts thất bại: {e}")
            return []
    
    def calculate_importance(self, fact: str, user_message: str) -> float:
        """Tính toán điểm quan trọng cho một fact."""
        score = 5.0  # Điểm cơ sở
        
        # Hệ số độ dài
        if len(fact) > 100:
            score += 1.0
        elif len(fact) < 30:
            score -= 1.0
        
        # Keyword boosting
        high_importance_keywords = [
            'name', 'email', 'phone', 'address', 'birthday',
            'favorite', 'prefer', 'always', 'never', 'important'
        ]
        
        fact_lower = fact.lower()
        for keyword in high_importance_keywords:
            if keyword in fact_lower:
                score += 1.0
                break
        
        # Dấu hiệu quan trọng rõ ràng trong tin nhắn người dùng
        message_lower = user_message.lower()
        if any(word in message_lower for word in ['important', 'remember', 'note', 'don\'t forget']):
            score += 2.0
        
        # Giới hạn trong phạm vi hợp lệ
        return max(0.0, min(10.0, score))

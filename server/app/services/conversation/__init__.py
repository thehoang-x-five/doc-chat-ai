"""Các dịch vụ Hội thoại & Chat"""
from app.services.conversation.conversation_service import ConversationService
from app.services.conversation.chat_pipeline import ChatPipeline
from app.services.conversation.memory_service import MemoryManager
from app.services.conversation.intent_detector import IntentDetector
from app.services.conversation.intent_cache import IntentCache

# Backward compatibility alias
ChatService = ConversationService

__all__ = [
    "ConversationService",
    "ChatPipeline",
    "ChatService",  # backward compat
    "MemoryManager",
    "IntentDetector",
    "IntentCache",
]


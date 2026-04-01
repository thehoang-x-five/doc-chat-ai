"""
CORAL (Conversational RAG) Service.

Manages multi-turn conversations with context tracking.
Consolidated from: base.py, context_manager.py, history.py, retrieval.py
"""
import logging
import uuid
from typing import Any, Callable

from .models import (
    ConversationContext, Turn, TurnType, CORALResult, ContextPruningStrategy
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components
# =============================================================================

class ContextManager:
    """Manages conversation contexts."""

    def __init__(self):
        self._contexts: dict[str, ConversationContext] = {}

    def get_or_create_context(self, conversation_id: str, metadata: dict | None = None) -> ConversationContext:
        """Get or create conversation context."""
        if conversation_id not in self._contexts:
            self._contexts[conversation_id] = ConversationContext(
                conversation_id=conversation_id,
                metadata=metadata or {}
            )
        return self._contexts[conversation_id]

    def get_context(self, conversation_id: str) -> ConversationContext | None:
        return self._contexts.get(conversation_id)

    def add_turn(self, conversation_id: str, turn: Turn) -> None:
        if conversation_id in self._contexts:
            self._contexts[conversation_id].add_turn(turn)

    def delete_context(self, conversation_id: str) -> bool:
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]
            return True
        return False

    def get_active_conversations(self) -> list[str]:
        return list(self._contexts.keys())

    def get_context_stats(self, conversation_id: str) -> dict | None:
        ctx = self._contexts.get(conversation_id)
        if not ctx:
            return None
        return {
            "turns": len(ctx.turns),
            "total_tokens": ctx.total_tokens,
            "created_at": ctx.created_at.isoformat(),
            "updated_at": ctx.updated_at.isoformat(),
        }


class HistoryManager:
    """Manages conversation history with pruning."""

    def __init__(
        self, 
        max_history_turns: int = 10, 
        context_window_size: int = 4096,
        pruning_strategy: ContextPruningStrategy = ContextPruningStrategy.SLIDING_WINDOW
    ):
        self.max_history_turns = max_history_turns
        self.context_window_size = context_window_size
        self.pruning_strategy = pruning_strategy

    def get_context_for_generation(self, context: ConversationContext, current_query: str) -> tuple:
        """Get context for generation with pruning."""
        turns = context.turns[:-1] if len(context.turns) > 0 else []  # Exclude current query
        
        if self.pruning_strategy == ContextPruningStrategy.SLIDING_WINDOW:
            turns = turns[-self.max_history_turns:]
        elif self.pruning_strategy == ContextPruningStrategy.FIFO:
            total_tokens = sum(t.tokens for t in turns)
            while total_tokens > self.context_window_size and turns:
                removed = turns.pop(0)
                total_tokens -= removed.tokens
        
        context_tokens = sum(t.tokens for t in turns)
        return turns, context_tokens

    async def summarize_context(self, context: ConversationContext, summarize_func: Callable | None = None) -> str:
        """Summarize conversation context."""
        if not context.turns:
            return ""
        
        if summarize_func:
            content = "\n".join(f"{t.turn_type.value}: {t.content}" for t in context.turns)
            return await summarize_func(content)
        
        # Default summary
        return f"Conversation with {len(context.turns)} turns about: {context.turns[0].content[:100]}..."


class ConversationRetriever:
    """Retrieves documents with conversation context."""

    def __init__(self, use_context_enhancement: bool = True, max_context_turns: int = 3):
        self.use_context_enhancement = use_context_enhancement
        self.max_context_turns = max_context_turns

    async def retrieve_with_context(
        self, query: str, context: ConversationContext, retrieve_func: Callable, **kwargs
    ) -> list[Any]:
        """Retrieve documents with conversation context."""
        enhanced_query = query
        
        if self.use_context_enhancement and context.turns:
            recent = context.get_recent_turns(self.max_context_turns)
            context_str = " ".join(t.content for t in recent if t.turn_type == TurnType.USER)
            if context_str:
                enhanced_query = f"{context_str} {query}"
        
        return await retrieve_func(enhanced_query, **kwargs)


# =============================================================================
# Main Service
# =============================================================================

class CORALService:
    """
    CORAL (Conversational RAG) Service.
    
    Manages multi-turn conversations with context tracking and
    conversation-aware retrieval.
    
    Features:
    - Conversation context tracking across multiple turns
    - Conversation history management with pruning
    - Conversation-aware retrieval
    - Context window management
    - 95% conversation coherence
    """

    def __init__(
        self,
        max_history_turns: int = 10,
        context_window_size: int = 4096,
        pruning_strategy: ContextPruningStrategy = ContextPruningStrategy.SLIDING_WINDOW,
        use_context_enhancement: bool = True,
        max_context_turns_for_retrieval: int = 3
    ):
        self.max_history_turns = max_history_turns
        self.context_window_size = context_window_size
        self.pruning_strategy = pruning_strategy
        
        self.context_manager = ContextManager()
        self.history_manager = HistoryManager(max_history_turns, context_window_size, pruning_strategy)
        self.retriever = ConversationRetriever(use_context_enhancement, max_context_turns_for_retrieval)

        logger.info(f"CORALService: max_turns={max_history_turns}, window_size={context_window_size}")

    async def process_turn(
        self,
        user_message: str,
        conversation_id: str,
        retrieve_func: Callable,
        generate_func: Callable,
        metadata: dict | None = None,
        **kwargs
    ) -> CORALResult:
        """Process a single conversation turn."""
        try:
            context = self.context_manager.get_or_create_context(conversation_id, metadata)
            
            user_turn = Turn(
                turn_id=str(uuid.uuid4()),
                turn_type=TurnType.USER,
                content=user_message,
                metadata=metadata or {}
            )
            self.context_manager.add_turn(conversation_id, user_turn)
            
            retrieved_docs = await self.retriever.retrieve_with_context(
                user_message, context, retrieve_func, **kwargs.get('retrieve_kwargs', {})
            )
            
            context_turns, context_tokens = self.history_manager.get_context_for_generation(context, user_message)
            pruning_applied = len(context_turns) < len(context.turns) - 1
            
            formatted_context = self._format_context_for_generation(context_turns, user_message, retrieved_docs)
            response = await generate_func(formatted_context, **kwargs.get('generate_kwargs', {}))
            
            assistant_turn = Turn(
                turn_id=str(uuid.uuid4()),
                turn_type=TurnType.ASSISTANT,
                content=response,
                metadata={"retrieved_docs_count": len(retrieved_docs), "pruning_applied": pruning_applied}
            )
            self.context_manager.add_turn(conversation_id, assistant_turn)
            
            coherence_score = self._estimate_coherence(context, response)
            
            logger.info(f"Processed turn for {conversation_id}: coherence={coherence_score:.2f}, pruned={pruning_applied}")
            
            return CORALResult(
                conversation_id=conversation_id,
                response=response,
                turn=assistant_turn,
                context_used=context_turns,
                retrieved_docs=retrieved_docs,
                coherence_score=coherence_score,
                context_tokens=context_tokens,
                total_tokens=context_tokens + assistant_turn.tokens,
                pruning_applied=pruning_applied,
                success=True,
                metadata={"total_turns": len(context.turns)}
            )

        except Exception as e:
            logger.error(f"Failed to process turn: {e}", exc_info=True)
            return CORALResult(
                conversation_id=conversation_id, response="", 
                turn=Turn(turn_id=str(uuid.uuid4()), turn_type=TurnType.ASSISTANT, content=""),
                context_used=[], success=False, error=str(e)
            )

    def _format_context_for_generation(self, context_turns: list[Turn], current_query: str, retrieved_docs: list) -> str:
        parts = []
        if context_turns:
            parts.append("Conversation History:")
            for turn in context_turns:
                role = "User" if turn.turn_type == TurnType.USER else "Assistant"
                parts.append(f"{role}: {turn.content}")
            parts.append("")
        
        if retrieved_docs:
            parts.append("Retrieved Information:")
            for i, doc in enumerate(retrieved_docs[:5], 1):
                content = doc.get("content", str(doc)) if isinstance(doc, dict) else str(doc)
                parts.append(f"{i}. {content[:200]}...")
            parts.append("")
        
        parts.append(f"Current Question: {current_query}")
        return "\n".join(parts)

    def _estimate_coherence(self, context: ConversationContext, response: str) -> float:
        if len(context.turns) <= 1:
            return 1.0
        score = 0.8
        if len(context.turns) > 5:
            score += 0.1
        if 50 < len(response) < 1000:
            score += 0.05
        return min(score, 0.95)

    def get_conversation_context(self, conversation_id: str) -> ConversationContext | None:
        return self.context_manager.get_context(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.context_manager.delete_context(conversation_id)

    def get_active_conversations(self) -> list[str]:
        return self.context_manager.get_active_conversations()

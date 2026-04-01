"""
Hybrid RAG Service Pattern.
Wraps RAGAnything (LightRAG) as a standard pattern service.
"""
import logging
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

class HybridRAGService:
    """
    Hybrid RAG Service (RAGAnything Wrapper).
    Implements the standard pattern interface.
    """
    def __init__(self, raganything_instance: Any):
        self._rag_instance = raganything_instance
        self.name = "hybrid_rag"

    async def query(
        self,
        question: str,
        documents: list[Any] | None = None,
        **kwargs,
    ) -> Any:
        """
        Execute Hybrid RAG query.
        
        Args:
            question: User question
            documents: Optional documents (ignored for Hybrid as it does its own retrieval)
            **kwargs: Extra args
        """
        if not self._rag_instance:
            raise ValueError("RAGAnything instance not initialized")
            
        # Extract RAGAnything specific params
        mode = kwargs.get("mode", "hybrid")
        workspace_id = kwargs.get("workspace_id")
        
        logger.info(f"Running Hybrid RAG (mode={mode})...")
        
        # Call RAGAnything's aquery
        # RAGAnything returns a string response
        response = await self._rag_instance.aquery(
            query=question,
            mode=mode,
            # We pass kwargs down, RAGAnything should handle them
            **kwargs
        )
        
        return {
            "answer": response,
            "pattern": "hybrid",
            "metadata": {
                "mode": mode,
                "strategy": "hybrid_graph_vector"
            }
        }

    def _build_system_prompt(
        self,
        context_text: str,
        memory_context: Optional[str] = None,
    ) -> str:
        """
        Build system prompt using PromptBuilder if available, 
        otherwise fallback to inline Vietnamese prompt.
        Ensures memory_context is always injected.
        """
        try:
            from app.services.generation.prompt_builder import PromptBuilder, PromptType
            builder = PromptBuilder(language="vi")
            
            # Build using PromptBuilder — returns (system_prompt, user_prompt)
            # We only need the system_prompt here; user_prompt is built separately
            base_system = builder.get_system_prompt(PromptType.RAG, "vi")
            
            # Construct full system prompt with all context sections
            parts = [base_system, ""]
            
            if memory_context:
                parts.append("**Lịch sử hội thoại & Ngữ cảnh bộ nhớ:**")
                parts.append(memory_context)
                parts.append("")
            
            if context_text:
                parts.append("**Ngữ cảnh từ tài liệu:**")
                parts.append(context_text)
                parts.append("")
            
            return "\n".join(parts)
            
        except ImportError:
            logger.warning("PromptBuilder not available, using fallback prompt")
            
            # Fallback — Vietnamese inline prompt with memory support
            parts = [
                "Bạn là trợ lý AI hữu ích chuyên trả lời câu hỏi dựa trên tài liệu.",
                "Chỉ sử dụng thông tin từ ngữ cảnh được cung cấp.",
                "Nếu không đủ thông tin, nói rõ điều đó.",
                "Trích dẫn nguồn khi có thể.",
                "",
            ]
            
            if memory_context:
                parts.append("**Lịch sử hội thoại & Ngữ cảnh bộ nhớ:**")
                parts.append(memory_context)
                parts.append("")
            
            if context_text:
                parts.append("**Ngữ cảnh từ tài liệu:**")
                parts.append(context_text)
                parts.append("")
            
            return "\n".join(parts)

    def _build_messages(
        self,
        question: str,
        system_prompt: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> List[dict]:
        """
        Build the messages array for LLM, including conversation history.
        
        Args:
            question: Current user question
            system_prompt: Full system prompt with context
            conversation_history: Previous messages [{"role": "user/assistant", "content": "..."}]
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        # Inject conversation history (up to 10 recent messages)
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        
        # Current question
        messages.append({"role": "user", "content": question})
        
        return messages

    async def query_stream(
        self,
        question: str,
        retriever: Any = None,
        **kwargs,
    ) -> Any:
        """
        Execute Hybrid RAG query with REAL streaming.
        
        Strategy:
        1. Retrieve context (Async) - Uses `retriever` (Vector) for document chunks
        2. Build prompt with PromptBuilder + memory_context + conversation_history
        3. Stream generation (Async Generator) with full context
        """
        from app.services.infrastructure.ai_providers.manager import manager
        
        # Extract context from kwargs (passed by StreamManager)
        memory_context = kwargs.pop("memory_context", None)
        conversation_history = kwargs.pop("conversation_history", None)
        
        logger.info(
            f"Running Hybrid RAG Streaming "
            f"(memory={'yes' if memory_context else 'no'}, "
            f"history={len(conversation_history) if conversation_history else 0} msgs)..."
        )
        
        # ──────────────────────────────────────────────────────────────
        # 1. Retrieval Phase — Get relevant document chunks
        # ──────────────────────────────────────────────────────────────
        context_text = ""
        chunks = []
        
        if retriever:
            try:
                chunks = await retriever.retrieve(question, k=5)
                context_parts = []
                for chunk in chunks:
                    source = chunk.metadata.get('source', chunk.metadata.get('filename', 'unknown'))
                    context_parts.append(
                        f"Content: {chunk.content}\nSource: {source}"
                    )
                context_text = "\n\n".join(context_parts)
                logger.info(f"Retrieved {len(chunks)} chunks for streaming")
            except Exception as e:
                logger.warning(f"Retrieval failed during streaming: {e}")
        
        # ──────────────────────────────────────────────────────────────
        # 2. Build Prompt — Using PromptBuilder + memory + history
        # ──────────────────────────────────────────────────────────────
        # Use provided system_prompt if available (from ChatPipeline),
        # otherwise build a new one using available contexts.
        system_prompt = kwargs.pop("system_prompt", None)
        
        if not system_prompt:
            system_prompt = self._build_system_prompt(
                context_text=context_text,
                memory_context=memory_context,
            )
        elif memory_context and "**Lịch sử hội thoại & Ngữ cảnh bộ nhớ:**" not in system_prompt:
            # If prompt provided but missing memory and we have memory, append it
            system_prompt += f"\n\n**Lịch sử hội thoại & Ngữ cảnh bộ nhớ:**\n{memory_context}"
        
        messages = self._build_messages(
            question=question,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )
        
        logger.info(
            f"Prompt built: system={len(system_prompt)} chars, "
            f"messages={len(messages)} entries"
        )
        
        # ──────────────────────────────────────────────────────────────
        # 3. Streaming Generation Phase
        # ──────────────────────────────────────────────────────────────
        async for chunk in manager.stream_chat_completion(messages, **kwargs):
            yield chunk  # Yields text strings
        
        # ──────────────────────────────────────────────────────────────
        # 4. Yield Citations Metadata
        # ──────────────────────────────────────────────────────────────
        final_citations = []
        if chunks:
            for chunk in chunks:
                final_citations.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "content": chunk.content,
                    "score": chunk.score,
                    "document_title": chunk.metadata.get("filename", "Unknown")
                })
        
        yield {"citations": final_citations}

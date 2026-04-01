"""
RAG Service Wrappers.
Factory functions to create wrappers for LLM, Vision, Embedding, and Retrieval.
"""
import logging
import asyncio
from typing import Any, Callable, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.core.rag.types import RAGResponse
from app.services.rag_patterns.pipeline.resilience import async_retry

logger = logging.getLogger(__name__)

def create_llm_wrapper(ai_manager: Any, generate_answer_func: Callable) -> Callable:
    """
    Create LLM wrapper for RAGAnything and Patterns.
    Adapts AIProviderManager.generate_completion(messages, model) to the
    RAG wrapper interface that takes (prompt, system_prompt, history, documents).
    """
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def llm_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        documents: list[Any] | None = None,
        **kwargs,
    ) -> str:
        """LLM wrapper implementing the RAGAnything interface."""
        
        # 1. Extract context from kwargs (injected by Orchestrator)
        orchestrator_context = kwargs.get("context", {}) or {}
        if isinstance(orchestrator_context, dict):
            memory_context = orchestrator_context.get("memory_context", "")
            conversation_history = orchestrator_context.get("conversation_history")
        else:
            memory_context = ""
            conversation_history = None

        # 2. Format documents into string
        doc_context = ""
        if documents:
            doc_parts = []
            for d in documents:
                if hasattr(d, 'page_content'):
                    doc_parts.append(d.page_content)
                elif isinstance(d, dict):
                    doc_parts.append(str(d.get('content', d)))
                else:
                    doc_parts.append(str(d))
            doc_context = "\n\n".join(doc_parts)
        
        # 3. Combine contexts
        full_context = ""
        if memory_context:
            full_context += f"[Memory Context]\n{memory_context}\n\n"
        if doc_context:
            full_context += f"[Retrieved Documents]\n{doc_context}\n\n"
        
        # Fallback to history from args if not in context
        final_history = history_messages or conversation_history
            
        # 4. Build messages list for AIProviderManager.generate_completion
        messages = []
        
        # System prompt
        sys_content = system_prompt or "You are a helpful AI assistant. Answer based on the provided context."
        if full_context:
            sys_content += f"\n\nContext:\n{full_context}"
        messages.append({"role": "system", "content": sys_content})
        
        # Conversation history
        if final_history:
            for msg in final_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role and content:
                    messages.append({"role": role, "content": content})
        
        # User question
        messages.append({"role": "user", "content": prompt})
        
        # 5. Call AIProviderManager.generate_completion(messages, model)
        #    Returns: (response_text, provider_name, model_name)
        try:
            answer, provider, model = await generate_answer_func(
                messages=messages,
                model=kwargs.get("model"),
            )
            logger.debug(f"RAG LLM via {provider} ({model})")
            return answer
        except Exception as e:
            logger.error(f"LLM wrapper generate failed: {e}")
            raise

    return llm_func

def create_vision_wrapper(generate_answer_func: Callable) -> Callable:
    """
    Create Vision wrapper for RAGAnything.
    Adapts AIProviderManager.generate_completion(messages, model) interface.
    """
    # Fallback chain for Vision models
    VISION_MODELS = [
        "gemini-3-pro-image",  # Cloud Code
        "gemini-2.5-pro",
        "gemini-2.5-flash", 
        None,                  # Auto
    ]

    @async_retry(max_attempts=3, base_delay=1.5, max_delay=30.0)
    async def vision_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        image_data: str | None = None,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> str:
        """Vision wrapper implementing the RAGAnything interface."""
        # Build messages for generate_completion
        built_messages = []
        if system_prompt:
            built_messages.append({"role": "system", "content": system_prompt})
        built_messages.append({"role": "user", "content": prompt})

        # Case 1: Pure text
        if not messages and not image_data:
            answer, _, _ = await generate_answer_func(
                messages=built_messages,
                model=kwargs.get("model"),
            )
            return answer

        # Case 2: Vision processing
        last_error = None
        for vision_model in VISION_MODELS:
            try:
                answer, provider, model = await generate_answer_func(
                    messages=built_messages,
                    model=vision_model,
                )
                logger.debug(f"RAG Vision via {provider} ({model})")
                return answer
            except Exception as e:
                last_error = e
                continue

        logger.error(f"All vision models failed: {last_error}")
        return "Unable to process image at this time."

    return vision_func

def create_embedding_wrapper(embedding_service: Any):
    """
    Create Embedding wrapper for RAGAnything.
    """
    from lightrag.utils import EmbeddingFunc

    @async_retry(max_attempts=3, base_delay=0.5, max_delay=15.0)
    async def embed_texts(texts: list[str]) -> list[list[float]]:
        if embedding_service is None:
            # Dummy embedding for testing
            return [[0.0] * 768 for _ in texts]
        return [embedding_service.embed_text(t) for t in texts]

    embedding_dim = 768 if embedding_service is None else embedding_service.dimension

    return EmbeddingFunc(
        embedding_dim=embedding_dim,
        max_token_size=8192,
        func=embed_texts,
    )

def create_retriever_wrapper(session: AsyncSession, embedding_service: Any) -> Callable:
    """
    Create Retriever wrapper for RAGAnything and Patterns.
    """
    async def retrieve_func(
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> list:
        """
        Retrieval function implementing the standard interface.
        """
        # Workspace ID is mandatory
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            logger.warning("No workspace_id for retrieval")
            return []
        
        if session is None:
            logger.warning("No database session for retrieval")
            return []
        
        try:
            # FIX: Use Real RetrieverService
            from app.services.core.retriever_service import RetrieverService
            
            retriever = RetrieverService(
                session=session,
                embedding_service=embedding_service,
            )
            
            document_ids = kwargs.get("document_ids")
            tags = kwargs.get("tags")
            min_score = kwargs.get("min_score", 0.0)
            
            results = await retriever.search(
                query=query,
                workspace_id=workspace_id,
                top_k=top_k,
                min_score=min_score,
                document_ids=document_ids,
                tags=tags,
            )
            
            # Format for patterns
            documents = []
            for r in results:
                documents.append({
                    "content": r.content,
                    "score": r.score,
                    "metadata": {
                        "chunk_id": str(r.chunk_id),
                        "document_id": str(r.document_id),
                        "document_title": r.document_title,
                        "page_start": r.page_start,
                        "page_end": r.page_end,
                        "section_title": r.section_title,
                    }
                })
            
            logger.debug(f"Retrieved {len(documents)} chunks for: {query[:50]}...")
            return documents
            
        except Exception as e:
            logger.error(f"Retriever wrapper error: {e}")
            return []
        
    return retrieve_func

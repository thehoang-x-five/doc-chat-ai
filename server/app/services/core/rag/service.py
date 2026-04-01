"""
Unified RAG Service.
Main entry point for all RAG operations.
"""
import asyncio
import logging
from typing import Any, Callable, Optional, AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.infrastructure.ai_providers.manager import AIProviderManager
from app.services.core.rag.types import RAGResponse
from app.services.core.rag.factory import (
    initialize_raganything,
    initialize_patterns,
    initialize_orchestration
)
from app.services.core.rag.utils import convert_to_response
from app.services.core.rag.wrappers import create_llm_wrapper, create_retriever_wrapper

logger = logging.getLogger(__name__)

class RAGService:
    """
    Unified RAG Service.
    Manages RAGAnything, Patterns, and Orchestration.
    """
    _instance: Optional["RAGService"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _initialized: bool = False

    def __new__(cls) -> "RAGService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_init_done"):
            return
        self._init_done = True
        
        self._raganything = None
        self._patterns = {} # Stores all pattern services
        
        self._pattern_registry = None
        self._query_analyzer = None
        self._pattern_orchestrator = None
        
        self._session: AsyncSession | None = None
        self._ai_manager = None
        self._embedding_service = None
        
        self._working_dir: Path = settings.STORAGE_DIR / "rag_storage"
        self._parser: str = getattr(settings, "DEFAULT_PARSER", "auto")
        self._parse_method: str = getattr(settings, "DEFAULT_PARSE_METHOD", "auto")

    @classmethod
    async def get_instance(cls, session: AsyncSession | None = None) -> "RAGService":
        instance = cls()
        async with cls._lock:
            if not cls._initialized:
                if session is None:
                    raise ValueError("Database session required for first initialization")
                await instance._initialize(session)
                cls._initialized = True
            elif session is not None:
                instance._session = session
        return instance

    async def _ensure_valid_session(self) -> bool:
        if self._session is None:
            return False
        try:
            if not self._session.is_active:
                logger.warning("Session inactive, rolling back...")
                await self._session.rollback()
            return True
        except Exception as e:
            logger.error(f"Session check error: {e}")
            return False

    async def _initialize(self, session: AsyncSession) -> None:
        logger.info("Initializing RAG Service (Refactored)...")
        self._session = session
        
        # 1. AI Manager
        if not self._ai_manager:
            self._ai_manager = AIProviderManager()

        # 2. Embedding Service
        if self._embedding_service is None:
            try:
                from app.services.core.embedding_service import get_embedding_service
                self._embedding_service = get_embedding_service()
            except Exception:
                logger.warning("EmbeddingService failed to init, using defaults")

        try:
            # 3. RAGAnything
            self._raganything = await initialize_raganything(
                working_dir=self._working_dir,
                parser=self._parser,
                parse_method=self._parse_method,
                ai_manager=self._ai_manager,
                embedding_service=self._embedding_service
            )

            # 4. Patterns
            # Create wrappers for patterns if needed
            wrappers = {
                "vision_func": None # Add vision wrapper if needed separately
                # Note: Factory handles creation inside initialize_raganything for RAGAnything
                # But initialize_patterns might need them too.
            }
            # For REVEAL, we need a vision wrapper factory or instance
            # pass create_vision_wrapper function? No, factory.py imports it.
            # We just need to pass services.
            
            # Re-create wrappers map for factory if it needs specific instances
            # But factory.py imports create_*_wrapper directly.
            # It mainly needs services.
            
            self._patterns = await initialize_patterns(
                raganything_instance=self._raganything,
                embedding_service=self._embedding_service,
                wrappers=wrappers
            )

            # 5. Orchestration
            (self._pattern_registry, 
             self._query_analyzer, 
             self._pattern_orchestrator) = initialize_orchestration(self._patterns)
            
            logger.info("RAG Service initialized successfully")

        except Exception as e:
            logger.error(f"RAG Service init failed: {e}")
            raise

    # =========================================================================
    # Public API
    # =========================================================================

    async def query(
        self,
        question: str,
        pattern: str = "auto",
        context: dict | None = None,
        **kwargs,
    ) -> RAGResponse:
        """Main query method."""
        await self._ensure_valid_session()
        
        # Inject dependencies into kwargs/context for Orchestrator/Wrappers
        if "workspace_id" in kwargs:
            # Ensure workspace_id is passed correctly
            pass
            
        # Default Wrapper injection (if not provided)
        # Orchestrator might use them
        if "generate_func" not in kwargs and self._ai_manager:
            bound_generate = self._ai_manager.generate_completion
            kwargs["generate_func"] = create_llm_wrapper(self._ai_manager, bound_generate)
            
        if "retrieve_func" not in kwargs:
            # Create Real Retriever
            kwargs["retrieve_func"] = create_retriever_wrapper(
                self._session, 
                self._embedding_service
            )

        # Simplify Query Rewriting (Step-Back) - Keep basic logic or improve
        # For now, let's keep it minimal to focus on architecture
        
        try:
            # Map "hybrid" to "hybrid_rag" pattern service
            used_pattern = pattern
            orchestrate_patterns = None
            
            if pattern == "auto":
                # Let orchestrator decide
                pass
            elif pattern == "hybrid":
                orchestrate_patterns = ["hybrid_rag"] # Matches name in factory/hybrid.py
                used_pattern = "hybrid"
            else:
                # Map old names to service keys
                # corrective -> corrective_rag
                key = f"{pattern}_rag" if not pattern.endswith("rag") and pattern != "coral" and pattern != "reveal" else pattern
                if pattern == "semantic": key = "semantic_highlight"
                
                # Check if key exists in services
                if key not in self._patterns and pattern in self._patterns:
                    key = pattern
                
                orchestrate_patterns = [key]

            # 1. Analyze Query
            characteristics = self._query_analyzer.analyze(question, context)
            
            # 2. Recommend Patterns (if not manually specified)
            recommended_patterns = orchestrate_patterns
            if not recommended_patterns:
                 recommended_patterns = self._query_analyzer.recommend_patterns(characteristics)
            
            # 3. Select Strategy
            strategy = self._pattern_orchestrator.select_optimal_strategy(
                characteristics,
                recommended_patterns,
            )
            
            # 4. Execute via Orchestrator
            result_obj = await self._pattern_orchestrator.orchestrate(
                query=question,
                pattern_services=self._patterns,
                strategy=strategy, 
                patterns=recommended_patterns, # If hybrid/auto, uses recommended
                context=context,
                **kwargs
            )

            # Convert result
            # Orhcestrator returns specific result object
            # We need to extract info
            
            # _orchestrated_query in original file returned a dict with "result", "patterns", "strategy"
            # But here `orchestrate` returns `OrchestrationResult`
            
            final_result = result_obj.final_result
            executed_patterns = result_obj.patterns_executed
            
            if pattern == "auto" and executed_patterns:
                used_pattern = f"auto({executed_patterns[0]})"
                
            response = convert_to_response(final_result, used_pattern, self._ai_manager)
            return response

        except Exception as e:
            logger.error(f"Query failed: {e}")
            if self._session:
                 await self._session.rollback()
            raise

    async def query_stream(
        self,
        question: str,
        pattern: str = "auto",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream query response.
        Prioritizes REAL streaming from pattern if available.
        """
        await self._ensure_valid_session()
        
        # 1. Setup Retriever (Shared)
        # We create a retriever wrapper to pass to patterns that need it (like Hybrid)
        # This allows Hybrid pattern to do Vector Search + Stream Gen
        retriever_wrapper = create_retriever_wrapper(
            self._session, 
            self._embedding_service
        )
        kwargs["retriever"] = retriever_wrapper
        
        # 2. Determine Pattern Service
        target_pattern_key = "hybrid_rag" # Default
        
        if pattern != "auto":
             # Normalize pattern name logic (copied from query)
             key = f"{pattern}_rag" if not pattern.endswith("rag") and pattern not in ["coral", "reveal"] else pattern
             if pattern == "semantic": key = "semantic_highlight"
             
             if key in self._patterns:
                 target_pattern_key = key
             elif pattern in self._patterns:
                 target_pattern_key = pattern
        
        # 3. Try Pattern Streaming
        if target_pattern_key in self._patterns:
            service = self._patterns[target_pattern_key]
            if hasattr(service, 'query_stream'):
                logger.info(f"Delegating streaming to {target_pattern_key}")
                try:
                    async for chunk in service.query_stream(question, **kwargs):
                        yield chunk
                    return
                except Exception as e:
                    logger.error(f"Streaming failed in {target_pattern_key}: {e}")
                    # Fallback to simulated
            else:
                logger.warning(f"Pattern {target_pattern_key} does not support query_stream, falling back")
        
        # 4. Fallback to Simulated Streaming (Chunking)
        # This handles cases where pattern doesn't support streaming or it failed
        logger.info("Falling back to simulated streaming (chunking)")
        
        # Run query once to get full text
        response = await self.query(question, pattern, **kwargs)
        text = response.answer
        
        # Simulate streaming with small chunks
        chunk_size = 5  # Small chunks for smoother feel
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
            await asyncio.sleep(0.01)  # Minimal delay
            
        # Yield Citations (if any)
        if hasattr(response, 'citations') and response.citations:
            citations_data = [
                {
                    "chunk_id": str(c.chunk_id) if hasattr(c, 'chunk_id') else '',
                    "document_id": str(c.document_id) if hasattr(c, 'document_id') else '',
                    "document_title": c.document_title if hasattr(c, 'document_title') else "",
                    "content": c.content if hasattr(c, 'content') else "",
                    "page": c.page if hasattr(c, 'page') else None,
                    "score": c.score if hasattr(c, 'score') else 0.0,
                }
                for c in response.citations
            ]
            yield {"citations": citations_data}


    async def graph_query(
        self,
        question: str,
        workspace_id: Any, # UUID
        mode: str = "hybrid",
        **kwargs
    ) -> str:
        """
        Direct access to Graph RAG query (RAGAnything).
        Used by HybridRetriever and other components requiring direct graph access.
        """
        await self._ensure_valid_session()
        
        if not self._raganything:
            logger.warning("RAGAnything not initialized")
            return ""

        try:
            # RAGAnything (LightRAG) query
            response = await self._raganything.aquery(
                query=question,
                mode=mode, 
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return ""

    # =========================================================================
    # Pattern-Specific Facades (Backward Compatibility)
    # =========================================================================
    
    async def query_with_corrective_rag(self, question: str, documents: list[Any], **kwargs):
        return await self._patterns["corrective_rag"].query(question, documents, **kwargs)

    async def query_with_self_rag(self, question: str, documents: list[Any], **kwargs):
        return await self._patterns["self_rag"].query(question, documents, **kwargs)

    async def query_with_adaptive_rag(self, question: str, documents: list[Any], **kwargs):
        return await self._patterns["adaptive_rag"].query(question, documents, **kwargs)

    async def query_with_corag(self, question: str, documents: list[Any], **kwargs):
        return await self._patterns["corag"].query(question, documents, **kwargs)
        
    async def query_with_coral(self, user_message: str, conversation_id: str, **kwargs):
        # Fix DEFAULT RETRIEVER here
        retrieve_func = kwargs.get("retrieve_func")
        if retrieve_func is None:
             kwargs["retrieve_func"] = create_retriever_wrapper(self._session, self._embedding_service)
        
        if "generate_func" not in kwargs:
             # Default generate func
             bound_generate = self._ai_manager.generate_completion
             kwargs["generate_func"] = create_llm_wrapper(self._ai_manager, bound_generate)

        return await self._patterns["coral"].process_turn(
            user_message=user_message,
            conversation_id=conversation_id,
            **kwargs
        )

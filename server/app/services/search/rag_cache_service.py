"""
Semantic cache cho RAG responses sử dụng GPTCache.

Cache các RAG responses với semantic similarity matching, để các câu hỏi tương tự
có thể retrieve cached responses ngay cả khi không khớp chính xác.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RAGCache:
    """
    Semantic cache cho RAG responses sử dụng GPTCache.
    
    Tính năng:
    - Semantic similarity matching (không phải exact match)
    - Tự động tìm các queries tương tự
    - Similarity threshold có thể cấu hình
    - SQLite + Faiss storage backend
    """
    
    _initialized = False
    _cache = None
    
    @classmethod
    def initialize(cls) -> None:
        """
        Khởi tạo GPTCache (gọi một lần khi startup).
        
        Thiết lập:
        - ONNX embedding model cho semantic similarity
        - SQLite cho metadata storage
        - Faiss cho vector storage
        - Similarity evaluation với distance threshold
        """
        if cls._initialized:
            return
        
        try:
            from gptcache import cache
            from gptcache.manager import get_data_manager, CacheBase, VectorBase
            from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation
            from app.services.core.embedding_service import get_embedding_service
            
            logger.info("Initializing RAG semantic cache (shared embedding service)...")
            
            # Sử dụng shared EmbeddingService thay vì ONNX model riêng
            embedding_service = get_embedding_service()
            dimension = embedding_service.dimension
            
            # Định nghĩa embedding function wrapper cho GPTCache
            def to_embeddings(text):
                # GPTCache expects text -> vector
                embedding, _ = embedding_service.embed_text(text)
                return embedding
            
            # Setup storage (SQLite + Faiss)
            data_manager = get_data_manager(
                CacheBase("sqlite"),  # Metadata storage
                VectorBase("faiss", dimension=dimension)  # Vector storage
            )
            
            # Khởi tạo cache với similarity evaluation
            cache.init(
                embedding_func=to_embeddings,
                data_manager=data_manager,
                similarity_evaluation=SearchDistanceEvaluation(),
            )
            
            cls._cache = cache
            cls._initialized = True
            logger.info("✅ RAG semantic cache initialized successfully (shared model)")
            
        except ImportError as e:
            logger.warning(f"GPTCache not available: {e}")
            logger.warning("Install with: pip install gptcache")
            cls._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize RAG cache: {e}")
            cls._initialized = False
    
    @classmethod
    def get(cls, workspace_id: str, question: str) -> Optional[dict]:
        """
        Lấy cached RAG response cho query tương tự.
        
        Sử dụng semantic similarity để tìm cached responses cho các câu hỏi tương tự,
        không chỉ exact matches.
        
        Args:
            workspace_id: Workspace UUID string
            question: Câu hỏi của user
            
        Returns:
            Cached response dict hoặc None nếu không tìm thấy
        """
        if not cls._initialized or cls._cache is None:
            return None
        
        try:
            from gptcache import cache
            
            # Tạo cache key
            cache_key = f"{workspace_id}:{question}"
            
            # Safe attempt to get from cache
            # Some versions might differ in API
            if hasattr(cache, 'get'):
                result = cache.get(cache_key)
                if result:
                    logger.info(f"🎯 RAG cache HIT: {question[:50]}...")
                    return result
            
            return None
            
        except Exception as e:
            logger.debug(f"RAG cache get skipped: {e}")
            return None
    
    @classmethod
    def set(cls, workspace_id: str, question: str, response: dict) -> None:
        """
        Lưu trữ RAG response trong semantic cache.
        """
        if not cls._initialized or cls._cache is None:
            return
        
        try:
            from gptcache import cache
            
            # Tạo cache key
            cache_key = f"{workspace_id}:{question}"
            
            if hasattr(cache, 'set'):
                cache.set(cache_key, response)
                logger.debug(f"RAG cached: {question[:50]}...")
                
        except Exception as e:
            logger.debug(f"RAG cache set skipped: {e}")
    
    @classmethod
    def clear(cls) -> None:
        """Xóa tất cả cache entries (cho testing)."""
        if not cls._initialized or cls._cache is None:
            return
        
        try:
            from gptcache import cache
            cache.flush()
            logger.info("Cleared RAG cache")
        except Exception as e:
            logger.warning(f"RAG cache clear error: {e}")


# Khởi tạo khi load module
RAGCache.initialize()

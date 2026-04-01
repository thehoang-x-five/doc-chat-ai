"""
Service quản lý Embedding cho RAG Pipeline.
Hỗ trợ cả sentence-transformers và Ollama với khả năng versioning model.
"""
import hashlib
import logging
import uuid
from typing import List, Optional, Dict, Any, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingModelInfo:
    """Thông tin chi tiết về một model embedding."""
    
    def __init__(
        self,
        model_id: uuid.UUID,
        name: str,
        provider: str,
        dimension: int,
        is_default: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.model_id = model_id
        self.name = name
        self.provider = provider
        self.dimension = dimension
        self.is_default = is_default
        self.config = config or {}


class EmbeddingService:
    """
    Service tạo text embeddings với hỗ trợ versioning.
    Backend hỗ trợ: sentence-transformers, Ollama.
    """
    
    def __init__(
        self,
        model_name: str = None,
        dimension: int = 768,
        batch_size: int = 32,
        cache_enabled: bool = True,
    ):
        """
        Khởi tạo embedding service.
        
        Args:
            model_name: Tên model (mặc định lấy từ settings)
            dimension: Số chiều vector
            batch_size: Kích thước batch khi xử lý hàng loạt
            cache_enabled: Bật/tắt caching cho embedding
        """
        self.model_name = model_name or settings.OLLAMA_EMBED_MODEL
        self.dimension = dimension
        self.batch_size = batch_size
        self.cache_enabled = cache_enabled
        
        # Cache lưu embedding (text hash -> vector)
        self._cache: Dict[str, List[float]] = {}
        
        # Registry lưu thông tin các model đã load
        self._model_registry: Dict[str, EmbeddingModelInfo] = {}
        self._default_model: Optional[EmbeddingModelInfo] = None
        
        # Thử load sentence-transformers trước
        self._st_model = None
        self._st_models: Dict[str, Any] = {}  # Cache các model ST đã load
        self._use_ollama = True
        
        try:
            import sentence_transformers
            st_model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            self._use_ollama = False
            self.dimension = 384  # paraphrase-multilingual-MiniLM-L12-v2 dimension
            logger.info(f"Đã phát hiện sentence-transformers. Sẽ lazy-load model: {st_model_name} khi cần")
            
            # Thiết lập thông tin model mặc định
            self._default_model = EmbeddingModelInfo(
                model_id=uuid.uuid4(),  # Sẽ được thay thế bằng DB ID thực tế
                name="paraphrase-multilingual-MiniLM-L12-v2",
                provider="sentence-transformers",
                dimension=self.dimension,
                is_default=True,
            )
        except ImportError:
            logger.info("sentence-transformers không có sẵn, sử dụng Ollama")
        except Exception as e:
            logger.info(f"Không thể kiểm tra trạng thái sentence-transformers, sử dụng Ollama: {e}")
    
    def ensure_model_loaded(self) -> None:
        """
        Eagerly load the SentenceTransformer model into memory.
        Called from lifespan startup (after healthcheck passes) to avoid cold-start.
        """
        if self._use_ollama or self._st_model is not None:
            return  # Already loaded or using Ollama
        
        try:
            from sentence_transformers import SentenceTransformer
            st_model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            logger.info(f"Loading SentenceTransformer model: {st_model_name}...")
            self._st_model = SentenceTransformer(st_model_name)
            self._st_models[st_model_name] = self._st_model
            self.dimension = self._st_model.get_sentence_embedding_dimension()
            if self._default_model:
                self._default_model.dimension = self.dimension
            logger.info(f"SentenceTransformer model loaded successfully (dim={self.dimension})")
        except Exception as e:
            logger.warning(f"Failed to load SentenceTransformer, falling back to Ollama: {e}")
            self._use_ollama = True
    
    def _compute_cache_key(self, text: str, model_id: Optional[uuid.UUID] = None) -> str:
        """Tạo cache key dựa trên text content và model ID."""
        key_str = f"{model_id or 'default'}:{text}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()
    
    def get_model_info(self, model_id: Optional[uuid.UUID] = None) -> EmbeddingModelInfo:
        """
        Lấy thông tin model embedding.
        
        Args:
            model_id: ID cụ thể của model, hoặc None để lấy mặc định
            
        Returns:
            Object EmbeddingModelInfo
        """
        if model_id and str(model_id) in self._model_registry:
            return self._model_registry[str(model_id)]
        
        # Trả về model mặc định hoặc tạo fallback
        if self._default_model:
            return self._default_model
        
        # Model fallback khi chưa có gì được load
        return EmbeddingModelInfo(
            model_id=uuid.uuid4(),
            name=self.model_name or "default",
            provider="ollama" if self._use_ollama else "sentence-transformers",
            dimension=self.dimension,
            is_default=True,
        )
    
    def register_model(self, model_info: EmbeddingModelInfo) -> None:
        """
        Đăng ký một model mới vào service registry.
        
        Args:
            model_info: Thông tin model cần đăng ký
        """
        self._model_registry[str(model_info.model_id)] = model_info
        if model_info.is_default:
            self._default_model = model_info
    
    def embed_text(
        self, 
        text: str, 
        model_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[float], EmbeddingModelInfo]:
        """
        Tạo vector embedding cho một đoạn văn bản.
        
        Args:
            text: Văn bản cần embed
            model_id: Model cụ thể cần dùng, hoặc None
            
        Returns:
            Tuple (vector embedding, thông tin model đã dùng)
        """
        model_info = self.get_model_info(model_id)
        
        if not text or not text.strip():
            return [0.0] * model_info.dimension, model_info
        
        # Kiểm tra cache
        if self.cache_enabled:
            cache_key = self._compute_cache_key(text, model_info.model_id)
            if cache_key in self._cache:
                return self._cache[cache_key], model_info
        
        # Tạo embedding dựa trên provider
        if model_info.provider == "sentence-transformers":
            embedding = self._embed_with_st(text, model_info)
        elif model_info.provider == "ollama":
            embedding = self._embed_with_ollama(text, model_info)
        else:
            # Fallback về hành vi mặc định
            if self._st_model is not None:
                embedding = self._embed_with_st(text, model_info)
            else:
                embedding = self._embed_with_ollama(text, model_info)
        
        # Lưu vào cache
        if self.cache_enabled:
            self._cache[cache_key] = embedding
        
        return embedding, model_info
    
    def embed_text_simple(self, text: str) -> List[float]:
        """
        Tạo embedding đơn giản (wrapper cho tương thích ngược).
        
        Args:
            text: Văn bản đầu vào
            
        Returns:
            List các số thực (vector)
        """
        embedding, _ = self.embed_text(text)
        return embedding
    
    def embed_batch(
        self, 
        texts: List[str],
        model_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[List[float]], EmbeddingModelInfo]:
        """
        Tạo embedding cho một danh sách văn bản (xử lý hàng loạt).
        
        Args:
            texts: List các văn bản
            model_id: Model cần dùng
            
        Returns:
            Tuple (list các vectors, thông tin model)
        """
        model_info = self.get_model_info(model_id)
        
        if not texts:
            return [], model_info
        
        # Kiểm tra cache cho từng text
        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []
        
        if self.cache_enabled:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results[i] = [0.0] * model_info.dimension
                else:
                    cache_key = self._compute_cache_key(text, model_info.model_id)
                    if cache_key in self._cache:
                        results[i] = self._cache[cache_key]
                    else:
                        texts_to_embed.append(text)
                        indices_to_embed.append(i)
        else:
            texts_to_embed = texts
            indices_to_embed = list(range(len(texts)))
        
        # Chạy embedding cho những text chưa có trong cache
        if texts_to_embed:
            if model_info.provider == "sentence-transformers":
                embeddings = self._embed_batch_with_st(texts_to_embed, model_info)
            elif model_info.provider == "ollama":
                embeddings = self._embed_batch_with_ollama(texts_to_embed, model_info)
            else:
                if self._st_model is not None:
                    embeddings = self._embed_batch_with_st(texts_to_embed, model_info)
                else:
                    embeddings = self._embed_batch_with_ollama(texts_to_embed, model_info)
            
            # Lưu kết quả và update cache
            for i, embedding in zip(indices_to_embed, embeddings):
                results[i] = embedding
                if self.cache_enabled:
                    cache_key = self._compute_cache_key(texts[i], model_info.model_id)
                    self._cache[cache_key] = embedding
        
        # Pad vectors to exactly 768 dimensions for PostgreSQL Vector(768) compatibility
        for i in range(len(results)):
            if results[i] and len(results[i]) < 768:
                results[i].extend([0.0] * (768 - len(results[i])))
            elif results[i] and len(results[i]) > 768:
                results[i] = results[i][:768]
                
        return results, model_info
    
    def embed_batch_simple(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embedding đơn giản (wrapper cho tương thích ngược).
        """
        embeddings, _ = self.embed_batch(texts)
        return embeddings
    
    def _get_st_model(self, model_info: EmbeddingModelInfo):
        """Lấy hoặc load model sentence-transformers."""
        model_name = model_info.name
        if model_name not in self._st_models:
            try:
                from sentence_transformers import SentenceTransformer
                full_name = f"sentence-transformers/{model_name}" if "/" not in model_name else model_name
                self._st_models[model_name] = SentenceTransformer(full_name)
            except Exception as e:
                logger.error(f"Lỗi khi load ST model {model_name}: {e}")
                return self._st_model  # Fallback về default
        return self._st_models[model_name]
    
    def _embed_with_st(self, text: str, model_info: EmbeddingModelInfo) -> List[float]:
        """Tạo embedding dùng thư viện sentence-transformers."""
        model = self._get_st_model(model_info)
        if model is None:
            return [0.0] * model_info.dimension
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def _embed_batch_with_st(self, texts: List[str], model_info: EmbeddingModelInfo) -> List[List[float]]:
        """Batch embedding dùng sentence-transformers (có hỗ trợ GPU batching)."""
        model = self._get_st_model(model_info)
        if model is None:
            return [[0.0] * model_info.dimension for _ in texts]
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return [e.tolist() for e in embeddings]
    
    def _embed_with_ollama(self, text: str, model_info: EmbeddingModelInfo) -> List[float]:
        """Tạo embedding thông qua Ollama API."""
        try:
            model_name = model_info.config.get("ollama_model", self.model_name)
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/embeddings",
                json={
                    "model": model_name,
                    "prompt": text,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])
            
            # Padding hoặc cắt bớt (truncate) để khớp số chiều dimension
            if len(embedding) < model_info.dimension:
                embedding.extend([0.0] * (model_info.dimension - len(embedding)))
            elif len(embedding) > model_info.dimension:
                embedding = embedding[:model_info.dimension]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Lỗi Ollama embedding: {e}")
            return [0.0] * model_info.dimension
    
    def _embed_batch_with_ollama(self, texts: List[str], model_info: EmbeddingModelInfo) -> List[List[float]]:
        """Batch embedding với Ollama (Chạy tuần tự do API hạn chế)."""
        # Ollama hiện chưa hỗ trợ batch native tốt, nên loop tuần tự
        return [self._embed_with_ollama(text, model_info) for text in texts]
    
    def clear_cache(self) -> None:
        """Xóa toàn bộ cache embedding."""
        self._cache.clear()
    
    @property
    def cache_size(self) -> int:
        """Lấy kích thước cache hiện tại."""
        return len(self._cache)
    
    @property
    def default_model_info(self) -> Optional[EmbeddingModelInfo]:
        """Lấy thông tin model mặc định."""
        return self._default_model


# =============================================================================
# SINGLETON INSTANCE (Eager loading - load model khi startup để chat nhanh nhất)
# =============================================================================

_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Lấy singleton instance của EmbeddingService.
    
    Model được load khi server khởi động (eager loading) để đảm bảo
    chat flow nhanh nhất ngay từ request đầu tiên.
    """
    global _embedding_service_instance
    if _embedding_service_instance is None:
        logger.info("Đang khởi tạo EmbeddingService...")
        _embedding_service_instance = EmbeddingService()
        logger.info("Đã khởi tạo Singleton EmbeddingService")
    return _embedding_service_instance


def init_embedding_service() -> None:
    """
    Khởi tạo EmbeddingService - gọi trong startup để pre-load model.
    """
    get_embedding_service()
    logger.info("EmbeddingService đã được pre-load và sẵn sàng sử dụng")


# Backward compatibility: module-level singleton (eager loading on import)
# Load ngay khi module được import để đảm bảo model sẵn sàng
logger.info("Đang load EmbeddingService tại module import...")
embedding_service = get_embedding_service()
logger.info("EmbeddingService đã sẵn sàng!")


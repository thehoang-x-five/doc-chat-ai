"""
Embedding service for the RAG pipeline.

Supports sentence-transformers, Ollama, and optional OpenAI embeddings while
keeping runtime behavior aligned with server settings instead of silently
hardcoding a different model.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


KNOWN_MODEL_DIMENSIONS = {
    "paraphrase-multilingual-mpnet-base-v2": 768,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "BAAI/bge-m3": 1024,
    "intfloat/multilingual-e5-large": 1024,
}


class EmbeddingModelInfo:
    """Metadata for an embedding model instance."""

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
    Embedding service with explicit provider/model selection.

    The output dimension is normalized to the configured target dimension so it
    remains compatible with the current pgvector schema.
    """

    def __init__(
        self,
        model_name: str = None,
        dimension: int = None,
        batch_size: int = 32,
        cache_enabled: bool = True,
        provider: str = None,
    ):
        self.provider = (provider or settings.EMBEDDING_PROVIDER or "sentence-transformers").strip().lower()
        self.model_name = self._resolve_model_name(model_name or settings.EMBEDDING_MODEL)
        self.dimension = int(dimension or settings.EMBEDDING_DIMENSION or 768)
        self.batch_size = batch_size
        self.cache_enabled = cache_enabled

        self._cache: Dict[str, List[float]] = {}
        self._model_registry: Dict[str, EmbeddingModelInfo] = {}
        self._default_model: Optional[EmbeddingModelInfo] = None

        self._st_model = None
        self._st_models: Dict[str, Any] = {}
        self._st_available = self._check_sentence_transformers_available()

        self._default_model = self._build_default_model_info()
        logger.info(
            "EmbeddingService configured with provider=%s model=%s target_dim=%s",
            self._default_model.provider,
            self._default_model.name,
            self.dimension,
        )

    def _resolve_model_name(self, model_name: Optional[str]) -> str:
        if not model_name:
            return settings.OLLAMA_EMBED_MODEL
        alias = model_name.strip()
        if alias.lower() == "bge-m3":
            return settings.BGE_MODEL
        if alias.lower() == "e5-large":
            return settings.E5_MODEL
        return alias

    def _check_sentence_transformers_available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401
            return True
        except Exception:
            return False

    def _infer_native_dimension(self, model_name: str) -> int:
        return KNOWN_MODEL_DIMENSIONS.get(model_name, self.dimension)

    def _build_default_model_info(self) -> EmbeddingModelInfo:
        provider = self.provider
        model_name = self.model_name

        if provider == "sentence-transformers" and not self._st_available:
            logger.warning(
                "sentence-transformers provider configured but package unavailable; "
                "falling back to Ollama"
            )
            provider = "ollama"
            model_name = settings.OLLAMA_EMBED_MODEL

        if provider == "openai" and not settings.OPENAI_API_KEY:
            logger.warning(
                "openai embedding provider configured without OPENAI_API_KEY; "
                "falling back to Ollama"
            )
            provider = "ollama"
            model_name = settings.OLLAMA_EMBED_MODEL

        return EmbeddingModelInfo(
            model_id=uuid.uuid4(),
            name=model_name,
            provider=provider,
            dimension=self.dimension,
            is_default=True,
            config={
                "target_dimension": self.dimension,
                "native_dimension": self._infer_native_dimension(model_name),
            },
        )

    def ensure_model_loaded(self) -> None:
        """Eager-load the configured sentence-transformers model if used."""
        if self._default_model is None:
            return
        if self._default_model.provider != "sentence-transformers":
            return
        self._get_st_model(self._default_model)

    def _compute_cache_key(self, text: str, model_id: Optional[uuid.UUID] = None) -> str:
        key_str = f"{model_id or 'default'}:{text}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    def get_model_info(self, model_id: Optional[uuid.UUID] = None) -> EmbeddingModelInfo:
        if model_id and str(model_id) in self._model_registry:
            return self._model_registry[str(model_id)]
        if self._default_model:
            return self._default_model
        return EmbeddingModelInfo(
            model_id=uuid.uuid4(),
            name=self.model_name or settings.OLLAMA_EMBED_MODEL,
            provider=self.provider,
            dimension=self.dimension,
            is_default=True,
            config={"target_dimension": self.dimension},
        )

    def register_model(self, model_info: EmbeddingModelInfo) -> None:
        self._model_registry[str(model_info.model_id)] = model_info
        if model_info.is_default:
            self._default_model = model_info

    def embed_text(
        self,
        text: str,
        model_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[float], EmbeddingModelInfo]:
        model_info = self.get_model_info(model_id)
        if not text or not text.strip():
            return [0.0] * self.dimension, model_info

        cache_key = self._compute_cache_key(text, model_info.model_id)
        if self.cache_enabled and cache_key in self._cache:
            return self._cache[cache_key], model_info

        if model_info.provider == "sentence-transformers":
            embedding = self._embed_with_st(text, model_info)
        elif model_info.provider == "openai":
            embedding = self._embed_with_openai(text, model_info)
        else:
            embedding = self._embed_with_ollama(text, model_info)

        embedding = self._normalize_embedding_dim(embedding)
        if self.cache_enabled:
            self._cache[cache_key] = embedding
        return embedding, model_info

    def embed_text_simple(self, text: str) -> List[float]:
        embedding, _ = self.embed_text(text)
        return embedding

    def embed_batch(
        self,
        texts: List[str],
        model_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[List[float]], EmbeddingModelInfo]:
        model_info = self.get_model_info(model_id)
        if not texts:
            return [], model_info

        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[str] = []
        indices_to_embed: List[int] = []

        for idx, text in enumerate(texts):
            if not text or not text.strip():
                results[idx] = [0.0] * self.dimension
                continue
            cache_key = self._compute_cache_key(text, model_info.model_id)
            if self.cache_enabled and cache_key in self._cache:
                results[idx] = self._cache[cache_key]
                continue
            texts_to_embed.append(text)
            indices_to_embed.append(idx)

        if texts_to_embed:
            if model_info.provider == "sentence-transformers":
                embedded = self._embed_batch_with_st(texts_to_embed, model_info)
            elif model_info.provider == "openai":
                embedded = self._embed_batch_with_openai(texts_to_embed, model_info)
            else:
                embedded = self._embed_batch_with_ollama(texts_to_embed, model_info)

            for idx, embedding in zip(indices_to_embed, embedded):
                normalized = self._normalize_embedding_dim(embedding)
                results[idx] = normalized
                if self.cache_enabled:
                    cache_key = self._compute_cache_key(texts[idx], model_info.model_id)
                    self._cache[cache_key] = normalized

        final_results = [
            result if result is not None else [0.0] * self.dimension
            for result in results
        ]
        return final_results, model_info

    def embed_batch_simple(self, texts: List[str]) -> List[List[float]]:
        embeddings, _ = self.embed_batch(texts)
        return embeddings

    def _normalize_embedding_dim(self, embedding: List[float]) -> List[float]:
        if len(embedding) < self.dimension:
            return embedding + ([0.0] * (self.dimension - len(embedding)))
        if len(embedding) > self.dimension:
            logger.debug(
                "Truncating embedding from native_dim=%s to target_dim=%s",
                len(embedding),
                self.dimension,
            )
            return embedding[: self.dimension]
        return embedding

    def _get_st_model(self, model_info: EmbeddingModelInfo):
        model_name = model_info.name
        if model_name not in self._st_models:
            from sentence_transformers import SentenceTransformer

            load_name = model_name
            if "/" not in load_name and not load_name.startswith("sentence-transformers/"):
                load_name = f"sentence-transformers/{load_name}"
            logger.info("Loading SentenceTransformer model: %s", load_name)
            model = SentenceTransformer(load_name)
            self._st_models[model_name] = model
            self._st_model = model
            native_dim = model.get_sentence_embedding_dimension()
            model_info.config["native_dimension"] = native_dim
        return self._st_models[model_name]

    def _embed_with_st(self, text: str, model_info: EmbeddingModelInfo) -> List[float]:
        model = self._get_st_model(model_info)
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _embed_batch_with_st(self, texts: List[str], model_info: EmbeddingModelInfo) -> List[List[float]]:
        model = self._get_st_model(model_info)
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return [embedding.tolist() for embedding in embeddings]

    def _embed_with_ollama(self, text: str, model_info: EmbeddingModelInfo) -> List[float]:
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/embeddings",
                json={
                    "model": model_info.name or settings.OLLAMA_EMBED_MODEL,
                    "prompt": text,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except Exception as exc:
            logger.error("Ollama embedding failed: %s", exc)
            return [0.0] * self.dimension

    def _embed_batch_with_ollama(self, texts: List[str], model_info: EmbeddingModelInfo) -> List[List[float]]:
        return [self._embed_with_ollama(text, model_info) for text in texts]

    def _embed_with_openai(self, text: str, model_info: EmbeddingModelInfo) -> List[float]:
        embeddings = self._embed_batch_with_openai([text], model_info)
        return embeddings[0] if embeddings else [0.0] * self.dimension

    def _embed_batch_with_openai(self, texts: List[str], model_info: EmbeddingModelInfo) -> List[List[float]]:
        try:
            response = httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_info.name,
                    "input": texts,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
            return [item.get("embedding", []) for item in items]
        except Exception as exc:
            logger.error("OpenAI embedding failed: %s", exc)
            return [[0.0] * self.dimension for _ in texts]

    async def delete_document_vectors(self, document_id: str) -> int:
        """
        Delete vectors for a document when using external vector stores.

        Current pgvector storage keeps embeddings on Chunk rows, so deleting
        chunks is the real cleanup path. This method exists to keep the delete
        flow explicit and future-proof for non-Postgres vector stores.
        """
        logger.info(
            "Vector cleanup for document %s is handled by chunk deletion (VECTOR_DB_TYPE=%s)",
            document_id,
            settings.VECTOR_DB_TYPE,
        )
        return 0

    def clear_cache(self) -> None:
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    @property
    def default_model_info(self) -> Optional[EmbeddingModelInfo]:
        return self._default_model


_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Return the singleton embedding service."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        logger.info("Initializing singleton EmbeddingService")
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance


def init_embedding_service() -> None:
    """Preload the singleton embedding service."""
    service = get_embedding_service()
    service.ensure_model_loaded()
    logger.info("EmbeddingService initialized and ready")


embedding_service = get_embedding_service()

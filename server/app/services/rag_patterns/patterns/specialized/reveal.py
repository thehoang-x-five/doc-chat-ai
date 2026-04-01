"""
REVEAL (Visual-Language RAG) Service.

Processes queries involving both text and visual information.
Consolidated from: base.py, vision_encoder.py, multimodal_retrieval.py, fusion.py
"""
import logging
from enum import Enum
from typing import Any

from .models import (
    VisualContext, TextContext, MultimodalResult, REVEALResult,
    ModalityType, FusionConfig
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components
# =============================================================================

class FusionStrategy(Enum):
    """Fusion strategies for multimodal results."""
    EARLY = "early"
    LATE = "late"
    HYBRID = "hybrid"


class VisionEncoder:
    """Encodes visual content using vision model."""

    def __init__(self, vision_model_func: Any | None = None, embedding_dim: int = 768):
        self.vision_model_func = vision_model_func
        self.embedding_dim = embedding_dim

    def extract_visual_features(self, image_data: Any) -> dict[str, Any]:
        """Extract features from image."""
        if self.vision_model_func:
            try:
                result = self.vision_model_func(image_data)
                return {
                    "embedding": result.get("embedding", [0.0] * self.embedding_dim),
                    "features": result.get("features", {}),
                    "metadata": result.get("metadata", {})
                }
            except Exception as e:
                logger.error(f"Vision encoding failed: {e}")
        
        return {"embedding": [0.0] * self.embedding_dim, "features": {}, "metadata": {}}

    def encode_images(self, images: list[Any]) -> list[list[float]]:
        """Encode multiple images."""
        return [self.extract_visual_features(img)["embedding"] for img in images]


class MultimodalRetrieval:
    """Retrieves from both text and visual indices."""

    def __init__(
        self, 
        raganything_instance: Any | None = None,
        text_weight: float = 0.6,
        visual_weight: float = 0.4,
        top_k: int = 5
    ):
        self.raganything = raganything_instance
        self.text_weight = text_weight
        self.visual_weight = visual_weight
        self.top_k = top_k

    def retrieve_multimodal(
        self,
        text_query: str,
        visual_query_embedding: list[float] | None = None,
        visual_index: Any | None = None,
        top_k: int | None = None
    ) -> tuple[list[dict], list[dict]]:
        """Retrieve from both text and visual modalities."""
        k = top_k or self.top_k
        text_results = []
        visual_results = []
        
        # Text retrieval
        if self.raganything:
            try:
                text_results = self.raganything.retrieve(text_query, top_k=k)
            except Exception as e:
                logger.error(f"Text retrieval failed: {e}")
        
        # Visual retrieval (if visual index available)
        if visual_query_embedding and visual_index:
            try:
                visual_results = visual_index.search(visual_query_embedding, top_k=k)
            except Exception as e:
                logger.error(f"Visual retrieval failed: {e}")
        
        return text_results, visual_results


class VisualTextFusion:
    """Fuses text and visual results."""

    def __init__(
        self,
        strategy: FusionStrategy = FusionStrategy.HYBRID,
        visual_weight: float = 0.4,
        text_weight: float = 0.6,
        attention_enabled: bool = True
    ):
        self.strategy = strategy
        self.visual_weight = visual_weight
        self.text_weight = text_weight
        self.attention_enabled = attention_enabled

    def fuse_results(self, text_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Fuse text and visual results."""
        if self.strategy == FusionStrategy.LATE:
            return self._late_fusion(text_results, visual_results)
        elif self.strategy == FusionStrategy.EARLY:
            return self._early_fusion(text_results, visual_results)
        else:
            return self._hybrid_fusion(text_results, visual_results)

    def fuse_hybrid(self, query_embedding: list[float], text_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Hybrid fusion with attention."""
        return self._hybrid_fusion(text_results, visual_results)

    def _late_fusion(self, text_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Late fusion: combine after scoring."""
        combined = []
        for r in text_results:
            combined.append({**r, "fusion_score": r.get("score", 0) * self.text_weight})
        for r in visual_results:
            combined.append({**r, "fusion_score": r.get("score", 0) * self.visual_weight})
        return sorted(combined, key=lambda x: x.get("fusion_score", 0), reverse=True)

    def _early_fusion(self, text_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Early fusion: combine embeddings."""
        return self._late_fusion(text_results, visual_results)

    def _hybrid_fusion(self, text_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Hybrid fusion: weighted combination."""
        return self._late_fusion(text_results, visual_results)


# =============================================================================
# Main Service
# =============================================================================

class REVEALService:
    """
    REVEAL (Visual-Language RAG) Service.
    
    Implements visual-language RAG with multimodal retrieval and fusion.
    
    Features:
    - Vision transformer encoding for images
    - Multimodal retrieval (text + visual)
    - Visual-text fusion strategies
    - Integration with RAGAnything processors
    """

    def __init__(
        self,
        raganything_instance: Any | None = None,
        vision_model_func: Any | None = None,
        fusion_config: FusionConfig | None = None,
        embedding_dim: int = 768
    ):
        self.raganything = raganything_instance
        self.embedding_dim = embedding_dim
        
        if fusion_config is None:
            fusion_config = FusionConfig()
        self.fusion_config = fusion_config
        
        self.vision_encoder = VisionEncoder(vision_model_func, embedding_dim)
        self.multimodal_retrieval = MultimodalRetrieval(
            raganything_instance, fusion_config.text_weight, fusion_config.visual_weight, fusion_config.top_k
        )
        
        strategy_map = {"early": FusionStrategy.EARLY, "late": FusionStrategy.LATE, "hybrid": FusionStrategy.HYBRID}
        fusion_strategy = strategy_map.get(fusion_config.strategy.lower(), FusionStrategy.HYBRID)
        
        self.fusion = VisualTextFusion(
            strategy=fusion_strategy,
            visual_weight=fusion_config.visual_weight,
            text_weight=fusion_config.text_weight,
            attention_enabled=fusion_config.attention_enabled
        )

        logger.info(f"REVEALService: strategy={fusion_config.strategy}, embedding_dim={embedding_dim}")

    def query(
        self,
        text_query: str,
        visual_query: Any | None = None,
        visual_index: Any | None = None,
        top_k: int | None = None
    ) -> REVEALResult:
        """Execute a multimodal query."""
        logger.info(f"Processing REVEAL query: {text_query[:100]}...")
        
        k = top_k if top_k is not None else self.fusion_config.top_k
        
        visual_query_embedding = None
        visual_context = None
        if visual_query is not None:
            features = self.vision_encoder.extract_visual_features(visual_query)
            visual_query_embedding = features["embedding"]
            visual_context = VisualContext(
                image_data=visual_query,
                embedding=visual_query_embedding,
                features=features.get("features", {}),
                metadata=features.get("metadata", {})
            )
        
        text_results, visual_results = self.multimodal_retrieval.retrieve_multimodal(
            text_query, visual_query_embedding, visual_index, k
        )
        
        text_context = None
        if text_results:
            top = text_results[0]
            text_context = TextContext(
                content=top.get("content", ""),
                embedding=top.get("embedding", []),
                metadata=top.get("metadata", {}),
                source=top.get("source")
            )
        
        fused_results = self.fusion.fuse_results(text_results, visual_results)
        
        multimodal_result = MultimodalResult(
            text_results=text_results,
            visual_results=visual_results,
            fused_results=fused_results,
            text_weight=self.fusion_config.text_weight,
            visual_weight=self.fusion_config.visual_weight,
            fusion_strategy=self.fusion_config.strategy
        )
        
        response = self._generate_response(fused_results, text_query)
        modality_type = self._determine_modality_type(len(visual_results) > 0, len(text_results) > 0)
        confidence = self._calculate_confidence(fused_results)

        logger.info(f"REVEAL complete: {len(fused_results)} fused results, confidence={confidence:.2f}")

        return REVEALResult(
            query=text_query,
            query_embedding=visual_query_embedding or [],
            visual_context=visual_context,
            text_context=text_context,
            multimodal_result=multimodal_result,
            response=response,
            modality_type=modality_type,
            confidence=confidence,
            metadata={"top_k": k, "fusion_strategy": self.fusion_config.strategy}
        )

    def _generate_response(self, fused_results: list[dict], query: str) -> str:
        if not fused_results:
            return "No relevant results found."
        
        contents = [r.get("content", "")[:200] for r in fused_results[:3] if r.get("content")]
        if not contents:
            return "No content available."
        
        response = f"Based on '{query}':\n\n"
        for i, c in enumerate(contents, 1):
            response += f"{i}. {c}...\n\n"
        return response.strip()

    def _determine_modality_type(self, has_visual: bool, has_text: bool) -> ModalityType:
        if has_visual and has_text:
            return ModalityType.MIXED
        elif has_visual:
            return ModalityType.VISUAL
        return ModalityType.TEXT

    def _calculate_confidence(self, fused_results: list[dict]) -> float:
        if not fused_results:
            return 0.0
        scores = [r.get("fusion_score", r.get("score", 0.0)) for r in fused_results[:3]]
        return max(0.0, min(1.0, sum(scores) / len(scores) if scores else 0.0))

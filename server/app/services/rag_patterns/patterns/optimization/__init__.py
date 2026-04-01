"""
Optimization Patterns Module.

This module consolidates RAG patterns focused on performance optimization:
- Adaptive RAG: Intelligent query routing based on confidence
- Speculative RAG: Fast, cost-effective generation with draft/verify
- CORAG: Cost-constrained chunk selection
- Semantic Highlight: Context compression via semantic extraction
"""

# Adaptive RAG
from .adaptive import (
    AdaptiveRAGService,
    ConfidenceAssessor,
    StrategySelector,
    QueryRouter,
)

# Speculative RAG
from .speculative import (
    SpeculativeRAGService,
    Drafter,
    Verifier,
    Merger,
)

# CORAG (Cost-Constrained RAG)
from .corag import (
    CORAGService,
    UtilityOptimizer,
    ChunkSelector,
    MCTSSearch,
    Chunk,
    OptimizationStep,
    OptimizationMetrics,
    CORAGResult,
)

# Semantic Highlight RAG
from .semantic import (
    SemanticHighlightRAGService,
    SentenceSplitter,
    SemanticScorer,
    EvidenceSelector,
    ContextCompressor,
    Sentence,
    CompressionMetrics,
    SemanticHighlightResult,
)

# Models from shared models.py
from .models import (
    # Adaptive RAG
    ConfidenceAssessment,
    RetrievalStrategy,
    AdaptiveRAGResult,
    # Speculative RAG
    Draft,
    VerificationResult,
    SpeculativeRAGResult,
    # Semantic Highlight RAG
    SemanticFragment,
    HighlightResult,
)

__all__ = [
    # Services
    "AdaptiveRAGService",
    "SpeculativeRAGService",
    "CORAGService",
    "SemanticHighlightRAGService",
    # Adaptive components
    "ConfidenceAssessor",
    "StrategySelector",
    "QueryRouter",
    # Speculative components
    "Drafter",
    "Verifier",
    "Merger",
    # CORAG components
    "UtilityOptimizer",
    "ChunkSelector",
    "MCTSSearch",
    # Semantic Highlight components
    "SentenceSplitter",
    "SemanticScorer",
    "EvidenceSelector",
    "ContextCompressor",
    # Models
    "ConfidenceAssessment",
    "RetrievalStrategy",
    "AdaptiveRAGResult",
    "Draft",
    "VerificationResult",
    "SpeculativeRAGResult",
    "Chunk",
    "OptimizationStep",
    "OptimizationMetrics",
    "CORAGResult",
    "Sentence",
    "CompressionMetrics",
    "SemanticHighlightResult",
    "SemanticFragment",
    "HighlightResult",
]

"""
Consolidated RAG Patterns.

This module provides organized access to all RAG pattern implementations.
Patterns are categorized into three modules:

- **accuracy**: Patterns focused on improving response accuracy
  - CorrectiveRAGService: Validates and corrects retrieved information
  - SelfRAGService: Iterative self-refinement of responses

- **optimization**: Patterns focused on performance optimization
  - AdaptiveRAGService: Intelligent query routing based on confidence
  - SpeculativeRAGService: Fast, cost-effective draft/verify generation
  - CORAGService: Cost-constrained chunk selection
  - SemanticHighlightRAGService: Context compression via semantic extraction

- **specialized**: Patterns for specific use cases
  - CORALService: Conversational RAG with context tracking
  - REVEALService: Visual-Language RAG with multimodal fusion
  - CodeRAGService: Code-aware RAG with symbol resolution
"""

# Accuracy Patterns
from .accuracy import (
    CorrectiveRAGService,
    SelfRAGService,
    RelevanceScorer,
    ConflictResolver,
    WebSearchFallback,
    QualityChecker,
    ResponseRefiner,
    QueryRewriter,
)

# Optimization Patterns
from .optimization import (
    AdaptiveRAGService,
    SpeculativeRAGService,
    CORAGService,
    SemanticHighlightRAGService,
    ConfidenceAssessor,
    StrategySelector,
    QueryRouter,
    Drafter,
    Verifier,
    Merger,
    UtilityOptimizer,
    ChunkSelector,
    MCTSSearch,
    SentenceSplitter,
    SemanticScorer,
    EvidenceSelector,
    ContextCompressor,
)

# Specialized Patterns
from .specialized import (
    CORALService,
    REVEALService,
    CodeRAGService,
    ContextManager,
    HistoryManager,
    ConversationRetriever,
    VisionEncoder,
    MultimodalRetrieval,
    VisualTextFusion,
    CodeParser,
    SymbolResolver,
    DocExtractor,
)

__all__ = [
    # ========== Accuracy Patterns ==========
    "CorrectiveRAGService",
    "SelfRAGService",
    "RelevanceScorer",
    "ConflictResolver",
    "WebSearchFallback",
    "QualityChecker",
    "ResponseRefiner",
    "QueryRewriter",
    # ========== Optimization Patterns ==========
    "AdaptiveRAGService",
    "SpeculativeRAGService",
    "CORAGService",
    "SemanticHighlightRAGService",
    "ConfidenceAssessor",
    "StrategySelector",
    "QueryRouter",
    "Drafter",
    "Verifier",
    "Merger",
    "UtilityOptimizer",
    "ChunkSelector",
    "MCTSSearch",
    "SentenceSplitter",
    "SemanticScorer",
    "EvidenceSelector",
    "ContextCompressor",
    # ========== Specialized Patterns ==========
    "CORALService",
    "REVEALService",
    "CodeRAGService",
    "ContextManager",
    "HistoryManager",
    "ConversationRetriever",
    "VisionEncoder",
    "MultimodalRetrieval",
    "VisualTextFusion",
    "CodeParser",
    "SymbolResolver",
    "DocExtractor",
]

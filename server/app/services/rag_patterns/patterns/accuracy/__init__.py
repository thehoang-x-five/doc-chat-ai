"""
Accuracy Patterns - Quality-focused RAG patterns.

Includes:
- CorrectiveRAGService: Validates and corrects retrieved information
- SelfRAGService: Iterative self-refinement and validation
"""
from .corrective import (
    CorrectiveRAGService,
    RelevanceScorer,
    ConflictResolver,
    WebSearchFallback,
)
from .models import (
    CorrectedRetrievalResult,
    CorrectionStep,
    Document,
    HallucinationCheck,
    QualityDelta,
    RefinementStep,
    SelfRAGResult,
    compute_similarity,
    docs_to_context,
    get_doc_content,
)
from .self_rag import (
    SelfRAGService,
    QualityChecker,
    ResponseRefiner,
    QueryRewriter,
)

__all__ = [
    # Services
    "CorrectiveRAGService",
    "SelfRAGService",
    # Corrective helpers
    "RelevanceScorer",
    "ConflictResolver",
    "WebSearchFallback",
    # Self-RAG helpers
    "QualityChecker",
    "ResponseRefiner",
    "QueryRewriter",
    # Models
    "Document",
    "CorrectionStep",
    "CorrectedRetrievalResult",
    "HallucinationCheck",
    "RefinementStep",
    "QualityDelta",
    "SelfRAGResult",
    # Utils
    "compute_similarity",
    "docs_to_context",
    "get_doc_content",
]

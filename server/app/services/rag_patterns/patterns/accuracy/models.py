"""
Shared data models for Accuracy patterns (Corrective RAG, Self RAG).

Contains dataclasses for documents, correction/refinement steps, and results.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# =============================================================================
# Corrective RAG Models
# =============================================================================

@dataclass
class Document:
    """Document with content and metadata."""
    document_id: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float | None = None


@dataclass
class CorrectionStep:
    """Record of a correction step."""
    step_type: str  # "relevance_check", "web_search", "conflict_resolution"
    documents_before: int
    documents_after: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CorrectedRetrievalResult:
    """Result of corrective retrieval."""
    final_documents: list[Document]
    corrections_made: int
    web_search_used: bool
    conflicts_resolved: int
    audit_trail: list[CorrectionStep]
    success: bool = True
    error_message: str | None = None


# =============================================================================
# Self RAG Models
# =============================================================================

@dataclass
class HallucinationCheck:
    """Result of hallucination detection."""
    has_hallucination: bool
    grounding_score: float
    hallucinated_segments: list[str] = field(default_factory=list)


@dataclass
class RefinementStep:
    """Record of a refinement iteration."""
    iteration: int
    query_used: str
    response_generated: str
    relevance_score: float
    grounding_score: float
    action_taken: str  # "accept", "rewrite", "retry"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QualityDelta:
    """Quality improvement measurement."""
    metric_name: str
    before: float
    after: float
    improvement: float


@dataclass
class SelfRAGResult:
    """Result of self-refinement process."""
    final_response: str
    iterations_used: int
    quality_improvements: list[QualityDelta]
    confidence_score: float
    refinement_log: list[RefinementStep]
    success: bool = True
    error_message: str | None = None


# =============================================================================
# Shared Utilities
# =============================================================================

def compute_similarity(text1: str, text2: str) -> float:
    """
    Compute simple text similarity using Jaccard word overlap.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0-1)
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if len(words1) == 0 or len(words2) == 0:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def docs_to_context(documents: list[Any]) -> str:
    """
    Convert documents to context string.
    
    Args:
        documents: List of document objects
        
    Returns:
        Combined context string
    """
    contexts = [get_doc_content(doc) for doc in documents]
    return "\n\n".join(contexts)


def get_doc_content(doc: Any) -> str:
    """
    Extract content from document object.
    
    Args:
        doc: Document object (can be dict, object with content attr, or string)
        
    Returns:
        Document content as string
    """
    if hasattr(doc, 'content'):
        return doc.content
    elif isinstance(doc, dict):
        return doc.get('content', '')
    elif isinstance(doc, str):
        return doc
    return str(doc)

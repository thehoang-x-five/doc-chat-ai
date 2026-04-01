"""
Shared data models for Optimization patterns.

Includes models for: AdaptiveRAG, SpeculativeRAG, CORAG, SemanticHighlightRAG
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# =============================================================================
# Adaptive RAG Models
# =============================================================================

@dataclass
class ConfidenceAssessment:
    """Result of confidence assessment."""
    confidence_score: float
    logprobs: list[float]
    needs_retrieval: bool
    reasoning: str


@dataclass
class RetrievalStrategy:
    """Selected retrieval strategy."""
    strategy_type: str  # "none", "lightweight", "vector", "graph", "hybrid"
    top_k: int
    reasoning: str


@dataclass
class AdaptiveRAGResult:
    """Result of adaptive RAG processing."""
    response: str
    retrieval_used: bool
    retrieval_strategy: str | None
    confidence_score: float
    decision_reasoning: str
    latency_saved_ms: float
    cost_saved_tokens: int
    documents_used: list[Any] = field(default_factory=list)
    decision_log: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Speculative RAG Models
# =============================================================================

@dataclass
class Draft:
    """A draft response from speculative generation."""
    content: str
    model: str
    confidence: float = 0.0
    generation_time: float = 0.0
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of draft verification."""
    draft: Draft
    is_valid: bool
    quality_score: float
    verification_reasoning: str = ""
    corrections: str | None = None
    verification_time: float = 0.0
    tokens_used: int = 0


@dataclass
class SpeculativeRAGResult:
    """Result of speculative RAG processing."""
    query: str
    selected_draft: Draft
    all_drafts: list[Draft]
    verification_results: list[VerificationResult]
    final_answer: str
    total_time: float
    total_tokens: int
    cost_savings: float = 0.0
    speedup_factor: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# CORAG (Cost-Constrained RAG) Models
# =============================================================================

@dataclass
class Chunk:
    """A text chunk with relevance and cost metadata."""
    chunk_id: str
    content: str
    token_count: int
    relevance_score: float = 0.0
    utility_score: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationStep:
    """Record of an optimization step."""
    step_type: str
    chunks_before: int
    chunks_after: int
    tokens_before: int
    tokens_after: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass 
class OptimizationMetrics:
    """Metrics from cost optimization."""
    original_tokens: int
    selected_tokens: int
    tokens_saved: int
    cost_savings_percent: float
    avg_relevance_before: float
    avg_relevance_after: float
    quality_retention: float


@dataclass
class CORAGResult:
    """Result of CORAG processing."""
    selected_chunks: list[Chunk]
    optimization_log: list[OptimizationStep] = field(default_factory=list)
    metrics: OptimizationMetrics | None = None
    budget_used: int = 0
    budget_remaining: int = 0
    quality_score: float = 0.0
    mcts_used: bool = False


# =============================================================================
# Semantic Highlight RAG Models
# =============================================================================

@dataclass
class Sentence:
    """A sentence with semantic score."""
    text: str
    score: float
    chunk_index: int
    sentence_index: int


@dataclass
class SemanticHighlightResult:
    """Result of semantic highlight compression."""
    compressed_context: str
    total_sentences: int
    selected_sentences: int
    compression_ratio: float
    avg_score: float
    highlighted_sentences: list[Sentence] = field(default_factory=list)
    original_tokens: int = 0
    compressed_tokens: int = 0
    error_message: str | None = None


@dataclass
class SemanticFragment:
    """A semantic fragment from highlight extraction."""
    text: str
    relevance_score: float
    start_pos: int = 0
    end_pos: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HighlightResult:
    """Result of highlighting operation."""
    fragments: list[SemanticFragment] = field(default_factory=list)
    total_fragments: int = 0
    avg_relevance: float = 0.0
    processing_time: float = 0.0


# =============================================================================
# Utility Functions
# =============================================================================

def estimate_confidence_heuristic(query: str) -> float:
    """
    Estimate confidence using heuristics based on query characteristics.
    
    Args:
        query: User query
        
    Returns:
        Confidence score (0-1)
    """
    query_lower = query.lower()

    # High confidence patterns (general knowledge)
    high_confidence_patterns = [
        "what is", "who is", "when was", "where is",
        "define", "explain", "how to", "why does",
        "tell me about", "describe"
    ]

    # Low confidence patterns (context-specific)
    low_confidence_patterns = [
        "in this document", "according to", "based on",
        "from the file", "in the context", "specific to",
        "in the provided", "from the text", "mentioned in"
    ]

    high_score = sum(1 for p in high_confidence_patterns if p in query_lower)
    low_score = sum(1 for p in low_confidence_patterns if p in query_lower)

    base_confidence = 0.7

    if low_score > 0:
        return max(0.3, base_confidence - (low_score * 0.2))
    elif high_score > 0:
        return min(0.9, base_confidence + (high_score * 0.1))

    word_count = len(query.split())
    if word_count > 20:
        return 0.5
    elif word_count < 5:
        return 0.8

    return base_confidence


def calculate_latency_savings(strategy: str) -> float:
    """Estimate latency savings based on retrieval strategy."""
    savings_map = {
        "none": 500.0,
        "lightweight": 200.0,
        "vector": 0.0,
        "graph": 0.0,
        "hybrid": 0.0,
    }
    return savings_map.get(strategy, 0.0)


def calculate_token_savings(strategy: str, top_k: int, full_top_k: int = 10) -> int:
    """Estimate token savings based on retrieval strategy."""
    tokens_per_doc = 500

    if strategy == "none":
        return full_top_k * tokens_per_doc
    elif strategy == "lightweight":
        return (full_top_k - top_k) * tokens_per_doc
    else:
        return 0

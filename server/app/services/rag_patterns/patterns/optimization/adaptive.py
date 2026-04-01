"""
Adaptive RAG Service - Pattern #7

Intelligently decides when to retrieve based on LLM confidence.
Consolidated from: base.py, assessor.py, router.py, strategy.py
"""
import logging
from collections.abc import Callable
from datetime import datetime

from .models import (
    AdaptiveRAGResult,
    ConfidenceAssessment,
    RetrievalStrategy,
    estimate_confidence_heuristic,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components
# =============================================================================

class ConfidenceAssessor:
    """Assesses LLM confidence for queries using logprobs or heuristics."""

    def __init__(
        self,
        high_confidence_threshold: float = 0.8,
        low_confidence_threshold: float = 0.6,
    ):
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold

    async def assess_confidence(
        self,
        query: str,
        generate_func=None,
        **kwargs
    ) -> ConfidenceAssessment:
        """Assess LLM confidence for query."""
        try:
            confidence_score = estimate_confidence_heuristic(query)
            needs_retrieval = confidence_score < self.high_confidence_threshold

            if confidence_score >= self.high_confidence_threshold:
                reasoning = "High confidence - query is general knowledge or simple"
            elif confidence_score >= self.low_confidence_threshold:
                reasoning = "Borderline confidence - lightweight retrieval recommended"
            else:
                reasoning = "Low confidence - full retrieval required"

            logger.debug(
                f"Confidence assessment: score={confidence_score:.3f}, "
                f"needs_retrieval={needs_retrieval}"
            )

            return ConfidenceAssessment(
                confidence_score=confidence_score,
                logprobs=[],
                needs_retrieval=needs_retrieval,
                reasoning=reasoning
            )

        except Exception as e:
            logger.warning(f"Error assessing confidence: {e}")
            return ConfidenceAssessment(
                confidence_score=0.5,
                logprobs=[],
                needs_retrieval=True,
                reasoning=f"Error in assessment: {str(e)}"
            )


class StrategySelector:
    """Selects optimal retrieval strategy based on query characteristics."""

    def __init__(
        self,
        high_confidence_threshold: float = 0.8,
        low_confidence_threshold: float = 0.6,
        lightweight_top_k: int = 3,
        full_top_k: int = 10,
    ):
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.lightweight_top_k = lightweight_top_k
        self.full_top_k = full_top_k

    def select_retrieval_strategy(
        self,
        query: str,
        confidence: float,
        query_type: str | None = None
    ) -> RetrievalStrategy:
        """Select optimal retrieval strategy."""
        query_lower = query.lower()

        if confidence >= self.high_confidence_threshold:
            return RetrievalStrategy("none", 0, "High confidence, no retrieval needed")

        if confidence >= self.low_confidence_threshold:
            return RetrievalStrategy(
                "lightweight", self.lightweight_top_k, 
                "Borderline confidence, lightweight retrieval"
            )

        # Use explicit query type if provided
        if query_type in ("graph", "vector", "hybrid"):
            return RetrievalStrategy(query_type, self.full_top_k, f"{query_type} query type detected")

        # Analyze query for graph indicators
        graph_indicators = [
            "related to", "connected to", "relationship", "link between",
            "how does", "connection", "associated with", "depends on"
        ]
        if any(ind in query_lower for ind in graph_indicators):
            return RetrievalStrategy("graph", self.full_top_k, "Query suggests graph relationships")

        # Complex queries: Hybrid retrieval
        if len(query.split()) > 15:
            return RetrievalStrategy("hybrid", self.full_top_k, "Complex query, using hybrid retrieval")

        # Default: Vector retrieval
        return RetrievalStrategy("vector", self.full_top_k, "Default vector retrieval")


class QueryRouter:
    """Routes queries to appropriate processing paths based on confidence."""

    def __init__(
        self,
        high_confidence_threshold: float = 0.8,
        low_confidence_threshold: float = 0.6,
        lightweight_top_k: int = 3,
        full_top_k: int = 10,
    ):
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.lightweight_top_k = lightweight_top_k
        self.full_top_k = full_top_k
        self.strategy_selector = StrategySelector(
            high_confidence_threshold, low_confidence_threshold,
            lightweight_top_k, full_top_k
        )

    async def route_query(
        self,
        query: str,
        confidence: ConfidenceAssessment,
        generate_func: Callable,
        retrieve_func: Callable | None,
        query_type: str | None,
        decision_log: list[dict],
        start_time: datetime,
        **kwargs
    ) -> AdaptiveRAGResult:
        """Route query based on confidence assessment."""
        if confidence.confidence_score >= self.high_confidence_threshold:
            return await self._process_without_retrieval(
                query, generate_func, confidence, decision_log, start_time, **kwargs
            )
        elif confidence.confidence_score >= self.low_confidence_threshold:
            return await self._process_with_lightweight_retrieval(
                query, generate_func, retrieve_func, confidence, decision_log, start_time, **kwargs
            )
        else:
            return await self._process_with_full_retrieval(
                query, generate_func, retrieve_func, confidence, query_type, 
                decision_log, start_time, **kwargs
            )

    async def _process_without_retrieval(
        self, query, generate_func, confidence, decision_log, start_time, **kwargs
    ) -> AdaptiveRAGResult:
        """Process query without retrieval (high confidence)."""
        decision_log.append({
            "step": "routing_decision",
            "decision": "skip_retrieval",
            "timestamp": datetime.now().isoformat()
        })

        response = await generate_func(query, documents=[], **kwargs)
        latency_saved = 500.0
        tokens_saved = 2000

        return AdaptiveRAGResult(
            response=response,
            retrieval_used=False,
            retrieval_strategy="none",
            confidence_score=confidence.confidence_score,
            decision_reasoning=confidence.reasoning,
            latency_saved_ms=latency_saved,
            cost_saved_tokens=tokens_saved,
            documents_used=[],
            decision_log=decision_log
        )

    async def _process_with_lightweight_retrieval(
        self, query, generate_func, retrieve_func, confidence, decision_log, start_time, **kwargs
    ) -> AdaptiveRAGResult:
        """Process query with lightweight retrieval."""
        decision_log.append({
            "step": "routing_decision",
            "decision": "lightweight_retrieval",
            "top_k": self.lightweight_top_k,
            "timestamp": datetime.now().isoformat()
        })

        retrieve_kwargs = {k: v for k, v in kwargs.items() if k != "top_k"}
        docs = await retrieve_func(query, top_k=self.lightweight_top_k, **retrieve_kwargs) if retrieve_func else []
        response = await generate_func(query, documents=docs, **kwargs)
        tokens_saved = (self.full_top_k - self.lightweight_top_k) * 500

        return AdaptiveRAGResult(
            response=response,
            retrieval_used=True,
            retrieval_strategy="lightweight",
            confidence_score=confidence.confidence_score,
            decision_reasoning=confidence.reasoning,
            latency_saved_ms=200.0,
            cost_saved_tokens=tokens_saved,
            documents_used=docs,
            decision_log=decision_log
        )

    async def _process_with_full_retrieval(
        self, query, generate_func, retrieve_func, confidence, query_type, 
        decision_log, start_time, **kwargs
    ) -> AdaptiveRAGResult:
        """Process query with full retrieval."""
        strategy = self.strategy_selector.select_retrieval_strategy(
            query, confidence.confidence_score, query_type
        )

        decision_log.append({
            "step": "routing_decision",
            "decision": "full_retrieval",
            "strategy": strategy.strategy_type,
            "top_k": strategy.top_k,
            "timestamp": datetime.now().isoformat()
        })

        docs = []
        if retrieve_func:
            retrieve_kwargs = {k: v for k, v in kwargs.items() if k != "top_k"}
            retrieve_kwargs["strategy"] = strategy.strategy_type
            docs = await retrieve_func(query, top_k=strategy.top_k, **retrieve_kwargs)

        response = await generate_func(query, documents=docs, **kwargs)

        return AdaptiveRAGResult(
            response=response,
            retrieval_used=True,
            retrieval_strategy=strategy.strategy_type,
            confidence_score=confidence.confidence_score,
            decision_reasoning=confidence.reasoning,
            latency_saved_ms=0.0,
            cost_saved_tokens=0,
            documents_used=docs,
            decision_log=decision_log
        )


# =============================================================================
# Main Service
# =============================================================================

class AdaptiveRAGService:
    """
    Adaptive RAG Service implementing Pattern #7.
    
    Intelligently routes queries based on LLM confidence:
    - Skips retrieval for high-confidence queries
    - Uses lightweight retrieval for borderline cases
    - Applies full retrieval with optimal strategy for low confidence
    """

    def __init__(
        self,
        high_confidence_threshold: float = 0.8,
        low_confidence_threshold: float = 0.6,
        lightweight_top_k: int = 3,
        full_top_k: int = 10
    ):
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.lightweight_top_k = lightweight_top_k
        self.full_top_k = full_top_k

        self.assessor = ConfidenceAssessor(high_confidence_threshold, low_confidence_threshold)
        self.router = QueryRouter(
            high_confidence_threshold, low_confidence_threshold,
            lightweight_top_k, full_top_k
        )

        logger.info(
            f"Initialized AdaptiveRAGService: "
            f"high={high_confidence_threshold}, low={low_confidence_threshold}"
        )

    async def process_query(
        self,
        query: str,
        generate_func: Callable,
        retrieve_func: Callable | None = None,
        query_type: str | None = None,
        **kwargs
    ) -> AdaptiveRAGResult:
        """Process query with adaptive retrieval strategy."""
        start_time = datetime.now()
        decision_log = []

        try:
            confidence = await self.assessor.assess_confidence(query, generate_func, **kwargs)
            decision_log.append({
                "step": "confidence_assessment",
                "confidence_score": confidence.confidence_score,
                "needs_retrieval": confidence.needs_retrieval,
                "reasoning": confidence.reasoning,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(
                f"Confidence: score={confidence.confidence_score:.3f}, "
                f"needs_retrieval={confidence.needs_retrieval}"
            )

            return await self.router.route_query(
                query=query,
                confidence=confidence,
                generate_func=generate_func,
                retrieve_func=retrieve_func,
                query_type=query_type,
                decision_log=decision_log,
                start_time=start_time,
                **kwargs
            )

        except Exception as e:
            logger.error(f"Error in adaptive RAG processing: {e}", exc_info=True)
            if retrieve_func:
                retrieve_kwargs = {k: v for k, v in kwargs.items() if k != "top_k"}
                docs = await retrieve_func(query, top_k=self.full_top_k, **retrieve_kwargs)
                response = await generate_func(query, documents=docs, **kwargs)
            else:
                response = await generate_func(query, **kwargs)

            return AdaptiveRAGResult(
                response=response,
                retrieval_used=retrieve_func is not None,
                retrieval_strategy="fallback",
                confidence_score=0.0,
                decision_reasoning=f"Error occurred, fallback: {str(e)}",
                latency_saved_ms=0.0,
                cost_saved_tokens=0,
                decision_log=decision_log
            )

    # Alias for orchestrator compatibility
    query = process_query

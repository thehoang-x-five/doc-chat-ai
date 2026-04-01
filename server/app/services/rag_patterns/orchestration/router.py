"""
Smart Router - Fast pattern selection for simple queries using rule-based logic.

This module provides:
1. Rule-based pattern selection for simple queries
2. Meta-pattern matching for known complex scenarios
3. Historical metrics integration (placeholder)
4. Fast routing decisions (< 50ms)

Migrated from raganything/patterns/smart_router.py
"""
import logging
import time
from dataclasses import dataclass

from .combinations import ALL_COMBINATIONS, CombinationMetadata
from .analyzer import (
    ExecutionStrategy,
    QueryAnalysisResult,
    QueryComplexity,
    QueryDomain,
)
from .registry import PatternDomain, PatternRegistry, get_registry

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """
    Result of routing decision.

    Attributes:
        selected_patterns: List of pattern names to execute
        execution_strategy: Recommended execution strategy
        confidence: Confidence in routing decision (0-1)
        reasoning: Human-readable reasoning for the decision
        estimated_latency_ms: Estimated latency in milliseconds
        estimated_cost: Estimated cost multiplier
        is_meta_pattern: Whether a meta-pattern was selected
        meta_pattern_id: ID of meta-pattern if applicable
    """

    selected_patterns: list[str]
    execution_strategy: ExecutionStrategy
    confidence: float
    reasoning: str
    estimated_latency_ms: float
    estimated_cost: float = 1.0
    is_meta_pattern: bool = False
    meta_pattern_id: str | None = None


@dataclass
class RouterConfig:
    """Configuration for Smart Router."""

    enable_meta_patterns: bool = True
    enable_metrics: bool = False
    max_patterns: int = 3
    confidence_threshold: float = 0.6
    fallback_pattern: str = "adaptive_rag"


class SmartRouter:
    """
    Smart Router for fast pattern selection.

    Uses rule-based logic to quickly select optimal patterns for queries.
    Operating in two modes:
    1. Meta-Pattern Matching: Check if query matches a pre-defined meta-pattern
    2. Rule-Based Selection: Apply domain/intent/requirement rules to select patterns

    Usage:
        router = SmartRouter()
        analyzer = QueryAnalyzer()
        analysis = analyzer.analyze_with_routing(query)
        decision = router.route(analysis)
    """

    def __init__(
        self,
        registry: PatternRegistry | None = None,
        config: RouterConfig | None = None,
    ):
        """Initialize the Smart Router."""
        self.registry = registry or get_registry()
        self.config = config or RouterConfig()
        self._metrics_store: dict | None = None
        logger.info("Smart Router initialized")

    def route(self, analysis: QueryAnalysisResult) -> RoutingDecision:
        """
        Route query to optimal pattern(s).

        Args:
            analysis: Query analysis result from QueryAnalyzer

        Returns:
            RoutingDecision: Routing decision with selected patterns
        """
        start_time = time.time()

        try:
            # Step 1: Try meta-pattern matching first
            if self.config.enable_meta_patterns:
                meta_decision = self._match_meta_pattern(analysis)
                if meta_decision:
                    elapsed_ms = (time.time() - start_time) * 1000
                    logger.info(
                        f"Meta-pattern matched: {meta_decision.meta_pattern_id} "
                        f"in {elapsed_ms:.2f}ms"
                    )
                    return meta_decision

            # Step 2: Rule-based pattern selection
            patterns = self._select_patterns_by_rules(analysis)

            # Step 3: Rank patterns by heuristics
            patterns = self._rank_by_heuristics(patterns, analysis)

            # Step 4: Limit to max patterns
            patterns = patterns[: self.config.max_patterns]

            # Step 5: Determine execution strategy
            strategy = self._determine_strategy(patterns, analysis)

            # Step 6: Estimate metrics
            estimated_latency, estimated_cost = self._estimate_metrics(patterns)

            # Step 7: Calculate confidence
            confidence = self._calculate_confidence(patterns, analysis)

            # Step 8: Generate reasoning
            reasoning = self._generate_reasoning(patterns, analysis, strategy)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Routed to {len(patterns)} patterns in {elapsed_ms:.2f}ms: {patterns}")

            return RoutingDecision(
                selected_patterns=patterns,
                execution_strategy=strategy,
                confidence=confidence,
                reasoning=reasoning,
                estimated_latency_ms=estimated_latency,
                estimated_cost=estimated_cost,
                is_meta_pattern=False,
                meta_pattern_id=None,
            )

        except Exception as e:
            logger.error(f"Routing failed: {e}, using fallback")
            return RoutingDecision(
                selected_patterns=[self.config.fallback_pattern],
                execution_strategy=ExecutionStrategy.SEQUENTIAL,
                confidence=0.5,
                reasoning=f"Fallback due to error: {str(e)}",
                estimated_latency_ms=1000,
                estimated_cost=1.0,
                is_meta_pattern=False,
                meta_pattern_id=None,
            )

    def _match_meta_pattern(self, analysis: QueryAnalysisResult) -> RoutingDecision | None:
        """Check if query matches a pre-defined meta-pattern."""
        chars = analysis.characteristics

        requirements = {
            "requires_accuracy": chars.requires_accuracy,
            "requires_speed": chars.requires_speed,
            "requires_cost_optimization": chars.requires_cost_optimization,
            "requires_multimodal": chars.requires_multimodal,
            "requires_conversation_context": chars.requires_conversation_context,
            "domain": chars.domain.value,
        }

        for combo_id, combo in ALL_COMBINATIONS.items():
            if self._matches_meta_pattern(combo, requirements):
                estimated_latency = combo.estimated_latency_ms
                estimated_cost = combo.estimated_cost_multiplier
                confidence = 0.85

                reasoning = (
                    f"Matched meta-pattern '{combo.name}': {combo.description}. "
                    f"Use cases: {', '.join(combo.use_cases[:2])}"
                )

                return RoutingDecision(
                    selected_patterns=combo.patterns,
                    execution_strategy=ExecutionStrategy.SEQUENTIAL,
                    confidence=confidence,
                    reasoning=reasoning,
                    estimated_latency_ms=estimated_latency,
                    estimated_cost=estimated_cost,
                    is_meta_pattern=True,
                    meta_pattern_id=combo_id,
                )

        return None

    def _matches_meta_pattern(self, combo: CombinationMetadata, requirements: dict) -> bool:
        """Check if requirements match a meta-pattern."""
        for req_key, req_value in combo.requirements.items():
            if req_key == "domain":
                if requirements.get("domain") != req_value:
                    return False
            else:
                if requirements.get(req_key, False) != req_value:
                    return False
        return True

    def _select_patterns_by_rules(self, analysis: QueryAnalysisResult) -> list[str]:
        """Select patterns using rule-based logic."""
        chars = analysis.characteristics
        patterns = []

        # Rule 1: Domain-specific patterns
        if chars.domain == QueryDomain.CODE:
            patterns.append("code_rag")
        elif chars.domain == QueryDomain.CONVERSATIONAL:
            patterns.append("coral")
        elif chars.domain == QueryDomain.MULTIMODAL or chars.requires_multimodal:
            patterns.append("reveal")

        # Rule 2: Accuracy requirements
        if chars.requires_accuracy:
            if chars.complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
                patterns.append("self_rag")
            patterns.append("corrective_rag")

        # Rule 3: Speed requirements
        if chars.requires_speed:
            patterns.append("speculative_rag")
            if "adaptive_rag" not in patterns:
                patterns.append("adaptive_rag")

        # Rule 4: Cost optimization
        if chars.requires_cost_optimization:
            patterns.append("corag")
            if "adaptive_rag" not in patterns:
                patterns.append("adaptive_rag")

        # Rule 5: Conversation context
        if chars.requires_conversation_context:
            if "coral" not in patterns:
                patterns.append("coral")

        # Rule 6: Add semantic highlight for token reduction
        if len(patterns) > 0:
            patterns.append("semantic_highlight")

        # Rule 7: Default fallback
        if not patterns:
            patterns.append("adaptive_rag")

        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for pattern in patterns:
            if pattern not in seen:
                seen.add(pattern)
                unique_patterns.append(pattern)

        return unique_patterns

    def _rank_by_heuristics(self, patterns: list[str], analysis: QueryAnalysisResult) -> list[str]:
        """Rank patterns by heuristics."""
        chars = analysis.characteristics
        pattern_scores = []

        for pattern_name in patterns:
            metadata = self.registry.get_pattern(pattern_name)
            if not metadata:
                continue

            score = 0.0

            if chars.requires_accuracy:
                score += metadata.accuracy_boost * 0.4

            if chars.requires_speed:
                latency_score = max(0, 1.0 - (metadata.avg_latency_ms / 2000))
                score += latency_score * 0.3

            if chars.requires_cost_optimization:
                cost_score = max(0, 2.0 - metadata.cost_multiplier)
                score += cost_score * 0.2

            if chars.domain == QueryDomain.CODE and PatternDomain.CODE in metadata.domains:
                score += 0.1
            elif chars.domain == QueryDomain.CONVERSATIONAL and PatternDomain.CONVERSATIONAL in metadata.domains:
                score += 0.1
            elif chars.domain == QueryDomain.MULTIMODAL and PatternDomain.MULTIMODAL in metadata.domains:
                score += 0.1

            pattern_scores.append((pattern_name, score))

        pattern_scores.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in pattern_scores]

    def _determine_strategy(self, patterns: list[str], analysis: QueryAnalysisResult) -> ExecutionStrategy:
        """Determine execution strategy for selected patterns."""
        return analysis.recommended_strategy

    def _estimate_metrics(self, patterns: list[str]) -> tuple[float, float]:
        """Estimate latency and cost for pattern combination."""
        metrics = self.registry.estimate_combination_metrics(patterns)
        return (metrics["total_latency_ms"], metrics["total_cost_multiplier"])

    def _calculate_confidence(self, patterns: list[str], analysis: QueryAnalysisResult) -> float:
        """Calculate confidence in routing decision."""
        confidence = analysis.characteristics.confidence

        if len(patterns) > 2:
            confidence *= 0.9

        conflicts = self.registry.get_conflicts(patterns)
        if conflicts:
            confidence *= 0.7

        if len(patterns) == 1:
            confidence = min(confidence * 1.1, 0.95)

        return max(0.5, min(confidence, 0.95))

    def _generate_reasoning(
        self,
        patterns: list[str],
        analysis: QueryAnalysisResult,
        strategy: ExecutionStrategy,
    ) -> str:
        """Generate human-readable reasoning for routing decision."""
        chars = analysis.characteristics
        reasons = []

        if chars.domain != QueryDomain.GENERAL:
            reasons.append(f"Domain: {chars.domain.value}")

        reasons.append(f"Complexity: {chars.complexity.value}")

        if chars.requires_accuracy:
            reasons.append("High accuracy required")
        if chars.requires_speed:
            reasons.append("Fast response required")
        if chars.requires_cost_optimization:
            reasons.append("Cost optimization required")

        pattern_names = ", ".join(patterns)
        reasons.append(f"Selected patterns: {pattern_names}")
        reasons.append(f"Strategy: {strategy.value}")

        return "; ".join(reasons)


__all__ = [
    "RoutingDecision",
    "RouterConfig",
    "SmartRouter",
]

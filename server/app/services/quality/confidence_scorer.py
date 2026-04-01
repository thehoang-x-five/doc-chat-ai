"""
Confidence Scorer - Weighted confidence scoring for RAG responses.

This module provides:
1. Composite confidence score calculation
2. Weighted formula: (Hallucination * 0.4) + (Relevance * 0.3) + (Safety * 0.3)
3. Latency penalty for SLA violations
4. Retry trigger for low-confidence responses

"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceComponents:
    """Components that make up the confidence score."""
    hallucination_score: float = 1.0  # 1.0 = no hallucination, 0.0 = fully hallucinated
    relevance_score: float = 1.0  # How relevant is the answer
    safety_score: float = 1.0  # Safety check score
    fact_check_score: float = 1.0  # Fact verification score
    grounding_score: float = 1.0  # How well grounded in sources
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "hallucination": self.hallucination_score,
            "relevance": self.relevance_score,
            "safety": self.safety_score,
            "fact_check": self.fact_check_score,
            "grounding": self.grounding_score,
        }


@dataclass
class ConfidenceResult:
    """Result of confidence scoring."""
    overall_score: float  # 0-1
    components: ConfidenceComponents
    is_confident: bool  # Above threshold
    needs_retry: bool  # Below retry threshold
    latency_penalty_applied: bool = False
    original_score: Optional[float] = None  # Before latency penalty
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "is_confident": self.is_confident,
            "needs_retry": self.needs_retry,
            "components": self.components.to_dict(),
            "latency_penalty_applied": self.latency_penalty_applied,
        }


class ConfidenceScorer:
    """
    Confidence Scorer for RAG response quality assessment.
    
    Combines multiple quality signals into a single confidence score:
    - Hallucination score (weight: 0.4)
    - Relevance score (weight: 0.3)
    - Safety score (weight: 0.3)
    
    Additional modifiers:
    - Latency penalty if response exceeds SLA budget
    - Fact check bonus/penalty
    - Grounding bonus
    
    Usage:
        scorer = ConfidenceScorer()
        result = scorer.compute_confidence(
            components=ConfidenceComponents(
                hallucination_score=0.9,
                relevance_score=0.85,
                safety_score=1.0,
            ),
            latency_ms=1500,
            budget_ms=2000,
        )
        if result.needs_retry:
            # Trigger regeneration
            pass
    """
    
    # Default weights
    DEFAULT_WEIGHTS = {
        "hallucination": 0.40,
        "relevance": 0.30,
        "safety": 0.30,
    }
    
    # Default thresholds
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    DEFAULT_RETRY_THRESHOLD = 0.5
    
    # Latency penalty
    LATENCY_PENALTY_FACTOR = 0.1  # Max 10% penalty
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        retry_threshold: float = DEFAULT_RETRY_THRESHOLD,
        apply_latency_penalty: bool = True,
    ):
        """
        Initialize Confidence Scorer.
        
        Args:
            weights: Custom weights for components
            confidence_threshold: Minimum score for confident response
            retry_threshold: Score below which retry is triggered
            apply_latency_penalty: Whether to penalize SLA violations
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.confidence_threshold = confidence_threshold
        self.retry_threshold = retry_threshold
        self.apply_latency_penalty = apply_latency_penalty
        
        # Normalize weights
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            self.weights = {k: v / total for k, v in self.weights.items()}
        
        logger.info(f"ConfidenceScorer initialized (threshold={confidence_threshold})")
    
    def compute_confidence(
        self,
        components: Optional[ConfidenceComponents] = None,
        hallucination_score: Optional[float] = None,
        relevance_score: Optional[float] = None,
        safety_score: Optional[float] = None,
        fact_check_score: Optional[float] = None,
        grounding_score: Optional[float] = None,
        latency_ms: Optional[float] = None,
        budget_ms: Optional[float] = None,
        pattern_confidence: Optional[float] = None,
    ) -> ConfidenceResult:
        """
        Compute overall confidence score.
        
        Args:
            components: Pre-built components object
            hallucination_score: Score from hallucination check (0-1)
            relevance_score: Relevance score (0-1)
            safety_score: Safety check score (0-1)
            fact_check_score: Fact verification score (0-1)
            grounding_score: Grounding score (0-1)
            latency_ms: Actual response latency
            budget_ms: SLA budget for response
            pattern_confidence: Optional pattern-level confidence
            
        Returns:
            ConfidenceResult with overall score and details
        """
        # Build components if not provided
        if components is None:
            components = ConfidenceComponents(
                hallucination_score=hallucination_score if hallucination_score is not None else 1.0,
                relevance_score=relevance_score if relevance_score is not None else 1.0,
                safety_score=safety_score if safety_score is not None else 1.0,
                fact_check_score=fact_check_score if fact_check_score is not None else 1.0,
                grounding_score=grounding_score if grounding_score is not None else 1.0,
            )
        
        # Calculate weighted base score
        base_score = (
            self.weights.get("hallucination", 0.4) * components.hallucination_score +
            self.weights.get("relevance", 0.3) * components.relevance_score +
            self.weights.get("safety", 0.3) * components.safety_score
        )
        
        # Apply modifiers
        score = base_score
        original_score = None
        latency_penalty_applied = False
        
        # Factor in fact check (bonus/penalty)
        if components.fact_check_score < 1.0:
            fact_penalty = (1.0 - components.fact_check_score) * 0.15
            score -= fact_penalty
        
        # Factor in grounding (bonus)
        if components.grounding_score > 0.8:
            grounding_bonus = (components.grounding_score - 0.8) * 0.1
            score += grounding_bonus
        
        # Factor in pattern confidence if provided
        if pattern_confidence is not None:
            score = score * 0.7 + pattern_confidence * 0.3
        
        # Apply latency penalty
        if self.apply_latency_penalty and latency_ms and budget_ms:
            if latency_ms > budget_ms:
                original_score = score
                latency_penalty_applied = True
                
                # Penalty increases with overage
                overage_ratio = min((latency_ms - budget_ms) / budget_ms, 1.0)
                penalty = overage_ratio * self.LATENCY_PENALTY_FACTOR
                score = max(0.0, score - penalty)
        
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        
        # Determine status
        is_confident = score >= self.confidence_threshold
        needs_retry = score < self.retry_threshold
        
        return ConfidenceResult(
            overall_score=score,
            components=components,
            is_confident=is_confident,
            needs_retry=needs_retry,
            latency_penalty_applied=latency_penalty_applied,
            original_score=original_score,
            metadata={
                "threshold": self.confidence_threshold,
                "retry_threshold": self.retry_threshold,
                "weights": self.weights,
            },
        )
    
    def compute_from_validation(
        self,
        validation_result: Any,  # ValidationResult from result_validator
        latency_ms: Optional[float] = None,
        budget_ms: Optional[float] = None,
    ) -> ConfidenceResult:
        """
        Compute confidence from a ValidationResult.
        
        Args:
            validation_result: Result from ResultValidator
            latency_ms: Actual latency
            budget_ms: SLA budget
            
        Returns:
            ConfidenceResult
        """
        # Extract scores from validation result
        hallucination_score = 1.0 - getattr(validation_result, 'hallucination_score', 0.0)
        relevance_score = getattr(validation_result, 'relevance_score', 1.0)
        grounding_score = getattr(validation_result, 'groundedness_score', 1.0)
        
        # Determine safety score
        safety_issues = getattr(validation_result, 'issues', [])
        safety_score = 1.0 if not safety_issues else max(0.5, 1.0 - len(safety_issues) * 0.1)
        
        return self.compute_confidence(
            hallucination_score=hallucination_score,
            relevance_score=relevance_score,
            safety_score=safety_score,
            grounding_score=grounding_score,
            latency_ms=latency_ms,
            budget_ms=budget_ms,
        )
    
    def should_retry(self, score: float) -> bool:
        """Check if score warrants retry."""
        return score < self.retry_threshold
    
    def get_confidence_level(self, score: float) -> str:
        """Get human-readable confidence level."""
        if score >= 0.9:
            return "very_high"
        elif score >= 0.8:
            return "high"
        elif score >= 0.7:
            return "medium"
        elif score >= 0.5:
            return "low"
        else:
            return "very_low"


# Default instance
confidence_scorer = ConfidenceScorer()

"""
Pattern Combinations - Predefined optimal combinations of RAG patterns.

This module provides:
1. Predefined pattern combinations for common use cases
2. Combination metadata (synergy factors, complexity, use cases)
3. Combination validation and recommendation logic

Migrated from raganything/patterns/combinations.py
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CombinationType(Enum):
    """Types of pattern combinations."""
    
    HIGH_ACCURACY = "high_accuracy"
    COST_OPTIMIZED = "cost_optimized"
    RESEARCH = "research"
    MULTIMODAL_CONVERSATIONAL = "multimodal_conversational"
    SELF_OPTIMIZING = "self_optimizing"


@dataclass
class CombinationMetadata:
    """
    Metadata for a pattern combination.
    
    Attributes:
        name: Combination name
        type: Combination type
        patterns: List of pattern names in execution order
        description: Combination description
        use_cases: List of use cases
        synergy_factor: Expected synergy factor (performance improvement)
        complexity_overhead: Complexity overhead (low/medium/high)
        estimated_latency_ms: Estimated latency in milliseconds
        estimated_cost_multiplier: Cost multiplier vs single pattern
        requirements: Requirements for using this combination
        dag: DAG structure for workflow execution
    """
    
    name: str
    type: CombinationType
    patterns: List[str]
    description: str
    use_cases: List[str] = field(default_factory=list)
    synergy_factor: float = 1.0
    complexity_overhead: str = "medium"
    estimated_latency_ms: int = 1000
    estimated_cost_multiplier: float = 1.0
    requirements: Dict[str, bool] = field(default_factory=dict)
    dag: Dict[str, List[str]] = field(default_factory=dict)


# Predefined Combinations

COMBINATION_1_HIGH_ACCURACY = CombinationMetadata(
    name="High-Accuracy RAG",
    type=CombinationType.HIGH_ACCURACY,
    patterns=["adaptive_rag", "corrective_rag"],
    description="Combines Adaptive RAG (intelligent routing) and Corrective RAG (validation + correction) for maximum accuracy.",
    use_cases=[
        "Critical decision-making queries",
        "Medical/legal/financial domains requiring high accuracy",
        "Complex research questions",
        "Fact-checking and verification",
    ],
    synergy_factor=1.4,
    complexity_overhead="high",
    estimated_latency_ms=2000,
    estimated_cost_multiplier=1.5,
    requirements={"requires_accuracy": True},
    dag={"adaptive_rag": [], "corrective_rag": ["adaptive_rag"]},
)

COMBINATION_2_COST_OPTIMIZED = CombinationMetadata(
    name="Cost-Optimized RAG",
    type=CombinationType.COST_OPTIMIZED,
    patterns=["speculative_rag", "corag"],
    description="Combines Speculative RAG (parallel draft generation) and CORAG (cost-constrained optimization) for speed and cost efficiency.",
    use_cases=[
        "High-volume query processing",
        "Real-time applications requiring fast responses",
        "Cost-sensitive deployments",
        "Chatbots and conversational AI",
    ],
    synergy_factor=1.6,
    complexity_overhead="medium",
    estimated_latency_ms=500,
    estimated_cost_multiplier=0.7,
    requirements={"requires_speed": True, "requires_cost_optimization": True},
    dag={"speculative_rag": [], "corag": ["speculative_rag"]},
)

COMBINATION_3_MAXIMUM_ACCURACY = CombinationMetadata(
    name="Maximum Accuracy RAG",
    type=CombinationType.RESEARCH,
    patterns=["self_rag", "corrective_rag"],
    description="Combines Self RAG (iterative refinement) and Corrective RAG (validation) for maximum accuracy in research queries.",
    use_cases=[
        "Academic research queries",
        "Scientific literature analysis",
        "Complex multi-step reasoning",
        "Publication-quality information retrieval",
    ],
    synergy_factor=1.8,
    complexity_overhead="high",
    estimated_latency_ms=3000,
    estimated_cost_multiplier=2.0,
    requirements={"requires_accuracy": True},
    dag={"self_rag": [], "corrective_rag": ["self_rag"]},
)

COMBINATION_4_MULTIMODAL_CONVERSATIONAL = CombinationMetadata(
    name="Multimodal Conversational RAG",
    type=CombinationType.MULTIMODAL_CONVERSATIONAL,
    patterns=["reveal", "coral"],
    description="Combines REVEAL (visual-language understanding) and CORAL (conversational context) for multimodal conversations.",
    use_cases=[
        "Multimodal chatbots (text + images)",
        "Visual question answering",
        "Document analysis with images/tables/charts",
        "Multi-turn conversations with visual context",
    ],
    synergy_factor=1.5,
    complexity_overhead="high",
    estimated_latency_ms=2500,
    estimated_cost_multiplier=1.8,
    requirements={"requires_multimodal": True, "requires_conversation_context": True},
    dag={"reveal": [], "coral": ["reveal"]},
)

COMBINATION_5_SELF_OPTIMIZING = CombinationMetadata(
    name="Self-Optimizing RAG",
    type=CombinationType.SELF_OPTIMIZING,
    patterns=["adaptive_rag", "semantic_highlight"],
    description="Combines Adaptive RAG (intelligent routing) with Semantic Highlight (token optimization) for continuous optimization.",
    use_cases=[
        "Production systems requiring continuous optimization",
        "Long-running deployments",
        "Systems with evolving query patterns",
        "Performance-critical applications",
    ],
    synergy_factor=1.7,
    complexity_overhead="medium",
    estimated_latency_ms=1200,
    estimated_cost_multiplier=0.5,
    requirements={"requires_cost_optimization": True},
    dag={"adaptive_rag": [], "semantic_highlight": ["adaptive_rag"]},
)


# Combination Registry
ALL_COMBINATIONS = {
    "high_accuracy": COMBINATION_1_HIGH_ACCURACY,
    "cost_optimized": COMBINATION_2_COST_OPTIMIZED,
    "maximum_accuracy": COMBINATION_3_MAXIMUM_ACCURACY,
    "multimodal_conversational": COMBINATION_4_MULTIMODAL_CONVERSATIONAL,
    "self_optimizing": COMBINATION_5_SELF_OPTIMIZING,
}


def recommend_combination(
    requirements: Dict[str, bool],
    available_patterns: List[str],
) -> Optional[CombinationMetadata]:
    """Recommend optimal combination based on requirements."""
    scores = {}
    
    for combo_id, combo in ALL_COMBINATIONS.items():
        # Check if all required patterns are available
        if not all(p in available_patterns for p in combo.patterns):
            continue
        
        # Calculate match score
        score = 0
        for req_key, req_value in requirements.items():
            if req_key in combo.requirements:
                if combo.requirements[req_key] == req_value:
                    score += 1
        
        scores[combo_id] = score
    
    if scores:
        best_combo_id = max(scores, key=scores.get)
        if scores[best_combo_id] > 0:
            return ALL_COMBINATIONS[best_combo_id]
    
    return None


def get_combination(combination_id: str) -> Optional[CombinationMetadata]:
    """Get combination by ID."""
    return ALL_COMBINATIONS.get(combination_id)


def list_combinations() -> List[CombinationMetadata]:
    """List all available combinations."""
    return list(ALL_COMBINATIONS.values())


def validate_combination(
    combination: CombinationMetadata,
    available_patterns: List[str],
) -> tuple:
    """Validate if a combination can be executed."""
    errors = []
    
    missing_patterns = [
        p for p in combination.patterns
        if p not in available_patterns
    ]
    
    if missing_patterns:
        errors.append(f"Missing required patterns: {', '.join(missing_patterns)}")
    
    return len(errors) == 0, errors


def get_execution_order(combination: CombinationMetadata) -> List[str]:
    """Get execution order for a combination."""
    return combination.patterns.copy()


def estimate_latency(combination: CombinationMetadata) -> int:
    """Estimate latency for a combination."""
    return combination.estimated_latency_ms


def estimate_cost(
    combination: CombinationMetadata,
    base_cost: float = 1.0,
) -> float:
    """Estimate cost for a combination."""
    return base_cost * combination.estimated_cost_multiplier


__all__ = [
    "CombinationType",
    "CombinationMetadata",
    "ALL_COMBINATIONS",
    "recommend_combination",
    "get_combination",
    "list_combinations",
    "validate_combination",
    "get_execution_order",
    "estimate_latency",
    "estimate_cost",
]

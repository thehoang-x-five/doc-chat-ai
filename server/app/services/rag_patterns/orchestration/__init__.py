"""
Orchestration Module - Pattern orchestration and workflow management.

This module provides:
1. Pattern Registry - Central registry for RAG patterns
2. Query Analyzer - Analyzes queries to determine optimal patterns
3. Pattern Orchestrator - Orchestrates pattern execution
4. Smart Router - Fast pattern selection using rules
5. Workflow Planner - Creates DAG-based execution plans
6. Combinations - Predefined pattern combinations

Migrated from raganything/patterns/
"""

from .registry import (
    PatternCapability,
    PatternDomain,
    PatternComplexity,
    PatternMetadata,
    PatternRegistry,
    get_registry,
)

from .analyzer import (
    RoutingMode,
    QueryComplexity,
    ExecutionStrategy,
    QueryDomain,
    QueryIntent,
    QueryCharacteristics,
    QueryAnalysisResult,
    QueryAnalyzer,
)

from .orchestrator import (
    PatternExecution,
    OrchestrationResult,
    PatternOrchestrator,
)

from .router import (
    RoutingDecision,
    RouterConfig,
    SmartRouter,
)

from .planner import (
    WorkflowNode,
    WorkflowPlan,
    PlannerConfig,
    WorkflowPlanner,
)

from .combinations import (
    CombinationType,
    CombinationMetadata,
    ALL_COMBINATIONS,
    recommend_combination,
    get_combination,
    list_combinations,
    validate_combination,
    get_execution_order,
    estimate_latency,
    estimate_cost,
)

__all__ = [
    # Registry
    "PatternCapability",
    "PatternDomain",
    "PatternComplexity",
    "PatternMetadata",
    "PatternRegistry",
    "get_registry",
    
    # Analyzer
    "RoutingMode",
    "QueryComplexity",
    "ExecutionStrategy",
    "QueryDomain",
    "QueryIntent",
    "QueryCharacteristics",
    "QueryAnalysisResult",
    "QueryAnalyzer",
    
    # Orchestrator
    "PatternExecution",
    "OrchestrationResult",
    "PatternOrchestrator",
    
    # Router
    "RoutingDecision",
    "RouterConfig",
    "SmartRouter",
    
    # Planner
    "WorkflowNode",
    "WorkflowPlan",
    "PlannerConfig",
    "WorkflowPlanner",
    
    # Combinations
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

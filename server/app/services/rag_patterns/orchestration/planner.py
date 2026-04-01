"""
Workflow Planner - Creates multi-step execution plans (DAGs) for complex queries.

This module provides:
1. DAG-based execution planning for composite patterns
2. Budget allocation across workflow nodes
3. Dependency resolution and validation
4. Template-based and rule-based planning strategies

Migrated from raganything/patterns/workflow_planner.py
"""
import logging
import uuid
from dataclasses import dataclass, field

from .combinations import ALL_COMBINATIONS, CombinationMetadata
from .analyzer import (
    ExecutionStrategy,
    QueryAnalysisResult,
    QueryDomain,
)
from .registry import PatternRegistry, get_registry

logger = logging.getLogger(__name__)


@dataclass
class WorkflowNode:
    """
    Node in workflow DAG.

    Attributes:
        node_id: Unique identifier for node
        pattern_name: Name of pattern to execute
        dependencies: List of node_ids this node depends on
        timeout_ms: Timeout for node execution
        fallback_node_id: Node ID to fallback to if failed
    """

    node_id: str
    pattern_name: str
    dependencies: list[str] = field(default_factory=list)
    timeout_ms: int = 5000
    fallback_node_id: str | None = None


@dataclass
class WorkflowPlan:
    """
    Complete workflow execution plan.

    Attributes:
        plan_id: Unique identifier for plan
        nodes: List of workflow nodes
        execution_strategy: Strategy for executing workflow
        total_budget_ms: Total SLA budget
        estimated_latency_ms: Estimated latency
        estimated_cost: Estimated cost multiplier
        dag: DAG representation (adjacency list)
        entry_nodes: Nodes without dependencies (starting points)
        exit_nodes: Nodes without dependents (ending points)
    """

    plan_id: str
    nodes: list[WorkflowNode]
    execution_strategy: ExecutionStrategy
    total_budget_ms: int
    estimated_latency_ms: float
    estimated_cost: float
    dag: dict[str, list[str]] = field(default_factory=dict)
    entry_nodes: list[str] = field(default_factory=list)
    exit_nodes: list[str] = field(default_factory=list)


@dataclass
class PlannerConfig:
    """Configuration for Workflow Planner."""

    max_nodes: int = 10
    max_depth: int = 5
    enable_fallback: bool = True
    buffer_percentage: float = 0.1  # 10% buffer


class WorkflowPlanner:
    """
    Workflow Planner creates execution plans for complex queries.

    Strategies:
    1. Template-Based: Match query with pre-defined meta-patterns
    2. Rule-Based: Apply composition rules based on query characteristics

    Features:
    - DAG generation with dependency resolution
    - Budget allocation across nodes
    - Cycle detection and validation
    - Fallback node creation
    - Multiple execution strategies

    Usage:
        planner = WorkflowPlanner()
        analyzer = QueryAnalyzer()
        analysis = analyzer.analyze_with_routing(query)
        plan = planner.plan(analysis)
    """

    def __init__(
        self,
        registry: PatternRegistry | None = None,
        config: PlannerConfig | None = None,
    ):
        """Initialize Workflow Planner."""
        self.registry = registry or get_registry()
        self.config = config or PlannerConfig()
        logger.info("Workflow Planner initialized")

    def plan(self, analysis: QueryAnalysisResult) -> WorkflowPlan:
        """
        Create workflow execution plan for query.

        Args:
            analysis: Query analysis result from QueryAnalyzer

        Returns:
            WorkflowPlan: Complete workflow plan with DAG
        """
        try:
            # Step 1: Try template-based planning (meta-patterns)
            meta_plan = self._plan_from_meta_pattern(analysis)
            if meta_plan:
                logger.info(f"Created plan from meta-pattern: {meta_plan.plan_id}")
                return meta_plan

            # Step 2: Rule-based planning
            patterns = self._select_patterns_by_rules(analysis)

            # Step 3: Determine execution strategy
            strategy = analysis.recommended_strategy

            # Step 4: Build DAG
            dag = self._build_dag(patterns, strategy)

            # Step 5: Create workflow nodes
            nodes = self._create_nodes(patterns, dag, analysis.sla_budget_ms)

            # Step 6: Allocate budgets
            self._allocate_budgets(nodes, analysis.sla_budget_ms)

            # Step 7: Add fallback nodes if enabled
            if self.config.enable_fallback:
                self._add_fallback_nodes(nodes, dag)

            # Step 8: Validate DAG
            is_valid, errors = self._validate_dag(nodes, dag)
            if not is_valid:
                raise ValueError(f"Invalid DAG: {errors}")

            # Step 9: Identify entry and exit nodes
            entry_nodes = self._find_entry_nodes(nodes)
            exit_nodes = self._find_exit_nodes(nodes, dag)

            # Step 10: Estimate metrics
            estimated_latency, estimated_cost = self._estimate_metrics(patterns)

            plan_id = str(uuid.uuid4())[:8]

            logger.info(
                f"Created workflow plan {plan_id}: "
                f"{len(nodes)} nodes, strategy={strategy.value}"
            )

            return WorkflowPlan(
                plan_id=plan_id,
                nodes=nodes,
                execution_strategy=strategy,
                total_budget_ms=analysis.sla_budget_ms,
                estimated_latency_ms=estimated_latency,
                estimated_cost=estimated_cost,
                dag=dag,
                entry_nodes=entry_nodes,
                exit_nodes=exit_nodes,
            )

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return self._create_fallback_plan(analysis)

    def _plan_from_meta_pattern(self, analysis: QueryAnalysisResult) -> WorkflowPlan | None:
        """Create plan from pre-defined meta-pattern."""
        chars = analysis.characteristics

        requirements = {
            "requires_accuracy": chars.requires_accuracy,
            "requires_speed": chars.requires_speed,
            "requires_cost_optimization": chars.requires_cost_optimization,
            "requires_multimodal": chars.requires_multimodal,
            "requires_conversation_context": chars.requires_conversation_context,
            "domain": chars.domain.value,
        }

        for _combo_id, combo in ALL_COMBINATIONS.items():
            if self._matches_meta_pattern(combo, requirements):
                return self._create_plan_from_combination(combo, analysis)

        return None

    def _matches_meta_pattern(self, combo: CombinationMetadata, requirements: dict) -> bool:
        """Check if requirements match meta-pattern."""
        for req_key, req_value in combo.requirements.items():
            if req_key == "domain":
                if requirements.get("domain") != req_value:
                    return False
            else:
                if requirements.get(req_key, False) != req_value:
                    return False
        return True

    def _create_plan_from_combination(
        self,
        combo: CombinationMetadata,
        analysis: QueryAnalysisResult,
    ) -> WorkflowPlan:
        """Create workflow plan from combination metadata."""
        dag = combo.dag.copy()
        nodes = self._create_nodes(combo.patterns, dag, analysis.sla_budget_ms)
        self._allocate_budgets(nodes, analysis.sla_budget_ms)
        entry_nodes = self._find_entry_nodes(nodes)
        exit_nodes = self._find_exit_nodes(nodes, dag)
        plan_id = str(uuid.uuid4())[:8]

        return WorkflowPlan(
            plan_id=plan_id,
            nodes=nodes,
            execution_strategy=ExecutionStrategy.SEQUENTIAL,
            total_budget_ms=analysis.sla_budget_ms,
            estimated_latency_ms=combo.estimated_latency_ms,
            estimated_cost=combo.estimated_cost_multiplier,
            dag=dag,
            entry_nodes=entry_nodes,
            exit_nodes=exit_nodes,
        )

    def _select_patterns_by_rules(self, analysis: QueryAnalysisResult) -> list[str]:
        """Select patterns using rule-based logic."""
        chars = analysis.characteristics
        patterns = []

        # Rule 1: Domain-specific patterns
        if chars.domain == QueryDomain.CODE:
            patterns.append("code_rag")
        elif chars.domain == QueryDomain.CONVERSATIONAL:
            patterns.append("coral")
        elif chars.requires_multimodal:
            patterns.append("reveal")

        # Rule 2: Accuracy requirements
        if chars.requires_accuracy:
            patterns.append("self_rag")
            patterns.append("corrective_rag")

        # Rule 3: Default base pattern
        if "adaptive_rag" not in patterns:
            patterns.insert(0, "adaptive_rag")

        # Remove duplicates
        seen = set()
        unique_patterns = []
        for pattern in patterns:
            if pattern not in seen:
                seen.add(pattern)
                unique_patterns.append(pattern)

        return unique_patterns[:self.config.max_nodes]

    def _build_dag(
        self,
        patterns: list[str],
        strategy: ExecutionStrategy,
    ) -> dict[str, list[str]]:
        """Build DAG from pattern list and execution strategy."""
        dag: dict[str, list[str]] = {}

        if strategy == ExecutionStrategy.SEQUENTIAL:
            for i, pattern in enumerate(patterns):
                if i == 0:
                    dag[pattern] = []
                else:
                    dag[pattern] = [patterns[i - 1]]

        elif strategy == ExecutionStrategy.PARALLEL:
            for pattern in patterns:
                dag[pattern] = []

        elif strategy == ExecutionStrategy.FALLBACK:
            for pattern in patterns:
                dag[pattern] = []

        elif strategy == ExecutionStrategy.CONDITIONAL:
            for i, pattern in enumerate(patterns):
                if i == 0:
                    dag[pattern] = []
                else:
                    dag[pattern] = [patterns[i - 1]]

        else:
            for i, pattern in enumerate(patterns):
                if i == 0:
                    dag[pattern] = []
                else:
                    dag[pattern] = [patterns[i - 1]]

        return dag

    def _create_nodes(
        self,
        patterns: list[str],
        dag: dict[str, list[str]],
        total_budget_ms: int,
    ) -> list[WorkflowNode]:
        """Create workflow nodes from patterns and DAG."""
        nodes = []

        for pattern in patterns:
            node_id = f"{pattern}_{uuid.uuid4().hex[:6]}"

            dependencies = []
            for dep_pattern in dag.get(pattern, []):
                dep_node = next(
                    (n for n in nodes if n.pattern_name == dep_pattern),
                    None
                )
                if dep_node:
                    dependencies.append(dep_node.node_id)

            timeout_ms = total_budget_ms // max(len(patterns), 1)

            node = WorkflowNode(
                node_id=node_id,
                pattern_name=pattern,
                dependencies=dependencies,
                timeout_ms=timeout_ms,
                fallback_node_id=None,
            )

            nodes.append(node)

        return nodes

    def _allocate_budgets(
        self,
        nodes: list[WorkflowNode],
        total_budget_ms: int,
    ) -> None:
        """Distribute latency budget across nodes."""
        if not nodes:
            return

        buffer_ms = int(total_budget_ms * self.config.buffer_percentage)
        available_budget = total_budget_ms - buffer_ms

        pattern_latencies = {}
        for node in nodes:
            metadata = self.registry.get_pattern(node.pattern_name)
            if metadata:
                pattern_latencies[node.node_id] = metadata.avg_latency_ms
            else:
                pattern_latencies[node.node_id] = 1000

        total_weight = sum(pattern_latencies.values())

        for node in nodes:
            if total_weight > 0:
                weight = pattern_latencies[node.node_id]
                node.timeout_ms = int((weight / total_weight) * available_budget)
            else:
                node.timeout_ms = available_budget // len(nodes)

            node.timeout_ms = max(node.timeout_ms, 500)

    def _add_fallback_nodes(
        self,
        nodes: list[WorkflowNode],
        dag: dict[str, list[str]],
    ) -> None:
        """Add fallback nodes for critical patterns."""
        critical_patterns = {"self_rag", "corrective_rag"}

        for node in nodes:
            if node.pattern_name in critical_patterns:
                fallback_pattern = "adaptive_rag"

                if not any(n.pattern_name == fallback_pattern for n in nodes):
                    fallback_node_id = f"{fallback_pattern}_fallback_{uuid.uuid4().hex[:6]}"

                    fallback_node = WorkflowNode(
                        node_id=fallback_node_id,
                        pattern_name=fallback_pattern,
                        dependencies=node.dependencies.copy(),
                        timeout_ms=node.timeout_ms // 2,
                        fallback_node_id=None,
                    )

                    node.fallback_node_id = fallback_node_id
                    nodes.append(fallback_node)

    def _validate_dag(
        self,
        nodes: list[WorkflowNode],
        dag: dict[str, list[str]],
    ) -> tuple[bool, list[str]]:
        """Validate DAG structure."""
        errors = []

        if self._has_cycle(nodes):
            errors.append("DAG contains cycles")

        node_ids = {n.node_id for n in nodes}
        for node in nodes:
            for dep_id in node.dependencies:
                if dep_id not in node_ids:
                    errors.append(f"Node {node.node_id} has invalid dependency: {dep_id}")

        max_depth = self._calculate_max_depth(nodes)
        if max_depth > self.config.max_depth:
            errors.append(f"DAG depth {max_depth} exceeds max {self.config.max_depth}")

        return len(errors) == 0, errors

    def _has_cycle(self, nodes: list[WorkflowNode]) -> bool:
        """Check for cycles in DAG using DFS."""
        graph = {node.node_id: node.dependencies for node in nodes}
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for dep_id in graph.get(node_id, []):
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node in nodes:
            if node.node_id not in visited:
                if dfs(node.node_id):
                    return True

        return False

    def _calculate_max_depth(self, nodes: list[WorkflowNode]) -> int:
        """Calculate maximum depth of DAG."""
        if not nodes:
            return 0

        node_map = {n.node_id: n for n in nodes}
        depths = {}

        def get_depth(node_id: str) -> int:
            if node_id in depths:
                return depths[node_id]

            node = node_map.get(node_id)
            if not node or not node.dependencies:
                depths[node_id] = 1
                return 1

            max_dep_depth = max(get_depth(dep_id) for dep_id in node.dependencies)
            depths[node_id] = max_dep_depth + 1
            return depths[node_id]

        return max(get_depth(node.node_id) for node in nodes)

    def _find_entry_nodes(self, nodes: list[WorkflowNode]) -> list[str]:
        """Find entry nodes (nodes without dependencies)."""
        return [n.node_id for n in nodes if not n.dependencies]

    def _find_exit_nodes(
        self,
        nodes: list[WorkflowNode],
        dag: dict[str, list[str]],
    ) -> list[str]:
        """Find exit nodes (nodes without dependents)."""
        dependents: dict[str, list[str]] = {n.node_id: [] for n in nodes}

        for node in nodes:
            for dep_id in node.dependencies:
                if dep_id in dependents:
                    dependents[dep_id].append(node.node_id)

        return [node_id for node_id, deps in dependents.items() if not deps]

    def _estimate_metrics(self, patterns: list[str]) -> tuple[float, float]:
        """Estimate latency and cost for pattern combination."""
        metrics = self.registry.estimate_combination_metrics(patterns)
        return (metrics["total_latency_ms"], metrics["total_cost_multiplier"])

    def _create_fallback_plan(self, analysis: QueryAnalysisResult) -> WorkflowPlan:
        """Create simple fallback plan when planning fails."""
        pattern = "adaptive_rag"
        node_id = f"{pattern}_{uuid.uuid4().hex[:6]}"

        node = WorkflowNode(
            node_id=node_id,
            pattern_name=pattern,
            dependencies=[],
            timeout_ms=analysis.sla_budget_ms,
            fallback_node_id=None,
        )

        plan_id = str(uuid.uuid4())[:8]

        logger.warning(f"Created fallback plan {plan_id} with single pattern")

        return WorkflowPlan(
            plan_id=plan_id,
            nodes=[node],
            execution_strategy=ExecutionStrategy.SEQUENTIAL,
            total_budget_ms=analysis.sla_budget_ms,
            estimated_latency_ms=1000,
            estimated_cost=1.0,
            dag={pattern: []},
            entry_nodes=[node_id],
            exit_nodes=[node_id],
        )


__all__ = [
    "WorkflowNode",
    "WorkflowPlan",
    "PlannerConfig",
    "WorkflowPlanner",
]

"""
Pattern Orchestrator - Orchestrates execution of multiple RAG patterns.

This module provides:
1. Pattern selection based on query characteristics
2. Sequential, parallel, conditional, and layered execution strategies
3. Pattern coordination and result aggregation
4. Error handling and fallback mechanisms
5. DAG-based workflow execution with timeout enforcement

Migrated from raganything/patterns/orchestrator.py
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from .analyzer import QueryAnalyzer, QueryCharacteristics
from .registry import PatternRegistry, get_registry

# Forward references for type hints
if TYPE_CHECKING:
    from .planner import WorkflowNode, WorkflowPlan

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Pattern execution strategies."""

    SEQUENTIAL = "sequential"      # Execute patterns one after another
    PARALLEL = "parallel"          # Execute patterns in parallel
    CONDITIONAL = "conditional"    # Execute based on conditions
    LAYERED = "layered"           # Execute in layers (pipeline)
    FALLBACK = "fallback"         # Execute with fallback on failure
    LOOP = "loop"                 # Execute with iterative refinement


@dataclass
class PatternExecution:
    """
    Result of a pattern execution.

    Attributes:
        pattern_name: Name of the pattern
        success: Whether execution succeeded
        result: Execution result
        error: Error message if failed
        latency_ms: Execution latency in milliseconds
        metadata: Additional metadata
    """

    pattern_name: str
    success: bool
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """
    Result of pattern orchestration.

    Attributes:
        query: Original query
        strategy: Execution strategy used
        patterns_executed: List of patterns executed
        executions: List of pattern executions
        final_result: Final aggregated result
        total_latency_ms: Total latency
        success: Whether orchestration succeeded
        metadata: Additional metadata
    """

    query: str
    strategy: ExecutionStrategy
    patterns_executed: list[str]
    executions: list[PatternExecution]
    final_result: Any = None
    total_latency_ms: float = 0.0
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PatternOrchestrator:
    """
    Orchestrates execution of multiple RAG patterns.

    Features:
    - Intelligent pattern selection based on query analysis
    - Multiple execution strategies (sequential, parallel, conditional, layered)
    - Result aggregation and conflict resolution
    - Error handling and fallback mechanisms
    - Performance tracking and optimization

    Usage:
        orchestrator = PatternOrchestrator()

        # Analyze query and select patterns
        result = await orchestrator.orchestrate(
            query="How do I implement binary search?",
            pattern_services={
                "code_rag": code_rag_service,
                "corrective_rag": corrective_rag_service,
            },
            strategy=ExecutionStrategy.SEQUENTIAL,
        )
    """

    def __init__(
        self,
        registry: PatternRegistry | None = None,
        analyzer: QueryAnalyzer | None = None,
        budget_manager: Any | None = None,
        trace_collector: Any | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            registry: Pattern registry (uses global if not provided)
            analyzer: Query analyzer (creates new if not provided)
            budget_manager: Latency budget manager (optional)
            trace_collector: TraceCollector for observability (optional)
        """
        self.registry = registry or get_registry()
        self.analyzer = analyzer or QueryAnalyzer()
        self.budget_manager = budget_manager
        self.trace_collector = trace_collector

    async def orchestrate(
        self,
        query: str,
        pattern_services: dict[str, Any],
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
        patterns: list[str] | None = None,
        context: dict | None = None,
        **kwargs,
    ) -> OrchestrationResult:
        """
        Orchestrate pattern execution.

        Args:
            query: User query
            pattern_services: Dictionary of pattern name -> service instance
            strategy: Execution strategy
            patterns: Specific patterns to use (auto-select if None)
            context: Optional context (conversation history, etc.)
            **kwargs: Additional arguments for pattern execution

        Returns:
            OrchestrationResult: Orchestration result
        """
        start_time = time.time()

        try:
            # Analyze query if patterns not specified
            if patterns is None:
                characteristics = self.analyzer.analyze(query, context)
                patterns = self.analyzer.recommend_patterns(characteristics)
                logger.info(f"Auto-selected patterns: {patterns}")

            # Validate patterns
            is_valid, errors = self.registry.validate_combination(patterns)
            if not is_valid:
                logger.warning(f"Invalid pattern combination: {errors}")
                # Use fallback pattern
                patterns = ["adaptive_rag"]

            # Filter to available patterns
            available_patterns = [
                p for p in patterns
                if p in pattern_services
            ]

            if not available_patterns:
                raise ValueError("No available patterns to execute")

            logger.info(
                f"Orchestrating {len(available_patterns)} patterns "
                f"with {strategy.value} strategy"
            )

            # Execute based on strategy
            if strategy == ExecutionStrategy.SEQUENTIAL:
                executions = await self._execute_sequential(
                    query, available_patterns, pattern_services, context, **kwargs
                )
            elif strategy == ExecutionStrategy.PARALLEL:
                executions = await self._execute_parallel(
                    query, available_patterns, pattern_services, context, **kwargs
                )
            elif strategy == ExecutionStrategy.CONDITIONAL:
                executions = await self._execute_conditional(
                    query, available_patterns, pattern_services, context, **kwargs
                )
            elif strategy == ExecutionStrategy.LAYERED:
                executions = await self._execute_layered(
                    query, available_patterns, pattern_services, context, **kwargs
                )
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            # Aggregate results
            final_result = self._aggregate_results(executions, strategy)

            # Calculate total latency
            total_latency = (time.time() - start_time) * 1000

            # Check if any execution succeeded
            success = any(e.success for e in executions)

            return OrchestrationResult(
                query=query,
                strategy=strategy,
                patterns_executed=available_patterns,
                executions=executions,
                final_result=final_result,
                total_latency_ms=total_latency,
                success=success,
                metadata={
                    "num_patterns": len(available_patterns),
                    "num_successful": sum(1 for e in executions if e.success),
                    "num_failed": sum(1 for e in executions if not e.success),
                },
            )

        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            total_latency = (time.time() - start_time) * 1000

            return OrchestrationResult(
                query=query,
                strategy=strategy,
                patterns_executed=[],
                executions=[],
                final_result=None,
                total_latency_ms=total_latency,
                success=False,
                metadata={"error": str(e)},
            )

    async def _execute_sequential(
        self,
        query: str,
        patterns: list[str],
        pattern_services: dict[str, Any],
        context: dict | None,
        **kwargs,
    ) -> list[PatternExecution]:
        """Execute patterns sequentially. Each pattern receives the output of the previous."""
        executions = []
        current_input = query

        for pattern_name in patterns:
            execution = await self._execute_pattern(
                pattern_name,
                current_input,
                pattern_services[pattern_name],
                context,
                **kwargs,
            )
            executions.append(execution)

            # Use output as input for next pattern
            if execution.success and execution.result:
                current_input = execution.result

        return executions

    async def _execute_parallel(
        self,
        query: str,
        patterns: list[str],
        pattern_services: dict[str, Any],
        context: dict | None,
        **kwargs,
    ) -> list[PatternExecution]:
        """Execute patterns in parallel. All patterns receive the same input."""
        tasks = [
            self._execute_pattern(
                pattern_name,
                query,
                pattern_services[pattern_name],
                context,
                **kwargs,
            )
            for pattern_name in patterns
        ]

        executions = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        result_executions = []
        for i, execution in enumerate(executions):
            if isinstance(execution, Exception):
                result_executions.append(
                    PatternExecution(
                        pattern_name=patterns[i],
                        success=False,
                        error=str(execution),
                    )
                )
            else:
                result_executions.append(execution)

        return result_executions

    async def _execute_conditional(
        self,
        query: str,
        patterns: list[str],
        pattern_services: dict[str, Any],
        context: dict | None,
        **kwargs,
    ) -> list[PatternExecution]:
        """Execute patterns conditionally based on previous results."""
        executions = []

        for pattern_name in patterns:
            # Check if we should execute this pattern
            should_execute = self._should_execute_pattern(
                pattern_name, executions, context
            )

            if not should_execute:
                logger.info(f"Skipping pattern {pattern_name} (condition not met)")
                continue

            execution = await self._execute_pattern(
                pattern_name,
                query,
                pattern_services[pattern_name],
                context,
                **kwargs,
            )
            executions.append(execution)

            # Stop if pattern failed critically
            if not execution.success and self._is_critical_failure(execution):
                logger.warning(f"Critical failure in {pattern_name}, stopping")
                break

        return executions

    async def _execute_layered(
        self,
        query: str,
        patterns: list[str],
        pattern_services: dict[str, Any],
        context: dict | None,
        **kwargs,
    ) -> list[PatternExecution]:
        """Execute patterns in layers (pipeline)."""
        # For now, treat as sequential
        return await self._execute_sequential(
            query, patterns, pattern_services, context, **kwargs
        )

    async def _execute_pattern(
        self,
        pattern_name: str,
        query: str,
        pattern_service: Any,
        context: dict | None,
        **kwargs,
    ) -> PatternExecution:
        """Execute a single pattern."""
        start_time = time.time()

        try:
            logger.debug(f"Executing pattern: {pattern_name}")

            # Call pattern service - try all known method names
            result = None
            
            # Inject context into kwargs if provided
            # This ensures patterns receiving **kwargs get the context (memory, history, etc.)
            if context is not None:
                kwargs["context"] = context
                # Also inject individual context keys if needed by specific patterns
                # but standardizing on kwargs['context'] is cleaner for the wrapper.

            if hasattr(pattern_service, "aquery"):
                result = await pattern_service.aquery(query, **kwargs)
            elif hasattr(pattern_service, "query"):
                result = await pattern_service.query(query, **kwargs)
            elif hasattr(pattern_service, "process_query"):
                result = await pattern_service.process_query(query, **kwargs)
            elif hasattr(pattern_service, "retrieve_and_correct"):
                result = await pattern_service.retrieve_and_correct(query, **kwargs)
            elif hasattr(pattern_service, "generate_with_refinement"):
                result = await pattern_service.generate_with_refinement(query, **kwargs)
            elif hasattr(pattern_service, "select_optimal_chunks"):
                result = await pattern_service.select_optimal_chunks(query, **kwargs)
            elif hasattr(pattern_service, "generate_with_drafts"):
                result = await pattern_service.generate_with_drafts(query, **kwargs)
            elif hasattr(pattern_service, "process_turn"):
                # process_turn explicitly takes context, so we pass it (it might duplicate in kwargs but that's safe)
                result = await pattern_service.process_turn(query, context, **kwargs)
            elif hasattr(pattern_service, "process_multimodal_query"):
                result = await pattern_service.process_multimodal_query(query, **kwargs)
            elif hasattr(pattern_service, "process"):
                result = await pattern_service.process(query, **kwargs)
            elif hasattr(pattern_service, "execute"):
                result = await pattern_service.execute(query, **kwargs)
            else:
                raise AttributeError(
                    f"Pattern service {pattern_name} has no recognized query method."
                )

            latency = (time.time() - start_time) * 1000

            return PatternExecution(
                pattern_name=pattern_name,
                success=True,
                result=result,
                latency_ms=latency,
                metadata={"query": query},
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Pattern {pattern_name} failed: {e}")

            return PatternExecution(
                pattern_name=pattern_name,
                success=False,
                error=str(e),
                latency_ms=latency,
                metadata={"query": query},
            )

    def _should_execute_pattern(
        self,
        pattern_name: str,
        previous_executions: list[PatternExecution],
        context: dict | None,
    ) -> bool:
        """Determine if a pattern should be executed based on conditions."""
        # Always execute first pattern
        if not previous_executions:
            return True

        # Check if previous pattern succeeded
        last_execution = previous_executions[-1]
        if not last_execution.success:
            # Execute corrective patterns after failures
            if pattern_name in ["corrective_rag", "self_rag"]:
                return True
            return False

        return True

    def _is_critical_failure(self, execution: PatternExecution) -> bool:
        """Determine if an execution failure is critical."""
        return False

    def _aggregate_results(
        self,
        executions: list[PatternExecution],
        strategy: ExecutionStrategy,
    ) -> Any:
        """Aggregate results from multiple pattern executions."""
        if not executions:
            return None

        # Get successful executions
        successful = [e for e in executions if e.success and e.result]

        if not successful:
            return None

        if strategy == ExecutionStrategy.SEQUENTIAL:
            return successful[-1].result
        elif strategy == ExecutionStrategy.PARALLEL:
            return self._select_best_result(successful)
        elif strategy == ExecutionStrategy.CONDITIONAL:
            return successful[-1].result
        elif strategy == ExecutionStrategy.LAYERED:
            return successful[-1].result
        else:
            return successful[0].result

    def _select_best_result(
        self,
        executions: list[PatternExecution],
    ) -> Any:
        """Select best result from multiple executions."""
        if not executions:
            return None

        # Return result with lowest latency
        best = min(executions, key=lambda e: e.latency_ms)
        return best.result

    def select_optimal_strategy(
        self,
        characteristics: QueryCharacteristics,
        patterns: list[str],
    ) -> ExecutionStrategy:
        """Select optimal execution strategy based on query characteristics."""
        if characteristics.requires_speed:
            return ExecutionStrategy.PARALLEL
        if characteristics.requires_accuracy:
            return ExecutionStrategy.SEQUENTIAL
        if len(patterns) > 2:
            return ExecutionStrategy.CONDITIONAL
        return ExecutionStrategy.SEQUENTIAL

    # ========== DAG-Based Workflow Execution ==========

    async def execute_workflow(
        self,
        plan: "WorkflowPlan",
        query: str,
        pattern_services: dict[str, Any],
        context: dict | None = None,
        budget_manager: Any | None = None,
        **kwargs,
    ) -> OrchestrationResult:
        """
        Execute a workflow plan (DAG).

        Args:
            plan: WorkflowPlan with DAG structure
            query: Original user query
            pattern_services: Dictionary of pattern name -> service instance
            context: Optional context
            budget_manager: Optional LatencyBudgetManager for timeout tracking
            **kwargs: Additional arguments for pattern execution

        Returns:
            OrchestrationResult: Orchestration result with DAG execution details
        """
        start_time = time.time()

        try:
            logger.info(
                f"Executing workflow plan {plan.plan_id} with "
                f"{len(plan.nodes)} nodes, strategy={plan.execution_strategy.value}"
            )

            budget_allocation = None

            # Execute DAG
            executions = await self._execute_dag(
                plan=plan,
                query=query,
                pattern_services=pattern_services,
                context=context,
                budget_allocation=budget_allocation,
                budget_manager=budget_manager,
                **kwargs,
            )

            # Aggregate results
            final_result = self._aggregate_dag_results(executions, plan)

            # Calculate total latency
            total_latency = (time.time() - start_time) * 1000
            success = any(e.success for e in executions)

            return OrchestrationResult(
                query=query,
                strategy=plan.execution_strategy,
                patterns_executed=[node.pattern_name for node in plan.nodes],
                executions=executions,
                final_result=final_result,
                total_latency_ms=total_latency,
                success=success,
                metadata={
                    "plan_id": plan.plan_id,
                    "num_nodes": len(plan.nodes),
                    "num_successful": sum(1 for e in executions if e.success),
                    "num_failed": sum(1 for e in executions if not e.success),
                    "budget_ms": plan.total_budget_ms,
                    "dag_structure": plan.dag,
                },
            )

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            total_latency = (time.time() - start_time) * 1000

            return OrchestrationResult(
                query=query,
                strategy=plan.execution_strategy,
                patterns_executed=[],
                executions=[],
                final_result=None,
                total_latency_ms=total_latency,
                success=False,
                metadata={"error": str(e), "plan_id": plan.plan_id},
            )

    async def _execute_dag(
        self,
        plan: "WorkflowPlan",
        query: str,
        pattern_services: dict[str, Any],
        context: dict | None,
        budget_allocation: Any | None,
        budget_manager: Any | None,
        **kwargs,
    ) -> list[PatternExecution]:
        """Execute DAG nodes respecting dependencies."""
        completed: dict[str, PatternExecution] = {}
        node_results: dict[str, Any] = {}

        # Build reverse dependency map
        dependents: dict[str, list[str]] = {node.node_id: [] for node in plan.nodes}
        for node in plan.nodes:
            for dep in node.dependencies:
                if dep in dependents:
                    dependents[dep].append(node.node_id)

        # Find entry nodes (no dependencies)
        ready_nodes = [node for node in plan.nodes if not node.dependencies]

        # Execute nodes in waves
        while ready_nodes:
            tasks = [
                self._execute_dag_node(
                    node=node,
                    inputs=node_results,
                    query=query,
                    pattern_services=pattern_services,
                    context=context,
                    budget_allocation=budget_allocation,
                    budget_manager=budget_manager,
                    **kwargs,
                )
                for node in ready_nodes
            ]

            wave_executions = await asyncio.gather(*tasks, return_exceptions=True)

            next_ready = []
            for i, execution in enumerate(wave_executions):
                node = ready_nodes[i]

                if isinstance(execution, Exception):
                    execution = PatternExecution(
                        pattern_name=node.pattern_name,
                        success=False,
                        error=str(execution),
                        metadata={"node_id": node.node_id},
                    )

                completed[node.node_id] = execution

                if execution.success and execution.result:
                    node_results[node.node_id] = execution.result

                # Handle fallback if node failed
                if not execution.success and node.fallback_node_id:
                    fallback_node = next(
                        (n for n in plan.nodes if n.node_id == node.fallback_node_id),
                        None,
                    )
                    if fallback_node and fallback_node.node_id not in completed:
                        logger.info(
                            f"Node {node.node_id} failed, executing fallback "
                            f"{fallback_node.node_id}"
                        )
                        next_ready.append(fallback_node)

                # Check if dependents are ready
                for dependent_id in dependents[node.node_id]:
                    dependent_node = next(
                        n for n in plan.nodes if n.node_id == dependent_id
                    )

                    if all(dep in completed for dep in dependent_node.dependencies):
                        if dependent_node not in next_ready:
                            next_ready.append(dependent_node)

            ready_nodes = next_ready

        return [
            completed.get(
                node.node_id,
                PatternExecution(
                    pattern_name=node.pattern_name,
                    success=False,
                    error="Node not executed",
                    metadata={"node_id": node.node_id},
                ),
            )
            for node in plan.nodes
        ]

    async def _execute_dag_node(
        self,
        node: "WorkflowNode",
        inputs: dict[str, Any],
        query: str,
        pattern_services: dict[str, Any],
        context: dict | None,
        budget_allocation: Any | None,
        budget_manager: Any | None,
        **kwargs,
    ) -> PatternExecution:
        """Execute a single DAG node with timeout."""
        start_time = time.time()

        try:
            logger.debug(f"Executing DAG node: {node.node_id} ({node.pattern_name})")

            if node.pattern_name not in pattern_services:
                raise ValueError(f"Pattern service not found: {node.pattern_name}")

            pattern_service = pattern_services[node.pattern_name]

            # Prepare input
            if node.dependencies and inputs:
                last_dep = node.dependencies[-1]
                node_input = inputs.get(last_dep, query)
            else:
                node_input = query

            # Execute with timeout
            try:
                execution = await asyncio.wait_for(
                    self._execute_pattern(
                        pattern_name=node.pattern_name,
                        query=node_input,
                        pattern_service=pattern_service,
                        context=context,
                        **kwargs,
                    ),
                    timeout=node.timeout_ms / 1000.0,
                )
            except asyncio.TimeoutError:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Node {node.node_id} timed out after {elapsed_ms:.0f}ms "
                    f"(limit: {node.timeout_ms}ms)"
                )

                return PatternExecution(
                    pattern_name=node.pattern_name,
                    success=False,
                    error=f"Timeout after {node.timeout_ms}ms",
                    latency_ms=elapsed_ms,
                    metadata={"node_id": node.node_id, "timeout": True},
                )

            execution.metadata["node_id"] = node.node_id
            execution.metadata["dependencies"] = node.dependencies

            return execution

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"DAG node {node.node_id} failed: {e}")

            return PatternExecution(
                pattern_name=node.pattern_name,
                success=False,
                error=str(e),
                latency_ms=elapsed_ms,
                metadata={"node_id": node.node_id},
            )

    def _aggregate_dag_results(
        self,
        executions: list[PatternExecution],
        plan: "WorkflowPlan",
    ) -> Any:
        """Aggregate results from DAG execution."""
        if not executions:
            return None

        exit_node_ids = set(plan.exit_nodes)
        exit_executions = [
            e
            for e in executions
            if e.success
            and e.result
            and e.metadata.get("node_id") in exit_node_ids
        ]

        if not exit_executions:
            successful = [e for e in executions if e.success and e.result]
            if successful:
                return successful[-1].result
            return None

        if len(exit_executions) > 1:
            return self._select_best_result(exit_executions)

        return exit_executions[0].result

    def get_trace_collector(self):
        """Get the trace collector instance."""
        return self.trace_collector

    def set_trace_collector(self, trace_collector: Any):
        """Set the trace collector instance."""
        self.trace_collector = trace_collector


__all__ = [
    "ExecutionStrategy",
    "PatternExecution",
    "OrchestrationResult",
    "PatternOrchestrator",
]

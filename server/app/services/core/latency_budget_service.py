"""
Latency Budget Manager - Enforces SLA-based timing constraints.

Module này cung cấp:
1. Budget allocation based on query complexity
2. User tier adjustments (free, premium, enterprise)
3. Budget checking và timeout detection
4. Node-level budget distribution

Latency Budget Manager đảm bảo queries được xử lý trong SLA-defined time budgets.

"""
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """Query complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class UserTier(str, Enum):
    """User tier levels."""

    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class BudgetAllocation:
    """
    Budget allocation for a workflow.

    Attributes:
        total_budget_ms: Total SLA budget in milliseconds
        node_budgets: Budget per node (node_id -> budget_ms)
        buffer_ms: Reserved buffer for overhead
        user_tier: User tier used for allocation
        complexity: Query complexity level
    """

    total_budget_ms: int
    node_budgets: dict[str, int] = field(default_factory=dict)
    buffer_ms: int = 0
    user_tier: str = "free"
    complexity: str = "simple"


@dataclass
class BudgetConfig:
    """
    Configuration for Latency Budget Manager.

    Attributes:
        sla_budgets: SLA budgets per complexity level (ms)
        user_tier_multipliers: Budget multipliers per user tier
        buffer_percentage: Percentage of budget reserved as buffer
        min_node_budget_ms: Minimum budget per node
    """

    sla_budgets: dict[str, int] = field(
        default_factory=lambda: {
            QueryComplexity.SIMPLE.value: 2000,
            QueryComplexity.MODERATE.value: 5000,
            QueryComplexity.COMPLEX.value: 30000,
            QueryComplexity.VERY_COMPLEX.value: 60000,
        }
    )
    user_tier_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            UserTier.FREE.value: 1.0,
            UserTier.PREMIUM.value: 1.5,
            UserTier.ENTERPRISE.value: 2.0,
        }
    )
    buffer_percentage: float = 0.1  # 10% buffer
    min_node_budget_ms: int = 500  # Minimum 500ms per node


class LatencyBudgetManager:
    """
    Latency Budget Manager enforces SLA-based timing constraints.

    Features:
    - Allocate total budget based on query complexity
    - Adjust budget based on user tier
    - Distribute budget across workflow n
        )
    """

    def __init__(self, config: BudgetConfig | None = None):
        """
        Initialize Latency Budget Manager.

        Args:
            config: Budget configuration (uses defaults if not provided)
        """
        self.config = config or BudgetConfig()
        logger.info("Latency Budget Manager initialized")

    def allocate_budget(
        self,
        complexity: QueryComplexity | str,
        num_nodes: int,
        user_tier: str = "free",
        node_weights: dict[str, float] | None = None,
    ) -> BudgetAllocation:
        """
        Allocate budget for a workflow.

        Budget allocation strategy:
        1. Get base budget from SLA budgets
        2. Adjust for user tier
        3. Reserve buffer (10% default)
        4. Distribute remaining budget across nodes

        Args:
            complexity: Query complexity level
            num_nodes: Number of nodes in workflow
            user_tier: User tier (free, premium, enterprise)
            node_weights: Optional weights for budget distribution

        Returns:
            BudgetAllocation: Allocated budget with node-level budgets
        """
        # Convert enum to string if needed
        if isinstance(complexity, QueryComplexity):
            complexity = complexity.value

        # Step 1: Get base budget
        base_budget_ms = self.config.sla_budgets.get(complexity, 2000)

        # Step 2: Adjust for user tier
        total_budget_ms = self.adjust_for_user_tier(base_budget_ms, user_tier)

        # Step 3: Reserve buffer
        buffer_ms = int(total_budget_ms * self.config.buffer_percentage)
        available_budget = total_budget_ms - buffer_ms

        # Step 4: Distribute budget across nodes
        node_budgets = self._distribute_budget(
            available_budget=available_budget,
            num_nodes=num_nodes,
            node_weights=node_weights,
        )

        logger.info(
            f"Allocated budget: total={total_budget_ms}ms, "
            f"available={available_budget}ms, buffer={buffer_ms}ms, "
            f"nodes={num_nodes}, tier={user_tier}"
        )

        return BudgetAllocation(
            total_budget_ms=total_budget_ms,
            node_budgets=node_budgets,
            buffer_ms=buffer_ms,
            user_tier=user_tier,
            complexity=complexity,
        )

    def adjust_for_user_tier(
        self,
        base_budget_ms: int,
        user_tier: str,
    ) -> int:
        """
        Adjust budget based on user tier.

        Premium and enterprise users get higher budgets.

        Args:
            base_budget_ms: Base budget in milliseconds
            user_tier: User tier (free, premium, enterprise)

        Returns:
            int: Adjusted budget in milliseconds
        """
        multiplier = self.config.user_tier_multipliers.get(user_tier, 1.0)
        adjusted_budget = int(base_budget_ms * multiplier)

        logger.debug(
            f"Adjusted budget for tier {user_tier}: "
            f"{base_budget_ms}ms -> {adjusted_budget}ms (x{multiplier})"
        )

        return adjusted_budget

    def check_budget(
        self,
        allocation: BudgetAllocation,
        node_id: str,
        elapsed_ms: float,
    ) -> bool:
        """
        Check if node execution is within budget.

        Args:
            allocation: Budget allocation
            node_id: Node identifier
            elapsed_ms: Elapsed time in milliseconds

        Returns:
            bool: True if within budget, False if exceeded
        """
        node_budget = allocation.node_budgets.get(node_id, 0)

        if node_budget == 0:
            logger.warning(f"No budget allocated for node {node_id}")
            return True  # Allow execution if no budget set

        is_within = elapsed_ms <= node_budget

        if not is_within:
            logger.warning(
                f"Node {node_id} exceeded budget: "
                f"{elapsed_ms:.0f}ms > {node_budget}ms"
            )
        else:
            logger.debug(
                f"Node {node_id} within budget: "
                f"{elapsed_ms:.0f}ms / {node_budget}ms"
            )

        return is_within

    def get_remaining_budget(
        self,
        allocation: BudgetAllocation,
        node_id: str,
        elapsed_ms: float,
    ) -> int:
        """
        Get remaining budget for a node.

        Args:
            allocation: Budget allocation
            node_id: Node identifier
            elapsed_ms: Elapsed time in milliseconds

        Returns:
            int: Remaining budget in milliseconds (0 if exceeded)
        """
        node_budget = allocation.node_budgets.get(node_id, 0)
        remaining = max(0, node_budget - int(elapsed_ms))

        return remaining

    def _distribute_budget(
        self,
        available_budget: int,
        num_nodes: int,
        node_weights: dict[str, float] | None = None,
    ) -> dict[str, int]:
        """
        Distribute budget across nodes.

        If node_weights provided, distribute proportionally.
        Otherwise, distribute evenly.

        Args:
            available_budget: Available budget after buffer
            num_nodes: Number of nodes
            node_weights: Optional weights for distribution

        Returns:
            dict[str, int]: Budget per node (node_id -> budget_ms)
        """
        if num_nodes == 0:
            return {}

        node_budgets = {}

        if node_weights:
            # Weighted distribution
            total_weight = sum(node_weights.values())

            for node_id, weight in node_weights.items():
                if total_weight > 0:
                    budget = int((weight / total_weight) * available_budget)
                else:
                    budget = available_budget // num_nodes

                # Enforce minimum budget
                budget = max(budget, self.config.min_node_budget_ms)
                node_budgets[node_id] = budget

        else:
            # Even distribution
            per_node_budget = available_budget // num_nodes

            # Enforce minimum budget
            per_node_budget = max(per_node_budget, self.config.min_node_budget_ms)

            # Create generic node IDs
            for i in range(num_nodes):
                node_budgets[f"node_{i}"] = per_node_budget

        return node_budgets

    def update_node_budget(
        self,
        allocation: BudgetAllocation,
        node_id: str,
        new_budget_ms: int,
    ) -> None:
        """
        Update budget for a specific node.

        Useful for dynamic budget adjustments during execution.

        Args:
            allocation: Budget allocation to update
            node_id: Node identifier
            new_budget_ms: New budget in milliseconds
        """
        old_budget = allocation.node_budgets.get(node_id, 0)
        allocation.node_budgets[node_id] = new_budget_ms

        logger.debug(
            f"Updated budget for node {node_id}: "
            f"{old_budget}ms -> {new_budget_ms}ms"
        )

    def get_budget_summary(self, allocation: BudgetAllocation) -> dict:
        """
        Get summary of budget allocation.

        Args:
            allocation: Budget allocation

        Returns:
            dict: Budget summary with statistics
        """
        node_budgets_list = list(allocation.node_budgets.values())

        summary = {
            "total_budget_ms": allocation.total_budget_ms,
            "buffer_ms": allocation.buffer_ms,
            "available_budget_ms": allocation.total_budget_ms - allocation.buffer_ms,
            "num_nodes": len(allocation.node_budgets),
            "user_tier": allocation.user_tier,
            "complexity": allocation.complexity,
            "node_budgets": allocation.node_budgets,
            "min_node_budget_ms": min(node_budgets_list) if node_budgets_list else 0,
            "max_node_budget_ms": max(node_budgets_list) if node_budgets_list else 0,
            "avg_node_budget_ms": (
                sum(node_budgets_list) // len(node_budgets_list)
                if node_budgets_list
                else 0
            ),
        }

        return summary

"""
CORAG Service - Pattern #18 (Cost-Constrained RAG)

Optimizes token usage while maintaining quality using utility-based chunk selection.
Consolidated from: base.py, optimizer.py, selector.py, mcts.py
"""
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Models (integrated from models.py)
# =============================================================================

@dataclass
class Chunk:
    """Chunk data structure."""
    chunk_id: str
    document_id: str
    content: str
    token_count: int
    relevance_score: float
    position: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationStep:
    """Single optimization step."""
    step_type: str  # "utility_computation", "greedy_selection", "mcts_optimization"
    chunks_before: int
    chunks_after: int
    tokens_before: int
    tokens_after: int
    reasoning: str
    timestamp: str


@dataclass
class OptimizationMetrics:
    """Optimization metrics."""
    cost_savings_percentage: float
    quality_impact_percentage: float
    tokens_saved: int
    chunks_removed: int
    alert_triggered: bool
    final_quality_score: float


@dataclass
class CORAGResult:
    """Result of CORAG processing."""
    selected_chunks: list[Chunk]
    total_tokens: int
    tokens_saved: int
    quality_score: float
    quality_delta: float
    optimization_log: list[OptimizationStep]
    metrics: OptimizationMetrics
    alert_message: str | None


class MCTSNode:
    """MCTS Node for chunk selection."""
    def __init__(self, chunks: list[Chunk], selected_indices: list[int], budget: int):
        self.chunks = chunks
        self.selected_indices = selected_indices
        self.budget = budget
        self.visits = 0
        self.value = 0.0
        self.children = []
        self.parent = None

    def is_terminal(self) -> bool:
        total_tokens = sum(self.chunks[i].token_count for i in self.selected_indices)
        return total_tokens >= self.budget or len(self.selected_indices) == len(self.chunks)

    def get_total_tokens(self) -> int:
        return sum(self.chunks[i].token_count for i in self.selected_indices)

    def ucb1(self, exploration_weight: float = 1.414) -> float:
        if self.visits == 0:
            return float('inf')
        if self.parent is None or self.parent.visits == 0:
            return self.value / self.visits
        return (self.value / self.visits) + exploration_weight * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_token_count(token_count: int, max_tokens: int) -> float:
    """Normalize token count to 0-1 range."""
    return min(token_count / max_tokens, 1.0) if max_tokens > 0 else 0.0


# =============================================================================
# Helper Components
# =============================================================================

class UtilityOptimizer:
    """Computes utility scores balancing relevance and cost."""
    
    def __init__(self, cost_weight: float = 0.3):
        self.cost_weight = cost_weight

    def compute_utility(self, chunk: Chunk, relevance_score: float, max_tokens: int) -> float:
        """Compute utility: (relevance * (1 - cost_weight)) - (tokens / max_tokens * cost_weight)"""
        token_ratio = normalize_token_count(chunk.token_count, max_tokens)
        return (relevance_score * (1 - self.cost_weight)) - (token_ratio * self.cost_weight)

    def compute_utilities(self, chunks: list[Chunk], max_tokens: int) -> list[tuple]:
        """Compute utility scores for all chunks."""
        return [(chunk, self.compute_utility(chunk, chunk.relevance_score, max_tokens)) for chunk in chunks]


class ChunkSelector:
    """Selects chunks using greedy and preference-based strategies."""
    
    def __init__(self, relevance_similarity_threshold: float = 0.1):
        self.relevance_similarity_threshold = relevance_similarity_threshold

    def greedy_selection(self, sorted_chunks: list[tuple], budget: int) -> tuple:
        """Greedy selection within budget, preferring shorter chunks when relevance is similar."""
        selected, total_tokens = [], 0

        for chunk, utility in sorted_chunks:
            should_add = True
            for selected_chunk, _ in selected:
                relevance_diff = abs(chunk.relevance_score - selected_chunk.relevance_score)
                if relevance_diff < self.relevance_similarity_threshold and chunk.token_count >= selected_chunk.token_count:
                    should_add = False
                    break

            if should_add and total_tokens + chunk.token_count <= budget:
                selected.append((chunk, utility))
                total_tokens += chunk.token_count

        return selected, total_tokens


class MCTSSearch:
    """Monte Carlo Tree Search for optimal chunk combinations."""
    
    def __init__(self, exploration_weight: float = 1.414):
        self.exploration_weight = exploration_weight

    async def mcts_search(self, chunks: list[Chunk], budget: int, iterations: int = 100) -> list[Chunk]:
        """Use MCTS to find optimal chunk combination."""
        sorted_chunks = sorted(chunks, key=lambda x: x.relevance_score, reverse=True)
        root = MCTSNode(sorted_chunks, [], budget)

        for _ in range(iterations):
            node = self._select(root)
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)
            value = self._simulate(node)
            self._backpropagate(node, value)

        if not root.children:
            return []

        best_node = max(root.children, key=lambda n: n.value / n.visits if n.visits > 0 else 0)
        return [best_node.chunks[i] for i in best_node.selected_indices]

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.children and not node.is_terminal():
            node = max(node.children, key=lambda n: n.ucb1(self.exploration_weight))
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        available = [i for i in range(len(node.chunks)) if i not in node.selected_indices]
        for idx in available:
            new_selected = node.selected_indices + [idx]
            if sum(node.chunks[i].token_count for i in new_selected) <= node.budget:
                child = MCTSNode(node.chunks, new_selected, node.budget)
                child.parent = node
                node.children.append(child)
        return random.choice(node.children) if node.children else node

    def _simulate(self, node: MCTSNode) -> float:
        current_selected = node.selected_indices.copy()
        current_tokens = node.get_total_tokens()
        available = [i for i in range(len(node.chunks)) if i not in current_selected]
        random.shuffle(available)

        for idx in available:
            if current_tokens + node.chunks[idx].token_count <= node.budget:
                current_selected.append(idx)
                current_tokens += node.chunks[idx].token_count

        if current_selected:
            avg_relevance = sum(node.chunks[i].relevance_score for i in current_selected) / len(current_selected)
            budget_usage = current_tokens / node.budget if node.budget > 0 else 0
            return avg_relevance * (0.7 + 0.3 * budget_usage)
        return 0.0

    def _backpropagate(self, node: MCTSNode, value: float):
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent


# =============================================================================
# Main Service
# =============================================================================

class CORAGService:
    """
    CORAG Service implementing Pattern #18 (Cost-Constrained RAG).
    
    Optimizes chunk selection to balance relevance and cost:
    - Uses utility function for chunk scoring
    - Prefers shorter chunks when relevance is similar
    - Applies MCTS for intelligent truncation
    - Tracks cost savings and quality impact
    """

    def __init__(
        self,
        cost_weight: float = 0.3,
        relevance_similarity_threshold: float = 0.1,
        quality_alert_threshold: float = 0.7,
        mcts_iterations: int = 100
    ):
        self.cost_weight = cost_weight
        self.relevance_similarity_threshold = relevance_similarity_threshold
        self.quality_alert_threshold = quality_alert_threshold
        self.mcts_iterations = mcts_iterations

        self.optimizer = UtilityOptimizer(cost_weight=cost_weight)
        self.selector = ChunkSelector(relevance_similarity_threshold=relevance_similarity_threshold)
        self.mcts = MCTSSearch()

        logger.info(f"CORAGService: cost_weight={cost_weight}, quality_threshold={quality_alert_threshold}")

    async def select_optimal_chunks(
        self,
        query: str,
        candidate_chunks: list[Chunk],
        token_budget: int,
        use_mcts: bool = True
    ) -> CORAGResult:
        """Select optimal chunks within budget."""
        optimization_log = []

        try:
            # Step 1: Compute utility scores
            chunks_with_utility = self.optimizer.compute_utilities(candidate_chunks, token_budget)
            optimization_log.append(OptimizationStep(
                step_type="utility_computation",
                chunks_before=len(candidate_chunks),
                chunks_after=len(chunks_with_utility),
                tokens_before=sum(c.token_count for c in candidate_chunks),
                tokens_after=sum(c[0].token_count for c in chunks_with_utility),
                reasoning="Computed utility scores",
                timestamp=datetime.now().isoformat()
            ))

            # Step 2: Sort by utility
            sorted_chunks = sorted(chunks_with_utility, key=lambda x: x[1], reverse=True)

            # Step 3: Greedy selection
            selected_chunks, greedy_tokens = self.selector.greedy_selection(sorted_chunks, token_budget)
            optimization_log.append(OptimizationStep(
                step_type="greedy_selection",
                chunks_before=len(sorted_chunks),
                chunks_after=len(selected_chunks),
                tokens_before=sum(c[0].token_count for c in sorted_chunks),
                tokens_after=greedy_tokens,
                reasoning="Greedy selection by utility",
                timestamp=datetime.now().isoformat()
            ))

            # Step 4: MCTS optimization if over budget
            if use_mcts and greedy_tokens > token_budget:
                selected_chunks = await self.mcts.mcts_search(
                    [c[0] for c in sorted_chunks], token_budget, self.mcts_iterations
                )
                optimization_log.append(OptimizationStep(
                    step_type="mcts_optimization",
                    chunks_before=len(sorted_chunks),
                    chunks_after=len(selected_chunks),
                    tokens_before=greedy_tokens,
                    tokens_after=sum(c.token_count for c in selected_chunks),
                    reasoning="MCTS optimization to fit budget",
                    timestamp=datetime.now().isoformat()
                ))
            else:
                selected_chunks = [c[0] for c in selected_chunks]

            # Step 5: Calculate metrics
            metrics = self._track_optimization(candidate_chunks, selected_chunks, token_budget)

            alert_message = None
            if metrics.alert_triggered:
                alert_message = f"Quality dropped to {metrics.final_quality_score:.2f} (below {self.quality_alert_threshold})"
                logger.warning(alert_message)

            total_tokens = sum(c.token_count for c in selected_chunks)
            original_tokens = sum(c.token_count for c in candidate_chunks)

            logger.info(f"CORAG: {len(selected_chunks)}/{len(candidate_chunks)} chunks, {total_tokens}/{original_tokens} tokens")

            return CORAGResult(
                selected_chunks=selected_chunks,
                total_tokens=total_tokens,
                tokens_saved=original_tokens - total_tokens,
                quality_score=metrics.final_quality_score,
                quality_delta=metrics.quality_impact_percentage,
                optimization_log=optimization_log,
                metrics=metrics,
                alert_message=alert_message
            )

        except Exception as e:
            logger.error(f"CORAG error: {e}", exc_info=True)
            # Fallback: top chunks by relevance
            sorted_by_relevance = sorted(candidate_chunks, key=lambda x: x.relevance_score, reverse=True)
            selected, total = [], 0
            for chunk in sorted_by_relevance:
                if total + chunk.token_count <= token_budget:
                    selected.append(chunk)
                    total += chunk.token_count

            return CORAGResult(
                selected_chunks=selected,
                total_tokens=total,
                tokens_saved=0,
                quality_score=0.0,
                quality_delta=0.0,
                optimization_log=[],
                metrics=OptimizationMetrics(0, 0, 0, 0, False, 0.0),
                alert_message=f"Error: {e}, using fallback"
            )

    def _track_optimization(
        self, original_chunks: list[Chunk], selected_chunks: list[Chunk], budget: int
    ) -> OptimizationMetrics:
        """Track cost savings and quality impact."""
        original_tokens = sum(c.token_count for c in original_chunks)
        selected_tokens = sum(c.token_count for c in selected_chunks)
        tokens_saved = original_tokens - selected_tokens

        original_quality = sum(c.relevance_score for c in original_chunks) / len(original_chunks) if original_chunks else 0.0
        selected_quality = sum(c.relevance_score for c in selected_chunks) / len(selected_chunks) if selected_chunks else 0.0

        cost_savings_pct = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0.0
        quality_impact_pct = ((selected_quality - original_quality) / original_quality * 100) if original_quality > 0 else 0.0

        return OptimizationMetrics(
            cost_savings_percentage=cost_savings_pct,
            quality_impact_percentage=quality_impact_pct,
            tokens_saved=tokens_saved,
            chunks_removed=len(original_chunks) - len(selected_chunks),
            alert_triggered=selected_quality < self.quality_alert_threshold,
            final_quality_score=selected_quality
        )

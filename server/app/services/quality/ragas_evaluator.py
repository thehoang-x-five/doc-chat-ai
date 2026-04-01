"""
Ragas Evaluator - Integration with Ragas evaluation framework.

This module provides:
1. Ragas metric evaluation (faithfulness, relevancy, precision, recall)
2. Batch evaluation for datasets
3. Result aggregation and reporting

Requires: pip install ragas

"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class RagasMetric(str, Enum):
    """Available Ragas metrics."""
    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCY = "answer_relevancy"
    CONTEXT_PRECISION = "context_precision"
    CONTEXT_RECALL = "context_recall"
    CONTEXT_RELEVANCY = "context_relevancy"
    ANSWER_SIMILARITY = "answer_similarity"
    ANSWER_CORRECTNESS = "answer_correctness"


@dataclass
class RagasSample:
    """Single sample for Ragas evaluation."""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None  # Required for some metrics


@dataclass
class RagasResult:
    """Result of Ragas evaluation."""
    scores: Dict[str, float]  # metric_name -> score
    sample_size: int
    passed: bool
    threshold: float
    details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scores": self.scores,
            "sample_size": self.sample_size,
            "passed": self.passed,
            "threshold": self.threshold,
        }


class RagasEvaluator:
    """
    Ragas integration for RAG evaluation.
    
    Evaluates RAG responses using Ragas metrics:
    - Faithfulness: How factually consistent is the answer with context
    - Answer Relevancy: How relevant is the answer to the question
    - Context Precision: Signal-to-noise ratio of retrieved contexts
    - Context Recall: Can answer be attributed to context
    
    Usage:
        evaluator = RagasEvaluator()
        
        # Single evaluation
        result = await evaluator.evaluate_single(
            question="What is RAG?",
            answer="RAG stands for...",
            contexts=["RAG is a technique..."],
        )
        
        # Batch evaluation
        results = await evaluator.evaluate_batch(samples)
    """
    
    DEFAULT_METRICS = [
        RagasMetric.FAITHFULNESS,
        RagasMetric.ANSWER_RELEVANCY,
    ]
    
    DEFAULT_THRESHOLD = 0.7
    
    def __init__(
        self,
        metrics: Optional[List[RagasMetric]] = None,
        threshold: float = DEFAULT_THRESHOLD,
        llm_model: str = "gpt-3.5-turbo",
        embedding_model: str = "text-embedding-ada-002",
    ):
        """
        Initialize Ragas Evaluator.
        
        Args:
            metrics: Metrics to evaluate
            threshold: Minimum score to pass
            llm_model: LLM model for generation-based metrics
            embedding_model: Embedding model for similarity metrics
        """
        self.metrics = metrics or self.DEFAULT_METRICS
        self.threshold = threshold
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        
        self._ragas_available = self._check_ragas_available()
        
        logger.info(f"RagasEvaluator initialized (available={self._ragas_available})")
    
    def _check_ragas_available(self) -> bool:
        """Check if Ragas is available."""
        try:
            import ragas
            return True
        except ImportError:
            logger.warning("Ragas not installed. Install with: pip install ragas")
            return False
    
    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        metrics: Optional[List[RagasMetric]] = None,
    ) -> RagasResult:
        """
        Evaluate a single RAG response.
        
        Args:
            question: The question asked
            answer: Generated answer
            contexts: Retrieved context passages
            ground_truth: Optional reference answer
            metrics: Optional override of metrics to use
            
        Returns:
            RagasResult with scores
        """
        sample = RagasSample(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )
        
        results = await self.evaluate_batch([sample], metrics)
        results.sample_size = 1
        
        return results
    
    async def evaluate_batch(
        self,
        samples: List[RagasSample],
        metrics: Optional[List[RagasMetric]] = None,
    ) -> RagasResult:
        """
        Evaluate a batch of RAG responses.
        
        Args:
            samples: List of samples to evaluate
            metrics: Optional override of metrics to use
            
        Returns:
            RagasResult with aggregated scores
        """
        if not samples:
            return RagasResult(
                scores={},
                sample_size=0,
                passed=True,
                threshold=self.threshold,
            )
        
        use_metrics = metrics or self.metrics
        
        if not self._ragas_available:
            return self._fallback_evaluation(samples, use_metrics)
        
        try:
            return await self._ragas_evaluation(samples, use_metrics)
        except Exception as e:
            logger.error(f"Ragas evaluation failed: {e}")
            return self._fallback_evaluation(samples, use_metrics)
    
    async def _ragas_evaluation(
        self,
        samples: List[RagasSample],
        metrics: List[RagasMetric],
    ) -> RagasResult:
        """Run actual Ragas evaluation."""
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset
        
        # Map metric enums to Ragas metric objects
        metric_map = {
            RagasMetric.FAITHFULNESS: faithfulness,
            RagasMetric.ANSWER_RELEVANCY: answer_relevancy,
            RagasMetric.CONTEXT_PRECISION: context_precision,
            RagasMetric.CONTEXT_RECALL: context_recall,
        }
        
        # Get metric objects
        ragas_metrics = []
        for m in metrics:
            if m in metric_map:
                ragas_metrics.append(metric_map[m])
        
        if not ragas_metrics:
            logger.warning("No valid Ragas metrics specified")
            return RagasResult(
                scores={},
                sample_size=len(samples),
                passed=True,
                threshold=self.threshold,
            )
        
        # Prepare dataset
        data = {
            "question": [s.question for s in samples],
            "answer": [s.answer for s in samples],
            "contexts": [s.contexts for s in samples],
        }
        
        # Add ground truth if all samples have it
        if all(s.ground_truth for s in samples):
            data["ground_truth"] = [s.ground_truth for s in samples]
        
        dataset = Dataset.from_dict(data)
        
        # Run evaluation
        result = evaluate(dataset, metrics=ragas_metrics)
        
        # Extract scores
        scores = {}
        for m in metrics:
            if m.value in result:
                scores[m.value] = float(result[m.value])
        
        # Calculate overall
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        passed = avg_score >= self.threshold
        
        return RagasResult(
            scores=scores,
            sample_size=len(samples),
            passed=passed,
            threshold=self.threshold,
            details=[
                {"sample_idx": i, "question": s.question[:100]}
                for i, s in enumerate(samples)
            ],
        )
    
    def _fallback_evaluation(
        self,
        samples: List[RagasSample],
        metrics: List[RagasMetric],
    ) -> RagasResult:
        """Fallback evaluation using heuristics when Ragas unavailable."""
        scores = {}
        
        for metric in metrics:
            if metric == RagasMetric.FAITHFULNESS:
                # Simple word overlap heuristic
                total = 0.0
                for s in samples:
                    context_words = set(" ".join(s.contexts).lower().split())
                    answer_words = set(s.answer.lower().split())
                    overlap = len(answer_words & context_words) / len(answer_words) if answer_words else 1.0
                    total += overlap
                scores[metric.value] = total / len(samples)
                
            elif metric == RagasMetric.ANSWER_RELEVANCY:
                # Question-answer keyword overlap
                total = 0.0
                for s in samples:
                    q_words = set(s.question.lower().split())
                    a_words = set(s.answer.lower().split())
                    overlap = len(q_words & a_words) / len(q_words) if q_words else 0.0
                    # Penalize very short or very long answers
                    len_factor = min(1.0, len(s.answer.split()) / 10)
                    total += overlap * 0.5 + len_factor * 0.5
                scores[metric.value] = total / len(samples)
                
            elif metric == RagasMetric.CONTEXT_PRECISION:
                # Heuristic: assume good precision if contexts are not too long
                total = 0.0
                for s in samples:
                    avg_context_len = sum(len(c.split()) for c in s.contexts) / len(s.contexts) if s.contexts else 0
                    precision = min(1.0, 100 / avg_context_len) if avg_context_len > 0 else 0.5
                    total += precision
                scores[metric.value] = total / len(samples)
            
            else:
                # Default score
                scores[metric.value] = 0.5
        
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        passed = avg_score >= self.threshold
        
        return RagasResult(
            scores=scores,
            sample_size=len(samples),
            passed=passed,
            threshold=self.threshold,
            details=[{"note": "Fallback heuristic evaluation used"}],
        )
    
    def get_summary_report(self, result: RagasResult) -> str:
        """Generate a human-readable summary report."""
        lines = [
            "=" * 50,
            "Ragas Evaluation Report",
            "=" * 50,
            f"Sample Size: {result.sample_size}",
            f"Threshold: {result.threshold}",
            f"Overall: {'PASSED' if result.passed else 'FAILED'}",
            "",
            "Metric Scores:",
        ]
        
        for metric, score in result.scores.items():
            status = "✓" if score >= result.threshold else "✗"
            lines.append(f"  {status} {metric}: {score:.3f}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


# Default instance
ragas_evaluator = RagasEvaluator()

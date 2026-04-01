"""
DeepEval Tester - Integration with DeepEval evaluation framework.

This module provides:
1. DeepEval metric testing
2. Batch test execution
3. Custom test case creation

Requires: pip install deepeval

"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DeepEvalMetric(str, Enum):
    """Available DeepEval metrics."""
    ANSWER_RELEVANCY = "answer_relevancy"
    FAITHFULNESS = "faithfulness"
    CONTEXTUAL_PRECISION = "contextual_precision"
    CONTEXTUAL_RECALL = "contextual_recall"
    HALLUCINATION = "hallucination"
    TOXICITY = "toxicity"
    BIAS = "bias"


@dataclass
class DeepEvalTestCase:
    """Single test case for DeepEval."""
    input: str
    actual_output: str
    expected_output: Optional[str] = None
    context: Optional[List[str]] = None
    retrieval_context: Optional[List[str]] = None


@dataclass
class DeepEvalResult:
    """Result of DeepEval testing."""
    passed: bool
    score: float
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "total_tests": len(self.test_results),
            "failures": len(self.failures),
        }


class DeepEvalTester:
    """
    DeepEval integration for RAG testing.
    
    Provides comprehensive testing capabilities:
    - Answer Relevancy: Is the answer relevant to the question
    - Faithfulness: Is the answer grounded in context
    - Contextual Precision/Recall: Quality of retrieval
    - Hallucination: Does answer contain made-up info
    
    Usage:
        tester = DeepEvalTester()
        
        # Single test
        result = await tester.test_single(
            input="What is RAG?",
            actual_output="RAG stands for...",
            context=["RAG is a technique..."],
        )
        
        # Batch tests
        results = await tester.test_batch(test_cases)
    """
    
    DEFAULT_METRICS = [
        DeepEvalMetric.ANSWER_RELEVANCY,
        DeepEvalMetric.FAITHFULNESS,
    ]
    
    DEFAULT_THRESHOLD = 0.5
    
    def __init__(
        self,
        metrics: Optional[List[DeepEvalMetric]] = None,
        threshold: float = DEFAULT_THRESHOLD,
        model: str = "gpt-3.5-turbo",
    ):
        """
        Initialize DeepEval Tester.
        
        Args:
            metrics: Metrics to test
            threshold: Minimum score to pass
            model: LLM model for evaluation
        """
        self.metrics = metrics or self.DEFAULT_METRICS
        self.threshold = threshold
        self.model = model
        
        self._deepeval_available = self._check_deepeval_available()
        
        logger.info(f"DeepEvalTester initialized (available={self._deepeval_available})")
    
    def _check_deepeval_available(self) -> bool:
        """Check if DeepEval is available."""
        try:
            import deepeval
            return True
        except ImportError:
            logger.warning("DeepEval not installed. Install with: pip install deepeval")
            return False
    
    async def test_single(
        self,
        input: str,
        actual_output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
        metrics: Optional[List[DeepEvalMetric]] = None,
    ) -> DeepEvalResult:
        """
        Test a single RAG response.
        
        Args:
            input: The input question
            actual_output: Generated answer
            expected_output: Optional expected answer
            context: Retrieved context passages
            metrics: Optional override of metrics to use
            
        Returns:
            DeepEvalResult with test results
        """
        test_case = DeepEvalTestCase(
            input=input,
            actual_output=actual_output,
            expected_output=expected_output,
            context=context,
            retrieval_context=context,
        )
        
        return await self.test_batch([test_case], metrics)
    
    async def test_batch(
        self,
        test_cases: List[DeepEvalTestCase],
        metrics: Optional[List[DeepEvalMetric]] = None,
    ) -> DeepEvalResult:
        """
        Run batch tests.
        
        Args:
            test_cases: List of test cases
            metrics: Optional override of metrics to use
            
        Returns:
            DeepEvalResult with aggregated results
        """
        if not test_cases:
            return DeepEvalResult(
                passed=True,
                score=1.0,
            )
        
        use_metrics = metrics or self.metrics
        
        if not self._deepeval_available:
            return self._fallback_test(test_cases, use_metrics)
        
        try:
            return await self._deepeval_test(test_cases, use_metrics)
        except Exception as e:
            logger.error(f"DeepEval test failed: {e}")
            return self._fallback_test(test_cases, use_metrics)
    
    async def _deepeval_test(
        self,
        test_cases: List[DeepEvalTestCase],
        metrics: List[DeepEvalMetric],
    ) -> DeepEvalResult:
        """Run actual DeepEval tests."""
        from deepeval import evaluate
        from deepeval.test_case import LLMTestCase
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            FaithfulnessMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            HallucinationMetric,
        )
        
        # Map metric enums to DeepEval metric classes
        metric_map = {
            DeepEvalMetric.ANSWER_RELEVANCY: AnswerRelevancyMetric,
            DeepEvalMetric.FAITHFULNESS: FaithfulnessMetric,
            DeepEvalMetric.CONTEXTUAL_PRECISION: ContextualPrecisionMetric,
            DeepEvalMetric.CONTEXTUAL_RECALL: ContextualRecallMetric,
            DeepEvalMetric.HALLUCINATION: HallucinationMetric,
        }
        
        # Create metric instances
        deepeval_metrics = []
        for m in metrics:
            if m in metric_map:
                deepeval_metrics.append(metric_map[m](threshold=self.threshold))
        
        if not deepeval_metrics:
            logger.warning("No valid DeepEval metrics specified")
            return DeepEvalResult(
                passed=True,
                score=1.0,
            )
        
        # Create test cases
        llm_test_cases = []
        for tc in test_cases:
            llm_test_cases.append(LLMTestCase(
                input=tc.input,
                actual_output=tc.actual_output,
                expected_output=tc.expected_output,
                context=tc.context,
                retrieval_context=tc.retrieval_context,
            ))
        
        # Run evaluation
        results = evaluate(llm_test_cases, deepeval_metrics)
        
        # Process results
        test_results = []
        failures = []
        total_score = 0.0
        
        for i, result in enumerate(results):
            test_result = {
                "index": i,
                "passed": result.success,
                "scores": {},
            }
            
            for metric_result in result.metrics_data:
                test_result["scores"][metric_result.name] = metric_result.score
                total_score += metric_result.score or 0.0
            
            test_results.append(test_result)
            
            if not result.success:
                failures.append({
                    "index": i,
                    "reason": [m.reason for m in result.metrics_data if not m.success],
                })
        
        avg_score = total_score / (len(test_cases) * len(deepeval_metrics)) if test_cases and deepeval_metrics else 0.0
        passed = len(failures) == 0
        
        return DeepEvalResult(
            passed=passed,
            score=avg_score,
            test_results=test_results,
            failures=failures,
        )
    
    def _fallback_test(
        self,
        test_cases: List[DeepEvalTestCase],
        metrics: List[DeepEvalMetric],
    ) -> DeepEvalResult:
        """Fallback testing using heuristics when DeepEval unavailable."""
        test_results = []
        failures = []
        total_score = 0.0
        
        for i, tc in enumerate(test_cases):
            scores = {}
            passed = True
            
            for metric in metrics:
                if metric == DeepEvalMetric.ANSWER_RELEVANCY:
                    # Simple keyword overlap
                    input_words = set(tc.input.lower().split())
                    output_words = set(tc.actual_output.lower().split())
                    score = len(input_words & output_words) / len(input_words) if input_words else 0.0
                    scores[metric.value] = min(1.0, score + 0.3)  # Boost
                    
                elif metric == DeepEvalMetric.FAITHFULNESS:
                    # Context grounding
                    if tc.context:
                        context_text = " ".join(tc.context).lower()
                        output_words = tc.actual_output.lower().split()
                        grounded = sum(1 for w in output_words if w in context_text) / len(output_words) if output_words else 0.0
                        scores[metric.value] = grounded
                    else:
                        scores[metric.value] = 0.5
                    
                elif metric == DeepEvalMetric.HALLUCINATION:
                    # Inverse of faithfulness (low = no hallucination = good)
                    if tc.context:
                        context_text = " ".join(tc.context).lower()
                        output_words = tc.actual_output.lower().split()
                        ungrounded = sum(1 for w in output_words if w not in context_text) / len(output_words) if output_words else 0.0
                        scores[metric.value] = 1.0 - ungrounded  # Convert to "no hallucination" score
                    else:
                        scores[metric.value] = 0.5
                
                else:
                    scores[metric.value] = 0.5
            
            avg_score = sum(scores.values()) / len(scores) if scores else 0.0
            if avg_score < self.threshold:
                passed = False
                failures.append({"index": i, "score": avg_score})
            
            total_score += avg_score
            test_results.append({
                "index": i,
                "passed": passed,
                "scores": scores,
            })
        
        overall_score = total_score / len(test_cases) if test_cases else 1.0
        
        return DeepEvalResult(
            passed=len(failures) == 0,
            score=overall_score,
            test_results=test_results,
            failures=failures,
            metadata={"note": "Fallback heuristic testing used"},
        )
    
    def create_test_cases_from_samples(
        self,
        samples: List[Dict[str, Any]],
    ) -> List[DeepEvalTestCase]:
        """
        Create test cases from sample data.
        
        Args:
            samples: List of dicts with question, answer, context keys
            
        Returns:
            List of DeepEvalTestCase
        """
        test_cases = []
        
        for sample in samples:
            test_cases.append(DeepEvalTestCase(
                input=sample.get("question", sample.get("input", "")),
                actual_output=sample.get("answer", sample.get("actual_output", "")),
                expected_output=sample.get("expected_output"),
                context=sample.get("context", sample.get("contexts")),
            ))
        
        return test_cases
    
    def get_summary_report(self, result: DeepEvalResult) -> str:
        """Generate a human-readable summary report."""
        lines = [
            "=" * 50,
            "DeepEval Test Report",
            "=" * 50,
            f"Total Tests: {len(result.test_results)}",
            f"Passed: {len(result.test_results) - len(result.failures)}",
            f"Failed: {len(result.failures)}",
            f"Overall Score: {result.score:.3f}",
            f"Status: {'PASSED' if result.passed else 'FAILED'}",
            "",
        ]
        
        if result.failures:
            lines.append("Failures:")
            for failure in result.failures[:5]:  # Show first 5
                lines.append(f"  - Test {failure['index']}: {failure.get('reason', failure.get('score', 'Unknown'))}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


# Default instance
deepeval_tester = DeepEvalTester()

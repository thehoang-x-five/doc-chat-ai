"""
Self RAG Service - Pattern #3

Iterative self-refinement and validation of responses.
Consolidated from: base.py, checker.py, refiner.py, rewriter.py
"""
import logging
from collections.abc import Callable
from typing import Any

from .models import (
    HallucinationCheck,
    QualityDelta,
    RefinementStep,
    SelfRAGResult,
    docs_to_context,
    get_doc_content,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components (inlined from separate files)
# =============================================================================

class QualityChecker:
    """
    Checks response quality using NLI and hallucination detection.
    Currently uses simplified word overlap.
    """

    def __init__(self, min_grounding_score: float = 0.5):
        self.min_grounding_score = min_grounding_score

    async def check_relevance(self, response: str, documents: list[Any]) -> float:
        """
        Check if response is relevant to documents.
        
        Args:
            response: Generated response
            documents: Retrieved documents
            
        Returns:
            Relevance score (0-1)
        """
        if not documents:
            return 0.0

        response_words = set(response.lower().split())

        overlaps = []
        for doc in documents:
            doc_content = get_doc_content(doc)
            doc_words = set(doc_content.lower().split())

            if len(response_words) > 0:
                overlap = len(response_words & doc_words) / len(response_words)
                overlaps.append(overlap)

        relevance = sum(overlaps) / len(overlaps) if overlaps else 0.0
        logger.debug(f"Relevance score: {relevance:.2f}")
        return relevance

    async def detect_hallucinations(
        self,
        response: str,
        context: str,
    ) -> HallucinationCheck:
        """
        Detect hallucinations in response.
        
        Args:
            response: Generated response
            context: Context from documents
            
        Returns:
            HallucinationCheck result
        """
        response_words = set(response.lower().split())
        context_words = set(context.lower().split())

        if len(response_words) == 0:
            return HallucinationCheck(has_hallucination=False, grounding_score=1.0)

        # Grounding score = overlap with context
        grounding_score = len(response_words & context_words) / len(response_words)

        # Detect absolute statements not in context
        hallucinated_segments = []
        absolute_patterns = [
            "definitely", "certainly", "absolutely", "always", "never",
            "all", "every", "none", "no one"
        ]

        for pattern in absolute_patterns:
            if pattern in response.lower() and pattern not in context.lower():
                hallucinated_segments.append(pattern)

        has_hallucination = grounding_score < self.min_grounding_score

        logger.debug(
            f"Hallucination check: grounding={grounding_score:.2f}, "
            f"has_hallucination={has_hallucination}"
        )

        return HallucinationCheck(
            has_hallucination=has_hallucination,
            grounding_score=grounding_score,
            hallucinated_segments=hallucinated_segments,
        )


class ResponseRefiner:
    """Tracks refinement iterations and quality improvements."""

    def track_iteration(
        self,
        iteration: int,
        query: str,
        response: str,
        relevance: float,
        grounding: float,
        action: str,
    ) -> RefinementStep:
        """Track a refinement iteration."""
        truncated_response = response[:200] + "..." if len(response) > 200 else response

        return RefinementStep(
            iteration=iteration,
            query_used=query,
            response_generated=truncated_response,
            relevance_score=relevance,
            grounding_score=grounding,
            action_taken=action,
        )

    def calculate_quality_delta(
        self,
        metric_name: str,
        before_score: float,
        after_score: float,
    ) -> QualityDelta:
        """Calculate quality improvement."""
        improvement = after_score - before_score

        logger.debug(
            f"Quality delta for {metric_name}: "
            f"{before_score:.2f} -> {after_score:.2f} (+{improvement:.2f})"
        )

        return QualityDelta(
            metric_name=metric_name,
            before=before_score,
            after=after_score,
            improvement=improvement,
        )


class QueryRewriter:
    """Rewrites queries for better retrieval."""

    async def rewrite_query(self, original_query: str, failed_response: str) -> str:
        """
        Rewrite query for better retrieval.
        
        Args:
            original_query: Original user query
            failed_response: Response that failed quality check
            
        Returns:
            Rewritten query with expanded terms
        """
        query_words = original_query.split()

        # term expansions
        expansions = {
            "python": ["python programming", "python language"],
            "code": ["source code", "programming code"],
            "error": ["bug", "issue", "problem"],
            "fix": ["solve", "resolve", "repair"],
        }

        expanded_terms = []
        for word in query_words:
            word_lower = word.lower()
            if word_lower in expansions:
                expanded_terms.extend(expansions[word_lower])

        if expanded_terms:
            rewritten = f"{original_query} {' '.join(expanded_terms[:2])}"
        else:
            rewritten = f"{original_query} detailed explanation"

        logger.info(f"Query rewritten: '{original_query}' -> '{rewritten}'")
        return rewritten


# =============================================================================
# Main Service
# =============================================================================

class SelfRAGService:
    """
    Service implementing Self RAG pattern.
    
    Uses iterative self-refinement where the LLM validates and improves
    its own responses through multiple iterations.
    
    Flow:
    1. Generate initial response
    2. Check relevance to documents (NLI)
    3. Detect hallucinations (grounding score)
    4. If quality insufficient, rewrite query and retry
    5. Repeat up to max_iterations
    6. Return best response with confidence score
    """

    def __init__(
        self,
        max_iterations: int = 3,
        min_relevance_score: float = 0.6,
        min_grounding_score: float = 0.5,
    ):
        """
        Initialize Self RAG service.
        
        Args:
            max_iterations: Maximum refinement iterations
            min_relevance_score: Minimum relevance score to accept
            min_grounding_score: Minimum grounding score to accept
        """
        self.max_iterations = max_iterations
        self.min_relevance_score = min_relevance_score
        self.min_grounding_score = min_grounding_score

        self.checker = QualityChecker(min_grounding_score=min_grounding_score)
        self.refiner = ResponseRefiner()
        self.rewriter = QueryRewriter()

        logger.info(
            f"SelfRAGService initialized: "
            f"max_iterations={max_iterations}, "
            f"min_relevance={min_relevance_score}, "
            f"min_grounding={min_grounding_score}"
        )

    async def generate_with_refinement(
        self,
        query: str,
        documents: list[Any],
        generate_func: Callable,
        retrieve_func: Callable,
    ) -> SelfRAGResult:
        """
        Generate response with self-refinement.
        
        Args:
            query: Original user query
            documents: Retrieved documents
            generate_func: Function to generate response (query, docs) -> response
            retrieve_func: Function to retrieve documents (query) -> docs
            
        Returns:
            SelfRAGResult with refined response
        """
        refinement_log = []
        quality_improvements = []

        current_query = query
        current_docs = documents
        best_response = None
        best_score = 0.0

        try:
            for iteration in range(1, self.max_iterations + 1):
                logger.info(f"Self-RAG iteration {iteration}/{self.max_iterations}")

                # Generate response
                response = await generate_func(current_query, current_docs)

                # Check relevance
                relevance_score = await self.checker.check_relevance(response, current_docs)

                # Detect hallucinations
                hallucination_check = await self.checker.detect_hallucinations(
                    response,
                    docs_to_context(current_docs)
                )
                grounding_score = hallucination_check.grounding_score

                # Combined quality score
                quality_score = (relevance_score + grounding_score) / 2.0

                # Log refinement step
                action = "accept"
                if quality_score < (self.min_relevance_score + self.min_grounding_score) / 2.0:
                    action = "rewrite" if iteration < self.max_iterations else "accept"

                refinement_log.append(self.refiner.track_iteration(
                    iteration=iteration,
                    query=current_query,
                    response=response,
                    relevance=relevance_score,
                    grounding=grounding_score,
                    action=action,
                ))

                # Track best response
                if quality_score > best_score:
                    if best_response:
                        quality_improvements.append(self.refiner.calculate_quality_delta(
                            metric_name="combined_quality",
                            before_score=best_score,
                            after_score=quality_score,
                        ))

                    best_response = response
                    best_score = quality_score

                # Check if quality is acceptable
                if (relevance_score >= self.min_relevance_score and
                    grounding_score >= self.min_grounding_score):
                    logger.info(
                        f"Quality acceptable at iteration {iteration}: "
                        f"relevance={relevance_score:.2f}, grounding={grounding_score:.2f}"
                    )
                    break

                # Rewrite query for next iteration
                if iteration < self.max_iterations:
                    logger.info(
                        f"Quality insufficient (score={quality_score:.2f}), "
                        f"rewriting query for iteration {iteration + 1}"
                    )

                    current_query = await self.rewriter.rewrite_query(query, response)
                    current_docs = await retrieve_func(current_query)

                    logger.info(f"Rewritten query: {current_query}")
                    logger.info(f"Retrieved {len(current_docs)} new documents")

            return SelfRAGResult(
                final_response=best_response or "Unable to generate satisfactory response",
                iterations_used=len(refinement_log),
                quality_improvements=quality_improvements,
                confidence_score=best_score,
                refinement_log=refinement_log,
                success=best_response is not None,
            )

        except Exception as e:
            logger.error(f"Error in self-refinement: {e}")

            return SelfRAGResult(
                final_response=best_response or "Error during refinement",
                iterations_used=len(refinement_log),
                quality_improvements=quality_improvements,
                confidence_score=best_score,
                refinement_log=refinement_log,
                success=False,
                error_message=str(e),
            )

    def get_refinement_summary(self, result: SelfRAGResult) -> str:
        """Get human-readable refinement summary."""
        lines = ["Self-RAG Refinement Summary:", ""]

        for step in result.refinement_log:
            lines.append(f"Iteration {step.iteration}:")
            lines.append(f"  Query: {step.query_used}")
            lines.append(f"  Relevance: {step.relevance_score:.2f}")
            lines.append(f"  Grounding: {step.grounding_score:.2f}")
            lines.append(f"  Action: {step.action_taken}")
            lines.append("")

        lines.append("Quality Improvements:")
        for delta in result.quality_improvements:
            lines.append(
                f"  {delta.metric_name}: {delta.before:.2f} -> {delta.after:.2f} "
                f"(+{delta.improvement:.2f})"
            )

        lines.append("")
        lines.append(f"Final Confidence: {result.confidence_score:.2f}")
        lines.append(f"Iterations Used: {result.iterations_used}/{self.max_iterations}")

        return "\n".join(lines)

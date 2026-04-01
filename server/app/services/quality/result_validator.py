"""
Result Validator - Confidence scoring and hallucination detection for RAG responses.

This module provides:
1. Confidence scoring based on retrieval quality and answer coherence
2. Hallucination detection by comparing response with source documents
3. Relevance checking between query, context, and response
4. Citation validation ensuring claims are grounded in sources

"""
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable, Set

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Overall validation status."""
    PASS = "pass"  # Response is valid and well-grounded
    WARN = "warn"  # Response has minor issues but usable
    FAIL = "fail"  # Response has significant issues


class HallucinationType(Enum):
    """Types of hallucination detected."""
    NONE = "none"  # No hallucination detected
    FABRICATED_FACT = "fabricated_fact"  # Fact not in sources
    CONTRADICTORY = "contradictory"  # Contradicts source material
    EXAGGERATED = "exaggerated"  # Exaggeration of source claims
    UNSUBSTANTIATED = "unsubstantiated"  # Claim without supporting evidence


@dataclass
class ValidationIssue:
    """Individual validation issue found."""
    issue_type: str  # "hallucination", "relevance", "confidence", "citation"
    severity: str  # "low", "medium", "high"
    description: str
    location: Optional[str] = None  # Where in response the issue occurs
    suggestion: Optional[str] = None  # How to fix the issue
    

@dataclass
class ValidationResult:
    """
    Complete validation result for a RAG response.
    
    Attributes:
        status: Overall validation status
        confidence_score: Overall confidence in response quality (0-1)
        retrieval_confidence: Confidence in retrieval quality (0-1)
        answer_confidence: Confidence in answer quality (0-1)
        hallucination_type: Type of hallucination detected if any
        hallucination_score: Likelihood of hallucination (0-1, lower is better)
        relevance_score: Relevance of response to query (0-1)
        groundedness_score: How well response is grounded in sources (0-1)
        issues: List of validation issues found
        metadata: Additional validation metadata
    """
    status: ValidationStatus
    confidence_score: float
    retrieval_confidence: float = 0.0
    answer_confidence: float = 0.0
    hallucination_type: HallucinationType = HallucinationType.NONE
    hallucination_score: float = 0.0
    relevance_score: float = 0.0
    groundedness_score: float = 0.0
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self, min_confidence: float = 0.7) -> bool:
        """Check if response passes validation with given confidence threshold."""
        return (
            self.status != ValidationStatus.FAIL
            and self.confidence_score >= min_confidence
            and self.hallucination_score < 0.5
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "confidence_score": self.confidence_score,
            "retrieval_confidence": self.retrieval_confidence,
            "answer_confidence": self.answer_confidence,
            "hallucination_type": self.hallucination_type.value,
            "hallucination_score": self.hallucination_score,
            "relevance_score": self.relevance_score,
            "groundedness_score": self.groundedness_score,
            "issues": [
                {
                    "type": i.issue_type,
                    "severity": i.severity,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "metadata": self.metadata,
            "is_valid": self.is_valid(),
        }


class ResultValidator:
    """
    Result Validator for RAG response quality assurance.
    
    Validates responses by:
    1. Calculating confidence scores based on retrieval quality
    2. Detecting potential hallucinations
    3. Checking relevance to the original query
    4. Verifying claims are grounded in source documents
    
    Usage:
        validator = ResultValidator()
        result = await validator.validate(
            query="What is RAG?",
            response="RAG is Retrieval-Augmented Generation...",
            sources=[{"content": "RAG stands for..."}],
        )
        if result.is_valid():
            # Use the response
            pass
    """
    
    # Keywords that often indicate uncertainty
    UNCERTAINTY_PHRASES = [
        "i think", "i believe", "probably", "maybe", "might be",
        "could be", "possibly", "it seems", "appears to", "likely",
        "tôi nghĩ", "có thể", "có lẽ", "dường như", "hình như",
    ]
    
    # Keywords that often indicate hallucination
    HALLUCINATION_INDICATORS = [
        "as i mentioned", "as we discussed", "as you know",
        "obviously", "clearly everyone knows", "it's well known that",
        "according to my knowledge", "in my experience",
        "như tôi đã nói", "như chúng ta đã thảo luận",
    ]
    
    def __init__(
        self,
        confidence_threshold: float = 0.7,
        hallucination_threshold: float = 0.5,
        use_llm: bool = False,
        llm_fn: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize the Result Validator.
        
        Args:
            confidence_threshold: Minimum confidence for valid response
            hallucination_threshold: Maximum hallucination score for valid response
            use_llm: Whether to use LLM for advanced validation
            llm_fn: Optional LLM function for advanced checks
        """
        self.confidence_threshold = confidence_threshold
        self.hallucination_threshold = hallucination_threshold
        self.use_llm = use_llm
        self.llm_fn = llm_fn
        
        logger.info(
            f"ResultValidator initialized (confidence≥{confidence_threshold}, "
            f"hallucination≤{hallucination_threshold})"
        )
    
    async def validate(
        self,
        query: str,
        response: str,
        sources: List[Dict[str, Any]],
        retrieval_scores: Optional[List[float]] = None,
    ) -> ValidationResult:
        """
        Validate a RAG response.
        
        Args:
            query: Original user query
            response: Generated response to validate
            sources: List of source documents used for generation
            retrieval_scores: Optional retrieval scores for each source
            
        Returns:
            ValidationResult with confidence scores and issues
        """
        if not query or not response:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                confidence_score=0.0,
                issues=[ValidationIssue(
                    issue_type="input",
                    severity="high",
                    description="Empty query or response",
                )],
            )
        
        issues = []
        
        # 1. Calculate retrieval confidence
        retrieval_confidence = self._calculate_retrieval_confidence(
            sources, retrieval_scores
        )
        
        # 2. Check hallucination
        hallucination_type, hallucination_score = self._detect_hallucination(
            response, sources
        )
        if hallucination_score > 0.3:
            severity = "high" if hallucination_score > 0.7 else "medium"
            issues.append(ValidationIssue(
                issue_type="hallucination",
                severity=severity,
                description=f"Potential hallucination detected: {hallucination_type.value}",
                suggestion="Consider rephrasing or adding source citations",
            ))
        
        # 3. Check relevance
        relevance_score = self._calculate_relevance(query, response)
        if relevance_score < 0.5:
            issues.append(ValidationIssue(
                issue_type="relevance",
                severity="medium",
                description="Response may not directly answer the query",
                suggestion="Provide a more focused answer to the question",
            ))
        
        # 4. Check groundedness
        groundedness_score = self._calculate_groundedness(response, sources)
        if groundedness_score < 0.5:
            issues.append(ValidationIssue(
                issue_type="groundedness",
                severity="medium",
                description="Response contains claims not well-grounded in sources",
                suggestion="Add citations or remove unsupported claims",
            ))
        
        # 5. Check answer quality
        answer_confidence = self._calculate_answer_confidence(response)
        if answer_confidence < 0.5:
            issues.append(ValidationIssue(
                issue_type="confidence",
                severity="low",
                description="Response contains uncertainty indicators",
                suggestion="Provide more definitive statements where possible",
            ))
        
        # 6. Calculate overall confidence
        confidence_score = self._calculate_overall_confidence(
            retrieval_confidence=retrieval_confidence,
            answer_confidence=answer_confidence,
            relevance_score=relevance_score,
            groundedness_score=groundedness_score,
            hallucination_score=hallucination_score,
        )
        
        # 7. Determine status
        if confidence_score >= self.confidence_threshold and hallucination_score < self.hallucination_threshold:
            status = ValidationStatus.PASS
        elif confidence_score >= 0.5 or len(issues) <= 1:
            status = ValidationStatus.WARN
        else:
            status = ValidationStatus.FAIL
        
        return ValidationResult(
            status=status,
            confidence_score=confidence_score,
            retrieval_confidence=retrieval_confidence,
            answer_confidence=answer_confidence,
            hallucination_type=hallucination_type,
            hallucination_score=hallucination_score,
            relevance_score=relevance_score,
            groundedness_score=groundedness_score,
            issues=issues,
            metadata={
                "num_sources": len(sources),
                "response_length": len(response),
                "query_length": len(query),
            },
        )
    
    def _calculate_retrieval_confidence(
        self,
        sources: List[Dict[str, Any]],
        retrieval_scores: Optional[List[float]],
    ) -> float:
        """Calculate confidence based on retrieval quality."""
        if not sources:
            return 0.0
        
        # If retrieval scores provided, use them
        if retrieval_scores:
            # Average of top scores, weighted by position
            weighted_sum = 0.0
            weight_sum = 0.0
            for i, score in enumerate(retrieval_scores[:5]):  # Top 5
                weight = 1.0 / (i + 1)  # Higher weight for earlier results
                weighted_sum += score * weight
                weight_sum += weight
            return min(1.0, weighted_sum / weight_sum) if weight_sum > 0 else 0.0
        
        # Otherwise, estimate from source content
        total_content = sum(len(s.get("content", "")) for s in sources)
        
        # More content generally means better retrieval
        if total_content > 2000:
            return 0.9
        elif total_content > 1000:
            return 0.8
        elif total_content > 500:
            return 0.7
        elif total_content > 200:
            return 0.6
        else:
            return 0.5
    
    def _detect_hallucination(
        self,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> tuple[HallucinationType, float]:
        """Detect potential hallucination in response."""
        response_lower = response.lower()
        
        # Check for hallucination indicator phrases
        indicator_count = sum(
            1 for phrase in self.HALLUCINATION_INDICATORS
            if phrase in response_lower
        )
        
        if indicator_count > 0:
            return HallucinationType.UNSUBSTANTIATED, min(1.0, 0.3 * indicator_count)
        
        # Check if response contains facts not in sources
        source_text = " ".join(s.get("content", "") for s in sources).lower()
        
        # Extract potential facts from response (sentences with numbers, names, etc.)
        sentences = re.split(r'[.!?]', response)
        ungrounded_count = 0
        total_factual = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains factual claims (numbers, proper nouns, etc.)
            has_numbers = bool(re.search(r'\d+', sentence))
            has_proper_nouns = bool(re.search(r'\b[A-Z][a-z]+\b', sentence))
            
            if has_numbers or has_proper_nouns:
                total_factual += 1
                
                # Check if key words appear in sources
                words = set(sentence.lower().split())
                source_words = set(source_text.split())
                
                overlap = len(words & source_words) / len(words) if words else 0
                if overlap < 0.3:
                    ungrounded_count += 1
        
        if total_factual == 0:
            return HallucinationType.NONE, 0.0
        
        hallucination_score = ungrounded_count / total_factual
        
        if hallucination_score > 0.5:
            return HallucinationType.FABRICATED_FACT, hallucination_score
        elif hallucination_score > 0.2:
            return HallucinationType.UNSUBSTANTIATED, hallucination_score
        else:
            return HallucinationType.NONE, hallucination_score
    
    def _calculate_relevance(
        self,
        query: str,
        response: str,
    ) -> float:
        """Calculate relevance of response to query."""
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when", "where"}
        query_words -= stopwords
        response_words -= stopwords
        
        if not query_words:
            return 1.0  # No specific query words to check
        
        # Calculate overlap
        overlap = len(query_words & response_words)
        relevance = overlap / len(query_words)
        
        return min(1.0, relevance)
    
    def _calculate_groundedness(
        self,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> float:
        """Calculate how well response is grounded in sources."""
        if not sources:
            return 0.0
        
        source_text = " ".join(s.get("content", "") for s in sources).lower()
        source_words = set(source_text.split())
        
        response_words = set(response.lower().split())
        
        # Remove very common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "in", "on", "at", "to", "for"}
        response_words -= stopwords
        
        if not response_words:
            return 1.0
        
        overlap = len(response_words & source_words)
        groundedness = overlap / len(response_words)
        
        return min(1.0, groundedness)
    
    def _calculate_answer_confidence(
        self,
        response: str,
    ) -> float:
        """Calculate confidence based on answer quality indicators."""
        response_lower = response.lower()
        
        # Check for uncertainty phrases
        uncertainty_count = sum(
            1 for phrase in self.UNCERTAINTY_PHRASES
            if phrase in response_lower
        )
        
        # More uncertainty phrases = lower confidence
        if uncertainty_count >= 3:
            return 0.4
        elif uncertainty_count >= 2:
            return 0.6
        elif uncertainty_count >= 1:
            return 0.75
        else:
            return 0.9
    
    def _calculate_overall_confidence(
        self,
        retrieval_confidence: float,
        answer_confidence: float,
        relevance_score: float,
        groundedness_score: float,
        hallucination_score: float,
    ) -> float:
        """Calculate overall confidence score."""
        # Weighted combination of factors
        weights = {
            "retrieval": 0.25,
            "answer": 0.20,
            "relevance": 0.20,
            "groundedness": 0.25,
            "hallucination": 0.10,  # Penalty for hallucination
        }
        
        confidence = (
            weights["retrieval"] * retrieval_confidence
            + weights["answer"] * answer_confidence
            + weights["relevance"] * relevance_score
            + weights["groundedness"] * groundedness_score
            - weights["hallucination"] * hallucination_score  # Subtract hallucination penalty
        )
        
        return max(0.0, min(1.0, confidence))
    
    async def validate_with_llm(
        self,
        query: str,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> ValidationResult:
        """
        Validate using LLM for more sophisticated analysis.
        
        This method uses an LLM to check:
        1. Whether the response adequately answers the query
        2. Whether claims are supported by sources
        3. Whether there are any contradictions
        
        Args:
            query: Original query
            response: Response to validate
            sources: Source documents
            
        Returns:
            ValidationResult with LLM-enhanced analysis
        """
        if not self.llm_fn:
            logger.warning("No LLM function provided, falling back to rule-based validation")
            return await self.validate(query, response, sources)
        
        # First do rule-based validation
        base_result = await self.validate(query, response, sources)
        
        # Then enhance with LLM
        try:
            source_text = "\n\n".join(
                f"Source {i+1}: {s.get('content', '')[:500]}"
                for i, s in enumerate(sources[:5])
            )
            
            prompt = f"""Analyze this RAG response for quality and accuracy.

Query: {query}

Response: {response}

Source Documents:
{source_text}

Evaluate the response on these criteria (score 0-10 for each):
1. Accuracy: Does the response correctly reflect the sources?
2. Completeness: Does it answer the question fully?
3. Groundedness: Are all claims supported by sources?
4. Relevance: Is the response focused on the question?

Provide your analysis in this format:
ACCURACY: [score]
COMPLETENESS: [score]
GROUNDEDNESS: [score]
RELEVANCE: [score]
ISSUES: [list any issues found]"""
            
            llm_response = await self.llm_fn(prompt)
            
            # Parse LLM response
            scores = self._parse_llm_scores(llm_response)
            
            # Update result with LLM scores
            if scores:
                base_result.groundedness_score = scores.get("groundedness", base_result.groundedness_score)
                base_result.relevance_score = scores.get("relevance", base_result.relevance_score)
                
                # Recalculate overall confidence
                base_result.confidence_score = self._calculate_overall_confidence(
                    retrieval_confidence=base_result.retrieval_confidence,
                    answer_confidence=scores.get("accuracy", base_result.answer_confidence),
                    relevance_score=base_result.relevance_score,
                    groundedness_score=base_result.groundedness_score,
                    hallucination_score=base_result.hallucination_score,
                )
                
                base_result.metadata["llm_validated"] = True
                base_result.metadata["llm_scores"] = scores
                
        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            base_result.metadata["llm_error"] = str(e)
        
        return base_result
    
    def _parse_llm_scores(self, llm_response: str) -> Dict[str, float]:
        """Parse scores from LLM response."""
        scores = {}
        patterns = {
            "accuracy": r"ACCURACY:\s*(\d+(?:\.\d+)?)",
            "completeness": r"COMPLETENESS:\s*(\d+(?:\.\d+)?)",
            "groundedness": r"GROUNDEDNESS:\s*(\d+(?:\.\d+)?)",
            "relevance": r"RELEVANCE:\s*(\d+(?:\.\d+)?)",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, llm_response, re.IGNORECASE)
            if match:
                # Normalize score from 0-10 to 0-1
                scores[key] = min(1.0, float(match.group(1)) / 10.0)
        
        return scores


# Default instance
result_validator = ResultValidator()

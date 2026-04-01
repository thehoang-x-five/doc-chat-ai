"""
Hallucination Checker - NLI-based verification for RAG responses.

This module provides:
1. Faithfulness scoring using Natural Language Inference
2. Sentence-level entailment checking
3. Loop-back trigger for low-scoring responses

Threshold: < 0.7 triggers regeneration.

"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EntailmentResult:
    """Result of entailment check for a single sentence."""
    sentence: str
    entailment_score: float  # 0-1, higher = more supported
    contradiction_score: float  # 0-1, higher = more contradicted
    neutral_score: float  # 0-1
    supporting_context: Optional[str] = None
    is_hallucination: bool = False


@dataclass
class HallucinationCheckResult:
    """Complete hallucination check result."""
    faithfulness_score: float  # Overall score 0-1
    is_faithful: bool  # True if score >= threshold
    sentence_results: List[EntailmentResult] = field(default_factory=list)
    hallucinated_sentences: List[str] = field(default_factory=list)
    needs_regeneration: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "faithfulness_score": self.faithfulness_score,
            "is_faithful": self.is_faithful,
            "hallucinated_sentences": self.hallucinated_sentences,
            "needs_regeneration": self.needs_regeneration,
            "num_sentences_checked": len(self.sentence_results),
            "metadata": self.metadata,
        }


class HallucinationChecker:
    """
    Hallucination Checker using NLI-based verification.
    
    Checks if each sentence in the answer is entailed (supported) by
    the provided context. Sentences that are contradicted or not
    supported are flagged as potential hallucinations.
    
    Usage:
        checker = HallucinationChecker()
        result = await checker.check_faithfulness(
            answer="RAG was invented in 2020...",
            context="RAG was introduced in the paper by Lewis et al...",
        )
        if not result.is_faithful:
            # Handle hallucination
            pass
    """
    
    # Default threshold for faithful responses
    DEFAULT_THRESHOLD = 0.7
    
    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        nli_model_fn: Optional[Callable[[str, str], Tuple[float, float, float]]] = None,
        use_llm: bool = True,
        llm_fn: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize the Hallucination Checker.
        
        Args:
            threshold: Minimum faithfulness score (0-1)
            nli_model_fn: Optional NLI model function (premise, hypothesis) -> (entail, contradict, neutral)
            use_llm: Whether to use LLM for checking (if no NLI model)
            llm_fn: Optional LLM function for checking
        """
        self.threshold = threshold
        self.nli_model_fn = nli_model_fn
        self.use_llm = use_llm
        self.llm_fn = llm_fn
        
        logger.info(f"HallucinationChecker initialized (threshold={threshold})")
    
    async def check_faithfulness(
        self,
        answer: str,
        context: str,
    ) -> HallucinationCheckResult:
        """
        Check if answer is faithful to the context.
        
        Args:
            answer: Generated answer to check
            context: Source context (retrieved documents)
            
        Returns:
            HallucinationCheckResult with faithfulness score
        """
        if not answer or not context:
            return HallucinationCheckResult(
                faithfulness_score=0.0 if not context else 1.0,
                is_faithful=not answer,  # Empty answer is "faithful"
                needs_regeneration=bool(answer and not context),
            )
        
        # Split answer into sentences
        sentences = self._split_sentences(answer)
        
        if not sentences:
            return HallucinationCheckResult(
                faithfulness_score=1.0,
                is_faithful=True,
            )
        
        # Check each sentence
        sentence_results = []
        hallucinated = []
        
        for sentence in sentences:
            result = await self._check_sentence(sentence, context)
            sentence_results.append(result)
            if result.is_hallucination:
                hallucinated.append(sentence)
        
        # Calculate overall faithfulness score
        if sentence_results:
            faithfulness_score = sum(r.entailment_score for r in sentence_results) / len(sentence_results)
        else:
            faithfulness_score = 1.0
        
        is_faithful = faithfulness_score >= self.threshold
        
        return HallucinationCheckResult(
            faithfulness_score=faithfulness_score,
            is_faithful=is_faithful,
            sentence_results=sentence_results,
            hallucinated_sentences=hallucinated,
            needs_regeneration=not is_faithful,
            metadata={
                "num_sentences": len(sentences),
                "num_hallucinated": len(hallucinated),
                "threshold": self.threshold,
            },
        )
    
    async def _check_sentence(
        self,
        sentence: str,
        context: str,
    ) -> EntailmentResult:
        """Check a single sentence against context."""
        # Skip very short sentences
        if len(sentence.split()) < 3:
            return EntailmentResult(
                sentence=sentence,
                entailment_score=1.0,
                contradiction_score=0.0,
                neutral_score=0.0,
            )
        
        # Use NLI model if available
        if self.nli_model_fn:
            try:
                entail, contradict, neutral = self.nli_model_fn(context, sentence)
                return EntailmentResult(
                    sentence=sentence,
                    entailment_score=entail,
                    contradiction_score=contradict,
                    neutral_score=neutral,
                    is_hallucination=contradict > 0.5 or (entail < 0.3 and neutral > 0.5),
                )
            except Exception as e:
                logger.warning(f"NLI model failed: {e}")
        
        # Use LLM-based checking
        if self.use_llm and self.llm_fn:
            return await self._check_with_llm(sentence, context)
        
        # Fallback: simple word overlap heuristic
        return self._check_with_heuristic(sentence, context)
    
    async def _check_with_llm(
        self,
        sentence: str,
        context: str,
    ) -> EntailmentResult:
        """Check sentence using LLM."""
        prompt = f"""You are a fact-checking assistant. Determine if the CLAIM is supported by the CONTEXT.

CONTEXT:
{context[:2000]}

CLAIM: {sentence}

Answer with one of:
- SUPPORTED: The claim is directly supported by the context
- CONTRADICTED: The claim contradicts the context
- NEUTRAL: The claim cannot be verified from the context

Respond with just one word: SUPPORTED, CONTRADICTED, or NEUTRAL"""
        
        try:
            response = await self.llm_fn(prompt)
            response = response.strip().upper()
            
            if "SUPPORTED" in response:
                return EntailmentResult(
                    sentence=sentence,
                    entailment_score=0.9,
                    contradiction_score=0.05,
                    neutral_score=0.05,
                )
            elif "CONTRADICTED" in response:
                return EntailmentResult(
                    sentence=sentence,
                    entailment_score=0.1,
                    contradiction_score=0.8,
                    neutral_score=0.1,
                    is_hallucination=True,
                )
            else:  # NEUTRAL or unknown
                return EntailmentResult(
                    sentence=sentence,
                    entailment_score=0.4,
                    contradiction_score=0.1,
                    neutral_score=0.5,
                    is_hallucination=True,  # Unsupported claims are risky
                )
        except Exception as e:
            logger.error(f"LLM check failed: {e}")
            return self._check_with_heuristic(sentence, context)
    
    def _check_with_heuristic(
        self,
        sentence: str,
        context: str,
    ) -> EntailmentResult:
        """Simple heuristic-based checking using word overlap."""
        sentence_words = set(sentence.lower().split())
        context_words = set(context.lower().split())
        
        # Remove stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "in", "on", "at", "to", "for", "of"}
        sentence_words -= stopwords
        
        if not sentence_words:
            return EntailmentResult(
                sentence=sentence,
                entailment_score=1.0,
                contradiction_score=0.0,
                neutral_score=0.0,
            )
        
        overlap = len(sentence_words & context_words) / len(sentence_words)
        
        # High overlap = likely supported
        if overlap > 0.6:
            entailment_score = 0.8
            is_hallucination = False
        elif overlap > 0.3:
            entailment_score = 0.5
            is_hallucination = False
        else:
            entailment_score = 0.2
            is_hallucination = True
        
        return EntailmentResult(
            sentence=sentence,
            entailment_score=entailment_score,
            contradiction_score=0.1,
            neutral_score=1.0 - entailment_score - 0.1,
            is_hallucination=is_hallucination,
        )
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitter
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Filter out very short sentences
        return [s.strip() for s in sentences if len(s.strip()) > 10]


# Default instance
hallucination_checker = HallucinationChecker()

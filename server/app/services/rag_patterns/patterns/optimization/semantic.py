"""
Semantic Highlight RAG Service - Context compression via semantic extraction.

Compresses context by selecting only the most relevant sentences.
Consolidated from: base.py, splitter.py, scorer.py, selector.py, compressor.py
"""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

try:
    import nltk
    from nltk.tokenize import sent_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

@dataclass
class Sentence:
    """A sentence in text."""
    text: str
    start_pos: int
    end_pos: int
    chunk_id: int
    relevance_score: float | None = None


@dataclass
class CompressionMetrics:
    """Metrics measuring compression effectiveness."""
    original_tokens: int
    compressed_tokens: int
    reduction_percentage: float
    original_sentences: int
    selected_sentences: int
    processing_time_ms: float
    threshold_used: float


@dataclass
class SemanticHighlightResult:
    """Result of context compression process."""
    compressed_context: str
    original_chunks: list[str]
    selected_sentences: list[Sentence]
    metrics: CompressionMetrics
    success: bool = True
    error_message: str | None = None


# =============================================================================
# Helper Components
# =============================================================================

class SentenceSplitter:
    """Splits text into individual sentences (English/Vietnamese/Multilingual)."""
    
    ABBREVIATIONS = {'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Sr', 'Jr', 'vs', 'etc', 'e.g', 'i.e'}
    
    def __init__(self, language: str = "multilingual"):
        self.language = language.lower()
        if NLTK_AVAILABLE and self.language in ["en", "multilingual"]:
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                try:
                    nltk.download('punkt', quiet=True)
                except Exception:
                    pass

    def split(self, text: str, chunk_id: int = 0) -> list[Sentence]:
        """Split text into sentences."""
        if not text or not text.strip():
            return []
        
        text = text.strip()
        sentences = self._split_multilingual(text) if self.language == "multilingual" else self._split_with_regex(text)
        
        result, current_pos = [], 0
        for sent_text in sentences:
            sent_text = self._postprocess_text(sent_text)
            start_pos = text.find(sent_text, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(sent_text)
            result.append(Sentence(text=sent_text.strip(), start_pos=start_pos, end_pos=end_pos, chunk_id=chunk_id))
            current_pos = end_pos
        
        if not result:
            result.append(Sentence(text=text, start_pos=0, end_pos=len(text), chunk_id=chunk_id))
        
        return result

    def _split_multilingual(self, text: str) -> list[str]:
        if NLTK_AVAILABLE:
            try:
                sentences = sent_tokenize(text)
                return [s.strip() for s in sentences if s.strip()]
            except Exception:
                pass
        return self._split_with_regex(text)

    def _split_with_regex(self, text: str) -> list[str]:
        text = self._preprocess_text(text)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def _preprocess_text(self, text: str) -> str:
        text = re.sub(r'(\d)\.(\d)', r'\1<DECIMAL>\2', text)
        for abbr in self.ABBREVIATIONS:
            text = re.sub(rf'\b{abbr}\.', f'{abbr}<ABBR>', text, flags=re.IGNORECASE)
        return text

    def _postprocess_text(self, text: str) -> str:
        return text.replace('<DECIMAL>', '.').replace('<ABBR>', '.')


class SemanticScorer:
    """Scores sentences by semantic similarity to query."""
    
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
        self._query_cache = {}
        self.batch_size = 32

    async def score_batch(self, query: str, sentences: list[Sentence]) -> list[float]:
        """Score sentences by relevance to query."""
        if not sentences or not query:
            return [0.0] * len(sentences) if sentences else []
        
        try:
            query_embedding = self._get_query_embedding(query)
            sentence_texts = [s.text for s in sentences]
            sentence_embeddings = self._get_sentence_embeddings(sentence_texts)
            scores = self._calculate_similarities(query_embedding, sentence_embeddings)
            return self._normalize_scores(scores)
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            return [0.0] * len(sentences)

    def _get_query_embedding(self, query: str) -> list[float]:
        if query in self._query_cache:
            return self._query_cache[query]
        embedding = self.embedding_service.embed_text_simple(query)
        self._query_cache[query] = embedding
        return embedding

    def _get_sentence_embeddings(self, sentence_texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(sentence_texts), self.batch_size):
            batch = sentence_texts[i:i + self.batch_size]
            all_embeddings.extend(self.embedding_service.embed_batch_simple(batch))
        return all_embeddings

    def _calculate_similarities(self, query_embedding: list[float], sentence_embeddings: list[list[float]]) -> list[float]:
        if not sentence_embeddings or np is None:
            return [0.0] * len(sentence_embeddings)
        
        query_vec = np.array(query_embedding)
        sentence_vecs = np.array(sentence_embeddings)
        query_norm = np.linalg.norm(query_vec)
        
        if query_norm == 0:
            return [-1.0] * len(sentence_embeddings)
        
        similarities = []
        for sent_vec in sentence_vecs:
            sent_norm = np.linalg.norm(sent_vec)
            if sent_norm == 0:
                similarities.append(-1.0)
            else:
                similarities.append(float(np.dot(query_vec, sent_vec) / (query_norm * sent_norm)))
        return similarities

    def _normalize_scores(self, scores: list[float]) -> list[float]:
        return [max(0.0, min(1.0, (score + 1.0) / 2.0)) for score in scores]


class EvidenceSelector:
    """Selects high-scoring sentences based on threshold."""
    
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def select(self, sentences: list[Sentence], scores: list[float], threshold: float | None = None) -> list[Sentence]:
        """Select sentences with score >= threshold."""
        effective_threshold = threshold if threshold is not None else self.threshold
        return [s for s, score in zip(sentences, scores) if score >= effective_threshold]


class ContextCompressor:
    """Compresses context by joining selected sentences."""
    
    def __init__(self, tokenizer: str = "cl100k_base"):
        if tiktoken is None:
            raise ImportError("tiktoken is required for ContextCompressor")
        self.encoding = tiktoken.get_encoding(tokenizer)

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text)) if text else 0

    def compress(self, selected_sentences: list[Sentence], original_chunks: list[str], threshold_used: float = 0.5) -> SemanticHighlightResult:
        """Compress context from selected sentences."""
        start_time = time.time()
        
        try:
            compressed_context = " ".join(s.text for s in selected_sentences)
            original_text = " ".join(original_chunks)
            original_tokens = self._count_tokens(original_text)
            compressed_tokens = self._count_tokens(compressed_context)
            
            reduction_percentage = ((1 - compressed_tokens / original_tokens) * 100) if original_tokens > 0 else 0.0
            
            original_sentences = sum(len([s for s in chunk.replace('!', '.').replace('?', '.').split('.') if s.strip()]) for chunk in original_chunks)
            
            metrics = CompressionMetrics(
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                reduction_percentage=reduction_percentage,
                original_sentences=original_sentences,
                selected_sentences=len(selected_sentences),
                processing_time_ms=(time.time() - start_time) * 1000,
                threshold_used=threshold_used
            )
            
            return SemanticHighlightResult(
                compressed_context=compressed_context,
                original_chunks=original_chunks,
                selected_sentences=selected_sentences,
                metrics=metrics,
                success=True
            )
        except Exception as e:
            return SemanticHighlightResult(
                compressed_context=" ".join(original_chunks),
                original_chunks=original_chunks,
                selected_sentences=[],
                metrics=CompressionMetrics(0, 0, 0, 0, 0, 0, threshold_used),
                success=False,
                error_message=str(e)
            )


# =============================================================================
# Main Service
# =============================================================================

class SemanticHighlightRAGService:
    """
    Semantic Highlight RAG Service.
    
    Compresses context by extracting only the most relevant sentences.
    
    Pipeline:
    1. Split chunks into sentences (SentenceSplitter)
    2. Score sentences by query relevance (SemanticScorer)
    3. Select high-scoring sentences (EvidenceSelector)
    4. Compress context and calculate metrics (ContextCompressor)
    
    Features:
    - Error handling with fallback to original chunks
    - Configurable threshold and language
    - Sentence count limiting
    """

    def __init__(
        self,
        embedding_service,
        relevance_threshold: float = 0.5,
        max_sentences_per_chunk: int = 50,
        language: str = "multilingual",
        tokenizer: str = "cl100k_base"
    ):
        if not 0.0 <= relevance_threshold <= 1.0:
            raise ValueError(f"relevance_threshold must be between 0.0 and 1.0, got {relevance_threshold}")

        self.embedding_service = embedding_service
        self.relevance_threshold = relevance_threshold
        self.max_sentences_per_chunk = max_sentences_per_chunk
        self.language = language

        self.splitter = SentenceSplitter(language=language)
        self.scorer = SemanticScorer(embedding_service=embedding_service)
        self.selector = EvidenceSelector(threshold=relevance_threshold)
        self.compressor = ContextCompressor(tokenizer=tokenizer)

        logger.info(f"SemanticHighlightRAGService: threshold={relevance_threshold}, max_sentences={max_sentences_per_chunk}")

    async def compress_context(self, query: str, chunks: list[str], threshold: float | None = None) -> SemanticHighlightResult:
        """Compress context using semantic highlighting."""
        start_time = time.time()
        effective_threshold = threshold if threshold is not None else self.relevance_threshold
        
        logger.info(f"Starting semantic highlight: {len(chunks)} chunks, threshold={effective_threshold}")

        try:
            # Step 1: Split chunks into sentences
            all_sentences = []
            for chunk_id, chunk in enumerate(chunks):
                try:
                    all_sentences.extend(self.splitter.split(chunk, chunk_id=chunk_id))
                except Exception as e:
                    logger.error(f"Failed to split chunk {chunk_id}: {e}")

            if not all_sentences:
                return self._create_fallback_result(chunks, effective_threshold, "No sentences extracted")

            # Step 2: Limit sentences
            max_total = self.max_sentences_per_chunk * len(chunks)
            if len(all_sentences) > max_total:
                all_sentences = all_sentences[:max_total]

            # Step 3: Score sentences
            try:
                scores = await self.scorer.score_batch(query, all_sentences)
            except Exception as e:
                return self._create_fallback_result(chunks, effective_threshold, f"Scoring failed: {e}")

            # Step 4: Select high-scoring sentences
            selected_sentences = self.selector.select(all_sentences, scores, threshold=effective_threshold)
            
            if not selected_sentences:
                return self._create_fallback_result(chunks, effective_threshold, f"No sentences met threshold {effective_threshold}")

            # Step 5: Compress and return
            result = self.compressor.compress(selected_sentences, chunks, threshold_used=effective_threshold)
            
            logger.info(f"Compression: {result.metrics.original_tokens} → {result.metrics.compressed_tokens} tokens "
                       f"({result.metrics.reduction_percentage:.1f}% reduction), time: {(time.time() - start_time) * 1000:.1f}ms")
            
            return result

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return self._create_fallback_result(chunks, effective_threshold, f"Unexpected error: {e}")

    def _create_fallback_result(self, chunks: list[str], threshold: float, error_message: str) -> SemanticHighlightResult:
        """Create fallback result when processing fails."""
        logger.warning(f"Using fallback: {error_message}")
        original_text = " ".join(chunks)
        try:
            original_tokens = self.compressor._count_tokens(original_text)
        except Exception:
            original_tokens = len(original_text.split())

        return SemanticHighlightResult(
            compressed_context=original_text,
            original_chunks=chunks,
            selected_sentences=[],
            metrics=CompressionMetrics(original_tokens, original_tokens, 0.0, 0, 0, 0.0, threshold),
            success=False,
            error_message=error_message
        )

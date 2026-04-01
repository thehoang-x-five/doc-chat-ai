"""
Grounding verification service - Dịch vụ xác minh grounding.
Ngăn chặn hallucination bằng cách xác minh câu trả lời của LLM dựa trên context được cung cấp.

Pattern từ AI Engineering best practices:
- Kiểm tra token overlap giữa answer và context
- Xác minh sự hiện diện của citations
- Trả về grounding score và confidence

Nâng cao với:
- Semantic similarity sử dụng sentence embeddings
- NLI (Natural Language Inference) để kiểm tra entailment
- Weighted scoring kết hợp nhiều phương pháp
"""
import logging
import re
from typing import Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import sentence transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")

# Try to import transformers for NLI
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available. Install with: pip install transformers")


@dataclass
class GroundingResult:
    """Kết quả xác minh grounding."""
    is_grounded: bool
    confidence: float
    reason: str


@dataclass
class EnhancedGroundingResult:
    """Kết quả grounding nâng cao với nhiều điểm số"""
    is_grounded: bool
    overall_score: float
    token_overlap_score: float
    semantic_similarity_score: float
    entailment_score: float
    confidence: float
    reason: str
    should_regenerate: bool


@dataclass
class EntailmentResult:
    """Kết quả kiểm tra entailment"""
    label: str  # "entailment", "neutral", "contradiction"
    score: float
    confidence: float


class GroundingVerifier:
    """Xác minh các response của LLM có dựa trên context được cung cấp."""
    
    def __init__(self):
        # Stopwords để loại trừ khỏi tính toán token overlap
        self.stopwords = {
            # English
            'the', 'and', 'for', 'are', 'but', 'not', 'with', 'this', 'that',
            'from', 'have', 'has', 'had', 'can', 'will', 'would', 'could',
            # Vietnamese
            'của', 'và', 'là', 'có', 'được', 'trong', 'cho', 'để', 'với',
            'này', 'đó', 'các', 'những', 'một', 'từ', 'theo', 'như', 'về'
        }
        
        # Lazy load models
        self._embedder = None
        self._nli_model = None
    
    def _get_embedder(self):
        """Lazy load sentence transformer"""
        if self._embedder is None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except Exception as e:
                logger.warning(f"Không thể load sentence transformer: {e}")
                self._embedder = None
        return self._embedder
    
    def _get_nli_model(self):
        """Lazy load NLI model"""
        if self._nli_model is None and TRANSFORMERS_AVAILABLE:
            try:
                self._nli_model = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-base")
            except Exception as e:
                logger.warning(f"Không thể load NLI model: {e}")
                self._nli_model = None
        return self._nli_model
    
    def verify(
        self, 
        answer: str, 
        context: str,
        min_overlap: float = 0.25
    ) -> GroundingResult:
        """
        Check if answer is grounded in context.
        
        Args:
            answer: LLM generated answer
            context: Retrieved context provided to LLM
            min_overlap: Minimum token overlap ratio (default: 0.25)
            
        Returns:
            GroundingResult with is_grounded, confidence, and reason
        """
        if not answer or not answer.strip():
            return GroundingResult(
                is_grounded=True,
                confidence=1.0,
                reason="Empty answer"
            )
        
        if not context or not context.strip():
            return GroundingResult(
                is_grounded=False,
                confidence=0.0,
                reason="No context provided"
            )
        
        # Extract meaningful tokens
        answer_tokens = self._extract_tokens(answer)
        context_tokens = self._extract_tokens(context)
        
        if not answer_tokens:
            return GroundingResult(
                is_grounded=True,
                confidence=1.0,
                reason="Không có token có nghĩa trong answer"
            )
        
        # Tính overlap
        overlap = len(answer_tokens & context_tokens)
        overlap_ratio = overlap / len(answer_tokens)
        
        # Kiểm tra citations
        has_citations = bool(re.search(r'\[.*?\]', answer))
        
        # Logic quyết định grounding
        if overlap_ratio >= min_overlap:
            return GroundingResult(
                is_grounded=True,
                confidence=overlap_ratio,
                reason=f"Overlap cao: {overlap_ratio:.1%}"
            )
        elif has_citations and overlap_ratio >= 0.15:
            return GroundingResult(
                is_grounded=True,
                confidence=overlap_ratio + 0.1,  # Bonus cho citations
                reason=f"Có citations, overlap vừa phải: {overlap_ratio:.1%}"
            )
        else:
            return GroundingResult(
                is_grounded=False,
                confidence=overlap_ratio,
                reason=f"Overlap thấp: {overlap_ratio:.1%}, citations không đủ"
            )
    
    async def verify_with_semantics(
        self,
        answer: str,
        context: str
    ) -> EnhancedGroundingResult:
        """
        Xác minh grounding sử dụng nhiều phương pháp: token overlap, semantic similarity, và entailment.
        
        Weighted scoring: token overlap (40%), semantic (30%), entailment (30%)
        
        Args:
            answer: Câu trả lời được generate bởi LLM
            context: Context được retrieve
            
        Returns:
            EnhancedGroundingResult với các điểm số chi tiết
        """
        # 1. Token overlap (40% weight)
        basic_result = self.verify(answer, context)
        token_overlap_score = basic_result.confidence
        
        # 2. Semantic similarity (30% weight)
        semantic_score = await self.compute_semantic_similarity(answer, context)
        
        # 3. Entailment (30% weight)
        entailment_result = await self.check_entailment(answer, context)
        entailment_score = entailment_result.score if entailment_result.label == "entailment" else 0.0
        
        # Tính overall score có trọng số
        overall_score = (
            token_overlap_score * 0.4 +
            semantic_score * 0.3 +
            entailment_score * 0.3
        )
        
        # Xác định có grounded không
        is_grounded = overall_score >= 0.5
        should_regenerate = overall_score < 0.5
        
        # Xây dựng reason
        reason_parts = [
            f"Token overlap: {token_overlap_score:.2f}",
            f"Semantic: {semantic_score:.2f}",
            f"Entailment: {entailment_score:.2f}",
            f"Overall: {overall_score:.2f}"
        ]
        reason = " | ".join(reason_parts)
        
        # Log nếu được đánh dấu để review
        if should_regenerate:
            logger.warning(f"Phát hiện grounding score thấp: {overall_score:.2f} - {reason}")
        
        return EnhancedGroundingResult(
            is_grounded=is_grounded,
            overall_score=overall_score,
            token_overlap_score=token_overlap_score,
            semantic_similarity_score=semantic_score,
            entailment_score=entailment_score,
            confidence=overall_score,
            reason=reason,
            should_regenerate=should_regenerate
        )
    
    async def compute_semantic_similarity(
        self,
        answer: str,
        context: str
    ) -> float:
        """
        Tính semantic similarity sử dụng sentence embeddings.
        
        Args:
            answer: Text câu trả lời
            context: Text context
            
        Returns:
            Similarity score 0.0-1.0
        """
        embedder = self._get_embedder()
        if not embedder:
            # Fallback sang token overlap
            logger.debug("Sentence transformer không khả dụng, sử dụng token overlap fallback")
            return self.verify(answer, context).confidence
        
        try:
            # Encode texts
            answer_embedding = embedder.encode(answer, convert_to_tensor=True)
            context_embedding = embedder.encode(context, convert_to_tensor=True)
            
            # Tính cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            similarity = cosine_similarity(
                answer_embedding.cpu().numpy().reshape(1, -1),
                context_embedding.cpu().numpy().reshape(1, -1)
            )[0][0]
            
            # Normalize về khoảng 0-1
            return float(max(0.0, min(1.0, similarity)))
        except Exception as e:
            logger.warning(f"Tính toán semantic similarity thất bại: {e}")
            return self.verify(answer, context).confidence
    
    async def check_entailment(
        self,
        answer: str,
        context: str
    ) -> EntailmentResult:
        """
        Kiểm tra xem answer có được entail bởi context sử dụng NLI model.
        
        Args:
            answer: Text câu trả lời (hypothesis)
            context: Text context (premise)
            
        Returns:
            EntailmentResult với label và score
        """
        nli_model = self._get_nli_model()
        if not nli_model:
            # Fallback: giả định neutral với confidence vừa phải
            logger.debug("NLI model không khả dụng, sử dụng fallback")
            return EntailmentResult(
                label="neutral",
                score=0.5,
                confidence=0.5
            )
        
        try:
            # Truncate texts nếu quá dài
            max_length = 512
            answer_truncated = answer[:max_length]
            context_truncated = context[:max_length]
            
            # Format cho NLI: premise [SEP] hypothesis
            nli_input = f"{context_truncated} [SEP] {answer_truncated}"
            
            # Chạy NLI
            result = nli_model(nli_input)[0]
            
            label = result['label'].lower()
            score = result['score']
            
            return EntailmentResult(
                label=label,
                score=score,
                confidence=score
            )
        except Exception as e:
            logger.warning(f"Kiểm tra entailment thất bại: {e}")
            return EntailmentResult(
                label="neutral",
                score=0.5,
                confidence=0.5
            )
    
    def _extract_tokens(self, text: str) -> set:
        """
        Trích xuất các tokens có nghĩa (3+ ký tự, loại trừ stopwords).
        
        Args:
            text: Text đầu vào
            
        Returns:
            Set các tokens đã lowercase
        """
        # Trích xuất words (3+ ký tự)
        tokens = re.findall(r'\w{3,}', text.lower())
        
        # Loại bỏ stopwords và trả về set
        return set(t for t in tokens if t not in self.stopwords and len(t) >= 3)


# Singleton instance
_grounding_verifier: GroundingVerifier = None


def get_grounding_verifier() -> GroundingVerifier:
    """Lấy hoặc tạo grounding verifier singleton."""
    global _grounding_verifier
    if _grounding_verifier is None:
        _grounding_verifier = GroundingVerifier()
    return _grounding_verifier

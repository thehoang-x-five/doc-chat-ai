"""
Reranking service giúp cải thiện độ liên quan của kết quả tìm kiếm.
Sử dụng mô hình cross-encoder để đánh giá lại (rerank) độ tương đồng ngữ nghĩa.

Pattern from AI Engineering Toolkit:
- Hybrid retrieval lấy top-K=20 (high recall)
- Reranker lọc xuống top-K=5 (high precision)
- Độ chính xác cao hơn so với chỉ dùng vector/BM25 scores
"""
import logging
from typing import List, Optional

try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    CrossEncoder = None

from app.services.core.retriever_service import RetrievalResult

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Rerank kết quả tìm kiếm sử dụng cross-encoder.
    
    Cross-encoders tính toán độ liên quan bằng cách encode cả query và document cùng lúc,
    cho kết quả chính xác hơn so với vector embeddings riêng lẻ (bi-encoder).
    
    Models khuyến nghị:
    - cross-encoder/ms-marco-multilingual-v2: Hỗ trợ đa ngôn ngữ (VN + EN)
    - cross-encoder/ms-marco-MiniLM-L-6-v2: Nhanh, chỉ tiếng Anh
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-multilingual-v2"):
        """
        Khởi tạo reranker service với cross-encoder model.
        
        Args:
            model_name: Tên HuggingFace model
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "sentence-transformers chưa được cài đặt. Reranking sẽ bị tắt. "
                "Cài đặt bằng lệnh: pip install sentence-transformers"
            )
            self.model = None
            self.model_name = None
            return
        
        self.model_name = model_name
        self.model: Optional[CrossEncoder] = None
        logger.info(f"Đang khởi tạo RerankerService với model: {model_name}")
    
    def _load_model(self) -> None:
        """Lazy load model khi cần sử dụng lần đầu."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            return
        
        if self.model is None:
            logger.info(f"Đang load cross-encoder model: {self.model_name}")
            self.model = CrossEncoder(self.model_name)
            logger.info("Load cross-encoder model thành công")
    
    async def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Đánh giá lại (Rerank) kết quả dựa trên độ liên quan với query.
        
        Args:
            query: Câu hỏi người dùng
            results: Danh sách chunks từ hybrid retriever
            top_k: Số lượng kết quả tốt nhất cần lấy
            
        Returns:
            Danh sách đã rerank (top_k items, sắp xếp theo độ liên quan giảm dần)
        """
        if not results:
            return []
        
        if len(results) <= top_k:
            # Không cần rerank nếu số kết quả ít hơn hoặc bằng top_k
            return results
        
        # Nếu không có sentence-transformers, trả về kết quả gốc
        if not SENTENCE_TRANSFORMERS_AVAILABLE or self.model is None:
            logger.warning("Reranking bị tắt - trả về kết quả gốc")
            return results[:top_k]
        
        # Lazy load model
        self._load_model()
        
        logger.debug(f"Đang rerank {len(results)} kết quả xuống top-{top_k}")
        
        # Chuẩn bị cặp input cho cross-encoder: [[query, doc1], [query, doc2], ...]
        pairs = [[query, r.content] for r in results]
        
        # Tính điểm relevance
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.error(f"Lỗi Reranking: {e}", exc_info=True)
            # Fallback: trả về kết quả gốc
            return results[:top_k]
        
        # Gán điểm rerank vào kết quả
        for i, result in enumerate(results):
            result.rerank_score = float(scores[i])
        
        # Sắp xếp theo điểm rerank (cao nhất trước)
        reranked = sorted(results, key=lambda x: x.rerank_score, reverse=True)
        
        logger.debug(f"Kết quả Rerank, điểm cao nhất: {reranked[0].rerank_score:.4f}")
        
        return reranked[:top_k]


# Singleton instance
_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    """Lấy hoặc tạo singleton reranker service."""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service

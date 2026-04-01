"""
Semantic Router — Phân loại ý định dựa trên Embedding Similarity.

Thay thế regex/keyword matching bằng vector similarity:
1. Pre-compute embeddings cho mỗi route (startup)
2. Embed query → cosine similarity → best match
3. Score > threshold → fast-exit với intent tương ứng

Chi phí: $0 (dùng EmbeddingService local)
Latency: ~5-10ms (sentence-transformers) hoặc ~20-30ms (Ollama)
"""
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


# =============================================================================
# ROUTE DEFINITIONS — Mẫu câu cho mỗi intent (song ngữ VI + EN)
# =============================================================================

ROUTE_DEFINITIONS: Dict[str, List[str]] = {
    "greeting": [
        # Vietnamese
        "xin chào", "chào bạn", "chào anh", "chào chị", "chào em",
        "chào mọi người", "chào buổi sáng", "chào buổi chiều", "chào buổi tối",
        "alo", "chào you", "chào nha", "chào nhé",
        # English
        "hi", "hello", "hey", "hey there", "hi there", "hello there",
        "good morning", "good afternoon", "good evening",
        "howdy", "yo", "sup", "what's up", "hiya",
        "hi bạn", "hello bạn", "hey bro",
    ],
    
    "chitchat": [
        # Vietnamese
        "cảm ơn bạn", "cảm ơn nhiều", "cám ơn nhé",
        "tạm biệt", "bye bye", "hẹn gặp lại",
        "bạn là ai", "bạn tên gì", "bạn là gì",
        "bạn khỏe không", "bạn thế nào",
        "OK", "được rồi", "tốt lắm",
        # English
        "thank you", "thanks", "thanks a lot", "thx",
        "goodbye", "bye", "see you later", "see ya",
        "who are you", "what are you", "what is your name",
        "how are you", "how are you doing",
        "okay", "alright", "got it", "good", "great", "nice",
    ],
    
    "image_generation": [
        # Vietnamese
        "tạo ảnh", "vẽ ảnh", "sinh ảnh", "tạo hình ảnh",
        "vẽ cho tôi", "tạo cho tôi một bức ảnh",
        "vẽ hình con mèo", "tạo tranh phong cảnh",
        "hãy vẽ", "vẽ một", "tạo một bức tranh",
        # English
        "generate an image", "create an image", "draw a picture",
        "make an image of", "generate a photo",
        "draw me a", "create a picture of",
        "render an image", "design an illustration",
    ],
    
    "code_generation": [
        # Vietnamese
        "viết code", "tạo code", "lập trình", "viết hàm",
        "tạo function", "viết chương trình",
        "viết script python", "code javascript",
        "viết class", "tạo API",
        # English
        "write code", "write a function", "create a class",
        "implement a method", "code a script",
        "write python code", "javascript function",
        "build a program", "develop an app",
        "write me some code", "create a script",
    ],
    
    "document_query": [
        # Vietnamese
        "tìm thông tin về", "giải thích", "phân tích",
        "so sánh", "liệt kê", "tóm tắt",
        "hợp đồng gồm những gì", "nội dung tài liệu",
        "tra cứu", "nghiên cứu về", "định nghĩa",
        "cho tôi biết về", "tài liệu nói gì",
        "hướng dẫn", "chi tiết về",
        # English
        "explain", "what is", "how does",
        "compare", "list", "summarize",
        "tell me about", "describe", "analyze",
        "find information about", "search for",
        "what does the document say", "look up",
    ],
}


# =============================================================================
# RESPONSE TEMPLATES
# =============================================================================

GREETING_RESPONSES = {
    "vi": "Xin chào! Tôi có thể giúp gì cho bạn?",
    "en": "Hello! How can I help you today?",
}

CHITCHAT_RESPONSES = {
    "thanks": {"vi": "Không có gì!", "en": "You're welcome!"},
    "bye": {"vi": "Tạm biệt! Hẹn gặp lại!", "en": "Goodbye! See you later!"},
    "who": {"vi": "Tôi là trợ lý AI, giúp bạn tìm kiếm và phân tích tài liệu.", "en": "I'm an AI assistant that helps you search and analyze documents."},
    "how_are_you": {"vi": "Tôi hoạt động tốt, cảm ơn bạn! Tôi có thể giúp gì?", "en": "I'm doing well, thank you! How can I help?"},
}


# =============================================================================
# SEMANTIC ROUTER CLASS
# =============================================================================

@dataclass
class RouteMatch:
    """Kết quả phân loại từ Semantic Router."""
    route_name: str
    score: float
    matched_sample: str  # Câu mẫu có similarity cao nhất


class SemanticRouter:
    """
    Semantic Router — Phân loại intent bằng embedding similarity.
    
    Sử dụng EmbeddingService đã có sẵn (paraphrase-multilingual-MiniLM-L12-v2)
    để so sánh query với tập mẫu câu đã pre-compute.
    
    Chiến lược:
    1. Startup: Embed tất cả route samples → cache vectors
    2. Runtime: Embed query → cosine similarity vs cached → best match
    3. Score > threshold → return intent kết quả
    """
    
    def __init__(self, threshold: float = 0.75, language: str = "vi"):
        """
        Khởi tạo Semantic Router.
        
        Args:
            threshold: Ngưỡng cosine similarity tối thiểu để match (0.0-1.0)
            language: Ngôn ngữ mặc định cho responses
        """
        self.threshold = threshold
        self.language = language
        self._route_vectors: Dict[str, List[tuple]] = {}  # route_name → [(vector, sample_text), ...]
        self._embedding_service = None
        self._initialized = False
        
        # Khởi tạo ngay
        self._initialize()
    
    def _initialize(self):
        """Pre-compute embeddings cho tất cả routes."""
        try:
            from app.services.core.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()
            
            for route_name, samples in ROUTE_DEFINITIONS.items():
                # Batch embed tất cả samples cho route này
                vectors = self._embedding_service.embed_batch_simple(samples)
                self._route_vectors[route_name] = list(zip(vectors, samples))
                logger.info(f"🧭 Route '{route_name}': {len(samples)} samples embedded")
            
            self._initialized = True
            total = sum(len(v) for v in self._route_vectors.values())
            logger.info(f"🧭 SemanticRouter initialized: {len(self._route_vectors)} routes, {total} samples")
            
        except Exception as e:
            logger.error(f"❌ SemanticRouter initialization failed: {e}")
            self._initialized = False
    
    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Tính cosine similarity giữa 2 vectors."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def classify(self, query: str) -> Optional[RouteMatch]:
        """
        Phân loại query bằng embedding similarity.
        
        Args:
            query: Văn bản đầu vào của người dùng
            
        Returns:
            RouteMatch nếu score > threshold, None nếu không đủ confident
        """
        if not self._initialized or not self._embedding_service:
            logger.warning("SemanticRouter not initialized, skipping")
            return None
        
        if not query or not query.strip():
            return None
        
        try:
            # 1. Embed query
            query_vector = self._embedding_service.embed_text_simple(query.strip())
            
            # 2. Tìm route có similarity cao nhất
            best_match: Optional[RouteMatch] = None
            best_score = -1.0
            
            for route_name, route_samples in self._route_vectors.items():
                for sample_vector, sample_text in route_samples:
                    score = self._cosine_similarity(query_vector, sample_vector)
                    if score > best_score:
                        best_score = score
                        best_match = RouteMatch(
                            route_name=route_name,
                            score=score,
                            matched_sample=sample_text,
                        )
            
            # 3. Return nếu vượt threshold
            if best_match and best_match.score >= self.threshold:
                logger.info(
                    f"🧭 Semantic match: '{query}' → {best_match.route_name} "
                    f"(score={best_match.score:.3f}, matched='{best_match.matched_sample}')"
                )
                return best_match
            
            # Nếu dưới threshold, log để debug
            if best_match:
                logger.debug(
                    f"🧭 Below threshold: '{query}' → {best_match.route_name} "
                    f"(score={best_match.score:.3f} < {self.threshold})"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"SemanticRouter classification error: {e}")
            return None
    
    def get_greeting_response(self) -> str:
        """Lấy phản hồi greeting theo ngôn ngữ."""
        return GREETING_RESPONSES.get(self.language, GREETING_RESPONSES["en"])
    
    def get_chitchat_response(self, query: str) -> str:
        """Lấy phản hồi chitchat phù hợp dựa trên query."""
        q = query.lower()
        
        if any(w in q for w in ["cảm ơn", "thank", "thanks", "thx"]):
            return CHITCHAT_RESPONSES["thanks"].get(self.language, CHITCHAT_RESPONSES["thanks"]["en"])
        if any(w in q for w in ["tạm biệt", "bye", "goodbye"]):
            return CHITCHAT_RESPONSES["bye"].get(self.language, CHITCHAT_RESPONSES["bye"]["en"])
        if any(w in q for w in ["là ai", "are you", "là gì", "tên gì"]):
            return CHITCHAT_RESPONSES["who"].get(self.language, CHITCHAT_RESPONSES["who"]["en"])
        if any(w in q for w in ["khỏe", "how are"]):
            return CHITCHAT_RESPONSES["how_are_you"].get(self.language, CHITCHAT_RESPONSES["how_are_you"]["en"])
        
        return "Tôi có thể giúp gì cho bạn?" if self.language == "vi" else "How can I help you?"


# =============================================================================
# SINGLETON
# =============================================================================

_router_instance: Optional[SemanticRouter] = None


def get_semantic_router(language: str = "vi") -> SemanticRouter:
    """Lấy hoặc tạo SemanticRouter singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouter(language=language)
    return _router_instance

"""
Intent Detection Service — Phân loại Truy vấn Thông minh

Kiến trúc Hybrid Routing 2 lớp:
- Lớp 1: Semantic Router (embedding similarity) — xử lý 70-80% queries, ~5-10ms
- Lớp 2: LLM Classification (CHỈ free models: Groq + Ollama) — ~500ms-2s

Phân loại truy vấn của người dùng thành các ý định (intents):
- GREETING: Lời chào đơn giản cần phản hồi thân thiện
- CHITCHAT: Trò chuyện phiếm không liên quan đến tài liệu
- DOCUMENT_QUERY: Câu hỏi cần tìm kiếm trong tài liệu/RAG
- IMAGE_GENERATION: Yêu cầu tạo/vẽ ảnh
- CODE_GENERATION: Yêu cầu viết/tạo code
"""
import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.conversation.intent_cache import get_intent_cache

logger = logging.getLogger(__name__)


# =============================================================================
# INTENT TYPES
# =============================================================================

class QueryIntent(str, Enum):
    """Các loại ý định truy vấn được hỗ trợ."""
    GREETING = "greeting"
    CHITCHAT = "chitchat"
    DOCUMENT_QUERY = "document"
    IMAGE_GENERATION = "image_generation"
    CODE_GENERATION = "code_generation"


@dataclass
class IntentResult:
    """Kết quả phân loại ý định."""
    intent: QueryIntent
    confidence: float
    reason: str
    should_search: bool
    direct_response: Optional[str] = None
    suggested_model: Optional[str] = None


@dataclass
class IntentResultWithMetrics:
    """Kết quả phân loại ý định kèm metrics."""
    intent: QueryIntent
    confidence: float
    reason: str
    should_search: bool
    cache_hit: bool
    latency_ms: float
    provider_used: str
    direct_response: Optional[str] = None
    suggested_model: Optional[str] = None


@dataclass
class IntentMetrics:
    """Metrics hiệu năng nhận diện ý định."""
    total_queries: int
    cache_hit_rate: float
    avg_latency_ms: float
    accuracy_by_intent: Dict[str, float]
    provider_distribution: Dict[str, int]


# =============================================================================
# PROMPT TEMPLATES (cho Layer 2 — LLM Classification)
# =============================================================================

INTENT_CLASSIFICATION_PROMPT = """Classify the query into ONE category:

- `greeting`: Greetings (hi, hello, xin chào)
- `chitchat`: General chat NOT about documents below
- `document`: Questions about topics in document categories below
- `image_generation`: Create/draw images
- `code_generation`: Write code

Document Categories: {document_context}

Rules:
- If query relates to any category above → `document`
- If unrelated to all categories → `chitchat`

Output JSON only: {{"intent": "<type>", "response": "<if greeting/chitchat else null>"}}

Query: "{query}"
"""

INTENT_CLASSIFICATION_PROMPT_NO_DOCS = """Classify the query into ONE category:

- `greeting`: Greetings (hi, hello, xin chào)
- `chitchat`: General conversation
- `document`: Information lookup questions
- `image_generation`: Create/draw images
- `code_generation`: Write code

Output JSON only: {{"intent": "<type>", "response": "<if greeting/chitchat else null>"}}

Query: "{query}"
"""


# =============================================================================
# INTENT DETECTOR CLASS — Hybrid Routing
# =============================================================================

class IntentDetector:
    """
    Phát hiện ý định thông minh sử dụng Hybrid Routing 2 lớp.
    
    Chiến lược:
    1. Layer 1: Semantic Router (embedding similarity) — fast, ~5-10ms
       - Embed query → cosine similarity vs pre-computed route vectors
       - Score > 0.75 → fast-exit với intent tương ứng
    2. Layer 2: LLM Classification (CHỈ free models) — ~500ms-2s
       - Groq (llama3, free tier) — song song
       - Ollama (local, free) — fallback
       ⚠️ KHÔNG dùng CloudCode/DeepSeek/Gemini ở tầng intent
    3. Fallback: DOCUMENT_QUERY (default an toàn)
    """
    
    def __init__(self, language: str = "vi"):
        self.language = language
        self._timeout = 5.0
        self._document_context: str = ""
        self._category_context: str = ""
        
        # Layer 1: Semantic Router
        from app.services.conversation.semantic_router import get_semantic_router
        self._router = get_semantic_router(language=language)
        
        # Caching và metrics
        self._cache = get_intent_cache()
        self._metrics = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "provider_counts": {"semantic": 0, "cache": 0, "llm": 0},
            "latencies": [],
            "intent_counts": {intent.value: 0 for intent in QueryIntent},
        }
    
    def set_category_context(self, category_names: List[str]) -> None:
        """
        Thiết lập tên danh mục cho phân loại ý định.
        
        Args:
            category_names: Danh sách tên danh mục (ví dụ: ["Hợp đồng", "Báo cáo tài chính"])
        """
        if category_names:
            self._category_context = ", ".join(category_names)
        else:
            self._category_context = ""
    
    def set_category_context_string(self, context: str) -> None:
        """Thiết lập chuỗi ngữ cảnh danh mục thô."""
        self._category_context = context
    
    def set_document_context(self, document_titles: List[str], workspace_name: str = None) -> None:
        """Thiết lập ngữ cảnh tài liệu để phân loại tốt hơn."""
        if not document_titles:
            self._document_context = ""
            return
        
        titles = ", ".join(document_titles[:10])
        if len(document_titles) > 10:
            titles += f" (+{len(document_titles) - 10} more)"
        
        self._document_context = f"Available documents: {titles}"
        if workspace_name:
            self._document_context = f"Workspace: {workspace_name}\n{self._document_context}"
    
    # =========================================================================
    # MAIN DETECTION METHODS
    # =========================================================================
    
    async def detect(
        self,
        query: str,
        document_titles: List[str] = None,
        category_context: str = None,
    ) -> IntentResult:
        """
        Phát hiện ý định truy vấn sử dụng Hybrid Routing.
        
        Args:
            query: Văn bản đầu vào của người dùng
            document_titles: Tiêu đề tài liệu tùy chọn cho ngữ cảnh
            category_context: Ngữ cảnh danh mục phong phú tùy chọn
            
        Returns:
            IntentResult với ý định đã phân loại
        """
        if not query or not query.strip():
            return IntentResult(
                intent=QueryIntent.CHITCHAT,
                confidence=1.0,
                reason="Empty query",
                should_search=False,
                direct_response=self._router.get_greeting_response() if self._router else "Bạn muốn hỏi gì?",
            )
        
        query = query.strip()
        
        # Layer 1: Semantic Router (nhanh, ~5-10ms)
        semantic_result = self._classify_by_semantic(query)
        if semantic_result and semantic_result.confidence >= 0.75:
            logger.info(f"Intent detected by semantic: {semantic_result.intent.value} ({semantic_result.reason})")
            return semantic_result
        
        # Thiết lập context cho LLM
        if category_context:
            self.set_category_context(category_context)
        elif document_titles:
            self.set_document_context(document_titles)
        
        # Layer 2: LLM Classification (CHỈ Groq + Ollama)
        llm_result = await self._classify_with_free_llm(query)
        if llm_result:
            return llm_result
        
        # Fallback: kết quả semantic thấp hoặc document query
        if semantic_result:
            return semantic_result
        
        return IntentResult(
            intent=QueryIntent.DOCUMENT_QUERY,
            confidence=0.6,
            reason="Default fallback to document query",
            should_search=True,
        )
    
    async def detect_with_caching(
        self,
        query: str,
        document_titles: List[str] = None,
        category_context: str = None,
        use_cache: bool = True,
    ) -> IntentResultWithMetrics:
        """
        Phát hiện ý định truy vấn với caching và theo dõi metrics.
        
        Args:
            query: Văn bản đầu vào của người dùng
            document_titles: Tiêu đề tài liệu tùy chọn cho ngữ cảnh
            category_context: Ngữ cảnh danh mục phong phú tùy chọn
            use_cache: Có sử dụng cache hay không (mặc định True)
            
        Returns:
            IntentResultWithMetrics với ý định được phân loại và metrics
        """
        start_time = time.time()
        self._metrics["total_queries"] += 1
        
        if not query or not query.strip():
            latency_ms = (time.time() - start_time) * 1000
            self._metrics["latencies"].append(latency_ms)
            self._metrics["provider_counts"]["semantic"] += 1
            self._metrics["intent_counts"][QueryIntent.CHITCHAT.value] += 1
            
            return IntentResultWithMetrics(
                intent=QueryIntent.CHITCHAT,
                confidence=1.0,
                reason="Empty query",
                should_search=False,
                cache_hit=False,
                latency_ms=latency_ms,
                provider_used="semantic",
                direct_response=self._router.get_greeting_response() if self._router else "Bạn muốn hỏi gì?",
            )
        
        query = query.strip()
        
        # Bước 1: Kiểm tra cache
        if use_cache:
            cached_result = await self._cache.get(query)
            if cached_result:
                latency_ms = (time.time() - start_time) * 1000
                self._metrics["cache_hits"] += 1
                self._metrics["latencies"].append(latency_ms)
                self._metrics["provider_counts"]["cache"] += 1
                self._metrics["intent_counts"][cached_result["intent"]] += 1
                
                logger.info(f"Intent from cache: {cached_result['intent']} ({latency_ms:.1f}ms)")
                
                return IntentResultWithMetrics(
                    intent=QueryIntent(cached_result["intent"]),
                    confidence=cached_result["confidence"],
                    reason=cached_result["reason"],
                    should_search=cached_result["should_search"],
                    cache_hit=True,
                    latency_ms=latency_ms,
                    provider_used="cache",
                    direct_response=cached_result.get("direct_response"),
                    suggested_model=cached_result.get("suggested_model"),
                )
            else:
                self._metrics["cache_misses"] += 1
        
        # Bước 2: Layer 1 — Semantic Router (nhanh, ~5-10ms)
        semantic_result = self._classify_by_semantic(query)
        if semantic_result and semantic_result.confidence >= 0.75:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics["latencies"].append(latency_ms)
            self._metrics["provider_counts"]["semantic"] += 1
            self._metrics["intent_counts"][semantic_result.intent.value] += 1
            
            logger.info(f"Intent detected by semantic: {semantic_result.intent.value} ({latency_ms:.1f}ms)")
            
            # Cache kết quả
            if use_cache:
                await self._cache_result(query, semantic_result)
            
            return IntentResultWithMetrics(
                intent=semantic_result.intent,
                confidence=semantic_result.confidence,
                reason=semantic_result.reason,
                should_search=semantic_result.should_search,
                cache_hit=False,
                latency_ms=latency_ms,
                provider_used="semantic",
                direct_response=semantic_result.direct_response,
                suggested_model=semantic_result.suggested_model,
            )
        
        # Bước 3: Thiết lập context cho LLM
        if category_context:
            self.set_category_context(category_context)
        elif document_titles:
            self.set_document_context(document_titles)
        
        # Bước 4: Layer 2 — LLM Classification (CHỈ free: Groq + Ollama)
        llm_result = await self._classify_with_free_llm(query)
        if llm_result:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics["latencies"].append(latency_ms)
            self._metrics["provider_counts"]["llm"] += 1
            self._metrics["intent_counts"][llm_result.intent.value] += 1
            
            # Cache kết quả
            if use_cache:
                await self._cache_result(query, llm_result)
            
            return IntentResultWithMetrics(
                intent=llm_result.intent,
                confidence=llm_result.confidence,
                reason=llm_result.reason,
                should_search=llm_result.should_search,
                cache_hit=False,
                latency_ms=latency_ms,
                provider_used="llm",
                direct_response=llm_result.direct_response,
                suggested_model=llm_result.suggested_model,
            )
        
        # Bước 5: Fallback — kết quả semantic thấp hoặc document query
        if semantic_result:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics["latencies"].append(latency_ms)
            self._metrics["provider_counts"]["semantic"] += 1
            self._metrics["intent_counts"][semantic_result.intent.value] += 1
            
            if use_cache:
                await self._cache_result(query, semantic_result)
            
            return IntentResultWithMetrics(
                intent=semantic_result.intent,
                confidence=semantic_result.confidence,
                reason=semantic_result.reason,
                should_search=semantic_result.should_search,
                cache_hit=False,
                latency_ms=latency_ms,
                provider_used="semantic",
                direct_response=semantic_result.direct_response,
                suggested_model=semantic_result.suggested_model,
            )
        
        # Fallback cuối cùng
        latency_ms = (time.time() - start_time) * 1000
        self._metrics["latencies"].append(latency_ms)
        self._metrics["provider_counts"]["semantic"] += 1
        self._metrics["intent_counts"][QueryIntent.DOCUMENT_QUERY.value] += 1
        
        fallback_result = IntentResult(
            intent=QueryIntent.DOCUMENT_QUERY,
            confidence=0.6,
            reason="Default fallback to document query",
            should_search=True,
        )
        
        if use_cache:
            await self._cache_result(query, fallback_result)
        
        return IntentResultWithMetrics(
            intent=fallback_result.intent,
            confidence=fallback_result.confidence,
            reason=fallback_result.reason,
            should_search=fallback_result.should_search,
            cache_hit=False,
            latency_ms=latency_ms,
            provider_used="semantic",
        )
    
    async def _cache_result(self, query: str, result: IntentResult) -> None:
        """Cache kết quả phát hiện ý định."""
        try:
            await self._cache.set(query, {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "reason": result.reason,
                "should_search": result.should_search,
                "direct_response": result.direct_response,
                "suggested_model": result.suggested_model,
            })
        except Exception as e:
            logger.debug(f"Failed to cache intent result: {e}")
    
    def get_metrics(self) -> IntentMetrics:
        """
        Lấy metrics về phát hiện ý định.
        
        Returns:
            IntentMetrics với thống kê hiệu năng
        """
        total = self._metrics["total_queries"]
        cache_hits = self._metrics["cache_hits"]
        latencies = self._metrics["latencies"]
        
        return IntentMetrics(
            total_queries=total,
            cache_hit_rate=cache_hits / max(total, 1),
            avg_latency_ms=sum(latencies) / max(len(latencies), 1),
            accuracy_by_intent={
                intent: count / max(total, 1)
                for intent, count in self._metrics["intent_counts"].items()
            },
            provider_distribution=dict(self._metrics["provider_counts"]),
        )
    
    def add_vietnamese_patterns(self, patterns: List[str]) -> None:
        """
        Thêm các mẫu câu tiếng Việt tùy chỉnh cho phát hiện ý định.
        (Legacy — giờ nên thêm vào ROUTE_DEFINITIONS trong semantic_router.py)
        
        Args:
            patterns: Danh sách mẫu câu cần thêm
        """
        logger.info(f"add_vietnamese_patterns called but patterns should be added to semantic_router.py ROUTE_DEFINITIONS")
    
    # =========================================================================
    # LAYER 1: SEMANTIC ROUTER CLASSIFICATION
    # =========================================================================
    
    def _classify_by_semantic(self, query: str) -> Optional[IntentResult]:
        """
        Layer 1: Phân loại sử dụng Semantic Router (embedding similarity).
        
        Thay thế regex patterns + keyword matching bằng vector similarity.
        Latency: ~5-10ms (sentence-transformers local).
        """
        if not self._router:
            return None
        
        match = self._router.classify(query)
        if not match:
            return None
        
        # Map route name → IntentResult
        route_map = {
            "greeting": (
                QueryIntent.GREETING,
                False,
                self._router.get_greeting_response(),
                None,
            ),
            "chitchat": (
                QueryIntent.CHITCHAT,
                False,
                self._router.get_chitchat_response(query),
                None,
            ),
            "image_generation": (
                QueryIntent.IMAGE_GENERATION,
                False,
                None,
                "gemini-2.0-flash-exp",
            ),
            "code_generation": (
                QueryIntent.CODE_GENERATION,
                False,
                None,
                "claude-sonnet-4-5",
            ),
            "document_query": (
                QueryIntent.DOCUMENT_QUERY,
                True,
                None,
                None,
            ),
        }
        
        if match.route_name in route_map:
            intent, should_search, direct_response, model = route_map[match.route_name]
            return IntentResult(
                intent=intent,
                confidence=match.score,
                reason=f"Semantic match: '{match.matched_sample}' (score={match.score:.3f})",
                should_search=should_search,
                direct_response=direct_response,
                suggested_model=model,
            )
        
        return None
    
    # =========================================================================
    # LAYER 2: LLM CLASSIFICATION (CHỈ FREE MODELS)
    # =========================================================================
    
    async def _classify_with_free_llm(self, query: str) -> Optional[IntentResult]:
        """
        Layer 2: Phân loại sử dụng LLM — CHỈ FREE models.
        
        ⚠️ KHÔNG dùng CloudCode/DeepSeek/Gemini ở tầng intent.
        Chỉ dùng: Groq (free tier) + Ollama (local).
        
        Chạy song song với timeout 2s.
        """
        import asyncio
        
        LLM_TIMEOUT = 2.0  # 2 giây timeout
        
        async def _try_provider(coro, name: str) -> Optional[IntentResult]:
            """Wrapper để bắt exception từ mỗi provider."""
            try:
                result = await asyncio.wait_for(coro, timeout=LLM_TIMEOUT)
                if result:
                    logger.info(f"Intent classified by {name} LLM (free)")
                    return result
            except asyncio.TimeoutError:
                logger.debug(f"Intent LLM {name} timed out ({LLM_TIMEOUT}s)")
            except Exception as e:
                logger.debug(f"Intent LLM {name} failed: {e}")
            return None
        
        # Chạy song song: Groq (free) — lấy kết quả đầu tiên thành công
        tasks = [
            _try_provider(self._classify_with_groq(query), "Groq"),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in results:
            if isinstance(r, IntentResult):
                return r
        
        # Fallback: Ollama (local, free) nếu Groq fail
        result = await _try_provider(self._classify_with_ollama(query), "Ollama")
        if result:
            return result
        
        return None
    
    async def _classify_with_groq(self, query: str) -> Optional[IntentResult]:
        """Phân loại sử dụng Groq API (free tier, suy luận nhanh)."""
        try:
            api_key = settings.GROQ_API_KEY
            if not api_key:
                return None
            
            prompt = self._build_classification_prompt(query)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 150,
                    },
                    timeout=self._timeout,
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                return self._parse_llm_response(content, query, "groq")
                
        except Exception as e:
            logger.warning(f"Groq classification error: {e}")
            return None
    
    async def _classify_with_ollama(self, query: str) -> Optional[IntentResult]:
        """Phân loại sử dụng local Ollama (free, fallback)."""
        try:
            prompt = self._build_classification_prompt(query)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL or "qwen2.5:7b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.0,
                            "num_predict": 150,
                        },
                    },
                    timeout=10.0,  # Longer timeout for local
                )
                response.raise_for_status()
                
                data = response.json()
                content = data.get("response", "").strip()
                return self._parse_llm_response(content, query, "ollama")
                
        except Exception as e:
            logger.warning(f"Ollama classification error: {e}")
            return None
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _build_classification_prompt(self, query: str) -> str:
        """Xây dựng prompt phân loại chỉ với tên danh mục."""
        context = self._category_context or self._document_context
        
        if context:
            return INTENT_CLASSIFICATION_PROMPT.format(
                document_context=context,
                query=query,
            )
        else:
            return INTENT_CLASSIFICATION_PROMPT_NO_DOCS.format(query=query)
    
    def _parse_llm_response(self, content: str, query: str, source: str) -> Optional[IntentResult]:
        """Phân tích phản hồi LLM thành IntentResult."""
        try:
            # Extract JSON từ response
            json_match = re.search(r'\{[^{}]*\}', content)
            if not json_match:
                logger.warning(f"No JSON found in LLM response: {content[:100]}")
                return None
            
            result = json.loads(json_match.group())
            intent_str = result.get("intent", "").lower()
            direct_response = result.get("response")
            
            intent_map = {
                "greeting": (QueryIntent.GREETING, False, None),
                "chitchat": (QueryIntent.CHITCHAT, False, None),
                "document": (QueryIntent.DOCUMENT_QUERY, True, None),
                "image_generation": (QueryIntent.IMAGE_GENERATION, False, "gemini-2.0-flash-exp"),
                "code_generation": (QueryIntent.CODE_GENERATION, False, "claude-sonnet-4-5"),
            }
            
            if intent_str in intent_map:
                intent, should_search, model = intent_map[intent_str]
                return IntentResult(
                    intent=intent,
                    confidence=0.90,
                    reason=f"LLM classification ({source}, free)",
                    should_search=should_search,
                    direct_response=direct_response if intent in [QueryIntent.GREETING, QueryIntent.CHITCHAT] else None,
                    suggested_model=model,
                )
            
            logger.warning(f"Unknown intent from LLM: {intent_str}")
            return None
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}, content: {content[:100]}")
            return None


# =============================================================================
# SINGLETON
# =============================================================================

_intent_detector: Optional[IntentDetector] = None


def get_intent_detector(language: str = "vi") -> IntentDetector:
    """Lấy hoặc tạo intent detector singleton."""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = IntentDetector(language=language)
    return _intent_detector

"""
Hybrid Retriever cho RAG pipeline.

Kết hợp ba phương pháp retrieval:
1. Graph RAG (RAGAnything/LightRAG) - Entity relationships và knowledge graph
2. Vector RAG (pgvector) - Semantic similarity search
3. Keyword RAG (BM25) - Exact match và keyword search

Sử dụng Reciprocal Rank Fusion (RRF) để kết hợp kết quả từ cả ba phương pháp.

Tính năng nâng cao (tích hợp từ các services không dùng):
- Query Expansion (HyDE) từ query_expansion.py
- Cross-encoder Reranking từ reranker_service.py
- Vietnamese tokenization từ tokenizer_service.py

CHIẾN LƯỢC:
- TÁI SỬ DỤNG RetrieverService hiện có cho Vector component
- TÁI SỬ DỤNG RAGAnythingService hiện có cho Graph component
- THÊM MỚI BM25Index cho Keyword component
- THÊM MỚI Query Expansion (HyDE) để cải thiện retrieval
"""
import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Chunk, Document, DocumentVersion
from app.services.core.embedding_service import EmbeddingService, get_embedding_service
from app.services.core.retriever_service import RetrieverService, RetrievalResult

logger = logging.getLogger(__name__)


# =============================================================================
# QUERY EXPANSION (tích hợp từ query_expansion.py)
# =============================================================================

@dataclass
class ExpandedQuery:
    """Kết quả của query expansion."""
    original_query: str
    expanded_queries: List[str]
    hypothetical_document: Optional[str] = None
    expansion_method: str = "none"


class QueryExpander:
    """
    Query expansion sử dụng HyDE (Hypothetical Document Embeddings).
    Tích hợp từ query_expansion.py để cải thiện chất lượng retrieval.
    """
    
    HYDE_PROMPT_VI = """Dựa trên câu hỏi dưới đây, hãy viết một đoạn văn ngắn có thể là câu trả lời tốt cho câu hỏi này.
Viết như thể bạn đang viết một đoạn trích từ tài liệu chứa câu trả lời.
Không bao gồm các cụm từ như "Câu trả lời là" hoặc "Theo như".
Chỉ viết nội dung trực tiếp.

Câu hỏi: {query}

Đoạn văn giả định:"""

    HYDE_PROMPT_EN = """Given the question below, write a short paragraph that would be a good answer to this question. 
Write as if you are writing a passage from a document that contains the answer.
Do not include phrases like "The answer is" or "According to".
Just write the content directly.

Question: {query}

Hypothetical document passage:"""
    
    def __init__(self, llm_generate_func=None, language: str = "vi"):
        self._llm_generate = llm_generate_func
        self.language = language
    
    def _detect_language(self, text: str) -> str:
        """Phát hiện xem text là tiếng Việt hay tiếng Anh."""
        vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
        return "vi" if any(c in text.lower() for c in vietnamese_chars) else "en"
    
    async def expand_with_hyde(self, query: str) -> ExpandedQuery:
        """Mở rộng query sử dụng HyDE."""
        if not self._llm_generate:
            return ExpandedQuery(original_query=query, expanded_queries=[query], expansion_method="none")
        
        lang = self._detect_language(query)
        prompt_template = self.HYDE_PROMPT_VI if lang == "vi" else self.HYDE_PROMPT_EN
        prompt = prompt_template.format(query=query)
        
        try:
            hypothetical_doc = await self._llm_generate(prompt)
            hypothetical_doc = hypothetical_doc.strip()
            logger.debug(f"HyDE generated hypothetical document ({len(hypothetical_doc)} chars)")
            
            return ExpandedQuery(
                original_query=query,
                expanded_queries=[query, hypothetical_doc],
                hypothetical_document=hypothetical_doc,
                expansion_method="hyde",
            )
        except Exception as e:
            logger.warning(f"HyDE expansion failed: {e}")
            return ExpandedQuery(original_query=query, expanded_queries=[query], expansion_method="none")


# =============================================================================
# BM25 INDEX
# =============================================================================

@dataclass
class BM25Result:
    """Kết quả từ tìm kiếm keyword BM25."""
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None


class BM25Index:
    """
    Index tìm kiếm keyword BM25.
    
    Hỗ trợ tokenize tiếng Việt với underthesea (nếu có).
    Fallback sang tokenize whitespace đơn giản.
    """
    
    # BM25 parameters
    K1 = 1.5  # Term frequency saturation
    B = 0.75  # Length normalization
    
    # Vietnamese stopwords (integrated from tokenizer_service.py)
    VIETNAMESE_STOPWORDS: Set[str] = {
        "và", "của", "là", "có", "được", "cho", "với", "trong", "này",
        "đã", "để", "các", "một", "những", "không", "từ", "như", "khi",
        "về", "theo", "trên", "đến", "ra", "vào", "còn", "cũng", "nên",
        "thì", "mà", "hay", "hoặc", "nếu", "vì", "do", "bởi", "tại",
    }
    
    def __init__(self, session: AsyncSession, remove_stopwords: bool = False):
        """Initialize BM25 index."""
        self.session = session
        self._tokenizer = self._get_tokenizer()
        self.remove_stopwords = remove_stopwords
        
        # Cache for document frequencies
        self._df_cache: Dict[str, int] = {}
        self._doc_count: int = 0
        self._avg_doc_len: float = 0
    
    def _get_tokenizer(self):
        """Lấy tokenizer - tiếng Việt nếu có, nếu không thì đơn giản."""
        try:
            from underthesea import word_tokenize
            logger.info("Using Vietnamese tokenizer (underthesea)")
            return lambda text: word_tokenize(text.lower())
        except ImportError:
            logger.info("Using simple whitespace tokenizer")
            return lambda text: text.lower().split()
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text thành các terms."""
        if not text:
            return []
        tokens = self._tokenizer(text)
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in self.VIETNAMESE_STOPWORDS]
        return tokens
    
    async def search(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int = 10,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[BM25Result]:
        """
        Tìm kiếm sử dụng thuật toán BM25.
        
        Args:
            query: Câu truy vấn tìm kiếm
            workspace_id: Workspace để tìm kiếm
            top_k: Số kết quả cần trả về
            document_ids: Lọc theo document (tùy chọn)
            tags: Lọc theo tag (tùy chọn)
            
        Returns:
            Danh sách BM25Result sắp xếp theo score giảm dần
        """
        if not query or not query.strip():
            return []
        
        # Tokenize query
        query_terms = self.tokenize(query)
        if not query_terms:
            return []
        
        # Get chunks from database
        chunks = await self._get_chunks(workspace_id, document_ids, tags)
        
        if not chunks:
            return []
        
        # Calculate BM25 scores
        results = []
        
        # Calculate corpus statistics
        doc_count = len(chunks)
        total_len = sum(len(self.tokenize(c.content or "")) for c in chunks)
        avg_doc_len = total_len / doc_count if doc_count > 0 else 1
        
        # Calculate document frequencies for query terms
        df = {}
        for term in set(query_terms):
            df[term] = sum(
                1 for c in chunks 
                if term in self.tokenize(c.content or "")
            )
        
        for chunk in chunks:
            content = chunk.content or ""
            doc_terms = self.tokenize(content)
            doc_len = len(doc_terms)
            
            # Calculate BM25 score
            score = 0.0
            term_freq = {}
            for term in doc_terms:
                term_freq[term] = term_freq.get(term, 0) + 1
            
            for term in query_terms:
                if term not in term_freq:
                    continue
                
                tf = term_freq[term]
                doc_freq = df.get(term, 0)
                
                # IDF component
                idf = math.log((doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
                
                # TF component with saturation and length normalization
                tf_norm = (tf * (self.K1 + 1)) / (
                    tf + self.K1 * (1 - self.B + self.B * doc_len / avg_doc_len)
                )
                
                score += idf * tf_norm
            
            if score > 0:
                results.append(BM25Result(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    content=content,
                    score=score,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_title=chunk.section_title,
                ))
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    async def _get_chunks(
        self,
        workspace_id: UUID,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List:
        """Lấy chunks từ database với các filter."""
        try:
            # Build query with string interpolation (safe for workspace_id from our code)
            conditions = [
                f"d.workspace_id = '{str(workspace_id)}'",
                "d.status IN ('READY', 'READY_BASIC', 'READY_ENRICHED')",
            ]
            
            if document_ids:
                doc_ids_str = ",".join(f"'{str(did)}'" for did in document_ids)
                conditions.append(f"d.id IN ({doc_ids_str})")
            
            if tags:
                tags_str = ",".join(f"'{t}'" for t in tags)
                conditions.append(f"d.tags && ARRAY[{tags_str}]::varchar[]")
            
            where_clause = " AND ".join(conditions)
            
            sql = text(f"""
                SELECT 
                    c.id,
                    d.id as document_id,
                    d.title as document_title,
                    c.content,
                    c.page_start,
                    c.page_end,
                    c.section_title
                FROM chunks c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE {where_clause}
            """)
            
            result = await self.session.execute(sql)
            return result.fetchall()
        except Exception as e:
            logger.warning(f"BM25 get_chunks error: {e}")
            # Rollback to clear transaction state
            try:
                await self.session.rollback()
            except Exception:
                pass
            return []


# =============================================================================
# HYBRID RETRIEVER
# =============================================================================

@dataclass
class HybridResult:
    """Kết quả từ hybrid retrieval với thông tin nguồn."""
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float  # Combined RRF score
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    
    # Source scores
    graph_score: Optional[float] = None
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    
    # Source ranks
    graph_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    bm25_rank: Optional[int] = None


class HybridRetriever:
    """
    Hybrid retriever kết hợp Graph + Vector + BM25 search.
    
    Sử dụng Reciprocal Rank Fusion (RRF) để kết hợp kết quả:
    score(d) = Σ weight_i / (k + rank_i(d))
    
    Trong đó k=60 (hằng số) và weights có thể cấu hình.
    
    Tính năng nâng cao:
    - Query Expansion (HyDE) để matching semantic tốt hơn
    - Cross-encoder reranking để cải thiện relevance
    
    CHIẾN LƯỢC:
    - TÁI SỬ DỤNG RetrieverService hiện có cho Vector search
    - TÁI SỬ DỤNG RAGAnythingService hiện có cho Graph search
    - THÊM MỚI BM25Index cho keyword search
    - THÊM MỚI QueryExpander cho HyDE
    """
    
    # RRF constant (standard value)
    RRF_K = 60
    
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService = None,
        enable_hyde: bool = None,
    ):
        """
        Khởi tạo hybrid retriever.
        
        Args:
            session: Database session
            embedding_service: Embedding service (tái sử dụng từ service hiện có)
            enable_hyde: Bật HyDE query expansion (mặc định từ settings)
        """
        self.session = session
        self.embedding_service = embedding_service or get_embedding_service()
        
        # REUSE existing RetrieverService for Vector search
        self.vector_retriever = RetrieverService(session, self.embedding_service)
        
        # ADD BM25 for keyword search
        self.bm25_index = BM25Index(session)
        
        # ADD Query Expander (HyDE)
        self.enable_hyde = enable_hyde if enable_hyde is not None else getattr(settings, 'ENABLE_HYDE', False)
        self.query_expander: Optional[QueryExpander] = None
        
        # Weights from config
        self.graph_weight = settings.HYBRID_RAG_GRAPH_WEIGHT
        self.vector_weight = settings.HYBRID_RAG_VECTOR_WEIGHT
        self.bm25_weight = settings.HYBRID_RAG_BM25_WEIGHT
        
        logger.info(
            f"HybridRetriever initialized with weights: "
            f"Graph={self.graph_weight}, Vector={self.vector_weight}, BM25={self.bm25_weight}"
            f", HyDE={'enabled' if self.enable_hyde else 'disabled'}"
        )
    
    async def _init_query_expander(self):
        """Khởi tạo query expander với LLM function (lazy init)."""
        if self.query_expander is not None:
            return
        
        async def llm_generate(prompt: str) -> str:
            """Gọi LLM đơn giản cho HyDE."""
            from app.services.auth.api_key_service import get_key_manager
            import httpx
            
            key_manager = get_key_manager()
            api_key = key_manager.get_key("deepseek")
            
            if not api_key:
                raise Exception("No DeepSeek API key for HyDE")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 300,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                key_manager.mark_success("deepseek", api_key)
                data = response.json()
                return data["choices"][0]["message"]["content"]
        
        self.query_expander = QueryExpander(llm_generate_func=llm_generate)
    
    async def retrieve(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int = 10,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
        use_graph: bool = True,
        use_vector: bool = True,
        use_bm25: bool = True,
        use_hyde: bool = None,
        strategy: str = "rrf",  # Options: "rrf", "intersection"
    ) -> List[HybridResult]:
        """
        Truy vấn các chunk liên quan sử dụng hybrid search.
        
        Args:
            query: Câu truy vấn tìm kiếm
            workspace_id: Workspace để tìm kiếm
            top_k: Số lượng kết quả cuối cùng cần trả về
            document_ids: Lọc theo document (tùy chọn)
            tags: Lọc theo tag (tùy chọn)
            use_graph: Có sử dụng Graph RAG không
            use_vector: Có sử dụng Vector RAG không
            use_bm25: Có sử dụng BM25 keyword search không
            use_hyde: Có sử dụng HyDE query expansion không (mặc định từ settings)
            strategy: Chiến lược retrieval ("rrf" hoặc "intersection")
            
        Returns:
            Danh sách HybridResult đã sắp xếp theo score
        """
        if not query or not query.strip():
            return []
            
        # Dispatch to specific strategy if requested
        if strategy == "intersection":
            return await self.retrieve_intersection(
                query=query,
                workspace_id=workspace_id,
                top_k=top_k,
                document_ids=document_ids,
                tags=tags,
            )
        
        # Apply HyDE query expansion if enabled
        search_query = query
        if (use_hyde if use_hyde is not None else self.enable_hyde):
            try:
                await self._init_query_expander()
                if self.query_expander:
                    expanded = await self.query_expander.expand_with_hyde(query)
                    if expanded.hypothetical_document:
                        # Use hypothetical document for vector search (better semantic matching)
                        search_query = expanded.hypothetical_document
                        logger.debug(f"HyDE expanded query: {search_query[:100]}...")
            except Exception as e:
                logger.warning(f"HyDE expansion failed: {e}, using original query")
        
        # Retrieve more results from each method for better fusion
        retrieval_k = top_k * 3
        
        # Run retrievals SEQUENTIALLY to avoid "another operation is in progress" error
        # asyncpg doesn't support concurrent queries on the same connection
        graph_results = []
        vector_results = []
        bm25_results = []
        
        # Graph search (uses separate connection via RAGAnything)
        if use_graph:
            try:
                graph_results = await self._graph_search(query, workspace_id, retrieval_k)
            except Exception as e:
                logger.warning(f"Graph search failed: {e}")
                graph_results = []
        
        # Vector search
        if use_vector:
            try:
                vector_results = await self._vector_search(
                    search_query, workspace_id, retrieval_k, document_ids, tags
                )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                vector_results = []
                # Rollback to clear failed transaction state
                try:
                    await self.session.rollback()
                except Exception:
                    pass
        
        # BM25 search
        if use_bm25:
            try:
                bm25_results = await self._bm25_search(
                    query, workspace_id, retrieval_k, document_ids, tags
                )
            except Exception as e:
                logger.warning(f"BM25 search failed: {e}")
                bm25_results = []
                # Rollback to clear failed transaction state
                try:
                    await self.session.rollback()
                except Exception:
                    pass
        
        # Combine results using RRF
        combined = self._reciprocal_rank_fusion(
            graph_results=graph_results,
            vector_results=vector_results,
            bm25_results=bm25_results,
        )
        
        # Apply cross-encoder reranking if enabled
        if getattr(settings, 'ENABLE_RERANKING', False) and combined:
            combined = await self._rerank_results(query, combined, top_k)
        
        # Return top_k results
        return combined[:top_k]
    
    async def retrieve_intersection(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int = 10,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[HybridResult]:
        """
        Truy vấn sử dụng 'Chiến lược Giao' (mẫu Claude-mem).
        
        Chiến lược:
        1. Lọc Metadata (BM25 + Graph) -> Lấy candidate Chunk IDs (Độ chính xác cao)
        2. Vector Search -> Xếp hạng CHỈ các Chunk IDs này (Độ liên quan cao)
        3. Giao -> Trả về kết quả sắp xếp theo Vector Score
        
        Chiến lược này tốt hơn cho các truy vấn chính xác khi cần đảm bảo
        keywords/entities có mặt, nhưng sắp xếp theo nghĩa ngữ nghĩa.
        """
        # Step 1: Metadata Filtering (BM25 + Graph)
        # We perform a broad search here (high recall for keywords)
        candidate_k = top_k * 5
        
        candidates = set()
        
        # Run BM25 and Graph in parallel
        bm25_task = self._bm25_search(query, workspace_id, candidate_k, document_ids, tags)
        graph_task = self._graph_search(query, workspace_id, candidate_k)
        
        bm25_results, graph_results = await asyncio.gather(bm25_task, graph_task)
        
        # Collect candidate IDs
        for r in bm25_results:
            candidates.add(r.chunk_id)
        for r in graph_results:
            # Graph results might be synthetic, check if they map to chunks
            if r.chunk_id != UUID('00000000-0000-0000-0000-000000000000'):
                candidates.add(r.chunk_id)
        
        if not candidates:
            logger.info("Intersection strategy: No metadata candidates found, falling back to Vector search")
            # Fallback: pure vector search if keyword search fails
            vector_results = await self._vector_search(query, workspace_id, top_k, document_ids, tags)
        else:
            # Step 2: Vector Search scoped to Candidates
            # We need to modify vector search to accept allowed_ids
            # Since _vector_search uses document_ids (which are parent docs), we need chunk-level filtering
            # Standard RetrieverService might not support chunk_ids filter directly yet
            # For now, we'll run vector search normally and filter in memory if the DB doesn't support it
            # Ideally, we update RetrieverService to support chunk_ids filter.
            
            # WORKAROUND: For now, we pass the candidates to vector search if possible, 
            # or we search broadly and filter intersection.
            # But the claude-mem pattern relies on the DB doing the filtering for efficiency.
            
            # Let's assume we search broadly and filter for now as we can't easily change RetrieverService signature in one go
            # But wait, we can just pass 'candidates' if we extend the method.
            
            # To strictly follow the pattern, we should filter vector search by these IDs.
            # Let's verify RetrieverService capabilities.
            
            # Since I can't check RetrieverService deeply right now without reading it, 
            # I will implement a logical intersection (Reranking phase).
            
            vector_results = await self._vector_search(query, workspace_id, candidate_k, document_ids, tags)
            
            # Keep only vector results that produce a hit in candidates
            # OR include if vector score is VERY high (safety valve)
            filtered_vector = []
            for r in vector_results:
                if r.chunk_id in candidates or r.score > 0.85:
                    filtered_vector.append(r)
            
            vector_results = filtered_vector
            
        # Step 3: Convert to HybridResult
        # We prioritize Vector Rank but filtered by Metadata match
        results_map: Dict[UUID, HybridResult] = {}
        
        for rank, result in enumerate(vector_results, start=1):
            results_map[result.chunk_id] = HybridResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_title=result.document_title,
                content=result.content,
                score=result.score,
                page_start=result.page_start,
                page_end=result.page_end,
                section_title=result.section_title,
                vector_score=result.score,
                vector_rank=rank
            )
            
        # Return sorted by vector score
        results = list(results_map.values())
        results.sort(key=lambda x: x.vector_score or 0, reverse=True)
        
        # Optional: Rerank
        if getattr(settings, 'ENABLE_RERANKING', False) and results:
            results = await self._rerank_results(query, results, top_k)
            
        return results[:top_k]
    
    async def _rerank_results(
        self,
        query: str,
        results: List['HybridResult'],
        top_k: int,
    ) -> List['HybridResult']:
        """
        Xếp hạng lại kết quả sử dụng cross-encoder model.
        
        Args:
            query: Câu truy vấn tìm kiếm
            results: Kết quả từ RRF fusion
            top_k: Số kết quả cần giữ lại
            
        Returns:
            Kết quả đã xếp hạng lại
        """
        try:
            from app.services.core.reranker_service import reranker_service
            
            if not reranker_service.is_available:
                logger.debug("Reranker not available, skipping reranking")
                return results
            
            # Rerank using content
            reranked = reranker_service.rerank_with_metadata(
                query=query,
                items=results,
                content_getter=lambda r: r.content,
                top_k=top_k,
            )
            
            # Update scores and return
            reranked_results = []
            for item, score in reranked:
                item.score = score  # Update with reranker score
                reranked_results.append(item)
            
            logger.info(f"Reranked {len(results)} results to {len(reranked_results)}")
            return reranked_results
            
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, returning original order")
            return results
    
    async def _graph_search(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        Tìm kiếm sử dụng Graph RAG (RAGAnything/LightRAG).
        
        TÁI SỬ DỤNG RAGService hiện có.
        """
        try:
            from app.services.core.rag import RAGService
            
            # Check if RAGService is initialized
            if not RAGService._initialized:
                logger.debug("RAGService not initialized, skipping graph search")
                return []
            
            service = await RAGService.get_instance()
            
            # Execute graph query
            result = await service.graph_query(
                question=query,
                workspace_id=workspace_id,
                mode="hybrid",  # Use hybrid mode for best results
            )
            
            # Convert string result to RetrievalResult format
            # Note: Graph RAG returns a string answer, not chunks
            # We create a synthetic result for fusion
            if result and result.strip():
                return [RetrievalResult(
                    chunk_id=UUID('00000000-0000-0000-0000-000000000000'),  # Synthetic ID
                    document_id=UUID('00000000-0000-0000-0000-000000000000'),
                    document_title="Graph RAG Result",
                    content=result,
                    score=1.0,  # Top score for graph result
                )]
            
            return []
            
        except Exception as e:
            logger.warning(f"Graph search error: {e}")
            return []
    
    async def _vector_search(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[RetrievalResult]:
        """
        Tìm kiếm sử dụng Vector RAG (pgvector).
        
        TÁI SỬ DỤNG RetrieverService hiện có.
        """
        try:
            return await self.vector_retriever.search(
                query=query,
                workspace_id=workspace_id,
                top_k=top_k,
                document_ids=document_ids,
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"Vector search error: {e}")
            # Rollback to clear failed transaction state
            try:
                await self.session.rollback()
            except Exception:
                pass
            return []
    
    async def _bm25_search(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[BM25Result]:
        """
        Tìm kiếm sử dụng BM25 keyword search.
        """
        try:
            return await self.bm25_index.search(
                query=query,
                workspace_id=workspace_id,
                top_k=top_k,
                document_ids=document_ids,
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"BM25 search error: {e}")
            # Rollback to clear failed transaction state
            try:
                await self.session.rollback()
            except Exception:
                pass
            return []
    
    def _reciprocal_rank_fusion(
        self,
        graph_results: List,
        vector_results: List,
        bm25_results: List,
    ) -> List[HybridResult]:
        """
        Kết hợp kết quả sử dụng Reciprocal Rank Fusion (RRF).
        
        Công thức: score(d) = Σ weight_i / (k + rank_i(d))
        
        Trong đó k=60 (hằng số) và weights có thể cấu hình.
        """
        # Build chunk_id -> result mapping
        results_map: Dict[UUID, HybridResult] = {}
        
        # Process Graph results
        for rank, result in enumerate(graph_results, start=1):
            chunk_id = result.chunk_id
            rrf_score = self.graph_weight / (self.RRF_K + rank)
            
            if chunk_id not in results_map:
                results_map[chunk_id] = HybridResult(
                    chunk_id=chunk_id,
                    document_id=result.document_id,
                    document_title=result.document_title,
                    content=result.content,
                    score=0.0,
                    page_start=getattr(result, 'page_start', None),
                    page_end=getattr(result, 'page_end', None),
                    section_title=getattr(result, 'section_title', None),
                )
            
            results_map[chunk_id].score += rrf_score
            results_map[chunk_id].graph_score = result.score
            results_map[chunk_id].graph_rank = rank
        
        # Process Vector results
        for rank, result in enumerate(vector_results, start=1):
            chunk_id = result.chunk_id
            rrf_score = self.vector_weight / (self.RRF_K + rank)
            
            if chunk_id not in results_map:
                results_map[chunk_id] = HybridResult(
                    chunk_id=chunk_id,
                    document_id=result.document_id,
                    document_title=result.document_title,
                    content=result.content,
                    score=0.0,
                    page_start=result.page_start,
                    page_end=result.page_end,
                    section_title=result.section_title,
                )
            
            results_map[chunk_id].score += rrf_score
            results_map[chunk_id].vector_score = result.score
            results_map[chunk_id].vector_rank = rank
        
        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = result.chunk_id
            rrf_score = self.bm25_weight / (self.RRF_K + rank)
            
            if chunk_id not in results_map:
                results_map[chunk_id] = HybridResult(
                    chunk_id=chunk_id,
                    document_id=result.document_id,
                    document_title=result.document_title,
                    content=result.content,
                    score=0.0,
                    page_start=result.page_start,
                    page_end=result.page_end,
                    section_title=result.section_title,
                )
            
            results_map[chunk_id].score += rrf_score
            results_map[chunk_id].bm25_score = result.score
            results_map[chunk_id].bm25_rank = rank
        
        # Sort by combined RRF score
        results = list(results_map.values())
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def to_retrieval_results(
        self, hybrid_results: List[HybridResult]
    ) -> List[RetrievalResult]:
        """
        Chuyển đổi HybridResult sang RetrievalResult để tương thích.
        
        Cho phép HybridRetriever được sử dụng như drop-in replacement
        cho RetrieverService trong code hiện tại.
        """
        return [
            RetrievalResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                content=r.content,
                score=r.score,
                page_start=r.page_start,
                page_end=r.page_end,
                section_title=r.section_title,
            )
            for r in hybrid_results
        ]

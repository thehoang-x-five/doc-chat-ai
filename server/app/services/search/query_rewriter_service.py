"""
Query Rewriter Service - Multi-query and Step-back Prompting for improved retrieval.

This module provides:
1. Multi-Query Generation: Generate alternative query formulations
2. Step-Back Prompting: Generate broader, conceptual queries for better recall
3. HyDE Integration: Generate hypothetical documents for semantic matching
4. Query Decomposition: Break complex queries into sub-queries

These techniques improve retrieval quality by addressing the "vocabulary mismatch"
problem between user queries and indexed documents.

"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


class RewriteStrategy(Enum):
    """Query rewrite strategies available."""
    MULTI_QUERY = "multi_query"  # Generate alternative formulations
    STEP_BACK = "step_back"  # Generate broader conceptual query
    HYDE = "hyde"  # Generate hypothetical document
    DECOMPOSE = "decompose"  # Break into sub-queries
    ALL = "all"  # Apply all strategies


@dataclass
class RewriteResult:
    """Result of query rewriting."""
    original_query: str
    rewritten_queries: List[str]
    strategy_used: RewriteStrategy
    hypothetical_document: Optional[str] = None
    step_back_query: Optional[str] = None
    sub_queries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryRewriterService:
    """
    Query Rewriter Service for multi-query generation and step-back prompting.
    
    Features:
    - Multi-Query: Generate 3-5 alternative formulations of a query
    - Step-Back: Generate broader, conceptual query for better recall
    - HyDE: Generate hypothetical answer document
    - Decompose: Break complex queries into simpler sub-queries
    
    Usage:
        rewriter = QueryRewriterService(llm_generate_fn=my_llm_fn)
        result = await rewriter.rewrite(
            query="What are the benefits of using RAG?",
            strategy=RewriteStrategy.MULTI_QUERY
        )
        # result.rewritten_queries contains alternative formulations
    """
    
    # Multi-query prompt templates
    MULTI_QUERY_PROMPT_EN = """You are an AI assistant helping to generate alternative search queries.
Given the following question, generate 3 different versions of the question that would retrieve
relevant information from a knowledge base. Focus on different wordings, synonyms, and perspectives.

Original question: {query}

Generate 3 alternative questions (one per line, no numbering):"""

    MULTI_QUERY_PROMPT_VI = """Bạn là trợ lý AI giúp tạo các truy vấn tìm kiếm thay thế.
Dựa trên câu hỏi sau, hãy tạo ra 3 phiên bản khác nhau của câu hỏi để tìm kiếm
thông tin liên quan từ cơ sở kiến thức. Tập trung vào các cách diễn đạt, từ đồng nghĩa
và góc nhìn khác nhau.

Câu hỏi gốc: {query}

Tạo 3 câu hỏi thay thế (mỗi câu một dòng, không đánh số):"""

    # Step-back prompt templates
    STEP_BACK_PROMPT_EN = """You are an AI assistant that helps generate broader, more conceptual questions.
Given a specific question, generate a more general "step-back" question that covers the underlying
concepts or principles. This helps retrieve broader context for answering the original question.

Original question: {query}

Generate ONE broader, more general question that covers the underlying concept:"""

    STEP_BACK_PROMPT_VI = """Bạn là trợ lý AI giúp tạo câu hỏi rộng hơn, mang tính khái niệm hơn.
Dựa trên câu hỏi cụ thể, hãy tạo một câu hỏi "step-back" tổng quát hơn bao quát các
khái niệm hoặc nguyên tắc cơ bản. Điều này giúp truy xuất bối cảnh rộng hơn để trả lời câu hỏi gốc.

Câu hỏi gốc: {query}

Tạo MỘT câu hỏi rộng hơn, tổng quát hơn bao quát khái niệm cơ bản:"""

    # HyDE prompt templates (already in hybrid_retriever_service)
    HYDE_PROMPT_EN = """Given the question, write a detailed paragraph that would answer this question.
The paragraph should be informative and contain relevant technical details.

Question: {query}

Answer paragraph:"""

    HYDE_PROMPT_VI = """Dựa trên câu hỏi, hãy viết một đoạn văn chi tiết trả lời câu hỏi này.
Đoạn văn nên mang tính thông tin và chứa các chi tiết kỹ thuật liên quan.

Câu hỏi: {query}

Đoạn trả lời:"""

    # Decomposition prompt templates
    DECOMPOSE_PROMPT_EN = """You are an AI assistant that breaks down complex questions into simpler sub-questions.
Given a complex question, generate 2-4 simpler questions that, when answered together,
would provide all the information needed to answer the original question.

Complex question: {query}

Generate 2-4 simpler sub-questions (one per line, no numbering):"""

    DECOMPOSE_PROMPT_VI = """Bạn là trợ lý AI phân tách câu hỏi phức tạp thành các câu hỏi con đơn giản hơn.
Dựa trên câu hỏi phức tạp, hãy tạo 2-4 câu hỏi đơn giản hơn mà khi trả lời cùng nhau,
sẽ cung cấp tất cả thông tin cần thiết để trả lời câu hỏi gốc.

Câu hỏi phức tạp: {query}

Tạo 2-4 câu hỏi con đơn giản hơn (mỗi câu một dòng, không đánh số):"""
    
    def __init__(
        self,
        llm_generate_fn: Optional[Callable[[str], str]] = None,
        language: str = "auto",
    ):
        """
        Initialize the Query Rewriter Service.
        
        Args:
            llm_generate_fn: Async function to generate text from LLM.
                            Signature: async (prompt: str) -> str
            language: Language for prompts ("en", "vi", or "auto" for detection)
        """
        self._llm_generate = llm_generate_fn
        self.language = language
        
        logger.info("QueryRewriterService initialized")
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is Vietnamese or English."""
        vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
        return "vi" if any(c in text.lower() for c in vietnamese_chars) else "en"
    
    async def rewrite(
        self,
        query: str,
        strategy: RewriteStrategy = RewriteStrategy.MULTI_QUERY,
        num_variants: int = 3,
    ) -> RewriteResult:
        """
        Rewrite a query using the specified strategy.
        
        Args:
            query: Original query to rewrite
            strategy: Rewriting strategy to use
            num_variants: Number of alternative queries to generate (for MULTI_QUERY)
            
        Returns:
            RewriteResult containing original and rewritten queries
        """
        if not query or not query.strip():
            return RewriteResult(
                original_query=query,
                rewritten_queries=[query] if query else [],
                strategy_used=strategy,
            )
        
        if self._llm_generate is None:
            logger.warning("No LLM function provided, returning original query")
            return RewriteResult(
                original_query=query,
                rewritten_queries=[query],
                strategy_used=strategy,
                metadata={"error": "No LLM function provided"},
            )
        
        # Detect language if auto
        lang = self.language if self.language != "auto" else self._detect_language(query)
        
        try:
            if strategy == RewriteStrategy.ALL:
                return await self._rewrite_all(query, lang, num_variants)
            elif strategy == RewriteStrategy.MULTI_QUERY:
                return await self._rewrite_multi_query(query, lang, num_variants)
            elif strategy == RewriteStrategy.STEP_BACK:
                return await self._rewrite_step_back(query, lang)
            elif strategy == RewriteStrategy.HYDE:
                return await self._rewrite_hyde(query, lang)
            elif strategy == RewriteStrategy.DECOMPOSE:
                return await self._rewrite_decompose(query, lang)
            else:
                logger.warning(f"Unknown strategy {strategy}, using MULTI_QUERY")
                return await self._rewrite_multi_query(query, lang, num_variants)
                
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}")
            return RewriteResult(
                original_query=query,
                rewritten_queries=[query],
                strategy_used=strategy,
                metadata={"error": str(e)},
            )
    
    async def _rewrite_multi_query(
        self,
        query: str,
        lang: str,
        num_variants: int = 3,
    ) -> RewriteResult:
        """Generate multiple alternative query formulations."""
        prompt_template = (
            self.MULTI_QUERY_PROMPT_VI if lang == "vi" else self.MULTI_QUERY_PROMPT_EN
        )
        prompt = prompt_template.format(query=query)
        
        response = await self._llm_generate(prompt)
        
        # Parse response - each line is an alternative query
        alternatives = self._parse_lines(response, max_lines=num_variants)
        
        # Always include original query
        all_queries = [query] + alternatives
        
        return RewriteResult(
            original_query=query,
            rewritten_queries=all_queries,
            strategy_used=RewriteStrategy.MULTI_QUERY,
            metadata={"num_alternatives": len(alternatives)},
        )
    
    async def _rewrite_step_back(
        self,
        query: str,
        lang: str,
    ) -> RewriteResult:
        """Generate a broader, conceptual step-back query."""
        prompt_template = (
            self.STEP_BACK_PROMPT_VI if lang == "vi" else self.STEP_BACK_PROMPT_EN
        )
        prompt = prompt_template.format(query=query)
        
        response = await self._llm_generate(prompt)
        
        step_back_query = response.strip()
        
        # Include both original and step-back query
        all_queries = [query, step_back_query]
        
        return RewriteResult(
            original_query=query,
            rewritten_queries=all_queries,
            strategy_used=RewriteStrategy.STEP_BACK,
            step_back_query=step_back_query,
        )
    
    async def _rewrite_hyde(
        self,
        query: str,
        lang: str,
    ) -> RewriteResult:
        """Generate a hypothetical document for semantic matching."""
        prompt_template = (
            self.HYDE_PROMPT_VI if lang == "vi" else self.HYDE_PROMPT_EN
        )
        prompt = prompt_template.format(query=query)
        
        response = await self._llm_generate(prompt)
        
        hypothetical_doc = response.strip()
        
        # For HyDE, we use the hypothetical document AS the search query
        all_queries = [query, hypothetical_doc]
        
        return RewriteResult(
            original_query=query,
            rewritten_queries=all_queries,
            strategy_used=RewriteStrategy.HYDE,
            hypothetical_document=hypothetical_doc,
        )
    
    async def _rewrite_decompose(
        self,
        query: str,
        lang: str,
    ) -> RewriteResult:
        """Break complex query into simpler sub-queries."""
        prompt_template = (
            self.DECOMPOSE_PROMPT_VI if lang == "vi" else self.DECOMPOSE_PROMPT_EN
        )
        prompt = prompt_template.format(query=query)
        
        response = await self._llm_generate(prompt)
        
        # Parse response - each line is a sub-query
        sub_queries = self._parse_lines(response, max_lines=4)
        
        # Include original plus all sub-queries
        all_queries = [query] + sub_queries
        
        return RewriteResult(
            original_query=query,
            rewritten_queries=all_queries,
            strategy_used=RewriteStrategy.DECOMPOSE,
            sub_queries=sub_queries,
        )
    
    async def _rewrite_all(
        self,
        query: str,
        lang: str,
        num_variants: int = 3,
    ) -> RewriteResult:
        """Apply all rewriting strategies and combine results."""
        # Run all strategies
        multi_result = await self._rewrite_multi_query(query, lang, num_variants)
        step_back_result = await self._rewrite_step_back(query, lang)
        hyde_result = await self._rewrite_hyde(query, lang)
        
        # Combine all unique queries
        all_queries = set([query])
        all_queries.update(multi_result.rewritten_queries)
        all_queries.update(step_back_result.rewritten_queries)
        all_queries.update(hyde_result.rewritten_queries)
        
        # Remove empty queries
        all_queries = [q for q in all_queries if q and q.strip()]
        
        return RewriteResult(
            original_query=query,
            rewritten_queries=list(all_queries),
            strategy_used=RewriteStrategy.ALL,
            hypothetical_document=hyde_result.hypothetical_document,
            step_back_query=step_back_result.step_back_query,
            metadata={
                "strategies_applied": ["multi_query", "step_back", "hyde"],
                "total_queries": len(all_queries),
            },
        )
    
    def _parse_lines(self, text: str, max_lines: int = 5) -> List[str]:
        """Parse response into individual lines, filtering empty and numbered lines."""
        lines = text.strip().split("\n")
        result = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Remove common numbering prefixes
            import re
            line = re.sub(r'^[\d]+[\.\)\-:]\s*', '', line)
            line = re.sub(r'^[-•*]\s*', '', line)
            
            # Skip if line is too short or too long
            if len(line) < 5 or len(line) > 500:
                continue
            
            result.append(line)
            
            if len(result) >= max_lines:
                break
        
        return result


# Default instance (without LLM function - needs to be set before use)
query_rewriter_service = QueryRewriterService()

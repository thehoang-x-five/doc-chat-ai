"""
Memory Manager - Quản lý ngữ cảnh hội thoại.

Triển khai bộ nhớ ngắn hạn (tin nhắn gần đây) và bộ nhớ dài hạn (lịch sử tóm tắt).
SỬ DỤNG LẠI (REUSES) chuỗi LLM provider hiện có từ rag package để tóm tắt.
Được cải tiến với NER, semantic deduplication (khử trùng lặp ngữ nghĩa), và intelligent pruning (cắt tỉa thông minh).
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Thử import spaCy cho NER
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available. Install with: pip install spacy")

# Thử import sentence transformers cho độ tương đồng ngữ nghĩa
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")


@dataclass
class Entity:
    """Thực thể định danh (Named entity) được trích xuất từ văn bản"""
    text: str
    type: str  # "PERSON", "ORG", "LOC", "DATE", etc.
    start: int
    end: int


@dataclass
class FactWithEntities:
    """Fact trong bộ nhớ kèm theo các thực thể đã trích xuất"""
    text: str
    entities: List[Entity]
    importance_score: float
    timestamp: datetime


@dataclass
class PruningResult:
    """Kết quả của thao tác cắt tỉa bộ nhớ"""
    facts_removed: int
    facts_kept: int
    importance_threshold: float
    memory_saved_tokens: int


@dataclass
class MemoryEntry:
    """Một mục bộ nhớ đơn lẻ (tin nhắn hoặc tóm tắt)."""
    role: str  # "user", "assistant", hoặc "summary"
    content: str
    timestamp: datetime
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMemory:
    """Ngữ cảnh bộ nhớ hoàn chỉnh cho một cuộc trò chuyện."""
    conversation_id: UUID
    short_term: List[MemoryEntry]  # Các tin nhắn gần đây
    long_term: Optional[MemoryEntry]  # Lịch sử tóm tắt
    total_tokens: int
    
    def to_context_string(self) -> str:
        """Chuyển đổi bộ nhớ thành chuỗi ngữ cảnh cho LLM prompt."""
        parts = []
        
        # Thêm tóm tắt dài hạn nếu có
        if self.long_term and self.long_term.content:
            parts.append(f"[Previous conversation summary]\n{self.long_term.content}\n")
        
        # Thêm tin nhắn ngắn hạn
        if self.short_term:
            parts.append("[Recent messages]")
            for entry in self.short_term:
                role_label = "User" if entry.role == "user" else "Assistant"
                parts.append(f"{role_label}: {entry.content}")
        
        return "\n".join(parts)


class MemoryManager:
    """
    Quản lý bộ nhớ cuộc trò chuyện với các thành phần ngắn hạn và dài hạn.
    
    Bộ nhớ ngắn hạn: N tin nhắn cuối cùng (có thể cấu hình)
    Bộ nhớ dài hạn: Lịch sử tóm tắt được lưu trong cơ sở dữ liệu
    
    SỬ DỤNG LẠI (REUSES) chuỗi LLM provider hiện có để tóm tắt.
    Được cải tiến với NER, semantic deduplication, và intelligent pruning.
    """
    
    # Cấu hình mặc định
    DEFAULT_SHORT_TERM_MESSAGES = 10  # Giữ 10 tin nhắn cuối
    DEFAULT_TOKEN_BUDGET = 4000  # Số tokens tối đa cho ngữ cảnh bộ nhớ
    DEFAULT_SUMMARY_THRESHOLD = 20  # Tóm tắt sau mỗi 20 tin nhắn
    
    def __init__(
        self,
        session: AsyncSession,
        short_term_messages: int = DEFAULT_SHORT_TERM_MESSAGES,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        summary_threshold: int = DEFAULT_SUMMARY_THRESHOLD,
    ):
        """
        Khởi tạo memory manager.
        
        Args:
            session: Database session
            short_term_messages: Số lượng tin nhắn gần đây cần giữ
            token_budget: Số tokens tối đa cho ngữ cảnh bộ nhớ
            summary_threshold: Số lượng tin nhắn trước khi tóm tắt
        """
        self.session = session
        self.short_term_messages = short_term_messages
        self.token_budget = token_budget
        self.summary_threshold = summary_threshold
        self._llm_provider = None  # Lazy load
        self._nlp = None  # Lazy load spaCy model
        self._embedder = None  # Lazy load sentence transformer

    def _estimate_tokens(self, text: str) -> int:
        """
        Ước tính số lượng token cho văn bản.
        Ước tính đơn giản: ~4 ký tự mỗi token cho tiếng Anh, ~2 cho tiếng Việt.
        """
        # Heuristic đơn giản: trung bình 3 ký tự mỗi token
        return len(text) // 3
    
    def _get_nlp_model(self):
        """Lazy load spaCy NER model"""
        if self._nlp is None and SPACY_AVAILABLE:
            try:
                # Cố gắng load model tiếng Việt trước, fallback về tiếng Anh
                try:
                    self._nlp = spacy.load("vi_core_news_lg")
                except OSError:
                    logger.warning("Vietnamese spaCy model not found, using English model")
                    self._nlp = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.warning(f"Failed to load spaCy model: {e}")
                self._nlp = None
        return self._nlp
    
    def _get_embedder(self):
        """Lazy load sentence transformer cho độ tương đồng ngữ nghĩa"""
        if self._embedder is None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
                self._embedder = None
        return self._embedder
    
    async def extract_facts_with_ner(self, text: str) -> List[FactWithEntities]:
        """
        Trích xuất facts cùng với các thực thể NER.
        
        Args:
            text: Văn bản đầu vào
            
        Returns:
            Danh sách các facts kèm theo thực thể đã trích xuất
        """
        nlp = self._get_nlp_model()
        if not nlp:
            # Fallback: coi toàn bộ văn bản là một fact không có thực thể
            return [FactWithEntities(
                text=text,
                entities=[],
                importance_score=await self.score_fact_importance(text, use_llm=False),
                timestamp=datetime.now()
            )]
        
        try:
            doc = nlp(text)
            facts = []
            
            # Trích xuất các câu thành facts
            for sent in doc.sents:
                entities = []
                for ent in sent.ents:
                    entities.append(Entity(
                        text=ent.text,
                        type=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char
                    ))
                
                # Chấm điểm độ quan trọng
                importance = await self.score_fact_importance(sent.text, use_llm=False)
                
                facts.append(FactWithEntities(
                    text=sent.text.strip(),
                    entities=entities,
                    importance_score=importance,
                    timestamp=datetime.now()
                ))
            
            return facts if facts else [FactWithEntities(
                text=text,
                entities=[],
                importance_score=await self.score_fact_importance(text, use_llm=False),
                timestamp=datetime.now()
            )]
        except Exception as e:
            logger.warning(f"NER extraction failed: {e}")
            return [FactWithEntities(
                text=text,
                entities=[],
                importance_score=await self.score_fact_importance(text, use_llm=False),
                timestamp=datetime.now()
            )]
    
    def deduplicate_facts(
        self, 
        facts: List[str],
        similarity_threshold: float = 0.9
    ) -> List[str]:
        """
        Loại bỏ các facts trùng lặp sử dụng độ tương đồng ngữ nghĩa.
        
        Args:
            facts: Danh sách các fact texts
            similarity_threshold: Ngưỡng tương đồng (mặc định: 0.9)
            
        Returns:
            Danh sách facts đã khử trùng lặp
        """
        if len(facts) <= 1:
            return facts
        
        embedder = self._get_embedder()
        if not embedder:
            # Fallback: khử trùng lặp khớp chính xác đơn giản
            return list(dict.fromkeys(facts))  # Giữ nguyên thứ tự
        
        try:
            # Tính embeddings
            embeddings = embedder.encode(facts)
            
            # Tính độ tương đồng từng cặp
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(embeddings)
            
            # Theo dõi các facts cần giữ lại
            keep = [True] * len(facts)
            
            for i in range(len(facts)):
                if not keep[i]:
                    continue
                for j in range(i + 1, len(facts)):
                    if keep[j] and similarities[i][j] > similarity_threshold:
                        # Đánh dấu trùng lặp để loại bỏ
                        keep[j] = False
            
            return [fact for i, fact in enumerate(facts) if keep[i]]
        except Exception as e:
            logger.warning(f"Semantic deduplication failed: {e}")
            # Fallback về khớp chính xác
            return list(dict.fromkeys(facts))
    
    def prune_memory(self, budget: int) -> PruningResult:
        """
        Cắt tỉa bộ nhớ thông minh để phù hợp với ngân sách (budget).
        
        Đây là placeholder cho logic cắt tỉa sẽ làm việc với các facts đã lưu.
        Trong thực tế, việc này sẽ truy vấn facts từ database, sắp xếp theo
        độ quan trọng, và loại bỏ các facts điểm thấp nhất.
        
        Args:
            budget: Token budget
            
        Returns:
            PruningResult với các thống kê
        """
        # Đây là phiên bản đơn giản hóa - trong production, nó sẽ:
        # 1. Query tất cả facts từ database
        # 2. Sắp xếp theo điểm quan trọng
        # 3. Loại bỏ facts điểm thấp nhất cho đến khi đạt budget
        # 4. Trả về thống kê
        
        return PruningResult(
            facts_removed=0,
            facts_kept=0,
            importance_threshold=0.5,
            memory_saved_tokens=0
        )
    
    async def score_fact_importance(self, fact: str, use_llm: bool = True) -> float:
        """
        Chấm điểm độ quan trọng của một memory fact (0-1).
        
        Pattern từ claude-mem Memory Intelligence Layer.
        
        Args:
            fact: Văn bản memory fact
            use_llm: Nếu True, dùng LLM chấm điểm; ngược lại dùng heuristics
            
        Returns:
            Điểm quan trọng 0.0-1.0
        """
        if use_llm:
            try:
                return await self._score_with_llm(fact)
            except Exception as e:
                logger.warning(f"LLM scoring failed, falling back to heuristics: {e}")
                return self._score_with_heuristics(fact)
        else:
            return self._score_with_heuristics(fact)
    
    async def _score_with_llm(self, fact: str) -> float:
        """
        Sử dụng LLM để chấm điểm độ quan trọng của fact.
        
        Returns:
            Score 0.0-1.0
        """
        llm_provider = await self._get_llm_provider()
        
        prompt = f"""Rate the importance of this memory fact for future conversations on a scale of 0-1.

Fact: "{fact}"

Importance criteria:
- 0.9-1.0: Critical info (user name, role, preferences)
- 0.7-0.8: Important context (project details, decisions)
- 0.5-0.6: Useful info (past questions, general context)
- 0.3-0.4: Minor details (greetings, small talk)
- 0.0-0.2: Trivial (very low value)

Respond with ONLY a number between 0 and 1 (e.g., "0.8")."""
        
        response = await llm_provider.generate(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.3,
        )
        
        if response.success and response.text:
            try:
                score = float(response.text.strip())
                return max(0.0, min(1.0, score))  # Clamp to [0, 1]
            except ValueError:
                logger.warning(f"Invalid LLM score response: {response.text}")
                return 0.5  # Default
        
        return 0.5  # Default
    
    def _score_with_heuristics(self, fact: str) -> float:
        """
        Chấm điểm độ quan trọng của fact sử dụng heuristics đơn giản.
        
        Returns:
            Score 0.0-1.0
        """
        fact_lower = fact.lower()
        score = 0.5  # Default
        
        # Chỉ số quan trọng cao
        if any(keyword in fact_lower for keyword in [
            'name is', 'tên là', 'called', 'work at', 'làm việc tại',
            'role', 'vai trò', 'prefer', 'thích', 'always', 'luôn'
        ]):
            score += 0.3
        
        # Quan trọng trung bình
        if any(keyword in fact_lower for keyword in [
            'project', 'dự án', 'decision', 'quyết định',
            'important', 'quan trọng', 'remember', 'nhớ'
        ]):
            score += 0.2
        
        # Quan trọng thấp
        if any(keyword in fact_lower for keyword in [
            'hello', 'xin chào', 'hi', 'bye', 'tạm biệt',
            'thanks', 'cảm ơn', 'ok', 'okay'
        ]):
            score -= 0.3
        
        # Điều chỉnh dựa trên độ dài (dài hơn = có thể quan trọng hơn)
        if len(fact) > 100:
            score += 0.1
        elif len(fact) < 20:
            score -= 0.1
        
        return max(0.0, min(1.0, score))  # Clamp to [0, 1]
    
    async def _get_llm_provider(self):
        """
        Lấy LLM provider để tóm tắt.
        SỬ DỤNG LẠI (REUSES) provider chain hiện có từ rag_service.py.
        """
        if self._llm_provider is None:
            # Import ở đây để tránh circular imports
            from app.services.core.rag import RAGService
            # Tạo một instance RAGService tối thiểu để truy cập provider chain
            self._llm_provider = await RAGService.get_instance(self.session)
        return self._llm_provider
    
    async def get_memory(
        self,
        conversation_id: UUID,
        include_summary: bool = True,
    ) -> ConversationMemory:
        """
        Lấy ngữ cảnh bộ nhớ cho một cuộc trò chuyện.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            include_summary: Bao gồm tóm tắt dài hạn
            
        Returns:
            ConversationMemory với các thành phần ngắn hạn và dài hạn
        """
        from app.db.models import Message
        
        short_term = []
        long_term = None
        
        # Lấy các tin nhắn gần đây (bộ nhớ ngắn hạn)
        try:
            messages_query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(desc(Message.created_at))
                .limit(self.short_term_messages)
            )
            result = await self.session.execute(messages_query)
            messages = list(result.scalars().all())
            messages.reverse()  # Thứ tự thời gian
            
            for msg in messages:
                token_count = self._estimate_tokens(msg.content)
                short_term.append(MemoryEntry(
                    role=msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                    content=msg.content,
                    timestamp=msg.created_at,
                    token_count=token_count,
                    metadata={
                        "message_id": str(msg.id),
                        "provider": msg.provider,
                        "model": msg.model,
                    }
                ))
        except Exception as e:
            logger.warning(f"Could not load messages for memory: {e}")
            # Trả về memory rỗng khi lỗi
        
        # Lấy tóm tắt dài hạn nếu có và được yêu cầu
        if include_summary:
            try:
                from app.db.models import ConversationSummary
                
                summary_query = (
                    select(ConversationSummary)
                    .where(ConversationSummary.conversation_id == conversation_id)
                    .order_by(desc(ConversationSummary.created_at))
                    .limit(1)
                )
                summary_result = await self.session.execute(summary_query)
                summary = summary_result.scalar_one_or_none()
                
                if summary:
                    long_term = MemoryEntry(
                        role="summary",
                        content=summary.summary_text,
                        timestamp=summary.created_at,
                        token_count=self._estimate_tokens(summary.summary_text),
                        metadata={
                            "summary_id": str(summary.id),
                            "messages_summarized": summary.messages_summarized,
                        }
                    )
            except Exception as e:
                # Bảng có thể chưa tồn tại - chỉ cần bỏ qua tóm tắt
                # Không log lỗi vì điều này được mong đợi trong thiết lập ban đầu
                logger.debug(f"Could not load summary (table may not exist): {e}")
        
        # Tính tổng tokens
        total_tokens = sum(e.token_count for e in short_term)
        if long_term:
            total_tokens += long_term.token_count
        
        return ConversationMemory(
            conversation_id=conversation_id,
            short_term=short_term,
            long_term=long_term,
            total_tokens=total_tokens,
        )
    
    async def should_summarize(self, conversation_id: UUID) -> bool:
        """
        Kiểm tra xem cuộc trò chuyện có nên được tóm tắt hay không.
        
        Trả về True nếu:
        - Số lượng tin nhắn vượt quá ngưỡng
        - Không có tóm tắt gần đây tồn tại
        """
        from app.db.models import Message
        
        try:
            # Đếm số lượng tin nhắn
            count_query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
            )
            result = await self.session.execute(count_query)
            message_count = len(list(result.scalars().all()))
            
            if message_count < self.summary_threshold:
                return False
            
            # Kiểm tra xem tóm tắt gần đây có tồn tại không
            try:
                from app.db.models import ConversationSummary
                
                summary_query = (
                    select(ConversationSummary)
                    .where(ConversationSummary.conversation_id == conversation_id)
                    .order_by(desc(ConversationSummary.created_at))
                    .limit(1)
                )
                summary_result = await self.session.execute(summary_query)
                summary = summary_result.scalar_one_or_none()
                
                if summary:
                    # Tóm tắt nếu có 10+ tin nhắn mới kể từ lần tóm tắt trước
                    new_messages = message_count - summary.messages_summarized
                    return new_messages >= 10
            except Exception as e:
                # Bảng có thể chưa tồn tại - trả về True để thử tóm tắt
                logger.debug(f"Could not check summary status (table may not exist): {e}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking if should summarize: {e}")
            return False

    async def summarize_conversation(
        self,
        conversation_id: UUID,
        force: bool = False,
    ) -> Optional[str]:
        """
        Tóm tắt lịch sử cuộc trò chuyện và lưu vào database.
        SỬ DỤNG LẠI (REUSES) chuỗi LLM provider hiện có để tóm tắt.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            force: Buộc tóm tắt ngay cả khi chưa đạt ngưỡng
            
        Returns:
            Văn bản tóm tắt hoặc None nếu không tóm tắt
        """
        from app.db.models import Message
        
        try:
            if not force and not await self.should_summarize(conversation_id):
                return None
        except Exception as e:
            logger.warning(f"Error checking summarization threshold: {e}")
            if not force:
                return None
        
        try:
            # Lấy tất cả tin nhắn để tóm tắt
            messages_query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            result = await self.session.execute(messages_query)
            messages = list(result.scalars().all())
            
            if not messages:
                return None
            
            # Xây dựng văn bản hội thoại để tóm tắt
            conversation_text = []
            for msg in messages:
                role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                conversation_text.append(f"{role.upper()}: {msg.content}")
            
            full_text = "\n".join(conversation_text)
            
            # Generate summary using existing LLM provider chain
            summary_prompt = f"""Summarize the following conversation, extracting key facts, decisions, and context that would be useful for continuing the conversation later.

CONVERSATION:
{full_text}

SUMMARY (be concise but comprehensive):"""
            
            llm = await self._get_llm_provider()
            # Sử dụng provider chain để tạo tóm tắt
            result = await llm._generate_answer_with_fallback(
                question=summary_prompt,
                context="",
            )
            summary_text = result[0] if result else None
            
            if not summary_text:
                logger.warning(f"Failed to generate summary for conversation {conversation_id}")
                return None
            
            # Lưu tóm tắt vào database
            try:
                from app.db.models import ConversationSummary
                
                summary = ConversationSummary(
                    conversation_id=conversation_id,
                    summary_text=summary_text,
                    messages_summarized=len(messages),
                )
                self.session.add(summary)
                await self.session.commit()
                
                logger.info(f"Created summary for conversation {conversation_id} ({len(messages)} messages)")
                return summary_text
            except Exception as e:
                # Bảng có thể chưa tồn tại - log và trả về tóm tắt dù sao
                logger.warning(f"Could not store summary (table may not exist): {e}")
                try:
                    await self.session.rollback()
                except Exception:
                    pass
                return summary_text
                
        except Exception as e:
            logger.error(f"Error summarizing conversation {conversation_id}: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return None
    
    def truncate_to_budget(
        self,
        memory: ConversationMemory,
        budget: Optional[int] = None,
    ) -> ConversationMemory:
        """
        Cắt bớt bộ nhớ để phù hợp với ngân sách token (token budget).
        
        Chiến lược:
        1. Giữ tóm tắt dài hạn (quan trọng nhất)
        2. Giữ càng nhiều tin nhắn gần đây càng tốt
        3. Cắt bớt tin nhắn cũ nhất trước
        
        Args:
            memory: ConversationMemory cần cắt bớt
            budget: Token budget (sử dụng mặc định nếu không chỉ định)
            
        Returns:
            ConversationMemory đã cắt bớt
        """
        budget = budget or self.token_budget
        
        # Bắt đầu với tokens tóm tắt dài hạn
        used_tokens = 0
        if memory.long_term:
            used_tokens = memory.long_term.token_count
        
        # Nếu chỉ riêng tóm tắt đã vượt quá budget, cắt bớt nó
        if used_tokens > budget:
            if memory.long_term:
                # Cắt tóm tắt để vừa budget
                max_chars = budget * 3  # Ước tính ngược từ token
                truncated_content = memory.long_term.content[:max_chars] + "..."
                memory.long_term = MemoryEntry(
                    role="summary",
                    content=truncated_content,
                    timestamp=memory.long_term.timestamp,
                    token_count=budget,
                    metadata=memory.long_term.metadata,
                )
            return ConversationMemory(
                conversation_id=memory.conversation_id,
                short_term=[],
                long_term=memory.long_term,
                total_tokens=budget,
            )
        
        # Thêm tin nhắn từ mới nhất, dừng khi vượt quá budget
        remaining_budget = budget - used_tokens
        kept_messages = []
        
        # Xử lý từ mới nhất đến cũ nhất
        for entry in reversed(memory.short_term):
            if entry.token_count <= remaining_budget:
                kept_messages.insert(0, entry)  # Chèn vào đầu để giữ nguyên thứ tự
                remaining_budget -= entry.token_count
            else:
                break  # Dừng khi không thể thêm nữa
        
        total_tokens = sum(e.token_count for e in kept_messages)
        if memory.long_term:
            total_tokens += memory.long_term.token_count
        
        return ConversationMemory(
            conversation_id=memory.conversation_id,
            short_term=kept_messages,
            long_term=memory.long_term,
            total_tokens=total_tokens,
        )
    
    async def get_context_for_query(
        self,
        conversation_id: UUID,
        budget: Optional[int] = None,
    ) -> str:
        """
        Lấy chuỗi ngữ cảnh bộ nhớ cho truy vấn RAG.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            budget: Token budget cho ngữ cảnh
            
        Returns:
            Chuỗi context để đưa vào prompt
        """
        memory = await self.get_memory(conversation_id)
        truncated = self.truncate_to_budget(memory, budget)
        return truncated.to_context_string()
    
    async def clear_memory(self, conversation_id: UUID) -> bool:
        """
        Xóa toàn bộ bộ nhớ của một cuộc trò chuyện.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            
        Returns:
            True nếu xóa thành công
        """
        try:
            from app.db.models import ConversationSummary
            
            # Xóa các tóm tắt sử dụng câu lệnh delete đơn giản
            delete_query = (
                select(ConversationSummary)
                .where(ConversationSummary.conversation_id == conversation_id)
            )
            result = await self.session.execute(delete_query)
            summaries = list(result.scalars().all())
            
            for summary in summaries:
                await self.session.delete(summary)
            
            await self.session.commit()
            logger.info(f"Cleared memory for conversation {conversation_id}")
            return True
        except Exception as e:
            # Bảng có thể chưa tồn tại hoặc lỗi khác
            logger.warning(f"Error clearing memory (table may not exist): {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return False

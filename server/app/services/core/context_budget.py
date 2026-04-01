"""
Context Budget Manager giúp phân bổ token thông minh.

Pattern từ AI Engineering best practices:
- Không bao giờ vượt quá context window của LLM
- Ưu tiên thông tin quan trọng nhất
- Phân bổ token hợp lý giữa memory, chunks và lịch sử hội thoại
"""
import logging
from typing import List, Any

logger = logging.getLogger(__name__)


class AllocatedContext:
    """Kết quả phân bổ context budget."""
    def __init__(
        self,
        memory: List[str],
        chunks: List[Any],
        history: List[Any],
        total_tokens: int
    ):
        self.memory = memory
        self.chunks = chunks
        self.history = history
        self.total_tokens = total_tokens


class ContextBudgetManager:
    """Quản lý ngân sách token cho các thành phần context."""
    
    def __init__(self, max_tokens: int = 8000):
        """
        Khởi tạo manager quản lý budget.
        
        Args:
            max_tokens: Số token tối đa cho context (mặc định: 8000)
        """
        self.max_tokens = max_tokens
    
    def allocate_context(
        self,
        query: str,
        memory_facts: List[str],
        retrieved_chunks: List[Any],
        conversation_history: List[Any]
    ) -> AllocatedContext:
        """
        Phân bổ ngân sách token thông minh.
        
        Thứ tự ưu tiên:
        1. Memory facts (20%, tối đa 1000 tokens)
        2. Retrieved chunks (60%, tối đa 4000 tokens)
        3. Lịch sử hội thoại (ngân sách còn lại)
        
        Args:
            query: Câu hỏi người dùng
            memory_facts: Danh sách các sự kiện từ bộ nhớ
            retrieved_chunks: Danh sách chunks tìm được
            conversation_history: Danh sách tin nhắn hội thoại
            
        Returns:
            AllocatedContext chứa các items đã được chọn
        """
        budget = self.max_tokens
        
        # Dành riêng cho query + system prompt (~500 tokens)
        budget -= self._estimate_tokens(query) + 500
        
        logger.debug(f"Tổng budget: {self.max_tokens}, khả dụng: {budget}")
        
        # Ưu tiên 1: Memory (20%, max 1000)
        memory_budget = min(1000, int(budget * 0.2))
        selected_memory = self._select_within_budget(
            memory_facts, memory_budget
        )
        used_memory = sum(self._estimate_tokens(m) for m in selected_memory)
        budget -= used_memory
        
        logger.debug(f"Memory đã cấp: {used_memory} tokens ({len(selected_memory)} facts)")
        
        # Ưu tiên 2: Chunks (60%, max 4000)
        chunk_budget = min(4000, int((self.max_tokens - 500) * 0.6))
        selected_chunks = self._select_within_budget(
            retrieved_chunks, chunk_budget
        )
        used_chunks = sum(self._estimate_tokens(getattr(c, 'content', str(c))) for c in selected_chunks)
        budget -= used_chunks
        
        logger.debug(f"Chunks đã cấp: {used_chunks} tokens ({len(selected_chunks)} chunks)")
        
        # Ưu tiên 3: History (ngân sách còn lại)
        selected_history = self._select_within_budget(
            conversation_history, budget
        )
        used_history = sum(self._estimate_tokens(getattr(m, 'content', str(m))) for m in selected_history)
        
        logger.debug(f"History đã cấp: {used_history} tokens ({len(selected_history)} messages)")
        
        total_used = used_memory + used_chunks + used_history
        
        return AllocatedContext(
            memory=selected_memory,
            chunks=selected_chunks,
            history=selected_history,
            total_tokens=total_used
        )
    
    def _select_within_budget(
        self, items: List[Any], budget: int
    ) -> List[Any]:
        """
        Chọn các items sao cho vừa với ngân sách token.
        
        Args:
            items: Danh sách items (chuỗi hoặc object có content)
            budget: Ngân sách token
            
        Returns:
            Danh sách items được chọn
        """
        if not items:
            return []
        
        selected = []
        used_tokens = 0
        
        for item in items:
            # Lấy nội dung
            if isinstance(item, str):
                content = item
            else:
                content = getattr(item, 'content', str(item))
            
            # Ước lượng token
            tokens = self._estimate_tokens(content)
            
            # Kiểm tra xem có vừa budget không
            if used_tokens + tokens <= budget:
                selected.append(item)
                used_tokens += tokens
            else:
                # Hết budget, dừng lại
                break
        
        return selected
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Ước lượng số token của văn bản.
        
        Quy tắc đơn giản: ~4 ký tự = 1 token
        Có thể dùng tiktoken sau này để chính xác hơn
        
        Args:
            text: Văn bản đầu vào
            
        Returns:
            Số token ước lượng
        """
        if not text:
            return 0
        
        # Ước lượng đơn giản: 1 token ≈ 4 ký tự
        # Cách này tương đối ổn cho cả tiếng Anh và tiếng Việt
        return len(text) // 4


# Singleton instance
_context_budget_manager: ContextBudgetManager = None


def get_context_budget_manager(max_tokens: int = 8000) -> ContextBudgetManager:
    """Lấy hoặc tạo singleton context budget manager."""
    global _context_budget_manager
    if _context_budget_manager is None:
        _context_budget_manager = ContextBudgetManager(max_tokens=max_tokens)
    return _context_budget_manager

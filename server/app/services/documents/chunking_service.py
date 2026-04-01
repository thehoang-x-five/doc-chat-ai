"""
Text chunking service cho pipeline RAG.
Token-based windowing với khả năng cấu hình chunk size và overlap.

Supports:
1. Token-based windowing: Simple fixed-size chunks with overlap
2. Paragraph-based chunking: Chunks by paragraph boundaries
3. Semantic chunking (NEW): Embedding-based boundary detection for improved quality

"""
import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """Chunking strategies available."""
    TOKEN_WINDOW = "token_window"  # Simple token-based windowing
    PARAGRAPH = "paragraph"  # Split by paragraph boundaries
    SEMANTIC = "semantic"  # Embedding-based semantic boundary detection
    HYBRID = "hybrid"  # Combination of paragraph + semantic


@dataclass
class ChunkMetadata:
    """Metadata cho một text chunk."""
    chunk_index: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    bbox_json: Optional[Dict[str, Any]] = None


@dataclass
class TextChunk:
    """Một chunk văn bản kèm metadata."""
    content: str
    token_count: int
    hash: str
    metadata: ChunkMetadata


class ChunkingService:
    """
    Dịch vụ chia nhỏ văn bản (chunking) cho RAG.
    Sử dụng token-based windowing với overlap có thể cấu hình.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Khởi tạo chunking service.
        
        Args:
            chunk_size: Kích thước chunk mục tiêu (theo tokens)
            chunk_overlap: Số lượng tokens chồng lấn giữa các chunks
            min_chunk_size: Kích thước chunk tối thiểu (chunks nhỏ hơn sẽ được gộp)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        # Tokenizer đơn giản (xấp xỉ dựa trên từ)
        # Cho production, nên dùng tiktoken hoặc tương tự
        self._tokenizer = None
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Ước tính số lượng token cho văn bản.
        Sử dụng xấp xỉ dựa trên từ đơn giản (1 từ ≈ 1.3 tokens).
        """
        words = len(text.split())
        return int(words * 1.3)
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize văn bản thành các từ.
        Tokenization đơn giản dựa trên khoảng trắng.
        """
        return text.split()
    
    def _detokenize(self, tokens: List[str]) -> str:
        """Nối các tokens trở lại thành văn bản."""
        return " ".join(tokens)
    
    def _compute_hash(self, text: str) -> str:
        """Tính SHA-256 hash của văn bản để khử trùng lặp."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    def _extract_section_title(self, text: str) -> Optional[str]:
        """
        Trích xuất tiêu đề phần (section title) từ văn bản nếu có.
        Tìm kiếm các markdown headers hoặc dòng viết hoa.
        """
        lines = text.strip().split("\n")
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # Kiểm tra markdown header
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()
        
        # Kiểm tra dòng viết hoa ngắn (khả năng là tiêu đề)
        if len(first_line) < 100 and first_line.isupper():
            return first_line
        
        return None
    
    def chunk_text(
        self,
        text: str,
        page_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[TextChunk]:
        """
        Chia nhỏ văn bản thành các chunks.
        
        Args:
            text: Văn bản đầy đủ cần chunk
            page_info: List tùy chọn các dict thông tin trang với keys 'page' và 'text'
            
        Returns:
            Danh sách các đối tượng TextChunk
        """
        if not text or not text.strip():
            return []
        
        # Làm sạch văn bản
        text = self._clean_text(text)
        
        # Tokenize
        tokens = self._tokenize(text)
        
        if len(tokens) == 0:
            return []
        
        # Nếu văn bản nhỏ hơn chunk size, trả về một chunk duy nhất
        if len(tokens) <= self.chunk_size:
            return [TextChunk(
                content=text,
                token_count=len(tokens),
                hash=self._compute_hash(text),
                metadata=ChunkMetadata(
                    chunk_index=0,
                    page_start=1,
                    page_end=1,
                    section_title=self._extract_section_title(text),
                ),
            )]
        
        # Tạo chunks với overlap
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(tokens):
            # Tính vị trí kết thúc
            end = min(start + self.chunk_size, len(tokens))
            
            # Lấy tokens của chunk
            chunk_tokens = tokens[start:end]
            chunk_text = self._detokenize(chunk_tokens)
            
            # Bỏ qua nếu chunk quá nhỏ (trừ khi là chunk cuối cùng)
            if len(chunk_tokens) < self.min_chunk_size and start + self.chunk_size < len(tokens):
                start += self.chunk_size - self.chunk_overlap
                continue
            
            # Xác định thông tin trang
            page_start, page_end = self._find_page_range(
                chunk_text, page_info
            ) if page_info else (None, None)
            
            # Tạo chunk
            chunk = TextChunk(
                content=chunk_text,
                token_count=len(chunk_tokens),
                hash=self._compute_hash(chunk_text),
                metadata=ChunkMetadata(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    section_title=self._extract_section_title(chunk_text),
                ),
            )
            chunks.append(chunk)
            
            # Di chuyển đến chunk tiếp theo với overlap
            start += self.chunk_size - self.chunk_overlap
            chunk_index += 1
            
            # Ngăn vòng lặp vô hạn
            if start >= len(tokens):
                break
        
        return chunks
    
    def chunk_by_paragraphs(
        self,
        text: str,
        page_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[TextChunk]:
        """
        Chunk văn bản theo đoạn văn (paragraphs), gộp các đoạn nhỏ.
        
        Args:
            text: Văn bản đầy đủ cần chunk
            page_info: Thông tin trang tùy chọn
            
        Returns:
            Danh sách các đối tượng TextChunk
        """
        if not text or not text.strip():
            return []
        
        # Tách theo dòng mới kép (đoạn văn)
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return []
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            
            # Nếu thêm đoạn này vượt quá chunk size
            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                # Lưu chunk hiện tại
                chunks.append(TextChunk(
                    content=current_chunk.strip(),
                    token_count=current_tokens,
                    hash=self._compute_hash(current_chunk.strip()),
                    metadata=ChunkMetadata(
                        chunk_index=chunk_index,
                        section_title=self._extract_section_title(current_chunk),
                    ),
                ))
                chunk_index += 1
                current_chunk = ""
                current_tokens = 0
            
            # Thêm đoạn vào chunk hiện tại
            if current_chunk:
                current_chunk += "\n\n"
            current_chunk += para
            current_tokens += para_tokens
        
        # Đừng quên chunk cuối cùng
        if current_chunk:
            chunks.append(TextChunk(
                content=current_chunk.strip(),
                token_count=current_tokens,
                hash=self._compute_hash(current_chunk.strip()),
                metadata=ChunkMetadata(
                    chunk_index=chunk_index,
                    section_title=self._extract_section_title(current_chunk),
                ),
            ))
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Làm sạch văn bản bằng cách chuẩn hóa khoảng trắng."""
        # Thay thế nhiều khoảng trắng bằng một khoảng trắng
        text = re.sub(r" +", " ", text)
        # Thay thế nhiều dòng mới bằng dòng mới kép
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    
    def _find_page_range(
        self,
        chunk_text: str,
        page_info: List[Dict[str, Any]],
    ) -> tuple:
        """
        Tìm chunk nằm trong những trang nào.
        
        Args:
            chunk_text: Văn bản của chunk
            page_info: Danh sách các dict thông tin trang
            
        Returns:
            Tuple của (page_start, page_end)
        """
        if not page_info:
            return (None, None)
        
        page_start = None
        page_end = None
        
        # Cách tiếp cận đơn giản: tìm trang đầu tiên và cuối cùng chứa văn bản chunk
        chunk_words = set(chunk_text.lower().split()[:10])  # 10 từ đầu tiên
        
        for page in page_info:
            page_text = page.get("text", "").lower()
            page_num = page.get("page", 1)
            
            # Kiểm tra từ chunk có xuất hiện trong trang không
            page_words = set(page_text.split())
            if chunk_words & page_words:  # Giao nhau
                if page_start is None:
                    page_start = page_num
                page_end = page_num
        
        return (page_start or 1, page_end or 1)

    # ========== NEW: Semantic Chunking ==========

    def chunk_semantic(
        self,
        text: str,
        embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
        similarity_threshold: float = 0.5,
        window_size: int = 3,
        page_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[TextChunk]:
        """
        Chunk text using semantic boundary detection.
        
        Uses embedding-based similarity to find natural topic boundaries.
        Sentences with low cosine similarity to their neighbors indicate
        topic changes and are used as chunk boundaries.
        
        Args:
            text: Full text to chunk
            embed_fn: Function to embed a list of sentences.
                      Signature: (sentences: List[str]) -> List[List[float]]
                      If None, falls back to paragraph-based chunking.
            similarity_threshold: Threshold below which to split (lower = more splits)
            window_size: Number of sentences to compare for similarity
            page_info: Optional page information
            
        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []
        
        # Clean text
        text = self._clean_text(text)
        
        # Split into sentences
        sentences = self._split_sentences(text)
        
        if len(sentences) <= 1:
            return self.chunk_text(text, page_info)
        
        # If no embedding function provided, fall back to paragraph chunking
        if embed_fn is None:
            logger.warning(
                "No embedding function provided for semantic chunking. "
                "Falling back to paragraph-based chunking."
            )
            return self.chunk_by_paragraphs(text, page_info)
        
        try:
            # Get embeddings for all sentences
            embeddings = embed_fn(sentences)
            embeddings = np.array(embeddings)
            
            # Calculate similarity between adjacent sentence windows
            boundaries = self._find_semantic_boundaries(
                embeddings=embeddings,
                sentences=sentences,
                similarity_threshold=similarity_threshold,
                window_size=window_size,
            )
            
            # Create chunks from boundaries
            chunks = self._create_chunks_from_boundaries(
                sentences=sentences,
                boundaries=boundaries,
                page_info=page_info,
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}. Falling back to token-based.")
            return self.chunk_text(text, page_info)
    
    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Uses regex-based sentence boundary detection.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Pattern for sentence boundaries
        # Handles: . ! ? followed by space and capital letter
        pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        
        sentences = re.split(pattern, text)
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _find_semantic_boundaries(
        self,
        embeddings: np.ndarray,
        sentences: List[str],
        similarity_threshold: float,
        window_size: int,
    ) -> List[int]:
        """
        Find semantic boundaries using cosine similarity.
        
        Compares windows of sentences and finds points where
        similarity drops below threshold.
        
        Args:
            embeddings: Sentence embeddings as numpy array
            sentences: List of sentences
            similarity_threshold: Minimum similarity to stay in same chunk
            window_size: Number of sentences per window
            
        Returns:
            List of sentence indices where chunks should start
        """
        boundaries = [0]  # Always start with first sentence
        
        if len(sentences) <= window_size * 2:
            return boundaries
        
        for i in range(window_size, len(sentences) - window_size):
            # Get embeddings for left and right windows
            left_window = embeddings[i - window_size:i]
            right_window = embeddings[i:i + window_size]
            
            # Average embeddings for each window
            left_avg = np.mean(left_window, axis=0)
            right_avg = np.mean(right_window, axis=0)
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(left_avg, right_avg)
            
            # If similarity is below threshold, this is a boundary
            if similarity < similarity_threshold:
                # Add boundary if not too close to previous
                if i - boundaries[-1] >= window_size:
                    boundaries.append(i)
        
        return boundaries
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity (0 to 1)
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def _create_chunks_from_boundaries(
        self,
        sentences: List[str],
        boundaries: List[int],
        page_info: Optional[List[Dict[str, Any]]],
    ) -> List[TextChunk]:
        """
        Create TextChunk objects from sentence boundaries.
        
        Args:
            sentences: List of sentences
            boundaries: Indices where chunks start
            page_info: Optional page information
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        
        # Add final boundary if not present
        if len(sentences) not in boundaries:
            boundaries.append(len(sentences))
        
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]
            
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_text = " ".join(chunk_sentences)
            
            # Skip empty chunks
            if not chunk_text.strip():
                continue
            
            # Check size constraints
            token_count = self._estimate_tokens(chunk_text)
            
            # If chunk is too large, split further with token-based
            if token_count > self.chunk_size * 1.5:
                sub_chunks = self.chunk_text(chunk_text, page_info)
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata.chunk_index = len(chunks)
                    chunks.append(sub_chunk)
            else:
                # Determine page range
                page_start, page_end = (
                    self._find_page_range(chunk_text, page_info)
                    if page_info else (None, None)
                )
                
                chunks.append(TextChunk(
                    content=chunk_text,
                    token_count=token_count,
                    hash=self._compute_hash(chunk_text),
                    metadata=ChunkMetadata(
                        chunk_index=len(chunks),
                        page_start=page_start,
                        page_end=page_end,
                        section_title=self._extract_section_title(chunk_text),
                    ),
                ))
        
        return chunks
    
    def chunk_adaptive(
        self,
        text: str,
        strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
        embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
        page_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[TextChunk]:
        """
        Chunk text using adaptive strategy selection.
        
        Automatically selects the best chunking method based on
        text characteristics and available resources.
        
        Args:
            text: Text to chunk
            strategy: Chunking strategy to use
            embed_fn: Optional embedding function for semantic chunking
            page_info: Optional page information
            
        Returns:
            List of TextChunk objects
        """
        if strategy == ChunkingStrategy.TOKEN_WINDOW:
            return self.chunk_text(text, page_info)
        
        elif strategy == ChunkingStrategy.PARAGRAPH:
            return self.chunk_by_paragraphs(text, page_info)
        
        elif strategy == ChunkingStrategy.SEMANTIC:
            return self.chunk_semantic(text, embed_fn, page_info=page_info)
        
        elif strategy == ChunkingStrategy.HYBRID:
            # Try semantic first, fall back to paragraph
            if embed_fn:
                return self.chunk_semantic(text, embed_fn, page_info=page_info)
            else:
                return self.chunk_by_paragraphs(text, page_info)
        
        else:
            logger.warning(f"Unknown strategy {strategy}, using token window")
            return self.chunk_text(text, page_info)


# Default instance
chunking_service = ChunkingService()


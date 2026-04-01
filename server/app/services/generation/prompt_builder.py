"""
Trình Xây dựng Prompt cho các mẫu prompt chuẩn hóa.
Cung cấp cấu trúc prompt nhất quán cho RAG, OCR, so sánh và các tác vụ khác.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Các loại prompt được hỗ trợ."""
    RAG = "rag"
    OCR = "ocr"
    COMPARE = "compare"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    GENERAL = "general"
    CODE = "code"
    IMAGE = "image"
    CHITCHAT = "chitchat"


@dataclass
class Citation:
    """Thông tin trích dẫn cho phản hồi RAG."""
    document_title: str
    page: Optional[int] = None
    score: float = 0.0
    quote: Optional[str] = None
    chunk_id: Optional[str] = None
    
    def to_string(self) -> str:
        """Định dạng trích dẫn thành chuỗi."""
        parts = [f"[{self.document_title}"]
        if self.page:
            parts.append(f", trang {self.page}")
        if self.score > 0:
            parts.append(f", độ tin cậy: {self.score:.0%}")
        parts.append("]")
        return "".join(parts)


@dataclass
class PromptContext:
    """Ngữ cảnh để xây dựng prompt."""
    question: str
    documents: List[Dict[str, Any]] = field(default_factory=list)
    memory_context: Optional[str] = None
    citations: List[Citation] = field(default_factory=list)
    language: str = "vi"  # Mặc định tiếng Việt
    max_tokens: int = 4000
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptBuilder:
    """
    Trình xây dựng prompt chuẩn hóa.
    Hỗ trợ nhiều loại prompt với cấu trúc nhất quán.
    """
    
    # ==========================================================================
    # PROMPT HỆ THỐNG (Vai trò + Mục tiêu + Ràng buộc)
    # ==========================================================================
    
    SYSTEM_PROMPTS = {
        "vi": {
            PromptType.RAG: """Bạn là trợ lý AI hữu ích chuyên trả lời câu hỏi dựa trên tài liệu.

**Vai trò**: Trợ lý nghiên cứu tài liệu
**Mục tiêu**: Trả lời chính xác dựa trên ngữ cảnh được cung cấp
**Ràng buộc**:
- Chỉ sử dụng thông tin từ ngữ cảnh được cung cấp
- Nếu không đủ thông tin, nói rõ điều đó
- Trích dẫn nguồn khi có thể (tài liệu, trang)
- Trả lời ngắn gọn, súc tích""",

            PromptType.OCR: """Bạn là trợ lý AI chuyên xử lý văn bản từ hình ảnh.

**Vai trò**: Chuyên gia OCR và xử lý văn bản
**Mục tiêu**: Trích xuất và cải thiện văn bản từ kết quả OCR
**Ràng buộc**:
- Sửa lỗi chính tả và ngữ pháp
- Giữ nguyên cấu trúc và định dạng
- Không thêm thông tin không có trong văn bản gốc""",

            PromptType.COMPARE: """Bạn là trợ lý AI chuyên so sánh tài liệu.

**Vai trò**: Chuyên gia phân tích so sánh
**Mục tiêu**: Tìm điểm giống và khác nhau giữa các tài liệu
**Ràng buộc**:
- Liệt kê rõ ràng các điểm khác biệt
- Đánh dấu các thay đổi quan trọng
- Giữ tính khách quan""",

            PromptType.EXTRACT: """Bạn là trợ lý AI chuyên trích xuất thông tin.

**Vai trò**: Chuyên gia trích xuất dữ liệu
**Mục tiêu**: Trích xuất thông tin cấu trúc từ văn bản
**Ràng buộc**:
- Chỉ trích xuất thông tin có trong văn bản
- Đánh dấu độ tin cậy cho mỗi trường
- Để trống nếu không tìm thấy thông tin""",

            PromptType.SUMMARIZE: """Bạn là trợ lý AI chuyên tóm tắt tài liệu.

**Vai trò**: Chuyên gia tóm tắt
**Mục tiêu**: Tạo bản tóm tắt ngắn gọn, đầy đủ
**Ràng buộc**:
- Giữ các điểm chính
- Không thêm thông tin mới
- Phù hợp với đối tượng đọc""",

            PromptType.GENERAL: """Bạn là trợ lý AI hữu ích.

**Vai trò**: Trợ lý đa năng
**Mục tiêu**: Hỗ trợ người dùng một cách hiệu quả
**Ràng buộc**:
- Trả lời chính xác và hữu ích
- Thừa nhận khi không biết
- Giữ tính chuyên nghiệp""",

            PromptType.CODE: """Bạn là lập trình viên chuyên nghiệp.

**Vai trò**: Chuyên gia lập trình
**Mục tiêu**: Viết code chất lượng cao, dễ đọc, dễ bảo trì
**Ràng buộc**:
- Code phải chạy được, không có lỗi cú pháp
- Thêm comments giải thích logic quan trọng
- Tuân thủ best practices của ngôn ngữ
- Xử lý edge cases và errors""",

            PromptType.CHITCHAT: """Bạn là trợ lý AI thân thiện.

**Vai trò**: Trợ lý hội thoại
**Mục tiêu**: Trò chuyện tự nhiên, hữu ích
**Ràng buộc**:
- Thân thiện nhưng chuyên nghiệp
- Trả lời ngắn gọn, đúng trọng tâm
- Không bịa đặt thông tin""",
        },
        "en": {
            PromptType.RAG: """You are a helpful AI assistant specialized in answering questions based on documents.

**Role**: Document Research Assistant
**Objective**: Answer accurately based on provided context
**Constraints**:
- Only use information from the provided context
- Clearly state if information is insufficient
- Cite sources when possible (document, page)
- Keep answers concise""",

            PromptType.OCR: """You are an AI assistant specialized in processing text from images.

**Role**: OCR and Text Processing Expert
**Objective**: Extract and improve text from OCR results
**Constraints**:
- Fix spelling and grammar errors
- Preserve structure and formatting
- Do not add information not in the original text""",

            PromptType.COMPARE: """You are an AI assistant specialized in comparing documents.

**Role**: Comparative Analysis Expert
**Objective**: Find similarities and differences between documents
**Constraints**:
- Clearly list differences
- Highlight important changes
- Maintain objectivity""",

            PromptType.EXTRACT: """You are an AI assistant specialized in information extraction.

**Role**: Data Extraction Expert
**Objective**: Extract structured information from text
**Constraints**:
- Only extract information present in the text
- Mark confidence for each field
- Leave blank if information not found""",

            PromptType.SUMMARIZE: """You are an AI assistant specialized in document summarization.

**Role**: Summarization Expert
**Objective**: Create concise, comprehensive summaries
**Constraints**:
- Keep main points
- Do not add new information
- Match target audience""",

            PromptType.GENERAL: """You are a helpful AI assistant.

**Role**: General Assistant
**Objective**: Help users effectively
**Constraints**:
- Answer accurately and helpfully
- Acknowledge when unsure
- Maintain professionalism""",

            PromptType.CODE: """You are a professional software developer.

**Role**: Programming Expert
**Objective**: Write high-quality, readable, maintainable code
**Constraints**:
- Code must be syntactically correct and runnable
- Add comments for important logic
- Follow language best practices
- Handle edge cases and errors""",

            PromptType.CHITCHAT: """You are a friendly AI assistant.

**Role**: Conversational Assistant
**Objective**: Natural, helpful conversation
**Constraints**:
- Friendly but professional
- Concise, on-point answers
- Don't make up information""",
        }
    }

    # ==========================================================================
    # MẪU NGỮ CẢNH
    # ==========================================================================
    
    CONTEXT_TEMPLATES = {
        "vi": {
            PromptType.RAG: """**Ngữ cảnh từ tài liệu:**

{context}

---

**Câu hỏi:** {question}

**Trả lời:**""",

            PromptType.OCR: """**Văn bản OCR cần xử lý:**

{text}

---

**Yêu cầu:** Sửa lỗi và cải thiện văn bản trên.

**Kết quả:**""",

            PromptType.COMPARE: """**Tài liệu 1:**
{doc1}

---

**Tài liệu 2:**
{doc2}

---

**Yêu cầu:** So sánh hai tài liệu trên.

**Phân tích:**""",

            PromptType.EXTRACT: """**Văn bản nguồn:**

{text}

---

**Các trường cần trích xuất:**
{fields}

**Kết quả (JSON):**""",

            PromptType.SUMMARIZE: """**Tài liệu cần tóm tắt:**

{text}

---

**Đối tượng:** {audience}
**Độ dài:** {length}

**Tóm tắt:**""",
        },
        "en": {
            PromptType.RAG: """**Context from documents:**

{context}

---

**Question:** {question}

**Answer:**""",

            PromptType.OCR: """**OCR text to process:**

{text}

---

**Request:** Fix errors and improve the text above.

**Result:**""",

            PromptType.COMPARE: """**Document 1:**
{doc1}

---

**Document 2:**
{doc2}

---

**Request:** Compare the two documents above.

**Analysis:**""",

            PromptType.EXTRACT: """**Source text:**

{text}

---

**Fields to extract:**
{fields}

**Result (JSON):**""",

            PromptType.SUMMARIZE: """**Document to summarize:**

{text}

---

**Audience:** {audience}
**Length:** {length}

**Summary:**""",
        }
    }
    
    def __init__(self, language: str = "vi"):
        """
        Khởi tạo trình xây dựng prompt.
        
        Args:
            language: Ngôn ngữ mặc định (vi hoặc en)
        """
        self.language = language if language in self.SYSTEM_PROMPTS else "vi"
    
    def get_system_prompt(
        self,
        prompt_type: PromptType = PromptType.RAG,
        language: Optional[str] = None,
    ) -> str:
        """
        Lấy prompt hệ thống cho một loại cụ thể.
        
        Args:
            prompt_type: Loại prompt
            language: Ghi đè ngôn ngữ
            
        Returns:
            Chuỗi prompt hệ thống
        """
        lang = language or self.language
        return self.SYSTEM_PROMPTS.get(lang, self.SYSTEM_PROMPTS["vi"]).get(
            prompt_type, self.SYSTEM_PROMPTS[lang][PromptType.GENERAL]
        )
    
    def build_rag_prompt(
        self,
        question: str,
        context: str,
        memory_context: Optional[str] = None,
        citations: Optional[List[Citation]] = None,
        language: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Xây dựng prompt RAG với ngữ cảnh và bộ nhớ tùy chọn.
        
        Args:
            question: Câu hỏi của người dùng
            context: Ngữ cảnh tài liệu đã truy xuất
            memory_context: Bộ nhớ hội thoại tùy chọn
            citations: Danh sách trích dẫn tùy chọn
            language: Ghi đè ngôn ngữ
            
        Returns:
            Tuple của (system_prompt, user_prompt)
        """
        lang = language or self.language
        
        # Xây dựng prompt hệ thống
        system_prompt = self.get_system_prompt(PromptType.RAG, lang)
        
        # Xây dựng ngữ cảnh với bộ nhớ nếu có
        full_context = ""
        if memory_context:
            full_context += f"**Lịch sử hội thoại:**\n{memory_context}\n\n"
        
        full_context += context
        
        # Thêm trích dẫn nếu có
        if citations:
            citation_text = "\n\n**Nguồn tham khảo:**\n"
            for i, cite in enumerate(citations, 1):
                citation_text += f"{i}. {cite.to_string()}\n"
            full_context += citation_text
        
        # Xây dựng prompt người dùng
        template = self.CONTEXT_TEMPLATES.get(lang, self.CONTEXT_TEMPLATES["vi"])[PromptType.RAG]
        user_prompt = template.format(context=full_context, question=question)
        
        return system_prompt, user_prompt
    
    def build_ocr_prompt(
        self,
        text: str,
        language: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Xây dựng prompt cải thiện OCR.
        
        Args:
            text: Văn bản OCR cần cải thiện
            language: Ghi đè ngôn ngữ
            
        Returns:
            Tuple của (system_prompt, user_prompt)
        """
        lang = language or self.language
        system_prompt = self.get_system_prompt(PromptType.OCR, lang)
        template = self.CONTEXT_TEMPLATES.get(lang, self.CONTEXT_TEMPLATES["vi"])[PromptType.OCR]
        user_prompt = template.format(text=text)
        return system_prompt, user_prompt
    
    def build_compare_prompt(
        self,
        doc1: str,
        doc2: str,
        language: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Xây dựng prompt so sánh tài liệu.
        
        Args:
            doc1: Văn bản tài liệu thứ nhất
            doc2: Văn bản tài liệu thứ hai
            language: Ghi đè ngôn ngữ
            
        Returns:
            Tuple của (system_prompt, user_prompt)
        """
        lang = language or self.language
        system_prompt = self.get_system_prompt(PromptType.COMPARE, lang)
        template = self.CONTEXT_TEMPLATES.get(lang, self.CONTEXT_TEMPLATES["vi"])[PromptType.COMPARE]
        user_prompt = template.format(doc1=doc1, doc2=doc2)
        return system_prompt, user_prompt
    
    def build_extract_prompt(
        self,
        text: str,
        fields: List[Dict[str, str]],
        language: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Xây dựng prompt trích xuất.
        
        Args:
            text: Văn bản nguồn
            fields: Danh sách các trường cần trích xuất với mô tả
            language: Ghi đè ngôn ngữ
            
        Returns:
            Tuple của (system_prompt, user_prompt)
        """
        lang = language or self.language
        system_prompt = self.get_system_prompt(PromptType.EXTRACT, lang)
        
        # Định dạng các trường
        fields_text = "\n".join([
            f"- {f.get('name', 'field')}: {f.get('description', '')}"
            for f in fields
        ])
        
        template = self.CONTEXT_TEMPLATES.get(lang, self.CONTEXT_TEMPLATES["vi"])[PromptType.EXTRACT]
        user_prompt = template.format(text=text, fields=fields_text)
        return system_prompt, user_prompt
    
    def build_summarize_prompt(
        self,
        text: str,
        audience: str = "general",
        length: str = "medium",
        language: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Xây dựng prompt tóm tắt.
        
        Args:
            text: Văn bản cần tóm tắt
            audience: Đối tượng mục tiêu (general, technical, executive)
            length: Độ dài tóm tắt (short, medium, long)
            language: Ghi đè ngôn ngữ
            
        Returns:
            Tuple của (system_prompt, user_prompt)
        """
        lang = language or self.language
        system_prompt = self.get_system_prompt(PromptType.SUMMARIZE, lang)
        
        # Dịch audience và length
        audience_map = {
            "vi": {"general": "Đại chúng", "technical": "Kỹ thuật", "executive": "Lãnh đạo"},
            "en": {"general": "General", "technical": "Technical", "executive": "Executive"},
        }
        length_map = {
            "vi": {"short": "Ngắn (1-2 đoạn)", "medium": "Trung bình (3-5 đoạn)", "long": "Dài (chi tiết)"},
            "en": {"short": "Short (1-2 paragraphs)", "medium": "Medium (3-5 paragraphs)", "long": "Long (detailed)"},
        }
        
        audience_text = audience_map.get(lang, audience_map["vi"]).get(audience, audience)
        length_text = length_map.get(lang, length_map["vi"]).get(length, length)
        
        template = self.CONTEXT_TEMPLATES.get(lang, self.CONTEXT_TEMPLATES["vi"])[PromptType.SUMMARIZE]
        user_prompt = template.format(text=text, audience=audience_text, length=length_text)
        return system_prompt, user_prompt
    
    def format_citations(
        self,
        citations: List[Citation],
        style: str = "inline",
    ) -> str:
        """
        Định dạng trích dẫn để hiển thị.
        
        Args:
            citations: Danh sách trích dẫn
            style: Kiểu định dạng (inline, footnote, list)
            
        Returns:
            Chuỗi trích dẫn đã định dạng
        """
        if not citations:
            return ""
        
        if style == "inline":
            return " ".join([cite.to_string() for cite in citations])
        
        elif style == "footnote":
            lines = []
            for i, cite in enumerate(citations, 1):
                lines.append(f"[{i}] {cite.to_string()}")
            return "\n".join(lines)
        
        elif style == "list":
            lines = ["**Nguồn tham khảo:**" if self.language == "vi" else "**References:**"]
            for i, cite in enumerate(citations, 1):
                line = f"{i}. {cite.document_title}"
                if cite.page:
                    line += f", trang {cite.page}" if self.language == "vi" else f", page {cite.page}"
                if cite.quote:
                    line += f'\n   "{cite.quote[:100]}..."' if len(cite.quote) > 100 else f'\n   "{cite.quote}"'
                lines.append(line)
            return "\n".join(lines)
        
        return ""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Ước tính số lượng token cho văn bản.
        
        Args:
            text: Văn bản cần ước tính
            
        Returns:
            Số lượng token ước tính
        """
        # Phương pháp đơn giản: ~3 ký tự mỗi token
        return len(text) // 3

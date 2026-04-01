"""
Dịch vụ cho Tóm tắt Thông minh với Tùy chọn Vai trò/Định dạng.

"""
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.summarize import (
    AUDIENCE_PROMPTS,
    FORMAT_INSTRUCTIONS,
    SummaryAudience,
    SummaryCitation,
    SummaryFormat,
    SummarizeRequest,
    SummaryResult,
)


class SummarizeService:
    """Dịch vụ tạo tóm tắt thông minh với tùy chọn đối tượng/định dạng."""
    
    def __init__(self):
        # Lưu trữ trong bộ nhớ cho demo (thay thế bằng DB trong production)
        self._summaries: Dict[str, SummaryResult] = {}
    
    async def summarize(
        self,
        workspace_id: str,
        request: SummarizeRequest,
        document_texts: Dict[str, Tuple[str, str]],  # {doc_id: (title, text)}
        user_id: Optional[str] = None,
    ) -> SummaryResult:
        """
        Tạo bản tóm tắt cho các tài liệu đã cho.
        
        Args:
            workspace_id: ID không gian làm việc
            request: Yêu cầu tóm tắt với các tùy chọn
            document_texts: Dict ánh xạ doc_id sang tuple (title, text)
            user_id: ID người dùng tùy chọn
            
        Returns:
            SummaryResult với bản tóm tắt đã tạo và trích dẫn
            
        Yêu cầu: 23.1-23.8
        """
        # Kết hợp văn bản tài liệu
        combined_text = ""
        document_titles = []
        for doc_id in request.document_ids:
            if doc_id in document_texts:
                title, text = document_texts[doc_id]
                document_titles.append(title or doc_id)
                combined_text += f"\n\n--- Document: {title or doc_id} ---\n{text}"
        
        if not combined_text.strip():
            raise ValueError("Không tìm thấy nội dung tài liệu")
        
        # Xây dựng prompt
        prompt = self._build_prompt(
            text=combined_text,
            audience=request.audience,
            format=request.format,
            max_length=request.max_length,
            focus_topics=request.focus_topics,
            language=request.language,
        )
        
        # Tạo bản tóm tắt sử dụng AI
        summary_content, citations = await self._generate_summary(
            prompt=prompt,
            document_texts=document_texts,
            include_citations=request.include_citations,
        )
        
        # Định dạng đầu ra theo định dạng được yêu cầu
        formatted_content = self._format_output(
            content=summary_content,
            format=request.format,
        )
        
        # Đếm từ
        word_count = len(formatted_content.split())
        
        # Tạo kết quả
        result_id = str(uuid.uuid4())
        result = SummaryResult(
            id=result_id,
            workspace_id=workspace_id,
            document_ids=request.document_ids,
            document_titles=document_titles,
            audience=request.audience,
            format=request.format,
            language=request.language,
            content=formatted_content,
            citations=citations if request.include_citations else [],
            word_count=word_count,
            focus_topics=request.focus_topics,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )
        
        self._summaries[result_id] = result
        return result

    def _build_prompt(
        self,
        text: str,
        audience: SummaryAudience,
        format: SummaryFormat,
        max_length: Optional[int],
        focus_topics: Optional[List[str]],
        language: str,
    ) -> str:
        """
        Xây dựng prompt tóm tắt dựa trên đối tượng và định dạng.
        Yêu cầu: 23.1, 23.2, 23.5, 23.6, 23.7
        """
        # Lấy hướng dẫn cụ thể theo đối tượng
        audience_prompt = AUDIENCE_PROMPTS.get(audience, AUDIENCE_PROMPTS[SummaryAudience.GENERAL])
        
        # Lấy hướng dẫn cụ thể theo định dạng
        format_prompt = FORMAT_INSTRUCTIONS.get(format, FORMAT_INSTRUCTIONS[SummaryFormat.PARAGRAPH])
        
        # Xây dựng phần chủ đề tập trung
        focus_section = ""
        if focus_topics:
            focus_section = f"\n\nTập trung đặc biệt vào các chủ đề này:\n- " + "\n- ".join(focus_topics)
        
        # Xây dựng ràng buộc độ dài
        length_section = ""
        if max_length:
            length_section = f"\n\nGiữ bản tóm tắt dưới {max_length} từ."
        
        # Xây dựng hướng dẫn ngôn ngữ
        language_section = ""
        if language != "en":
            lang_names = {
                "vi": "Vietnamese",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "fr": "French",
                "de": "German",
                "es": "Spanish",
            }
            lang_name = lang_names.get(language, language)
            language_section = f"\n\nViết bản tóm tắt bằng {lang_name}."
        
        prompt = f"""Bạn là một chuyên gia tóm tắt tài liệu chuyên nghiệp.

{audience_prompt}

{format_prompt}
{focus_section}{length_section}{language_section}

QUAN TRỌNG: Đối với mỗi điểm chính, bao gồm một dấu trích dẫn như [1], [2], v.v. tham chiếu đến phần tài liệu nguồn.

Nội dung Tài liệu:
{text[:15000]}

Tạo bản tóm tắt toàn diện theo các hướng dẫn trên:
"""
        return prompt
    
    async def _generate_summary(
        self,
        prompt: str,
        document_texts: Dict[str, Tuple[str, str]],
        include_citations: bool,
    ) -> Tuple[str, List[SummaryCitation]]:
        """
        Tạo bản tóm tắt bằng cách sử dụng nhà cung cấp AI.
  
        """
        summary_content = ""
        citations = []
        
        # Thử sử dụng nhà cung cấp AI qua DeepSeek
        try:
            from app.services.auth.api_key_service import get_key_manager
            import httpx
            
            key_manager = get_key_manager()
            api_key = key_manager.get_key("deepseek")
            
            if api_key:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7,
                            "max_tokens": 2000,
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    key_manager.mark_success("deepseek", api_key)
                    data = response.json()
                    summary_content = data["choices"][0]["message"]["content"]
        except Exception as e:
            pass
        
        # Dự phòng: tạo bản tóm tắt cơ bản nếu AI thất bại
        if not summary_content:
            summary_content = self._generate_fallback_summary(document_texts)
        
        # Trích xuất trích dẫn từ bản tóm tắt đã tạo
        if include_citations:
            citations = self._extract_citations(summary_content, document_texts)
        
        return summary_content, citations
    
    def _generate_fallback_summary(
        self,
        document_texts: Dict[str, Tuple[str, str]],
    ) -> str:
        """Tạo bản tóm tắt cơ bản khi AI không khả dụng."""
        summaries = []
        for doc_id, (title, text) in document_texts.items():
            # Lấy vài câu đầu tiên
            sentences = text.split('.')[:5]
            excerpt = '. '.join(s.strip() for s in sentences if s.strip())
            if excerpt:
                summaries.append(f"**{title or 'Document'}**: {excerpt}...")
        
        return "\n\n".join(summaries) if summaries else "Không thể tạo bản tóm tắt."
    
    def _extract_citations(
        self,
        summary: str,
        document_texts: Dict[str, Tuple[str, str]],
    ) -> List[SummaryCitation]:
        """
        Trích xuất và xác thực trích dẫn từ bản tóm tắt.
        Yêu cầu: 23.3, 23.4
        """
        citations = []
        
        # Tìm các dấu trích dẫn như [1], [2], v.v.
        citation_pattern = r'\[(\d+)\]'
        markers = re.findall(citation_pattern, summary)
        
        # Đối với mỗi dấu duy nhất, thử tìm văn bản nguồn liên quan
        doc_list = list(document_texts.items())
        seen_markers = set()
        
        for marker in markers:
            if marker in seen_markers:
                continue
            seen_markers.add(marker)
            
            marker_idx = int(marker) - 1
            if 0 <= marker_idx < len(doc_list):
                doc_id, (title, text) = doc_list[marker_idx]
                
                # Tìm đoạn trích liên quan từ tài liệu
                excerpt = self._find_relevant_excerpt(summary, text)
                
                citations.append(SummaryCitation(
                    document_id=doc_id,
                    document_title=title,
                    text_excerpt=excerpt,
                    relevance_score=0.8,
                ))
        
        # Nếu không tìm thấy trích dẫn rõ ràng, tạo trích dẫn từ nội dung tài liệu
        if not citations:
            for doc_id, (title, text) in document_texts.items():
                excerpt = text[:200] + "..." if len(text) > 200 else text
                citations.append(SummaryCitation(
                    document_id=doc_id,
                    document_title=title,
                    text_excerpt=excerpt,
                    relevance_score=0.7,
                ))
        
        return citations
    
    def _find_relevant_excerpt(self, summary: str, document_text: str) -> str:
        """Tìm đoạn trích liên quan từ tài liệu có liên quan đến bản tóm tắt."""
        # Phương pháp đơn giản: tìm từ trùng lặp và trích xuất ngữ cảnh xung quanh
        summary_words = set(summary.lower().split())
        
        sentences = document_text.split('.')
        best_sentence = ""
        best_score = 0
        
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(summary_words & sentence_words)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence.strip()
        
        if best_sentence:
            return best_sentence[:300] + ("..." if len(best_sentence) > 300 else "")
        
        # Dự phòng về phần đầu của tài liệu
        return document_text[:200] + "..."
    
    def _format_output(
        self,
        content: str,
        format: SummaryFormat,
    ) -> str:
        """
        Đảm bảo đầu ra khớp với định dạng được yêu cầu.
        Yêu cầu: 23.2
        """
        # AI nên đã định dạng đúng, nhưng chúng ta có thể làm sạch một chút
        content = content.strip()
        
        if format == SummaryFormat.BULLET:
            # Đảm bảo các điểm đầu dòng được định dạng đúng
            lines = content.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('•', '-', '*', '[')):
                    if not line.startswith('#'):  # Không phải tiêu đề
                        line = f"• {line}"
                formatted_lines.append(line)
            content = '\n'.join(formatted_lines)
        
        elif format == SummaryFormat.CHECKLIST:
            # Đảm bảo định dạng checklist
            lines = content.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('- [', '* [', '[')):
                    if not line.startswith('#'):  # Không phải tiêu đề
                        line = f"- [ ] {line}"
                formatted_lines.append(line)
            content = '\n'.join(formatted_lines)
        
        return content
    
    # =========================================================================
    # CÁC THAO TÁC CRUD
    # =========================================================================
    
    async def get_summary(
        self,
        summary_id: str,
        workspace_id: str,
    ) -> Optional[SummaryResult]:
        """Lấy bản tóm tắt theo ID."""
        summary = self._summaries.get(summary_id)
        if summary and summary.workspace_id == workspace_id:
            return summary
        return None
    
    async def list_summaries(
        self,
        workspace_id: str,
        document_id: Optional[str] = None,
        audience: Optional[SummaryAudience] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[SummaryResult], int]:
        """Liệt kê các bản tóm tắt với bộ lọc tùy chọn."""
        summaries = [
            s for s in self._summaries.values()
            if s.workspace_id == workspace_id
        ]
        
        if document_id:
            summaries = [s for s in summaries if document_id in s.document_ids]
        if audience:
            summaries = [s for s in summaries if s.audience == audience]
        
        # Sắp xếp theo created_at giảm dần
        summaries.sort(key=lambda s: s.created_at, reverse=True)
        
        total = len(summaries)
        return summaries[skip:skip + limit], total
    
    async def delete_summary(
        self,
        summary_id: str,
        workspace_id: str,
    ) -> bool:
        """Xóa bản tóm tắt."""
        summary = await self.get_summary(summary_id, workspace_id)
        if not summary:
            return False
        
        del self._summaries[summary_id]
        return True


# Instance singleton
_summarize_service: Optional[SummarizeService] = None


def get_summarize_service() -> SummarizeService:
    """Lấy hoặc tạo instance SummarizeService."""
    global _summarize_service
    if _summarize_service is None:
        _summarize_service = SummarizeService()
    return _summarize_service

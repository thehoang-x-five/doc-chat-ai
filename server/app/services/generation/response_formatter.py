"""
Trình Định dạng Phản hồi cho định dạng đầu ra chuẩn hóa.
Định dạng kết quả OCR, so sánh, trích xuất, tóm tắt và RAG.
Được tăng cường với streaming SSE, trích dẫn có thể nhấp và chức năng xuất.
"""
import logging
import re
import csv
import io
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union, AsyncGenerator
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# Thử import openpyxl cho xuất Excel
try:
    import openpyxl
    from openpyxl.styles import Font, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    logger.warning("openpyxl không khả dụng. Cài đặt với: pip install openpyxl")


class ResponseType(Enum):
    """Các loại phản hồi được hỗ trợ."""
    OCR = "ocr"
    COMPARE = "compare"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    RAG = "rag"
    TABLE = "table"
    IMAGE = "image"


@dataclass
class FormattedCitation:
    """Trích dẫn đã định dạng để hiển thị."""
    index: int
    document_title: str
    page: Optional[int] = None
    score: float = 0.0
    quote: Optional[str] = None
    highlight_start: int = 0
    highlight_end: int = 0


@dataclass
class FormattedResponse:
    """Định dạng phản hồi chuẩn hóa."""
    response_type: ResponseType
    content: str
    html_content: Optional[str] = None
    citations: List[FormattedCitation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    language: str = "vi"


@dataclass
class FormattedChunk:
    """Chunk streaming cho SSE"""
    content: str
    chunk_index: int
    is_final: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Source:
    """Tài liệu nguồn cho trích dẫn"""
    document_id: str
    document_title: str
    page_number: Optional[int] = None
    matched_quote: str = ""
    url: Optional[str] = None


class ResponseFormatter:
    """
    Trình định dạng cho đầu ra phản hồi chuẩn hóa.
    Hỗ trợ nhiều loại phản hồi với định dạng nhất quán.
    """
    
    def __init__(self, language: str = "vi"):
        """
        Khởi tạo trình định dạng phản hồi.
        
        Args:
            language: Ngôn ngữ mặc định (vi hoặc en)
        """
        self.language = language
    
    # ==========================================================================
    # ĐỊNH DẠNG OCR
    # ==========================================================================
    
    def format_ocr_result(
        self,
        text: str,
        pages: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 1.0,
        include_html: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng kết quả OCR với cấu trúc phù hợp.
        
        Args:
            text: Văn bản đã trích xuất
            pages: Kết quả theo từng trang tùy chọn
            confidence: Điểm tin cậy tổng thể
            include_html: Bao gồm phiên bản định dạng HTML
            
        Returns:
            FormattedResponse với kết quả OCR
        """
        # Làm sạch văn bản
        cleaned_text = self._clean_text(text)
        
        # Xây dựng metadata
        metadata = {
            "char_count": len(cleaned_text),
            "word_count": len(cleaned_text.split()),
            "page_count": len(pages) if pages else 1,
        }
        
        # Tạo HTML nếu được yêu cầu
        html_content = None
        if include_html:
            html_content = self._text_to_html(cleaned_text)
        
        return FormattedResponse(
            response_type=ResponseType.OCR,
            content=cleaned_text,
            html_content=html_content,
            metadata=metadata,
            confidence=confidence,
            language=self.language,
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG SO SÁNH
    # ==========================================================================
    
    def format_compare_result(
        self,
        analysis: str,
        differences: Optional[List[Dict[str, Any]]] = None,
        similarity_score: float = 0.0,
        include_html: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng kết quả so sánh với các dấu diff.
        
        Args:
            analysis: Văn bản phân tích so sánh
            differences: Danh sách các điểm khác biệt cụ thể
            similarity_score: Độ tương đồng tổng thể (0-1)
            include_html: Bao gồm phiên bản định dạng HTML
            
        Returns:
            FormattedResponse với kết quả so sánh
        """
        # Xây dựng nội dung với các điểm khác biệt
        content_parts = [analysis]
        
        if differences:
            diff_section = "\n\n**Các điểm khác biệt:**\n" if self.language == "vi" else "\n\n**Differences:**\n"
            for i, diff in enumerate(differences, 1):
                diff_type = diff.get("type", "change")
                location = diff.get("location", "")
                old_value = diff.get("old", "")
                new_value = diff.get("new", "")
                
                if diff_type == "added":
                    diff_section += f"{i}. ➕ Thêm mới: {new_value}\n"
                elif diff_type == "removed":
                    diff_section += f"{i}. ➖ Đã xóa: {old_value}\n"
                else:
                    diff_section += f"{i}. 🔄 Thay đổi ({location}): '{old_value}' → '{new_value}'\n"
            
            content_parts.append(diff_section)
        
        content = "".join(content_parts)
        
        # Xây dựng metadata
        metadata = {
            "similarity_score": similarity_score,
            "difference_count": len(differences) if differences else 0,
        }
        
        # Tạo HTML nếu được yêu cầu
        html_content = None
        if include_html:
            html_content = self._markdown_to_html(content)
        
        return FormattedResponse(
            response_type=ResponseType.COMPARE,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=similarity_score,
            language=self.language,
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG TRÍCH XUẤT
    # ==========================================================================
    
    def format_extract_result(
        self,
        fields: List[Dict[str, Any]],
        source_text: Optional[str] = None,
        include_html: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng kết quả trích xuất với nhãn trường.
        
        Args:
            fields: Danh sách các trường đã trích xuất với giá trị và độ tin cậy
            source_text: Văn bản nguồn tùy chọn
            include_html: Bao gồm phiên bản định dạng HTML
            
        Returns:
            FormattedResponse với kết quả trích xuất
        """
        # Xây dựng nội dung
        content_parts = []
        total_confidence = 0.0
        extracted_count = 0
        
        for field in fields:
            name = field.get("name", "field")
            value = field.get("value", "")
            confidence = field.get("confidence", 1.0)
            status = field.get("status", "extracted")
            
            if status == "extracted" and value:
                content_parts.append(f"**{name}**: {value}")
                total_confidence += confidence
                extracted_count += 1
            elif status == "not_found":
                content_parts.append(f"**{name}**: _(không tìm thấy)_" if self.language == "vi" else f"**{name}**: _(not found)_")
            elif status == "needs_review":
                content_parts.append(f"**{name}**: {value} ⚠️ _(cần xem xét)_" if self.language == "vi" else f"**{name}**: {value} ⚠️ _(needs review)_")
        
        content = "\n".join(content_parts)
        
        # Tính độ tin cậy trung bình
        avg_confidence = total_confidence / extracted_count if extracted_count > 0 else 0.0
        
        # Xây dựng metadata
        metadata = {
            "fields_total": len(fields),
            "fields_extracted": extracted_count,
            "fields_not_found": sum(1 for f in fields if f.get("status") == "not_found"),
            "fields_need_review": sum(1 for f in fields if f.get("status") == "needs_review"),
        }
        
        # Tạo HTML nếu được yêu cầu
        html_content = None
        if include_html:
            html_content = self._markdown_to_html(content)
        
        return FormattedResponse(
            response_type=ResponseType.EXTRACT,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=avg_confidence,
            language=self.language,
        )

    # ==========================================================================
    # ĐỊNH DẠNG TÓM TẮT
    # ==========================================================================
    
    def format_summary_result(
        self,
        summary: str,
        key_points: Optional[List[str]] = None,
        word_count: Optional[int] = None,
        include_html: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng kết quả tóm tắt với các phần và điểm nổi bật.
        
        Args:
            summary: Văn bản tóm tắt
            key_points: Danh sách các điểm chính tùy chọn
            word_count: Số từ của bản tóm tắt
            include_html: Bao gồm phiên bản định dạng HTML
            
        Returns:
            FormattedResponse với kết quả tóm tắt
        """
        content_parts = [summary]
        
        if key_points:
            points_header = "\n\n**Điểm chính:**\n" if self.language == "vi" else "\n\n**Key Points:**\n"
            content_parts.append(points_header)
            for point in key_points:
                content_parts.append(f"• {point}\n")
        
        content = "".join(content_parts)
        
        # Xây dựng metadata
        metadata = {
            "word_count": word_count or len(summary.split()),
            "key_points_count": len(key_points) if key_points else 0,
        }
        
        # Tạo HTML nếu được yêu cầu
        html_content = None
        if include_html:
            html_content = self._markdown_to_html(content)
        
        return FormattedResponse(
            response_type=ResponseType.SUMMARIZE,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=1.0,
            language=self.language,
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG PHẢN HỒI RAG
    # ==========================================================================
    
    def format_rag_response(
        self,
        answer: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 1.0,
        include_html: bool = True,
        highlight_quotes: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng phản hồi RAG với trích dẫn và trích dẫn được làm nổi bật.
        
        Args:
            answer: Câu trả lời được tạo
            citations: Danh sách các dict trích dẫn
            confidence: Độ tin cậy tổng thể
            include_html: Bao gồm phiên bản định dạng HTML
            highlight_quotes: Làm nổi bật văn bản được trích dẫn
            
        Returns:
            FormattedResponse với kết quả RAG
        """
        # Xử lý trích dẫn
        formatted_citations = []
        if citations:
            for i, cite in enumerate(citations, 1):
                formatted_citations.append(FormattedCitation(
                    index=i,
                    document_title=cite.get("document_title", cite.get("title", "Unknown")),
                    page=cite.get("page"),
                    score=cite.get("score", 0.0),
                    quote=cite.get("quote"),
                ))
        
        # Xây dựng nội dung với trích dẫn nội tuyến
        content = answer
        if formatted_citations:
            citation_section = "\n\n---\n**Nguồn tham khảo:**\n" if self.language == "vi" else "\n\n---\n**References:**\n"
            for cite in formatted_citations:
                cite_line = f"[{cite.index}] {cite.document_title}"
                if cite.page:
                    cite_line += f", trang {cite.page}" if self.language == "vi" else f", page {cite.page}"
                if cite.score > 0:
                    cite_line += f" (độ tin cậy: {cite.score:.0%})" if self.language == "vi" else f" (confidence: {cite.score:.0%})"
                citation_section += cite_line + "\n"
            content += citation_section
        
        # Xây dựng metadata
        metadata = {
            "citation_count": len(formatted_citations),
            "has_citations": len(formatted_citations) > 0,
            "answer_length": len(answer),
        }
        
        # Tạo HTML nếu được yêu cầu
        html_content = None
        if include_html:
            html_content = self._markdown_to_html(content)
            if highlight_quotes and formatted_citations:
                html_content = self._highlight_quotes(html_content, formatted_citations)
        
        return FormattedResponse(
            response_type=ResponseType.RAG,
            content=content,
            html_content=html_content,
            citations=formatted_citations,
            metadata=metadata,
            confidence=confidence,
            language=self.language,
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG BẢNG
    # ==========================================================================
    
    def format_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        title: Optional[str] = None,
        include_html: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng bảng dưới dạng JSON + HTML.
        
        Args:
            headers: Tiêu đề cột
            rows: Các hàng của bảng
            title: Tiêu đề bảng tùy chọn
            include_html: Bao gồm phiên bản định dạng HTML
            
        Returns:
            FormattedResponse với bảng
        """
        # Xây dựng bảng markdown
        content_parts = []
        if title:
            content_parts.append(f"**{title}**\n\n")
        
        # Hàng tiêu đề
        content_parts.append("| " + " | ".join(headers) + " |")
        content_parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Các hàng dữ liệu
        for row in rows:
            content_parts.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        content = "\n".join(content_parts)
        
        # Xây dựng metadata với biểu diễn JSON
        metadata = {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers),
        }
        
        # Tạo bảng HTML
        html_content = None
        if include_html:
            html_parts = ['<table class="formatted-table">']
            if title:
                html_parts.append(f'<caption>{title}</caption>')
            html_parts.append('<thead><tr>')
            for header in headers:
                html_parts.append(f'<th>{header}</th>')
            html_parts.append('</tr></thead>')
            html_parts.append('<tbody>')
            for row in rows:
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(f'<td>{cell}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody></table>')
            html_content = "".join(html_parts)
        
        return FormattedResponse(
            response_type=ResponseType.TABLE,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=1.0,
            language=self.language,
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG ẢNH
    # ==========================================================================
    
    def format_image_metadata(
        self,
        image_url: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        alt_text: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> FormattedResponse:
        """
        Định dạng ảnh với metadata.
        
        Args:
            image_url: URL hoặc đường dẫn đến ảnh
            width: Chiều rộng ảnh
            height: Chiều cao ảnh
            alt_text: Văn bản thay thế
            caption: Chú thích ảnh
            
        Returns:
            FormattedResponse với metadata ảnh
        """
        # Xây dựng markdown
        alt = alt_text or "Image"
        content = f"![{alt}]({image_url})"
        if caption:
            content += f"\n*{caption}*"
        
        # Xây dựng metadata
        metadata = {
            "url": image_url,
            "width": width,
            "height": height,
            "alt_text": alt_text,
            "caption": caption,
        }
        
        # Tạo HTML
        html_parts = ['<figure class="formatted-image">']
        img_attrs = [f'src="{image_url}"']
        if alt_text:
            img_attrs.append(f'alt="{alt_text}"')
        if width:
            img_attrs.append(f'width="{width}"')
        if height:
            img_attrs.append(f'height="{height}"')
        html_parts.append(f'<img {" ".join(img_attrs)} />')
        if caption:
            html_parts.append(f'<figcaption>{caption}</figcaption>')
        html_parts.append('</figure>')
        html_content = "".join(html_parts)
        
        return FormattedResponse(
            response_type=ResponseType.IMAGE,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=1.0,
            language=self.language,
        )
    
    # ==========================================================================
    # HỖ TRỢ STREAMING (SSE)
    # ==========================================================================
    
    async def format_streaming(
        self,
        response_type: str,
        content_generator: AsyncGenerator[str, None],
        chunk_interval_ms: int = 100
    ) -> AsyncGenerator[FormattedChunk, None]:
        """
        Định dạng phản hồi với hỗ trợ streaming sử dụng SSE.
        
        Args:
            response_type: Loại phản hồi
            content_generator: Trình tạo async tạo ra các chunk nội dung
            chunk_interval_ms: Khoảng thời gian giữa các chunk tính bằng mili giây
            
        Yields:
            Các đối tượng FormattedChunk để streaming
        """
        chunk_index = 0
        accumulated_content = ""
        
        async for content_chunk in content_generator:
            accumulated_content += content_chunk
            chunk_index += 1
            
            yield FormattedChunk(
                content=content_chunk,
                chunk_index=chunk_index,
                is_final=False,
                metadata={
                    "response_type": response_type,
                    "accumulated_length": len(accumulated_content)
                }
            )
            
            # Đợi khoảng thời gian
            await asyncio.sleep(chunk_interval_ms / 1000.0)
        
        # Gửi chunk cuối cùng
        yield FormattedChunk(
            content="",
            chunk_index=chunk_index + 1,
            is_final=True,
            metadata={
                "response_type": response_type,
                "total_length": len(accumulated_content),
                "total_chunks": chunk_index
            }
        )
    
    # ==========================================================================
    # ĐỊNH DẠNG TRÍCH DẪN NÂNG CAO
    # ==========================================================================
    
    def format_citations(
        self,
        text: str,
        sources: List[Source]
    ) -> str:
        """
        Định dạng trích dẫn với liên kết có thể nhấp và trích dẫn được làm nổi bật.
        
        Args:
            text: Văn bản phản hồi
            sources: Danh sách tài liệu nguồn
            
        Returns:
            Văn bản với trích dẫn đã định dạng
        """
        if not sources:
            return text
        
        # Thêm các dấu trích dẫn nội tuyến
        formatted_text = text
        
        # Thêm phần trích dẫn
        citation_section = "\n\n---\n**Nguồn tham khảo:**\n" if self.language == "vi" else "\n\n---\n**References:**\n"
        
        for i, source in enumerate(sources, 1):
            cite_line = f"[{i}] "
            
            # Thêm liên kết có thể nhấp nếu có URL
            if source.url:
                cite_line += f"[{source.document_title}]({source.url})"
            else:
                cite_line += source.document_title
            
            # Thêm số trang
            if source.page_number:
                cite_line += f", trang {source.page_number}" if self.language == "vi" else f", page {source.page_number}"
            
            # Thêm trích dẫn khớp nếu có
            if source.matched_quote:
                quote_preview = source.matched_quote[:100] + "..." if len(source.matched_quote) > 100 else source.matched_quote
                cite_line += f'\n   > "{quote_preview}"'
            
            citation_section += cite_line + "\n\n"
        
        return formatted_text + citation_section
    
    # ==========================================================================
    # CHỨC NĂNG XUẤT BẢNG
    # ==========================================================================
    
    def format_table_export(
        self,
        table_data: List[List[str]],
        format: str = "csv"
    ) -> bytes:
        """
        Xuất bảng sang định dạng CSV hoặc Excel.
        
        Args:
            table_data: Dữ liệu bảng (hàng đầu tiên là tiêu đề)
            format: Định dạng xuất ("csv" hoặc "excel")
            
        Returns:
            Bytes của tệp đã xuất
        """
        if format.lower() == "csv":
            return self._export_to_csv(table_data)
        elif format.lower() in ["excel", "xlsx"]:
            return self._export_to_excel(table_data)
        else:
            raise ValueError(f"Định dạng xuất không được hỗ trợ: {format}")
    
    def _export_to_csv(self, table_data: List[List[str]]) -> bytes:
        """Xuất bảng sang định dạng CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        for row in table_data:
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')
    
    def _export_to_excel(self, table_data: List[List[str]]) -> bytes:
        """Xuất bảng sang định dạng Excel"""
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl là bắt buộc để xuất Excel. Cài đặt với: pip install openpyxl")
        
        # Tạo workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Export"
        
        # Ghi dữ liệu
        for row_idx, row in enumerate(table_data, 1):
            for col_idx, cell_value in enumerate(row, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
                
                # Định dạng hàng tiêu đề
                if row_idx == 1:
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')
        
        # Tự động điều chỉnh độ rộng cột
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Lưu thành bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.read()
    
    # ==========================================================================
    # METADATA ẢNH VỚI LAZY LOADING
    # ==========================================================================
    
    def format_image_with_lazy_loading(
        self,
        image_url: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        alt_text: Optional[str] = None,
        caption: Optional[str] = None,
        lazy_load: bool = True,
        responsive: bool = True,
    ) -> FormattedResponse:
        """
        Định dạng ảnh với lazy loading và metadata kích thước responsive.
        
        Args:
            image_url: URL hoặc đường dẫn đến ảnh
            width: Chiều rộng ảnh
            height: Chiều cao ảnh
            alt_text: Văn bản thay thế
            caption: Chú thích ảnh
            lazy_load: Bật lazy loading
            responsive: Bật kích thước responsive
            
        Returns:
            FormattedResponse với metadata ảnh nâng cao
        """
        # Xây dựng markdown
        alt = alt_text or "Image"
        content = f"![{alt}]({image_url})"
        if caption:
            content += f"\n*{caption}*"
        
        # Xây dựng metadata với thông tin lazy loading và responsive
        metadata = {
            "url": image_url,
            "width": width,
            "height": height,
            "alt_text": alt_text,
            "caption": caption,
            "lazy_load": lazy_load,
            "responsive": responsive,
            "loading_strategy": "lazy" if lazy_load else "eager",
            "sizes": self._generate_responsive_sizes(width) if responsive and width else None,
        }
        
        # Tạo HTML với lazy loading
        html_parts = ['<figure class="formatted-image">']
        img_attrs = [f'src="{image_url}"']
        
        if alt_text:
            img_attrs.append(f'alt="{alt_text}"')
        
        if lazy_load:
            img_attrs.append('loading="lazy"')
        
        if responsive:
            img_attrs.append('style="max-width: 100%; height: auto;"')
        elif width and height:
            img_attrs.append(f'width="{width}" height="{height}"')
        
        html_parts.append(f'<img {" ".join(img_attrs)} />')
        
        if caption:
            html_parts.append(f'<figcaption>{caption}</figcaption>')
        
        html_parts.append('</figure>')
        html_content = "".join(html_parts)
        
        return FormattedResponse(
            response_type=ResponseType.IMAGE,
            content=content,
            html_content=html_content,
            metadata=metadata,
            confidence=1.0,
            language=self.language,
        )
    
    def _generate_responsive_sizes(self, base_width: int) -> Dict[str, int]:
        """Tạo kích thước ảnh responsive"""
        return {
            "small": base_width // 4,
            "medium": base_width // 2,
            "large": base_width,
            "xlarge": int(base_width * 1.5),
        }
    
    # ==========================================================================
    # PHƯƠNG THỨC TIỆN ÍCH
    # ==========================================================================
    
    def _clean_text(self, text: str) -> str:
        """Làm sạch văn bản bằng cách loại bỏ khoảng trắng thừa."""
        # Loại bỏ nhiều khoảng trắng
        text = re.sub(r' +', ' ', text)
        # Loại bỏ nhiều dòng mới
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _text_to_html(self, text: str) -> str:
        """Chuyển đổi văn bản thuần sang HTML với các đoạn văn."""
        paragraphs = text.split('\n\n')
        html_parts = []
        for para in paragraphs:
            if para.strip():
                # Escape các thực thể HTML
                para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                # Chuyển đổi dòng mới đơn thành <br>
                para = para.replace('\n', '<br>')
                html_parts.append(f'<p>{para}</p>')
        return '\n'.join(html_parts)
    
    def _markdown_to_html(self, markdown: str) -> str:
        """
        Chuyển đổi markdown sang HTML.
        Triển khai đơn giản cho các mẫu phổ biến.
        """
        html = markdown
        
        # Đậm: **text** -> <strong>text</strong>
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        
        # Nghiêng: *text* hoặc _text_ -> <em>text</em>
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)
        
        # Tiêu đề: # text -> <h1>text</h1>
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Danh sách: - item -> <li>item</li>
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^• (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        
        # Đường kẻ ngang: --- -> <hr>
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
        
        # Đoạn văn
        paragraphs = html.split('\n\n')
        formatted = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # Không bọc nếu đã có thẻ HTML
                if not para.startswith('<'):
                    para = f'<p>{para}</p>'
                formatted.append(para)
        
        return '\n'.join(formatted)
    
    def _highlight_quotes(
        self,
        html: str,
        citations: List[FormattedCitation],
    ) -> str:
        """Làm nổi bật văn bản được trích dẫn từ các trích dẫn."""
        for cite in citations:
            if cite.quote:
                # Escape các ký tự regex đặc biệt trong trích dẫn
                escaped_quote = re.escape(cite.quote[:50])  # 50 ký tự đầu tiên
                pattern = f'({escaped_quote})'
                replacement = f'<mark class="citation-highlight" data-citation="{cite.index}">{cite.quote[:50]}</mark>'
                html = re.sub(pattern, replacement, html, count=1, flags=re.IGNORECASE)
        return html

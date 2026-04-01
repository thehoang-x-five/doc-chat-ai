"""
Dịch vụ cho tính năng So sánh Tài liệu (Document Comparison).

"""
import difflib
import re
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from app.schemas.compare import (
    ChangeCategory,
    ChangeType,
    CompareResult,
    CompareSource,
    CompareSourceType,
    CompareStatistics,
    DiffChange,
    SourceInfo,
)


class CompareService:
    """Dịch vụ so sánh tài liệu"""
    
    def __init__(self):
        self._results_cache = {}  # Cache trong bộ nhớ cho demo
    
    async def compare(
        self,
        workspace_id: str,
        source_a: CompareSource,
        text_a: str,
        source_b: CompareSource,
        text_b: str,
        include_ai_summary: bool = True,
        user_id: str = None,
        title_a: str = "Tài liệu A",
        title_b: str = "Tài liệu B",
    ) -> CompareResult:
        """
        So sánh hai tài liệu và trả về kết quả diff.
        """
        # Căn chỉnh các phần (sections)
        aligned = self._align_sections(text_a, text_b)
        
        # Tính toán diff
        changes = self._compute_diff(aligned)
        
        # Tính toán thống kê
        statistics = self._calculate_statistics(changes)
        
        # Tạo tóm tắt AI nếu được yêu cầu
        ai_summary = None
        if include_ai_summary and changes:
            ai_summary = await self._generate_ai_summary(changes, statistics)
        
        # Xây dựng kết quả
        result_id = str(uuid.uuid4())
        result = CompareResult(
            id=result_id,
            workspace_id=workspace_id,
            source_a=SourceInfo(
                type=source_a.type,
                title=title_a,
                document_id=source_a.document_id,
                version_id=source_a.version_id,
                url=source_a.url,
            ),
            source_b=SourceInfo(
                type=source_b.type,
                title=title_b,
                document_id=source_b.document_id,
                version_id=source_b.version_id,
                url=source_b.url,
            ),
            changes=changes,
            statistics=statistics,
            ai_summary=ai_summary,
            created_at=datetime.utcnow(),
            created_by=user_id or "system",
        )
        
        # Cache kết quả
        self._results_cache[result_id] = result
        
        return result

    
    async def compare_versions(
        self,
        workspace_id: str,
        document_id: str,
        version_a_text: str,
        version_b_text: str,
        version_a: int,
        version_b: int,
        include_ai_summary: bool = True,
        user_id: str = None,
        document_title: str = "Tài liệu",
    ) -> CompareResult:
        """So sánh hai phiên bản của cùng một tài liệu"""
        source_a = CompareSource(
            type=CompareSourceType.VERSION,
            document_id=document_id,
            version_id=f"{document_id}_v{version_a}",
        )
        source_b = CompareSource(
            type=CompareSourceType.VERSION,
            document_id=document_id,
            version_id=f"{document_id}_v{version_b}",
        )
        
        return await self.compare(
            workspace_id=workspace_id,
            source_a=source_a,
            text_a=version_a_text,
            source_b=source_b,
            text_b=version_b_text,
            include_ai_summary=include_ai_summary,
            user_id=user_id,
            title_a=f"{document_title} (v{version_a})",
            title_b=f"{document_title} (v{version_b})",
        )
    
    def get_result(self, compare_id: str) -> Optional[CompareResult]:
        """Lấy một kết quả so sánh đã lưu"""
        return self._results_cache.get(compare_id)
    
    def _align_sections(self, text_a: str, text_b: str) -> List[Tuple[str, str, str]]:
        """
        Căn chỉnh các phần (sections) sử dụng so sánh từng dòng.
        Trả về danh sách các tuple (tag, content_a, content_b).
        tag: 'equal', 'replace', 'delete', 'insert'
        """
        lines_a = text_a.splitlines(keepends=True)
        lines_b = text_b.splitlines(keepends=True)
        
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        aligned = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            content_a = ''.join(lines_a[i1:i2])
            content_b = ''.join(lines_b[j1:j2])
            aligned.append((tag, content_a, content_b))
        
        return aligned
    
    def _compute_diff(self, aligned_sections: List[Tuple[str, str, str]]) -> List[DiffChange]:
        """Tính toán diff chi tiết giữa các phần đã căn chỉnh"""
        changes = []
        
        for tag, content_a, content_b in aligned_sections:
            if tag == 'equal':
                continue
            
            if tag == 'delete':
                change = DiffChange(
                    type=ChangeType.REMOVED,
                    category=self._categorize_change(content_a, ""),
                    content_a=content_a.strip(),
                    content_b=None,
                    confidence=1.0,
                )
                changes.append(change)
            
            elif tag == 'insert':
                change = DiffChange(
                    type=ChangeType.ADDED,
                    category=self._categorize_change("", content_b),
                    content_a=None,
                    content_b=content_b.strip(),
                    confidence=1.0,
                )
                changes.append(change)
            
            elif tag == 'replace':
                change = DiffChange(
                    type=ChangeType.MODIFIED,
                    category=self._categorize_change(content_a, content_b),
                    content_a=content_a.strip(),
                    content_b=content_b.strip(),
                    confidence=self._calculate_similarity(content_a, content_b),
                )
                changes.append(change)
        
        return changes

    
    def _categorize_change(self, content_a: str, content_b: str) -> ChangeCategory:
        """Phân loại loại thay đổi (văn bản, số, ngày tháng, cấu trúc)"""
        combined = f"{content_a} {content_b}"
        
        # Kiểm tra mẫu ngày tháng (date patterns)
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
            r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
        ]
        for pattern in date_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return ChangeCategory.DATE
        
        # Kiểm tra mẫu số (number patterns: tiền tệ, phần trăm, số thường)
        number_patterns = [
            r'\$[\d,]+\.?\d*',
            r'[\d,]+\.?\d*%',
            r'\b\d{1,3}(,\d{3})*(\.\d+)?\b',
        ]
        for pattern in number_patterns:
            if re.search(pattern, combined):
                return ChangeCategory.NUMBER
        
        # Kiểm tra thay đổi cấu trúc (headers, lists, etc.)
        structural_patterns = [
            r'^#{1,6}\s',  # Markdown headers
            r'^\d+\.\s',   # Numbered lists
            r'^[-*]\s',    # Bullet lists
            r'^>\s',       # Blockquotes
        ]
        for pattern in structural_patterns:
            if re.search(pattern, combined, re.MULTILINE):
                return ChangeCategory.STRUCTURAL
        
        return ChangeCategory.TEXT
    
    def _calculate_similarity(self, text_a: str, text_b: str) -> float:
        """Tính toán tỷ lệ tương đồng giữa hai văn bản"""
        if not text_a and not text_b:
            return 1.0
        if not text_a or not text_b:
            return 0.0
        
        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        return matcher.ratio()
    
    def _calculate_statistics(self, changes: List[DiffChange]) -> CompareStatistics:
        """Tính toán thống kê từ các thay đổi"""
        added = sum(1 for c in changes if c.type == ChangeType.ADDED)
        removed = sum(1 for c in changes if c.type == ChangeType.REMOVED)
        modified = sum(1 for c in changes if c.type == ChangeType.MODIFIED)
        
        return CompareStatistics(
            added=added,
            removed=removed,
            modified=modified,
            total=added + removed + modified,
        )
    
    async def _generate_ai_summary(
        self,
        changes: List[DiffChange],
        statistics: CompareStatistics,
    ) -> str:
        """
        Tạo tóm tắt AI về các thay đổi chính.
        Sử dụng tạo tóm tắt dựa trên quy tắc với tùy chọn tăng cường bằng AI.
        Yêu cầu: 21.6
        """
        # Xây dựng tóm tắt dựa trên thay đổi
        summary_parts = []
        
        # Thống kê tổng quan
        summary_parts.append(
            f"Tổng cộng có {statistics.total} thay đổi: "
            f"{statistics.added} thêm mới, {statistics.removed} xóa bỏ, "
            f"{statistics.modified} sửa đổi."
        )
        
        # Phân loại thay đổi
        by_category: dict = {}
        for change in changes:
            cat = change.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(change)
        
        # Báo cáo theo danh mục
        if ChangeCategory.NUMBER.value in by_category:
            count = len(by_category[ChangeCategory.NUMBER.value])
            number_changes = by_category[ChangeCategory.NUMBER.value]
            summary_parts.append(f"Có {count} thay đổi về số liệu.")
            # Sample một số thay đổi số liệu
            if count <= 3:
                for nc in number_changes:
                    if nc.content_a and nc.content_b:
                        summary_parts.append(f"  • '{nc.content_a[:50]}...' → '{nc.content_b[:50]}...'")
        
        if ChangeCategory.DATE.value in by_category:
            count = len(by_category[ChangeCategory.DATE.value])
            summary_parts.append(f"Có {count} thay đổi về ngày tháng.")
        
        if ChangeCategory.STRUCTURAL.value in by_category:
            count = len(by_category[ChangeCategory.STRUCTURAL.value])
            summary_parts.append(f"Có {count} thay đổi về cấu trúc (tiêu đề, danh sách, v.v.).")
        
        if ChangeCategory.TEXT.value in by_category:
            count = len(by_category[ChangeCategory.TEXT.value])
            summary_parts.append(f"Có {count} thay đổi về nội dung văn bản.")
        
        # Làm nổi bật các thay đổi đáng kể (nội dung dài)
        significant = [c for c in changes if len(c.content_a or '') > 100 or len(c.content_b or '') > 100]
        if significant:
            summary_parts.append(f"Có {len(significant)} thay đổi đáng chú ý với nội dung dài.")
        
        # Các thay đổi có độ tin cậy thấp
        low_confidence = [c for c in changes if c.confidence < 0.5]
        if low_confidence:
            summary_parts.append(f"Có {len(low_confidence)} thay đổi cần xem xét kỹ (độ tin cậy thấp).")
        
        # Thử sử dụng AI provider để tóm tắt nâng cao nếu khả dụng
        try:
            from app.services.auth.api_key_service import get_key_manager
            import httpx
            
            key_manager = get_key_manager()
            api_key = key_manager.get_key("deepseek")
            
            if api_key and changes:
                # Xây dựng context cho AI
                changes_text = "\n".join([
                    f"- {c.type.value}: {(c.content_a or '')[:100]} → {(c.content_b or '')[:100]}"
                    for c in changes[:10]  # Giới hạn 10 thay đổi đầu tiên
                ])
                
                prompt = f"""Tóm tắt ngắn gọn các thay đổi sau giữa hai tài liệu (tối đa 2-3 câu):

Thống kê: {statistics.total} thay đổi ({statistics.added} thêm, {statistics.removed} xóa, {statistics.modified} sửa)

Các thay đổi chính:
{changes_text}

Tóm tắt:"""
                
                # Thử lấy tóm tắt từ AI
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7,
                            "max_tokens": 200,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    key_manager.mark_success("deepseek", api_key)
                    data = response.json()
                    ai_response = data["choices"][0]["message"]["content"]
                    if ai_response and ai_response.strip():
                        return ai_response.strip()
        except Exception:
            # Fall back về tóm tắt dựa trên quy tắc nếu AI thất bại
            pass
        
        return " ".join(summary_parts)


# Singleton instance
_compare_service: Optional[CompareService] = None


def get_compare_service() -> CompareService:
    """Lấy hoặc tạo instance CompareService"""
    global _compare_service
    if _compare_service is None:
        _compare_service = CompareService()
    return _compare_service

"""
Dịch vụ trích xuất dữ liệu dựa trên mẫu (Template-based Data Extraction).
Yêu cầu: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7, 22.8
"""
import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.extraction import (
    ExportFormat,
    ExtractedField,
    ExtractionResult,
    ExtractionTemplate,
    FieldType,
    TemplateField,
    TemplateCreateRequest,
    TemplateUpdateRequest,
    ValidationRule,
)


class ExtractionService:
    """Dịch vụ trích xuất dữ liệu dựa trên mẫu từ tài liệu."""
    
    def __init__(self):
        # In-memory storage cho demo (thay thế bằng DB trong production)
        self._templates: Dict[str, ExtractionTemplate] = {}
        self._results: Dict[str, ExtractionResult] = {}
    
    # =========================================================================
    # CÁC THAO TÁC CRUD MẪU (TEMPLATE)
    # =========================================================================
    
    async def create_template(
        self,
        workspace_id: str,
        request: TemplateCreateRequest,
        user_id: Optional[str] = None,
    ) -> ExtractionTemplate:
        """
        Tạo mẫu trích xuất mới.
        Yêu cầu: 22.1
        """
        template_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        template = ExtractionTemplate(
            id=template_id,
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
            fields=request.fields,
            created_at=now,
            updated_at=now,
            created_by=user_id,
        )
        
        self._templates[template_id] = template
        return template
    
    async def get_template(
        self,
        template_id: str,
        workspace_id: str,
    ) -> Optional[ExtractionTemplate]:
        """Lấy mẫu theo ID."""
        template = self._templates.get(template_id)
        if template and template.workspace_id == workspace_id:
            return template
        return None
    
    async def list_templates(
        self,
        workspace_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ExtractionTemplate], int]:
        """Liệt kê các mẫu trong một workspace."""
        templates = [
            t for t in self._templates.values()
            if t.workspace_id == workspace_id
        ]
        total = len(templates)
        return templates[skip:skip + limit], total
    
    async def update_template(
        self,
        template_id: str,
        workspace_id: str,
        request: TemplateUpdateRequest,
    ) -> Optional[ExtractionTemplate]:
        """Cập nhật một mẫu hiện có."""
        template = await self.get_template(template_id, workspace_id)
        if not template:
            return None
        
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.fields is not None:
            template.fields = request.fields
        
        template.updated_at = datetime.utcnow()
        self._templates[template_id] = template
        return template
    
    async def delete_template(
        self,
        template_id: str,
        workspace_id: str,
    ) -> bool:
        """Xóa một mẫu."""
        template = await self.get_template(template_id, workspace_id)
        if not template:
            return False
        
        del self._templates[template_id]
        # Cũng xóa các kết quả liên quan
        result_ids_to_delete = [
            r.id for r in self._results.values()
            if r.template_id == template_id
        ]
        for rid in result_ids_to_delete:
            del self._results[rid]
        
        return True


    # =========================================================================
    # CÁC THAO TÁC TRÍCH XUẤT
    # =========================================================================
    
    async def extract(
        self,
        workspace_id: str,
        template_id: str,
        document_id: str,
        document_text: str,
        document_title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Trích xuất dữ liệu từ tài liệu sử dụng một mẫu.
        Yêu cầu: 22.2, 22.4, 22.7, 22.8
        """
        template = await self.get_template(template_id, workspace_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Trích xuất các trường sử dụng AI
        extracted_fields = await self._extract_fields(
            template.fields,
            document_text,
        )
        
        # Tính toán thống kê
        fields_extracted = sum(1 for f in extracted_fields if f.value is not None)
        fields_failed = sum(1 for f in extracted_fields if f.value is None and self._is_required(f.field_name, template.fields))
        fields_need_review = sum(1 for f in extracted_fields if f.needs_review)
        
        # Tính toán độ tin cậy tổng thể
        confidences = [f.confidence for f in extracted_fields if f.value is not None]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        result_id = str(uuid.uuid4())
        result = ExtractionResult(
            id=result_id,
            workspace_id=workspace_id,
            template_id=template_id,
            template_name=template.name,
            document_id=document_id,
            document_title=document_title,
            fields=extracted_fields,
            overall_confidence=overall_confidence,
            fields_extracted=fields_extracted,
            fields_failed=fields_failed,
            fields_need_review=fields_need_review,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )
        
        self._results[result_id] = result
        return result
    
    def _is_required(self, field_name: str, fields: List[TemplateField]) -> bool:
        """Kiểm tra xem một trường có bắt buộc không."""
        for f in fields:
            if f.name == field_name:
                return f.required
        return False
    
    async def _extract_fields(
        self,
        fields: List[TemplateField],
        document_text: str,
    ) -> List[ExtractedField]:
        """
        Trích xuất giá trị trường từ văn bản tài liệu sử dụng AI.
        Yêu cầu: 22.2, 22.7, 22.8
        """
        extracted = []
        
        for field in fields:
            # Xây dựng prompt trích xuất
            prompt = self._build_extraction_prompt(field, document_text)
            
            # Thử trích xuất sử dụng AI
            try:
                value, raw_text, confidence, source_location = await self._ai_extract_field(
                    field, document_text, prompt
                )
                
                # Validate giá trị trích xuất được
                validation_passed, validation_errors = self._validate_field(
                    field, value
                )
                
                # Cờ báo hiệu cần xem xét nếu độ tin cậy thấp
                needs_review = confidence < 0.7 or not validation_passed
                
                extracted.append(ExtractedField(
                    field_name=field.name,
                    field_type=field.type,
                    value=value,
                    raw_text=raw_text,
                    confidence=confidence,
                    source_location=source_location,
                    validation_passed=validation_passed,
                    validation_errors=validation_errors,
                    needs_review=needs_review,
                ))
            except Exception as e:
                # Trích xuất trường thất bại
                extracted.append(ExtractedField(
                    field_name=field.name,
                    field_type=field.type,
                    value=None,
                    confidence=0.0,
                    validation_passed=False,
                    validation_errors=[str(e)],
                    needs_review=True,
                ))
        
        return extracted
    
    def _build_extraction_prompt(
        self,
        field: TemplateField,
        document_text: str,
    ) -> str:
        """Build prompt for AI extraction."""
        examples_str = ""
        if field.examples:
            examples_str = f"\nExamples: {', '.join(field.examples)}"
        
        return f"""Extract the following field from the document:

Field Name: {field.name}
Field Type: {field.type.value}
Description: {field.description or 'N/A'}{examples_str}

Document:
{document_text[:4000]}

Instructions:
1. Find the value for "{field.name}" in the document
2. Return the extracted value in the correct format for type "{field.type.value}"
3. If the field is not found, return null
4. Include the exact text from the document where you found this value

Response format (JSON):
{{"value": <extracted_value>, "raw_text": "<exact text from document>", "confidence": <0.0-1.0>, "location": "<page/section>"}}
"""
    
    async def _ai_extract_field(
        self,
        field: TemplateField,
        document_text: str,
        prompt: str,
    ) -> Tuple[Any, Optional[str], float, Optional[str]]:
        """
        Sử dụng AI để trích xuất giá trị trường.
        Trả về: (value, raw_text, confidence, source_location)
        """
        # Thử sử dụng AI provider thông qua AIProviderManager
        try:
            from app.services.infrastructure.ai_providers.manager import manager as ai_manager
            
            messages = [{"role": "user", "content": prompt}]
            
            # Sử dụng generate_completion với fallback
            ai_response = await ai_manager.generate_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse JSON phản hồi
            try:
                # Tìm JSON trong phản hồi
                json_match = re.search(r'\{[^{}]*\}', ai_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    value = self._convert_value(data.get("value"), field.type)
                    return (
                        value,
                        data.get("raw_text"),
                        float(data.get("confidence", 0.8)),
                        data.get("location"),
                    )
            except json.JSONDecodeError:
                pass
                
        except Exception:
            # AI extraction thất bại, chuyển sang pattern matching
            pass
        
        # Fallback: khớp mẫu đơn giản
        return await self._pattern_extract_field(field, document_text)
    
    async def _pattern_extract_field(
        self,
        field: TemplateField,
        document_text: str,
    ) -> Tuple[Any, Optional[str], float, Optional[str]]:
        """
        Fallback extraction sử dụng khớp mẫu (pattern matching).
        """
        # Khớp mẫu đơn giản dựa trên tên trường
        patterns = {
            FieldType.EMAIL: r'[\w\.-]+@[\w\.-]+\.\w+',
            FieldType.PHONE: r'[\+\d][\d\s\-\(\)]{8,}',
            FieldType.URL: r'https?://[^\s]+',
            FieldType.DATE: r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}',
            FieldType.NUMBER: r'\b\d+(?:\.\d+)?\b',
            FieldType.CURRENCY: r'[\$€£¥]\s*[\d,]+(?:\.\d{2})?',
        }
        
        # Thử pattern cụ thể cho loại trường
        if field.type in patterns:
            match = re.search(patterns[field.type], document_text)
            if match:
                raw_text = match.group()
                value = self._convert_value(raw_text, field.type)
                return (value, raw_text, 0.6, None)
        
        # Thử tìm tên trường theo sau là giá trị
        name_pattern = re.escape(field.name) + r'[:\s]+([^\n]+)'
        match = re.search(name_pattern, document_text, re.IGNORECASE)
        if match:
            raw_text = match.group(1).strip()
            value = self._convert_value(raw_text, field.type)
            return (value, raw_text, 0.5, None)
        
        return (None, None, 0.0, None)
    
    def _convert_value(self, value: Any, field_type: FieldType) -> Any:
        """Chuyển đổi giá trị đã trích xuất sang đúng kiểu."""
        if value is None:
            return None
        
        try:
            if field_type == FieldType.NUMBER:
                # Loại bỏ ký tự không phải số trừ dấu thập phân
                clean = re.sub(r'[^\d.-]', '', str(value))
                return float(clean) if '.' in clean else int(clean)
            elif field_type == FieldType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ('true', 'yes', '1', 'có', 'đúng')
            elif field_type == FieldType.CURRENCY:
                # Loại bỏ ký hiệu tiền tệ và chuyển đổi sang số
                clean = re.sub(r'[^\d.-]', '', str(value))
                return float(clean)
            elif field_type == FieldType.LIST:
                if isinstance(value, list):
                    return value
                # Thử tách bằng các dấu phân cách phổ biến
                return [v.strip() for v in str(value).split(',')]
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)
    
    def _validate_field(
        self,
        field: TemplateField,
        value: Any,
    ) -> Tuple[bool, List[str]]:
        """
        Validate giá trị đã trích xuất theo các quy tắc của trường.
        Yêu cầu: 22.4
        """
        errors = []
        
        # Kiểm tra bắt buộc
        if field.required and value is None:
            errors.append(f"Field '{field.name}' is required")
            return False, errors
        
        if value is None:
            return True, []
        
        # Kiểm tra các quy tắc validate
        for rule in field.validation_rules:
            if rule.type == "min":
                if isinstance(value, (int, float)) and value < rule.value:
                    errors.append(rule.message or f"Value must be at least {rule.value}")
            elif rule.type == "max":
                if isinstance(value, (int, float)) and value > rule.value:
                    errors.append(rule.message or f"Value must be at most {rule.value}")
            elif rule.type == "pattern":
                if not re.match(rule.value, str(value)):
                    errors.append(rule.message or f"Value does not match pattern")
            elif rule.type == "enum":
                if value not in rule.value:
                    errors.append(rule.message or f"Value must be one of: {rule.value}")
        
        return len(errors) == 0, errors


    # =========================================================================
    # TRÍCH XUẤT HÀNG LOẠT (BATCH EXTRACTION)
    # =========================================================================
    
    async def batch_extract(
        self,
        workspace_id: str,
        template_id: str,
        documents: List[Dict[str, Any]],  # List of {id, text, title}
        user_id: Optional[str] = None,
    ) -> List[ExtractionResult]:
        """
        Trích xuất dữ liệu từ nhiều tài liệu sử dụng cùng một mẫu.
        Yêu cầu: 22.6
        """
        results = []
        for doc in documents:
            try:
                result = await self.extract(
                    workspace_id=workspace_id,
                    template_id=template_id,
                    document_id=doc["id"],
                    document_text=doc["text"],
                    document_title=doc.get("title"),
                    user_id=user_id,
                )
                results.append(result)
            except Exception as e:
                # Tạo kết quả thất bại
                template = await self.get_template(template_id, workspace_id)
                results.append(ExtractionResult(
                    id=str(uuid.uuid4()),
                    workspace_id=workspace_id,
                    template_id=template_id,
                    template_name=template.name if template else "Unknown",
                    document_id=doc["id"],
                    document_title=doc.get("title"),
                    fields=[],
                    overall_confidence=0.0,
                    fields_extracted=0,
                    fields_failed=len(template.fields) if template else 0,
                    fields_need_review=0,
                    created_at=datetime.utcnow(),
                    created_by=user_id,
                ))
        
        return results
    
    # =========================================================================
    # CÁC THAO TÁC KẾT QUẢ
    # =========================================================================
    
    async def get_result(
        self,
        result_id: str,
        workspace_id: str,
    ) -> Optional[ExtractionResult]:
        """Lấy một kết quả trích xuất theo ID."""
        result = self._results.get(result_id)
        if result and result.workspace_id == workspace_id:
            return result
        return None
    
    async def list_results(
        self,
        workspace_id: str,
        template_id: Optional[str] = None,
        document_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ExtractionResult], int]:
        """Liệt kê các kết quả trích xuất với các bộ lọc tùy chọn."""
        results = [
            r for r in self._results.values()
            if r.workspace_id == workspace_id
        ]
        
        if template_id:
            results = [r for r in results if r.template_id == template_id]
        if document_id:
            results = [r for r in results if r.document_id == document_id]
        
        total = len(results)
        return results[skip:skip + limit], total
    
    # =========================================================================
    # CÁC THAO TÁC XUẤT (EXPORT)
    # =========================================================================
    
    async def export_results(
        self,
        workspace_id: str,
        result_ids: List[str],
        format: ExportFormat,
    ) -> Tuple[bytes, str]:
        """
        Xuất các kết quả trích xuất sang định dạng chỉ định.
        Yêu cầu: 22.5
        Trả về: (file_content, filename)
        """
        # Lấy kết quả
        results = []
        for rid in result_ids:
            result = await self.get_result(rid, workspace_id)
            if result:
                results.append(result)
        
        if not results:
            raise ValueError("No results found to export")
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if format == ExportFormat.JSON:
            return self._export_json(results), f"extraction_{timestamp}.json"
        elif format == ExportFormat.CSV:
            return self._export_csv(results), f"extraction_{timestamp}.csv"
        elif format == ExportFormat.EXCEL:
            return self._export_excel(results), f"extraction_{timestamp}.xlsx"
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _export_json(self, results: List[ExtractionResult]) -> bytes:
        """Xuất kết quả sang định dạng JSON."""
        data = []
        for result in results:
            row = {
                "id": result.id,
                "document_id": result.document_id,
                "document_title": result.document_title,
                "template_name": result.template_name,
                "overall_confidence": result.overall_confidence,
                "created_at": result.created_at.isoformat(),
                "fields": {},
            }
            for field in result.fields:
                row["fields"][field.field_name] = {
                    "value": field.value,
                    "confidence": field.confidence,
                    "needs_review": field.needs_review,
                }
            data.append(row)
        
        return json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    
    def _export_csv(self, results: List[ExtractionResult]) -> bytes:
        """Xuất kết quả sang định dạng CSV."""
        if not results:
            return b""
        
        # Get all field names from first result
        field_names = [f.field_name for f in results[0].fields]
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        header = ["document_id", "document_title", "overall_confidence"] + field_names
        writer.writerow(header)
        
        # Data rows
        for result in results:
            row = [
                result.document_id,
                result.document_title or "",
                result.overall_confidence,
            ]
            field_values = {f.field_name: f.value for f in result.fields}
            for name in field_names:
                row.append(field_values.get(name, ""))
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')
    
    def _export_excel(self, results: List[ExtractionResult]) -> bytes:
        """Xuất kết quả sang định dạng Excel."""
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Extraction Results"
            
            if not results:
                return b""
            
            # Get all field names
            field_names = [f.field_name for f in results[0].fields]
            
            # Header
            header = ["document_id", "document_title", "overall_confidence"] + field_names
            ws.append(header)
            
            # Data rows
            for result in results:
                row = [
                    result.document_id,
                    result.document_title or "",
                    result.overall_confidence,
                ]
                field_values = {f.field_name: f.value for f in result.fields}
                for name in field_names:
                    val = field_values.get(name, "")
                    # Convert lists to string for Excel
                    if isinstance(val, list):
                        val = ", ".join(str(v) for v in val)
                    row.append(val)
                ws.append(row)
            
            # Save to bytes
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()
        except ImportError:
            # Fallback to CSV if openpyxl not available
            return self._export_csv(results)


# Singleton instance
_extraction_service: Optional[ExtractionService] = None


def get_extraction_service() -> ExtractionService:
    """Get or create ExtractionService instance."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service

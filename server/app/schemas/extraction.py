"""
Schemas for Template-based Data Extraction feature.
Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7, 22.8
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Type of field to extract"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    CURRENCY = "currency"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    LIST = "list"
    OBJECT = "object"


class ValidationRule(BaseModel):
    """Validation rule for a field"""
    type: str  # required, min, max, pattern, enum, custom
    value: Optional[Any] = None
    message: Optional[str] = None


class TemplateField(BaseModel):
    """Definition of a field to extract"""
    name: str = Field(..., min_length=1, max_length=100)
    type: FieldType = FieldType.TEXT
    description: Optional[str] = None
    required: bool = False
    validation_rules: List[ValidationRule] = []
    examples: List[str] = []  # Example values to help AI
    default_value: Optional[Any] = None


class ExtractionTemplate(BaseModel):
    """Template for extracting structured data from documents"""
    id: Optional[str] = None
    workspace_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    fields: List[TemplateField]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class ExtractedField(BaseModel):
    """A single extracted field value"""
    field_name: str
    field_type: FieldType
    value: Optional[Any] = None
    raw_text: Optional[str] = None  # Original text from document
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_location: Optional[str] = None  # Page/section reference
    source_chunk_id: Optional[str] = None  # Citation to chunk
    validation_passed: bool = True
    validation_errors: List[str] = []
    needs_review: bool = False  # Flag for low confidence


class ExtractionResult(BaseModel):
    """Result of extracting data from a document using a template"""
    id: str
    workspace_id: str
    template_id: str
    template_name: str
    document_id: str
    document_title: Optional[str] = None
    fields: List[ExtractedField]
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fields_extracted: int = 0
    fields_failed: int = 0
    fields_need_review: int = 0
    created_at: datetime
    created_by: Optional[str] = None


# =============================================================================
# Request/Response Schemas
# =============================================================================

class TemplateCreateRequest(BaseModel):
    """Request to create an extraction template"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    fields: List[TemplateField]


class TemplateUpdateRequest(BaseModel):
    """Request to update an extraction template"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    fields: Optional[List[TemplateField]] = None


class TemplateResponse(BaseModel):
    """Response for template operations"""
    id: str
    workspace_id: str
    name: str
    description: Optional[str] = None
    fields: List[TemplateField]
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class TemplateListResponse(BaseModel):
    """Response for listing templates"""
    templates: List[TemplateResponse]
    total: int


class ExtractRequest(BaseModel):
    """Request to extract data from a document"""
    template_id: str
    document_id: str


class BatchExtractRequest(BaseModel):
    """Request to extract data from multiple documents"""
    template_id: str
    document_ids: List[str]


class ExtractResponse(BaseModel):
    """Response for extraction operation"""
    id: str
    workspace_id: str
    template_id: str
    template_name: str
    document_id: str
    document_title: Optional[str] = None
    fields: List[ExtractedField]
    overall_confidence: float
    fields_extracted: int
    fields_failed: int
    fields_need_review: int
    created_at: datetime


class BatchExtractResponse(BaseModel):
    """Response for batch extraction"""
    results: List[ExtractResponse]
    total_documents: int
    successful: int
    failed: int


class ExportFormat(str, Enum):
    """Export format options"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


class ExportRequest(BaseModel):
    """Request to export extraction results"""
    result_ids: List[str]
    format: ExportFormat = ExportFormat.JSON


class ExportResponse(BaseModel):
    """Response for export operation"""
    download_url: str
    format: ExportFormat
    filename: str
    expires_at: datetime

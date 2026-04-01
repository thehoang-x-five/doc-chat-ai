"""
Pydantic schemas for API requests and responses
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


# OCR Settings
class PreprocessSettings(BaseModel):
    autoOrientation: bool = True
    deskew: bool = True
    denoise: bool = False
    binarize: bool = False
    contrastBoost: bool = False


class ExtractSettings(BaseModel):
    tables: bool = True
    equations: bool = True
    images: bool = False


class OcrSettings(BaseModel):
    parser: str = Field(default="docling", description="Parser to use (docling|mineru)")
    parse_method: str = Field(default="auto", description="Parse method (auto|ocr|txt)")
    language: str = Field(default="auto", description="Language (auto|vi|en|...)")
    mode: str = Field(default="balanced", description="Processing mode (fast|balanced|accurate)")
    preserveLayout: bool = True
    returnLayout: bool = True
    startPage: Optional[int] = None
    endPage: Optional[int] = None
    preprocess: PreprocessSettings = Field(default_factory=PreprocessSettings)
    extract: ExtractSettings = Field(default_factory=ExtractSettings)


# OCR Request
class OCRRequest(BaseModel):
    """Request model for OCR processing"""
    file: Optional[Any] = None  # File upload
    url: Optional[str] = None  # URL to document
    settings: OcrSettings = Field(default_factory=OcrSettings)
    enableAI: bool = Field(default=False, description="Enable AI enhancement")
    aiProvider: Optional[str] = Field(default=None, description="AI provider to use")


# Response models
class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class LayoutWord(BaseModel):
    text: str
    bbox: BoundingBox
    confidence: float


class LayoutLine(BaseModel):
    text: str
    confidence: float
    bbox: BoundingBox
    words: List[LayoutWord] = Field(default_factory=list)


class LayoutBlock(BaseModel):
    type: str  # text|heading|table|image|list
    text: str
    bbox: BoundingBox
    confidence: float
    lines: List[LayoutLine] = Field(default_factory=list)


class LayoutPage(BaseModel):
    page: int
    width: float
    height: float
    blocks: List[LayoutBlock]


class Layout(BaseModel):
    pages: List[LayoutPage]


class Page(BaseModel):
    page: int
    text: str
    confidence: float


class Structured(BaseModel):
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    equations: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)


class Timings(BaseModel):
    parseMs: int
    postMs: int


class Meta(BaseModel):
    parser: str
    parse_method: str
    language: str
    pageCount: int
    avgConfidence: float
    timings: Timings


class OcrResult(BaseModel):
    fullText: str
    markdownText: Optional[str] = None
    layoutText: Optional[str] = None
    pages: List[Page]
    structured: Structured
    layout: Layout
    meta: Meta
    enhancedText: Optional[str] = None  # AI-enhanced text
    aiMetadata: Optional[Dict[str, Any]] = None  # AI enhancement metadata


class JobResponse(BaseModel):
    jobId: str
    status: str  # queued|running|done|error
    step: str = Field(default="upload")  # upload|preprocess|parse|postprocess|done
    percent: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="")
    result: Optional[OcrResult] = None
    error: Optional[str] = None


class AsyncJobResponse(BaseModel):
    jobId: str
    status: str


# Convert models
class PdfOptions(BaseModel):
    pageSize: str = Field(default="A4")
    fontSize: int = Field(default=12, ge=8, le=72)


class ConvertRequest(BaseModel):
    text: str
    format: str = Field(..., pattern="^(txt|md|json|pdf|docx)$")
    fileName: str = Field(default="output")
    includeMetadata: bool = Field(default=True)
    pdfOptions: Optional[PdfOptions] = None


# RAG models (optional)
class RagIngestRequest(BaseModel):
    docId: Optional[str] = None
    jobId: Optional[str] = None


class RagQueryRequest(BaseModel):
    question: str
    mode: str = Field(default="hybrid", pattern="^(hybrid|local|global|naive)$")
    vlmEnhanced: bool = Field(default=True)


class RagQueryResponse(BaseModel):
    answer: str
    contexts: List[Dict[str, Any]] = Field(default_factory=list)


# Health check
class HealthResponse(BaseModel):
    ok: bool
    version: str
    parserDefault: str
    enableRag: bool
    ollamaReachable: bool
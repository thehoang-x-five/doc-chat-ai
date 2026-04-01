"""
Type definitions for RAG Pipeline

Contains enums, dataclasses, and type definitions used throughout the pipeline.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


# ============================================================================
# ENUMS
# ============================================================================

class DocStatus(str, Enum):
    """
    Document processing status.
    
    Used to track the state of documents through the processing pipeline.
    """
    
    READY = "ready"
    """Document is ready to be processed."""
    
    HANDLING = "handling"
    """Document is currently being handled (initial stage)."""
    
    PENDING = "pending"
    """Document is pending processing (queued)."""
    
    PROCESSING = "processing"
    """Document is actively being processed."""
    
    PROCESSED = "processed"
    """Document has been successfully processed."""
    
    FAILED = "failed"
    """Document processing failed."""


class ContentType(str, Enum):
    """
    Types of content that can be processed.
    
    Used by modal processors to identify content type.
    """
    
    TEXT = "text"
    """Plain text content."""
    
    IMAGE = "image"
    """Image content (photos, diagrams, charts)."""
    
    TABLE = "table"
    """Tabular data (spreadsheets, data tables)."""
    
    EQUATION = "equation"
    """Mathematical equations and formulas."""
    
    CODE = "code"
    """Source code."""
    
    GENERIC = "generic"
    """Generic/unknown content type."""


class ParserType(str, Enum):
    """
    Available document parsers.
    
    Each parser has different strengths and use cases.
    """
    
    MINERU = "mineru"
    """MinerU parser - Good for complex layouts and multimodal content."""
    
    DOCLING = "docling"
    """Docling parser - Fast and reliable for standard documents."""
    
    AUTO = "auto"
    """Automatic parser selection based on document type."""


class ParseMethod(str, Enum):
    """
    Document parsing methods.
    
    Different methods for extracting content from documents.
    """
    
    AUTO = "auto"
    """Automatic method selection."""
    
    OCR = "ocr"
    """Optical Character Recognition - for scanned documents."""
    
    TXT = "txt"
    """Text extraction - for digital documents."""


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ProcessingResult:
    """
    Result of document processing.
    
    Contains all information about a processed document including
    extracted content, metadata, and processing statistics.
    """
    
    document_id: str
    """Unique identifier for the document."""
    
    status: DocStatus
    """Processing status."""
    
    content: str = ""
    """Extracted text content."""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Document metadata (title, author, page count, etc.)."""
    
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    """Processed chunks with embeddings and metadata."""
    
    entities: List[Dict[str, Any]] = field(default_factory=list)
    """Extracted entities (for knowledge graph)."""
    
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    """Extracted relationships between entities."""
    
    images: List[Dict[str, Any]] = field(default_factory=list)
    """Processed images with analysis."""
    
    tables: List[Dict[str, Any]] = field(default_factory=list)
    """Processed tables with analysis."""
    
    equations: List[Dict[str, Any]] = field(default_factory=list)
    """Processed equations with analysis."""
    
    error: Optional[str] = None
    """Error message if processing failed."""
    
    processing_time_ms: float = 0.0
    """Total processing time in milliseconds."""
    
    stats: Dict[str, Any] = field(default_factory=dict)
    """Processing statistics (token count, chunk count, etc.)."""


@dataclass
class ModalContent:
    """
    Multimodal content item.
    
    Represents a single piece of multimodal content (image, table, equation)
    extracted from a document.
    """
    
    content_type: ContentType
    """Type of content."""
    
    content_id: str
    """Unique identifier for this content."""
    
    raw_content: Any
    """Raw content (image bytes, table data, equation LaTeX, etc.)."""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Content metadata (caption, page number, position, etc.)."""
    
    analysis: Optional[str] = None
    """AI-generated analysis of the content."""
    
    embedding: Optional[List[float]] = None
    """Vector embedding of the content."""
    
    context: Optional[str] = None
    """Surrounding context from the document."""


@dataclass
class BatchProcessingResult:
    """
    Result of batch document processing.
    
    Contains results for multiple documents processed in a batch.
    """
    
    total_documents: int
    """Total number of documents in the batch."""
    
    successful: int
    """Number of successfully processed documents."""
    
    failed: int
    """Number of failed documents."""
    
    results: List[ProcessingResult] = field(default_factory=list)
    """Individual processing results."""
    
    errors: List[Dict[str, Any]] = field(default_factory=list)
    """Error details for failed documents."""
    
    total_time_ms: float = 0.0
    """Total batch processing time in milliseconds."""
    
    stats: Dict[str, Any] = field(default_factory=dict)
    """Aggregate statistics."""


# ============================================================================
# TYPE ALIASES
# ============================================================================

DocumentPath = str | Path
"""Type alias for document paths (string or Path object)."""

EmbeddingVector = List[float]
"""Type alias for embedding vectors."""

EntityDict = Dict[str, Any]
"""Type alias for entity dictionaries."""

RelationshipDict = Dict[str, Any]
"""Type alias for relationship dictionaries."""


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "DocStatus",
    "ContentType",
    "ParserType",
    "ParseMethod",
    
    # Dataclasses
    "ProcessingResult",
    "ModalContent",
    "BatchProcessingResult",
    
    # Type aliases
    "DocumentPath",
    "EmbeddingVector",
    "EntityDict",
    "RelationshipDict",
]

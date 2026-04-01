"""
RAG Pipeline - Document processing and multimodal analysis

This submodule handles:
- Document parsing (PDF, images, Office docs)
- Multimodal content processing (images, tables, equations)
- Batch processing
- Context extraction

MIGRATION STATUS: ✅ Complete
All components fully migrated from raganything:
- Config, Prompts, Types, Utils: ✅ Complete
- Parsers, Processors, Pipeline: ✅ Complete  
- Batch processing: ✅ Complete
- Resilience (retry, CircuitBreaker): ✅ Complete
- Callbacks (observability, metrics): ✅ Complete
"""

from app.services.rag_patterns.pipeline.config import RAGConfig
from app.services.rag_patterns.pipeline.pipeline import RAGPipeline, compute_mdhash_id
from app.services.rag_patterns.pipeline.batch import (
    BatchParser,
    BatchProcessor,
    BatchProcessingResult as BatchResult,
)
from app.services.rag_patterns.pipeline.types import (
    DocStatus,
    ContentType,
    ParserType,
    ParseMethod,
    ProcessingResult,
    ModalContent,
    BatchProcessingResult,
)
from app.services.rag_patterns.pipeline.parsers import (
    BaseParser,
    MineruParser,
    DoclingParser,
    ParserFactory,
    MineruExecutionError,
)
from app.services.rag_patterns.pipeline.processors import (
    BaseModalProcessor,
    ImageModalProcessor,
    TableModalProcessor,
    EquationModalProcessor,
    GenericModalProcessor,
    ProcessorFactory,
    ContextExtractor,
    ContextConfig,
)
from app.services.rag_patterns.pipeline.prompts import PROMPTS
from app.services.rag_patterns.pipeline.resilience import (
    retry,
    async_retry,
    CircuitBreaker,
)
from app.services.rag_patterns.pipeline.callbacks import (
    ProcessingEvent,
    ProcessingCallback,
    MetricsCallback,
    CallbackManager,
)
from app.services.rag_patterns.pipeline.utils import (
    separate_content,
    insert_text_content,
    insert_text_content_with_multimodal_content,
    encode_image_to_base64,
    validate_image_file,
    get_image_mime_type,
    get_processor_for_type,
    get_processor_supports,
    compute_file_hash,
    get_file_extension,
    get_file_basename,
    ensure_directory,
    is_supported_document,
    truncate_text,
    clean_text,
    count_tokens_approximate,
)

__all__ = [
    # Core Pipeline
    "RAGConfig",
    "RAGPipeline",
    "compute_mdhash_id",
    
    # Batch Processing
    "BatchParser",
    "BatchProcessor",
    "BatchResult",
    
    # Types
    "DocStatus",
    "ContentType",
    "ParserType",
    "ParseMethod",
    "ProcessingResult",
    "ModalContent",
    "BatchProcessingResult",
    
    # Parsers
    "BaseParser",
    "MineruParser",
    "DoclingParser",
    "ParserFactory",
    "MineruExecutionError",
    
    # Processors
    "BaseModalProcessor",
    "ImageModalProcessor",
    "TableModalProcessor",
    "EquationModalProcessor",
    "GenericModalProcessor",
    "ProcessorFactory",
    "ContextExtractor",
    "ContextConfig",
    
    # Prompts
    "PROMPTS",
    
    # Resilience
    "retry",
    "async_retry",
    "CircuitBreaker",
    
    # Callbacks
    "ProcessingEvent",
    "ProcessingCallback",
    "MetricsCallback",
    "CallbackManager",
    
    # Utils - Content
    "separate_content",
    "insert_text_content",
    "insert_text_content_with_multimodal_content",
    
    # Utils - Image
    "encode_image_to_base64",
    "validate_image_file",
    "get_image_mime_type",
    
    # Utils - Processor
    "get_processor_for_type",
    "get_processor_supports",
    
    # Utils - File
    "compute_file_hash",
    "get_file_extension",
    "get_file_basename",
    "ensure_directory",
    "is_supported_document",
    
    # Utils - Text
    "truncate_text",
    "clean_text",
    "count_tokens_approximate",
]

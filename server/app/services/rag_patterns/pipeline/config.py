"""
RAG Pipeline Configuration

Extends server settings with RAG-specific configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.core.config import settings


@dataclass
class RAGConfig:
    """
    Configuration for RAG Pipeline.
    
    This config extends the server's Settings with RAG-specific options.
    It uses server settings as the source of truth and adds RAG-specific features.
    """
    
    # ========================================================================
    # DIRECTORY CONFIGURATION (from server settings)
    # ========================================================================
    
    working_dir: Path = field(default_factory=lambda: settings.STORAGE_DIR / "rag_storage")
    """Directory where RAG storage and cache files are stored."""
    
    parser_output_dir: Path = field(default_factory=lambda: settings.STORAGE_DIR / "parsed_output")
    """Default output directory for parsed content."""
    
    # ========================================================================
    # PARSER CONFIGURATION (from server settings)
    # ========================================================================
    
    parser: str = field(default_factory=lambda: settings.DEFAULT_PARSER)
    """Parser selection: 'mineru' or 'docling'."""
    
    parse_method: str = field(default_factory=lambda: settings.DEFAULT_PARSE_METHOD)
    """Default parsing method: 'auto', 'ocr', or 'txt'."""
    
    display_content_stats: bool = True
    """Whether to display content statistics during parsing."""
    
    # ========================================================================
    # MULTIMODAL PROCESSING CONFIGURATION (from server settings)
    # ========================================================================
    
    enable_image_processing: bool = field(default_factory=lambda: settings.ENABLE_IMAGE_PROCESSING)
    """Enable image content processing and vision model analysis."""
    
    enable_table_processing: bool = field(default_factory=lambda: settings.ENABLE_TABLE_PROCESSING)
    """Enable table content processing and structured data extraction."""
    
    enable_equation_processing: bool = field(default_factory=lambda: settings.ENABLE_EQUATION_PROCESSING)
    """Enable equation content processing and mathematical analysis."""
    
    # ========================================================================
    # BATCH PROCESSING CONFIGURATION (from server settings)
    # ========================================================================
    
    max_concurrent_files: int = field(default_factory=lambda: settings.MAX_CONCURRENT_FILES)
    """Maximum number of files to process concurrently in batch mode."""
    
    supported_file_extensions: List[str] = field(
        default_factory=lambda: [ext if ext.startswith('.') else f'.{ext}' 
                                for ext in settings.ALLOWED_EXTENSIONS]
    )
    """List of supported file extensions for batch processing."""
    
    recursive_folder_processing: bool = field(default_factory=lambda: settings.RECURSIVE_FOLDER_PROCESSING)
    """Whether to recursively process subfolders in batch mode."""
    
    # ========================================================================
    # CONTEXT EXTRACTION CONFIGURATION (from server settings)
    # ========================================================================
    
    context_window: int = field(default_factory=lambda: settings.CONTEXT_WINDOW)
    """Number of pages/chunks to include before and after current item for context."""
    
    context_mode: str = field(default_factory=lambda: settings.CONTEXT_MODE)
    """Context extraction mode: 'page' for page-based, 'chunk' for chunk-based."""
    
    max_context_tokens: int = field(default_factory=lambda: settings.MAX_CONTEXT_TOKENS)
    """Maximum number of tokens in extracted context."""
    
    include_headers: bool = field(default_factory=lambda: settings.INCLUDE_HEADERS)
    """Whether to include document headers and titles in context."""
    
    include_captions: bool = field(default_factory=lambda: settings.INCLUDE_CAPTIONS)
    """Whether to include image/table captions in context."""
    
    context_filter_content_types: List[str] = field(
        default_factory=lambda: ["text", "image", "table"]
    )
    """Content types to include in context extraction."""
    
    content_format: str = "minerU"
    """Default content format for context extraction when processing documents."""
    
    # ========================================================================
    # PATH HANDLING CONFIGURATION
    # ========================================================================
    
    use_full_path: bool = False
    """Whether to use full file path (True) or just basename (False) for file references."""
    
    # ========================================================================
    # RESILIENCE CONFIGURATION
    # ========================================================================
    
    retry_max_attempts: int = 3
    """Maximum number of retry attempts for transient failures."""
    
    retry_base_delay: float = 1.0
    """Base delay in seconds between retries (exponential backoff)."""
    
    retry_max_delay: float = 60.0
    """Upper bound on delay between retries."""
    
    circuit_breaker_threshold: int = 5
    """Number of failures before circuit breaker opens."""
    
    circuit_breaker_timeout: float = 60.0
    """Seconds to wait before circuit breaker transitions to half-open."""
    
    # ========================================================================
    # INTEGRATION WITH SERVER SETTINGS
    # ========================================================================
    
    @property
    def storage_dir(self) -> Path:
        """Get storage directory from server settings."""
        return settings.STORAGE_DIR
    
    @property
    def default_device(self) -> str:
        """Get default device from server settings."""
        return settings.DEFAULT_DEVICE
    
    @property
    def default_lang(self) -> str:
        """Get default language from server settings."""
        return settings.DEFAULT_LANG
    
    @property
    def ollama_base_url(self) -> str:
        """Get Ollama base URL from server settings."""
        return settings.OLLAMA_BASE_URL
    
    @property
    def ollama_vision_model(self) -> str:
        """Get Ollama vision model from server settings."""
        return settings.OLLAMA_VISION_MODEL
    
    @property
    def ollama_embed_model(self) -> str:
        """Get Ollama embedding model from server settings."""
        return settings.OLLAMA_EMBED_MODEL
    
    def __post_init__(self):
        """Post-initialization: ensure directories exist."""
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.parser_output_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_server_settings(cls) -> "RAGConfig":
        """
        Create RAGConfig from server settings.
        
        This is the recommended way to create a RAGConfig instance,
        ensuring consistency with server configuration.
        
        Returns:
            RAGConfig: Configuration instance
        """
        return cls()
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "working_dir": str(self.working_dir),
            "parser_output_dir": str(self.parser_output_dir),
            "parser": self.parser,
            "parse_method": self.parse_method,
            "display_content_stats": self.display_content_stats,
            "enable_image_processing": self.enable_image_processing,
            "enable_table_processing": self.enable_table_processing,
            "enable_equation_processing": self.enable_equation_processing,
            "max_concurrent_files": self.max_concurrent_files,
            "supported_file_extensions": self.supported_file_extensions,
            "recursive_folder_processing": self.recursive_folder_processing,
            "context_window": self.context_window,
            "context_mode": self.context_mode,
            "max_context_tokens": self.max_context_tokens,
            "include_headers": self.include_headers,
            "include_captions": self.include_captions,
            "context_filter_content_types": self.context_filter_content_types,
            "content_format": self.content_format,
            "use_full_path": self.use_full_path,
            "retry_max_attempts": self.retry_max_attempts,
            "retry_base_delay": self.retry_base_delay,
            "retry_max_delay": self.retry_max_delay,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_timeout": self.circuit_breaker_timeout,
        }

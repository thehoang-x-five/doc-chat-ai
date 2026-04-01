"""
RAG Pipeline - Main document processing pipeline

This module provides the RAGPipeline class that orchestrates:
- Document parsing (PDF, images, Office docs)
- Text and multimodal content separation
- Multimodal content processing (images, tables, equations)
- Integration with LightRAG for knowledge graph construction

Migrated from raganything/processor.py and raganything/raganything.py
"""

import os
import re
import time
import json
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from app.services.rag_patterns.pipeline.config import RAGConfig
from app.services.rag_patterns.pipeline.types import (
    ProcessingResult,
    DocStatus,
    ContentType,
)
from app.services.rag_patterns.pipeline.parsers import (
    ParserFactory,
    MineruParser,
    DoclingParser,
    MineruExecutionError,
)
from app.services.rag_patterns.pipeline.processors import (
    ProcessorFactory,
    ContextExtractor,
    ContextConfig,
)
from app.services.rag_patterns.pipeline.prompts import PROMPTS
from app.services.rag_patterns.pipeline.utils import (
    separate_content,
    get_processor_for_type,
)
from app.services.rag_patterns.pipeline.callbacks import (
    CallbackManager,
    MetricsCallback,
)

logger = logging.getLogger(__name__)


def compute_mdhash_id(content: str, prefix: str = "") -> str:
    """Compute a hash-based ID for content."""
    hash_obj = hashlib.md5(content.encode("utf-8"))
    return f"{prefix}{hash_obj.hexdigest()}"


# ============================================================================
# RAG PIPELINE
# ============================================================================


@dataclass
class RAGPipeline:
    """
    Main RAG processing pipeline.

    Orchestrates the complete document processing workflow:
    1. Parse document (PDF, images, Office docs)
    2. Separate text and multimodal content
    3. Process multimodal items (images, tables, equations)
    4. Extract entities and relationships
    5. Insert into knowledge graph

    Example:
        >>> config = RAGConfig.from_server_settings()
        >>> pipeline = RAGPipeline(config=config, lightrag=lightrag_instance)
        >>> result = await pipeline.process_document("document.pdf")
    """

    # Core configuration
    config: Optional[RAGConfig] = field(default=None)
    """RAG configuration object."""

    # External dependencies (injected)
    lightrag: Optional[Any] = field(default=None)
    """LightRAG instance for knowledge graph operations."""

    llm_func: Optional[Callable] = field(default=None)
    """LLM function for text analysis."""

    vision_func: Optional[Callable] = field(default=None)
    """Vision model function for image analysis."""

    embedding_func: Optional[Callable] = field(default=None)
    """Embedding function for vectorization."""

    # LightRAG configuration
    lightrag_kwargs: Dict[str, Any] = field(default_factory=dict)
    """Additional LightRAG parameters."""

    # Internal state
    modal_processors: Dict[str, Any] = field(default_factory=dict, init=False)
    """Dictionary of multimodal processors."""

    context_extractor: Optional[ContextExtractor] = field(default=None, init=False)
    """Context extractor for modal processing."""

    parse_cache: Optional[Any] = field(default=None, init=False)
    """Parse result cache storage."""

    callback_manager: CallbackManager = field(default=None, init=False)
    """Callback manager for pipeline event dispatching."""

    _parser: Optional[Any] = field(default=None, init=False)
    """Document parser instance."""

    _parser_installation_checked: bool = field(default=False, init=False)
    """Flag to track parser installation check."""

    def __post_init__(self):
        """Post-initialization setup."""
        if self.config is None:
            self.config = RAGConfig.from_server_settings()

        self.working_dir = self.config.working_dir
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize callback manager
        if self.callback_manager is None:
            self.callback_manager = CallbackManager()

        # Create working directory if needed
        if self.working_dir and not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
            self.logger.info(f"Created working directory: {self.working_dir}")

        self.logger.info("RAGPipeline initialized")
        self.logger.info(f"  Working directory: {self.working_dir}")
        self.logger.info(f"  Parser: {self.config.parser}")
        self.logger.info(f"  Parse method: {self.config.parse_method}")

    # ========================================================================
    # PARSER MANAGEMENT
    # ========================================================================

    def _get_parser(self):
        """Get or create parser instance (lazy loading)."""
        if self._parser is None:
            self._parser = ParserFactory.create_parser(self.config.parser, self.config)
        return self._parser

    def check_parser_installation(self) -> bool:
        """Check if the configured parser is properly installed."""
        parser = self._get_parser()
        return parser.check_installation()

    def _get_file_reference(self, file_path: str) -> str:
        """Get file reference based on use_full_path configuration."""
        if getattr(self.config, "use_full_path", False):
            return str(file_path)
        else:
            return os.path.basename(file_path)

    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================

    def _generate_cache_key(
        self, file_path: Path, parse_method: str = None, **kwargs
    ) -> str:
        """Generate cache key based on file path and parsing configuration."""
        mtime = file_path.stat().st_mtime

        config_dict = {
            "file_path": str(file_path.absolute()),
            "mtime": mtime,
            "parser": self.config.parser,
            "parse_method": parse_method or self.config.parse_method,
        }

        relevant_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "lang",
                "device",
                "start_page",
                "end_page",
                "formula",
                "table",
                "backend",
                "source",
            ]
        }
        config_dict.update(relevant_kwargs)

        config_str = json.dumps(config_dict, sort_keys=True)
        cache_key = hashlib.md5(config_str.encode()).hexdigest()
        return cache_key

    def _generate_content_based_doc_id(self, content_list: List[Dict[str, Any]]) -> str:
        """Generate doc_id based on document content."""
        content_hash_data = []

        for item in content_list:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    content_hash_data.append(item["text"].strip())
                elif item.get("type") == "image" and item.get("img_path"):
                    content_hash_data.append(f"image:{item['img_path']}")
                elif item.get("type") == "table" and item.get("table_body"):
                    content_hash_data.append(f"table:{item['table_body']}")
                elif item.get("type") == "equation" and item.get("text"):
                    content_hash_data.append(f"equation:{item['text']}")
                else:
                    content_hash_data.append(str(item))

        content_signature = "\n".join(content_hash_data)
        doc_id = compute_mdhash_id(content_signature, prefix="doc-")
        return doc_id

    async def _get_cached_result(
        self, cache_key: str, file_path: Path, parse_method: str = None, **kwargs
    ) -> Optional[Tuple[List[Dict[str, Any]], str]]:
        """Get cached parsing result if available and valid."""
        if self.parse_cache is None:
            return None

        try:
            cached_data = await self.parse_cache.get_by_id(cache_key)
            if not cached_data:
                return None

            current_mtime = file_path.stat().st_mtime
            cached_mtime = cached_data.get("mtime", 0)

            if current_mtime != cached_mtime:
                self.logger.debug(f"Cache invalid - file modified: {cache_key}")
                return None

            cached_config = cached_data.get("parse_config", {})
            current_config = {
                "parser": self.config.parser,
                "parse_method": parse_method or self.config.parse_method,
            }

            relevant_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "lang",
                    "device",
                    "start_page",
                    "end_page",
                    "formula",
                    "table",
                    "backend",
                    "source",
                ]
            }
            current_config.update(relevant_kwargs)

            if cached_config != current_config:
                self.logger.debug(f"Cache invalid - config changed: {cache_key}")
                return None

            content_list = cached_data.get("content_list", [])
            doc_id = cached_data.get("doc_id")

            if content_list and doc_id:
                self.logger.debug(f"Found valid cached result for key: {cache_key}")
                return content_list, doc_id

            return None

        except Exception as e:
            self.logger.warning(f"Error accessing parse cache: {e}")
            return None

    async def _store_cached_result(
        self,
        cache_key: str,
        content_list: List[Dict[str, Any]],
        doc_id: str,
        file_path: Path,
        parse_method: str = None,
        **kwargs,
    ) -> None:
        """Store parsing result in cache."""
        if self.parse_cache is None:
            return

        try:
            file_mtime = file_path.stat().st_mtime

            parse_config = {
                "parser": self.config.parser,
                "parse_method": parse_method or self.config.parse_method,
            }

            relevant_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "lang",
                    "device",
                    "start_page",
                    "end_page",
                    "formula",
                    "table",
                    "backend",
                    "source",
                ]
            }
            parse_config.update(relevant_kwargs)

            cache_data = {
                cache_key: {
                    "content_list": content_list,
                    "doc_id": doc_id,
                    "mtime": file_mtime,
                    "parse_config": parse_config,
                    "cached_at": time.time(),
                    "cache_version": "1.0",
                }
            }
            await self.parse_cache.upsert(cache_data)
            await self.parse_cache.index_done_callback()
            self.logger.info(f"Stored parsing result in cache: {cache_key}")

        except Exception as e:
            self.logger.warning(f"Error storing to parse cache: {e}")

    # ========================================================================
    # DOCUMENT PARSING
    # ========================================================================

    async def parse_document(
        self,
        file_path: Union[str, Path],
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = None,
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Parse document with caching support.

        Args:
            file_path: Path to the file to parse
            output_dir: Output directory for parser
            parse_method: Parse method to use
            display_stats: Whether to display content statistics
            **kwargs: Additional parser parameters

        Returns:
            Tuple of (content_list, doc_id)
        """
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if display_stats is None:
            display_stats = getattr(self.config, "display_content_stats", False)

        self.logger.info(f"Starting document parsing: {file_path}")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        callback_file = str(file_path)
        parse_start_time = time.time()
        self.callback_manager.dispatch(
            "on_parse_start",
            file_path=callback_file,
            parser=self.config.parser,
        )

        # Generate cache key and check cache
        cache_key = self._generate_cache_key(file_path, parse_method, **kwargs)
        cached_result = await self._get_cached_result(
            cache_key, file_path, parse_method, **kwargs
        )
        if cached_result is not None:
            content_list, doc_id = cached_result
            self.logger.info(f"Using cached parsing result for: {file_path}")
            if display_stats:
                self.logger.info(f"* Total blocks in cached content_list: {len(content_list)}")
            duration = time.time() - parse_start_time
            self.callback_manager.dispatch(
                "on_parse_complete",
                file_path=callback_file,
                content_blocks=len(content_list),
                doc_id=doc_id,
                duration_seconds=duration,
            )
            return content_list, doc_id

        # Parse based on file extension
        ext = file_path.suffix.lower()
        parser = self._get_parser()

        try:
            self.logger.info(f"Using {self.config.parser} parser with method: {parse_method}")

            if ext in [".pdf"]:
                self.logger.info("Detected PDF file, using parser for PDF...")
                content_list = await asyncio.to_thread(
                    parser.parse_pdf,
                    pdf_path=file_path,
                    output_dir=output_dir,
                    method=parse_method,
                    **kwargs,
                )
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"]:
                self.logger.info("Detected image file, using parser for images...")
                if hasattr(parser, "parse_image"):
                    content_list = await asyncio.to_thread(
                        parser.parse_image,
                        image_path=file_path,
                        output_dir=output_dir,
                        **kwargs,
                    )
                else:
                    self.logger.warning(f"{self.config.parser} doesn't support image parsing, falling back to MinerU")
                    content_list = MineruParser().parse_image(
                        image_path=file_path, output_dir=output_dir, **kwargs
                    )
            elif ext in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".html", ".htm", ".xhtml"]:
                self.logger.info("Detected Office or HTML document...")
                content_list = await asyncio.to_thread(
                    parser.parse_office_doc,
                    doc_path=file_path,
                    output_dir=output_dir,
                    **kwargs,
                )
            else:
                self.logger.info(f"Using generic parser for {ext} file...")
                content_list = await asyncio.to_thread(
                    parser.parse_document,
                    file_path=file_path,
                    method=parse_method,
                    output_dir=output_dir,
                    **kwargs,
                )

        except MineruExecutionError as e:
            self.logger.error(f"Mineru command failed: {e}")
            self.callback_manager.dispatch(
                "on_parse_error",
                file_path=callback_file,
                error=e,
                parser=self.config.parser,
            )
            raise
        except Exception as e:
            self.logger.error(f"Error during parsing with {self.config.parser}: {str(e)}")
            self.callback_manager.dispatch(
                "on_parse_error",
                file_path=callback_file,
                error=e,
                parser=self.config.parser,
            )
            raise

        self.logger.info(f"Parsing complete! Extracted {len(content_list)} content blocks")

        if len(content_list) == 0:
            raise ValueError("Parsing failed: No content was extracted")

        doc_id = self._generate_content_based_doc_id(content_list)

        await self._store_cached_result(
            cache_key, content_list, doc_id, file_path, parse_method, **kwargs
        )

        if display_stats:
            self.logger.info(f"* Total blocks in content_list: {len(content_list)}")
            block_types: Dict[str, int] = {}
            for block in content_list:
                if isinstance(block, dict):
                    block_type = block.get("type", "unknown")
                    if isinstance(block_type, str):
                        block_types[block_type] = block_types.get(block_type, 0) + 1
            for block_type, count in block_types.items():
                self.logger.info(f"  - {block_type}: {count}")

        duration = time.time() - parse_start_time
        self.callback_manager.dispatch(
            "on_parse_complete",
            file_path=callback_file,
            content_blocks=len(content_list),
            doc_id=doc_id,
            duration_seconds=duration,
        )

        return content_list, doc_id

    # ========================================================================
    # PROCESSOR MANAGEMENT
    # ========================================================================

    def _create_context_config(self) -> ContextConfig:
        """Create context configuration from pipeline config."""
        return ContextConfig(
            context_window=getattr(self.config, "context_window", 1),
            context_mode=getattr(self.config, "context_mode", "page"),
            max_context_tokens=getattr(self.config, "max_context_tokens", 2000),
            include_headers=getattr(self.config, "include_headers", True),
            include_captions=getattr(self.config, "include_captions", True),
            filter_content_types=getattr(self.config, "context_filter_content_types", ["text"]),
        )

    def _create_context_extractor(self) -> ContextExtractor:
        """Create context extractor with tokenizer from LightRAG."""
        context_config = self._create_context_config()
        tokenizer = None
        if self.lightrag and hasattr(self.lightrag, "tokenizer"):
            tokenizer = self.lightrag.tokenizer
        return ContextExtractor(config=context_config, tokenizer=tokenizer)

    def _initialize_processors(self):
        """Initialize multimodal processors with appropriate model functions."""
        self.context_extractor = self._create_context_extractor()
        self.modal_processors = {}

        if getattr(self.config, "enable_image_processing", True):
            self.modal_processors["image"] = ProcessorFactory.create_processor(
                "image", self.config, self.llm_func, self.vision_func
            )

        if getattr(self.config, "enable_table_processing", True):
            self.modal_processors["table"] = ProcessorFactory.create_processor(
                "table", self.config, self.llm_func, self.vision_func
            )

        if getattr(self.config, "enable_equation_processing", True):
            self.modal_processors["equation"] = ProcessorFactory.create_processor(
                "equation", self.config, self.llm_func, self.vision_func
            )

        self.modal_processors["generic"] = ProcessorFactory.create_processor(
            "generic", self.config, self.llm_func, self.vision_func
        )

        self.logger.info("Multimodal processors initialized")
        self.logger.info(f"Available processors: {list(self.modal_processors.keys())}")

    def set_content_source_for_context(
        self, content_source: Any, content_format: str = "auto"
    ):
        """Set content source for context extraction in all modal processors."""
        if not self.modal_processors:
            self.logger.warning("Modal processors not initialized")
            return

        for processor_name, processor in self.modal_processors.items():
            try:
                processor.set_content_source(content_source, content_format)
            except Exception as e:
                self.logger.error(f"Failed to set content source for {processor_name}: {e}")

        self.logger.info(f"Content source set for context extraction (format: {content_format})")

    # ========================================================================
    # LIGHTRAG INITIALIZATION
    # ========================================================================

    async def _ensure_lightrag_initialized(self) -> Dict[str, Any]:
        """Ensure LightRAG instance is initialized."""
        try:
            if not self._parser_installation_checked:
                if not self.check_parser_installation():
                    error_msg = f"Parser '{self.config.parser}' is not properly installed."
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                self._parser_installation_checked = True
                self.logger.info(f"Parser '{self.config.parser}' installation verified")

            if self.lightrag is None:
                error_msg = "LightRAG instance must be provided"
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Initialize LightRAG storages if needed
            try:
                if (
                    not hasattr(self.lightrag, "_storages_status")
                    or self.lightrag._storages_status.name != "INITIALIZED"
                ):
                    self.logger.info("Initializing LightRAG storages")
                    await self.lightrag.initialize_storages()

                    try:
                        from lightrag.kg.shared_storage import initialize_pipeline_status
                        await initialize_pipeline_status()
                    except ImportError:
                        self.logger.warning("Could not import initialize_pipeline_status")

                # Initialize parse cache if not done
                if self.parse_cache is None and hasattr(self.lightrag, "key_string_value_json_storage_cls"):
                    # Safe workspace access to prevent MissingGreenlet
                    safe_workspace = "default_workspace"
                    try:
                        if hasattr(self.lightrag, "workspace"):
                            ws = self.lightrag.workspace
                            # Check if it's an object that might be detached
                            if hasattr(ws, "name"):
                                safe_workspace = str(ws.name)
                            elif hasattr(ws, "id"):
                                safe_workspace = str(ws.id)
                            else:
                                safe_workspace = str(ws)
                    except BaseException as e:
                        self.logger.warning(f"Error accessing workspace ({type(e).__name__}): {e}, using default")
                        safe_workspace = "default_workspace"

                    self.parse_cache = self.lightrag.key_string_value_json_storage_cls(
                        namespace="parse_cache",
                        workspace=safe_workspace,
                        global_config=self.lightrag.__dict__,
                        embedding_func=self.embedding_func,
                    )
                    await self.parse_cache.initialize()

                # Initialize processors if not done
                if not self.modal_processors:
                    self._initialize_processors()

                return {"success": True}

            except Exception as e:
                error_msg = f"Failed to initialize LightRAG: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Unexpected error during initialization: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    # ========================================================================
    # PUBLIC API — QUERY
    # ========================================================================

    async def aquery(
        self,
        query: str,
        mode: str = "hybrid",
        system_prompt: str | None = None,
        **kwargs,
    ) -> Any:
        """Execute RAG query with callback dispatching and optional VLM routing.

        Args:
            query: Query text
            mode: Query mode ("local", "global", "hybrid", "naive", "mix", "bypass")
            system_prompt: Optional system prompt to include
            **kwargs: Other query parameters
                - vlm_enhanced: bool, auto-detected based on vision_func availability.
                  If True, replaces image paths in retrieved context with base64 images.

        Returns:
            Query result string
        """
        await self._ensure_lightrag_initialized()

        if not self.lightrag:
            raise ValueError("LightRAG instance must be provided for queries")

        # Check if VLM enhanced query should be used
        vlm_enhanced = kwargs.pop("vlm_enhanced", None)
        if vlm_enhanced is None:
            vlm_enhanced = self.vision_func is not None

        if vlm_enhanced and self.vision_func:
            return await self.aquery_vlm_enhanced(
                query, mode=mode, system_prompt=system_prompt, **kwargs
            )
        elif vlm_enhanced and not self.vision_func:
            self.logger.warning(
                "VLM enhanced query requested but vision_func not available, "
                "falling back to normal query"
            )

        query_start_time = time.time()
        self.callback_manager.dispatch(
            "on_query_start", query=query, mode=mode,
        )

        try:
            from lightrag import QueryParam
            query_param = QueryParam(mode=mode, **kwargs)
            result = await self.lightrag.aquery(
                query, param=query_param, system_prompt=system_prompt
            )
        except Exception as exc:
            self.callback_manager.dispatch(
                "on_query_error", query=query, mode=mode, error=exc,
            )
            raise

        duration = time.time() - query_start_time
        result_len = len(result) if isinstance(result, str) else 0
        self.callback_manager.dispatch(
            "on_query_complete",
            query=query,
            mode=mode,
            duration_seconds=duration,
            result_length=result_len,
        )
        self.logger.info("Text query completed")
        return result

    async def aquery_with_multimodal(
        self,
        query: str,
        multimodal_content: list = None,
        mode: str = "hybrid",
        **kwargs,
    ) -> Any:
        """Multimodal query — combines text and multimodal content.

        Args:
            query: Base query text
            multimodal_content: List of multimodal content dicts with 'type' key
            mode: Query mode
            **kwargs: Other query parameters

        Returns:
            Query result string
        """
        await self._ensure_lightrag_initialized()

        if not multimodal_content:
            return await self.aquery(query, mode=mode, **kwargs)

        self.logger.info(f"Executing multimodal query: {query[:100]}...")

        # Process multimodal content to generate enhanced query text
        enhanced_parts = [f"User query: {query}"]

        for i, content in enumerate(multimodal_content):
            content_type = content.get("type", "unknown")
            processor = get_processor_for_type(self.modal_processors, content_type)

            if processor:
                try:
                    description, _ = await processor.process(
                        content=content, context=None, entity_name=None,
                        item_info={"index": i, "type": content_type},
                    )
                    enhanced_parts.append(
                        f"\nRelated {content_type} content: {description}"
                    )
                except Exception as e:
                    self.logger.error(f"Error processing multimodal query content: {e}")
            else:
                enhanced_parts.append(
                    f"\nRelated {content_type} content: {str(content)[:200]}"
                )

        enhanced_query = "\n".join(enhanced_parts)
        return await self.aquery(enhanced_query, mode=mode, **kwargs)

    async def aquery_vlm_enhanced(
        self,
        query: str,
        mode: str = "hybrid",
        system_prompt: str | None = None,
        extra_safe_dirs: List[str] = None,
        **kwargs,
    ) -> str:
        """VLM enhanced query — replaces image paths in context with base64 for VLM.

        Workflow:
        1. Get retrieval prompt from LightRAG (only_need_prompt=True)
        2. Extract image paths, encode to base64
        3. Build multimodal VLM messages
        4. Call vision model for visual QA

        Args:
            query: User query
            mode: Underlying LightRAG query mode
            system_prompt: Optional system prompt
            extra_safe_dirs: Additional safe directories to allow images from
            **kwargs: Other query parameters

        Returns:
            VLM query result
        """
        if not self.vision_func:
            raise ValueError(
                "VLM enhanced query requires vision_func. "
                "Please provide a vision model function when initializing RAGPipeline."
            )

        await self._ensure_lightrag_initialized()
        self.logger.info(f"Executing VLM enhanced query: {query[:100]}...")

        # Clear previous image cache
        if hasattr(self, "_current_images_base64"):
            delattr(self, "_current_images_base64")

        # 1. Get original retrieval prompt (without generating final answer)
        from lightrag import QueryParam
        query_param = QueryParam(mode=mode, only_need_prompt=True, **kwargs)
        raw_prompt = await self.lightrag.aquery(query, param=query_param)

        # 2. Extract and process image paths
        enhanced_prompt, images_found = self._process_image_paths_for_vlm(
            raw_prompt, extra_safe_dirs=extra_safe_dirs
        )

        if not images_found:
            self.logger.info("No valid images found, falling back to normal query")
            query_param = QueryParam(mode=mode, **kwargs)
            return await self.lightrag.aquery(
                query, param=query_param, system_prompt=system_prompt
            )

        self.logger.info(f"Processed {images_found} images for VLM")

        # 3. Build VLM message format
        messages = self._build_vlm_messages_with_images(
            enhanced_prompt, query, system_prompt
        )

        # 4. Call VLM for question answering
        result = await self._call_vlm_with_multimodal_content(messages)

        self.logger.info("VLM enhanced query completed")
        return result

    # ========================================================================
    # VLM QUERY HELPERS
    # ========================================================================

    def _process_image_paths_for_vlm(
        self, prompt: str, extra_safe_dirs: List[str] = None
    ) -> tuple:
        """Process image paths in prompt for VLM processing.

        Args:
            prompt: Original prompt containing image path references
            extra_safe_dirs: Optional list of additional safe directories

        Returns:
            tuple: (processed prompt, number of images found)
        """
        enhanced_prompt = prompt
        images_processed = 0
        self._current_images_base64 = []

        # Match 'Image Path: ...' lines
        image_path_pattern = (
            r"Image Path:\s*([^\r\n]*?\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|tif))"
        )

        matches = re.findall(image_path_pattern, prompt)
        self.logger.info(f"Found {len(matches)} image path matches in prompt")

        def replace_image_path(match):
            nonlocal images_processed
            image_path = match.group(1).strip()

            if not image_path or len(image_path) < 3:
                return match.group(0)

            abs_image_path = Path(image_path).resolve()
            if not abs_image_path.exists():
                self.logger.warning(f"Image file not found: {image_path}")
                return match.group(0)

            # Security: only allow images from safe directories
            is_safe = False
            try:
                is_safe = abs_image_path.is_relative_to(Path.cwd())
            except (ValueError, TypeError):
                pass

            if not is_safe and self.config:
                try:
                    is_safe = (
                        abs_image_path.is_relative_to(Path(self.config.working_dir).resolve())
                        or abs_image_path.is_relative_to(Path(self.config.parser_output_dir).resolve())
                    )
                except Exception:
                    pass

            if not is_safe and extra_safe_dirs:
                for safe_dir in extra_safe_dirs:
                    try:
                        if abs_image_path.is_relative_to(Path(safe_dir).resolve()):
                            is_safe = True
                            break
                    except Exception:
                        continue

            if not is_safe:
                self.logger.warning(f"Blocking image outside safe directories: {image_path}")
                return match.group(0)

            try:
                import base64
                with open(abs_image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
                if image_base64:
                    images_processed += 1
                    self._current_images_base64.append(image_base64)
                    return f"Image Path: {image_path}\n[VLM_IMAGE_{images_processed}]"
            except Exception as e:
                self.logger.error(f"Failed to encode image {image_path}: {e}")

            return match.group(0)

        enhanced_prompt = re.sub(image_path_pattern, replace_image_path, enhanced_prompt)
        return enhanced_prompt, images_processed

    def _build_vlm_messages_with_images(
        self, enhanced_prompt: str, user_query: str, system_prompt: str = None,
    ) -> List[Dict]:
        """Build VLM message format with inline base64 images.

        Args:
            enhanced_prompt: Enhanced prompt with [VLM_IMAGE_N] markers
            user_query: Original user query
            system_prompt: Optional system prompt

        Returns:
            List of message dicts in VLM format
        """
        images_base64 = getattr(self, "_current_images_base64", [])

        if not images_base64:
            return [
                {
                    "role": "user",
                    "content": f"Context:\n{enhanced_prompt}\n\nUser Question: {user_query}",
                }
            ]

        content_parts = []
        text_parts = enhanced_prompt.split("[VLM_IMAGE_")

        for i, text_part in enumerate(text_parts):
            if i == 0:
                if text_part.strip():
                    content_parts.append({"type": "text", "text": text_part})
            else:
                marker_match = re.match(r"(\d+)\](.*)", text_part, re.DOTALL)
                if marker_match:
                    image_num = int(marker_match.group(1)) - 1
                    remaining_text = marker_match.group(2)

                    if 0 <= image_num < len(images_base64):
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{images_base64[image_num]}"
                            },
                        })

                    if remaining_text.strip():
                        content_parts.append({"type": "text", "text": remaining_text})

        content_parts.append({
            "type": "text",
            "text": f"\n\nUser Question: {user_query}\n\nPlease answer based on the context and images provided.",
        })

        base_system = (
            "You are a helpful assistant that can analyze both text and image "
            "content to provide comprehensive answers."
        )
        full_system = f"{base_system} {system_prompt}" if system_prompt else base_system

        return [
            {"role": "system", "content": full_system},
            {"role": "user", "content": content_parts},
        ]

    async def _call_vlm_with_multimodal_content(self, messages: List[Dict]) -> str:
        """Call VLM to process multimodal content.

        Args:
            messages: VLM message format with system + user messages

        Returns:
            VLM response result
        """
        try:
            user_message = messages[-1]
            content = user_message["content"]
            system_prompt = messages[0]["content"] if len(messages) > 1 else None

            if isinstance(content, str):
                result = await self.vision_func(
                    content, system_prompt=system_prompt
                )
            else:
                result = await self.vision_func(
                    "",  # Empty prompt since we're using messages format
                    messages=messages,
                )

            return result
        except Exception as e:
            self.logger.error(f"VLM call failed: {e}")
            raise



    # ========================================================================
    # MULTIMODAL PROCESSING
    # ========================================================================

    async def _process_multimodal_content(
        self,
        multimodal_items: List[Dict[str, Any]],
        file_path: str,
        doc_id: str,
        pipeline_status: Optional[Any] = None,
        pipeline_status_lock: Optional[Any] = None,
    ):
        """Process multimodal content using specialized processors."""
        if not multimodal_items:
            self.logger.debug("No multimodal content to process")
            return

        mm_start_time = time.time()
        self.callback_manager.dispatch(
            "on_multimodal_start",
            file_path=file_path,
            item_count=len(multimodal_items),
            doc_id=doc_id,
        )

        # Check if already processed
        try:
            if self.lightrag:
                existing_doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
                if existing_doc_status:
                    if existing_doc_status.get("multimodal_processed", False):
                        self.logger.info(f"Document {doc_id} multimodal is already processed")
                        return
        except Exception as e:
            self.logger.debug(f"Error checking document status for {doc_id}: {e}")

        log_message = "Starting multimodal content processing..."
        self.logger.info(log_message)

        try:
            await self._ensure_lightrag_initialized()
            await self._process_multimodal_content_batch(multimodal_items, file_path, doc_id)
            await self._mark_multimodal_processing_complete(doc_id)

            duration = time.time() - mm_start_time
            self.callback_manager.dispatch(
                "on_multimodal_complete",
                file_path=file_path,
                processed_count=len(multimodal_items),
                duration_seconds=duration,
                doc_id=doc_id,
            )
            self.logger.info("Multimodal content processing complete")

        except Exception as e:
            self.logger.error(f"Error in multimodal processing: {e}")
            self.logger.warning("Falling back to individual processing")
            await self._process_multimodal_content_individual(multimodal_items, file_path, doc_id)
            await self._mark_multimodal_processing_complete(doc_id)
            duration = time.time() - mm_start_time
            self.callback_manager.dispatch(
                "on_multimodal_complete",
                file_path=file_path,
                processed_count=len(multimodal_items),
                duration_seconds=duration,
                doc_id=doc_id,
            )

    async def _process_multimodal_content_individual(
        self,
        multimodal_items: List[Dict[str, Any]],
        file_path: str,
        doc_id: str,
    ):
        """Process multimodal content individually (fallback method)."""
        file_name = self._get_file_reference(file_path)
        all_chunk_results = []
        multimodal_chunk_ids = []

        existing_chunks_count = 0
        if self.lightrag:
            try:
                existing_doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
                existing_chunks_count = existing_doc_status.get("chunks_count", 0) if existing_doc_status else 0
            except Exception:
                pass

        for i, item in enumerate(multimodal_items):
            try:
                content_type = item.get("type", "unknown")
                self.logger.info(f"Processing item {i+1}/{len(multimodal_items)}: {content_type}")

                processor = get_processor_for_type(self.modal_processors, content_type)

                if processor:
                    item_info = {
                        "page_idx": item.get("page_idx", 0),
                        "index": i,
                        "type": content_type,
                    }

                    description, entity_info = await processor.process(
                        content=item,
                        context=None,
                        entity_name=None,
                        item_info=item_info,
                    )

                    chunk_content = processor.format_chunk(item, description)
                    chunk_id = compute_mdhash_id(chunk_content, prefix="chunk-")
                    multimodal_chunk_ids.append(chunk_id)

                    self.logger.info(f"{content_type} processing complete")
                else:
                    self.logger.warning(f"No processor found for {content_type}")

            except Exception as e:
                self.logger.error(f"Error processing multimodal content: {str(e)}")
                continue

        self.logger.info("Individual multimodal processing complete")

    async def _process_multimodal_content_batch(
        self,
        multimodal_items: List[Dict[str, Any]],
        file_path: str,
        doc_id: str,
    ):
        """Batch processing for multimodal content."""
        if not multimodal_items:
            return

        existing_chunks_count = 0
        if self.lightrag:
            try:
                existing_doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
                existing_chunks_count = existing_doc_status.get("chunks_count", 0) if existing_doc_status else 0
            except Exception:
                pass

        # Use concurrency control
        max_parallel = 2
        if self.lightrag and hasattr(self.lightrag, "max_parallel_insert"):
            max_parallel = self.lightrag.max_parallel_insert
        semaphore = asyncio.Semaphore(max_parallel)

        total_items = len(multimodal_items)
        completed_count = 0
        progress_lock = asyncio.Lock()

        self.logger.info(f"Starting batch processing of {total_items} multimodal items")

        async def process_single_item(item: Dict[str, Any], index: int):
            nonlocal completed_count
            async with semaphore:
                try:
                    content_type = item.get("type", "unknown")
                    processor = get_processor_for_type(self.modal_processors, content_type)

                    if not processor:
                        self.logger.warning(f"No processor for type: {content_type}")
                        return None

                    item_info = {
                        "page_idx": item.get("page_idx", 0),
                        "index": index,
                        "type": content_type,
                    }

                    description, entity_info = await processor.process(
                        content=item,
                        context=None,
                        entity_name=None,
                        item_info=item_info,
                    )

                    async with progress_lock:
                        completed_count += 1
                        if completed_count % max(1, total_items // 10) == 0 or completed_count == total_items:
                            progress = (completed_count / total_items) * 100
                            self.logger.info(f"Progress: {completed_count}/{total_items} ({progress:.1f}%)")

                    return {
                        "index": index,
                        "content_type": content_type,
                        "description": description,
                        "entity_info": entity_info,
                        "original_item": item,
                        "item_info": item_info,
                        "chunk_order_index": existing_chunks_count + index,
                        "processor": processor,
                        "file_path": file_path,
                    }

                except Exception as e:
                    self.logger.error(f"Error processing {item.get('type', 'unknown')} item {index}: {e}")
                    return None

        tasks = [
            asyncio.create_task(process_single_item(item, i))
            for i, item in enumerate(multimodal_items)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        multimodal_data_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Task failed: {result}")
                continue
            if result is not None:
                multimodal_data_list.append(result)

        if not multimodal_data_list:
            self.logger.warning("No valid multimodal descriptions generated")
            return

        self.logger.info(f"Generated descriptions for {len(multimodal_data_list)}/{len(multimodal_items)} items")

        # Convert to chunks and store
        if self.lightrag:
            await self._process_multimodal_with_lightrag(
                multimodal_data_list, file_path, doc_id
            )

    async def _process_multimodal_with_lightrag(
        self,
        multimodal_data_list: List[Dict[str, Any]],
        file_path: str,
        doc_id: str,
    ):
        """Process multimodal data with LightRAG integration."""
        chunks = {}
        file_ref = self._get_file_reference(file_path)

        for data in multimodal_data_list:
            description = data["description"]
            entity_info = data["entity_info"]
            chunk_order_index = data["chunk_order_index"]
            content_type = data["content_type"]
            original_item = data["original_item"]
            processor = data["processor"]

            formatted_content = processor.format_chunk(original_item, description)
            chunk_id = compute_mdhash_id(formatted_content, prefix="chunk-")

            tokens = len(formatted_content.split())  # Simple token estimation

            chunks[chunk_id] = {
                "content": formatted_content,
                "tokens": tokens,
                "full_doc_id": doc_id,
                "chunk_order_index": chunk_order_index,
                "file_path": file_ref,
                "llm_cache_list": [],
                "is_multimodal": True,
                "modal_entity_name": entity_info.get("entity_name", "unknown"),
                "original_type": content_type,
                "page_idx": data["item_info"].get("page_idx", 0),
            }

        if chunks:
            try:
                # Store in LightRAG storage
                await self.lightrag.text_chunks.upsert(chunks)
                await self.lightrag.chunks_vdb.upsert(chunks)

                # Update doc_status
                chunk_ids = list(chunks.keys())
                await self._update_doc_status_with_chunks(doc_id, chunk_ids)

                self.logger.info(f"Stored {len(chunks)} multimodal chunks to LightRAG")

            except Exception as e:
                self.logger.error(f"Error storing chunks: {e}")
                raise

    async def _update_doc_status_with_chunks(self, doc_id: str, chunk_ids: List[str]):
        """Update document status with multimodal chunks."""
        if not self.lightrag:
            return

        try:
            current_doc_status = await self.lightrag.doc_status.get_by_id(doc_id)

            if current_doc_status:
                existing_chunks_list = current_doc_status.get("chunks_list", [])
                existing_chunks_count = current_doc_status.get("chunks_count", 0)

                updated_chunks_list = existing_chunks_list + chunk_ids
                updated_chunks_count = existing_chunks_count + len(chunk_ids)

                await self.lightrag.doc_status.upsert({
                    doc_id: {
                        **current_doc_status,
                        "chunks_list": updated_chunks_list,
                        "chunks_count": updated_chunks_count,
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    }
                })

                await self.lightrag.doc_status.index_done_callback()
                self.logger.info(f"Updated doc_status with {len(chunk_ids)} multimodal chunks")

        except Exception as e:
            self.logger.warning(f"Error updating doc_status: {e}")

    async def _mark_multimodal_processing_complete(self, doc_id: str):
        """Mark multimodal content processing as complete."""
        if not self.lightrag:
            return

        try:
            current_doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
            if current_doc_status:
                await self.lightrag.doc_status.upsert({
                    doc_id: {
                        **current_doc_status,
                        "multimodal_processed": True,
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    }
                })
                await self.lightrag.doc_status.index_done_callback()
                self.logger.debug(f"Marked multimodal processing complete for {doc_id}")
        except Exception as e:
            self.logger.warning(f"Error marking multimodal complete for {doc_id}: {e}")

    # ========================================================================
    # MAIN PROCESSING METHODS
    # ========================================================================

    async def process_document(
        self,
        file_path: Union[str, Path],
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = None,
        split_by_character: str = None,
        split_by_character_only: bool = False,
        doc_id: str = None,
        file_name: str = None,
        **kwargs,
    ) -> ProcessingResult:
        """
        Complete document processing workflow.

        Args:
            file_path: Path to the file to process
            output_dir: Output directory for parser
            parse_method: Parse method to use
            display_stats: Whether to display content statistics
            split_by_character: Character to split text by
            split_by_character_only: If True, split only by character
            doc_id: Optional document ID
            file_name: Optional file name for reference
            **kwargs: Additional parser parameters

        Returns:
            ProcessingResult with extracted content and metadata
        """
        await self._ensure_lightrag_initialized()

        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if display_stats is None:
            display_stats = getattr(self.config, "display_content_stats", False)

        doc_start_time = time.time()
        self.logger.info(f"Starting complete document processing: {file_path}")

        try:
            # Step 1: Parse document
            content_list, content_based_doc_id = await self.parse_document(
                file_path, output_dir, parse_method, display_stats, **kwargs
            )

            if doc_id is None:
                doc_id = content_based_doc_id

            # Step 2: Separate text and multimodal content
            text_content, multimodal_items = separate_content(content_list)

            # Step 2.5: Set content source for context extraction
            if multimodal_items:
                self.logger.info("Setting content source for context-aware processing...")
                self.set_content_source_for_context(
                    content_list, getattr(self.config, "content_format", "auto")
                )

            # Step 3: Insert pure text content
            if text_content.strip() and self.lightrag:
                if file_name is None:
                    file_name = self._get_file_reference(str(file_path))

                text_insert_start = time.time()
                self.callback_manager.dispatch(
                    "on_text_insert_start",
                    file_path=str(file_path),
                    text_length=len(text_content),
                )

                from app.services.rag_patterns.pipeline.utils import insert_text_content
                await insert_text_content(
                    self.lightrag,
                    input=text_content,
                    file_paths=file_name,
                    split_by_character=split_by_character,
                    split_by_character_only=split_by_character_only,
                    ids=doc_id,
                )

                self.callback_manager.dispatch(
                    "on_text_insert_complete",
                    file_path=str(file_path),
                    duration_seconds=time.time() - text_insert_start,
                )
            else:
                if file_name is None:
                    file_name = self._get_file_reference(str(file_path))

            # Step 4: Process multimodal content
            if multimodal_items:
                await self._process_multimodal_content(multimodal_items, file_name, doc_id)
            else:
                await self._mark_multimodal_processing_complete(doc_id)
                self.logger.debug(f"No multimodal content in {doc_id}")

            doc_duration = time.time() - doc_start_time
            self.callback_manager.dispatch(
                "on_document_complete",
                file_path=str(file_path),
                doc_id=doc_id,
                duration_seconds=doc_duration,
            )
            self.logger.info(f"Document {file_path} processing complete!")

            return ProcessingResult(
                doc_id=doc_id,
                file_path=str(file_path),
                text_content=text_content,
                multimodal_items=multimodal_items,
                content_list=content_list,
                status=DocStatus.PROCESSED,
            )

        except Exception as e:
            self.callback_manager.dispatch(
                "on_document_error",
                file_path=str(file_path),
                error=e,
                stage="process_document",
            )
            raise

    async def insert_content_list(
        self,
        content_list: List[Dict[str, Any]],
        file_path: str = "unknown_document",
        split_by_character: str = None,
        split_by_character_only: bool = False,
        doc_id: str = None,
        display_stats: bool = None,
    ) -> ProcessingResult:
        """
        Insert content list directly without document parsing.

        Args:
            content_list: Pre-parsed content list
            file_path: Reference file path/name
            split_by_character: Character to split text by
            split_by_character_only: If True, split only by character
            doc_id: Optional document ID
            display_stats: Whether to display statistics

        Returns:
            ProcessingResult with processing details
        """
        await self._ensure_lightrag_initialized()

        if display_stats is None:
            display_stats = getattr(self.config, "display_content_stats", False)

        self.logger.info(f"Starting content list insertion for: {file_path}")

        if doc_id is None:
            doc_id = self._generate_content_based_doc_id(content_list)

        if display_stats:
            self.logger.info(f"* Total blocks: {len(content_list)}")
            block_types: Dict[str, int] = {}
            for block in content_list:
                if isinstance(block, dict):
                    block_type = block.get("type", "unknown")
                    block_types[block_type] = block_types.get(block_type, 0) + 1
            for block_type, count in block_types.items():
                self.logger.info(f"  - {block_type}: {count}")

        text_content, multimodal_items = separate_content(content_list)

        if multimodal_items:
            self.set_content_source_for_context(
                content_list, getattr(self.config, "content_format", "auto")
            )

        if text_content.strip() and self.lightrag:
            file_ref = self._get_file_reference(file_path)
            from app.services.rag_patterns.pipeline.utils import insert_text_content
            await insert_text_content(
                self.lightrag,
                input=text_content,
                file_paths=file_ref,
                split_by_character=split_by_character,
                split_by_character_only=split_by_character_only,
                ids=doc_id,
            )
        else:
            file_ref = self._get_file_reference(file_path)

        if multimodal_items:
            await self._process_multimodal_content(multimodal_items, file_ref, doc_id)
        else:
            await self._mark_multimodal_processing_complete(doc_id)

        self.logger.info(f"Content list insertion complete for: {file_path}")

        return ProcessingResult(
            doc_id=doc_id,
            file_path=file_path,
            text_content=text_content,
            multimodal_items=multimodal_items,
            content_list=content_list,
            status=DocStatus.PROCESSED,
        )

    # ========================================================================
    # STATUS CHECKING
    # ========================================================================

    async def is_document_fully_processed(self, doc_id: str) -> bool:
        """Check if document is fully processed (text + multimodal)."""
        if not self.lightrag:
            return False

        try:
            doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
            if not doc_status:
                return False

            text_processed = doc_status.get("status") == DocStatus.PROCESSED
            multimodal_processed = doc_status.get("multimodal_processed", False)
            return text_processed and multimodal_processed

        except Exception as e:
            self.logger.error(f"Error checking status for {doc_id}: {e}")
            return False

    async def get_document_processing_status(self, doc_id: str) -> Dict[str, Any]:
        """Get detailed processing status for a document."""
        if not self.lightrag:
            return {
                "exists": False,
                "text_processed": False,
                "multimodal_processed": False,
                "fully_processed": False,
                "chunks_count": 0,
            }

        try:
            doc_status = await self.lightrag.doc_status.get_by_id(doc_id)
            if not doc_status:
                return {
                    "exists": False,
                    "text_processed": False,
                    "multimodal_processed": False,
                    "fully_processed": False,
                    "chunks_count": 0,
                }

            text_processed = doc_status.get("status") == DocStatus.PROCESSED
            multimodal_processed = doc_status.get("multimodal_processed", False)
            fully_processed = text_processed and multimodal_processed

            return {
                "exists": True,
                "text_processed": text_processed,
                "multimodal_processed": multimodal_processed,
                "fully_processed": fully_processed,
                "chunks_count": doc_status.get("chunks_count", 0),
                "chunks_list": doc_status.get("chunks_list", []),
                "status": doc_status.get("status", ""),
                "updated_at": doc_status.get("updated_at", ""),
                "raw_status": doc_status,
            }

        except Exception as e:
            self.logger.error(f"Error getting status for {doc_id}: {e}")
            return {
                "exists": False,
                "error": str(e),
                "text_processed": False,
                "multimodal_processed": False,
                "fully_processed": False,
                "chunks_count": 0,
            }

    def get_processor_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            "parser_installed": self.check_parser_installation() if self._parser else False,
            "config": {
                "parser": self.config.parser,
                "parse_method": self.config.parse_method,
                "working_dir": self.config.working_dir,
            },
            "models": {
                "llm_model": "Provided" if self.llm_func else "Not provided",
                "vision_model": "Provided" if self.vision_func else "Not provided",
                "embedding_model": "Provided" if self.embedding_func else "Not provided",
            },
            "processors": list(self.modal_processors.keys()) if self.modal_processors else [],
            "lightrag_initialized": self.lightrag is not None,
        }

    async def finalize_storages(self):
        """Finalize all storages including parse cache and LightRAG storages."""
        try:
            tasks = []

            if self.parse_cache is not None:
                tasks.append(self.parse_cache.finalize())
                self.logger.debug("Scheduled parse cache finalization")

            if self.lightrag is not None:
                tasks.append(self.lightrag.finalize_storages())
                self.logger.debug("Scheduled LightRAG storages finalization")

            if tasks:
                await asyncio.gather(*tasks)
                self.logger.info("Successfully finalized all RAGPipeline storages")

        except Exception as e:
            self.logger.error(f"Error during storage finalization: {e}")
            raise


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RAGPipeline",
    "compute_mdhash_id",
]

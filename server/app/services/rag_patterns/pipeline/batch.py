"""
Batch Processing for RAG Pipeline

This module provides batch processing functionality for documents:
- BatchParser: Synchronous and async batch parsing
- BatchProcessor: Batch document processing with RAG integration
- BatchProcessingResult: Results container for batch operations

Migrated from raganything/batch.py and raganything/batch_parser.py
"""

import os
import asyncio
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.rag_patterns.pipeline.parsers import ParserFactory, MineruParser, DoclingParser
from app.services.rag_patterns.pipeline.config import RAGConfig

logger = logging.getLogger(__name__)


# ============================================================================
# BATCH PROCESSING RESULTS
# ============================================================================


@dataclass
class BatchProcessingResult:
    """Result container for batch processing operations."""
    successful_files: List[str] = field(default_factory=list)
    failed_files: List[Tuple[str, str]] = field(default_factory=list)
    total_files: int = 0
    processing_time: float = 0.0
    results: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_count(self) -> int:
        return len(self.successful_files)
    
    @property
    def failure_count(self) -> int:
        return len(self.failed_files)
    
    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.success_count / self.total_files * 100
    
    def summary(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "successful": self.success_count,
            "failed": self.failure_count,
            "success_rate": f"{self.success_rate:.1f}%",
            "processing_time": f"{self.processing_time:.2f}s",
        }


# ============================================================================
# BATCH PARSER
# ============================================================================


class BatchParser:
    """
    Batch document parser.
    
    Handles parsing of multiple documents with parallel processing support.
    
    Example:
        >>> parser = BatchParser(parser_type="mineru", max_workers=4)
        >>> result = parser.process_batch(["doc1.pdf", "doc2.pdf"])
    """
    
    # Supported file extensions by category
    SUPPORTED_EXTENSIONS = {
        "pdf": [".pdf"],
        "image": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"],
        "office": [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"],
        "html": [".html", ".htm", ".xhtml"],
        "text": [".txt", ".md", ".rst", ".csv", ".json"],
    }
    
    def __init__(
        self,
        parser_type: str = "mineru",
        max_workers: int = 4,
        show_progress: bool = True,
        skip_installation_check: bool = False,
    ):
        """
        Initialize batch parser.
        
        Args:
            parser_type: Parser type ("mineru" or "docling")
            max_workers: Maximum parallel workers
            show_progress: Show progress during processing
            skip_installation_check: Skip parser installation check
        """
        self.parser_type = parser_type
        self.max_workers = max_workers
        self.show_progress = show_progress
        self.skip_installation_check = skip_installation_check
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self._parser = None
    
    def _get_parser(self):
        """Get or create parser instance."""
        if self._parser is None:
            if self.parser_type == "docling":
                self._parser = DoclingParser()
            else:
                self._parser = MineruParser()
        return self._parser
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        extensions = []
        for ext_list in self.SUPPORTED_EXTENSIONS.values():
            extensions.extend(ext_list)
        return extensions
    
    def is_supported_file(self, file_path: Union[str, Path]) -> bool:
        """Check if file is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in self.get_supported_extensions()
    
    def filter_supported_files(
        self, 
        file_paths: List[str], 
        recursive: bool = False
    ) -> List[str]:
        """Filter paths to only include supported files."""
        supported = []
        
        for path_str in file_paths:
            path = Path(path_str)
            
            if path.is_file():
                if self.is_supported_file(path):
                    supported.append(str(path))
            elif path.is_dir():
                pattern = "**/*" if recursive else "*"
                for file_path in path.glob(pattern):
                    if file_path.is_file() and self.is_supported_file(file_path):
                        supported.append(str(file_path))
        
        return supported
    
    def _parse_single_file(
        self,
        file_path: str,
        output_dir: str,
        parse_method: str,
        **kwargs,
    ) -> Tuple[bool, str, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Parse a single file.
        
        Returns:
            Tuple of (success, file_path, content_list, error_message)
        """
        try:
            parser = self._get_parser()
            file_path_obj = Path(file_path)
            ext = file_path_obj.suffix.lower()
            
            if ext in self.SUPPORTED_EXTENSIONS["pdf"]:
                content_list = parser.parse_pdf(
                    pdf_path=file_path,
                    output_dir=output_dir,
                    method=parse_method,
                    **kwargs,
                )
            elif ext in self.SUPPORTED_EXTENSIONS["image"]:
                content_list = parser.parse_image(
                    image_path=file_path,
                    output_dir=output_dir,
                    **kwargs,
                )
            elif ext in self.SUPPORTED_EXTENSIONS["office"] + self.SUPPORTED_EXTENSIONS["html"]:
                content_list = parser.parse_office_doc(
                    doc_path=file_path,
                    output_dir=output_dir,
                    **kwargs,
                )
            else:
                content_list = parser.parse_document(
                    file_path=file_path,
                    method=parse_method,
                    output_dir=output_dir,
                    **kwargs,
                )
            
            return True, file_path, content_list, None
            
        except Exception as e:
            return False, file_path, None, str(e)
    
    def process_batch(
        self,
        file_paths: List[str],
        output_dir: str = None,
        parse_method: str = "auto",
        recursive: bool = False,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Process multiple files in batch synchronously.
        
        Args:
            file_paths: List of file paths or directories
            output_dir: Output directory for parsed results
            parse_method: Parsing method to use
            recursive: Process directories recursively
            **kwargs: Additional parser arguments
            
        Returns:
            BatchProcessingResult with processing details
        """
        start_time = time.time()
        
        # Filter and collect files
        filtered_files = self.filter_supported_files(file_paths, recursive)
        
        if not filtered_files:
            self.logger.warning("No supported files found")
            return BatchProcessingResult(total_files=0)
        
        self.logger.info(f"Starting batch processing of {len(filtered_files)} files")
        
        result = BatchProcessingResult(total_files=len(filtered_files))
        
        # Process with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._parse_single_file,
                    file_path,
                    output_dir or str(Path(file_path).parent),
                    parse_method,
                    **kwargs,
                ): file_path
                for file_path in filtered_files
            }
            
            completed = 0
            for future in as_completed(futures):
                success, file_path, content_list, error = future.result()
                completed += 1
                
                if self.show_progress:
                    progress = completed / len(filtered_files) * 100
                    self.logger.info(f"Progress: {completed}/{len(filtered_files)} ({progress:.1f}%)")
                
                if success:
                    result.successful_files.append(file_path)
                    result.results[file_path] = content_list
                else:
                    result.failed_files.append((file_path, error))
        
        result.processing_time = time.time() - start_time
        self.logger.info(f"Batch processing complete in {result.processing_time:.2f}s")
        
        return result
    
    async def process_batch_async(
        self,
        file_paths: List[str],
        output_dir: str = None,
        parse_method: str = "auto",
        recursive: bool = False,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Process multiple files in batch asynchronously.
        
        Args:
            file_paths: List of file paths or directories
            output_dir: Output directory for parsed results
            parse_method: Parsing method to use
            recursive: Process directories recursively
            **kwargs: Additional parser arguments
            
        Returns:
            BatchProcessingResult with processing details
        """
        start_time = time.time()
        
        # Filter and collect files
        filtered_files = self.filter_supported_files(file_paths, recursive)
        
        if not filtered_files:
            self.logger.warning("No supported files found")
            return BatchProcessingResult(total_files=0)
        
        self.logger.info(f"Starting async batch processing of {len(filtered_files)} files")
        
        result = BatchProcessingResult(total_files=len(filtered_files))
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_file(file_path: str):
            async with semaphore:
                return await asyncio.to_thread(
                    self._parse_single_file,
                    file_path,
                    output_dir or str(Path(file_path).parent),
                    parse_method,
                    **kwargs,
                )
        
        tasks = [process_file(fp) for fp in filtered_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                file_path = filtered_files[i]
                result.failed_files.append((file_path, str(res)))
            else:
                success, file_path, content_list, error = res
                if success:
                    result.successful_files.append(file_path)
                    result.results[file_path] = content_list
                else:
                    result.failed_files.append((file_path, error))
        
        result.processing_time = time.time() - start_time
        self.logger.info(f"Async batch processing complete in {result.processing_time:.2f}s")
        
        return result


# ============================================================================
# BATCH PROCESSOR (Mixin-style functionality)
# ============================================================================


@dataclass
class BatchProcessor:
    """
    Batch document processor with RAG integration.
    
    Combines batch parsing with RAG processing for complete workflow.
    
    Example:
        >>> processor = BatchProcessor(config=config, pipeline=pipeline)
        >>> result = await processor.process_folder("/documents")
    """
    
    config: Optional[RAGConfig] = None
    pipeline: Optional[Any] = None
    
    def __post_init__(self):
        """Initialize batch processor."""
        if self.config is None:
            self.config = RAGConfig.from_server_settings()
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self._batch_parser = None
    
    def _get_batch_parser(self) -> BatchParser:
        """Get or create batch parser."""
        if self._batch_parser is None:
            self._batch_parser = BatchParser(
                parser_type=self.config.parser,
                max_workers=getattr(self.config, "max_concurrent_files", 4),
                show_progress=True,
            )
        return self._batch_parser
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return self._get_batch_parser().get_supported_extensions()
    
    def filter_supported_files(
        self, 
        file_paths: List[str], 
        recursive: bool = None
    ) -> List[str]:
        """Filter paths to include only supported files."""
        if recursive is None:
            recursive = getattr(self.config, "recursive_folder_processing", False)
        return self._get_batch_parser().filter_supported_files(file_paths, recursive)
    
    async def process_folder(
        self,
        folder_path: str,
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = True,
        split_by_character: str = None,
        split_by_character_only: bool = False,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = None,
        max_workers: int = None,
    ) -> BatchProcessingResult:
        """
        Process all supported files in a folder.
        
        Args:
            folder_path: Path to folder containing files
            output_dir: Output directory for parsed files
            parse_method: Parsing method to use
            display_stats: Whether to display statistics
            split_by_character: Character to split text by
            split_by_character_only: Split only by character
            file_extensions: File extensions to process
            recursive: Process subdirectories
            max_workers: Maximum concurrent workers
            
        Returns:
            BatchProcessingResult with processing details
        """
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if file_extensions is None:
            file_extensions = getattr(
                self.config, 
                "supported_file_extensions",
                self._get_batch_parser().get_supported_extensions()
            )
        if recursive is None:
            recursive = getattr(self.config, "recursive_folder_processing", False)
        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrent_files", 4)
        
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        # Collect files based on extensions
        files_to_process = []
        for file_ext in file_extensions:
            pattern = f"**/*{file_ext}" if recursive else f"*{file_ext}"
            files_to_process.extend(folder_path_obj.glob(pattern))
        
        if not files_to_process:
            self.logger.warning(f"No supported files found in {folder_path}")
            return BatchProcessingResult(total_files=0)
        
        self.logger.info(f"Found {len(files_to_process)} files to process")
        
        start_time = time.time()
        result = BatchProcessingResult(total_files=len(files_to_process))
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process with semaphore control
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_single_file(file_path: Path) -> Tuple[bool, str, Optional[str]]:
            async with semaphore:
                is_in_subdir = len(file_path.relative_to(folder_path_obj).parents) > 1
                
                try:
                    if self.pipeline:
                        await self.pipeline.process_document(
                            str(file_path),
                            output_dir=(
                                output_dir
                                if not is_in_subdir
                                else str(output_path / file_path.parent.relative_to(folder_path_obj))
                            ),
                            parse_method=parse_method,
                            split_by_character=split_by_character,
                            split_by_character_only=split_by_character_only,
                            file_name=(
                                None
                                if not is_in_subdir
                                else str(file_path.relative_to(folder_path_obj))
                            ),
                        )
                    else:
                        # Just parse without RAG if no pipeline
                        parser = self._get_batch_parser()._get_parser()
                        await asyncio.to_thread(
                            parser.parse_document,
                            file_path=str(file_path),
                            method=parse_method,
                            output_dir=output_dir,
                        )
                    
                    return True, str(file_path), None
                    
                except Exception as e:
                    self.logger.error(f"Failed to process {file_path}: {str(e)}")
                    return False, str(file_path), str(e)
        
        # Create and run tasks
        tasks = [asyncio.create_task(process_single_file(fp)) for fp in files_to_process]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for res in task_results:
            if isinstance(res, Exception):
                result.failed_files.append(("unknown", str(res)))
            else:
                success, file_path, error = res
                if success:
                    result.successful_files.append(file_path)
                else:
                    result.failed_files.append((file_path, error))
        
        result.processing_time = time.time() - start_time
        
        # Display stats
        if display_stats:
            self.logger.info("Batch processing complete!")
            self.logger.info(f"  Successful: {result.success_count} files")
            self.logger.info(f"  Failed: {result.failure_count} files")
            self.logger.info(f"  Time: {result.processing_time:.2f}s")
            
            if result.failed_files:
                self.logger.warning("Failed files:")
                for file_path, error in result.failed_files:
                    self.logger.warning(f"  - {file_path}: {error}")
        
        return result
    
    def process_documents_batch(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Process multiple documents in batch (synchronous).
        
        Args:
            file_paths: List of file paths or directories
            output_dir: Output directory
            parse_method: Parsing method
            max_workers: Maximum workers
            recursive: Process directories recursively
            show_progress: Show progress
            **kwargs: Additional arguments
            
        Returns:
            BatchProcessingResult
        """
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrent_files", 4)
        if recursive is None:
            recursive = getattr(self.config, "recursive_folder_processing", False)
        
        batch_parser = BatchParser(
            parser_type=self.config.parser,
            max_workers=max_workers,
            show_progress=show_progress,
            skip_installation_check=True,
        )
        
        return batch_parser.process_batch(
            file_paths=file_paths,
            output_dir=output_dir,
            parse_method=parse_method,
            recursive=recursive,
            **kwargs,
        )
    
    async def process_documents_batch_async(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Process multiple documents in batch (asynchronous).
        
        Args:
            file_paths: List of file paths or directories
            output_dir: Output directory
            parse_method: Parsing method
            max_workers: Maximum workers
            recursive: Process directories recursively
            show_progress: Show progress
            **kwargs: Additional arguments
            
        Returns:
            BatchProcessingResult
        """
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrent_files", 4)
        if recursive is None:
            recursive = getattr(self.config, "recursive_folder_processing", False)
        
        batch_parser = BatchParser(
            parser_type=self.config.parser,
            max_workers=max_workers,
            show_progress=show_progress,
            skip_installation_check=True,
        )
        
        return await batch_parser.process_batch_async(
            file_paths=file_paths,
            output_dir=output_dir,
            parse_method=parse_method,
            recursive=recursive,
            **kwargs,
        )
    
    async def process_documents_with_rag(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process documents and add to RAG.
        
        Combines parsing and RAG insertion workflow.
        
        Args:
            file_paths: List of file paths or directories
            output_dir: Output directory
            parse_method: Parsing method
            max_workers: Maximum workers
            recursive: Process directories recursively
            show_progress: Show progress
            **kwargs: Additional arguments
            
        Returns:
            Dict with parse and RAG results
        """
        start_time = time.time()
        
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrent_files", 4)
        if recursive is None:
            recursive = getattr(self.config, "recursive_folder_processing", False)
        
        self.logger.info("Starting batch processing with RAG integration")
        
        # Step 1: Parse documents
        parse_result = self.process_documents_batch(
            file_paths=file_paths,
            output_dir=output_dir,
            parse_method=parse_method,
            max_workers=max_workers,
            recursive=recursive,
            show_progress=show_progress,
            **kwargs,
        )
        
        # Step 2: Process with RAG if pipeline available
        rag_results = {}
        
        if self.pipeline and parse_result.successful_files:
            self.logger.info(f"Processing {len(parse_result.successful_files)} files with RAG")
            
            for file_path in parse_result.successful_files:
                try:
                    await self.pipeline.process_document(
                        file_path,
                        output_dir=output_dir,
                        parse_method=parse_method,
                        **kwargs,
                    )
                    rag_results[file_path] = {"status": "success", "processed": True}
                    
                except Exception as e:
                    self.logger.error(f"Failed to process {file_path} with RAG: {str(e)}")
                    rag_results[file_path] = {
                        "status": "failed",
                        "error": str(e),
                        "processed": False,
                    }
        
        processing_time = time.time() - start_time
        
        return {
            "parse_result": parse_result,
            "rag_results": rag_results,
            "total_processing_time": processing_time,
            "successful_rag_files": len([r for r in rag_results.values() if r.get("processed")]),
            "failed_rag_files": len([r for r in rag_results.values() if not r.get("processed")]),
        }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BatchParser",
    "BatchProcessor",
    "BatchProcessingResult",
]

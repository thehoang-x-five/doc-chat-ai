"""
Utility Functions for RAG Pipeline

Contains helper functions for:
- Content separation (text vs multimodal)
- Text content insertion into LightRAG
- Processor utilities
- Image/file validation

Migrated from raganything/utils.py with server adaptations
"""

import os
import base64
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# CONTENT SEPARATION
# ============================================================================


def separate_content(
    content_list: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Separate text content and multimodal content from parsed document.

    Args:
        content_list: Content list from parser (MinerU/Docling)

    Returns:
        Tuple of (text_content, multimodal_items):
            - text_content: Merged pure text content
            - multimodal_items: List of multimodal items (images, tables, equations)
    """
    text_parts = []
    multimodal_items = []

    for item in content_list:
        content_type = item.get("type", "text")

        if content_type == "text":
            text = item.get("text", "")
            if text.strip():
                text_parts.append(text)
        else:
            # Multimodal content (image, table, equation, etc.)
            multimodal_items.append(item)

    # Merge all text content
    text_content = "\n\n".join(text_parts)

    logger.info("Content separation complete:")
    logger.info(f"  - Text content length: {len(text_content)} characters")
    logger.info(f"  - Multimodal items count: {len(multimodal_items)}")

    # Count multimodal types for logging
    modal_types = {}
    for item in multimodal_items:
        modal_type = item.get("type", "unknown")
        modal_types[modal_type] = modal_types.get(modal_type, 0) + 1

    if modal_types:
        logger.info(f"  - Multimodal type distribution: {modal_types}")

    return text_content, multimodal_items


# ============================================================================
# TEXT INSERTION FUNCTIONS
# ============================================================================


async def insert_text_content(
    lightrag,
    input: Union[str, List[str]],
    split_by_character: Optional[str] = None,
    split_by_character_only: bool = False,
    ids: Optional[Union[str, List[str]]] = None,
    file_paths: Optional[Union[str, List[str]]] = None,
):
    """
    Insert pure text content into LightRAG.

    Args:
        lightrag: LightRAG instance
        input: Single document string or list of document strings
        split_by_character: Optional character to split text by
        split_by_character_only: If True, split only by character
        ids: Document ID(s), MD5 hash generated if not provided
        file_paths: File path(s) for citation
    """
    logger.info("Starting text content insertion into LightRAG...")

    await lightrag.ainsert(
        input=input,
        file_paths=file_paths,
        split_by_character=split_by_character,
        split_by_character_only=split_by_character_only,
        ids=ids,
    )

    logger.info("Text content insertion complete")


async def insert_text_content_with_multimodal_content(
    lightrag,
    input: Union[str, List[str]],
    multimodal_content: Optional[List[Dict[str, Any]]] = None,
    split_by_character: Optional[str] = None,
    split_by_character_only: bool = False,
    ids: Optional[Union[str, List[str]]] = None,
    file_paths: Optional[Union[str, List[str]]] = None,
    scheme_name: Optional[str] = None,
):
    """
    Insert text content with multimodal content into LightRAG.

    Args:
        lightrag: LightRAG instance
        input: Single document string or list of document strings
        multimodal_content: Multimodal content list (optional)
        split_by_character: Optional character to split text by
        split_by_character_only: If True, split only by character
        ids: Document ID(s), MD5 hash generated if not provided
        file_paths: File path(s) for citation
        scheme_name: Scheme name (optional)
    """
    logger.info("Starting text content insertion with multimodal into LightRAG...")

    try:
        await lightrag.ainsert(
            input=input,
            multimodal_content=multimodal_content,
            file_paths=file_paths,
            split_by_character=split_by_character,
            split_by_character_only=split_by_character_only,
            ids=ids,
            scheme_name=scheme_name,
        )
    except TypeError as e:
        # Handle case where LightRAG doesn't support multimodal_content parameter
        logger.warning(f"ainsert may not support multimodal_content: {e}")
        logger.info("Falling back to standard insert without multimodal content")
        await lightrag.ainsert(
            input=input,
            file_paths=file_paths,
            split_by_character=split_by_character,
            split_by_character_only=split_by_character_only,
            ids=ids,
        )
    except Exception as e:
        logger.error(f"Error during text insertion: {e}")
        raise

    logger.info("Text content insertion complete")


# ============================================================================
# PROCESSOR UTILITIES
# ============================================================================


def get_processor_for_type(
    modal_processors: Dict[str, Any], 
    content_type: str
) -> Optional[Any]:
    """
    Get appropriate processor based on content type.

    Args:
        modal_processors: Dictionary of available processors
        content_type: Content type (image, table, equation, etc.)

    Returns:
        Corresponding processor instance or None
    """
    # Direct mapping to corresponding processor
    if content_type == "image":
        return modal_processors.get("image")
    elif content_type == "table":
        return modal_processors.get("table")
    elif content_type == "equation":
        return modal_processors.get("equation")
    else:
        # For other types, use generic processor
        return modal_processors.get("generic")


def get_processor_supports(proc_type: str) -> List[str]:
    """
    Get processor supported features.

    Args:
        proc_type: Processor type (image, table, equation, generic)

    Returns:
        List of supported feature descriptions
    """
    supports_map = {
        "image": [
            "Image content analysis",
            "Visual understanding",
            "Image description generation",
            "Image entity extraction",
        ],
        "table": [
            "Table structure analysis",
            "Data statistics",
            "Trend identification",
            "Table entity extraction",
        ],
        "equation": [
            "Mathematical formula parsing",
            "Variable identification",
            "Formula meaning explanation",
            "Formula entity extraction",
        ],
        "generic": [
            "General content analysis",
            "Structured processing",
            "Entity extraction",
        ],
    }
    return supports_map.get(proc_type, ["Basic processing"])


# ============================================================================
# IMAGE UTILITIES
# ============================================================================


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image file to base64 string.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string, empty string if encoding fails
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return ""


def validate_image_file(image_path: str, max_size_mb: int = 50) -> bool:
    """
    Validate if a file is a valid image file.

    Args:
        image_path: Path to the image file
        max_size_mb: Maximum file size in MB

    Returns:
        True if valid, False otherwise
    """
    try:
        path = Path(image_path)

        logger.debug(f"Validating image path: {image_path}")

        # Check if file exists
        if not path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return False

        # Check file extension
        image_extensions = [
            ".jpg", ".jpeg", ".png", ".gif",
            ".bmp", ".webp", ".tiff", ".tif",
        ]

        path_lower = str(path).lower()
        has_valid_extension = any(path_lower.endswith(ext) for ext in image_extensions)

        if not has_valid_extension:
            logger.warning(f"File does not appear to be an image: {image_path}")
            return False

        # Check file size
        file_size = path.stat().st_size
        max_size = max_size_mb * 1024 * 1024

        if file_size > max_size:
            logger.warning(f"Image file too large ({file_size} bytes): {image_path}")
            return False

        logger.debug(f"Image validation successful: {image_path}")
        return True

    except Exception as e:
        logger.error(f"Error validating image file {image_path}: {e}")
        return False


def get_image_mime_type(image_path: str) -> str:
    """
    Get MIME type for an image file.

    Args:
        image_path: Path to image file

    Returns:
        MIME type string
    """
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mime_types.get(ext, "image/jpeg")


# ============================================================================
# HASH UTILITIES
# ============================================================================


def compute_mdhash_id(content: str, prefix: str = "") -> str:
    """
    Compute a hash-based ID for content.

    Args:
        content: Content to hash
        prefix: Optional prefix for the ID

    Returns:
        Hash-based ID string
    """
    hash_obj = hashlib.md5(content.encode("utf-8"))
    return f"{prefix}{hash_obj.hexdigest()}"


def compute_file_hash(file_path: str) -> str:
    """
    Compute MD5 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        MD5 hash string
    """
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5()
            for chunk in iter(lambda: f.read(8192), b""):
                file_hash.update(chunk)
        return file_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error computing file hash: {e}")
        return ""


# ============================================================================
# FILE UTILITIES
# ============================================================================


def get_file_extension(file_path: str) -> str:
    """Get lowercase file extension."""
    return Path(file_path).suffix.lower()


def get_file_basename(file_path: str) -> str:
    """Get file basename without directory."""
    return os.path.basename(file_path)


def ensure_directory(directory_path: str) -> Path:
    """
    Ensure directory exists, create if needed.

    Args:
        directory_path: Path to directory

    Returns:
        Path object
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_supported_document(file_path: str) -> bool:
    """
    Check if file is a supported document type.

    Args:
        file_path: Path to file

    Returns:
        True if supported
    """
    supported_extensions = {
        ".pdf", ".doc", ".docx", ".ppt", ".pptx",
        ".xls", ".xlsx", ".html", ".htm", ".xhtml",
        ".txt", ".md", ".rst", ".csv", ".json",
        ".jpg", ".jpeg", ".png", ".bmp", ".tiff",
        ".tif", ".gif", ".webp",
    }
    return get_file_extension(file_path) in supported_extensions


# ============================================================================
# CONTENT UTILITIES
# ============================================================================


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    import re
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def count_tokens_approximate(text: str) -> int:
    """
    Approximate token count (simple word-based estimation).

    Args:
        text: Text to count tokens for

    Returns:
        Approximate token count
    """
    # Simple approximation: 1 token ≈ 0.75 words (4 characters)
    return max(1, len(text) // 4)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Content separation
    "separate_content",
    # Text insertion
    "insert_text_content",
    "insert_text_content_with_multimodal_content",
    # Processor utilities
    "get_processor_for_type",
    "get_processor_supports",
    # Image utilities
    "encode_image_to_base64",
    "validate_image_file",
    "get_image_mime_type",
    # Hash utilities
    "compute_mdhash_id",
    "compute_file_hash",
    # File utilities
    "get_file_extension",
    "get_file_basename",
    "ensure_directory",
    "is_supported_document",
    # Content utilities
    "truncate_text",
    "clean_text",
    "count_tokens_approximate",
]

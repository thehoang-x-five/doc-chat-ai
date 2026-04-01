"""
File validation utilities.
"""
import mimetypes
from pathlib import Path
from typing import Set, Tuple, Optional

from app.core.config import settings


# Allowed file extensions
ALLOWED_EXTENSIONS: Set[str] = {
    # Documents
    "pdf", "docx", "pptx", "xlsx",
    # Images
    "jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp", "gif",
    # Text / Markup
    "txt", "md", "csv", "html", "xhtml",
}

# Blocked extensions (executables, scripts)
BLOCKED_EXTENSIONS: Set[str] = {
    "exe", "bat", "cmd", "sh", "ps1", "vbs", "js",
    "msi", "dll", "so", "dylib",
    "php", "py", "rb", "pl",
}

# MIME type mapping
MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "html": "text/html",
    "xhtml": "application/xhtml+xml",
}

# Default max file size (50MB)
DEFAULT_MAX_SIZE = 50 * 1024 * 1024


class FileValidationError(Exception):
    """File validation error."""
    pass


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    return Path(filename).suffix.lower().lstrip(".")


def validate_file_type(filename: str) -> Tuple[bool, str]:
    """
    Validate file type against allowed extensions.
    
    Args:
        filename: Original filename
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    ext = get_file_extension(filename)
    
    if not ext:
        return False, "File has no extension"
    
    if ext in BLOCKED_EXTENSIONS:
        return False, f"File type '{ext}' is not allowed (executable)"
    
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' is not supported"
    
    return True, ""


def validate_file_size(size: int, max_size: int = None) -> Tuple[bool, str]:
    """
    Validate file size.
    
    Args:
        size: File size in bytes
        max_size: Maximum allowed size (default from settings)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    max_size = max_size or DEFAULT_MAX_SIZE
    
    if size <= 0:
        return False, "File is empty"
    
    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"File exceeds maximum size of {max_mb:.0f}MB"
    
    return True, ""


def detect_mime_type(filename: str, content: bytes = None) -> str:
    """
    Detect MIME type from filename and optionally content.
    
    Args:
        filename: Original filename
        content: File content (optional, for magic number detection)
        
    Returns:
        MIME type string
    """
    ext = get_file_extension(filename)
    
    # Try our mapping first
    if ext in MIME_TYPES:
        return MIME_TYPES[ext]
    
    # Fall back to mimetypes module
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return mime_type
    
    # Default
    return "application/octet-stream"


def get_document_type(filename: str) -> str:
    """
    Get document type category from filename.
    
    Args:
        filename: Original filename
        
    Returns:
        Document type (pdf, docx, image, txt, etc.)
    """
    ext = get_file_extension(filename)
    
    if ext == "pdf":
        return "pdf"
    elif ext == "docx":
        return "docx"
    elif ext == "xlsx":
        return "xlsx"
    elif ext == "pptx":
        return "pptx"
    elif ext in ["jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "gif"]:
        return "image"
    elif ext in ["txt", "md"]:
        return "txt"
    elif ext == "csv":
        return "csv"
    elif ext in ["html", "xhtml"]:
        return "html"
    else:
        return "unknown"


def validate_file(
    filename: str,
    size: int,
    max_size: int = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate file type and size.
    
    Args:
        filename: Original filename
        size: File size in bytes
        max_size: Maximum allowed size
        
    Returns:
        Tuple of (is_valid, error_message or None)
    """
    # Validate type
    type_valid, type_error = validate_file_type(filename)
    if not type_valid:
        return False, type_error
    
    # Validate size
    size_valid, size_error = validate_file_size(size, max_size)
    if not size_valid:
        return False, size_error
    
    return True, None


# =============================================================================
# TEXT VALIDATION - SQL INJECTION, PROMPT INJECTION, PII DETECTION
# =============================================================================

import re
import logging
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    r"\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b",
    r"--",  # SQL comment
    r"/\*.*?\*/",  # Multi-line comment
    r";\s*(DROP|DELETE|UPDATE|INSERT)",  # Dangerous commands after semicolon
    r"'\s*(OR|AND)\s*'?\d*'?\s*=\s*'?\d*",  # OR 1=1, AND 1=1
    r"(xp_|sp_)\w+",  # SQL Server stored procedures
]

# Prompt Injection patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now",
    r"system\s*:",
    r"<\|im_start\|>",  # ChatML format
    r"<\|im_end\|>",
    r"\[INST\]",  # Llama format
    r"\[/INST\]",
    r"jailbreak",
    r"DAN\s+mode",  # Do Anything Now
    r"developer\s+mode",
]

# PII patterns
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}


@dataclass
class SecurityViolation:
    """Security violation detected in text."""
    type: str  # "sql_injection", "prompt_injection"
    pattern: str
    matched_text: str
    severity: str  # "high", "medium", "low"
    position: Tuple[int, int]


@dataclass
class PIIMatch:
    """PII detected in text."""
    type: str  # "email", "phone", "credit_card", "ssn"
    original: str
    masked: str
    position: Tuple[int, int]


@dataclass
class ValidationResult:
    """Result of text validation."""
    is_valid: bool
    sanitized_text: str
    violations: List[SecurityViolation]
    pii_detected: List[PIIMatch]
    error_message: Optional[str] = None


def detect_sql_injection(text: str) -> List[SecurityViolation]:
    """
    Detect SQL injection patterns in text.
    
    Args:
        text: Input text to check
        
    Returns:
        List of SecurityViolation objects
    """
    violations = []
    
    for pattern in SQL_INJECTION_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            violations.append(SecurityViolation(
                type="sql_injection",
                pattern=pattern,
                matched_text=match.group(),
                severity="high",
                position=(match.start(), match.end())
            ))
    
    return violations


def detect_prompt_injection(text: str) -> List[SecurityViolation]:
    """
    Detect prompt injection patterns in text.
    
    Args:
        text: Input text to check
        
    Returns:
        List of SecurityViolation objects
    """
    violations = []
    
    for pattern in PROMPT_INJECTION_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            violations.append(SecurityViolation(
                type="prompt_injection",
                pattern=pattern,
                matched_text=match.group(),
                severity="high",
                position=(match.start(), match.end())
            ))
    
    return violations


def detect_and_mask_pii(text: str) -> Tuple[str, List[PIIMatch]]:
    """
    Detect and mask PII in text.
    
    Args:
        text: Input text to check
        
    Returns:
        Tuple of (sanitized_text, list of PIIMatch objects)
    """
    pii_matches = []
    sanitized = text
    offset = 0  # Track position changes due to masking
    
    for pii_type, pattern in PII_PATTERNS.items():
        matches = list(re.finditer(pattern, text))
        for match in matches:
            original = match.group()
            
            # Create mask based on type
            if pii_type == "email":
                parts = original.split("@")
                masked = f"{parts[0][0]}***@{parts[1]}" if len(parts) == 2 else "***@***.***"
            elif pii_type == "phone":
                masked = "***-***-" + original[-4:] if len(original) >= 4 else "***-***-****"
            elif pii_type == "credit_card":
                masked = "****-****-****-" + original.replace("-", "").replace(" ", "")[-4:]
            elif pii_type == "ssn":
                masked = "***-**-" + original[-4:]
            else:
                masked = "***"
            
            # Record match
            pii_matches.append(PIIMatch(
                type=pii_type,
                original=original,
                masked=masked,
                position=(match.start() + offset, match.end() + offset)
            ))
            
            # Replace in sanitized text
            start = match.start() + offset
            end = match.end() + offset
            sanitized = sanitized[:start] + masked + sanitized[end:]
            offset += len(masked) - len(original)
    
    return sanitized, pii_matches


def validate_text_input(text: str, check_pii: bool = True) -> ValidationResult:
    """
    Validate text input for security threats and PII.
    
    Args:
        text: Input text to validate
        check_pii: Whether to check and mask PII
        
    Returns:
        ValidationResult object
    """
    violations = []
    pii_detected = []
    sanitized_text = text
    
    # Check SQL injection
    sql_violations = detect_sql_injection(text)
    violations.extend(sql_violations)
    
    # Check prompt injection
    prompt_violations = detect_prompt_injection(text)
    violations.extend(prompt_violations)
    
    # Check and mask PII
    if check_pii:
        sanitized_text, pii_detected = detect_and_mask_pii(text)
    
    # Determine if valid
    is_valid = len(violations) == 0
    error_message = None
    
    if not is_valid:
        violation_types = set(v.type for v in violations)
        error_message = f"Security violations detected: {', '.join(violation_types)}"
        
        # Log security violation
        logger.warning(
            f"Security violation detected",
            extra={
                "violation_types": list(violation_types),
                "violation_count": len(violations),
                "pii_count": len(pii_detected),
                "timestamp": datetime.now().isoformat(),
                "sanitized_input": sanitized_text[:100],  # First 100 chars only
            }
        )
    
    return ValidationResult(
        is_valid=is_valid,
        sanitized_text=sanitized_text,
        violations=violations,
        pii_detected=pii_detected,
        error_message=error_message
    )

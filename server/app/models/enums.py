"""
Data models for AI provider system
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class ProviderName(str, Enum):
    """Supported AI providers"""
    CLOUDCODE = "cloudcode"  # FREE Claude/Gemini via Google Cloud Code - STRONGEST
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OLLAMA = "ollama"


# Alias for backward compatibility
AIProvider = ProviderName


@dataclass
class ProviderConfig:
    """Configuration for an AI provider"""
    name: str
    enabled: bool
    api_key: str
    base_url: str
    model: str
    vision_model: Optional[str] = None
    priority: int = 99  # Lower number = higher priority
    timeout_seconds: int = 30
    max_retries: int = 2


@dataclass
class ProviderStatus:
    """Health and status information for a provider"""
    name: str
    available: bool
    last_check: datetime
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    supports_vision: bool = False
    rate_limit_remaining: Optional[int] = None
    quota_exceeded: bool = False
    quota_reset_time: Optional[datetime] = None
    unavailable_reason: Optional[str] = None  # "quota_exceeded", "rate_limit", "api_error", etc.


@dataclass
class EnhancementResult:
    """Result of AI text enhancement"""
    original_text: str
    enhanced_text: str
    provider_used: str
    model_used: str
    processing_time_ms: int
    token_usage: Optional[Dict[str, int]] = None
    confidence_score: float = 0.0
    improvements: List[str] = field(default_factory=list)
    fallback_occurred: bool = False
    error: Optional[str] = None


@dataclass
class TestResult:
    """Result of OCR test run"""
    file_name: str
    provider: str
    original_text: str
    enhanced_text: str
    processing_time_ms: int
    character_count: int
    word_count: int
    accuracy_score: Optional[float] = None
    improvements_detected: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

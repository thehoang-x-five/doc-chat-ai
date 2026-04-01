"""
Safety Checker - PII detection, toxicity checking, and tone verification.

This module provides:
1. PII detection and redaction (email, phone, SSN, credit card)
2. Toxicity detection using existing guardrails
3. Tone alignment verification

"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    NAME = "name"  # Requires NER
    ADDRESS = "address"  # Requires NER


class ToxicityLevel(str, Enum):
    """Levels of toxicity."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"


class ToneType(str, Enum):
    """Types of tone."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    CASUAL = "casual"
    NEUTRAL = "neutral"


@dataclass
class PIIMatch:
    """A PII match found in text."""
    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class PIIResult:
    """Result of PII detection."""
    has_pii: bool
    matches: List[PIIMatch] = field(default_factory=list)
    redacted_text: Optional[str] = None
    pii_types_found: List[PIIType] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pii": self.has_pii,
            "pii_types_found": [t.value for t in self.pii_types_found],
            "num_matches": len(self.matches),
        }


@dataclass
class ToxicityResult:
    """Result of toxicity detection."""
    is_toxic: bool
    level: ToxicityLevel
    score: float  # 0-1
    categories: List[str] = field(default_factory=list)
    flagged_content: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_toxic": self.is_toxic,
            "level": self.level.value,
            "score": self.score,
            "categories": self.categories,
        }


@dataclass
class ToneResult:
    """Result of tone analysis."""
    detected_tone: ToneType
    alignment_score: float  # 0-1, how well it matches target
    is_aligned: bool
    target_tone: Optional[ToneType] = None
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_tone": self.detected_tone.value,
            "alignment_score": self.alignment_score,
            "is_aligned": self.is_aligned,
        }


@dataclass
class SafetyCheckResult:
    """Combined safety check result."""
    is_safe: bool
    pii_result: PIIResult
    toxicity_result: ToxicityResult
    tone_result: Optional[ToneResult] = None
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "pii": self.pii_result.to_dict(),
            "toxicity": self.toxicity_result.to_dict(),
            "tone": self.tone_result.to_dict() if self.tone_result else None,
            "issues": self.issues,
        }


class SafetyChecker:
    """
    Safety Checker for PII, toxicity, and tone verification.
    
    Uses regex patterns for PII detection and integrates with
    existing GuardrailsService for toxicity checking.
    
    Usage:
        checker = SafetyChecker()
        result = checker.check_all(
            text="Contact me at john@email.com",
            target_tone=ToneType.PROFESSIONAL,
        )
        if not result.is_safe:
            print(f"Issues: {result.issues}")
    """
    
    # PII detection patterns
    PII_PATTERNS = {
        PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        PIIType.PHONE: r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        PIIType.SSN: r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b',
        PIIType.CREDIT_CARD: r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
        PIIType.IP_ADDRESS: r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
    }
    
    # Redaction placeholders
    REDACTION_MAP = {
        PIIType.EMAIL: "[EMAIL REDACTED]",
        PIIType.PHONE: "[PHONE REDACTED]",
        PIIType.SSN: "[SSN REDACTED]",
        PIIType.CREDIT_CARD: "[CARD REDACTED]",
        PIIType.IP_ADDRESS: "[IP REDACTED]",
        PIIType.PASSPORT: "[PASSPORT REDACTED]",
        PIIType.NAME: "[NAME REDACTED]",
        PIIType.ADDRESS: "[ADDRESS REDACTED]",
    }
    
    # Toxic keywords (basic list)
    TOXIC_KEYWORDS = [
        "hate", "kill", "die", "stupid", "idiot", "moron",
        "racist", "sexist", "discriminate", "violence", "attack",
    ]
    
    # Tone indicators
    TONE_INDICATORS = {
        ToneType.PROFESSIONAL: ["please", "thank you", "regards", "sincerely", "appreciate"],
        ToneType.FRIENDLY: ["hey", "hi", "awesome", "great", "cool", "amazing"],
        ToneType.FORMAL: ["therefore", "consequently", "hereby", "pursuant", "regarding"],
        ToneType.CASUAL: ["gonna", "wanna", "gotta", "yeah", "nope", "sup"],
    }
    
    def __init__(
        self,
        guardrails_service: Any = None,
        toxicity_threshold: float = 0.5,
        tone_threshold: float = 0.6,
    ):
        """
        Initialize Safety Checker.
        
        Args:
            guardrails_service: Optional existing GuardrailsService
            toxicity_threshold: Score above which content is toxic
            tone_threshold: Minimum alignment score for tone
        """
        self.guardrails_service = guardrails_service
        self.toxicity_threshold = toxicity_threshold
        self.tone_threshold = tone_threshold
        logger.info("SafetyChecker initialized")
    
    def check_all(
        self,
        text: str,
        target_tone: Optional[ToneType] = None,
        redact_pii: bool = True,
    ) -> SafetyCheckResult:
        """
        Run all safety checks on text.
        
        Args:
            text: Text to check
            target_tone: Optional target tone for alignment
            redact_pii: Whether to include redacted text
            
        Returns:
            SafetyCheckResult with all check results
        """
        # Run checks
        pii_result = self.check_pii(text, redact=redact_pii)
        toxicity_result = self.check_toxicity(text)
        tone_result = self.check_tone(text, target_tone) if target_tone else None
        
        # Collect issues
        issues = []
        
        if pii_result.has_pii:
            issues.append(f"PII detected: {', '.join(t.value for t in pii_result.pii_types_found)}")
        
        if toxicity_result.is_toxic:
            issues.append(f"Toxic content detected (level: {toxicity_result.level.value})")
        
        if tone_result and not tone_result.is_aligned:
            issues.append(f"Tone mismatch: detected {tone_result.detected_tone.value}, expected {target_tone.value}")
        
        is_safe = not pii_result.has_pii and not toxicity_result.is_toxic
        if tone_result:
            is_safe = is_safe and tone_result.is_aligned
        
        return SafetyCheckResult(
            is_safe=is_safe,
            pii_result=pii_result,
            toxicity_result=toxicity_result,
            tone_result=tone_result,
            issues=issues,
        )
    
    def check_pii(
        self,
        text: str,
        redact: bool = True,
    ) -> PIIResult:
        """
        Check for PII in text.
        
        Args:
            text: Text to check
            redact: Whether to generate redacted text
            
        Returns:
            PIIResult with matches and optional redacted text
        """
        matches = []
        types_found = set()
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                ))
                types_found.add(pii_type)
        
        # Generate redacted text if requested
        redacted_text = None
        if redact and matches:
            redacted_text = self._redact_text(text, matches)
        
        return PIIResult(
            has_pii=len(matches) > 0,
            matches=matches,
            redacted_text=redacted_text,
            pii_types_found=list(types_found),
        )
    
    def _redact_text(self, text: str, matches: List[PIIMatch]) -> str:
        """Redact PII matches from text."""
        # Sort matches by position (reverse) to preserve indices
        sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)
        
        result = text
        for match in sorted_matches:
            placeholder = self.REDACTION_MAP.get(match.pii_type, "[REDACTED]")
            result = result[:match.start] + placeholder + result[match.end:]
        
        return result
    
    def check_toxicity(
        self,
        text: str,
    ) -> ToxicityResult:
        """
        Check for toxic content.
        
        Uses GuardrailsService if available, otherwise falls back
        to keyword-based detection.
        
        Args:
            text: Text to check
            
        Returns:
            ToxicityResult with toxicity assessment
        """
        # Use guardrails service if available
        if self.guardrails_service:
            try:
                result = self.guardrails_service.check_toxicity(text)
                return ToxicityResult(
                    is_toxic=result.get("is_toxic", False),
                    level=ToxicityLevel(result.get("level", "none")),
                    score=result.get("score", 0.0),
                    categories=result.get("categories", []),
                    flagged_content=result.get("flagged_content", []),
                )
            except Exception as e:
                logger.warning(f"Guardrails check failed: {e}")
        
        # Fallback to keyword-based detection
        return self._keyword_toxicity_check(text)
    
    def _keyword_toxicity_check(self, text: str) -> ToxicityResult:
        """Simple keyword-based toxicity check."""
        text_lower = text.lower()
        flagged = []
        
        for keyword in self.TOXIC_KEYWORDS:
            if keyword in text_lower:
                flagged.append(keyword)
        
        if not flagged:
            return ToxicityResult(
                is_toxic=False,
                level=ToxicityLevel.NONE,
                score=0.0,
            )
        
        # Calculate score based on keyword density
        score = min(len(flagged) * 0.2, 1.0)
        
        if score >= 0.8:
            level = ToxicityLevel.SEVERE
        elif score >= 0.6:
            level = ToxicityLevel.HIGH
        elif score >= 0.4:
            level = ToxicityLevel.MEDIUM
        else:
            level = ToxicityLevel.LOW
        
        return ToxicityResult(
            is_toxic=score >= self.toxicity_threshold,
            level=level,
            score=score,
            categories=["keyword_match"],
            flagged_content=flagged,
        )
    
    def check_tone(
        self,
        text: str,
        target_tone: Optional[ToneType] = None,
    ) -> ToneResult:
        """
        Check tone of text and alignment with target.
        
        Args:
            text: Text to analyze
            target_tone: Target tone to check alignment
            
        Returns:
            ToneResult with tone assessment
        """
        text_lower = text.lower()
        
        # Count tone indicators
        tone_scores = {}
        for tone, indicators in self.TONE_INDICATORS.items():
            score = sum(1 for ind in indicators if ind in text_lower)
            tone_scores[tone] = score
        
        # Detect primary tone
        if not any(tone_scores.values()):
            detected_tone = ToneType.NEUTRAL
        else:
            detected_tone = max(tone_scores, key=tone_scores.get)
        
        # Calculate alignment
        if target_tone:
            if detected_tone == target_tone:
                alignment_score = 1.0
            elif detected_tone == ToneType.NEUTRAL:
                alignment_score = 0.7  # Neutral is somewhat acceptable
            else:
                alignment_score = 0.3  # Mismatch
        else:
            alignment_score = 1.0
        
        is_aligned = alignment_score >= self.tone_threshold
        
        # Generate suggestions
        suggestions = []
        if not is_aligned and target_tone:
            target_indicators = self.TONE_INDICATORS.get(target_tone, [])
            if target_indicators:
                suggestions.append(f"Consider using phrases like: {', '.join(target_indicators[:3])}")
        
        return ToneResult(
            detected_tone=detected_tone,
            alignment_score=alignment_score,
            is_aligned=is_aligned,
            target_tone=target_tone,
            suggestions=suggestions,
        )


# Default instance
safety_checker = SafetyChecker()

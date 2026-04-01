"""
Guardrails Service cho RAG Pipeline
Cung cấp các kiểm tra an toàn toàn diện cho input và output sử dụng các rails có thể cấu hình.

Đây là implementation nhẹ không yêu cầu thư viện NeMo Guardrails.
Cung cấp chức năng tương tự với pattern matching và rule-based checks.

Tính năng:
- Input rails: jailbreak, PII, topic restrictions, prompt injection, SQL injection
- Output rails: toxicity, bias, factuality, PII leakage, hallucination
- Hot-reload configuration
- User-friendly error messages
- Violation logging
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging
import re
import yaml

logger = logging.getLogger(__name__)


@dataclass
class GuardrailViolation:
    """Bản ghi vi phạm guardrail."""
    rail_name: str
    rail_type: str  # "input" or "output"
    severity: str  # "critical", "high", "medium", "low"
    message: str
    detected_content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GuardrailResult:
    """Kết quả kiểm tra guardrail."""
    passed: bool
    violations: List[GuardrailViolation]
    sanitized_text: Optional[str] = None
    action: str = "allow"  # "allow", "block", "sanitize", "warn"
    user_message: Optional[str] = None


class GuardrailsService:
    """
    Service kiểm tra input và output với các safety rails.
    
    Implementation này cung cấp pattern-based guardrails mà không yêu cầu
    thư viện NeMo Guardrails. Nhẹ và có thể cấu hình qua YAML.
    
    Tính năng:
    - Input rails cho user queries
    - Output rails cho LLM responses
    - Hot-reload configuration
    - Violation logging
    - User-friendly error messages
    """
    
    def __init__(self, config_path: str = "server/config/guardrails_config.yml"):
        """
        Initialize guardrails service.
        
        Args:
            config_path: Path to guardrails configuration YAML file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._violations_log: List[GuardrailViolation] = []
        
        # Load configuration
        self.reload_config()
        
        logger.info(f"GuardrailsService initialized with config: {config_path}")
    
    def reload_config(self) -> None:
        """Hot-reload cấu hình guardrails từ file YAML."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Không tìm thấy config file: {self.config_path}, sử dụng defaults")
                self.config = self._get_default_config()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            logger.info("Guardrails configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Lỗi khi load guardrails config: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Lấy cấu hình mặc định nếu không tìm thấy file."""
        return {
            "input_rails": [],
            "output_rails": [],
            "settings": {
                "enabled": True,
                "log_violations": True,
                "fail_open": False,
                "error_messages": {
                    "default": "I cannot process this request. Please try rephrasing."
                }
            }
        }
    
    async def check_input(
        self,
        text: str,
        user_id: str,
        workspace_id: str,
    ) -> GuardrailResult:
        """
        Kiểm tra user input với các input rails.
        
        Args:
            text: Text input của user
            user_id: Định danh user
            workspace_id: Định danh workspace
            
        Returns:
            GuardrailResult với pass/fail và violations
        """
        if not self.config.get("settings", {}).get("enabled", True):
            return GuardrailResult(passed=True, violations=[], action="allow")
        
        violations = []
        sanitized_text = text
        action = "allow"
        
        # Kiểm tra từng input rail
        for rail in self.config.get("input_rails", []):
            if not rail.get("enabled", True):
                continue
            
            rail_name = rail.get("name", "unknown")
            
            # Kiểm tra patterns
            if rail_name == "jailbreak_detection":
                violation = self._check_jailbreak(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
            
            elif rail_name == "pii_filter":
                violation, sanitized = self._check_pii(text, rail)
                if violation:
                    violations.append(violation)
                    sanitized_text = sanitized
                    action = rail.get("action", "sanitize")
            
            elif rail_name == "topic_restriction":
                violation = self._check_topic(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
            
            elif rail_name == "prompt_injection":
                violation = self._check_prompt_injection(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
            
            elif rail_name == "sql_injection":
                violation = self._check_sql_injection(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
        
        # Log violations
        if violations and self.config.get("settings", {}).get("log_violations", True):
            for v in violations:
                self._violations_log.append(v)
                logger.warning(
                    f"Input guardrail violation: {v.rail_name} "
                    f"(severity: {v.severity}, user: {user_id}, workspace: {workspace_id})"
                )
        
        # Xác định kết quả
        passed = len(violations) == 0 or action == "warn"
        
        # Lấy user-friendly message
        user_message = None
        if not passed:
            user_message = self._get_error_message(violations[0].rail_name)
        
        return GuardrailResult(
            passed=passed,
            violations=violations,
            sanitized_text=sanitized_text if action == "sanitize" else None,
            action=action,
            user_message=user_message,
        )
    
    async def check_output(
        self,
        text: str,
        context: str,
    ) -> GuardrailResult:
        """
        Kiểm tra LLM output với các output rails.
        
        Args:
            text: Text output của LLM
            context: Context được sử dụng để generation
            
        Returns:
            GuardrailResult với pass/fail và violations
        """
        if not self.config.get("settings", {}).get("enabled", True):
            return GuardrailResult(passed=True, violations=[], action="allow")
        
        violations = []
        sanitized_text = text
        action = "allow"
        
        # Kiểm tra từng output rail
        for rail in self.config.get("output_rails", []):
            if not rail.get("enabled", True):
                continue
            
            rail_name = rail.get("name", "unknown")
            
            # Kiểm tra patterns
            if rail_name == "toxicity_check":
                violation = self._check_toxicity(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
            
            elif rail_name == "bias_check":
                violation = self._check_bias(text, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "warn")
            
            elif rail_name == "factuality_check":
                violation = self._check_factuality(text, context, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "block")
            
            elif rail_name == "pii_leakage":
                violation, sanitized = self._check_pii_leakage(text, rail)
                if violation:
                    violations.append(violation)
                    sanitized_text = sanitized
                    action = rail.get("action", "sanitize")
            
            elif rail_name == "hallucination_detection":
                violation = self._check_hallucination(text, context, rail)
                if violation:
                    violations.append(violation)
                    action = rail.get("action", "warn")
        
        # Log violations
        if violations and self.config.get("settings", {}).get("log_violations", True):
            for v in violations:
                self._violations_log.append(v)
                logger.warning(
                    f"Output guardrail violation: {v.rail_name} "
                    f"(severity: {v.severity})"
                )
        
        # Determine result
        passed = len(violations) == 0 or action == "warn"
        
        # Get user-friendly message
        user_message = None
        if not passed:
            user_message = self._get_error_message(violations[0].rail_name)
        
        return GuardrailResult(
            passed=passed,
            violations=violations,
            sanitized_text=sanitized_text if action == "sanitize" else None,
            action=action,
            user_message=user_message,
        )
    
    # ========== INPUT RAIL CHECKS ==========
    
    def _check_jailbreak(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra các nỗ lực jailbreak."""
        patterns = rail.get("patterns", [])
        text_lower = text.lower()
        
        for pattern in patterns:
            if pattern.lower() in text_lower:
                return GuardrailViolation(
                    rail_name="jailbreak_detection",
                    rail_type="input",
                    severity=rail.get("severity", "high"),
                    message=f"Jailbreak pattern detected: {pattern}",
                    detected_content=pattern,
                )
        
        return None
    
    def _check_pii(self, text: str, rail: Dict) -> tuple:
        """Kiểm tra PII và trả về violation + sanitized text."""
        # Các PII patterns đơn giản
        pii_patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        }
        
        sanitized = text
        detected = []
        
        for pii_type, pattern in pii_patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected.extend(matches)
                # Mask PII
                sanitized = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", sanitized)
        
        if detected:
            return (
                GuardrailViolation(
                    rail_name="pii_filter",
                    rail_type="input",
                    severity=rail.get("severity", "high"),
                    message=f"PII detected: {len(detected)} instances",
                    detected_content=", ".join(detected[:3]),  # 3 đầu tiên
                ),
                sanitized
            )
        
        return None, text
    
    def _check_topic(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra các chủ đề bị hạn chế."""
        blocked_topics = rail.get("blocked_topics", [])
        text_lower = text.lower()
        
        # Keyword matching đơn giản cho topics
        topic_keywords = {
            "illegal_activities": ["illegal", "crime", "steal", "hack", "fraud"],
            "harmful_content": ["harm", "hurt", "damage", "destroy"],
            "violence": ["violence", "kill", "murder", "attack"],
            "hate_speech": ["hate", "racist", "discriminate"],
        }
        
        for topic in blocked_topics:
            keywords = topic_keywords.get(topic, [topic])
            for keyword in keywords:
                if keyword in text_lower:
                    return GuardrailViolation(
                        rail_name="topic_restriction",
                        rail_type="input",
                        severity=rail.get("severity", "high"),
                        message=f"Restricted topic detected: {topic}",
                        detected_content=keyword,
                    )
        
        return None
    
    def _check_prompt_injection(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra các nỗ lực prompt injection."""
        patterns = rail.get("patterns", [])
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return GuardrailViolation(
                    rail_name="prompt_injection",
                    rail_type="input",
                    severity=rail.get("severity", "critical"),
                    message="Prompt injection pattern detected",
                    detected_content=pattern,
                )
        
        return None
    
    def _check_sql_injection(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra các nỗ lực SQL injection."""
        patterns = rail.get("patterns", [])
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return GuardrailViolation(
                    rail_name="sql_injection",
                    rail_type="input",
                    severity=rail.get("severity", "critical"),
                    message="SQL injection pattern detected",
                    detected_content=pattern,
                )
        
        return None
    
    # ========== OUTPUT RAIL CHECKS ==========
    
    def _check_toxicity(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra toxic content (đơn giản hóa)."""
        # Kiểm tra toxicity đơn giản với keyword matching
        toxic_keywords = [
            "hate", "stupid", "idiot", "dumb", "kill", "die",
            "offensive", "insult", "threat"
        ]
        
        text_lower = text.lower()
        detected = [kw for kw in toxic_keywords if kw in text_lower]
        
        if detected:
            return GuardrailViolation(
                rail_name="toxicity_check",
                rail_type="output",
                severity=rail.get("severity", "high"),
                message=f"Toxic content detected: {len(detected)} keywords",
                detected_content=", ".join(detected[:3]),
            )
        
        return None
    
    def _check_bias(self, text: str, rail: Dict) -> Optional[GuardrailViolation]:
        """Kiểm tra biased content (đơn giản hóa)."""
        # Kiểm tra bias đơn giản
        bias_keywords = [
            "always", "never", "all", "none", "every", "only",
            "men are", "women are", "people from"
        ]
        
        text_lower = text.lower()
        detected = [kw for kw in bias_keywords if kw in text_lower]
        
        if len(detected) >= 2:  # Nhiều chỉ báo bias
            return GuardrailViolation(
                rail_name="bias_check",
                rail_type="output",
                severity=rail.get("severity", "medium"),
                message=f"Potential bias detected: {len(detected)} indicators",
                detected_content=", ".join(detected[:3]),
            )
        
        return None
    
    def _check_factuality(
        self,
        text: str,
        context: str,
        rail: Dict
    ) -> Optional[GuardrailViolation]:
        """Kiểm tra xem response có dựa trên context không (đơn giản hóa)."""
        # Kiểm tra overlap đơn giản
        text_words = set(text.lower().split())
        context_words = set(context.lower().split())
        
        if len(text_words) == 0:
            return None
        
        overlap = len(text_words & context_words) / len(text_words)
        min_score = rail.get("min_grounding_score", 0.5)
        
        if overlap < min_score:
            return GuardrailViolation(
                rail_name="factuality_check",
                rail_type="output",
                severity=rail.get("severity", "high"),
                message=f"Low grounding score: {overlap:.2f} < {min_score}",
                detected_content=f"overlap={overlap:.2f}",
            )
        
        return None
    
    def _check_pii_leakage(self, text: str, rail: Dict) -> tuple:
        """Kiểm tra PII leakage trong output."""
        return self._check_pii(text, rail)
    
    def _check_hallucination(
        self,
        text: str,
        context: str,
        rail: Dict
    ) -> Optional[GuardrailViolation]:
        """Kiểm tra thông tin bị hallucinated (đơn giản hóa)."""
        # Kiểm tra các absolute statements không có trong context
        absolute_patterns = [
            r'\b(definitely|certainly|absolutely|always|never)\b',
            r'\b(all|every|none|no one)\b',
        ]
        
        for pattern in absolute_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches and len(matches) >= 2:
                return GuardrailViolation(
                    rail_name="hallucination_detection",
                    rail_type="output",
                    severity=rail.get("severity", "medium"),
                    message=f"Potential hallucination: {len(matches)} absolute statements",
                    detected_content=", ".join(matches[:3]),
                )
        
        return None
    
    # ========== UTILITY METHODS ==========
    
    def _get_error_message(self, rail_name: str) -> str:
        """Lấy user-friendly error message cho một rail."""
        error_messages = self.config.get("settings", {}).get("error_messages", {})
        return error_messages.get(rail_name, error_messages.get("default", 
            "I cannot process this request. Please try rephrasing."))
    
    def get_violations_log(
        self,
        rail_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[GuardrailViolation]:
        """
        Lấy các violations gần đây.
        
        Args:
            rail_type: Filter theo "input" hoặc "output" (optional)
            severity: Filter theo severity (optional)
            limit: Số lượng violations tối đa trả về
            
        Returns:
            List các GuardrailViolation objects
        """
        violations = self._violations_log[-limit:]
        
        if rail_type:
            violations = [v for v in violations if v.rail_type == rail_type]
        
        if severity:
            violations = [v for v in violations if v.severity == severity]
        
        return violations
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê guardrails."""
        total = len(self._violations_log)
        
        if total == 0:
            return {
                "total_violations": 0,
                "by_type": {},
                "by_severity": {},
                "by_rail": {},
            }
        
        by_type = {}
        by_severity = {}
        by_rail = {}
        
        for v in self._violations_log:
            by_type[v.rail_type] = by_type.get(v.rail_type, 0) + 1
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
            by_rail[v.rail_name] = by_rail.get(v.rail_name, 0) + 1
        
        return {
            "total_violations": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_rail": by_rail,
        }

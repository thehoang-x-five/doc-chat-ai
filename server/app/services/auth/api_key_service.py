"""
API Key Manager để rotate nhiều API key.

Được cải tiến với các tính năng từ provider_manager.py:
- Hỗ trợ đa tài khoản (multi-account) cho mỗi provider
- Theo dõi hạn mức (quota) theo tài khoản/model
- Tự động xoay vòng tài khoản khi hạn mức thấp
- Giám sát sức khỏe (health monitoring) và circuit breaker
- Mapping/aliasing model

Hỗ trợ nhiều key cho mỗi provider, tự động xoay vòng khi:
- Rate limited (429)
- Hết hạn mức Quota (402)
- Không được cấp quyền - Unauthorized (401)
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS (từ provider_manager.py)
# =============================================================================

class AccountStatus(str, Enum):
    """Trạng thái sức khỏe tài khoản."""
    HEALTHY = "healthy"
    LOW_QUOTA = "low_quota"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR = "error"
    DISABLED = "disabled"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ModelQuota:
    """Thông tin hạn mức cho một model cụ thể (từ provider_manager.py)."""
    model_name: str
    used: int = 0
    limit: int = 0
    percentage: float = 100.0  # Phần trăm còn lại
    reset_time: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def update_usage(self, tokens_used: int) -> None:
        """Cập nhật mức sử dụng và tính toán lại phần trăm."""
        self.used += tokens_used
        if self.limit > 0:
            self.percentage = max(0, (1 - self.used / self.limit) * 100)
        self.last_updated = datetime.utcnow()
    
    def is_low(self, threshold: float = 20.0) -> bool:
        """Kiểm tra xem hạn mức có dưới ngưỡng không."""
        return self.percentage < threshold


@dataclass
class KeyStatus:
    """Trạng thái của một API key với tính năng theo dõi nâng cao."""
    key: str
    is_valid: bool = True
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    cooldown_until: Optional[datetime] = None
    
    # Enhanced tracking (từ provider_manager.py)
    status: AccountStatus = AccountStatus.HEALTHY
    quotas: Dict[str, ModelQuota] = field(default_factory=dict)
    total_requests: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    avg_latency_ms: float = 0
    
    def is_available(self) -> bool:
        """Kiểm tra xem key có sẵn sàng để sử dụng không."""
        if not self.is_valid:
            return False
        if self.status == AccountStatus.DISABLED:
            return False
        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return False
        return True
    
    @property
    def overall_quota_percentage(self) -> float:
        """Lấy phần trăm hạn mức trung bình trên tất cả các model."""
        if not self.quotas:
            return 100.0
        return sum(q.percentage for q in self.quotas.values()) / len(self.quotas)
    
    def mark_error(self, error: str, cooldown_seconds: int = 60) -> None:
        """Đánh dấu key bị lỗi với tracking nâng cao."""
        self.last_error = error
        self.error_count += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.cooldown_until = datetime.utcnow() + timedelta(seconds=cooldown_seconds)
        
        # Cập nhật trạng thái dựa trên loại lỗi
        if "429" in error or "rate" in error.lower():
            self.status = AccountStatus.RATE_LIMITED
            self.cooldown_until = datetime.utcnow() + timedelta(seconds=60)
        elif "402" in error or "quota" in error.lower() or "balance" in error.lower() or "insufficient" in error.lower():
            # Hết hạn mức/số dư - vô hiệu hóa trong 24 giờ
            self.status = AccountStatus.QUOTA_EXCEEDED
            self.cooldown_until = datetime.utcnow() + timedelta(hours=24)
            self.is_valid = False  # Đánh dấu không hợp lệ ngay lập tức cho các vấn đề về hạn mức
            logger.warning(f"API key bị vô hiệu hóa trong 24h do vấn đề hạn mức/số dư: {error}")
        elif self.consecutive_failures >= 3:
            self.status = AccountStatus.ERROR
            self.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
        
        # Đánh dấu là không hợp lệ sau quá nhiều lỗi
        if self.error_count >= 5:
            self.is_valid = False
            self.status = AccountStatus.DISABLED
            logger.warning(f"API key bị đánh dấu không hợp lệ sau {self.error_count} lỗi")
    
    def mark_success(self, latency_ms: float = 0, model: str = None, tokens: int = 0) -> None:
        """Đánh dấu key thành công với tracking nâng cao."""
        self.last_used = datetime.utcnow()
        self.error_count = 0
        self.consecutive_failures = 0
        self.cooldown_until = None
        self.total_requests += 1
        
        # Update latency (exponential moving average)
        if latency_ms > 0:
            if self.avg_latency_ms == 0:
                self.avg_latency_ms = latency_ms
            else:
                self.avg_latency_ms = 0.8 * self.avg_latency_ms + 0.2 * latency_ms
        
        # Cập nhật quota nếu có model được chỉ định
        if model and tokens > 0:
            if model not in self.quotas:
                self.quotas[model] = ModelQuota(model_name=model)
            self.quotas[model].update_usage(tokens)
        
        # Khôi phục trạng thái nếu đang ở trạng thái lỗi
        if self.status in (AccountStatus.ERROR, AccountStatus.RATE_LIMITED):
            self.status = AccountStatus.HEALTHY
            logger.info(f"API key đã khôi phục về trạng thái HEALTHY")


class APIKeyManager:
    """
    Manager nâng cao để xoay vòng API key giữa các provider.
    
    Tính năng (gộp từ provider_manager.py):
    - Hỗ trợ đa tài khoản cho mỗi provider
    - Theo dõi hạn mức theo tài khoản/model
    - Tự động xoay vòng tài khoản khi hạn mức thấp
    - Giám sát sức khỏe và circuit breaker
    - Lựa chọn thông minh dựa trên quota và độ trễ
    
    Sử dụng:
        manager = APIKeyManager()
        key = manager.get_key("groq")
        # Sử dụng key...
        manager.mark_success("groq", key, latency_ms=100, model="llama-3.3-70b", tokens=500)
    """
    
    def __init__(self):
        """Khởi tạo key manager với các key từ settings."""
        self._keys: Dict[str, List[KeyStatus]] = {}
        self._current_index: Dict[str, int] = {}
        
        # Load keys từ settings
        self._load_keys()
    
    def _load_keys(self) -> None:
        """Load API keys từ settings."""
        # Key Groq (hỗ trợ comma-separated và GROQ_API_KEYS)
        groq_keys = self._parse_keys(settings.GROQ_API_KEY, getattr(settings, 'GROQ_API_KEYS', ''))
        if groq_keys:
            self._keys["groq"] = [KeyStatus(key=k) for k in groq_keys]
            self._current_index["groq"] = 0
            logger.info(f"Đã load {len(groq_keys)} Groq API keys")
        
        # Key DeepSeek
        deepseek_keys = self._parse_keys(settings.DEEPSEEK_API_KEY, getattr(settings, 'DEEPSEEK_API_KEYS', ''))
        if deepseek_keys:
            self._keys["deepseek"] = [KeyStatus(key=k) for k in deepseek_keys]
            self._current_index["deepseek"] = 0
            logger.info(f"Đã load {len(deepseek_keys)} DeepSeek API keys")
        
        # Key Gemini
        gemini_keys = self._parse_keys(settings.GEMINI_API_KEY, getattr(settings, 'GEMINI_API_KEYS', ''))
        if gemini_keys:
            self._keys["gemini"] = [KeyStatus(key=k) for k in gemini_keys]
            self._current_index["gemini"] = 0
            logger.info(f"Đã load {len(gemini_keys)} Gemini API keys")
        
        # Key Together.ai (cho FLUX image generation)
        together_keys = self._parse_keys(
            getattr(settings, 'TOGETHER_API_KEY', ''),
            getattr(settings, 'TOGETHER_API_KEYS', '')
        )
        if together_keys:
            self._keys["together"] = [KeyStatus(key=k) for k in together_keys]
            self._current_index["together"] = 0
            logger.info(f"Đã load {len(together_keys)} Together.ai API keys")
        
        # Key Hugging Face (cho SDXL image generation)
        huggingface_keys = self._parse_keys(
            getattr(settings, 'HUGGINGFACE_API_KEY', ''),
            getattr(settings, 'HUGGINGFACE_API_KEYS', '')
        )
        if huggingface_keys:
            self._keys["huggingface"] = [KeyStatus(key=k) for k in huggingface_keys]
            self._current_index["huggingface"] = 0
            logger.info(f"Đã load {len(huggingface_keys)} Hugging Face API keys")
        
        # Key Stability AI (cho Stable Diffusion)
        stability_keys = self._parse_keys(
            getattr(settings, 'STABILITY_API_KEY', ''),
            getattr(settings, 'STABILITY_API_KEYS', '')
        )
        if stability_keys:
            self._keys["stability"] = [KeyStatus(key=k) for k in stability_keys]
            self._current_index["stability"] = 0
            logger.info(f"Đã load {len(stability_keys)} Stability AI API keys")
    
    def _parse_keys(self, primary: str, additional: str = "") -> List[str]:
        """Parse các key phân tách bằng dấu phẩy từ nguồn chính và bổ sung."""
        keys = []
        if primary:
            keys.extend([k.strip() for k in primary.split(",") if k.strip()])
        if additional:
            keys.extend([k.strip() for k in additional.split(",") if k.strip()])
        return list(dict.fromkeys(keys))  # Loại bỏ trùng lặp trong khi giữ nguyên thứ tự
    
    def get_key(self, provider: str, prefer_high_quota: bool = True) -> Optional[str]:
        """
        Lấy một API key khả dụng cho provider.
        
        Chiến lược lựa chọn nâng cao:
        1. Nếu prefer_high_quota: chọn key có phần trăm hạn mức cao nhất
        2. Ngược lại: round-robin và bỏ qua các key không khả dụng
        
        Args:
            provider: Tên Provider (groq, deepseek, gemini)
            prefer_high_quota: Ưu tiên key có hạn mức còn lại cao hơn
            
        Returns:
            Chuỗi API key hoặc None nếu không có key nào khả dụng
        """
        if provider not in self._keys:
            return None
        
        keys = self._keys[provider]
        if not keys:
            return None
        
        # Lấy các key khả dụng
        available_keys = [k for k in keys if k.is_available()]
        
        if not available_keys:
            # Không có key khả dụng, thử tìm key đã hết thời gian cooldown
            for key_status in keys:
                if key_status.is_valid:
                    return key_status.key
            logger.error(f"Không có API key nào khả dụng cho {provider}")
            return None
        
        if prefer_high_quota and len(available_keys) > 1:
            # Sắp xếp theo: quota percentage (giảm dần), latency (tăng dần), consecutive failures (tăng dần)
            available_keys.sort(key=lambda k: (
                -k.overall_quota_percentage,
                k.avg_latency_ms,
                k.consecutive_failures,
            ))
            return available_keys[0].key
        
        # Lựa chọn Round-robin
        start_index = self._current_index.get(provider, 0)
        for i in range(len(keys)):
            index = (start_index + i) % len(keys)
            key_status = keys[index]
            
            if key_status.is_available():
                self._current_index[provider] = (index + 1) % len(keys)
                return key_status.key
        
        return available_keys[0].key if available_keys else None
    
    def get_best_key(self, provider: str) -> Optional[str]:
        """Lấy key tốt nhất dựa trên quota và sức khỏe."""
        return self.get_key(provider, prefer_high_quota=True)
    
    def mark_success(
        self, 
        provider: str, 
        key: str, 
        latency_ms: float = 0,
        model: str = None,
        tokens: int = 0,
    ) -> None:
        """
        Đánh dấu một key là thành công với tracking nâng cao.
        
        Args:
            provider: Tên Provider
            key: API key
            latency_ms: Độ trễ request tính bằng mili giây
            model: Model đã sử dụng (để theo dõi hạn mức)
            tokens: Tokens đã sử dụng (để theo dõi hạn mức)
        """
        if provider not in self._keys:
            return
        
        for key_status in self._keys[provider]:
            if key_status.key == key:
                key_status.mark_success(latency_ms, model, tokens)
                break
    
    def mark_error(self, provider: str, key: str, error: str, cooldown_seconds: int = 60) -> None:
        """Đánh dấu một key là bị lỗi."""
        if provider not in self._keys:
            return
        
        for key_status in self._keys[provider]:
            if key_status.key == key:
                key_status.mark_error(error, cooldown_seconds)
                logger.warning(f"Lỗi key {provider}: {error}, cooldown {cooldown_seconds}s")
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê nâng cao về tất cả các key."""
        stats = {}
        for provider, keys in self._keys.items():
            available_keys = [k for k in keys if k.is_available()]
            stats[provider] = {
                "total": len(keys),
                "available": len(available_keys),
                "valid": sum(1 for k in keys if k.is_valid),
                "in_cooldown": sum(1 for k in keys if k.cooldown_until and datetime.utcnow() < k.cooldown_until),
                "avg_quota_percentage": sum(k.overall_quota_percentage for k in keys) / len(keys) if keys else 0,
                "total_requests": sum(k.total_requests for k in keys),
                "total_failures": sum(k.total_failures for k in keys),
                "avg_latency_ms": sum(k.avg_latency_ms for k in keys) / len(keys) if keys else 0,
            }
        return stats
    
    def get_account_details(self) -> List[Dict[str, Any]]:
        """Lấy thông tin chi tiết cho tất cả các tài khoản (để hiển thị UI, giống như provider_manager)."""
        details = []
        for provider, keys in self._keys.items():
            for i, k in enumerate(keys):
                details.append({
                    "id": f"{provider}_{i}",
                    "name": f"{provider.capitalize()} #{i+1}",
                    "provider": provider,
                    "status": k.status.value,
                    "quota_percentage": round(k.overall_quota_percentage, 1),
                    "quotas": {
                        name: {
                            "percentage": round(q.percentage, 1),
                            "used": q.used,
                            "limit": q.limit,
                        }
                        for name, q in k.quotas.items()
                    },
                    "total_requests": k.total_requests,
                    "total_failures": k.total_failures,
                    "avg_latency_ms": round(k.avg_latency_ms, 1),
                    "last_used": k.last_used.isoformat() if k.last_used else None,
                    "last_error": k.last_error,
                    "is_available": k.is_available(),
                })
        return details


# Global instance
_key_manager: Optional[APIKeyManager] = None


def get_key_manager() -> APIKeyManager:
    """Lấy hoặc tạo global key manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager()
    return _key_manager

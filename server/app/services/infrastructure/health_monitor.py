"""
Health Monitor Service
Theo dõi sức khỏe của các AI providers và tự động phát hiện lỗi.

Tính năng:
- Check health định kỳ cho tất cả providers
- Tự động đánh dấu unhealthy khi có lỗi
- Phát hiện recovery tự động
- Tracking lịch sử health checks
- Tính toán uptime và latency trung bình
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Kết quả của một lần health check"""
    provider: str
    healthy: bool
    latency_ms: float = 0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HealthMonitor:
    """
    Theo dõi sức khỏe của các AI providers và infrastructure.
    
    Tính năng:
    - Check health định kỳ
    - Tự động đánh dấu unhealthy khi fail
    - Phát hiện recovery
    - Tracking lịch sử health
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 60  # giây
        self._history: Dict[str, List[HealthCheckResult]] = {}
        self._max_history = 100  # Giữ 100 checks gần nhất mỗi provider
    
    async def start(self, interval: int = 60) -> None:
        """Bắt đầu monitoring định kỳ."""
        if self._running:
            logger.warning("Health monitor đang chạy rồi")
            return
        
        self._running = True
        self._check_interval = interval
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor đã start với interval {interval}s")
    
    async def stop(self) -> None:
        """Dừng health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor đã dừng")
    
    async def _monitor_loop(self) -> None:
        """Loop chính để monitoring."""
        while self._running:
            try:
                await self._run_all_checks()
            except Exception as e:
                logger.error(f"Lỗi health check: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    async def _run_all_checks(self) -> None:
        """Chạy tất cả health checks song song."""
        checks = await asyncio.gather(
            self._check_cloudcode(),
            self._check_deepseek(),
            self._check_gemini(),
            self._check_groq(),
            self._check_ollama(),
            return_exceptions=True,
        )
        
        for result in checks:
            if isinstance(result, HealthCheckResult):
                self._record_result(result)
            elif isinstance(result, Exception):
                logger.error(f"Exception trong health check: {result}")
    
    def _record_result(self, result: HealthCheckResult) -> None:
        """Ghi lại kết quả health check."""
        if result.provider not in self._history:
            self._history[result.provider] = []
        
        self._history[result.provider].append(result)
        
        # Trim history để không tốn memory
        if len(self._history[result.provider]) > self._max_history:
            self._history[result.provider] = self._history[result.provider][-self._max_history:]
        
        # Log khi status thay đổi
        history = self._history[result.provider]
        if len(history) >= 2:
            prev = history[-2]
            if prev.healthy != result.healthy:
                if result.healthy:
                    logger.info(f"Provider {result.provider} đã hồi phục")
                else:
                    logger.warning(f"Provider {result.provider} bị unhealthy: {result.error}")
    
    async def _check_cloudcode(self) -> HealthCheckResult:
        """Check health của Cloud Code provider."""
        start = time.time()
        try:
            from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
            manager = get_cloudcode_manager()
            accounts = manager.list_accounts()
            
            if not accounts:
                return HealthCheckResult(
                    provider="cloudcode",
                    healthy=False,
                    error="Chưa config account nào",
                )
            
            # Check xem có account nào còn quota không
            has_quota = any(
                any(q.get("quota", 0) > 0 for q in acc.get("quotas", {}).values())
                for acc in accounts
            )
            
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                provider="cloudcode",
                healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                provider="cloudcode",
                healthy=False,
                error=str(e)[:100],
            )
    
    async def _check_deepseek(self) -> HealthCheckResult:
        """Check health của DeepSeek API."""
        if not settings.DEEPSEEK_API_KEY:
            return HealthCheckResult(
                provider="deepseek",
                healthy=False,
                error="Chưa config",
            )
        
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.DEEPSEEK_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                provider="deepseek",
                healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                provider="deepseek",
                healthy=False,
                error=str(e)[:100],
            )
    
    async def _check_gemini(self) -> HealthCheckResult:
        """Check health của Gemini API."""
        if not settings.GEMINI_API_KEY:
            return HealthCheckResult(
                provider="gemini",
                healthy=False,
                error="Chưa config",
            )
        
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.GEMINI_BASE_URL}/models",
                    params={"key": settings.GEMINI_API_KEY},
                    timeout=10.0,
                )
                response.raise_for_status()
                
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                provider="gemini",
                healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                provider="gemini",
                healthy=False,
                error=str(e)[:100],
            )
    
    async def _check_groq(self) -> HealthCheckResult:
        """Check health của Groq API."""
        if not settings.GROQ_API_KEY:
            return HealthCheckResult(
                provider="groq",
                healthy=False,
                error="Chưa config",
            )
        
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.GROQ_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                provider="groq",
                healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                provider="groq",
                healthy=False,
                error=str(e)[:100],
            )
    
    async def _check_ollama(self) -> HealthCheckResult:
        """Check health của Ollama local."""
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.OLLAMA_BASE_URL}/api/tags",
                    timeout=5.0,
                )
                response.raise_for_status()
                
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                provider="ollama",
                healthy=True,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                provider="ollama",
                healthy=False,
                error=str(e)[:100],
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Lấy status hiện tại của tất cả providers."""
        status = {}
        
        for provider, history in self._history.items():
            if not history:
                continue
            
            latest = history[-1]
            
            # Tính uptime % từ 10 checks gần nhất
            recent = history[-10:]
            healthy_count = sum(1 for r in recent if r.healthy)
            uptime_pct = (healthy_count / len(recent)) * 100 if recent else 0
            
            # Tính latency trung bình từ các checks healthy
            healthy_latencies = [r.latency_ms for r in recent if r.healthy and r.latency_ms > 0]
            avg_latency = sum(healthy_latencies) / len(healthy_latencies) if healthy_latencies else 0
            
            status[provider] = {
                "healthy": latest.healthy,
                "last_check": latest.timestamp.isoformat(),
                "last_error": latest.error if not latest.healthy else None,
                "uptime_percentage": round(uptime_pct, 1),
                "avg_latency_ms": round(avg_latency, 1),
                "checks_count": len(history),
            }
        
        return status
    
    def get_history(self, provider: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Lấy lịch sử health check của một provider."""
        history = self._history.get(provider, [])
        return [
            {
                "healthy": r.healthy,
                "latency_ms": round(r.latency_ms, 1),
                "error": r.error,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in history[-limit:]
        ]


# Instance global
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Lấy hoặc tạo instance global của health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


async def start_health_monitor(interval: int = 60) -> None:
    """Start health monitor global."""
    monitor = get_health_monitor()
    await monitor.start(interval)


async def stop_health_monitor() -> None:
    """Dừng health monitor global."""
    monitor = get_health_monitor()
    await monitor.stop()

"""
Health check endpoints.
Provides comprehensive health monitoring for all system components.
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings


router = APIRouter(tags=["Health"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ComponentHealth(BaseModel):
    """Health status of a single component."""
    name: str
    status: str = Field(..., description="healthy, degraded, unhealthy")
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ProviderHealthInfo(BaseModel):
    """Health info for an AI provider."""
    name: str
    status: str
    available: bool
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0
    quota: Optional[float] = None


class HealthResponse(BaseModel):
    """Basic health check response."""
    status: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with all components."""
    status: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    uptime_seconds: Optional[float] = None
    components: List[ComponentHealth] = []
    providers: List[ProviderHealthInfo] = []


class ReadinessResponse(BaseModel):
    """Readiness probe response."""
    ready: bool
    checks: Dict[str, bool] = {}


class LivenessResponse(BaseModel):
    """Liveness probe response."""
    alive: bool


# =============================================================================
# STARTUP TIME TRACKING
# =============================================================================

_startup_time: Optional[float] = None


def set_startup_time():
    """Set startup time (call from app startup)."""
    global _startup_time
    _startup_time = time.time()


def get_uptime() -> Optional[float]:
    """Get uptime in seconds."""
    if _startup_time:
        return time.time() - _startup_time
    return None


# =============================================================================
# HEALTH CHECK FUNCTIONS
# =============================================================================

async def check_database(db: AsyncSession) -> ComponentHealth:
    """Check database connectivity."""
    start = time.time()
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        latency = (time.time() - start) * 1000
        return ComponentHealth(
            name="database",
            status="healthy",
            latency_ms=round(latency, 2),
            message="PostgreSQL connection OK",
        )
    except Exception as e:
        return ComponentHealth(
            name="database",
            status="unhealthy",
            message=f"Database error: {str(e)[:100]}",
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    start = time.time()
    try:
        import redis.asyncio as redis
        
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        
        latency = (time.time() - start) * 1000
        return ComponentHealth(
            name="redis",
            status="healthy",
            latency_ms=round(latency, 2),
            message="Redis connection OK",
        )
    except Exception as e:
        return ComponentHealth(
            name="redis",
            status="unhealthy",
            message=f"Redis error: {str(e)[:100]}",
        )


async def check_minio() -> ComponentHealth:
    """Check MinIO/S3 connectivity."""
    start = time.time()
    try:
        from app.storage.object_store import ObjectStore
        
        storage = ObjectStore()
        # Try to check if bucket exists
        storage.ensure_bucket()
        
        latency = (time.time() - start) * 1000
        return ComponentHealth(
            name="minio",
            status="healthy",
            latency_ms=round(latency, 2),
            message="MinIO connection OK",
            details={"bucket": storage.bucket},
        )
    except Exception as e:
        return ComponentHealth(
            name="minio",
            status="unhealthy",
            message=f"MinIO error: {str(e)[:100]}",
        )


async def check_celery() -> ComponentHealth:
    """Check Celery worker connectivity."""
    start = time.time()
    try:
        from app.queue.celery_app import celery_app
        
        # Inspect active workers
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        latency = (time.time() - start) * 1000
        
        if active:
            worker_count = len(active)
            return ComponentHealth(
                name="celery",
                status="healthy",
                latency_ms=round(latency, 2),
                message=f"{worker_count} worker(s) active",
                details={"workers": list(active.keys())},
            )
        else:
            return ComponentHealth(
                name="celery",
                status="degraded",
                latency_ms=round(latency, 2),
                message="No active workers found",
            )
    except Exception as e:
        return ComponentHealth(
            name="celery",
            status="unhealthy",
            message=f"Celery error: {str(e)[:100]}",
        )



async def get_provider_health_info() -> List[ProviderHealthInfo]:
    """Get health info for all AI providers."""
    providers = []
    
    # Get RAG service provider health
    try:
        from app.services.infrastructure.ai_providers.manager import manager as ai_manager
        health_data = await ai_manager.get_provider_status()
        
        for name, data in health_data.items():
            providers.append(ProviderHealthInfo(
                name=name,
                status="healthy" if data.available else "unhealthy",
                available=data.available,
                consecutive_failures=0, # Not exposed in status object directly usually
                total_requests=0,
                total_failures=0,
                avg_latency_ms=data.response_time_ms or 0,
            ))
    except Exception as e:
        # logger.error(f"Failed to get provider health: {e}")
        pass
    
    # Get Cloud Code provider health
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        stats = manager.get_statistics()
        
        providers.append(ProviderHealthInfo(
            name="cloudcode",
            status="healthy" if stats.get("total_accounts", 0) > 0 else "unavailable",
            available=stats.get("total_accounts", 0) > 0,
            total_requests=0,
            quota=stats.get("avg_claude_quota"),
            details=stats,
        ))
    except Exception:
        pass
    
    # Check other providers availability (Config check)
    # ... (Keep existing checks for config if needed, but AI Manager handles them mostly)
    
    return providers


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 if the API is running.
    """
    return HealthResponse(status="healthy")


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """
    Detailed health check with all component statuses.
    
    Checks:
    - Database (PostgreSQL)
    - Redis
    - MinIO/S3
    - Celery workers
    - AI providers
    """
    # Run all checks concurrently
    db_health, redis_health, minio_health = await asyncio.gather(
        check_database(db),
        check_redis(),
        check_minio(),
        return_exceptions=True,
    )
    
    # Handle exceptions
    components = []
    for health in [db_health, redis_health, minio_health]:
        if isinstance(health, Exception):
            components.append(ComponentHealth(
                name="unknown",
                status="unhealthy",
                message=str(health)[:100],
            ))
        else:
            components.append(health)
    
    # Check Celery (sync operation, run in thread)
    try:
        celery_health = await check_celery()
        components.append(celery_health)
    except Exception as e:
        components.append(ComponentHealth(
            name="celery",
            status="unhealthy",
            message=str(e)[:100],
        ))
    
    # Get provider health
    providers = await get_provider_health_info()
    
    # Determine overall status
    statuses = [c.status for c in components]
    if "unhealthy" in statuses:
        overall_status = "unhealthy"
    elif "degraded" in statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return DetailedHealthResponse(
        status=overall_status,
        uptime_seconds=get_uptime(),
        components=components,
        providers=providers,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """
    Kubernetes readiness probe.
    Returns ready=true if all critical components are healthy.
    """
    checks = {}
    
    # Check database
    db_health = await check_database(db)
    checks["database"] = db_health.status == "healthy"
    
    # Check Redis
    redis_health = await check_redis()
    checks["redis"] = redis_health.status == "healthy"
    
    # All critical checks must pass
    ready = all(checks.values())
    
    return ReadinessResponse(ready=ready, checks=checks)


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_probe():
    """
    Kubernetes liveness probe.
    Returns alive=true if the process is running.
    """
    return LivenessResponse(alive=True)


@router.get("/health/providers")
async def provider_health():
    """
    Get health status of all AI providers.
    
    Returns detailed information about:
    - Cloud Code accounts and quotas
    - DeepSeek, Gemini, Groq availability
    - Ollama local status
    - Request statistics and latency
    - Health monitor status
    """
    providers = await get_provider_health_info()
    
    # Get more detailed Cloud Code stats
    cloudcode_stats = None
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        cloudcode_stats = manager.get_statistics()
    except Exception:
        pass
    
    # Get health monitor status
    monitor_status = None
    try:
        from app.services.infrastructure.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        monitor_status = monitor.get_status()
    except Exception:
        pass
    
    return {
        "providers": [p.model_dump() for p in providers],
        "cloudcode_details": cloudcode_stats,
        "health_monitor": monitor_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/monitor/{provider}")
async def provider_health_history(provider: str, limit: int = 20):
    """
    Get health check history for a specific provider.
    
    Args:
        provider: Provider name (cloudcode, deepseek, gemini, groq, ollama)
        limit: Number of history entries to return
    """
    try:
        from app.services.infrastructure.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        history = monitor.get_history(provider, limit)
        return {
            "provider": provider,
            "history": history,
            "count": len(history),
        }
    except Exception as e:
        return {
            "provider": provider,
            "error": str(e),
            "history": [],
        }

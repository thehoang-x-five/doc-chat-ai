"""
Redis-based rate limiting middleware.
Implements per-user and per-endpoint rate limiting with sliding window.
"""
import logging
import time
from typing import Optional, Callable
from uuid import UUID

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Rate limit configuration for different endpoints."""
    
    # Default limits (requests per minute)
    DEFAULT_LIMIT = 60
    DEFAULT_WINDOW = 60  # seconds
    
    # Endpoint-specific limits
    ENDPOINT_LIMITS = {
        # Auth endpoints (stricter)
        "/api/v1/auth/login": (5, 60),  # 5 per minute
        "/api/v1/auth/register": (3, 60),  # 3 per minute
        "/api/v1/auth/otp/request": (3, 60),  # 3 per minute
        "/api/v1/auth/forgot-password": (3, 60),  # 3 per minute
        
        # Chat/RAG endpoints (moderate)
        "/api/v1/chat/query": (20, 60),  # 20 per minute
        "/api/v1/chat/conversations": (30, 60),  # 30 per minute
        
        # OCR endpoints (resource intensive)
        "/api/v1/ocr/process": (10, 60),  # 10 per minute
        "/api/v1/documents/upload": (20, 60),  # 20 per minute
        
        # General API
        "/api/v1/": (100, 60),  # 100 per minute for other endpoints
    }
    
    @classmethod
    def get_limit(cls, path: str) -> tuple[int, int]:
        """Get rate limit for a path (limit, window_seconds)."""
        # Check exact match first
        if path in cls.ENDPOINT_LIMITS:
            return cls.ENDPOINT_LIMITS[path]
        
        # Check prefix match
        for prefix, limit in cls.ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                return limit
        
        return (cls.DEFAULT_LIMIT, cls.DEFAULT_WINDOW)


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize rate limiter with Redis connection."""
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
    
    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting."""
        # Normalize endpoint
        endpoint_key = endpoint.replace("/", "_").strip("_")
        return f"ratelimit:{identifier}:{endpoint_key}"
    
    async def is_allowed(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: User ID or IP address
            endpoint: API endpoint path
            limit: Max requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, retry_after)
        """
        redis_client = await self.get_redis()
        key = self._get_key(identifier, endpoint)
        now = time.time()
        window_start = now - window
        
        try:
            # Use pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove old entries outside window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry on key
            pipe.expire(key, window + 1)
            
            results = await pipe.execute()
            current_count = results[1]
            
            remaining = max(0, limit - current_count - 1)
            
            if current_count >= limit:
                # Get oldest entry to calculate retry-after
                oldest = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + window - now) + 1
                else:
                    retry_after = window
                
                # Remove the request we just added (it's over limit)
                await redis_client.zrem(key, str(now))
                
                return False, 0, retry_after
            
            return True, remaining, 0
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Fail open - allow request if Redis is down
            return True, limit, 0
    
    async def get_usage(
        self,
        identifier: str,
        endpoint: str,
        window: int,
    ) -> int:
        """Get current usage count for identifier."""
        redis_client = await self.get_redis()
        key = self._get_key(identifier, endpoint)
        now = time.time()
        window_start = now - window
        
        try:
            # Remove old entries and count
            await redis_client.zremrangebyscore(key, 0, window_start)
            return await redis_client.zcard(key)
        except redis.RedisError:
            return 0
    
    async def reset(self, identifier: str, endpoint: str):
        """Reset rate limit for identifier."""
        redis_client = await self.get_redis()
        key = self._get_key(identifier, endpoint)
        await redis_client.delete(key)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    """
    
    def __init__(
        self,
        app,
        rate_limiter: RateLimiter = None,
        get_identifier: Callable[[Request], str] = None,
    ):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            rate_limiter: RateLimiter instance
            get_identifier: Function to extract identifier from request
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.get_identifier = get_identifier or self._default_get_identifier
    
    def _default_get_identifier(self, request: Request) -> str:
        """Default identifier extraction (IP or user ID)."""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return str(user_id)
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/v1/health"]:
            return await call_next(request)
        
        # Get identifier and limits
        identifier = self.get_identifier(request)
        limit, window = RateLimitConfig.get_limit(request.url.path)
        
        # Check rate limit
        is_allowed, remaining, retry_after = await self.rate_limiter.is_allowed(
            identifier=identifier,
            endpoint=request.url.path,
            limit=limit,
            window=window,
        )
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {identifier} on {request.url.path}"
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "Content-Type": "application/json",
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                    "Retry-After": str(retry_after),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
        
        return response


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(
    request: Request,
    limit: int = None,
    window: int = None,
) -> bool:
    """
    Dependency for checking rate limit in endpoints.
    
    Usage:
        @router.post("/endpoint")
        async def endpoint(
            allowed: bool = Depends(lambda r: check_rate_limit(r, limit=10, window=60))
        ):
            ...
    """
    rate_limiter = get_rate_limiter()
    
    # Get identifier
    user_id = getattr(request.state, "user_id", None)
    identifier = str(user_id) if user_id else request.client.host
    
    # Get limits
    if limit is None or window is None:
        limit, window = RateLimitConfig.get_limit(request.url.path)
    
    is_allowed, remaining, retry_after = await rate_limiter.is_allowed(
        identifier=identifier,
        endpoint=request.url.path,
        limit=limit,
        window=window,
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    
    return True

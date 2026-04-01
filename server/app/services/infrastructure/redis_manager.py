"""
Redis Client Manager - Centralized Redis connection for caching.

Provides a singleton Redis client for use across all caching modules.
"""

import asyncio
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Singleton Redis client manager.
    
    Usage:
        redis = await RedisManager.get_client()
        await redis.set("key", "value")
    """
    
    _instance: Optional["RedisManager"] = None
    _client: Optional[aioredis.Redis] = None
    _connected: bool = False
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    async def get_client(cls) -> Optional[aioredis.Redis]:
        """
        Get Redis client, lazily connecting if needed.
        
        Returns:
            Redis client or None if connection fails
        """
        async with cls._lock:
            if cls._client is not None and cls._connected:
                return cls._client
            
            try:
                redis_url = settings.redis_url
                cls._client = aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # We handle encoding manually
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                
                # Test connection
                await cls._client.ping()
                cls._connected = True
                
                logger.info(f"✅ Redis connected: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
                return cls._client
                
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}. Caching disabled.")
                cls._client = None
                cls._connected = False
                return None
    
    @classmethod
    async def close(cls):
        """Close Redis connection."""
        if cls._client:
            await cls._client.close()
            cls._client = None
            cls._connected = False
            logger.info("Redis connection closed")
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Redis is connected."""
        return cls._connected


# Convenience function
async def get_redis() -> Optional[aioredis.Redis]:
    """Get Redis client."""
    return await RedisManager.get_client()

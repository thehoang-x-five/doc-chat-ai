"""
Memory Cache Manager - Redis-based caching for Memory and Memori contexts.

Reduces memory recall latency from 2-3s to <100ms for cached hits.
"""

import hashlib
import json
import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class MemoryCacheManager:
    """
    Redis-based cache for Memory and Memori contexts.
    
    Cache Keys:
    - memory:{conversation_id} - TTL 10 min
    - memori:{conversation_id}:{query_hash} - TTL 15 min
    """
    
    MEMORY_TTL = 600  # 10 minutes
    MEMORI_TTL = 900  # 15 minutes
    
    def __init__(self, redis_client=None):
        """
        Initialize cache manager.
        
        Args:
            redis_client: Redis client instance. If None, caching is disabled.
        """
        self.redis = redis_client
        self._enabled = redis_client is not None
        
        if not self._enabled:
            logger.warning("MemoryCacheManager initialized without Redis - caching disabled")
    
    @staticmethod
    def _hash_query(query: str) -> str:
        """Create hash of query for cache key."""
        return hashlib.md5(query.encode()).hexdigest()[:16]
    
    async def get_memory(self, conversation_id: UUID) -> Optional[str]:
        """
        Get cached memory context.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Cached context string or None if miss
        """
        if not self._enabled:
            return None
        
        try:
            key = f"memory:{conversation_id}"
            result = await self.redis.get(key)
            
            if result:
                logger.debug(f"Memory cache HIT: {conversation_id}")
                return result.decode() if isinstance(result, bytes) else result
            
            logger.debug(f"Memory cache MISS: {conversation_id}")
            return None
            
        except Exception as e:
            logger.warning(f"Memory cache get error: {e}")
            return None
    
    async def set_memory(self, conversation_id: UUID, context: str) -> None:
        """
        Cache memory context.
        
        Args:
            conversation_id: Conversation ID
            context: Memory context string
        """
        if not self._enabled or not context:
            return
        
        try:
            key = f"memory:{conversation_id}"
            await self.redis.setex(key, self.MEMORY_TTL, context)
            logger.debug(f"Memory cache SET: {conversation_id}, TTL: {self.MEMORY_TTL}s")
            
        except Exception as e:
            logger.warning(f"Memory cache set error: {e}")
    
    async def get_memori(self, conversation_id: UUID, query: str) -> Optional[str]:
        """
        Get cached memori context for query.
        
        Args:
            conversation_id: Conversation ID
            query: User query (hashed for key)
            
        Returns:
            Cached context string or None if miss
        """
        if not self._enabled:
            return None
        
        try:
            query_hash = self._hash_query(query)
            key = f"memori:{conversation_id}:{query_hash}"
            result = await self.redis.get(key)
            
            if result:
                logger.debug(f"Memori cache HIT: {conversation_id}")
                return result.decode() if isinstance(result, bytes) else result
            
            logger.debug(f"Memori cache MISS: {conversation_id}")
            return None
            
        except Exception as e:
            logger.warning(f"Memori cache get error: {e}")
            return None
    
    async def set_memori(self, conversation_id: UUID, query: str, context: str) -> None:
        """
        Cache memori context.
        
        Args:
            conversation_id: Conversation ID
            query: User query (hashed for key)
            context: Memori context string
        """
        if not self._enabled or not context:
            return
        
        try:
            query_hash = self._hash_query(query)
            key = f"memori:{conversation_id}:{query_hash}"
            await self.redis.setex(key, self.MEMORI_TTL, context)
            logger.debug(f"Memori cache SET: {conversation_id}, TTL: {self.MEMORI_TTL}s")
            
        except Exception as e:
            logger.warning(f"Memori cache set error: {e}")
    
    async def invalidate_conversation(self, conversation_id: UUID) -> None:
        """
        Invalidate all cache entries for a conversation.
        Called when new messages are added.
        
        Args:
            conversation_id: Conversation ID
        """
        if not self._enabled:
            return
        
        try:
            # Delete memory cache
            memory_key = f"memory:{conversation_id}"
            await self.redis.delete(memory_key)
            
            # Delete all memori caches for this conversation
            pattern = f"memori:{conversation_id}:*"
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
            
            logger.debug(f"Cache invalidated for conversation: {conversation_id}")
            
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")
    
    async def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self._enabled:
            return {"enabled": False}
        
        try:
            info = await self.redis.info("keyspace")
            return {
                "enabled": True,
                "keyspace": info,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}

"""
Request Deduplication Cache - Prevent processing duplicate queries.

Saves resources by caching results for identical queries within 5 seconds.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class DedupCache:
    """
    Request deduplication cache.
    
    Prevents processing identical queries submitted within 5 seconds.
    Uses Redis for distributed caching.
    
    Key format: dedup:{user_id}:{workspace_id}:{query_hash}
    TTL: 5 seconds
    """
    
    TTL = 5  # seconds
    
    def __init__(self, redis_client=None):
        """
        Initialize dedup cache.
        
        Args:
            redis_client: Redis client instance. If None, dedup is disabled.
        """
        self.redis = redis_client
        self._enabled = redis_client is not None
        
        if not self._enabled:
            logger.debug("DedupCache initialized without Redis - dedup disabled")
    
    @staticmethod
    def _hash_query(query: str) -> str:
        """Create hash of query for cache key."""
        return hashlib.md5(query.encode()).hexdigest()[:16]
    
    def _make_key(self, user_id: UUID, workspace_id: UUID, query: str) -> str:
        """Create cache key."""
        query_hash = self._hash_query(query)
        return f"dedup:{user_id}:{workspace_id}:{query_hash}"
    
    async def get(
        self,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response for query.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            query: Query string
            
        Returns:
            Cached response dict or None if miss
        """
        if not self._enabled:
            return None
        
        try:
            key = self._make_key(user_id, workspace_id, query)
            result = await self.redis.get(key)
            
            if result:
                logger.info(f"Dedup cache HIT - returning cached response")
                data = result.decode() if isinstance(result, bytes) else result
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.warning(f"Dedup cache get error: {e}")
            return None
    
    async def set(
        self,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
        response: Dict[str, Any],
    ) -> None:
        """
        Cache response for query.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            query: Query string
            response: Response dict to cache
        """
        if not self._enabled:
            return
        
        try:
            key = self._make_key(user_id, workspace_id, query)
            data = json.dumps(response, default=str)
            await self.redis.setex(key, self.TTL, data)
            logger.debug(f"Dedup cache SET, TTL: {self.TTL}s")
            
        except Exception as e:
            logger.warning(f"Dedup cache set error: {e}")
    
    async def check_and_set_processing(
        self,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
    ) -> bool:
        """
        Check if query is being processed and mark as processing.
        
        Uses Redis SETNX for atomic check-and-set.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            query: Query string
            
        Returns:
            True if this is the first request (should process)
            False if already being processed (should wait or skip)
        """
        if not self._enabled:
            return True
        
        try:
            key = self._make_key(user_id, workspace_id, query) + ":processing"
            
            # Atomic set-if-not-exists
            result = await self.redis.setnx(key, "1")
            
            if result:
                # We got the lock, set TTL
                await self.redis.expire(key, self.TTL)
                return True
            else:
                # Already being processed
                logger.info("Query already being processed - duplicate detected")
                return False
                
        except Exception as e:
            logger.warning(f"Dedup processing check error: {e}")
            return True  # Allow processing on error
    
    async def clear_processing(
        self,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
    ) -> None:
        """
        Clear processing flag after completion.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            query: Query string
        """
        if not self._enabled:
            return
        
        try:
            key = self._make_key(user_id, workspace_id, query) + ":processing"
            await self.redis.delete(key)
            
        except Exception as e:
            logger.warning(f"Dedup clear error: {e}")

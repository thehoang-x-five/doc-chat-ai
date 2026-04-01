"""
Search cache service cho các queries lặp lại nhanh.

Sử dụng Redis để cache search results và tránh lặp lại:
- Embedding generation
- Vector database queries
- Result formatting

Cache TTL: 1 giờ (có thể cấu hình)
"""
import hashlib
import json
import logging
from typing import Any, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class SearchCache:
    """Cache search results để cải thiện performance."""
    
    def __init__(self, ttl: int = 3600):
        """
        Khởi tạo search cache.
        
        Args:
            ttl: Time to live tính bằng giây (mặc định: 1 giờ)
        """
        # Sử dụng Redis trực tiếp thay vì rag_cache
        try:
            import redis.asyncio as redis
            from app.core.config import settings
            
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.ttl = ttl
            self.prefix = "search"
            logger.info("SearchCache initialized with Redis")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for SearchCache: {e}")
            self.redis = None
            self.ttl = ttl
            self.prefix = "search"
    
    def _make_key(self, query: str, workspace_id: str, limit: int, **kwargs) -> str:
        """
        Generate cache key từ search parameters.
        
        Args:
            query: Search query
            workspace_id: Workspace ID
            limit: Result limit
            **kwargs: Các parameters bổ sung (tags, document_ids, etc.)
            
        Returns:
            Cache key (MD5 hash)
        """
        # Sort kwargs để key generation nhất quán
        sorted_kwargs = sorted(kwargs.items())
        key_str = f"{self.prefix}:{workspace_id}:{query}:{limit}:{sorted_kwargs}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(
        self, 
        query: str, 
        workspace_id: str, 
        limit: int,
        **kwargs
    ) -> Optional[List[Any]]:
        """
        Lấy cached search results.
        
        Args:
            query: Search query
            workspace_id: Workspace ID
            limit: Result limit
            **kwargs: Các parameters bổ sung
            
        Returns:
            Cached results hoặc None nếu không tìm thấy
        """
        if not self.redis:
            return None
            
        try:
            key = self._make_key(query, workspace_id, limit, **kwargs)
            cached_data = await self.redis.get(key)
            
            if cached_data:
                logger.debug(f"Search cache HIT: {query[:50]}...")
                return json.loads(cached_data)
            
            logger.debug(f"Search cache MISS: {query[:50]}...")
            return None
            
        except Exception as e:
            logger.warning(f"Search cache get error: {e}")
            return None
    
    async def set(
        self, 
        query: str, 
        workspace_id: str, 
        limit: int,
        results: List[Any],
        **kwargs
    ) -> bool:
        """
        Cache search results.
        
        Args:
            query: Search query
            workspace_id: Workspace ID
            limit: Result limit
            results: Search results cần cache
            **kwargs: Các parameters bổ sung
            
        Returns:
            True nếu cache thành công
        """
        if not self.redis:
            return False
            
        try:
            key = self._make_key(query, workspace_id, limit, **kwargs)
            
            # Serialize results sang JSON
            # Convert UUID và các non-serializable types khác
            serialized = json.dumps(results, default=str)
            
            await self.redis.setex(key, self.ttl, serialized)
            logger.debug(f"Search cached: {query[:50]}... ({len(results)} results)")
            return True
            
        except Exception as e:
            logger.warning(f"Search cache set error: {e}")
            return False
    
    async def invalidate(self, workspace_id: str) -> int:
        """
        Invalidate tất cả search cache cho một workspace.
        
        Hữu ích khi documents được thêm/cập nhật/xóa.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Số lượng keys bị invalidated
        """
        if not self.redis:
            return 0
            
        try:
            # Pattern để match tất cả search keys cho workspace này
            pattern = f"{self.prefix}:{workspace_id}:*"
            
            # Lấy tất cả matching keys
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                # Xóa tất cả keys
                await self.redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} search cache entries for workspace {workspace_id}")
                return len(keys)
            
            return 0
            
        except Exception as e:
            logger.warning(f"Search cache invalidate error: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """
        Xóa tất cả search cache.
        
        Returns:
            True nếu xóa thành công
        """
        if not self.redis:
            return False
            
        try:
            pattern = f"{self.prefix}:*"
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} search cache entries")
            
            return True
            
        except Exception as e:
            logger.warning(f"Search cache clear error: {e}")
            return False


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_search_cache_instance: Optional[SearchCache] = None


def get_search_cache() -> SearchCache:
    """
    Lấy singleton search cache instance.
    
    Returns:
        SearchCache instance
    """
    global _search_cache_instance
    if _search_cache_instance is None:
        _search_cache_instance = SearchCache()
        logger.info("Initialized singleton SearchCache")
    return _search_cache_instance

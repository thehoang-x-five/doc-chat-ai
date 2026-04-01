"""
Intent detection cache sử dụng Redis.

Cache kết quả nhận diện ý định để tránh gọi API lặp lại cho cùng một câu hỏi.
Sử dụng MD5 hash của câu hỏi đã được chuẩn hóa làm cache keys với TTL 5 phút.
"""
import redis.asyncio as redis
import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class IntentCache:
    """
    Redis-based cache cho kết quả nhận diện ý định (intent detection).
    
    Tính năng:
    - Hết hạn dựa trên TTL (5 phút)
    - MD5 hash keys để lookup nhất quán
    - Fallback nhẹ nhàng khi cache lỗi
    - Theo dõi Hit/miss để giám sát
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Khởi tạo intent cache.
        
        Args:
            redis_url: URL kết nối Redis
        """
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl = 300  # 5 phút
        self.prefix = "intent:"
        
        # Tracking metrics
        self.hits = 0
        self.misses = 0
    
    def _get_key(self, question: str) -> str:
        """
        Tạo cache key từ câu hỏi.
        
        Chuẩn hóa câu hỏi (chữ thường, loại bỏ khoảng trắng) và tạo MD5 hash
        để tạo key nhất quán.
        
        Args:
            question: Câu hỏi người dùng
            
        Returns:
            Chuỗi cache key
        """
        # Chuẩn hóa câu hỏi (lowercase, strip whitespace)
        normalized = question.lower().strip()
        # MD5 hash để có key nhất quán
        hash_key = hashlib.md5(normalized.encode()).hexdigest()
        return f"{self.prefix}{hash_key}"
    
    async def get(self, question: str) -> Optional[dict]:
        """
        Lấy kết quả intent đã cache.
        
        Args:
            question: Câu hỏi người dùng
            
        Returns:
            dict chứa kết quả intent hoặc None nếu chưa cache
        """
        try:
            key = self._get_key(question)
            cached = await self.redis.get(key)
            
            if cached:
                self.hits += 1
                logger.debug(f"Intent cache HIT: {question[:50]}...")
                
                # Log tỷ lệ hit mỗi 100 requests
                total = self.hits + self.misses
                if total > 0 and total % 100 == 0:
                    hit_rate = (self.hits / total) * 100
                    logger.info(f"📊 Intent cache hit rate: {hit_rate:.1f}% ({self.hits}/{total})")
                
                return json.loads(cached)
            
            self.misses += 1
            logger.debug(f"Intent cache MISS: {question[:50]}...")
            return None
            
        except Exception as e:
            logger.warning(f"Lỗi khi lấy intent cache: {e}")
            return None  # Graceful fallback
    
    async def set(self, question: str, result: dict) -> None:
        """
        Lưu kết quả intent vào cache.
        
        Args:
            question: Câu hỏi người dùng
            result: Kết quả nhận diện intent (dict)
        """
        try:
            key = self._get_key(question)
            await self.redis.setex(
                key,
                self.ttl,
                json.dumps(result, default=str)
            )
            logger.debug(f"Đã cache intent: {question[:50]}...")
            
        except Exception as e:
            logger.warning(f"Lỗi khi lưu intent cache: {e}")
            # Không raise - caching là tùy chọn
    
    async def clear(self, pattern: str = None) -> None:
        """
        Xóa các mục trong cache.
        
        Args:
            pattern: Pattern tùy chọn để khớp keys (ví dụ: "test*")
                    Nếu None, xóa tất cả các mục intent cache
        """
        try:
            if pattern:
                keys = await self.redis.keys(f"{self.prefix}{pattern}*")
            else:
                keys = await self.redis.keys(f"{self.prefix}*")
            
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"Đã xóa {len(keys)} mục intent cache")
            else:
                logger.debug("Không có mục intent cache nào để xóa")
                
        except Exception as e:
            logger.warning(f"Lỗi khi xóa intent cache: {e}")
    
    async def close(self) -> None:
        """Đóng kết nối Redis."""
        try:
            await self.redis.close()
        except Exception as e:
            logger.warning(f"Lỗi khi đóng intent cache: {e}")


# Singleton instance
_intent_cache: Optional[IntentCache] = None


def get_intent_cache() -> IntentCache:
    """
    Lấy hoặc tạo intent cache singleton.
    
    Returns:
        Instance IntentCache
    """
    global _intent_cache
    if _intent_cache is None:
        from app.core.config import settings
        redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379')
        _intent_cache = IntentCache(redis_url)
    return _intent_cache

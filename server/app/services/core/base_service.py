"""
Base classes cho tất cả các services.
Cung cấp chức năng chung và các contracts cơ sở.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """
    Class cơ sở cho tất cả các services.
    
    Cung cấp:
    - Quản lý Database session
    - Giao diện Health check
    - Logging chuẩn
    - Representation chuỗi
    """
    
    def __init__(self, session: Optional[AsyncSession] = None):
        """
        Khởi tạo base service.
        
        Args:
            session: Database session (tùy chọn)
        """
        self.session = session
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def health_check(self) -> bool:
        """
        Kiểm tra sức khỏe service (Health check).
        
        Returns:
            True nếu service hoạt động tốt, False nếu lỗi
        """
        # Default implementation - override ở các subclasses
        return True
    
    def __repr__(self):
        """String representation của service."""
        return f"<{self.__class__.__name__}>"


class BaseLLMService(BaseService):
    """
    Class cơ sở cho các services phụ thuộc LLM.
    
    Cung cấp:
    - Quản lý LLM provider
    - Health check cho LLM availability
    """
    
    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        llm_provider: Optional[Any] = None
    ):
        """
        Khởi tạo LLM service.
        
        Args:
            session: Database session (tùy chọn)
            llm_provider: Instance của LLM provider (tùy chọn)
        """
        super().__init__(session)
        self.llm = llm_provider
    
    async def health_check(self) -> bool:
        """
        Kiểm tra sức khỏe LLM provider.
        
        Returns:
            True nếu LLM provider khả dụng và hoạt động tốt
        """
        if self.llm is None:
            return True  # Không yêu cầu LLM
        
        try:
            # Check nếu LLM có method health_check
            if hasattr(self.llm, 'health_check'):
                return await self.llm.health_check()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi kiểm tra sức khỏe LLM: {e}")
            return False


class BaseCacheService(BaseService):
    """
    Class cơ sở cho các services có sử dụng Cache.
    
    Cung cấp:
    - Quản lý Cache
    - Health check cho độ sẵn sàng của Cache
    """
    
    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        cache: Optional[Any] = None
    ):
        """
        Khởi tạo cache service.
        
        Args:
            session: Database session (tùy chọn)
            cache: Cache instance (Redis, etc.)
        """
        super().__init__(session)
        self.cache = cache
    
    async def health_check(self) -> bool:
        """
        Kiểm tra sức khỏe Cache.
        
        Returns:
            True nếu cache khả dụng và hoạt động tốt
        """
        if self.cache is None:
            return True  # Không yêu cầu cache
        
        try:
            # Check nếu cache có method ping
            if hasattr(self.cache, 'ping'):
                await self.cache.ping()
                return True
            return True
        except Exception as e:
            self.logger.error(f"Lỗi kiểm tra sức khỏe Cache: {e}")
            return False


class BaseAsyncService(BaseService):
    """
    Class cơ sở cho các services xử lý Async Job.
    
    Cung cấp:
    - Quản lý Async job
    - Theo dõi trạng thái Job (Job tracking)
    """
    
    def __init__(self, session: Optional[AsyncSession] = None):
        """Khởi tạo async service."""
        super().__init__(session)
        self._jobs: Dict[str, Any] = {}
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy trạng thái job.
        
        Args:
            job_id: Định danh Job
            
        Returns:
            Dict trạng thái job hoặc None nếu không tìm thấy
        """
        return self._jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Hủy một job đang chạy.
        
        Args:
            job_id: Định danh Job
            
        Returns:
            True nếu hủy thành công, False nếu không tìm thấy
        """
        if job_id in self._jobs:
            # Implementation phụ thuộc vào loại job
            self.logger.info(f"Đang hủy job: {job_id}")
            return True
        return False

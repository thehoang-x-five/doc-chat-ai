"""
Service Registry Pattern
Quản lý dịch vụ tập trung và dependency injection.
"""
from typing import Dict, Type, Optional, Any, Callable
from app.services.core.base_service import BaseService
import logging

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Registry trung tâm cho toàn bộ các services.
    
    Cung cấp:
    - Đăng ký service (Service registration)
    - Singleton pattern cho các instance service
    - Khám phá service (Service discovery)
    - Dependency injection
    """
    
    _services: Dict[str, Type[BaseService]] = {}
    _instances: Dict[str, BaseService] = {}
    _factories: Dict[str, Callable] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        service_class: Type[BaseService],
        factory: Optional[Callable] = None
    ) -> None:
        """
        Đăng ký một service class.
        
        Args:
            name: Tên service (định danh duy nhất)
            service_class: Class của service cần đăng ký
            factory: Hàm factory để tạo instance (tùy chọn)
        """
        cls._services[name] = service_class
        if factory:
            cls._factories[name] = factory
        logger.info(f"Đã đăng ký service: {name} ({service_class.__name__})")
    
    @classmethod
    def get_class(cls, name: str) -> Optional[Type[BaseService]]:
        """
        Lấy service class theo tên.
        
        Args:
            name: Tên service
            
        Returns:
            Service class hoặc None nếu không tìm thấy
        """
        return cls._services.get(name)
    
    @classmethod
    def get_instance(cls, name: str, **kwargs) -> Optional[BaseService]:
        """
        Lấy hoặc tạo service instance (singleton).
        
        Args:
            name: Tên service
            **kwargs: Tham số truyền vào constructor của service
            
        Returns:
            Service instance hoặc None nếu không tìm thấy
        """
        # Trả về instance đã có nếu tồn tại
        if name in cls._instances:
            return cls._instances[name]
        
        # Tạo instance mới
        if name in cls._factories:
            # Dùng factory function
            instance = cls._factories[name](**kwargs)
        elif name in cls._services:
            # Dùng class constructor
            service_class = cls._services[name]
            instance = service_class(**kwargs)
        else:
            logger.warning(f"Không tìm thấy service: {name}")
            return None
        
        # Cache instance
        cls._instances[name] = instance
        logger.debug(f"Đã tạo service instance: {name}")
        return instance
    
    @classmethod
    def list_services(cls) -> list:
        """
        Liệt kê tất cả services đã đăng ký.
        
        Returns:
            Danh sách tên các services
        """
        return list(cls._services.keys())
    
    @classmethod
    def clear(cls) -> None:
        """
        Xóa tất cả instances (dùng cho testing).
        
        Lưu ý: Không xóa registration của service class
        """
        cls._instances.clear()
        logger.debug("Đã xóa tất cả service instances")
    
    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Hủy đăng ký một service.
        
        Args:
            name: Tên service
        """
        if name in cls._services:
            del cls._services[name]
        if name in cls._instances:
            del cls._instances[name]
        if name in cls._factories:
            del cls._factories[name]
        logger.info(f"Đã hủy đăng ký service: {name}")
    
    @classmethod
    async def health_check_all(cls) -> Dict[str, bool]:
        """
        Kiểm tra sức khỏe toàn bộ services đã đăng ký.
        
        Returns:
            Dict mapping tên service với trạng thái sức khỏe
        """
        results = {}
        for name in cls.list_services():
            try:
                instance = cls.get_instance(name)
                if instance:
                    results[name] = await instance.health_check()
                else:
                    results[name] = False
            except Exception as e:
                logger.error(f"Health check thất bại cho {name}: {e}")
                results[name] = False
        return results


# Auto-register core services
def register_core_services() -> None:
    """Đăng ký các core services."""
    try:
        from app.services.core import (
            RAGService,
            RetrieverService,
            EmbeddingService,
            RerankerService,
        )
        
        # RAGService là singleton, dùng factory để lấy instance
        # Không truyền arguments vào constructor vì __new__ không nhận
        def rag_factory(**kwargs):
            """Factory cho RAGService singleton."""
            return RAGService()
        
        ServiceRegistry.register("rag", RAGService, factory=rag_factory)
        ServiceRegistry.register("retriever", RetrieverService)
        ServiceRegistry.register("embedding", EmbeddingService)
        ServiceRegistry.register("reranker", RerankerService)
        
        logger.info("Core services đã được đăng ký")
    except ImportError as e:
        logger.warning(f"Không thể đăng ký core services: {e}")


def register_conversation_services() -> None:
    """Đăng ký các conversation services."""
    try:
        from app.services.conversation import (
            ChatService,
            MemoryManager,
            IntentDetector,
            IntentCache,
        )
        
        ServiceRegistry.register("chat", ChatService)
        ServiceRegistry.register("memory", MemoryManager)
        ServiceRegistry.register("intent_detector", IntentDetector)
        ServiceRegistry.register("intent_cache", IntentCache)
        
        logger.info("Conversation services đã được đăng ký")
    except ImportError as e:
        logger.warning(f"Không thể đăng ký conversation services: {e}")


def register_document_services() -> None:
    """Đăng ký các document services."""
    try:
        from app.services.documents import (
            DocumentService,
            ChunkingService,
            ExtractionService,
            CategoryService,
        )
        
        ServiceRegistry.register("document", DocumentService)
        ServiceRegistry.register("chunking", ChunkingService)
        ServiceRegistry.register("extraction", ExtractionService)
        ServiceRegistry.register("category", CategoryService)
        
        logger.info("Document services đã được đăng ký")
    except ImportError as e:
        logger.warning(f"Không thể đăng ký document services: {e}")


def register_all_services() -> None:
    """Đăng ký tất cả services."""
    register_core_services()
    register_conversation_services()
    register_document_services()
    logger.info("Tất cả services đã được đăng ký")


# NOTE: Tắt tự động đăng ký để tránh circular imports
# Gọi register_all_services() tường minh trong app startup (ví dụ: main.py lifespan)
# try:
#     register_all_services()
# except Exception as e:
#     logger.warning(f"Auto-registration thất bại: {e}")

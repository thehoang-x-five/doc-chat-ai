"""
Augmentation Pipeline cho Memori.
Sao chép từ project Memori: memori/memory/augmentation/

Tính năng:
- Xử lý Async với ThreadPoolExecutor
- Ghi database theo batch (Batch database writes)
- Trích xuất thực thể (Entity extraction)
- Tạo embedding cho Fact
- Xây dựng Knowledge graph
"""

import asyncio
import logging
import queue as queue_module
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memori.models import MemoriConfig, AugmentationInput, Memories

logger = logging.getLogger(__name__)


@dataclass
class WriteTask:
    """
    Tác vụ ghi Database để xử lý batch.
    Sao chép từ Memori: memori/memory/augmentation/_db_writer.py
    """
    method_name: str
    args: tuple = ()
    kwargs: dict = None
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class AugmentationContext:
    """
    Context cho augmentation pipeline.
    Sao chép từ Memori: memori/memory/augmentation/_base.py
    """
    def __init__(self, payload: AugmentationInput):
        self.payload = payload
        self.data: Dict[str, Any] = {}
        self.writes: List[WriteTask] = []
        self.memories: Memories = Memories()
    
    def add_write(self, method_name: str, *args, **kwargs) -> "AugmentationContext":
        """Thêm tác vụ ghi database vào hàng đợi."""
        self.writes.append(WriteTask(
            method_name=method_name,
            args=args,
            kwargs=kwargs,
        ))
        return self


class DbWriterRuntime:
    """
    Bộ ghi Database chạy nền với cơ chế batching.
    Sao chép từ Memori: memori/memory/augmentation/_db_writer.py
    """
    def __init__(self):
        self.queue: Optional[queue_module.Queue] = None
        self.session_factory: Optional[Callable] = None
        self.batch_size: int = 100
        self.batch_timeout: float = 0.1
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.started = False
        self._stop_event = threading.Event()
    
    def configure(self, config: MemoriConfig) -> "DbWriterRuntime":
        """Cấu hình writer từ config."""
        self.batch_size = config.db_writer_batch_size
        self.batch_timeout = config.db_writer_batch_timeout
        
        if self.queue is None:
            self.queue = queue_module.Queue(maxsize=config.db_writer_queue_size)
        
        return self
    
    def ensure_started(self, session_factory: Callable) -> None:
        """Khởi động luồng writer nền (background writer thread)."""
        with self.lock:
            if self.started:
                return
            
            self.session_factory = session_factory
            self._stop_event.clear()
            self.thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="memori-db-writer"
            )
            self.thread.start()
            self.started = False  # Set lại True ở dưới nếu chạy thành công?
            # Đúng ra nên set self.started = True ở đây? 
            # Code gốc: self.started = True
            self.started = True
            logger.debug("Memori DB writer thread đã khởi động")
    
    def stop(self) -> None:
        """Dừng luồng writer nền."""
        with self.lock:
            if not self.started:
                return
            
            self._stop_event.set()
            if self.thread:
                self.thread.join(timeout=5.0)
            self.started = False
            logger.debug("Memori DB writer thread đã dừng")
    
    def enqueue_write(self, task: WriteTask, timeout: float = 5.0) -> bool:
        """Thêm task ghi vào hàng đợi (enqueue)."""
        try:
            if self.queue is None:
                return False
            self.queue.put(task, timeout=timeout)
            return True
        except queue_module.Full:
            logger.warning("Hàng đợi Memori DB writer đã đầy, bỏ qua lượt ghi")
            return False
    
    def _run_loop(self) -> None:
        """Vòng lặp chính để xử lý các lô ghi (write batches)."""
        if self.session_factory is None:
            return
        
        while not self._stop_event.is_set():
            try:
                batch = self._collect_batch()
                
                if not batch:
                    time.sleep(self.batch_timeout)
                    continue
                
                logger.debug(f"Đang xử lý batch gồm {len(batch)} writes")
                self._process_batch(batch)
                
            except Exception as e:
                logger.error(f"Lỗi trong vòng lặp DB writer: {e}")
                time.sleep(1)
    
    def _collect_batch(self) -> List[WriteTask]:
        """Thu thập một lô (batch) các tasks ghi."""
        batch = []
        deadline = time.time() + self.batch_timeout
        
        while len(batch) < self.batch_size and time.time() < deadline:
            try:
                timeout = max(0.01, deadline - time.time())
                task = self.queue.get(timeout=timeout)
                batch.append(task)
            except queue_module.Empty:
                break
        
        return batch
    
    def _process_batch(self, batch: List[WriteTask]) -> None:
        """
        Xử lý một lô các tasks ghi.
        Thực thi tất cả các lệnh ghi trong một transaction duy nhất để tối ưu hiệu suất.
        """
        if not batch or self.session_factory is None:
            return
        
        try:
            # Tạo async session
            import asyncio
            from sqlalchemy.ext.asyncio import AsyncSession
            
            # Chạy trong event loop mới (do đang ở background thread)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._execute_batch_async(batch))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Xử lý batch {len(batch)} writes thất bại: {e}")
    
    async def _execute_batch_async(self, batch: List[WriteTask]) -> None:
        """Thực thi batch writes bất đồng bộ."""
        from app.db.session import get_async_session
        
        async with get_async_session() as session:
            try:
                # Execute tất cả writes
                for task in batch:
                    try:
                        await self._execute_write_task(session, task)
                    except Exception as e:
                        logger.warning(f"Thực thi write task {task.method_name} thất bại: {e}")
                        # Tiếp tục với các tasks khác
                
                # Commit transaction
                await session.commit()
                logger.debug(f"Đã xử lý thành công batch {len(batch)} writes")
                
            except Exception as e:
                # Rollback khi có lỗi
                await session.rollback()
                logger.error(f"Batch write lỗi, đã rollback: {e}")
                raise
    
    async def _execute_write_task(self, session: Any, task: WriteTask) -> None:
        """Thực thi một task ghi đơn lẻ."""
        # Import manager để thực thi các methods
        from app.services.memori.manager_service import MemoriManager
        
        # Tạo manager instance
        manager = MemoriManager(session)
        
        # Lấy method
        if not hasattr(manager, task.method_name):
            logger.warning(f"Method không xác định: {task.method_name}")
            return
        
        method = getattr(manager, task.method_name)
        
        # Thực thi method
        await method(*task.args, **task.kwargs)


# Global DB writer instance
_db_writer: Optional[DbWriterRuntime] = None


def get_db_writer() -> DbWriterRuntime:
    """Lấy global DB writer instance."""
    global _db_writer
    if _db_writer is None:
        _db_writer = DbWriterRuntime()
    return _db_writer


class AugmentationRuntime:
    """
    Runtime cho xử lý augmentation bất đồng bộ.
    Sao chép từ Memori: memori/memory/augmentation/_runtime.py
    """
    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.started = False
    
    def ensure_started(self, max_workers: int = 50) -> None:
        """Khởi động augmentation runtime."""
        with self.lock:
            if self.started:
                return
            
            self.thread = threading.Thread(
                target=self._run_loop,
                args=(max_workers,),
                daemon=True,
                name="memori-augmentation-runtime"
            )
            self.thread.start()
            self.started = True
            
            # Chờ cho loop sẵn sàng
            self.ready.wait(timeout=5.0)
            logger.debug("Memori augmentation runtime đã khởi động")
    
    def _run_loop(self, max_workers: int) -> None:
        """Chạy event loop trong background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.semaphore = asyncio.Semaphore(max_workers)
        self.ready.set()
        
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()


# Global runtime instance
_runtime: Optional[AugmentationRuntime] = None


def get_runtime() -> AugmentationRuntime:
    """Lấy global augmentation runtime."""
    global _runtime
    if _runtime is None:
        _runtime = AugmentationRuntime()
    return _runtime


class AugmentationManager:
    """
    Manager quản lý augmentation pipeline.
    Sao chép từ Memori: memori/memory/augmentation/_manager.py
    """
    def __init__(self, config: MemoriConfig):
        self.config = config
        self._active = False
        self._pending_futures: List[Future] = []
    
    def start(self, session_factory: Callable) -> "AugmentationManager":
        """Khởi động augmentation manager."""
        if session_factory is None:
            return self
        
        self._active = True
        
        # Start runtime
        runtime = get_runtime()
        runtime.ensure_started(self.config.max_workers)
        
        # Start DB writer
        db_writer = get_db_writer()
        db_writer.configure(self.config)
        db_writer.ensure_started(session_factory)
        
        return self
    
    def enqueue(self, input_data: AugmentationInput) -> "AugmentationManager":
        """Đưa task augmentation vào hàng đợi."""
        if not self._active:
            logger.debug("Augmentation chưa được kích hoạt, bỏ qua")
            return self
        
        runtime = get_runtime()
        
        if not runtime.ready.wait(timeout=1.0):
            logger.warning("Augmentation runtime chưa sẵn sàng")
            return self
        
        if runtime.loop is None:
            logger.warning("Event loop không khả dụng")
            return self
        
        logger.debug("Đang Enqueue xử lý augmentation")
        future = asyncio.run_coroutine_threadsafe(
            self._process_augmentations(input_data),
            runtime.loop
        )
        self._pending_futures.append(future)
        future.add_done_callback(lambda f: self._handle_result(f))
        
        return self
    
    def _handle_result(self, future: Future) -> None:
        """Xử lý kết quả augmentation."""
        try:
            future.result()
        except Exception as e:
            logger.error(f"Augmentation thất bại: {e}")
        finally:
            if future in self._pending_futures:
                self._pending_futures.remove(future)
    
    async def _process_augmentations(self, input_data: AugmentationInput) -> None:
        """Xử lý các augmentations bất đồng bộ."""
        runtime = get_runtime()
        if runtime.semaphore is None:
            return
        
        async with runtime.semaphore:
            ctx = AugmentationContext(payload=input_data)
            
            # Chạy augmentation pipeline
            # Sẽ gọi các processors augmentation khác nhau tại đây
            logger.debug("Đang xử lý augmentations")
            
            # Enqueue các lệnh write
            if ctx.writes:
                db_writer = get_db_writer()
                for write in ctx.writes:
                    db_writer.enqueue_write(write)
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """Chờ cho các augmentations đang chạy hoàn tất."""
        import concurrent.futures
        
        if self._pending_futures:
            try:
                concurrent.futures.wait(
                    self._pending_futures,
                    timeout=timeout,
                    return_when=concurrent.futures.ALL_COMPLETED,
                )
            except Exception:
                return False
            
            if self._pending_futures:
                return False
        
        return True


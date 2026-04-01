"""
Job service để quản lý các background jobs.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import Job, JobStatus, JobType
from app.services.analytics.workspace_service import WorkspaceService, PermissionDeniedError


class JobServiceError(Exception):
    """Base exception cho job service errors."""
    pass


class JobNotFoundError(JobServiceError):
    """Không tìm thấy Job."""
    pass


class JobService:
    """
    Job service để quản lý các background jobs.
    """
    
    def __init__(self, session):
        self.session = session
        self._is_async = isinstance(session, AsyncSession)
    
    # =========================================================================
    # ASYNC METHODS
    # =========================================================================
    
    async def create(
        self,
        workspace_id: UUID,
        job_type: str,
        document_version_id: UUID = None,
        config: dict = None,
    ) -> Job:
        """
        Tạo job mới.
        
        Args:
            workspace_id: ID Workspace
            job_type: Loại Job (OCR, INDEX, CONVERT)
            document_version_id: ID Document version (tùy chọn)
            config: Cấu hình Job (tùy chọn)
            
        Returns:
            Job đã tạo
        """
        job = Job(
            workspace_id=workspace_id,
            document_version_id=document_version_id,
            type=job_type,
            status=JobStatus.QUEUED,
            config_json=config or {},
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job
    
    async def get(self, job_id: UUID, user_id: UUID = None) -> Job:
        """Lấy job theo ID."""
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise JobNotFoundError("Không tìm thấy Job")
        
        # Kiểm tra quyền nếu có user_id
        if user_id:
            workspace_service = WorkspaceService(self.session)
            if not await workspace_service.check_permission(
                job.workspace_id, user_id, "read"
            ):
                raise PermissionDeniedError("Không có quyền xem job này")
        
        return job
    
    async def list(
        self,
        workspace_id: UUID,
        user_id: UUID,
        status: str = None,
        job_type: str = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Job]:
        """Liệt kê jobs trong workspace với filter."""
        workspace_service = WorkspaceService(self.session)
        if not await workspace_service.check_permission(
            workspace_id, user_id, "read"
        ):
            raise PermissionDeniedError("Không có quyền liệt kê jobs")
        
        query = select(Job).where(Job.workspace_id == workspace_id)
        
        if status:
            query = query.where(Job.status == status)
        
        if job_type:
            query = query.where(Job.type == job_type)
        
        query = query.order_by(Job.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_status(
        self,
        job_id: UUID,
        status: str = None,
        step: str = None,
        progress: int = None,
        error_message: str = None,
    ) -> Job:
        """Cập nhật trạng thái và tiến độ của job."""
        job = await self.get(job_id)
        
        if status:
            job.status = status
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            elif status in [JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELED]:
                job.finished_at = datetime.now(timezone.utc)
        
        if step:
            job.step = step
        
        if progress is not None:
            job.progress = progress
        
        if error_message:
            job.error_message = error_message
        
        await self.session.flush()
        await self.session.refresh(job)
        return job
    
    async def cancel(self, job_id: UUID, user_id: UUID) -> Job:
        """Hủy một job."""
        job = await self.get(job_id, user_id)
        
        workspace_service = WorkspaceService(self.session)
        if not await workspace_service.check_permission(
            job.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền hủy job")
        
        if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
            raise JobServiceError("Không thể hủy job này")
        
        job.status = JobStatus.CANCELED
        job.finished_at = datetime.now(timezone.utc)
        
        await self.session.flush()
        await self.session.refresh(job)
        
        # TODO: Revoke Celery task nếu đang chạy
        
        return job
    
    # =========================================================================
    # SYNC METHODS (cho Celery tasks)
    # =========================================================================
    
    def update_status_sync(
        self,
        job_id: UUID,
        status: str = None,
        step: str = None,
        progress: int = None,
        error_message: str = None,
    ) -> Job:
        """Phiên bản đồng bộ của update_status cho Celery tasks."""
        result = self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise JobNotFoundError("Không tìm thấy Job")
        
        if status:
            job.status = status
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            elif status in [JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELED]:
                job.finished_at = datetime.now(timezone.utc)
        
        if step:
            job.step = step
        
        if progress is not None:
            job.progress = progress
        
        if error_message:
            job.error_message = error_message
        
        return job
    
    def get_sync(self, job_id: UUID) -> Job:
        """Phiên bản đồng bộ của get cho Celery tasks."""
        result = self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise JobNotFoundError("Không tìm thấy Job")
        
        return job
    
    # =========================================================================
    # QUEUE METHODS
    # =========================================================================
    
    async def enqueue(self, job: Job) -> str:
        """
        Đẩy job vào hàng đợi Celery.
        
        Args:
            job: Job cần đẩy
            
        Returns:
            Celery task ID
        """
        from app.queue.tasks import process_ocr, process_index, process_convert
        
        task_map = {
            JobType.OCR: process_ocr,
            JobType.INDEX: process_index,
            JobType.CONVERT: process_convert,
        }
        
        task_func = task_map.get(job.type)
        if not task_func:
            raise JobServiceError(f"Loại job không xác định: {job.type}")
        
        # Gửi task tới Celery
        result = task_func.delay(
            str(job.id),
            str(job.document_version_id) if job.document_version_id else None,
            job.config_json,
        )
        
        return result.id
    
    async def get_queued_jobs(self) -> List[Job]:
        """Lấy tất cả jobs đang queued để recovery sau khi restart."""
        result = await self.session.execute(
            select(Job)
            .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            .order_by(Job.created_at)
        )
        return list(result.scalars().all())

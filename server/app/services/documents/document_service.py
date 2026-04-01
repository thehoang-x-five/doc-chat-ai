"""
Dịch vụ tài liệu (Document service) để quản lý tài liệu và phiên bản (versioning).
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import timedelta
import hashlib

logger = logging.getLogger(__name__)

from fastapi import UploadFile
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Document, DocumentVersion, Chunk, Job, 
    DocumentStatus, JobType, JobStatus
)
from app.storage.object_store import ObjectStore
from app.utils.validation import (
    validate_file, detect_mime_type, get_document_type
)
from app.services.analytics.workspace_service import WorkspaceService, PermissionDeniedError


class DocumentServiceError(Exception):
    """Exception cơ sở cho các lỗi của document service."""
    pass


class DocumentNotFoundError(DocumentServiceError):
    """Không tìm thấy tài liệu."""
    pass


class InvalidFileError(DocumentServiceError):
    """Loại tệp hoặc kích thước không hợp lệ."""
    pass


class DocumentService:
    """
    Dịch vụ tài liệu xử lý tải lên, lập phiên bản và quản lý.
    """
    
    def __init__(self, session: AsyncSession, storage: ObjectStore = None):
        self.session = session
        self.storage = storage or ObjectStore()
        self.workspace_service = WorkspaceService(session)
    
    # =========================================================================
    # UPLOAD
    # =========================================================================
    
    async def upload(
        self,
        workspace_id: UUID,
        user_id: UUID,
        file: UploadFile,
        tags: List[str] = None,
    ) -> Document:
        """
        Tải lên một tệp và tạo bản ghi tài liệu.
        
        Args:
            workspace_id: ID Workspace
            user_id: ID người dùng tải lên
            file: Tệp tải lên
            tags: Thẻ tùy chọn
            
        Returns:
            Document đã tạo
        """
        # Kiểm tra quyền
        if not await self.workspace_service.check_permission(
            workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền upload")
        
        # Lấy kích thước tệp mà không nạp toàn bộ vào RAM
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        # Validate tệp
        is_valid, error = validate_file(file.filename, file_size)
        if not is_valid:
            raise InvalidFileError(error)
        
        # Tạo tài liệu
        doc_type = get_document_type(file.filename)
        document = Document(
            workspace_id=workspace_id,
            title=file.filename,
            doc_type=doc_type,
            source="upload",
            tags=tags or [],
            status=DocumentStatus.NEW,
            created_by=user_id,
        )
        self.session.add(document)
        await self.session.flush()
        
        # Upload lên storage thông qua stream để tiết kiệm RAM
        file_key = ObjectStore.generate_key(
            str(workspace_id),
            str(document.id),
            file.filename,
            prefix="documents",
        )
        self.storage.upload(
            file_key,
            file.file,
            content_type=detect_mime_type(file.filename),
        )
        file.file.seek(0) # Reset lại nếu cần dùng sau này
        
        # Tính toán checksum bằng cách đọc từng chunk thay vì load RAM
        sha256_hash = hashlib.sha256()
        for chunk in iter(lambda: file.file.read(4096 * 1024), b""):
            sha256_hash.update(chunk)
        checksum = sha256_hash.hexdigest()
        file.file.seek(0)

        # Kiểm tra trùng lặp (dedup) trong cùng workspace
        existing = await self.session.execute(
            select(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(
                Document.workspace_id == workspace_id,
                Document.status.notin_(["DELETED", "ARCHIVED", "FAILED"]),
                DocumentVersion.checksum_sha256 == checksum,
            )
        )
        dup_version = existing.scalar_one_or_none()
        if dup_version:
            dup_doc = await self.session.get(Document, dup_version.document_id)
            dup_title = dup_doc.title if dup_doc else "unknown"
            # Xóa file đã upload lên MinIO
            try:
                self.storage.delete(file_key)
            except Exception:
                pass
            # Xóa document placeholder vừa tạo
            await self.session.delete(document)
            await self.session.flush()
            raise InvalidFileError(
                f"File trùng lặp — nội dung giống với tài liệu \"{dup_title}\" đã có trong workspace."
            )

        # Tạo phiên bản tài liệu
        version = DocumentVersion(
            document_id=document.id,
            version=1,
            original_file_key=file_key,
            mime_type=detect_mime_type(file.filename),
            size_bytes=file_size,
            checksum_sha256=checksum,
        )
        self.session.add(version)
        await self.session.flush()
        
        # Tạo job OCR
        job = Job(
            workspace_id=workspace_id,
            document_version_id=version.id,
            type=JobType.OCR,
            status=JobStatus.QUEUED,
        )
        self.session.add(job)
        await self.session.flush()
        
        # Cập nhật trạng thái tài liệu
        document.status = DocumentStatus.INDEXING
        await self.session.refresh(document)
        
        # *** Dispatch Celery OCR task ***
        await self._dispatch_ocr(job.id, version.id, document.id)
        
        return document
    
    async def create_presigned_upload(
        self,
        workspace_id: UUID,
        user_id: UUID,
        filename: str,
        size: int,
        mime_type: Optional[str] = None,
        tags: List[str] = None,
    ) -> tuple[Document, str]:
        """Tạo URL presigned cho frontend tải trực tiếp (bỏ qua proxy)."""
        if not await self.workspace_service.check_permission(workspace_id, user_id, "write"):
            raise PermissionDeniedError("Không có quyền upload")
            
        is_valid, error = validate_file(filename, size)
        if not is_valid:
            raise InvalidFileError(error)
            
        doc_type = get_document_type(filename)
        document = Document(
            workspace_id=workspace_id,
            title=filename,
            doc_type=doc_type,
            source="upload",
            tags=tags or [],
            status=DocumentStatus.UPLOADING,
            created_by=user_id,
        )
        self.session.add(document)
        await self.session.flush()
        
        file_key = ObjectStore.generate_key(
            str(workspace_id), str(document.id), filename, prefix="documents"
        )
        url = self.storage.get_presigned_upload_url(file_key, expires=timedelta(hours=2))
        
        version = DocumentVersion(
            document_id=document.id,
            version=1,
            original_file_key=file_key,
            mime_type=mime_type or detect_mime_type(filename),
            size_bytes=size,
        )
        self.session.add(version)
        await self.session.commit()
        
        return document, url

    async def confirm_presigned_upload(self, document_id: UUID, user_id: UUID) -> Document:
        """Xác nhận frontend đã upload xong vào MinIO và đưa vào hàng đợi."""
        document = await self.get(document_id, user_id)
        if not await self.workspace_service.check_permission(document.workspace_id, user_id, "write"):
            raise PermissionDeniedError("Không có quyền ghi")
            
        if document.status != DocumentStatus.UPLOADING:
            return document
            
        versions = await self.get_versions(document_id, user_id)
        if not versions:
            raise DocumentNotFoundError("No versions found")
        latest_version = versions[0]
        
        if not self.storage.exists(latest_version.original_file_key):
            document.status = DocumentStatus.FAILED
            await self.session.commit()
            raise InvalidFileError("File not found in storage after upload.")
            
        job = Job(
            workspace_id=document.workspace_id,
            document_version_id=latest_version.id,
            type=JobType.OCR,
            status=JobStatus.QUEUED,
        )
        self.session.add(job)
        document.status = DocumentStatus.INDEXING
        await self.session.commit()
        
        await self._dispatch_ocr(job.id, latest_version.id, document.id)
        return document
    
    async def upload_from_url(
        self,
        workspace_id: UUID,
        user_id: UUID,
        url: str,
        title: str = None,
        tags: List[str] = None,
    ) -> Document:
        """
        Tạo tài liệu từ URL.
        
        Args:
            workspace_id: ID Workspace
            user_id: ID người dùng
            url: URL nguồn
            title: Tiêu đề tùy chọn
            tags: Thẻ tùy chọn
            
        Returns:
            Document đã tạo
        """
        # Kiểm tra quyền
        if not await self.workspace_service.check_permission(
            workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền upload")
        
        # Tạo tài liệu
        document = Document(
            workspace_id=workspace_id,
            title=title or url,
            doc_type="url",
            source="url",
            tags=tags or [],
            status=DocumentStatus.NEW,
            created_by=user_id,
        )
        self.session.add(document)
        await self.session.flush()
        
        # Tạo phiên bản với URL làm key
        version = DocumentVersion(
            document_id=document.id,
            version=1,
            original_file_key=url,
        )
        self.session.add(version)
        await self.session.flush()
        
        # Tạo job OCR
        job = Job(
            workspace_id=workspace_id,
            document_version_id=version.id,
            type=JobType.OCR,
            status=JobStatus.QUEUED,
            config_json={"url": url},
        )
        self.session.add(job)
        await self.session.flush()
        
        document.status = DocumentStatus.INDEXING
        await self.session.refresh(document)
        
        # *** Dispatch Celery OCR task ***
        await self._dispatch_ocr(job.id, version.id, document.id)
        
        return document

    # =========================================================================
    # CELERY DISPATCH
    # =========================================================================
    
    async def _dispatch_ocr(self, job_id, version_id, document_id):
        """
        Dispatch OCR processing to Celery, with sync fallback.
        Called after the DB transaction is flushed (job+version exist).
        """
        try:
            from app.queue.tasks.ocr import process_ocr
            process_ocr.apply_async(args=[str(job_id), str(version_id)], countdown=3)
            logger.info(f"Document {document_id} queued for Celery OCR processing (3s delay)")
        except Exception as e:
            logger.warning(f"Celery not available ({e}), will use sync fallback")
            # Sync fallback happens in the API layer if needed

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    async def get(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        """Lấy tài liệu theo ID."""
        result = await self.session.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise DocumentNotFoundError("Không tìm thấy tài liệu")
        
        # Kiểm tra quyền
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "read"
        ):
            raise PermissionDeniedError("Không có quyền xem tài liệu")
        
        return document
    
    async def list(
        self,
        workspace_id: UUID,
        user_id: UUID,
        status: str = None,
        tags: List[str] = None,
        search: str = None,
        skip: int = 0,
        limit: int = 50,
        include_archived: bool = False,
    ) -> List[dict]:
        """Liệt kê tài liệu trong workspace với bộ lọc. Trả về enriched document dicts."""
        # Kiểm tra quyền
        if not await self.workspace_service.check_permission(
            workspace_id, user_id, "read"
        ):
            raise PermissionDeniedError("Không có quyền liệt kê tài liệu")
        
        query = select(Document).where(Document.workspace_id == workspace_id)
        
        if status:
            query = query.where(Document.status == status)
        elif not include_archived:
            # By default, exclude ARCHIVED and DELETED documents
            query = query.where(Document.status.not_in([DocumentStatus.ARCHIVED, DocumentStatus.DELETED]))
        else:
            # If including archived, we still want to filter out DELETED
            query = query.where(Document.status != DocumentStatus.DELETED)
        
        if tags:
            query = query.where(Document.tags.overlap(tags))
        
        if search:
            query = query.where(Document.title.ilike(f"%{search}%"))
        
        query = query.order_by(Document.created_at.desc())
        query = query.offset(skip).limit(limit)
        query = query.options(selectinload(Document.versions))
        
        result = await self.session.execute(query)
        documents = list(result.scalars().all())
        
        # Bổ sung thông tin phiên bản
        enriched = []
        for doc in documents:
            doc_dict = {
                "id": doc.id,
                "workspace_id": doc.workspace_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "source": doc.source,
                "tags": doc.tags or [],
                "status": doc.status,
                "category_id": doc.category_id,
                "content_summary": doc.content_summary,
                "processing_progress": doc.processing_progress or 0,
                "processing_step": doc.processing_step,
                "created_by": doc.created_by,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "size": 0,
                "mime_type": None,
                "chunk_count": 0,
                "version": 1,
            }
            
            # Lấy thông tin phiên bản mới nhất
            if doc.versions:
                latest = max(doc.versions, key=lambda v: v.version)
                doc_dict["size"] = latest.size_bytes or 0
                doc_dict["mime_type"] = latest.mime_type
                doc_dict["version"] = latest.version
                
                # Đếm số chunks
                chunk_count_result = await self.session.execute(
                    select(func.count(Chunk.id)).where(
                        Chunk.document_version_id == latest.id
                    )
                )
                doc_dict["chunk_count"] = chunk_count_result.scalar() or 0
            
            enriched.append(doc_dict)
        
        return enriched

    async def update_tags(
        self,
        document_id: UUID,
        user_id: UUID,
        tags: List[str],
    ) -> Document:
        """Cập nhật tags cho tài liệu."""
        document = await self.get(document_id, user_id)
        
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền cập nhật tài liệu")
        
        document.tags = tags
        await self.session.flush()
        await self.session.refresh(document)
        
        return document
    
    async def delete(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Xóa vĩnh viễn tài liệu kèm chunks, versions, và vectors."""
        document = await self.get(document_id, user_id)
        
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền xóa tài liệu")
        
        # Xóa vectors khỏi vector store
        try:
            from app.services.core.embedding_service import EmbeddingService
            emb_service = EmbeddingService()
            await emb_service.delete_document_vectors(str(document_id))
            logger.info(f"Deleted vectors for document {document_id}")
        except Exception as e:
            logger.warning(f"Could not delete vectors for {document_id}: {e}")
        
        # Xóa chunks thuộc tất cả versions
        for version in document.versions:
            await self.session.execute(
                delete(Chunk).where(Chunk.document_version_id == version.id)
            )
        
        # Xóa document (cascade xóa versions) hoặc đánh dấu DELETED
        if document.status in [DocumentStatus.NEW, DocumentStatus.INDEXING, "processing"]:
            document.status = DocumentStatus.DELETED
            document.processing_step = "Canceled by user"
            await self.session.flush()
            logger.info(f"Marked document {document_id} as DELETED for graceful cancellation")
        else:
            await self.session.execute(
                delete(Document).where(Document.id == document_id)
            )
            await self.session.flush()
            logger.info(f"Hard-deleted document {document_id} with all chunks and versions")
            
        return True

    async def archive(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        """Lưu trữ tài liệu — ẩn khỏi danh sách và chat nhưng không xóa."""
        document = await self.get(document_id, user_id)
        
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền lưu trữ tài liệu")
        
        document.status = DocumentStatus.ARCHIVED
        await self.session.flush()
        await self.session.refresh(document)
        
        logger.info(f"Archived document {document_id}")
        return document

    async def restore(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Document:
        """Khôi phục tài liệu đã lưu trữ về trạng thái READY."""
        result = await self.session.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise DocumentNotFoundError("Không tìm thấy tài liệu")
        
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền khôi phục tài liệu")
        
        document.status = DocumentStatus.READY_BASIC
        await self.session.flush()
        await self.session.refresh(document)
        
        logger.info(f"Restored document {document_id}")
        return document
    
    # =========================================================================
    # VERSIONING
    # =========================================================================
    
    async def reindex(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> Job:
        """
        Re-index tài liệu bằng cách tạo phiên bản mới.
        Giữ lại các phiên bản trước đó.
        """
        document = await self.get(document_id, user_id)
        
        if not await self.workspace_service.check_permission(
            document.workspace_id, user_id, "write"
        ):
            raise PermissionDeniedError("Không có quyền reindex")
        
        # Lấy phiên bản mới nhất
        result = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        
        if not latest:
            raise DocumentServiceError("Không tìm thấy version nào")

        # Tạo phiên bản mới
        new_version = DocumentVersion(
            document_id=document_id,
            version=latest.version + 1,
            original_file_key=latest.original_file_key,
            mime_type=latest.mime_type,
            size_bytes=latest.size_bytes,
            checksum_sha256=latest.checksum_sha256,
        )
        self.session.add(new_version)
        await self.session.flush()
        
        # Tạo job OCR
        job = Job(
            workspace_id=document.workspace_id,
            document_version_id=new_version.id,
            type=JobType.OCR,
            status=JobStatus.QUEUED,
        )
        self.session.add(job)
        await self.session.flush()
        
        # Cập nhật trạng thái tài liệu
        document.status = DocumentStatus.INDEXING
        
        return job
    
    async def get_versions(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> List[DocumentVersion]:
        """Lấy tất cả các phiên bản của tài liệu."""
        document = await self.get(document_id, user_id)
        
        result = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())
        )
        return list(result.scalars().all())
    
    async def get_chunks(
        self,
        document_id: UUID,
        user_id: UUID,
        version: int = None,
    ) -> List[Chunk]:
        """Lấy các chunks của tài liệu (mặc định là phiên bản mới nhất)."""
        document = await self.get(document_id, user_id)
        
        # Lấy version
        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        )
        if version:
            query = query.where(DocumentVersion.version == version)
        else:
            query = query.order_by(DocumentVersion.version.desc()).limit(1)
        
        result = await self.session.execute(query)
        doc_version = result.scalar_one_or_none()
        
        if not doc_version:
            return []
        
        # Lấy chunks
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.document_version_id == doc_version.id)
            .order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_all_tags(
        self,
        user_id: UUID,
        workspace_id: UUID = None,
    ) -> List[dict]:
        """
        Lấy tất cả các tag duy nhất từ tài liệu cùng với số lượng.
        
        Args:
            user_id: ID người dùng để kiểm tra quyền
            workspace_id: Bộ lọc workspace tùy chọn
            
        Returns:
            Danh sách {"name": tag, "count": count}
        """
        from sqlalchemy import func, text
        from app.db.models import WorkspaceUser
        
        # Build query to get tags from accessible workspaces
        if workspace_id:
            # Kiểm tra quyền cho workspace cụ thể
            if not await self.workspace_service.check_permission(
                workspace_id, user_id, "read"
            ):
                raise PermissionDeniedError("Không có quyền truy cập workspace")
            
            # Lấy tags từ workspace này
            result = await self.session.execute(
                text("""
                    SELECT unnest(tags) as tag, COUNT(*) as count
                    FROM documents
                    WHERE workspace_id = :workspace_id
                    AND status != 'DELETED'
                    AND tags IS NOT NULL
                    AND array_length(tags, 1) > 0
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                """),
                {"workspace_id": str(workspace_id)}
            )
        else:
            # Lấy tags từ tất cả các workspace có quyền truy cập
            accessible_workspaces = await self.session.execute(
                select(WorkspaceUser.workspace_id).where(
                    WorkspaceUser.user_id == user_id
                )
            )
            workspace_ids = [str(w[0]) for w in accessible_workspaces.all()]
            
            if not workspace_ids:
                return []
            
            result = await self.session.execute(
                text("""
                    SELECT unnest(tags) as tag, COUNT(*) as count
                    FROM documents
                    WHERE workspace_id = ANY(:workspace_ids::uuid[])
                    AND status != 'DELETED'
                    AND tags IS NOT NULL
                    AND array_length(tags, 1) > 0
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                """),
                {"workspace_ids": workspace_ids}
            )
        
        rows = result.fetchall()
        return [{"name": row.tag, "count": row.count} for row in rows]

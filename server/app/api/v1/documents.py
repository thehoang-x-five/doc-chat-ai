"""
Document API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, resolve_workspace_id
from app.services.documents.document_service import (
    DocumentService,
    DocumentNotFoundError,
    InvalidFileError,
    DocumentServiceError,
)
from app.services.analytics.workspace_service import PermissionDeniedError
from app.schemas.document import (
    UploadFromUrlRequest,
    UpdateDocumentRequest,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentVersionResponse,
    ChunkResponse,
)
from app.schemas.job import JobResponse
from app.db.models import User


from fastapi.security import HTTPAuthorizationCredentials
from app.api.deps import security

async def get_current_user_with_token(
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Allow authentication via query parameter ?token=... or standard Bearer header."""
    actual_token = token
    if not actual_token and credentials:
        actual_token = credentials.credentials
        
    if not actual_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
    from app.core.security import verify_access_token
    payload = verify_access_token(actual_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    import uuid
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == getattr(uuid, "UUID", uuid.UUID)(payload.sub)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

router = APIRouter(prefix="/documents", tags=["Documents"])

# NOTE: Static routes must be defined BEFORE dynamic routes with path parameters
# to avoid FastAPI matching "/tags" as "/{document_id}"

@router.get("/tags", response_model=List[dict])
async def get_document_tags(
    workspace_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all unique tags from documents with counts.
    Optionally filter by workspace_id.
    Returns: [{"name": "tag1", "count": 5}, ...]
    """
    service = DocumentService(db)
    
    try:
        actual_workspace_id = None
        if workspace_id:
            actual_workspace_id = await resolve_workspace_id(workspace_id, current_user, db)
        tags = await service.get_all_tags(
            user_id=current_user.id,
            workspace_id=actual_workspace_id,
        )
        return tags
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document file.
    Tags should be comma-separated string.
    """
    service = DocumentService(db)
    
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    
    try:
        actual_workspace_id = await resolve_workspace_id(workspace_id, current_user, db)
        document = await service.upload(
            workspace_id=actual_workspace_id,
            user_id=current_user.id,
            file=file,
            tags=tag_list,
        )
        return DocumentResponse.model_validate(document)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidFileError as e:
        from app.core.config import settings as app_settings
        raise HTTPException(
            status_code=415,
            detail={
                "message": str(e),
                "supported_formats": sorted(app_settings.ALLOWED_EXTENSIONS),
            },
        )


@router.post("/upload-url", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_from_url(
    workspace_id: str,
    data: UploadFromUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload document from URL."""
    service = DocumentService(db)
    
    try:
        actual_workspace_id = await resolve_workspace_id(workspace_id, current_user, db)
        document = await service.upload_from_url(
            workspace_id=actual_workspace_id,
            user_id=current_user.id,
            url=str(data.url),
            title=data.title,
            tags=data.tags,
        )
        return DocumentResponse.model_validate(document)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    workspace_id: str,
    status: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents in workspace with filters."""
    service = DocumentService(db)
    
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    
    try:
        actual_workspace_id = await resolve_workspace_id(workspace_id, current_user, db)
        documents = await service.list(
            workspace_id=actual_workspace_id,
            user_id=current_user.id,
            status=status,
            tags=tag_list,
            search=search,
            skip=skip,
            limit=limit,
            include_archived=include_archived,
        )
        return DocumentListResponse(
            documents=[DocumentResponse(**d) for d in documents],
            total=len(documents),
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details with versions."""
    service = DocumentService(db)
    
    try:
        document = await service.get(document_id, current_user.id)
        versions = await service.get_versions(document_id, current_user.id)
        
        return DocumentDetailResponse(
            **DocumentResponse.model_validate(document).model_dump(),
            versions=[DocumentVersionResponse.model_validate(v) for v in versions],
            latest_version=DocumentVersionResponse.model_validate(versions[0]) if versions else None,
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{document_id}/presigned-confirm", response_model=DocumentDetailResponse)
async def confirm_presigned_upload_url(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a presigned upload and enqueue the processing job."""
    service = DocumentService(db)
    try:
        document = await service.confirm_presigned_upload(document_id, current_user.id)
        versions = await service.get_versions(document_id, current_user.id)
        return DocumentDetailResponse(
            **DocumentResponse.model_validate(document).model_dump(),
            versions=[DocumentVersionResponse.model_validate(v) for v in versions],
            latest_version=DocumentVersionResponse.model_validate(versions[0]) if versions else None,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidFileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Presigned confirm failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Presigned confirm error: {str(e)}"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    data: UpdateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update document tags."""
    service = DocumentService(db)
    
    try:
        document = await service.update_tags(
            document_id=document_id,
            user_id=current_user.id,
            tags=data.tags,
        )
        return DocumentResponse.model_validate(document)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete document permanently (hard delete: DB + VectorDB)."""
    service = DocumentService(db)
    
    try:
        await service.delete(document_id, current_user.id)
        return {"success": True, "message": "Document deleted permanently"}
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{document_id}/archive")
async def archive_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive document — hide from list and chat but keep data."""
    service = DocumentService(db)
    
    try:
        doc = await service.archive(document_id, current_user.id)
        return {"success": True, "message": "Document archived", "status": doc.status}
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{document_id}/restore")
async def restore_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore archived document back to READY status."""
    service = DocumentService(db)
    
    try:
        doc = await service.restore(document_id, current_user.id)
        return {"success": True, "message": "Document restored", "status": doc.status}
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{document_id}/reindex", response_model=JobResponse)
async def reindex_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-index document (creates new version)."""
    service = DocumentService(db)
    
    try:
        job = await service.reindex(document_id, current_user.id)
        return JobResponse.model_validate(job)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except DocumentServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{document_id}/versions", response_model=List[DocumentVersionResponse])
async def get_document_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a document."""
    service = DocumentService(db)
    
    try:
        versions = await service.get_versions(document_id, current_user.id)
        return [DocumentVersionResponse.model_validate(v) for v in versions]
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: UUID,
    version: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chunks for document."""
    service = DocumentService(db)
    
    try:
        chunks = await service.get_chunks(document_id, current_user.id, version)
        return [ChunkResponse.model_validate(c) for c in chunks]
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: UUID,
    format: str = Query("text", description="Output format: text or markdown"),
    current_user: User = Depends(get_current_user_with_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the full extracted text content of a document.
    Returns the complete OCR/parsed text stored in MinIO, not the chunked version.
    Supports 'text' (plain text) or 'markdown' format.
    """
    from fastapi.responses import PlainTextResponse
    service = DocumentService(db)

    try:
        document = await service.get(document_id, current_user.id)
        versions = await service.get_versions(document_id, current_user.id)
        if not versions:
            raise HTTPException(status_code=404, detail="No versions found")

        latest = versions[0]
        workspace_id = str(document.workspace_id)
        doc_id = str(document.id)
        version = latest.version

        from app.storage.object_store import ObjectStore
        store = ObjectStore()

        # Try to load the requested format from MinIO
        if format == "markdown":
            key = f"outputs/{workspace_id}/{doc_id}/v{version}/content.md"
        else:
            key = f"outputs/{workspace_id}/{doc_id}/v{version}/text.txt"

        try:
            content_bytes = store.download(key)
            content = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            # Fallback: try the other format
            fallback_key = f"outputs/{workspace_id}/{doc_id}/v{version}/{'text.txt' if format == 'markdown' else 'content.md'}"
            try:
                content_bytes = store.download(fallback_key)
                content = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                # Last resort: concatenate chunks
                chunks = await service.get_chunks(document_id, current_user.id)
                content = "\n\n".join(c.content for c in chunks if c.content)

        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    mode: str = Query("inline", description="inline (for viewer) or attachment (for save-to-disk)"),
    current_user: User = Depends(get_current_user_with_token),
    db: AsyncSession = Depends(get_db),
):
    """Download the original uploaded file for viewing/rendering.
    
    Always streams file through the backend to avoid CORS issues
    when MinIO is on a different origin than the frontend.
    """
    service = DocumentService(db)

    try:
        document = await service.get(document_id, current_user.id)
        versions = await service.get_versions(document_id, current_user.id)
        if not versions:
            raise HTTPException(status_code=404, detail="No versions found")

        latest = versions[0]
        file_key = latest.original_file_key
        mime_type = latest.mime_type or "application/octet-stream"
        filename = document.title or "download"

        from app.storage.object_store import ObjectStore
        store = ObjectStore()
        
        disposition = "attachment" if mode == "attachment" else "inline"

        # Local storage -> use FileResponse (automatic Range support + CORS via middleware)
        if store._use_local:
            local_path = store._local_store._get_path(file_key)
            if not local_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found on disk: {file_key}"
                )
            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(local_path),
                filename=filename,
                media_type=mime_type,
                content_disposition_type=disposition,
            )

        # MinIO storage -> try MinIO first, then fall back to local storage
        # (Older files may still be in local storage before MinIO was enabled)
        from fastapi.responses import StreamingResponse
        from app.storage.object_store import LocalFileStore
        
        # Check if file exists in MinIO
        try:
            stat = store._client.stat_object(store.bucket, file_key)
            file_in_minio = True
        except Exception:
            file_in_minio = False
        
        if file_in_minio:
            response_obj = store._client.get_object(store.bucket, file_key)
            
            def iter_file():
                try:
                    for chunk in response_obj.stream(amt=64 * 1024):
                        yield chunk
                finally:
                    response_obj.close()
                    response_obj.release_conn()
            
            headers = {
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Accept-Ranges": "bytes",
                "Content-Length": str(stat.size),
            }
            
            return StreamingResponse(
                iter_file(),
                media_type=mime_type,
                headers=headers,
            )
        
        # Fallback: try local storage (for files uploaded before MinIO was enabled)
        local_store = LocalFileStore()
        local_path = local_store._get_path(file_key)
        if local_path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(local_path),
                filename=filename,
                media_type=mime_type,
                content_disposition_type=disposition,
            )
        
        raise HTTPException(
            status_code=404,
            detail=f"File not found in MinIO or local storage: {file_key}"
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

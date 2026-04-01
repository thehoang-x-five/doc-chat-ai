"""
Workspace API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.analytics.workspace_service import (
    WorkspaceService,
    WorkspaceNotFoundError,
    PermissionDeniedError,
    MemberExistsError,
    WorkspaceServiceError,
)
from app.services.documents.document_service import (
    DocumentService,
    DocumentNotFoundError,
    InvalidFileError,
    DocumentServiceError,
)
from app.schemas.workspace import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    AddMemberRequest,
    UpdateMemberRoleRequest,
    WorkspaceResponse,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    MemberResponse,
)
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
)
from app.schemas.common import SuccessResponse
from app.db.models import User


router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace. Creator becomes OWNER."""
    service = WorkspaceService(db)
    
    workspace = await service.create(
        user_id=current_user.id,
        name=data.name,
        plan=data.plan,
        answer_policy=data.answer_policy,
        evidence_threshold=data.evidence_threshold,
    )
    
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workspaces where current user is a member."""
    service = WorkspaceService(db)
    
    workspaces = await service.list_for_user(current_user.id)
    
    return WorkspaceListResponse(
        workspaces=[WorkspaceResponse.model_validate(w) for w in workspaces],
        total=len(workspaces),
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get workspace details. User must be a member."""
    service = WorkspaceService(db)
    
    try:
        workspace = await service.get(workspace_id, current_user.id)
        members = await service.get_members(workspace_id, current_user.id)
        
        return WorkspaceDetailResponse(
            **WorkspaceResponse.model_validate(workspace).model_dump(),
            members=[
                MemberResponse(
                    user_id=m.user_id,
                    email=m.user.email if m.user else "",
                    full_name=m.user.full_name if m.user else None,
                    role=m.role,
                    joined_at=m.joined_at,
                )
                for m in members
            ],
            member_count=len(members),
        )
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    data: UpdateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace settings. Only OWNER can update."""
    service = WorkspaceService(db)
    
    try:
        workspace = await service.update(
            workspace_id=workspace_id,
            user_id=current_user.id,
            name=data.name,
            answer_policy=data.answer_policy,
            evidence_threshold=data.evidence_threshold,
        )
        return WorkspaceResponse.model_validate(workspace)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.delete("/{workspace_id}", response_model=SuccessResponse)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete workspace. Only OWNER can delete."""
    service = WorkspaceService(db)
    
    try:
        await service.delete(workspace_id, current_user.id)
        return SuccessResponse(message="Workspace deleted")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =============================================================================
# MEMBER MANAGEMENT
# =============================================================================

@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: UUID,
    data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to workspace. Only OWNER can add members."""
    service = WorkspaceService(db)
    
    try:
        membership = await service.add_member(
            workspace_id=workspace_id,
            owner_id=current_user.id,
            member_email=data.email,
            role=data.role,
        )
        
        # Get user info
        from sqlalchemy import select
        from app.db.models import User as UserModel
        result = await db.execute(
            select(UserModel).where(UserModel.id == membership.user_id)
        )
        user = result.scalar_one()
        
        return MemberResponse(
            user_id=membership.user_id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            joined_at=membership.joined_at,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except MemberExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except WorkspaceServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{workspace_id}/members/{user_id}", response_model=SuccessResponse)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from workspace. Only OWNER can remove members."""
    service = WorkspaceService(db)
    
    try:
        await service.remove_member(workspace_id, current_user.id, user_id)
        return SuccessResponse(message="Member removed")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/{workspace_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    data: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update member's role. Only OWNER can update roles."""
    service = WorkspaceService(db)
    
    try:
        membership = await service.update_member_role(
            workspace_id=workspace_id,
            owner_id=current_user.id,
            member_id=user_id,
            new_role=data.role,
        )
        
        # Get user info
        from sqlalchemy import select
        from app.db.models import User as UserModel
        result = await db.execute(
            select(UserModel).where(UserModel.id == membership.user_id)
        )
        user = result.scalar_one()
        
        return MemberResponse(
            user_id=membership.user_id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            joined_at=membership.joined_at,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except WorkspaceServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}/members", response_model=List[MemberResponse])
async def list_members(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a workspace."""
    service = WorkspaceService(db)
    
    try:
        members = await service.get_members(workspace_id, current_user.id)
        return [
            MemberResponse(
                user_id=m.user_id,
                email=m.user.email if m.user else "",
                full_name=m.user.full_name if m.user else None,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m in members
        ]
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =============================================================================
# DOCUMENT MANAGEMENT (nested under workspace)
# =============================================================================

from app.schemas.document import PresignedUploadRequest, PresignedUploadResponse

@router.post("/{workspace_id}/documents/presigned-upload", response_model=PresignedUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_presigned_upload_url(
    workspace_id: UUID,
    data: PresignedUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a presigned URL to upload a document directly from the browser to MinIO.
    """
    service = DocumentService(db)
    try:
        document, url = await service.create_presigned_upload(
            workspace_id=workspace_id,
            user_id=current_user.id,
            filename=data.filename,
            size=data.size,
            mime_type=data.mime_type,
            tags=data.tags,
        )
        return PresignedUploadResponse(
            document_id=document.id,
            upload_url=url,
        )
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
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Presigned upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Presigned upload error: {str(e)}"
        )
        


@router.post("/{workspace_id}/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_to_workspace(
    workspace_id: UUID,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document to a workspace.
    Document will be automatically dispatched to Celery worker for OCR processing.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    service = DocumentService(db)
    
    # Parse tags
    tag_list = []
    if tags:
        try:
            import json
            tag_list = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    try:
        # DocumentService.upload() now handles:
        # 1. File validation + storage upload
        # 2. DB insert (Document, DocumentVersion, Job)
        # 3. Celery dispatch (process_ocr.delay) with fallback logging
        document = await service.upload(
            workspace_id=workspace_id,
            user_id=current_user.id,
            file=file,
            tags=tag_list,
        )
        
        # Build response with version info
        from sqlalchemy import select, func
        from app.db.models import DocumentVersion, Chunk
        
        version_result = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.created_at.desc())
            .limit(1)
        )
        latest_version = version_result.scalar_one_or_none()
        
        chunk_count = 0
        size = 0
        mime_type = None
        version_num = 1
        
        if latest_version:
            size = latest_version.size_bytes or 0
            mime_type = latest_version.mime_type
            version_num = latest_version.version
            
            count_result = await db.execute(
                select(func.count(Chunk.id)).where(Chunk.document_version_id == latest_version.id)
            )
            chunk_count = count_result.scalar() or 0
        
        return DocumentResponse(
            id=document.id,
            workspace_id=document.workspace_id,
            title=document.title,
            doc_type=document.doc_type,
            source=document.source,
            tags=document.tags or [],
            status=document.status,
            category_id=document.category_id,
            content_summary=document.content_summary,
            created_by=document.created_by,
            created_at=document.created_at,
            updated_at=document.updated_at,
            size=size,
            mime_type=mime_type,
            chunk_count=chunk_count,
            version=version_num,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidFileError as e:

        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}/documents", response_model=DocumentListResponse)
async def list_workspace_documents(
    workspace_id: UUID,
    status: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents in workspace with filters."""
    service = DocumentService(db)
    
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    
    try:
        documents = await service.list(
            workspace_id=workspace_id,
            user_id=current_user.id,
            status=status,
            tags=tag_list,
            search=search,
            skip=skip,
            limit=limit,
        )
        return DocumentListResponse(
            documents=[DocumentResponse(**d) for d in documents],
            total=len(documents),
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

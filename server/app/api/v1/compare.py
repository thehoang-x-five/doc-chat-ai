"""
API endpoints for Document Comparison feature.
Requirements: 21.7, 21.8
"""
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import Optional

from app.api.deps import get_current_user
from app.schemas.auth import UserResponse
from app.schemas.compare import (
    CompareResponse,
    CompareSource,
    CompareSourceType,
    CompareVersionsRequest,
)
from app.services.generation.compare_service import get_compare_service

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=CompareResponse)
async def compare_documents(
    workspace_id: str = Form(...),
    source_a_type: str = Form(...),
    source_a_file: Optional[UploadFile] = File(None),
    source_a_url: Optional[str] = Form(None),
    source_a_document_id: Optional[str] = Form(None),
    source_b_type: str = Form(...),
    source_b_file: Optional[UploadFile] = File(None),
    source_b_url: Optional[str] = Form(None),
    source_b_document_id: Optional[str] = Form(None),
    include_ai_summary: bool = Form(True),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Compare two documents from various sources.
    
    Supports:
    - File upload (PDF, DOCX, TXT, etc.)
    - URL
    - Existing document in KB
    """
    service = get_compare_service()
    
    # Extract text from source A
    text_a, title_a = await _extract_text_from_source(
        source_type=source_a_type,
        file=source_a_file,
        url=source_a_url,
        document_id=source_a_document_id,
    )
    
    # Extract text from source B
    text_b, title_b = await _extract_text_from_source(
        source_type=source_b_type,
        file=source_b_file,
        url=source_b_url,
        document_id=source_b_document_id,
    )
    
    # Build source objects
    source_a = CompareSource(
        type=CompareSourceType(source_a_type),
        url=source_a_url,
        document_id=source_a_document_id,
    )
    source_b = CompareSource(
        type=CompareSourceType(source_b_type),
        url=source_b_url,
        document_id=source_b_document_id,
    )
    
    # Compare
    result = await service.compare(
        workspace_id=workspace_id,
        source_a=source_a,
        text_a=text_a,
        source_b=source_b,
        text_b=text_b,
        include_ai_summary=include_ai_summary,
        user_id=str(current_user.id),
        title_a=title_a,
        title_b=title_b,
    )
    
    return CompareResponse(
        id=result.id,
        workspace_id=result.workspace_id,
        source_a=result.source_a,
        source_b=result.source_b,
        changes=result.changes,
        statistics=result.statistics,
        ai_summary=result.ai_summary,
        created_at=result.created_at,
    )


@router.post("/versions", response_model=CompareResponse)
async def compare_versions(
    request: CompareVersionsRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Compare two versions of the same document"""
    service = get_compare_service()
    
    # TODO: Fetch actual version texts from document service
    # For now, return mock data
    text_a = f"Version {request.version_a} content"
    text_b = f"Version {request.version_b} content"
    
    result = await service.compare_versions(
        workspace_id="",  # Will be fetched from document
        document_id=request.document_id,
        version_a_text=text_a,
        version_b_text=text_b,
        version_a=request.version_a,
        version_b=request.version_b,
        include_ai_summary=request.include_ai_summary,
        user_id=str(current_user.id),
    )
    
    return CompareResponse(
        id=result.id,
        workspace_id=result.workspace_id,
        source_a=result.source_a,
        source_b=result.source_b,
        changes=result.changes,
        statistics=result.statistics,
        ai_summary=result.ai_summary,
        created_at=result.created_at,
    )


@router.get("/{compare_id}", response_model=CompareResponse)
async def get_compare_result(
    compare_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a saved comparison result"""
    service = get_compare_service()
    result = service.get_result(compare_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Comparison result not found")
    
    return CompareResponse(
        id=result.id,
        workspace_id=result.workspace_id,
        source_a=result.source_a,
        source_b=result.source_b,
        changes=result.changes,
        statistics=result.statistics,
        ai_summary=result.ai_summary,
        created_at=result.created_at,
    )


async def _extract_text_from_source(
    source_type: str,
    file: Optional[UploadFile] = None,
    url: Optional[str] = None,
    document_id: Optional[str] = None,
) -> tuple[str, str]:
    """Extract text from various source types"""
    
    if source_type == "upload" and file:
        content = await file.read()
        # Simple text extraction - in production, use OCR service
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="ignore")
        return text, file.filename or "Uploaded File"
    
    elif source_type == "url" and url:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text, url
    
    elif source_type == "document" and document_id:
        # TODO: Fetch from document service
        return f"Document {document_id} content", f"Document {document_id}"
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source configuration for type: {source_type}"
        )

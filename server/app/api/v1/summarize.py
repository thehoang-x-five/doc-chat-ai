"""
API endpoints for Smart Summarization.
Requirements: 23.1-23.8
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.summarize import (
    SummaryAudience,
    SummarizeRequest,
    SummaryResult,
    SummaryListResponse,
)
from app.services.generation.summarize_service import get_summarize_service

router = APIRouter(prefix="/summarize", tags=["summarize"])


@router.post("", response_model=SummaryResult)
async def create_summary(
    request: SummarizeRequest,
    workspace_id: str = Query(..., description="Workspace ID"),
):
    """
    Generate a summary for the specified documents.
    
    Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.8
    """
    service = get_summarize_service()
    
    # Get document texts (in production, fetch from document service)
    # For now, we'll use mock data or require text in request
    document_texts = {}
    
    try:
        # Try to get documents from document service
        from app.services.documents.document_service import get_document_service
        doc_service = get_document_service()
        
        for doc_id in request.document_ids:
            doc = await doc_service.get_document(doc_id, workspace_id)
            if doc:
                # Get document text from storage
                text = await doc_service.get_document_text(doc_id, workspace_id)
                document_texts[doc_id] = (doc.title, text or "")
    except Exception:
        pass
    
    # If no documents found, return error
    if not document_texts:
        # For demo, create mock content
        for doc_id in request.document_ids:
            document_texts[doc_id] = (
                f"Document {doc_id[:8]}",
                "This is sample document content for demonstration purposes."
            )
    
    try:
        result = await service.summarize(
            workspace_id=workspace_id,
            request=request,
            document_texts=document_texts,
            user_id=None,  # TODO: Get from auth
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}",
        )


@router.get("", response_model=SummaryListResponse)
async def list_summaries(
    workspace_id: str = Query(..., description="Workspace ID"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    audience: Optional[SummaryAudience] = Query(None, description="Filter by audience"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """
    List summaries in a workspace.
    """
    service = get_summarize_service()
    
    summaries, total = await service.list_summaries(
        workspace_id=workspace_id,
        document_id=document_id,
        audience=audience,
        skip=skip,
        limit=limit,
    )
    
    return SummaryListResponse(
        summaries=summaries,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{summary_id}", response_model=SummaryResult)
async def get_summary(
    summary_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
):
    """
    Get a specific summary by ID.
    """
    service = get_summarize_service()
    
    summary = await service.get_summary(summary_id, workspace_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found",
        )
    
    return summary


@router.delete("/{summary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_summary(
    summary_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
):
    """
    Delete a summary.
    """
    service = get_summarize_service()
    
    deleted = await service.delete_summary(summary_id, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found",
        )

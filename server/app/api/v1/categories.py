"""
Document Categories API endpoints.

Manages document categories for organizing and classifying documents.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import DocumentCategory, Document, User
from app.api.deps import get_current_user
from app.services.documents.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CategoryCreate(BaseModel):
    """Create category request."""
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class CategoryUpdate(BaseModel):
    """Update category request."""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    display_order: Optional[int] = None


class CategoryResponse(BaseModel):
    """Category response."""
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: Optional[str]
    content_summary: Optional[str]
    keywords: List[str]
    icon: Optional[str]
    color: Optional[str]
    display_order: int
    is_auto_generated: bool
    document_count: int = 0

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """Category list response."""
    categories: List[CategoryResponse]
    total: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{workspace_id}", response_model=CategoryListResponse)
async def list_categories(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all categories in a workspace."""
    # Get categories
    query = select(DocumentCategory).where(
        DocumentCategory.workspace_id == workspace_id
    ).order_by(DocumentCategory.display_order, DocumentCategory.name)
    
    result = await db.execute(query)
    categories = result.scalars().all()
    
    # Get document counts
    response_categories = []
    for cat in categories:
        count_query = select(func.count(Document.id)).where(
            Document.category_id == cat.id,
            Document.status == "READY"
        )
        count_result = await db.execute(count_query)
        doc_count = count_result.scalar() or 0
        
        response_categories.append(CategoryResponse(
            id=cat.id,
            workspace_id=cat.workspace_id,
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            content_summary=cat.content_summary,
            keywords=cat.keywords or [],
            icon=cat.icon,
            color=cat.color,
            display_order=cat.display_order,
            is_auto_generated=cat.is_auto_generated,
            document_count=doc_count,
        ))
    
    return CategoryListResponse(
        categories=response_categories,
        total=len(response_categories),
    )


@router.post("/{workspace_id}", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    workspace_id: UUID,
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new category."""
    category_service = CategoryService(db)
    
    category = await category_service.get_or_create_category(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
    )
    
    # Update optional fields
    if data.icon:
        category.icon = data.icon
    if data.color:
        category.color = data.color
    category.is_auto_generated = False
    
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse(
        id=category.id,
        workspace_id=category.workspace_id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        content_summary=category.content_summary,
        keywords=category.keywords or [],
        icon=category.icon,
        color=category.color,
        display_order=category.display_order,
        is_auto_generated=category.is_auto_generated,
        document_count=0,
    )


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a category."""
    query = select(DocumentCategory).where(DocumentCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Update fields
    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.icon is not None:
        category.icon = data.icon
    if data.color is not None:
        category.color = data.color
    if data.display_order is not None:
        category.display_order = data.display_order
    
    await db.commit()
    await db.refresh(category)
    
    # Get document count
    count_query = select(func.count(Document.id)).where(
        Document.category_id == category.id,
        Document.status == "READY"
    )
    count_result = await db.execute(count_query)
    doc_count = count_result.scalar() or 0
    
    return CategoryResponse(
        id=category.id,
        workspace_id=category.workspace_id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        content_summary=category.content_summary,
        keywords=category.keywords or [],
        icon=category.icon,
        color=category.color,
        display_order=category.display_order,
        is_auto_generated=category.is_auto_generated,
        document_count=doc_count,
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a category. Documents will have their category set to null."""
    query = select(DocumentCategory).where(DocumentCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    await db.delete(category)
    await db.commit()


@router.post("/{category_id}/refresh-summary")
async def refresh_category_summary(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refresh the AI-generated summary for a category."""
    category_service = CategoryService(db)
    summary = await category_service.update_category_summary(category_id)
    
    if not summary:
        raise HTTPException(status_code=400, detail="Failed to generate summary")
    
    await db.commit()
    
    return {"success": True, "summary": summary}


@router.post("/documents/{document_id}/categorize")
async def categorize_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-categorize a document using AI."""
    # Get document
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if document is ready (has been indexed)
    if document.status not in ("READY", "indexed"):
        # Document is still being processed, return pending status instead of error
        return {
            "success": False,
            "pending": True,
            "message": f"Document is still being processed (status: {document.status}). Categorization will be available after indexing completes.",
            "category_id": None,
            "category_name": None,
        }
    
    category_service = CategoryService(db)
    category = await category_service.auto_categorize_document(document)
    
    if not category:
        # Could be no chunks yet or LLM failed - return graceful response
        return {
            "success": False,
            "pending": False,
            "message": "Could not categorize document. It may not have enough content or the AI service is unavailable.",
            "category_id": None,
            "category_name": None,
        }
    
    await db.commit()
    
    return {
        "success": True,
        "pending": False,
        "category_id": str(category.id),
        "category_name": category.name,
        "document_summary": document.content_summary,
        "main_headings": document.main_headings,
    }


class SetCategoryRequest(BaseModel):
    """Set document category request."""
    category_id: Optional[UUID] = None


@router.put("/documents/{document_id}/category")
async def set_document_category(
    document_id: UUID,
    data: SetCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually set document category. Auto-refreshes category summaries."""
    # Get document
    doc_query = select(Document).where(Document.id == document_id)
    doc_result = await db.execute(doc_query)
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    old_category_id = document.category_id
    new_category_id = data.category_id
    
    # Verify new category exists if provided
    if new_category_id:
        cat_query = select(DocumentCategory).where(DocumentCategory.id == new_category_id)
        cat_result = await db.execute(cat_query)
        category = cat_result.scalar_one_or_none()
        
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
    
    # Update document category
    document.category_id = new_category_id
    await db.commit()
    
    # Refresh category summaries in background (don't block response)
    category_service = CategoryService(db)
    
    # Refresh old category summary (if had one)
    if old_category_id:
        try:
            await category_service.update_category_summary(old_category_id)
            await db.commit()
        except Exception as e:
            import logging
            logging.warning(f"Failed to refresh old category summary: {e}")
    
    # Refresh new category summary (if moving to one)
    if new_category_id:
        try:
            await category_service.update_category_summary(new_category_id)
            await db.commit()
        except Exception as e:
            import logging
            logging.warning(f"Failed to refresh new category summary: {e}")
    
    return {"success": True, "category_id": str(new_category_id) if new_category_id else None}

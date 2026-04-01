"""
Image Generation API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.services.generation.image_generation_service import (
    get_image_generation_service,
    ImageGenerationResult,
)

router = APIRouter(prefix="/images", tags=["images"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ImageGenerateRequest(BaseModel):
    """Request to generate images."""
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text description of the image")
    num_images: int = Field(1, ge=1, le=4, description="Number of images to generate")
    aspect_ratio: str = Field("1:1", description="Aspect ratio (1:1, 3:4, 4:3, 9:16, 16:9)")
    negative_prompt: Optional[str] = Field(None, max_length=1000, description="What to avoid in the image")


class ImageGenerateResponse(BaseModel):
    """Response from image generation."""
    success: bool
    images: List[str]  # Base64 encoded images
    prompt: str
    model: str
    provider: str
    error: Optional[str] = None
    processing_time_ms: int = 0


class ImageModelInfo(BaseModel):
    """Information about an image generation model."""
    id: str
    name: str
    provider: str
    description: str
    free_tier: str
    aspect_ratios: List[str]
    max_images: int


class ImageModelsResponse(BaseModel):
    """Response with available image models."""
    models: List[ImageModelInfo]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(
    data: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate images from text prompt using AI.
    
    Uses Google Imagen 3 (free tier: 50 images/day).
    
    Supported aspect ratios:
    - 1:1 (square)
    - 3:4 (portrait)
    - 4:3 (landscape)
    - 9:16 (vertical/mobile)
    - 16:9 (horizontal/widescreen)
    """
    service = get_image_generation_service()
    
    try:
        result = await service.generate(
            prompt=data.prompt,
            num_images=data.num_images,
            aspect_ratio=data.aspect_ratio,
            negative_prompt=data.negative_prompt,
        )
        
        return ImageGenerateResponse(
            success=result.success,
            images=result.images,
            prompt=result.prompt,
            model=result.model,
            provider=result.provider,
            error=result.error,
            processing_time_ms=result.processing_time_ms,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image generation failed: {str(e)}",
        )


@router.get("/models", response_model=ImageModelsResponse)
async def get_image_models(
    current_user: User = Depends(get_current_user),
):
    """Get available image generation models."""
    service = get_image_generation_service()
    models = service.get_supported_models()
    
    return ImageModelsResponse(
        models=[ImageModelInfo(**m) for m in models]
    )

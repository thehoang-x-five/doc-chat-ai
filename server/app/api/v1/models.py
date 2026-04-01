"""
Unified Model Listing API.
Lists all available models from all providers (Cloud Code, DeepSeek, Gemini, Groq, Ollama).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/models", tags=["Models"])


class ModelInfo(BaseModel):
    """Model information."""
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Display name")
    provider: str = Field(..., description="Provider name")
    type: str = Field(..., description="Model type: text, image, thinking")
    priority: int = Field(..., description="Priority (lower = higher priority)")
    available: bool = Field(..., description="Whether model is available")
    quota: Optional[float] = Field(None, description="Quota percentage (Cloud Code only)")
    description: Optional[str] = Field(None, description="Model description")


class ModelsListResponse(BaseModel):
    """Models list response."""
    models: List[ModelInfo]
    total: int


# Model definitions
CLOUDCODE_MODELS = [
    {"id": "claude-sonnet-4-5", "name": "Claude 4.5 Sonnet", "type": "text", "priority": 0,
     "description": "Strongest Claude model, excellent for complex tasks"},
    {"id": "claude-sonnet-4-5-thinking", "name": "Claude 4.5 Sonnet (Thinking)", "type": "thinking", "priority": 1,
     "description": "Claude with extended thinking capability"},
    {"id": "claude-opus-4-5-thinking", "name": "Claude 4.5 Opus (Thinking)", "type": "thinking", "priority": 2,
     "description": "Most powerful Claude model with thinking"},
    {"id": "gemini-3-pro-high", "name": "Gemini 3 Pro High", "type": "text", "priority": 3,
     "description": "High-quality Gemini Pro model"},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "type": "text", "priority": 4,
     "description": "Gemini Pro with long context support"},
    {"id": "gemini-3-flash", "name": "Gemini 3 Flash", "type": "text", "priority": 5,
     "description": "Fast Gemini model for quick responses"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "type": "text", "priority": 6,
     "description": "Fast and efficient Gemini model"},
    {"id": "gemini-3-pro-low", "name": "Gemini 3 Pro Low", "type": "text", "priority": 7,
     "description": "Lower quality Gemini Pro model"},
    {"id": "gemini-2.5-flash-thinking", "name": "Gemini 2.5 Flash (Thinking)", "type": "thinking", "priority": 8,
     "description": "Gemini Flash with thinking capability"},
    {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "type": "text", "priority": 9,
     "description": "Lightweight Gemini model"},
    {"id": "gemini-3-pro-image", "name": "Gemini 3 Pro Image", "type": "image", "priority": 10,
     "description": "Gemini model for image understanding"},
]

OTHER_MODELS = [
    {"id": "deepseek-chat", "name": "DeepSeek V3", "provider": "deepseek", "type": "text", "priority": 20,
     "description": "Strongest free model, comparable to GPT-4"},
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "gemini", "type": "text", "priority": 21,
     "description": "Google Gemini Pro via API"},
    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "gemini", "type": "text", "priority": 22,
     "description": "Fast Google Gemini via API"},
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "provider": "groq", "type": "text", "priority": 23,
     "description": "Fast Llama model via Groq"},
    {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B", "provider": "ollama", "type": "text", "priority": 100,
     "description": "Local Qwen model via Ollama"},
]

# Image Generation Models (ranked by quality)
IMAGE_GEN_MODELS = [
    {"id": "flux-schnell", "name": "FLUX.1-schnell", "provider": "together", "type": "image", "priority": 50,
     "description": "🥇 Strongest FREE - High quality, fast (60 req/min)"},
    {"id": "flux", "name": "FLUX", "provider": "pollinations", "type": "image", "priority": 51,
     "description": "🥈 100% FREE - No API key needed, unlimited"},
    {"id": "sdxl", "name": "Stable Diffusion XL", "provider": "huggingface", "type": "image", "priority": 52,
     "description": "🥉 Good quality - Free tier with rate limits"},
    {"id": "imagen-3", "name": "Imagen 3", "provider": "cloudcode", "type": "image", "priority": 53,
     "description": "Google Imagen via Cloud Code accounts"},
    {"id": "stable-diffusion", "name": "Stable Diffusion v1.6", "provider": "stability", "type": "image", "priority": 54,
     "description": "Original SD - 25 free credits"},
    {"id": "gemini-2.0-flash-img", "name": "Gemini 2.0 Flash", "provider": "gemini", "type": "image", "priority": 55,
     "description": "Google multimodal - 50 images/day FREE"},
]


@router.get("", response_model=ModelsListResponse)
async def list_all_models():
    """
    List all available models from all providers.
    
    Returns models from:
    - Cloud Code (FREE Claude/Gemini via Google)
    - DeepSeek (if API key configured)
    - Gemini API (if API key configured)
    - Groq (if API key configured)
    - Ollama (local)
    """
    models = []
    
    # Get Cloud Code models with quota info
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        cloudcode_manager = get_cloudcode_manager()
        available_models = cloudcode_manager.get_available_models()
        
        # Create lookup for quota
        quota_lookup = {m["name"]: m["max_quota"] for m in available_models}
        accounts_lookup = {m["name"]: m["accounts_with_quota"] for m in available_models}
        
        for model_def in CLOUDCODE_MODELS:
            model_id = model_def["id"]
            quota = quota_lookup.get(model_id, 0)
            accounts = accounts_lookup.get(model_id, 0)
            
            models.append(ModelInfo(
                id=model_id,
                name=model_def["name"],
                provider="cloudcode",
                type=model_def["type"],
                priority=model_def["priority"],
                available=accounts > 0,
                quota=quota if accounts > 0 else None,
                description=model_def["description"],
            ))
    except Exception:
        # Cloud Code not available, add models as unavailable
        for model_def in CLOUDCODE_MODELS:
            models.append(ModelInfo(
                id=model_def["id"],
                name=model_def["name"],
                provider="cloudcode",
                type=model_def["type"],
                priority=model_def["priority"],
                available=False,
                quota=None,
                description=model_def["description"],
            ))
    
    # Add other providers
    for model_def in OTHER_MODELS:
        provider = model_def["provider"]
        available = False
        
        if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
            available = True
        elif provider == "gemini" and settings.GEMINI_API_KEY:
            available = True
        elif provider == "groq" and settings.GROQ_API_KEY:
            available = True
        elif provider == "ollama":
            available = True  # Ollama is always available (local)
        
        models.append(ModelInfo(
            id=model_def["id"],
            name=model_def["name"],
            provider=provider,
            type=model_def["type"],
            priority=model_def["priority"],
            available=available,
            quota=None,
            description=model_def["description"],
        ))
    
    # Add Image Generation models
    for model_def in IMAGE_GEN_MODELS:
        provider = model_def["provider"]
        available = False
        
        if provider == "together":
            available = bool(getattr(settings, 'TOGETHER_API_KEY', ''))
        elif provider == "pollinations":
            available = True  # Always available - no API key needed
        elif provider == "huggingface":
            available = bool(getattr(settings, 'HUGGINGFACE_API_KEY', ''))
        elif provider == "cloudcode":
            # Check if Cloud Code has imagen-3 quota
            try:
                from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
                manager = get_cloudcode_manager()
                if manager and manager.list_accounts():
                    available = True
            except Exception:
                pass
        elif provider == "stability":
            available = bool(getattr(settings, 'STABILITY_API_KEY', ''))
        elif provider == "gemini":
            available = bool(settings.GEMINI_API_KEY)
        
        models.append(ModelInfo(
            id=model_def["id"],
            name=model_def["name"],
            provider=provider,
            type=model_def["type"],
            priority=model_def["priority"],
            available=available,
            quota=None,
            description=model_def["description"],
        ))
    
    # Sort by priority
    models.sort(key=lambda m: m.priority)
    
    return ModelsListResponse(models=models, total=len(models))


@router.get("/available")
async def list_available_models():
    """List only available models (with quota or API key configured)."""
    response = await list_all_models()
    available = [m for m in response.models if m.available]
    return {"models": available, "total": len(available)}


@router.get("/by-provider/{provider}")
async def list_models_by_provider(provider: str):
    """List models for a specific provider."""
    response = await list_all_models()
    filtered = [m for m in response.models if m.provider == provider]
    return {"models": filtered, "total": len(filtered)}


@router.get("/by-type/{model_type}")
async def list_models_by_type(model_type: str):
    """
    List models by type.
    
    Types: text, image, thinking
    """
    response = await list_all_models()
    filtered = [m for m in response.models if m.type == model_type]
    return {"models": filtered, "total": len(filtered)}

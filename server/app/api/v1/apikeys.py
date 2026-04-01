"""
API Keys management endpoints for free AI providers.
Allows users to configure their own API keys for Groq, DeepSeek, Gemini API, Ollama.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import httpx

from app.api.deps import get_current_user, get_current_user_optional
from app.db.models import User
from app.core.config import settings

router = APIRouter(prefix="/apikeys", tags=["API Keys"])

# In-memory storage for demo (should use database in production)
# Structure: { user_id: { provider: { api_key, last_updated, is_valid } } }
_user_api_keys: dict = {}

# System default keys (from environment)
_system_keys = {
    "groq": settings.GROQ_API_KEY if hasattr(settings, 'GROQ_API_KEY') else None,
    "deepseek": settings.DEEPSEEK_API_KEY if hasattr(settings, 'DEEPSEEK_API_KEY') else None,
    "gemini": settings.GEMINI_API_KEY if hasattr(settings, 'GEMINI_API_KEY') else None,
    "ollama": settings.OLLAMA_BASE_URL if hasattr(settings, 'OLLAMA_BASE_URL') else "http://localhost:11434",
}


class ApiKeyInfo(BaseModel):
    provider: str
    hasKey: bool
    lastUpdated: Optional[str] = None
    isValid: Optional[bool] = None


class SaveApiKeyRequest(BaseModel):
    provider: str
    api_key: str


class TestApiKeyResponse(BaseModel):
    valid: bool
    error: Optional[str] = None


@router.get("", response_model=List[ApiKeyInfo])
async def get_api_keys(user: User = Depends(get_current_user)):
    """Get list of configured API keys for current user."""
    user_keys = _user_api_keys.get(str(user.id), {})
    
    providers = ["groq", "deepseek", "gemini", "ollama"]
    result = []
    
    for provider in providers:
        key_info = user_keys.get(provider, {})
        has_key = bool(key_info.get("api_key")) or bool(_system_keys.get(provider))
        
        result.append(ApiKeyInfo(
            provider=provider,
            hasKey=has_key,
            lastUpdated=key_info.get("last_updated"),
            isValid=key_info.get("is_valid"),
        ))
    
    return result


@router.post("")
async def save_api_key(
    request: SaveApiKeyRequest,
    user: User = Depends(get_current_user)
):
    """Save an API key for a provider."""
    if request.provider not in ["groq", "deepseek", "gemini", "ollama"]:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    user_id = str(user.id)
    if user_id not in _user_api_keys:
        _user_api_keys[user_id] = {}
    
    _user_api_keys[user_id][request.provider] = {
        "api_key": request.api_key,
        "last_updated": datetime.utcnow().isoformat(),
        "is_valid": None,  # Will be set after testing
    }
    
    return {"success": True}


@router.delete("/{provider}")
async def delete_api_key(
    provider: str,
    user: User = Depends(get_current_user)
):
    """Delete an API key for a provider."""
    user_id = str(user.id)
    if user_id in _user_api_keys and provider in _user_api_keys[user_id]:
        del _user_api_keys[user_id][provider]
    
    return {"success": True}


@router.post("/{provider}/test", response_model=TestApiKeyResponse)
async def test_api_key(
    provider: str,
    user: User = Depends(get_current_user)
):
    """Test if an API key is valid."""
    user_id = str(user.id)
    user_keys = _user_api_keys.get(user_id, {})
    key_info = user_keys.get(provider, {})
    api_key = key_info.get("api_key") or _system_keys.get(provider)
    
    if not api_key:
        return TestApiKeyResponse(valid=False, error="No API key configured")
    
    try:
        is_valid = await _test_provider_key(provider, api_key)
        
        # Update validity status
        if user_id in _user_api_keys and provider in _user_api_keys[user_id]:
            _user_api_keys[user_id][provider]["is_valid"] = is_valid
        
        if is_valid:
            return TestApiKeyResponse(valid=True)
        else:
            return TestApiKeyResponse(valid=False, error="API key validation failed")
            
    except Exception as e:
        return TestApiKeyResponse(valid=False, error=str(e))


async def _test_provider_key(provider: str, api_key: str) -> bool:
    """Test if a provider API key is valid."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if provider == "groq":
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                return response.status_code == 200
                
            elif provider == "deepseek":
                response = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                return response.status_code == 200
                
            elif provider == "gemini":
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
                return response.status_code == 200
                
            elif provider == "ollama":
                # For Ollama, api_key is actually the base URL
                base_url = api_key.rstrip("/")
                response = await client.get(f"{base_url}/api/tags")
                return response.status_code == 200
                
            return False
            
        except Exception:
            return False


def get_user_api_key(user_id: str, provider: str) -> Optional[str]:
    """Get API key for a user and provider (utility function for other services)."""
    user_keys = _user_api_keys.get(user_id, {})
    key_info = user_keys.get(provider, {})
    return key_info.get("api_key") or _system_keys.get(provider)

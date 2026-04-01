"""
Provider Management API - Enhanced with API Key Manager.

Endpoints for:
- Viewing provider accounts and their status
- Viewing quota and health statistics
- Cloud Code account management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.models import User
from app.services.auth.api_key_service import get_key_manager, AccountStatus

router = APIRouter(prefix="/providers", tags=["providers"])


# =============================================================================
# SCHEMAS
# =============================================================================

class AccountDetailResponse(BaseModel):
    """Detailed account information."""
    id: str
    name: str
    provider: str
    status: str
    quota_percentage: float
    quotas: dict
    total_requests: int
    total_failures: int
    avg_latency_ms: float
    last_used: Optional[str]
    last_error: Optional[str]
    is_available: bool


class ProviderStatsResponse(BaseModel):
    """Provider statistics (dashboard data)."""
    groq: Optional[dict] = None
    deepseek: Optional[dict] = None
    gemini: Optional[dict] = None


class CloudCodeAccountResponse(BaseModel):
    """Cloud Code account information."""
    id: str
    email: str
    name: Optional[str]
    is_available: bool
    total_requests: int
    total_failures: int
    last_used: Optional[str]
    best_model: Optional[str]
    quotas: dict


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/stats", response_model=ProviderStatsResponse)
async def get_provider_statistics(
    current_user: User = Depends(get_current_user),
):
    """
    Get provider statistics dashboard.
    
    Returns stats for all API key providers:
    - Total keys
    - Available/valid counts
    - Quota percentages
    - Request/failure counts
    """
    manager = get_key_manager()
    return manager.get_stats()


@router.get("/accounts", response_model=List[AccountDetailResponse])
async def list_provider_accounts(
    provider: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    List all provider accounts with detailed status.
    
    Optionally filter by provider type (groq, deepseek, gemini).
    """
    manager = get_key_manager()
    accounts = manager.get_account_details()
    
    if provider:
        accounts = [a for a in accounts if a["provider"] == provider.lower()]
    
    return accounts


@router.post("/accounts/{provider}/{index}/enable")
async def enable_account(
    provider: str,
    index: int,
    current_user: User = Depends(get_current_user),
):
    """Re-enable a disabled account."""
    manager = get_key_manager()
    
    if provider not in manager._keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider} not found",
        )
    
    keys = manager._keys[provider]
    if index < 0 or index >= len(keys):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account index {index} not found",
        )
    
    key_status = keys[index]
    key_status.status = AccountStatus.HEALTHY
    key_status.cooldown_until = None
    key_status.consecutive_failures = 0
    key_status.is_valid = True
    
    return {"message": f"Account {provider}_{index} enabled"}


@router.post("/accounts/{provider}/{index}/disable")
async def disable_account(
    provider: str,
    index: int,
    current_user: User = Depends(get_current_user),
):
    """Manually disable an account."""
    manager = get_key_manager()
    
    if provider not in manager._keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider} not found",
        )
    
    keys = manager._keys[provider]
    if index < 0 or index >= len(keys):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account index {index} not found",
        )
    
    key_status = keys[index]
    key_status.status = AccountStatus.DISABLED
    
    return {"message": f"Account {provider}_{index} disabled"}


# =============================================================================
# CLOUD CODE ENDPOINTS
# =============================================================================

@router.get("/cloudcode/accounts", response_model=List[CloudCodeAccountResponse])
async def list_cloudcode_accounts(
    current_user: User = Depends(get_current_user),
):
    """List all Cloud Code accounts."""
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        accounts = manager.list_accounts()
        
        return [
            CloudCodeAccountResponse(
                id=acc.id,
                email=acc.email,
                name=acc.name,
                is_available=acc.is_available,
                total_requests=acc.total_requests,
                total_failures=acc.total_failures,
                last_used=acc.last_used.isoformat() if acc.last_used else None,
                best_model=acc.get_best_available_model(),
                quotas={
                    name: {
                        "percentage": round(q.percentage, 1),
                        "is_available": q.is_available,
                    }
                    for name, q in acc.quotas.items()
                },
            )
            for acc in accounts
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Cloud Code accounts: {str(e)}",
        )


@router.get("/cloudcode/stats")
async def get_cloudcode_statistics(
    current_user: User = Depends(get_current_user),
):
    """Get Cloud Code provider statistics."""
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        return manager.get_statistics()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Cloud Code stats: {str(e)}",
        )


@router.get("/cloudcode/models")
async def get_cloudcode_available_models(
    current_user: User = Depends(get_current_user),
):
    """Get available Cloud Code models across all accounts."""
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        return manager.get_available_models()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Cloud Code models: {str(e)}",
        )

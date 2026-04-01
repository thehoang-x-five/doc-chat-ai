"""
Cloud Code API endpoints.

Provides endpoints for managing Google Cloud Code accounts
which enable FREE access to Claude and Gemini models.
"""
from typing import List, Optional
import secrets
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.infrastructure.ai_providers.cloudcode_provider_service import (
    get_cloudcode_manager,
    GoogleOAuth,
    CloudCodeAccount,
)
from app.api.deps import get_current_user, get_current_user_optional
from app.db.models import User

router = APIRouter(prefix="/cloudcode", tags=["Cloud Code"])

# OAuth session storage (in-memory)
_oauth_sessions: dict = {}


# =============================================================================
# SCHEMAS
# =============================================================================

class OAuthUrlResponse(BaseModel):
    """OAuth URL response."""
    auth_url: str
    state: str


class OAuthStartResponse(BaseModel):
    """OAuth start response for frontend."""
    authUrl: str
    sessionId: str
    redirectUri: str


class OAuthStatusResponse(BaseModel):
    """OAuth status response."""
    completed: bool
    success: Optional[bool] = None
    error: Optional[str] = None
    account: Optional[dict] = None


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    code: str
    redirect_uri: str
    state: Optional[str] = None


class AddRefreshTokenRequest(BaseModel):
    """Add account using refresh token."""
    email: str = ""  # Optional - will be auto-fetched from Google if empty
    refresh_token: str


class AccountResponse(BaseModel):
    """Account response."""
    id: str
    email: str
    name: Optional[str] = None
    is_available: bool
    total_requests: int
    total_failures: int
    last_used: Optional[str] = None
    isOwn: Optional[bool] = None
    isDefault: Optional[bool] = None
    quotas: Optional[dict] = None
    models: Optional[List[dict]] = None  # Full list of models with quota


class AccountListResponse(BaseModel):
    """Account list response."""
    accounts: List[AccountResponse]
    total: int


class StatisticsResponse(BaseModel):
    """Statistics response."""
    total_accounts: int
    available_accounts: int
    total_requests: int
    total_failures: int


class GenerateRequest(BaseModel):
    """Generate content request."""
    prompt: str
    model: str = Field(default="claude-sonnet-4-5", description="Model to use")
    system_prompt: Optional[str] = None
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0, le=2)


class GenerateResponse(BaseModel):
    """Generate content response."""
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    account_email: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# =============================================================================
# OAUTH ENDPOINTS - Using local callback server (like Antigravity)
# =============================================================================

@router.post("/oauth/start", response_model=OAuthStartResponse)
async def start_oauth(user: User = Depends(get_current_user)):
    """
    Start OAuth flow for adding a Cloud Code account.
    Creates a local callback server and returns auth URL.
    """
    from app.services.auth.oauth_callback_server import start_oauth_flow
    
    session_id = secrets.token_urlsafe(32)
    
    try:
        # Pass session_id to start_oauth_flow so we can track it
        auth_url, redirect_uri = await start_oauth_flow(session_id)
        
        # Store session info
        _oauth_sessions[session_id] = {
            "redirect_uri": redirect_uri,
            "user_id": str(user.id),
            "completed": False,
            "success": None,
            "error": None,
            "account": None,
        }
        
        # Start background task to wait for OAuth completion
        asyncio.create_task(_process_oauth_callback(session_id))
        
        return OAuthStartResponse(
            authUrl=auth_url,
            sessionId=session_id,
            redirectUri=redirect_uri
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth: {e}")


async def _process_oauth_callback(session_id: str):
    """Background task to process OAuth callback."""
    import logging
    logger = logging.getLogger(__name__)
    
    from app.services.auth.oauth_callback_server import wait_for_oauth_code
    
    session = _oauth_sessions.get(session_id)
    if not session:
        logger.error(f"OAuth session {session_id} not found")
        return
    
    try:
        logger.info(f"[{session_id[:8]}] Waiting for OAuth code...")
        # Wait for authorization code (max 5 minutes)
        code = await wait_for_oauth_code(session_id, timeout=300.0)
        logger.info(f"[{session_id[:8]}] Received OAuth code: {code[:20]}...")
        
        # Exchange code for tokens and add account
        manager = get_cloudcode_manager()
        logger.info(f"[{session_id[:8]}] Exchanging code for tokens...")
        account = await manager.add_account_from_oauth(
            code=code,
            redirect_uri=session["redirect_uri"],
        )
        logger.info(f"[{session_id[:8]}] Account added: {account.email}")
        
        # Set owner
        account.owner_id = session["user_id"]
        
        # Mark session as completed
        session["completed"] = True
        session["success"] = True
        session["account"] = {
            "id": account.id,
            "email": account.email,
            "name": getattr(account, 'name', None),
        }
        logger.info(f"[{session_id[:8]}] OAuth session completed successfully")
        
    except asyncio.TimeoutError:
        logger.error(f"[{session_id[:8]}] OAuth timeout")
        session["completed"] = True
        session["success"] = False
        session["error"] = "OAuth timeout - please try again"
        
    except Exception as e:
        logger.error(f"[{session_id[:8]}] OAuth error: {e}")
        import traceback
        traceback.print_exc()
        session["completed"] = True
        session["success"] = False
        session["error"] = str(e)
    
    # Clean up session after 5 minutes
    await asyncio.sleep(300)
    _oauth_sessions.pop(session_id, None)


@router.get("/oauth/status/{session_id}", response_model=OAuthStatusResponse)
async def check_oauth_status(session_id: str):
    """Check OAuth session status."""
    session = _oauth_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return OAuthStatusResponse(
        completed=session["completed"],
        success=session.get("success"),
        error=session.get("error"),
        account=session.get("account"),
    )


@router.post("/oauth/cancel")
async def cancel_oauth(session_id: str = None):
    """Cancel the current OAuth flow."""
    from app.services.auth.oauth_callback_server import cancel_oauth_flow
    
    await cancel_oauth_flow(session_id)
    return {"message": "OAuth flow cancelled"}


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/oauth/url", response_model=OAuthUrlResponse)
async def get_oauth_url(
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
):
    """
    Get Google OAuth authorization URL.
    
    Use this URL to redirect users to Google for authentication.
    After authentication, Google will redirect back to your redirect_uri
    with an authorization code.
    """
    import secrets
    state = secrets.token_urlsafe(16)
    auth_url = GoogleOAuth.get_auth_url(redirect_uri, state)
    
    return OAuthUrlResponse(auth_url=auth_url, state=state)


@router.post("/oauth/callback", response_model=AccountResponse)
async def oauth_callback(request: OAuthCallbackRequest):
    """
    Handle OAuth callback and add account.
    
    Exchange the authorization code for tokens and add the account
    to the Cloud Code provider manager.
    """
    try:
        manager = get_cloudcode_manager()
        account = await manager.add_account_from_oauth(
            code=request.code,
            redirect_uri=request.redirect_uri,
        )
        
        return AccountResponse(
            id=account.id,
            email=account.email,
            is_available=account.is_available,
            total_requests=account.total_requests,
            total_failures=account.total_failures,
            last_used=account.last_used.isoformat() if account.last_used else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {e}")


@router.post("/accounts/refresh-token", response_model=AccountResponse)
async def add_account_from_refresh_token(request: AddRefreshTokenRequest):
    """
    Add account using refresh token directly.
    
    This is useful if you already have a refresh token from another source
    (e.g., exported from Antigravity app).
    """
    try:
        manager = get_cloudcode_manager()
        account = await manager.add_account_from_refresh_token(
            email=request.email,
            refresh_token=request.refresh_token,
        )
        
        return AccountResponse(
            id=account.id,
            email=account.email,
            is_available=account.is_available,
            total_requests=account.total_requests,
            total_failures=account.total_failures,
            last_used=account.last_used.isoformat() if account.last_used else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add account: {e}")


@router.get("/accounts")
async def list_accounts(user: User = Depends(get_current_user)):
    """List Cloud Code accounts. Admin sees all, users see only their own."""
    manager = get_cloudcode_manager()
    accounts = manager.list_accounts()
    
    is_admin = user.role_global == "ADMIN"
    user_id = str(user.id)
    
    result = []
    for a in accounts:
        # Check if account belongs to current user
        is_own = getattr(a, 'owner_id', None) == user_id
        
        # Non-admin users only see their own accounts
        if not is_admin and not is_own:
            continue
        
        # Get quotas (summary for card display)
        quotas = {
            "claude": 0,
            "gemini": 0,
            "geminiImage": 0,
        }
        
        # Get full models list (for details dialog)
        models_list = []
        
        if hasattr(a, 'quotas') and a.quotas:
            for model_name, model_quota in a.quotas.items():
                name = model_name.lower()
                pct = model_quota.percentage if hasattr(model_quota, 'percentage') else 0
                reset_time = model_quota.reset_time if hasattr(model_quota, 'reset_time') else None
                
                # Add to full models list
                models_list.append({
                    "name": model_name,
                    "percentage": pct,
                    "resetTime": reset_time.isoformat() if reset_time else None,
                })
                
                # Update summary quotas
                if 'claude' in name:
                    quotas['claude'] = max(quotas['claude'], pct)
                elif 'image' in name:
                    quotas['geminiImage'] = max(quotas['geminiImage'], pct)
                elif 'gemini' in name:
                    quotas['gemini'] = max(quotas['gemini'], pct)
        
        # Sort models by name
        models_list.sort(key=lambda x: x['name'])
        
        result.append(AccountResponse(
            id=a.id,
            email=a.email,
            name=getattr(a, 'name', None),
            is_available=a.is_available,
            total_requests=a.total_requests,
            total_failures=a.total_failures,
            last_used=a.last_used.isoformat() if a.last_used else None,
            isOwn=is_own,
            isDefault=getattr(a, 'is_default', False),
            quotas=quotas,
            models=models_list,
        ))
    
    return result


@router.post("/accounts", response_model=AccountResponse)
async def add_account(
    request: AddRefreshTokenRequest,
    user: User = Depends(get_current_user)
):
    """Add account using refresh token."""
    try:
        manager = get_cloudcode_manager()
        account = await manager.add_account_from_refresh_token(
            email=request.email,
            refresh_token=request.refresh_token,
        )
        
        # Set owner
        account.owner_id = str(user.id)
        
        # Get quotas from account
        quotas = {"claude": 0, "gemini": 0, "geminiImage": 0}
        if account.quotas:
            for model_name, model_quota in account.quotas.items():
                name_lower = model_name.lower()
                pct = model_quota.percentage
                if 'claude' in name_lower:
                    quotas['claude'] = max(quotas['claude'], pct)
                elif 'image' in name_lower:
                    quotas['geminiImage'] = max(quotas['geminiImage'], pct)
                elif 'gemini' in name_lower:
                    quotas['gemini'] = max(quotas['gemini'], pct)
        
        return AccountResponse(
            id=account.id,
            email=account.email,
            name=getattr(account, 'name', None),
            is_available=account.is_available,
            total_requests=account.total_requests,
            total_failures=account.total_failures,
            last_used=account.last_used.isoformat() if account.last_used else None,
            isOwn=True,
            isDefault=False,
            quotas=quotas,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add account: {e}")


@router.delete("/accounts/{account_id}")
async def remove_account(account_id: str, user: User = Depends(get_current_user)):
    """Remove a Cloud Code account."""
    manager = get_cloudcode_manager()
    
    # Check ownership (admin can delete any)
    if user.role_global != "ADMIN":
        accounts = manager.list_accounts()
        account = next((a for a in accounts if a.id == account_id), None)
        if account and getattr(account, 'owner_id', None) != str(user.id):
            raise HTTPException(status_code=403, detail="Cannot delete other user's account")
    
    if not manager.remove_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"message": "Account removed successfully"}


@router.post("/accounts/{account_id}/default")
async def set_default_account(account_id: str, user: User = Depends(get_current_user)):
    """Set an account as default for the current user."""
    manager = get_cloudcode_manager()
    accounts = manager.list_accounts()
    
    account = next((a for a in accounts if a.id == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Check ownership
    if user.role_global != "ADMIN" and getattr(account, 'owner_id', None) != str(user.id):
        raise HTTPException(status_code=403, detail="Cannot set other user's account as default")
    
    # Clear other defaults and set this one
    for a in accounts:
        if getattr(a, 'owner_id', None) == str(user.id):
            a.is_default = (a.id == account_id)
    
    return {"message": "Default account updated"}


@router.post("/accounts/{account_id}/refresh")
async def refresh_account(account_id: str, user: User = Depends(get_current_user)):
    """Refresh quota for an account."""
    manager = get_cloudcode_manager()
    
    try:
        await manager.refresh_account_quota(account_id)
        return {"message": "Account quota refreshed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh: {e}")


@router.get("/accounts/{account_id}/details")
async def get_account_details(account_id: str, user: User = Depends(get_current_user)):
    """Get detailed statistics for a specific account."""
    manager = get_cloudcode_manager()
    accounts = manager.list_accounts()
    
    account = next((a for a in accounts if a.id == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Check ownership (admin can view any)
    is_admin = user.role_global == "ADMIN"
    is_own = getattr(account, 'owner_id', None) == str(user.id)
    if not is_admin and not is_own:
        raise HTTPException(status_code=403, detail="Cannot view other user's account details")
    
    # Calculate success rate
    total = account.total_requests or 0
    failures = account.total_failures or 0
    success_rate = ((total - failures) / total * 100) if total > 0 else 100.0
    
    # Get quotas (summary)
    quotas = {"claude": 0, "gemini": 0, "geminiImage": 0}
    
    # Get full models list
    models_list = []
    
    if hasattr(account, 'quotas') and account.quotas:
        for model_name, model_quota in account.quotas.items():
            name_lower = model_name.lower()
            pct = model_quota.percentage if hasattr(model_quota, 'percentage') else 0
            reset_time = model_quota.reset_time if hasattr(model_quota, 'reset_time') else None
            
            # Add to full models list
            models_list.append({
                "name": model_name,
                "percentage": pct,
                "resetTime": reset_time.isoformat() if reset_time else None,
            })
            
            # Update summary quotas
            if 'claude' in name_lower:
                quotas['claude'] = max(quotas['claude'], pct)
            elif 'image' in name_lower:
                quotas['geminiImage'] = max(quotas['geminiImage'], pct)
            elif 'gemini' in name_lower:
                quotas['gemini'] = max(quotas['gemini'], pct)
    
    # Sort models by name
    models_list.sort(key=lambda x: x['name'])
    
    # Get additional stats if available
    avg_latency = getattr(account, 'avg_latency_ms', None)
    last_error = getattr(account, 'last_error', None)
    created_at = getattr(account, 'created_at', None)
    daily_requests = getattr(account, 'daily_requests', 0)
    weekly_requests = getattr(account, 'weekly_requests', 0)
    
    return {
        "id": account.id,
        "email": account.email,
        "name": getattr(account, 'name', None),
        "quotas": quotas,
        "models": models_list,
        "totalRequests": total,
        "totalFailures": failures,
        "successRate": round(success_rate, 1),
        "avgLatencyMs": avg_latency,
        "lastError": last_error,
        "lastUsed": account.last_used.isoformat() if account.last_used else None,
        "createdAt": created_at.isoformat() if created_at else None,
        "dailyRequests": daily_requests,
        "weeklyRequests": weekly_requests,
        "isDefault": getattr(account, 'is_default', False),
        "isOwn": is_own,
    }


@router.post("/accounts/refresh-all")
async def refresh_all_accounts(user: User = Depends(get_current_user)):
    """Refresh quota for all accounts."""
    manager = get_cloudcode_manager()
    
    try:
        results = await manager.refresh_all_quotas()
        success_count = sum(1 for v in results.values() if v)
        failed_count = len(results) - success_count
        
        return {
            "message": f"Refreshed {success_count} account(s)",
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh all: {e}")


@router.get("/statistics")
async def get_statistics():
    """Get Cloud Code provider statistics with detailed account and model info."""
    manager = get_cloudcode_manager()
    stats = manager.get_statistics()
    available_models = manager.get_available_models()
    accounts = manager.list_accounts()
    
    # Calculate average quotas
    claude_quotas = []
    gemini_quotas = []
    gemini_image_quotas = []
    low_quota_count = 0
    
    for account in accounts:
        if hasattr(account, 'quotas') and account.quotas:
            claude_pct = 0
            gemini_pct = 0
            gemini_image_pct = 0
            
            for model_name, model_quota in account.quotas.items():
                name_lower = model_name.lower()
                pct = model_quota.percentage if hasattr(model_quota, 'percentage') else 0
                
                if 'claude' in name_lower:
                    claude_pct = max(claude_pct, pct)
                elif 'image' in name_lower:
                    gemini_image_pct = max(gemini_image_pct, pct)
                elif 'gemini' in name_lower:
                    gemini_pct = max(gemini_pct, pct)
            
            if claude_pct > 0:
                claude_quotas.append(claude_pct)
            if gemini_pct > 0:
                gemini_quotas.append(gemini_pct)
            if gemini_image_pct > 0:
                gemini_image_quotas.append(gemini_image_pct)
            
            # Count low quota accounts (< 20% on any main model)
            if claude_pct < 20 or gemini_pct < 20:
                low_quota_count += 1
    
    avg_claude = sum(claude_quotas) / len(claude_quotas) if claude_quotas else 0
    avg_gemini = sum(gemini_quotas) / len(gemini_quotas) if gemini_quotas else 0
    avg_gemini_image = sum(gemini_image_quotas) / len(gemini_image_quotas) if gemini_image_quotas else 0
    
    return {
        "total_accounts": stats["total_accounts"],
        "available_accounts": stats["available_accounts"],
        "total_requests": stats["total_requests"],
        "total_failures": stats["total_failures"],
        "avg_claude_quota": round(avg_claude, 1),
        "avg_gemini_quota": round(avg_gemini, 1),
        "avg_gemini_image_quota": round(avg_gemini_image, 1),
        "low_quota_accounts": low_quota_count,
        "accounts": stats.get("accounts", []),
        "available_models": available_models,
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest):
    """
    Generate content using Cloud Code API.
    
    This endpoint allows direct access to Claude/Gemini models
    via Google Cloud Code API for FREE.
    
    Available models:
    - claude-sonnet-4-5 (Claude 4.5 Sonnet - STRONGEST)
    - claude-sonnet-4-5-thinking (Claude 4.5 Sonnet with thinking)
    - claude-opus-4-5-thinking (Claude 4.5 Opus with thinking)
    - gemini-3-flash (Gemini 3 Flash - Fast)
    - gemini-3-pro-high (Gemini 3 Pro High)
    - gemini-2.5-pro (Gemini 2.5 Pro)
    - gemini-2.5-flash (Gemini 2.5 Flash)
    """
    manager = get_cloudcode_manager()
    
    if not manager.list_accounts():
        raise HTTPException(
            status_code=400,
            detail="No Cloud Code accounts configured. Please add an account first."
        )
    
    response = await manager.generate(
        messages=[{"role": "user", "content": request.prompt}],
        model=request.model,
        system_prompt=request.system_prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    
    return GenerateResponse(
        success=response.success,
        content=response.content,
        model=response.model,
        account_email=response.account_email,
        latency_ms=response.latency_ms,
        error=response.error,
    )


@router.get("/models")
async def list_available_models():
    """List available models via Cloud Code API."""
    manager = get_cloudcode_manager()
    available_models = manager.get_available_models()
    
    # Static model info
    model_info = {
        "claude-sonnet-4-5": {
            "name": "Claude 4.5 Sonnet",
            "description": "Strongest Claude model, excellent for complex tasks",
            "type": "claude",
        },
        "claude-sonnet-4-5-thinking": {
            "name": "Claude 4.5 Sonnet (Thinking)",
            "description": "Claude with extended thinking capability",
            "type": "claude",
        },
        "claude-opus-4-5-thinking": {
            "name": "Claude 4.5 Opus (Thinking)",
            "description": "Most powerful Claude model with thinking",
            "type": "claude",
        },
        "gemini-3-flash": {
            "name": "Gemini 3 Flash",
            "description": "Fast Gemini model for quick responses",
            "type": "gemini",
        },
        "gemini-3-pro-high": {
            "name": "Gemini 3 Pro High",
            "description": "High-quality Gemini Pro model",
            "type": "gemini",
        },
        "gemini-3-pro-low": {
            "name": "Gemini 3 Pro Low",
            "description": "Lower quality Gemini Pro model",
            "type": "gemini",
        },
        "gemini-2.5-pro": {
            "name": "Gemini 2.5 Pro",
            "description": "Gemini Pro with long context support",
            "type": "gemini",
        },
        "gemini-2.5-flash": {
            "name": "Gemini 2.5 Flash",
            "description": "Fast and efficient Gemini model",
            "type": "gemini",
        },
        "gemini-2.5-flash-lite": {
            "name": "Gemini 2.5 Flash Lite",
            "description": "Lightweight Gemini model",
            "type": "gemini",
        },
        "gemini-2.5-flash-thinking": {
            "name": "Gemini 2.5 Flash (Thinking)",
            "description": "Gemini Flash with thinking capability",
            "type": "gemini",
        },
    }
    
    # Merge with availability info
    models = []
    for model in available_models:
        model_id = model["name"]
        info = model_info.get(model_id, {
            "name": model_id,
            "description": f"Model {model_id}",
            "type": "unknown",
        })
        models.append({
            "id": model_id,
            "name": info["name"],
            "description": info["description"],
            "type": info["type"],
            "priority": model["priority"],
            "accounts_with_quota": model["accounts_with_quota"],
            "max_quota": model["max_quota"],
            "available": model["accounts_with_quota"] > 0,
        })
    
    return {"models": models}


@router.post("/reload")
async def reload_accounts():
    """
    Reload accounts from disk.
    
    This will reload accounts from:
    - Local storage directory
    - .kiro directory (Antigravity format)
    """
    from pathlib import Path
    from app.services.infrastructure.ai_providers.cloudcode_provider_service import init_cloudcode_manager
    
    manager = await init_cloudcode_manager()
    accounts = manager.list_accounts()
    
    return {
        "message": f"Reloaded {len(accounts)} accounts",
        "accounts": [
            {
                "email": a.email,
                "name": a.name,
                "best_model": a.get_best_available_model(),
            }
            for a in accounts
        ],
    }

"""
OAuth endpoints for adding Google accounts to Cloud Code.
Allows users to add accounts via web UI without Antigravity.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel

from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager, GoogleOAuth

router = APIRouter(prefix="/oauth", tags=["OAuth"])


class OAuthCallbackResponse(BaseModel):
    """Response after OAuth callback."""
    success: bool
    message: str
    account_email: str = None
    account_id: str = None


@router.get("/google/login")
async def google_login():
    """
    Initiate Google OAuth flow.
    
    Redirects user to Google login page.
    After login, Google will redirect back to /oauth/google/callback
    """
    # Generate OAuth URL
    redirect_uri = "http://localhost:8000/api/v1/oauth/google/callback"
    state = "cloudcode_oauth"  # Can be random for security
    
    auth_url = GoogleOAuth.get_auth_url(redirect_uri, state)
    
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(None, description="State parameter"),
):
    """
    Handle OAuth callback from Google.
    
    This endpoint receives the authorization code from Google
    and exchanges it for tokens, then adds the account to Cloud Code.
    """
    try:
        # Exchange code for tokens
        redirect_uri = "http://localhost:8000/api/v1/oauth/google/callback"
        
        manager = get_cloudcode_manager()
        account = await manager.add_account_from_oauth(code, redirect_uri)
        
        # Return success page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Account Added</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    text-align: center;
                }}
                .success {{
                    color: #28a745;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                .info {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="success">✅ Account Added Successfully!</div>
            <div class="info">
                <p><strong>Email:</strong> {account.email}</p>
                <p><strong>Account ID:</strong> {account.id}</p>
                <p><strong>Models:</strong> {len(account.quotas)} available</p>
            </div>
            <p>You can now close this window.</p>
            <a href="/api/v1/oauth/accounts" class="button">View All Accounts</a>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        # Return error page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    text-align: center;
                }}
                .error {{
                    color: #dc3545;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                .info {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="error">❌ Failed to Add Account</div>
            <div class="info">
                <p><strong>Error:</strong> {str(e)}</p>
            </div>
            <p>Please try again or contact support.</p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content, status_code=400)


@router.get("/accounts", response_class=HTMLResponse)
async def list_accounts():
    """
    List all Cloud Code accounts.
    
    Returns an HTML page showing all accounts and their status.
    """
    try:
        manager = get_cloudcode_manager()
        await manager.load_accounts()
        accounts = manager.list_accounts()
        
        # Build accounts HTML
        accounts_html = ""
        for i, acc in enumerate(accounts, 1):
            status = "✅ Available" if acc.is_available else "❌ Unavailable"
            accounts_html += f"""
            <div class="account">
                <h3>{i}. {acc.name or acc.email} {status}</h3>
                <p><strong>Email:</strong> {acc.email}</p>
                <p><strong>ID:</strong> {acc.id}</p>
                <p><strong>Requests:</strong> {acc.total_requests} (Failures: {acc.total_failures})</p>
                <p><strong>Models:</strong> {len(acc.quotas)} available</p>
            </div>
            """
        
        if not accounts:
            accounts_html = "<p>No accounts found. Add one using the button below.</p>"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cloud Code Accounts</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                }}
                h1 {{
                    text-align: center;
                    color: #333;
                }}
                .account {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                    border-left: 4px solid #007bff;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #28a745;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 20px 0;
                }}
                .center {{
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <h1>Cloud Code Accounts</h1>
            <div class="center">
                <a href="/api/v1/oauth/google/login" class="button">+ Add New Account</a>
            </div>
            {accounts_html}
            <div class="center">
                <p>Total: {len(accounts)} accounts</p>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

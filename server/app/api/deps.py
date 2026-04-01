"""
API dependencies
Common dependencies for API endpoints
"""
from typing import Optional, AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_access_token
from app.db.session import get_db
from app.db.models import User


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_redis():
    """
    Get Redis client for caching and OTP storage.
    Returns None if Redis is not configured.
    """
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url)
        yield client
        await client.close()
    except Exception:
        yield None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == UUID(payload.sub))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def get_storage_path():
    """Get storage directory path"""
    return settings.STORAGE_DIR


def get_max_file_size():
    """Get maximum file size"""
    return settings.MAX_FILE_SIZE


async def resolve_workspace_id(
    workspace_id_input: str,
    current_user: User,
    db: AsyncSession
) -> UUID:
    """
    Resolve a workspace ID string to a valid UUID.
    If 'default' or empty is passed, it returns the user's oldest joined workspace.
    """
    from uuid import UUID
    if not workspace_id_input or str(workspace_id_input).lower() == "default":
        from sqlalchemy import select
        from app.db.models import Workspace, WorkspaceUser
        result = await db.execute(
            select(Workspace.id)
            .join(WorkspaceUser)
            .where(WorkspaceUser.user_id == current_user.id)
            .order_by(Workspace.created_at.asc())
            .limit(1)
        )
        default_id = result.scalar_one_or_none()
        if not default_id:
             raise HTTPException(status_code=404, detail="User has no workspace")
        return default_id
    
    try:
        if isinstance(workspace_id_input, UUID):
            return workspace_id_input
        return UUID(str(workspace_id_input))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid workspace ID format")

async def get_workspace_id(
    workspace_id: Optional[str] = None,
) -> str:
    """
    Get workspace ID from query parameter.
    Returns a default workspace ID if not provided.
    """
    if workspace_id:
        return workspace_id
    # Return a default workspace ID for testing/development
    return "default-workspace"

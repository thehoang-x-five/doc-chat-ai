"""
Authentication API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, get_redis
from app.services.auth.auth_service import (
    AuthService,
    UserExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    OTPRequiredError,
)
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    AuthTokenResponse,
    RefreshRequest,
    OTPRequestRequest,
    OTPResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    ForgotPasswordRequest,
    ChangePasswordRequest,
    UserResponse,
)
from app.schemas.common import SuccessResponse
from app.db.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.
    """
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.register(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
        )
        return RegisterResponse(user=UserResponse.model_validate(user))
    except UserExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and issue tokens.
    """
    auth_service = AuthService(db)
    
    try:
        user, token_pair = await auth_service.login(
            email=data.email,
            password=data.password,
            ip_address=get_client_ip(request),
        )
        
        # Set refresh token in HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=token_pair.refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        
        return AuthTokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            user=UserResponse.model_validate(user),
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    data: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.
    Token can be provided in body or cookie.
    """
    # Get refresh token from body or cookie
    refresh_token = None
    if data and data.refresh_token:
        refresh_token = data.refresh_token
    else:
        refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )
    
    auth_service = AuthService(db)
    
    try:
        user, token_pair = await auth_service.refresh(
            refresh_token=refresh_token,
            ip_address=get_client_ip(request),
        )
        
        # Update cookie
        response.set_cookie(
            key="refresh_token",
            value=token_pair.refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        
        return AuthTokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            user=UserResponse.model_validate(user),
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout user and invalidate refresh token.
    """
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        auth_service = AuthService(db)
        await auth_service.logout(current_user.id, refresh_token)
    
    # Clear cookie
    response.delete_cookie("refresh_token")
    
    return SuccessResponse(message="Logged out successfully")


@router.post("/otp/request", response_model=OTPResponse)
async def request_otp(
    data: OTPRequestRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Request OTP for email verification.
    """
    auth_service = AuthService(db, redis)
    
    # Generate OTP (in production, send via email)
    otp = await auth_service.request_otp(data.email, data.intent_id)
    
    # TODO: Send OTP via email service
    # For development, log the OTP
    print(f"OTP for {data.email}: {otp}")
    
    return OTPResponse()


@router.post("/otp/verify", response_model=OTPVerifyResponse)
async def verify_otp(
    data: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Verify OTP code.
    """
    auth_service = AuthService(db, redis)
    
    valid = await auth_service.verify_otp(data.email, data.intent_id, data.otp)
    
    return OTPVerifyResponse(
        valid=valid,
        message="OTP verified" if valid else "Invalid or expired OTP",
    )


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Reset password using OTP verification.
    """
    auth_service = AuthService(db, redis)
    
    try:
        await auth_service.forgot_password(
            email=data.email,
            otp=data.otp,
            new_password=data.new_password,
        )
        return SuccessResponse(message="Password reset successfully")
    except OTPRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Change password for authenticated user.
    """
    auth_service = AuthService(db, redis)
    
    try:
        await auth_service.change_password(
            user_id=current_user.id,
            otp=data.otp,
            current_password=data.current_password,
            new_password=data.new_password,
        )
        return SuccessResponse(message="Password changed successfully")
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except OTPRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user information.
    """
    return UserResponse.model_validate(current_user)

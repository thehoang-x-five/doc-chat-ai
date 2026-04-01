"""
Authentication Pydantic schemas.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    full_name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class OTPRequestRequest(BaseModel):
    """OTP request."""
    email: EmailStr
    intent_id: str = Field(..., pattern="^(password_reset|email_verify|password_change)$")


class OTPVerifyRequest(BaseModel):
    """OTP verification request."""
    email: EmailStr
    intent_id: str
    otp: str = Field(..., min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=64)


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    otp: str = Field(..., min_length=6, max_length=6)
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=64)


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class UserResponse(BaseModel):
    """User information response."""
    id: UUID
    email: str
    full_name: Optional[str]
    role_global: str
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AuthTokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RegisterResponse(BaseModel):
    """Registration response."""
    user: UserResponse
    message: str = "Registration successful"


class OTPResponse(BaseModel):
    """OTP request response."""
    message: str = "OTP sent to email"
    expires_in: int = 300


class OTPVerifyResponse(BaseModel):
    """OTP verification response."""
    valid: bool
    message: str

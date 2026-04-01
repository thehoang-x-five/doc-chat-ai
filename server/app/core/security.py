"""
Security utilities for authentication.
JWT token generation/validation, password hashing, OTP management.
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    role: str  # user role
    exp: datetime
    type: str  # "access" or "refresh"


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# =============================================================================
# PASSWORD HASHING
# =============================================================================

def _prepare_password(password: str) -> str:
    """
    Prepare password for bcrypt by hashing with SHA256 first.
    This handles passwords longer than 72 bytes.
    
    Args:
        password: Plain text password
        
    Returns:
        Base64-encoded SHA256 hash (always 44 chars, safe for bcrypt)
    """
    import base64
    # Hash with SHA256 first to handle any length password
    sha256_hash = hashlib.sha256(password.encode('utf-8')).digest()
    # Base64 encode to get printable string (44 chars)
    return base64.b64encode(sha256_hash).decode('ascii')


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    prepared = _prepare_password(password)
    return pwd_context.hash(prepared)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    prepared = _prepare_password(plain_password)
    return pwd_context.verify(prepared, hashed_password)


# =============================================================================
# JWT TOKEN MANAGEMENT
# =============================================================================

def create_access_token(user_id: str, role: str) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User's UUID as string
        role: User's role (ADMIN, USER)
        
    Returns:
        Encoded JWT access token
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> Tuple[str, str, datetime]:
    """
    Create a refresh token.
    
    Args:
        user_id: User's UUID as string
        
    Returns:
        Tuple of (raw_token, token_hash, expires_at)
    """
    # Generate random token
    raw_token = secrets.token_urlsafe(32)
    
    # Hash for storage
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    # Expiration
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    
    return raw_token, token_hash, expires_at


def verify_access_token(token: str) -> Optional[TokenPayload]:
    """
    Verify and decode a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenPayload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            return None
        return TokenPayload(**payload)
    except JWTError:
        return None


def verify_refresh_token_hash(raw_token: str, stored_hash: str) -> bool:
    """
    Verify a refresh token against its stored hash.
    
    Args:
        raw_token: Raw refresh token from client
        stored_hash: Hash stored in database
        
    Returns:
        True if token matches hash
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return secrets.compare_digest(token_hash, stored_hash)


# =============================================================================
# OTP MANAGEMENT
# =============================================================================

def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric OTP code.
    
    Args:
        length: Number of digits (default 6)
        
    Returns:
        OTP code string
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(otp: str, email: str, intent_id: str) -> str:
    """
    Hash OTP with email and intent for storage.
    
    Args:
        otp: OTP code
        email: User's email
        intent_id: Intent identifier (e.g., "password_reset", "email_verify")
        
    Returns:
        Hashed OTP string
    """
    data = f"{otp}:{email}:{intent_id}"
    return hashlib.sha256(data.encode()).hexdigest()


def verify_otp_hash(otp: str, email: str, intent_id: str, stored_hash: str) -> bool:
    """
    Verify OTP against stored hash.
    
    Args:
        otp: OTP code to verify
        email: User's email
        intent_id: Intent identifier
        stored_hash: Hash stored in Redis
        
    Returns:
        True if OTP is valid
    """
    computed_hash = hash_otp(otp, email, intent_id)
    return secrets.compare_digest(computed_hash, stored_hash)


# =============================================================================
# TOKEN PAIR CREATION
# =============================================================================

def create_token_pair(user_id: str, role: str) -> Tuple[TokenPair, str, datetime]:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: User's UUID as string
        role: User's role
        
    Returns:
        Tuple of (TokenPair, refresh_token_hash, refresh_expires_at)
    """
    access_token = create_access_token(user_id, role)
    raw_refresh, refresh_hash, refresh_expires = create_refresh_token(user_id)
    
    token_pair = TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    
    return token_pair, refresh_hash, refresh_expires

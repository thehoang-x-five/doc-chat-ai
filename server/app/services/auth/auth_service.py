"""
Authentication service cho việc đăng ký, đăng nhập và quản lý token của người dùng.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_token_pair,
    verify_refresh_token_hash,
    generate_otp,
    hash_otp,
    verify_otp_hash,
    TokenPair,
)
from app.core.email import email_service
from app.db.models import User, RefreshToken, WorkspaceUser, Workspace


class AuthServiceError(Exception):
    """Base exception cho auth service errors."""
    pass


class UserExistsError(AuthServiceError):
    """Người dùng đã tồn tại."""
    pass


class InvalidCredentialsError(AuthServiceError):
    """Thông tin đăng nhập không hợp lệ."""
    pass


class InvalidTokenError(AuthServiceError):
    """Token không hợp lệ hoặc đã hết hạn."""
    pass


class OTPRequiredError(AuthServiceError):
    """Yêu cầu xác thực OTP."""
    pass


class OTPCooldownError(AuthServiceError):
    """Chưa hết thời gian chờ gửi lại OTP."""
    pass


class OTPMaxAttemptsError(AuthServiceError):
    """Vượt quá số lần thử xác thực OTP tối đa."""
    pass


class AuthService:
    """
    Authentication service xử lý đăng ký, đăng nhập và quản lý token.
    """
    
    def __init__(self, session: AsyncSession, redis_client=None):
        self.session = session
        self.redis = redis_client
        # Sử dụng settings từ config
        self.OTP_EXPIRY_SECONDS = settings.otp_expire_minutes * 60
        self.OTP_COOLDOWN_SECONDS = settings.otp_resend_cooldown_seconds
        self.OTP_MAX_ATTEMPTS = settings.otp_max_verify_attempts
        self.OTP_CODE_LENGTH = settings.otp_code_length

    # =========================================================================
    # ĐĂNG KÝ (REGISTRATION)
    # =========================================================================
    
    async def register(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> User:
        """
        Đăng ký người dùng mới.
        
        Args:
            email: Địa chỉ email người dùng
            password: Mật khẩu dạng plain text
            full_name: Họ tên đầy đủ (tùy chọn)
            
        Returns:
            User object đã tạo
            
        Raises:
            UserExistsError: Nếu email đã được đăng ký
        """
        # Kiểm tra nếu user đã tồn tại
        existing = await self.session.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none():
            raise UserExistsError(f"Người dùng với email {email} đã tồn tại")
        
        # Tạo user
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role_global="USER",
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        
        return user
    
    # =========================================================================
    # ĐĂNG NHẬP (LOGIN)
    # =========================================================================
    
    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, TokenPair]:
        """
        Xác thực người dùng và cấp token.
        
        Args:
            email: Email người dùng
            password: Mật khẩu dạng plain text
            ip_address: IP Client để audit
            
        Returns:
            Tuple của (User, TokenPair)
            
        Raises:
            InvalidCredentialsError: Nếu thông tin đăng nhập không hợp lệ
        """
        # Tìm user
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Email hoặc mật khẩu không hợp lệ")
        
        # Tạo tokens
        token_pair, refresh_hash, refresh_expires = create_token_pair(
            str(user.id), user.role_global
        )
        
        # Lưu refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires,
            ip_address=ip_address,
        )
        self.session.add(refresh_token)
        
        # Cập nhật lần đăng nhập cuối
        user.last_login_at = datetime.now(timezone.utc)
        
        await self.session.flush()
        
        return user, token_pair

    # =========================================================================
    # LÀM MỚI TOKEN (TOKEN REFRESH)
    # =========================================================================
    
    async def refresh(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, TokenPair]:
        """
        Làm mới access token sử dụng refresh token.
        
        Args:
            refresh_token: Raw refresh token
            ip_address: IP Client để audit
            
        Returns:
            Tuple của (User, TokenPair mới)
            
        Raises:
            InvalidTokenError: Nếu refresh token không hợp lệ hoặc đã hết hạn
        """
        # Tìm tất cả refresh tokens chưa bị thu hồi
        result = await self.session.execute(
            select(RefreshToken)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > datetime.now(timezone.utc))
        )
        tokens = result.scalars().all()
        
        # Tìm token khớp
        valid_token = None
        for token in tokens:
            if verify_refresh_token_hash(refresh_token, token.token_hash):
                valid_token = token
                break
        
        if not valid_token:
            raise InvalidTokenError("Refresh token không hợp lệ hoặc đã hết hạn")
        
        # Lấy user
        result = await self.session.execute(
            select(User).where(User.id == valid_token.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidTokenError("Không tìm thấy người dùng")
        
        # Thu hồi token cũ
        valid_token.revoked_at = datetime.now(timezone.utc)
        
        # Tạo tokens mới
        token_pair, refresh_hash, refresh_expires = create_token_pair(
            str(user.id), user.role_global
        )
        
        # Lưu refresh token mới
        new_refresh = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires,
            ip_address=ip_address,
        )
        self.session.add(new_refresh)
        
        await self.session.flush()
        
        return user, token_pair
    
    # =========================================================================
    # ĐĂNG XUẤT (LOGOUT)
    # =========================================================================
    
    async def logout(self, user_id: UUID, refresh_token: str) -> None:
        """
        Đăng xuất người dùng bằng cách thu hồi refresh token.
        
        Args:
            user_id: ID người dùng
            refresh_token: Raw refresh token để thu hồi
        """
        result = await self.session.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            if verify_refresh_token_hash(refresh_token, token.token_hash):
                token.revoked_at = datetime.now(timezone.utc)
                break
        
        await self.session.flush()

    # =========================================================================
    # QUẢN LÝ OTP (OTP MANAGEMENT)
    # =========================================================================
    
    async def request_otp(self, email: str, intent_id: str, send_email: bool = True) -> str:
        """
        Tạo và lưu trữ OTP để xác thực email.
        
        Args:
            email: Email người dùng
            intent_id: Định danh intent (password_reset, email_verify, v.v.)
            send_email: Có gửi OTP qua email hay không
            
        Returns:
            Mã OTP đã tạo
            
        Raises:
            OTPCooldownError: Nếu chưa hết thời gian chờ (cooldown)
        """
        if self.redis:
            # Kiểm tra cooldown
            cooldown_key = f"otp_cooldown:{intent_id}:{email}"
            if await self.redis.exists(cooldown_key):
                ttl = await self.redis.ttl(cooldown_key)
                raise OTPCooldownError(f"Vui lòng đợi {ttl} giây trước khi yêu cầu OTP mới")
        
        otp = generate_otp(self.OTP_CODE_LENGTH)
        otp_hash = hash_otp(otp, email, intent_id)
        
        # Lưu vào Redis với thời hạn
        if self.redis:
            key = f"otp:{intent_id}:{email}"
            attempts_key = f"otp_attempts:{intent_id}:{email}"
            
            await self.redis.setex(key, self.OTP_EXPIRY_SECONDS, otp_hash)
            await self.redis.setex(cooldown_key, self.OTP_COOLDOWN_SECONDS, "1")
            await self.redis.delete(attempts_key)  # Reset số lần thử khi có OTP mới
        
        # Gửi email
        if send_email:
            email_service.send_otp_email(email, otp, intent_id)
        
        return otp
    
    async def verify_otp(self, email: str, intent_id: str, otp: str) -> bool:
        """
        Xác thực mã OTP.
        
        Args:
            email: Email người dùng
            intent_id: Định danh intent
            otp: Mã OTP cần xác thực
            
        Returns:
            True nếu OTP hợp lệ
            
        Raises:
            OTPMaxAttemptsError: Nếu vượt quá số lần thử tối đa
        """
        if not self.redis:
            return False
        
        key = f"otp:{intent_id}:{email}"
        attempts_key = f"otp_attempts:{intent_id}:{email}"
        
        # Check attempts
        attempts = await self.redis.get(attempts_key)
        if attempts and int(attempts) >= self.OTP_MAX_ATTEMPTS:
            await self.redis.delete(key)  # Vô hiệu hóa OTP
            raise OTPMaxAttemptsError("Vượt quá số lần thử xác thực tối đa")
        
        stored_hash = await self.redis.get(key)
        
        if not stored_hash:
            return False
        
        if verify_otp_hash(otp, email, intent_id, stored_hash.decode()):
            # Xóa OTP sau khi xác thực thành công
            await self.redis.delete(key)
            await self.redis.delete(attempts_key)
            return True
        
        # Tăng số lần thử
        await self.redis.incr(attempts_key)
        await self.redis.expire(attempts_key, self.OTP_EXPIRY_SECONDS)
        
        return False
    
    # =========================================================================
    # QUẢN LÝ MẬT KHẨU (PASSWORD MANAGEMENT)
    # =========================================================================
    
    async def forgot_password(
        self,
        email: str,
        otp: str,
        new_password: str,
    ) -> bool:
        """
        Reset mật khẩu sau khi xác thực OTP.
        
        Args:
            email: Email người dùng
            otp: Mã OTP
            new_password: Mật khẩu mới
            
        Returns:
            True nếu mật khẩu đã được reset
            
        Raises:
            OTPRequiredError: Nếu OTP không hợp lệ
        """
        # Xác thực OTP
        if not await self.verify_otp(email, "password_reset", otp):
            raise OTPRequiredError("OTP không hợp lệ hoặc đã hết hạn")
        
        # Cập nhật mật khẩu
        result = await self.session.execute(
            update(User)
            .where(User.email == email)
            .values(password_hash=hash_password(new_password))
        )
        
        if result.rowcount == 0:
            return False
        
        # Thu hồi tất cả refresh tokens
        await self._revoke_all_tokens_by_email(email)
        
        await self.session.flush()
        return True

    async def change_password(
        self,
        user_id: UUID,
        otp: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Đổi mật khẩu cho user đã xác thực.
        
        Args:
            user_id: ID người dùng
            otp: Mã OTP
            current_password: Mật khẩu hiện tại để xác minh
            new_password: Mật khẩu mới
            
        Returns:
            True nếu mật khẩu được thay đổi
            
        Raises:
            InvalidCredentialsError: Nếu mật khẩu hiện tại sai
            OTPRequiredError: Nếu OTP không hợp lệ
        """
        # Lấy user
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidCredentialsError("Không tìm thấy người dùng")
        
        # Xác minh mật khẩu hiện tại
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Mật khẩu hiện tại không chính xác")
        
        # Xác thực OTP
        if not await self.verify_otp(user.email, "password_change", otp):
            raise OTPRequiredError("OTP không hợp lệ hoặc đã hết hạn")
        
        # Cập nhật mật khẩu
        user.password_hash = hash_password(new_password)
        
        # Thu hồi tất cả refresh tokens
        await self._revoke_all_tokens(user_id)
        
        await self.session.flush()
        return True
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _revoke_all_tokens(self, user_id: UUID) -> None:
        """Thu hồi tất cả refresh tokens của một người dùng."""
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
    
    async def _revoke_all_tokens_by_email(self, email: str) -> None:
        """Thu hồi tất cả refresh tokens của một người dùng theo email."""
        result = await self.session.execute(
            select(User.id).where(User.email == email)
        )
        user_id = result.scalar_one_or_none()
        if user_id:
            await self._revoke_all_tokens(user_id)
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Lấy người dùng theo ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Lấy người dùng theo email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

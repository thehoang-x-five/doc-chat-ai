"""
Email service for sending OTP and notifications.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service using SMTP."""
    
    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from
        self.display_name = settings.smtp_display_name
        self.enable_ssl = settings.smtp_enable_ssl
    
    def _create_connection(self):
        """Create SMTP connection."""
        if self.enable_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP(self.host, self.port)
            server.starttls(context=context)
        else:
            server = smtplib.SMTP(self.host, self.port)
        
        server.login(self.user, self.password)
        return server
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body_html: HTML body
            body_text: Plain text body (optional)
            
        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.display_name} <{self.from_email}>"
            msg["To"] = to_email
            
            # Add plain text part
            if body_text:
                part1 = MIMEText(body_text, "plain")
                msg.attach(part1)
            
            # Add HTML part
            part2 = MIMEText(body_html, "html")
            msg.attach(part2)
            
            # Send
            server = self._create_connection()
            server.sendmail(self.from_email, to_email, msg.as_string())
            server.quit()
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_otp_email(self, to_email: str, otp_code: str, intent: str) -> bool:
        """
        Send OTP verification email.
        
        Args:
            to_email: Recipient email
            otp_code: OTP code
            intent: Purpose (password_reset, email_verify, etc.)
            
        Returns:
            True if sent successfully
        """
        intent_messages = {
            "password_reset": {
                "subject": "Đặt lại mật khẩu - RAG Platform",
                "title": "Đặt lại mật khẩu",
                "message": "Bạn đã yêu cầu đặt lại mật khẩu. Sử dụng mã OTP bên dưới để xác nhận:",
            },
            "email_verify": {
                "subject": "Xác thực email - RAG Platform",
                "title": "Xác thực email",
                "message": "Vui lòng sử dụng mã OTP bên dưới để xác thực địa chỉ email của bạn:",
            },
            "login_verify": {
                "subject": "Xác thực đăng nhập - RAG Platform",
                "title": "Xác thực đăng nhập",
                "message": "Sử dụng mã OTP bên dưới để hoàn tất đăng nhập:",
            },
        }
        
        config = intent_messages.get(intent, {
            "subject": f"Mã OTP - RAG Platform",
            "title": "Xác thực",
            "message": "Mã OTP của bạn:",
        })
        
        expire_minutes = settings.otp_expire_minutes
        
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
                .otp-code {{ font-size: 32px; font-weight: bold; color: #4F46E5; text-align: center; 
                            padding: 20px; background: white; border-radius: 8px; margin: 20px 0;
                            letter-spacing: 8px; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{config['title']}</h1>
                </div>
                <div class="content">
                    <p>Xin chào,</p>
                    <p>{config['message']}</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>Mã này sẽ hết hạn sau <strong>{expire_minutes} phút</strong>.</p>
                    <p>Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.</p>
                </div>
                <div class="footer">
                    <p>© 2025 RAG Platform. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        {config['title']}
        
        {config['message']}
        
        Mã OTP: {otp_code}
        
        Mã này sẽ hết hạn sau {expire_minutes} phút.
        
        Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.
        """
        
        return self.send_email(to_email, config["subject"], body_html, body_text)


# Singleton instance
email_service = EmailService()

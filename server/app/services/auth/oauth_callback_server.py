"""
Local OAuth Server - Tương tự cách tiếp cận của Antigravity.

Tạo một local TCP server để nhận OAuth callbacks từ Google.
Điều này giúp tránh các vấn đề về session management và CORS.
"""
import asyncio
import logging
import secrets
from typing import Optional, Callable, Awaitable
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class OAuthCallbackServer:
    """
    Local HTTP server để nhận OAuth callbacks.
    Tương tự như implementation oauth_server.rs của Antigravity.
    """
    
    def __init__(self):
        self.server: Optional[asyncio.Server] = None
        self.port: Optional[int] = None
        self.redirect_uri: Optional[str] = None
        self.code_future: Optional[asyncio.Future] = None
        self._running = False
    
    async def start(self) -> str:
        """
        Khởi động OAuth callback server trên một random port khả dụng.
        Trả về redirect URI để sử dụng cho OAuth.
        """
        if self._running:
            return self.redirect_uri
        
        # Tìm port khả dụng
        self.server = await asyncio.start_server(
            self._handle_connection,
            host='127.0.0.1',
            port=0,  # Để OS tự gán free port
        )
        
        # Lấy port được gán
        addr = self.server.sockets[0].getsockname()
        self.port = addr[1]
        self.redirect_uri = f"http://127.0.0.1:{self.port}/oauth-callback"
        self._running = True
        
        # Tạo future để đợi mã code
        self.code_future = asyncio.get_event_loop().create_future()
        
        logger.info(f"OAuth callback server đã khởi động trên port {self.port}")
        logger.info(f"Redirect URI: {self.redirect_uri}")
        
        # Bắt đầu serve trong background
        asyncio.create_task(self._serve())
        
        return self.redirect_uri
    
    async def _serve(self) -> None:
        """Serve connections cho đến khi stopped."""
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Lỗi OAuth server: {e}")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Xử lý kết nối HTTP đến."""
        try:
            logger.info(f"OAuth server nhận được kết nối trên port {self.port}")
            
            # Đọc HTTP request
            data = await asyncio.wait_for(reader.read(4096), timeout=10.0)
            request = data.decode('utf-8', errors='ignore')
            
            logger.info(f"OAuth server nhận request: {request[:200]}...")
            
            # Parse dòng request
            lines = request.split('\r\n')
            if not lines:
                logger.warning("OAuth server: empty request")
                return
            
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) < 2:
                logger.warning(f"OAuth server: request line không hợp lệ: {request_line}")
                return
            
            method, path = parts[0], parts[1]
            logger.info(f"OAuth server: {method} {path[:100]}...")
            
            # Parse query parameters
            if '?' in path:
                path_part, query_string = path.split('?', 1)
                params = parse_qs(query_string)
            else:
                path_part = path
                params = {}
            
            # Kiểm tra xem đây có phải là OAuth callback
            if '/oauth-callback' in path_part:
                code = params.get('code', [None])[0]
                error = params.get('error', [None])[0]
                
                logger.info(f"OAuth callback: code={code[:20] if code else None}..., error={error}")
                
                if code:
                    # Thành công - gửi response và giải quyết future
                    response = self._success_html()
                    writer.write(response.encode('utf-8'))
                    await writer.drain()
                    
                    logger.info(f"OAuth server: setting code_future result, future.done={self.code_future.done() if self.code_future else 'None'}")
                    
                    if self.code_future and not self.code_future.done():
                        self.code_future.set_result(code)
                        logger.info(f"OAuth server: code_future result set successfully")
                    else:
                        logger.warning(f"OAuth server: code_future đã done hoặc None")
                    
                    logger.info(f"Nhận được OAuth callback thành công, code: {code[:20]}...")
                    
                elif error:
                    # Lỗi từ Google
                    error_desc = params.get('error_description', ['Unknown error'])[0]
                    response = self._error_html(f"{error}: {error_desc}")
                    writer.write(response.encode('utf-8'))
                    await writer.drain()
                    
                    if self.code_future and not self.code_future.done():
                        self.code_future.set_exception(Exception(f"Lỗi OAuth: {error} - {error_desc}"))
                    
                    logger.error(f"Lỗi OAuth: {error} - {error_desc}")
                    
                else:
                    # Không có code hoặc lỗi
                    response = self._error_html("Không nhận được authorization code")
                    writer.write(response.encode('utf-8'))
                    await writer.drain()
            else:
                # Path không xác định
                response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\nNot Found"
                writer.write(response.encode('utf-8'))
                await writer.drain()
                
        except asyncio.TimeoutError:
            logger.warning("OAuth callback connection timeout")
        except Exception as e:
            logger.error(f"Lỗi khi xử lý OAuth callback: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
    
    def _success_html(self) -> str:
        """Tạo HTML response thành công."""
        return """HTTP/1.1 200 OK\r
Content-Type: text/html; charset=utf-8\r
Connection: close\r
\r
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Successful</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .card {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
        }
        .icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
        h1 {
            color: #4CAF50;
            margin: 0 0 10px 0;
            font-size: 24px;
        }
        p {
            color: #666;
            margin: 0;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <h1>Authorization Successful!</h1>
        <p>You can close this window and return to the application.</p>
    </div>
    <script>
        // Try to close window after 2 seconds
        setTimeout(function() {
            try { window.close(); } catch(e) {}
        }, 2000);
    </script>
</body>
</html>"""
    
    def _error_html(self, error: str) -> str:
        """Tạo HTML response lỗi."""
        import html
        safe_error = html.escape(error)
        return f"""HTTP/1.1 200 OK\r
Content-Type: text/html; charset=utf-8\r
Connection: close\r
\r
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Failed</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .card {{
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
        }}
        .icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        h1 {{
            color: #f5576c;
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        p {{
            color: #666;
            margin: 0;
            font-size: 14px;
        }}
        .error {{
            background: #fff3f3;
            border: 1px solid #ffcdd2;
            border-radius: 8px;
            padding: 12px;
            margin-top: 16px;
            color: #c62828;
            font-size: 12px;
            word-break: break-word;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Authorization Failed</h1>
        <p>Please try again or contact support.</p>
        <div class="error">{safe_error}</div>
    </div>
    <script>
        setTimeout(function() {{
            try {{ window.close(); }} catch(e) {{}}
        }}, 3000);
    </script>
</body>
</html>"""
    
    async def wait_for_code(self, timeout: float = 300.0) -> str:
        """
        Đợi authorization code OAuth.
        
        Args:
            timeout: Thời gian chờ tối đa tính bằng giây (mặc định 5 phút)
            
        Returns:
            Authorization code từ Google
            
        Raises:
            asyncio.TimeoutError: Nếu hết thời gian chờ
            Exception: Nếu OAuth thất bại
        """
        if not self.code_future:
            raise RuntimeError("OAuth server chưa được khởi động")
        
        try:
            code = await asyncio.wait_for(self.code_future, timeout=timeout)
            return code
        finally:
            # Dừng server sau khi nhận được code
            await self.stop()
    
    async def stop(self) -> None:
        """Dừng OAuth callback server."""
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
            except:
                pass
            self.server = None
        
        self._running = False
        self.port = None
        logger.info("OAuth callback server stopped")


# Store active OAuth servers by session ID
_oauth_servers: dict[str, OAuthCallbackServer] = {}
_oauth_lock = asyncio.Lock()


async def start_oauth_flow(session_id: str) -> tuple[str, str]:
    """
    Bắt đầu luồng OAuth mới cho một session cụ thể.
    
    Args:
        session_id: Định danh session duy nhất
    
    Returns:
        Tuple của (auth_url, redirect_uri)
    """
    async with _oauth_lock:
        # Dừng bất kỳ server hiện tại nào cho session này
        if session_id in _oauth_servers:
            await _oauth_servers[session_id].stop()
        
        # Tạo server mới
        server = OAuthCallbackServer()
        redirect_uri = await server.start()
        
        # Lưu trữ server theo session ID
        _oauth_servers[session_id] = server
        
        # Tạo auth URL
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import GoogleOAuth
        auth_url = GoogleOAuth.get_auth_url(redirect_uri, "")
        
        logger.info(f"Đã bắt đầu OAuth flow cho session {session_id}, redirect_uri: {redirect_uri}")
        
        return auth_url, redirect_uri


async def wait_for_oauth_code(session_id: str, timeout: float = 300.0) -> str:
    """
    Đợi authorization code OAuth cho một session cụ thể.
    
    Args:
        session_id: Session identifier
        timeout: Thời gian chờ tối đa (giây)
        
    Returns:
        Authorization code
    """
    server = _oauth_servers.get(session_id)
    
    logger.info(f"wait_for_oauth_code gọi cho session {session_id[:8]}, server tồn tại: {server is not None}")
    
    if not server:
        raise RuntimeError(f"OAuth flow chưa bắt đầu cho session {session_id}")
    
    logger.info(f"Đang đợi code trên server port {server.port}, code_future tồn tại: {server.code_future is not None}")
    
    try:
        code = await server.wait_for_code(timeout)
        logger.info(f"Đã nhận code cho session {session_id[:8]}: {code[:20]}...")
        return code
    except Exception as e:
        logger.error(f"Lỗi khi đợi code cho session {session_id[:8]}: {e}")
        raise
    finally:
        # Dọn dẹp server sau khi lấy code
        async with _oauth_lock:
            _oauth_servers.pop(session_id, None)


async def cancel_oauth_flow(session_id: str = None) -> None:
    """Hủy OAuth flow(s)."""
    async with _oauth_lock:
        if session_id:
            # Hủy session cụ thể
            if session_id in _oauth_servers:
                await _oauth_servers[session_id].stop()
                del _oauth_servers[session_id]
        else:
            # Hủy tất cả sessions
            for server in _oauth_servers.values():
                await server.stop()
            _oauth_servers.clear()


def get_oauth_redirect_uri(session_id: str) -> Optional[str]:
    """Lấy OAuth redirect URI cho một session."""
    server = _oauth_servers.get(session_id)
    return server.redirect_uri if server else None

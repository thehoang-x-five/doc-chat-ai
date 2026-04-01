"""
Request logging middleware with correlation IDs.
Provides structured logging for all API requests.
"""
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return correlation_id_var.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests with correlation IDs.
    
    Features:
    - Generates unique correlation ID for each request
    - Logs request start and completion
    - Tracks response time
    - Adds correlation ID to response headers
    """
    
    # Paths to skip logging (health checks, etc.)
    SKIP_PATHS = {"/api/health", "/api/v1/health", "/api/v1/health/live", "/docs", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for certain paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
        correlation_id_var.set(correlation_id)
        
        # Extract request info
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")[:50]
        
        # Log request start
        logger.info(
            f"[{correlation_id}] --> {method} {path}"
            f"{f'?{query}' if query else ''} "
            f"from {client_ip}"
        )
        
        # Process request
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            status_code = response.status_code
            log_level = logging.INFO if status_code < 400 else logging.WARNING
            
            logger.log(
                log_level,
                f"[{correlation_id}] <-- {method} {path} "
                f"{status_code} {duration_ms:.0f}ms"
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{correlation_id}] <-- {method} {path} "
                f"ERROR {duration_ms:.0f}ms: {str(e)[:100]}"
            )
            raise
        finally:
            # Clear correlation ID
            correlation_id_var.set(None)


class CorrelationIDFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to log records.
    Use with logging formatters to include correlation ID in all logs.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


def setup_logging(level: str = "INFO", json_format: bool = False):
    """
    Set up structured logging with correlation ID support.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format for logs (for production)
    """
    # Create formatter
    if json_format:
        format_str = (
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"correlation_id": "%(correlation_id)s", "name": "%(name)s", '
            '"message": "%(message)s"}'
        )
    else:
        format_str = (
            "%(asctime)s - %(levelname)s - [%(correlation_id)s] - "
            "%(name)s - %(message)s"
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handler with filter
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format_str))
    handler.addFilter(CorrelationIDFilter())
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

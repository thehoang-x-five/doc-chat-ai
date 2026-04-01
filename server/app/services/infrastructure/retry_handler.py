"""
Retry Handler - Exponential backoff retry logic for LLM calls.

Reduces worst-case retry delay from 15s to 7s with smarter retry strategy.
"""

import asyncio
import logging
import time
from typing import Any, Callable, List, Optional, Type

logger = logging.getLogger(__name__)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, attempts: int, total_time: float, last_error: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.total_time = total_time
        self.last_error = last_error


class RetryHandler:
    """
    Exponential backoff retry handler for LLM API calls.
    
    Features:
    - Exponential backoff: 1s, 2s, 4s (max 7s total delay)
    - Skips retry for non-retryable errors (4xx)
    - Logs retry attempts with reason
    - Tracks metrics (attempt count, total time)
    
    Usage:
        retry_handler = RetryHandler(max_retries=3)
        result = await retry_handler.execute(async_function)
    """
    
    # Default retryable exceptions
    DEFAULT_RETRYABLE = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 8.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Optional[tuple] = None,
    ):
        """
        Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay cap in seconds (default: 8.0)
            exponential_base: Multiplier for exponential backoff (default: 2.0)
            retryable_exceptions: Tuple of exception types to retry
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions or self.DEFAULT_RETRYABLE
        
        # Metrics
        self._last_attempt_count = 0
        self._last_total_time = 0.0
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
    
    def is_retryable(self, error: Exception) -> bool:
        """
        Check if error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if retryable, False otherwise
        """
        # Check for HTTP status code (4xx = don't retry)
        if hasattr(error, 'status_code'):
            status = error.status_code
            if 400 <= status < 500:
                logger.debug(f"Non-retryable client error: {status}")
                return False
        
        # Check for response status in httpx/aiohttp style
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status = error.response.status_code
            if 400 <= status < 500:
                logger.debug(f"Non-retryable client error: {status}")
                return False
        
        # Check if it's a known retryable exception type
        if isinstance(error, self.retryable_exceptions):
            return True
        
        # Check error message for common retryable patterns
        error_str = str(error).lower()
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "429",  # Too Many Requests
            "500",  # Internal Server Error
            "502",  # Bad Gateway
            "503",  # Service Unavailable
            "504",  # Gateway Timeout
        ]
        
        for pattern in retryable_patterns:
            if pattern in error_str:
                return True
        
        return False
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            RetryExhaustedError: If all retries exhausted
            Exception: Original exception if not retryable
        """
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                # Log success after retries
                if attempt > 0:
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Succeeded after {attempt} retries ({elapsed:.1f}s)")
                
                self._last_attempt_count = attempt + 1
                self._last_total_time = time.time() - start_time
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Check if retryable
                if not self.is_retryable(e):
                    logger.warning(f"❌ Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
                # Check if we have retries left
                if attempt >= self.max_retries:
                    break
                
                # Calculate delay
                delay = self.get_delay(attempt)
                
                logger.warning(
                    f"⚠️ Retry {attempt + 1}/{self.max_retries}: "
                    f"{type(e).__name__}: {str(e)[:100]}... "
                    f"Waiting {delay:.1f}s"
                )
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        total_time = time.time() - start_time
        self._last_attempt_count = self.max_retries + 1
        self._last_total_time = total_time
        
        raise RetryExhaustedError(
            f"All {self.max_retries} retries exhausted after {total_time:.1f}s",
            attempts=self.max_retries + 1,
            total_time=total_time,
            last_error=last_error,
        )
    
    @property
    def last_attempt_count(self) -> int:
        """Get attempt count from last execution."""
        return self._last_attempt_count
    
    @property
    def last_total_time(self) -> float:
        """Get total time from last execution."""
        return self._last_total_time


# Global default instance
default_retry_handler = RetryHandler()


async def with_retry(func: Callable, *args, **kwargs) -> Any:
    """
    Convenience function to execute with default retry handler.
    
    Usage:
        result = await with_retry(my_async_func, arg1, arg2)
    """
    return await default_retry_handler.execute(func, *args, **kwargs)

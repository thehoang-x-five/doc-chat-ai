"""
Base AI Provider Interface
All AI providers must implement this interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator


class ProviderException(Exception):
    """Base exception for provider errors"""
    pass


class QuotaExceededException(ProviderException):
    """Raised when provider quota/credits are exhausted"""
    pass


class RateLimitException(ProviderException):
    """Raised when provider rate limit is exceeded"""
    pass


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers
    All providers (Groq, DeepSeek, Gemini, Ollama) must implement this interface
    """
    
    def __init__(self, api_key: str, base_url: str, model: str, vision_model: Optional[str] = None):
        """
        Initialize provider
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for API endpoint
            model: Default model to use
            vision_model: Vision model name (if supported)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.vision_model = vision_model
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send chat completion request
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to self.model)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
            
        Raises:
            QuotaExceededException: If quota/credits exhausted
            RateLimitException: If rate limit exceeded
            ProviderException: For other provider errors
        """
        pass

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion response.
        Default implementation falls back to chat_completion if not overridden.
        """
        # Default behavior: buffer entire response and yield as single chunk
        # This allows all providers to support "streaming" interface even if they don't support it natively
        response = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        yield response

    
    @abstractmethod
    async def vision_completion(
        self,
        prompt: str,
        image_data: bytes,
        model: Optional[str] = None
    ) -> str:
        """
        Send vision-based completion request
        
        Args:
            prompt: Text prompt for image analysis
            image_data: Image bytes
            model: Vision model to use (defaults to self.vision_model)
            
        Returns:
            Generated text response from image analysis
            
        Raises:
            QuotaExceededException: If quota/credits exhausted
            RateLimitException: If rate limit exceeded
            ProviderException: For other provider errors
            NotImplementedError: If provider doesn't support vision
        """
        pass
    
    @abstractmethod
    async def check_health(self) -> bool:
        """
        Check if provider is available and healthy
        
        Returns:
            True if provider is available, False otherwise
        """
        pass
    
    @abstractmethod
    def supports_vision(self) -> bool:
        """
        Check if provider supports vision models
        
        Returns:
            True if vision is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get provider name
        
        Returns:
            Provider name (e.g., "groq", "deepseek", "gemini", "ollama")
        """
        pass

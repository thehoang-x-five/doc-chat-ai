"""
Cloud Code AI Provider Wrapper
Wraps CloudCodeProviderManager to work with AIProviderManager interface.
Provides FREE access to Claude/Gemini models via Google Cloud Code API.
"""
import logging
from typing import List, Dict, Optional, AsyncGenerator
from pathlib import Path

from app.services.infrastructure.ai_providers.base_provider import (
    BaseAIProvider,
    ProviderException,
    QuotaExceededException,
    RateLimitException
)

logger = logging.getLogger(__name__)


class CloudCodeProvider(BaseAIProvider):
    """
    Cloud Code AI provider - FREE Claude/Gemini access.
    
    Uses Google's internal Cloud Code API (cloudcode-pa.googleapis.com)
    which provides free access to Claude 4.5 Sonnet, Gemini 2.5/3 models.
    
    Features:
    - Multi-account support with automatic rotation
    - Smart model selection based on quota
    - Auto-fallback when quota exhausted
    """
    
    def __init__(
        self, 
        api_key: str = "",  # Not used, accounts loaded from storage
        base_url: str = "",  # Not used
        model: str = "claude-sonnet-4-5",  # Default to strongest model
        vision_model: Optional[str] = "gemini-3-pro-high",
        accounts_dir: Optional[str] = None,
    ):
        """
        Initialize Cloud Code provider.
        
        Args:
            api_key: Not used (accounts loaded from storage)
            base_url: Not used
            model: Default model (claude-sonnet-4-5, gemini-3-flash, etc.)
            vision_model: Vision model for image analysis
            accounts_dir: Directory containing Cloud Code account JSON files
        """
        super().__init__(api_key, base_url, model, vision_model)
        
        self._manager = None
        self._accounts_dir = Path(accounts_dir) if accounts_dir else Path("./storage/cloudcode_accounts")
        self._initialized = False
        
        logger.info(f"Initialized Cloud Code provider with model {self.model}")
    
    async def _ensure_initialized(self):
        """Lazy initialization of CloudCodeProviderManager."""
        if self._initialized:
            return
        
        try:
            from app.services.infrastructure.ai_providers.cloudcode_provider_service import CloudCodeProviderManager
            
            self._manager = CloudCodeProviderManager(self._accounts_dir)
            count = await self._manager.load_accounts()
            
            if count == 0:
                logger.warning("No Cloud Code accounts found. Add accounts via /api/v1/cloudcode/accounts")
            else:
                logger.info(f"Cloud Code provider loaded {count} accounts")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Code manager: {e}")
            raise ProviderException(f"Cloud Code initialization failed: {e}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send chat completion request via Cloud Code.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (claude-sonnet-4-5, gemini-3-flash, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        await self._ensure_initialized()
        
        if not self._manager or not self._manager.list_accounts():
            raise ProviderException("No Cloud Code accounts available")
        
        model = model or self.model
        
        try:
            logger.debug(f"Sending Cloud Code request with model {model}")
            
            response = await self._manager.generate(
                messages=messages,
                model=model,
                max_tokens=max_tokens or 2048,
                temperature=temperature,
                auto_fallback=True,
            )
            
            if not response.success:
                error = response.error or "Unknown error"
                
                # Check for quota/rate limit errors
                if "429" in error or "quota" in error.lower() or "rate" in error.lower():
                    raise QuotaExceededException(f"Cloud Code quota exceeded: {error}")
                
                raise ProviderException(f"Cloud Code error: {error}")
            
            content = response.content or ""
            logger.debug(f"Cloud Code response: {len(content)} chars from {response.model} ({response.account_email})")
            
            return content
            
        except QuotaExceededException:
            raise
        except Exception as e:
            logger.error(f"Cloud Code chat completion failed: {e}")
            raise ProviderException(f"Cloud Code error: {str(e)}")

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion request via Cloud Code.
        """
        await self._ensure_initialized()
        
        if not self._manager or not self._manager.list_accounts():
            yield "" # Or raise exception, but generator usually just stops
            return
        
        model = model or self.model
        
        try:
            logger.debug(f"Streaming Cloud Code request with model {model}")
            
            async for chunk in self._manager.stream_generate(
                messages=messages,
                model=model,
                max_tokens=max_tokens or 2048,
                temperature=temperature,
                auto_fallback=True,
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Cloud Code stream failed: {e}")
            yield f"[ERROR: {str(e)}]"

    
    async def vision_completion(
        self,
        prompt: str,
        image_data: bytes,
        model: Optional[str] = None
    ) -> str:
        """
        Send vision-based completion request via Cloud Code.
        
        Args:
            prompt: Text prompt for image analysis
            image_data: Image bytes
            model: Vision model to use
            
        Returns:
            Generated text response from image analysis
        """
        await self._ensure_initialized()
        
        if not self._manager or not self._manager.list_accounts():
            raise ProviderException("No Cloud Code accounts available")
        
        model = model or self.vision_model or "gemini-3-pro-high"
        
        import base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Build vision message in OpenAI format (CloudCode will convert)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    }
                ]
            }
        ]
        
        try:
            response = await self._manager.generate(
                messages=messages,
                model=model,
                max_tokens=2048,
                temperature=0.1,
                auto_fallback=True,
            )
            
            if not response.success:
                raise ProviderException(f"Cloud Code vision error: {response.error}")
            
            return response.content or ""
            
        except Exception as e:
            logger.error(f"Cloud Code vision completion failed: {e}")
            raise ProviderException(f"Cloud Code vision error: {str(e)}")
    
    async def check_health(self) -> bool:
        """
        Check if Cloud Code is available.
        
        Returns:
            True if accounts are loaded and available
        """
        try:
            await self._ensure_initialized()
            
            if not self._manager:
                return False
            
            accounts = self._manager.list_accounts()
            available = [a for a in accounts if a.is_available]
            
            return len(available) > 0
            
        except Exception as e:
            logger.debug(f"Cloud Code health check failed: {e}")
            return False
    
    def supports_vision(self) -> bool:
        """Cloud Code supports vision via Gemini models."""
        return True
    
    def get_name(self) -> str:
        """Get provider name."""
        return "cloudcode"
    
    async def close(self):
        """Close the provider."""
        if self._manager:
            await self._manager.close()

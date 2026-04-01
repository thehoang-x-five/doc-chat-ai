"""
Ollama AI Provider Implementation
Local LLM with vision support
"""
import logging
import httpx
import base64
from typing import List, Dict, Optional
from app.services.infrastructure.ai_providers.base_provider import (
    BaseAIProvider,
    ProviderException,
    QuotaExceededException,
    RateLimitException
)

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """
    Ollama AI provider implementation
    Local LLM with vision support
    """
    
    def __init__(self, api_key: str, base_url: str, model: str, vision_model: Optional[str] = None):
        """
        Initialize Ollama provider
        
        Args:
            api_key: Not used for Ollama (local), but kept for interface consistency
            base_url: Ollama API base URL (e.g., http://localhost:11434/api)
            model: Default model (e.g., llama3.2)
            vision_model: Vision model (e.g., llava)
        """
        super().__init__(api_key, base_url, model, vision_model or "llava")
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"Initialized Ollama provider with model {self.model}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send chat completion request to Ollama
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to self.model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
            
        Raises:
            ProviderException: For errors (Ollama is local, no quota/rate limits)
        """
        model = model or self.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            logger.debug(f"Sending chat completion request to Ollama with model {model}")
            
            response = await self.client.post(
                f"{self.base_url}/chat",
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_msg)
                except:
                    pass
                logger.error(f"Ollama API error: {error_msg}")
                raise ProviderException(f"Ollama API error: {error_msg}")
            
            data = response.json()
            
            if "message" not in data or "content" not in data["message"]:
                raise ProviderException("Ollama returned invalid response format")
            
            content = data["message"]["content"]
            
            logger.debug(f"Ollama chat completion successful, generated {len(content)} characters")
            return content
            
        except httpx.TimeoutException:
            logger.error("Ollama request timeout")
            raise ProviderException("Ollama request timeout")
        except httpx.RequestError as e:
            logger.error(f"Ollama request error: {e}")
            raise ProviderException(f"Ollama request error: {str(e)}")
        except ProviderException:
            raise
        except Exception as e:
            logger.error(f"Unexpected Ollama error: {e}")
            raise ProviderException(f"Unexpected Ollama error: {str(e)}")
    
    async def vision_completion(
        self,
        prompt: str,
        image_data: bytes,
        model: Optional[str] = None
    ) -> str:
        """
        Send vision-based completion request to Ollama
        
        Args:
            prompt: Text prompt for image analysis
            image_data: Image bytes
            model: Vision model to use
            
        Returns:
            Generated text response from image analysis
            
        Raises:
            ProviderException: For errors
        """
        model = model or self.vision_model
        
        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Ollama vision format
        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            logger.debug(f"Sending vision completion request to Ollama with model {model}")
            
            response = await self.client.post(
                f"{self.base_url}/chat",
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_msg)
                except:
                    pass
                raise ProviderException(f"Ollama vision API error: {error_msg}")
            
            data = response.json()
            
            if "message" not in data or "content" not in data["message"]:
                raise ProviderException("Ollama vision returned invalid response format")
            
            content = data["message"]["content"]
            
            logger.debug(f"Ollama vision completion successful")
            return content
            
        except Exception as e:
            logger.error(f"Ollama vision error: {e}")
            raise ProviderException(f"Ollama vision error: {str(e)}")
    
    async def check_health(self) -> bool:
        """
        Check if Ollama is available and healthy
        
        Returns:
            True if available, False otherwise
        """
        try:
            # Check if Ollama is running by listing models
            response = await self.client.get(
                f"{self.base_url.rstrip('/api')}/api/tags",
                timeout=5.0
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"Ollama health check failed: {e}")
            return False
    
    def supports_vision(self) -> bool:
        """
        Check if Ollama supports vision models
        
        Returns:
            True (Ollama supports vision via llava and similar models)
        """
        return True
    
    def get_name(self) -> str:
        """
        Get provider name
        
        Returns:
            "ollama"
        """
        return "ollama"
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

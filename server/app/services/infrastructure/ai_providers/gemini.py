"""
Google Gemini AI Provider Implementation
Multimodal AI with native vision support
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


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI provider implementation
    Uses Google AI API format with native multimodal support
    Supports multiple API keys with automatic rotation
    """
    
    def __init__(self, api_key: str, base_url: str, model: str, vision_model: Optional[str] = None):
        """
        Initialize Gemini provider
        
        Args:
            api_key: Google AI API key(s) - comma-separated for multiple keys
            base_url: Gemini API base URL
            model: Default model (e.g., gemini-1.5-flash)
            vision_model: Vision model (Gemini models support vision natively)
        """
        super().__init__(api_key, base_url, model, vision_model or model)
        
        # Parse multiple keys
        self.api_keys = [k.strip() for k in api_key.split(",") if k.strip()]
        self.current_key_index = 0
        
        # Create client with first key
        self.client = httpx.AsyncClient(
            params={"key": self.api_keys[0]},
            timeout=30.0
        )
        logger.info(f"Initialized Gemini provider with model {self.model} and {len(self.api_keys)} API key(s)")
    
    def _rotate_key(self):
        """Rotate to next API key"""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            # Recreate client with new key
            self.client = httpx.AsyncClient(
                params={"key": self.api_keys[self.current_key_index]},
                timeout=30.0
            )
            logger.info(f"Rotated to Gemini API key {self.current_key_index + 1}/{len(self.api_keys)}")
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Convert OpenAI-style messages to Gemini format
        
        Args:
            messages: OpenAI-style messages
            
        Returns:
            Gemini-formatted messages
        """
        gemini_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Convert role mapping
            if role == "system":
                # Gemini doesn't have system role, prepend to first user message
                if gemini_messages and gemini_messages[-1]["role"] == "user":
                    gemini_messages[-1]["parts"][0]["text"] = f"{content}\n\n{gemini_messages[-1]['parts'][0]['text']}"
                else:
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": content}]
                    })
            elif role == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
            else:  # user
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
        
        return gemini_messages
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send chat completion request to Gemini with automatic key rotation
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to self.model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
            
        Raises:
            QuotaExceededException: If all keys quota exhausted
            RateLimitException: If rate limit exceeded on all keys
            ProviderException: For other errors
        """
        model = model or self.model
        
        # Convert messages to Gemini format
        gemini_messages = self._convert_messages_to_gemini_format(messages)
        
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or 2048  # Default to 2048 tokens if not specified
            }
        }
        
        # Try all keys
        last_error = None
        tried_keys = 0
        
        while tried_keys < len(self.api_keys):
            try:
                logger.debug(f"Sending chat completion request to Gemini with model {model} (key {self.current_key_index + 1}/{len(self.api_keys)})")
                
                response = await self.client.post(
                    f"{self.base_url}/models/{model}:generateContent",
                    json=payload
                )
                
                # Check for errors
                if response.status_code == 429:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                    logger.warning(f"Gemini rate limit exceeded on key {self.current_key_index + 1}: {error_msg}")
                    self._rotate_key()
                    tried_keys += 1
                    last_error = RateLimitException(f"Gemini rate limit: {error_msg}")
                    continue
                
                if response.status_code == 403 or response.status_code == 400:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("error", {}).get("message", "API key invalid or quota exceeded")
                    logger.warning(f"Gemini key {self.current_key_index + 1} error: {error_msg}")
                    self._rotate_key()
                    tried_keys += 1
                    last_error = QuotaExceededException(f"Gemini quota exceeded: {error_msg}")
                    continue
                
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    logger.error(f"Gemini API error: {error_msg}")
                    raise ProviderException(f"Gemini API error: {error_msg}")
                
                # Parse Gemini response format
                data = response.json()
                
                if "candidates" not in data or len(data["candidates"]) == 0:
                    raise ProviderException("Gemini returned empty response")
                
                candidate = data["candidates"][0]
                
                if "content" not in candidate or "parts" not in candidate["content"]:
                    raise ProviderException("Gemini response missing content")
                
                parts = candidate["content"]["parts"]
                if len(parts) == 0 or "text" not in parts[0]:
                    raise ProviderException("Gemini response missing text")
                
                content = parts[0]["text"]
                
                logger.debug(f"Gemini chat completion successful, generated {len(content)} characters")
                return content
                
            except (QuotaExceededException, RateLimitException) as e:
                last_error = e
                tried_keys += 1
                continue
            except httpx.TimeoutException:
                logger.error("Gemini request timeout")
                raise ProviderException("Gemini request timeout")
            except httpx.RequestError as e:
                logger.error(f"Gemini request error: {e}")
                raise ProviderException(f"Gemini request error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected Gemini error: {e}")
                raise ProviderException(f"Unexpected Gemini error: {str(e)}")
        
        # All keys exhausted
        if last_error:
            raise last_error
        raise ProviderException("All Gemini API keys exhausted")
    
    async def vision_completion(
        self,
        prompt: str,
        image_data: bytes,
        model: Optional[str] = None
    ) -> str:
        """
        Send vision-based completion request to Gemini
        
        Args:
            prompt: Text prompt for image analysis
            image_data: Image bytes
            model: Vision model to use
            
        Returns:
            Generated text response from image analysis
            
        Raises:
            QuotaExceededException: If quota/credits exhausted
            RateLimitException: If rate limit exceeded
            ProviderException: For other errors
        """
        model = model or self.vision_model
        
        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Detect image format
        image_format = "image/jpeg"  # Default
        if image_data.startswith(b'\x89PNG'):
            image_format = "image/png"
        elif image_data.startswith(b'GIF'):
            image_format = "image/gif"
        elif image_data.startswith(b'\xff\xd8'):
            image_format = "image/jpeg"
        
        # Gemini multimodal format
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": image_format,
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1
            }
        }
        
        try:
            logger.debug(f"Sending vision completion request to Gemini with model {model}")
            
            response = await self.client.post(
                f"{self.base_url}/models/{model}:generateContent",
                json=payload
            )
            
            # Check for errors (same as chat_completion)
            if response.status_code == 429:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                raise RateLimitException(f"Gemini rate limit: {error_msg}")
            
            if response.status_code == 403:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", "Quota exceeded")
                raise QuotaExceededException(f"Gemini quota exceeded: {error_msg}")
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                raise ProviderException(f"Gemini vision API error: {error_msg}")
            
            # Parse response
            data = response.json()
            
            if "candidates" not in data or len(data["candidates"]) == 0:
                raise ProviderException("Gemini vision returned empty response")
            
            candidate = data["candidates"][0]
            
            if "content" not in candidate or "parts" not in candidate["content"]:
                raise ProviderException("Gemini vision response missing content")
            
            parts = candidate["content"]["parts"]
            if len(parts) == 0 or "text" not in parts[0]:
                raise ProviderException("Gemini vision response missing text")
            
            content = parts[0]["text"]
            
            logger.debug(f"Gemini vision completion successful")
            return content
            
        except (QuotaExceededException, RateLimitException):
            raise
        except Exception as e:
            logger.error(f"Gemini vision error: {e}")
            raise ProviderException(f"Gemini vision error: {str(e)}")
    
    async def check_health(self) -> bool:
        """
        Check if Gemini is available and healthy
        
        Returns:
            True if available, False otherwise
        """
        try:
            # Just check if we can reach the API endpoint (don't send actual request to save quota)
            # Use models list endpoint which is free
            response = await self.client.get(
                f"{self.base_url}/models",
                timeout=10.0
            )
            
            # 200 = OK, 400/401 = API key issue but server reachable
            return response.status_code in [200, 400, 401]
            
        except Exception as e:
            logger.debug(f"Gemini health check failed: {e}")
            return False
    
    def supports_vision(self) -> bool:
        """
        Check if Gemini supports vision models
        
        Returns:
            True (Gemini models support vision natively)
        """
        return True
    
    def get_name(self) -> str:
        """
        Get provider name
        
        Returns:
            "gemini"
        """
        return "gemini"
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
"""
Ollama client for local LLM/embedding/vision
"""
import json
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.llm_model = settings.OLLAMA_LLM_MODEL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        self.vision_model = settings.OLLAMA_VISION_MODEL
        
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Chat completion with Ollama"""
        if not model:
            model = self.llm_model
            
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
            
    async def embed(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings with Ollama"""
        if not model:
            model = self.embed_model
            
        embeddings = []
        
        async with httpx.AsyncClient() as client:
            for text in texts:
                payload = {
                    "model": model,
                    "prompt": text
                }
                
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                embeddings.append(result["embedding"])
                
        return embeddings
        
    async def vision_chat(
        self,
        prompt: str,
        image_data: str,  # base64 encoded
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Vision chat with Ollama"""
        if not model:
            model = self.vision_model
            
        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_data]
            }
        ]
        
        return await self.chat(messages, model)


async def check_ollama_connection() -> bool:
    """Check if Ollama is reachable"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.OLLAMA_BASE_URL.rstrip('/api')}/api/tags",
                timeout=5.0
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama connection check failed: {e}")
        return False


# Global client instance
ollama_client = OllamaClient()
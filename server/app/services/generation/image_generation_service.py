"""
Dịch vụ Tạo Ảnh với nhiều nhà cung cấp MIỄN PHÍ.

Các nhà cung cấp được xếp hạng theo chất lượng (mạnh nhất đến yếu nhất):
1. Together.ai (FLUX.1-schnell) - Gói MIỄN PHÍ, chất lượng cao, nhanh
2. Pollinations.ai (FLUX) - 100% MIỄN PHÍ, không cần API key, không giới hạn
3. Hugging Face (Stable Diffusion XL) - Gói MIỄN PHÍ, chất lượng tốt
4. Cloud Code (Imagen-3) - Miễn phí qua tài khoản Google Cloud Code
5. Stability AI (Stable Diffusion) - Có gói MIỄN PHÍ
6. Google AI Studio (Gemini) - Gói miễn phí với giới hạn hàng ngày
"""
import asyncio
import base64
import logging
import time
import urllib.parse
import re
from dataclasses import dataclass
from typing import Optional, List

import httpx

from app.core.config import settings
from app.services.auth.api_key_service import get_key_manager

logger = logging.getLogger(__name__)


@dataclass
class ImageGenerationResult:
    """Kết quả từ việc tạo ảnh."""
    success: bool
    images: List[str]  # Ảnh được mã hóa Base64
    prompt: str
    model: str
    provider: str
    error: Optional[str] = None
    processing_time_ms: int = 0


class ImageGenerationService:
    """
    Dịch vụ tạo ảnh sử dụng nhiều nhà cung cấp AI MIỄN PHÍ.
    
    Các nhà cung cấp được thử theo thứ tự chất lượng (mạnh nhất đến yếu nhất):
    1. Together.ai - FLUX.1-schnell (Gói MIỄN PHÍ: 60 yêu cầu/phút)
    2. Pollinations.ai - FLUX (100% MIỄN PHÍ, không giới hạn)
    3. Hugging Face - SDXL (Có gói MIỄN PHÍ)
    4. Cloud Code - Imagen-3 (Miễn phí qua tài khoản)
    5. Stability AI - SD (Có gói MIỄN PHÍ)
    6. Google AI Studio - Gemini (Gói miễn phí có giới hạn)
    """
    
    # Các điểm cuối API
    TOGETHER_API_URL = "https://api.together.xyz/v1/images/generations"
    HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    STABILITY_API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image"
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
    
    # Cài đặt mặc định
    DEFAULT_ASPECT_RATIO = "1:1"
    DEFAULT_NUM_IMAGES = 1
    ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9"]
    
    def __init__(self):
        self.key_manager = get_key_manager()
    
    def _get_dimensions(self, aspect_ratio: str) -> tuple:
        """Chuyển đổi tỷ lệ khung hình sang chiều rộng/chiều cao."""
        dimensions = {
            "1:1": (1024, 1024),
            "3:4": (768, 1024),
            "4:3": (1024, 768),
            "9:16": (576, 1024),
            "16:9": (1024, 576),
        }
        return dimensions.get(aspect_ratio, (1024, 1024))
    
    async def generate(
        self,
        prompt: str,
        num_images: int = 1,
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None,
        preferred_provider: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Tạo ảnh từ mô tả văn bản sử dụng nhà cung cấp tốt nhất có sẵn.
        
        Args:
            prompt: Mô tả văn bản của ảnh
            num_images: Số lượng ảnh (1-4)
            aspect_ratio: Tỷ lệ khung hình (1:1, 3:4, 4:3, 9:16, 16:9)
            negative_prompt: Những gì cần tránh
            preferred_provider: Chỉ định nhà cung cấp cụ thể (tùy chọn)
            
        Returns:
            ImageGenerationResult với ảnh được mã hóa base64
        """
        start_time = time.time()
        num_images = max(1, min(4, num_images))
        if aspect_ratio not in self.ASPECT_RATIOS:
            aspect_ratio = self.DEFAULT_ASPECT_RATIO
        
        width, height = self._get_dimensions(aspect_ratio)
        errors = []
        
        # Định nghĩa thứ tự nhà cung cấp (mạnh nhất đến yếu nhất)
        providers = [
            ("together", self._generate_with_together),
            ("pollinations", self._generate_with_pollinations),
            ("huggingface", self._generate_with_huggingface),
            ("cloudcode", self._generate_with_cloudcode),
            ("stability", self._generate_with_stability),
            ("gemini", self._generate_with_gemini),
        ]
        
        # Nếu chỉ định nhà cung cấp ưu tiên, thử nó trước
        if preferred_provider:
            providers = sorted(providers, key=lambda x: 0 if x[0] == preferred_provider else 1)
        
        for provider_name, provider_func in providers:
            logger.info(f"Trying {provider_name} for image generation...")
            
            try:
                result = await provider_func(
                    prompt=prompt,
                    width=width,
                    height=height,
                    negative_prompt=negative_prompt,
                )
                
                if result.success:
                    result.processing_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"✅ {provider_name} succeeded in {result.processing_time_ms}ms")
                    return result
                else:
                    errors.append(f"{provider_name}: {result.error}")
                    logger.info(f"❌ {provider_name} failed: {result.error}")
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")
                logger.warning(f"❌ {provider_name} exception: {e}")
        
        # Tất cả nhà cung cấp đều thất bại
        return ImageGenerationResult(
            success=False,
            images=[],
            prompt=prompt,
            model="none",
            provider="none",
            error=f"Tất cả nhà cung cấp đều thất bại:\n" + "\n".join(errors),
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
    
    # =========================================================================
    # NHÀ CUNG CẤP 1: Together.ai (FLUX.1-schnell) - MIỄN PHÍ MẠNH NHẤT
    # =========================================================================
    async def _generate_with_together(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Together.ai - mô hình FLUX.1-schnell.
        Gói MIỄN PHÍ: 60 yêu cầu/phút, chất lượng cao.
        Lấy API key: https://api.together.xyz/
        """
        api_key = self.key_manager.get_key("together")
        
        if not api_key:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="flux-schnell", provider="together",
                error="No Together.ai API key. Get free key at https://api.together.xyz/",
            )
        
        try:
            payload = {
                "model": "black-forest-labs/FLUX.1-schnell-Free",
                "prompt": prompt,
                "width": width,
                "height": height,
                "steps": 4,
                "n": 1,
                "response_format": "b64_json",
            }
            
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOGETHER_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    images = [img["b64_json"] for img in data.get("data", []) if "b64_json" in img]
                    
                    if images:
                        self.key_manager.mark_success("together", api_key)
                        return ImageGenerationResult(
                            success=True, images=images, prompt=prompt,
                            model="FLUX.1-schnell", provider="together",
                        )
                
                error_msg = f"HTTP {response.status_code}"
                if response.status_code in [401, 429]:
                    self.key_manager.mark_error("together", api_key, error_msg, 60)
                
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="FLUX.1-schnell", provider="together",
                    error=error_msg,
                )
                
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="FLUX.1-schnell", provider="together",
                error=str(e),
            )
    
    # =========================================================================
    # NHÀ CUNG CẤP 2: Pollinations.ai (FLUX) - 100% MIỄN PHÍ, KHÔNG CẦN API KEY
    # =========================================================================
    async def _generate_with_pollinations(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Pollinations.ai - 100% MIỄN PHÍ, không cần API key, không giới hạn.
        Các mô hình: flux, flux-realism, flux-anime, flux-3d, turbo
        """
        try:
            encoded_prompt = urllib.parse.quote(prompt)
            # Các mô hình có sẵn: flux, flux-realism, flux-anime, flux-3d, turbo, any-dark
            model = "flux"
            
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model={model}&nologo=true&enhance=true"
            
            if negative_prompt:
                url += f"&negative={urllib.parse.quote(negative_prompt)}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=120.0, follow_redirects=True)
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        image_base64 = base64.b64encode(response.content).decode("utf-8")
                        return ImageGenerationResult(
                            success=True, images=[image_base64], prompt=prompt,
                            model="FLUX", provider="pollinations",
                        )
                
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="FLUX", provider="pollinations",
                    error=f"HTTP {response.status_code}",
                )
                
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="FLUX", provider="pollinations",
                error=str(e),
            )
    
    # =========================================================================
    # NHÀ CUNG CẤP 3: Hugging Face (SDXL) - GÓI MIỄN PHÍ
    # =========================================================================
    async def _generate_with_huggingface(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Hugging Face Inference API - Stable Diffusion XL.
        Có gói MIỄN PHÍ. Lấy token: https://huggingface.co/settings/tokens
        """
        api_key = self.key_manager.get_key("huggingface")
        
        if not api_key:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="SDXL", provider="huggingface",
                error="No Hugging Face token. Get free at https://huggingface.co/settings/tokens",
            )
        
        try:
            payload = {"inputs": prompt}
            if negative_prompt:
                payload["parameters"] = {"negative_prompt": negative_prompt}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.HUGGINGFACE_API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                    timeout=120.0,
                )
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        image_base64 = base64.b64encode(response.content).decode("utf-8")
                        self.key_manager.mark_success("huggingface", api_key)
                        return ImageGenerationResult(
                            success=True, images=[image_base64], prompt=prompt,
                            model="SDXL", provider="huggingface",
                        )
                
                error_msg = f"HTTP {response.status_code}"
                if response.status_code in [401, 429, 503]:
                    self.key_manager.mark_error("huggingface", api_key, error_msg, 60)
                
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="SDXL", provider="huggingface",
                    error=error_msg,
                )
                
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="SDXL", provider="huggingface",
                error=str(e),
            )
    
    # =========================================================================
    # NHÀ CUNG CẤP 4: Cloud Code (Imagen-3) - MIỄN PHÍ QUA TÀI KHOẢN
    # =========================================================================
    async def _generate_with_cloudcode(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """Cloud Code API với mô hình Imagen-3."""
        try:
            from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
            manager = get_cloudcode_manager()
            
            if not manager or not manager.list_accounts():
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="imagen-3", provider="cloudcode",
                    error="No Cloud Code accounts available",
                )
            
            # Thử tạo ảnh gốc với imagen-3
            response = await manager.generate_image(prompt=prompt, num_images=1)
            
            if response and response.get("success") and response.get("images"):
                return ImageGenerationResult(
                    success=True,
                    images=response["images"],
                    prompt=prompt,
                    model=response.get("model", "imagen-3"),
                    provider="cloudcode",
                )
            
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="imagen-3", provider="cloudcode",
                error=response.get("error", "Image generation failed") if response else "No response",
            )
            
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="imagen-3", provider="cloudcode",
                error=str(e),
            )
    
    # =========================================================================
    # NHÀ CUNG CẤP 5: Stability AI (Stable Diffusion) - GÓI MIỄN PHÍ
    # =========================================================================
    async def _generate_with_stability(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Stability AI - Stable Diffusion.
        Gói MIỄN PHÍ: 25 credits. Lấy key: https://platform.stability.ai/
        """
        api_key = self.key_manager.get_key("stability")
        
        if not api_key:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="stable-diffusion", provider="stability",
                error="No Stability AI key. Get free at https://platform.stability.ai/",
            )
        
        try:
            # Stability yêu cầu kích thước cụ thể
            valid_dims = [(512, 512), (768, 768), (1024, 1024), (512, 768), (768, 512)]
            if (width, height) not in valid_dims:
                width, height = 1024, 1024
            
            payload = {
                "text_prompts": [{"text": prompt, "weight": 1}],
                "cfg_scale": 7,
                "height": height,
                "width": width,
                "samples": 1,
                "steps": 30,
            }
            
            if negative_prompt:
                payload["text_prompts"].append({"text": negative_prompt, "weight": -1})
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.STABILITY_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    images = [art["base64"] for art in data.get("artifacts", []) if "base64" in art]
                    
                    if images:
                        self.key_manager.mark_success("stability", api_key)
                        return ImageGenerationResult(
                            success=True, images=images, prompt=prompt,
                            model="stable-diffusion-v1.6", provider="stability",
                        )
                
                error_msg = f"HTTP {response.status_code}"
                if response.status_code in [401, 402, 429]:
                    self.key_manager.mark_error("stability", api_key, error_msg, 300)
                
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="stable-diffusion", provider="stability",
                    error=error_msg,
                )
                
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="stable-diffusion", provider="stability",
                error=str(e),
            )
    
    # =========================================================================
    # NHÀ CUNG CẤP 6: Google AI Studio (Gemini) - GÓI MIỄN PHÍ
    # =========================================================================
    async def _generate_with_gemini(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: Optional[str] = None,
    ) -> ImageGenerationResult:
        """
        Google AI Studio - Gemini với tạo ảnh.
        Gói MIỄN PHÍ: 50 ảnh/ngày. Lấy key: https://aistudio.google.com/
        """
        api_key = self.key_manager.get_key("gemini")
        
        if not api_key:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="gemini-2.0-flash", provider="gemini",
                error="No Gemini API key. Get free at https://aistudio.google.com/",
            )
        
        try:
            payload = {
                "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.GEMINI_API_URL,
                    params={"key": api_key},
                    json=payload,
                    timeout=120.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    images = []
                    
                    for candidate in data.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if "inlineData" in part:
                                inline = part["inlineData"]
                                if inline.get("mimeType", "").startswith("image/"):
                                    images.append(inline.get("data", ""))
                    
                    if images:
                        self.key_manager.mark_success("gemini", api_key)
                        return ImageGenerationResult(
                            success=True, images=images, prompt=prompt,
                            model="gemini-2.0-flash", provider="gemini",
                        )
                
                error_msg = f"HTTP {response.status_code}"
                if response.status_code in [401, 429]:
                    self.key_manager.mark_error("gemini", api_key, error_msg, 300)
                
                return ImageGenerationResult(
                    success=False, images=[], prompt=prompt,
                    model="gemini-2.0-flash", provider="gemini",
                    error=error_msg,
                )
                
        except Exception as e:
            return ImageGenerationResult(
                success=False, images=[], prompt=prompt,
                model="gemini-2.0-flash", provider="gemini",
                error=str(e),
            )
    
    def get_supported_models(self) -> List[dict]:
        """Lấy danh sách các mô hình tạo ảnh được hỗ trợ (xếp hạng theo chất lượng)."""
        return [
            {
                "id": "flux-schnell",
                "name": "FLUX.1-schnell (Together.ai)",
                "provider": "together",
                "description": "🥇 Strongest FREE model - High quality, fast",
                "free_tier": "60 req/min FREE",
                "quality": 95,
                "speed": "fast",
                "api_key_required": True,
                "api_key_url": "https://api.together.xyz/",
            },
            {
                "id": "flux",
                "name": "FLUX (Pollinations.ai)",
                "provider": "pollinations",
                "description": "🥈 100% FREE, no API key, unlimited",
                "free_tier": "Unlimited (completely free)",
                "quality": 90,
                "speed": "medium",
                "api_key_required": False,
            },
            {
                "id": "sdxl",
                "name": "Stable Diffusion XL (Hugging Face)",
                "provider": "huggingface",
                "description": "🥉 Good quality, free tier available",
                "free_tier": "Free tier with rate limits",
                "quality": 85,
                "speed": "medium",
                "api_key_required": True,
                "api_key_url": "https://huggingface.co/settings/tokens",
            },
            {
                "id": "imagen-3",
                "name": "Imagen 3 (Cloud Code)",
                "provider": "cloudcode",
                "description": "Google's Imagen via Cloud Code accounts",
                "free_tier": "Free via Cloud Code",
                "quality": 88,
                "speed": "medium",
                "api_key_required": False,
            },
            {
                "id": "stable-diffusion",
                "name": "Stable Diffusion (Stability AI)",
                "provider": "stability",
                "description": "Original SD model, 25 free credits",
                "free_tier": "25 credits FREE",
                "quality": 80,
                "speed": "slow",
                "api_key_required": True,
                "api_key_url": "https://platform.stability.ai/",
            },
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash (Google)",
                "provider": "gemini",
                "description": "Google's multimodal model",
                "free_tier": "50 images/day FREE",
                "quality": 75,
                "speed": "fast",
                "api_key_required": True,
                "api_key_url": "https://aistudio.google.com/",
            },
        ]


# Instance singleton
_image_service: Optional[ImageGenerationService] = None


def get_image_generation_service() -> ImageGenerationService:
    """Lấy instance dịch vụ tạo ảnh."""
    global _image_service
    if _image_service is None:
        _image_service = ImageGenerationService()
    return _image_service

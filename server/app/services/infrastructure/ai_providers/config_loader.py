"""
Configuration loader for AI providers
"""
import logging
from typing import Dict, List
from pathlib import Path
from app.core.config import settings
from app.models.enums import ProviderConfig, ProviderName

logger = logging.getLogger(__name__)


class AIProviderConfigLoader:
    """Loads and validates AI provider configurations"""
    
    @staticmethod
    def load_provider_configs() -> List[ProviderConfig]:
        """
        Load all provider configurations from environment variables
        
        Returns:
            List of ProviderConfig objects sorted by priority
        """
        configs = []
        
        # Parse priority string (e.g., "cloudcode:0,groq:1,deepseek:2,gemini:3,ollama:4")
        priorities = AIProviderConfigLoader._parse_priorities(settings.AI_PROVIDER_PRIORITY)
        
        # Load Cloud Code config (FREE Claude/Gemini - STRONGEST)
        # Cloud Code doesn't need API key - uses OAuth accounts from storage
        cloudcode_accounts_dir = Path(settings.STORAGE_DIR) / "cloudcode_accounts"
        if cloudcode_accounts_dir.exists() and any(cloudcode_accounts_dir.glob("*.json")):
            configs.append(ProviderConfig(
                name=ProviderName.CLOUDCODE,
                enabled=True,
                api_key="",  # Not needed
                base_url="",  # Not needed
                model="claude-sonnet-4-5",  # Default to strongest
                vision_model="gemini-3-pro-high",
                priority=priorities.get(ProviderName.CLOUDCODE, 0),  # Highest priority
                timeout_seconds=settings.AI_ENHANCEMENT_TIMEOUT,
                max_retries=settings.AI_ENHANCEMENT_MAX_RETRIES
            ))
            logger.info(f"Loaded Cloud Code provider config with priority {priorities.get(ProviderName.CLOUDCODE, 0)}")
        else:
            logger.info("Cloud Code accounts not found, skipping (add via /api/v1/cloudcode/accounts)")
        
        # Load Groq config
        if settings.GROQ_API_KEY:
            configs.append(ProviderConfig(
                name=ProviderName.GROQ,
                enabled=True,
                api_key=settings.GROQ_API_KEY,
                base_url=settings.GROQ_BASE_URL,
                model=settings.GROQ_MODEL,
                vision_model=settings.GROQ_VISION_MODEL,
                priority=priorities.get(ProviderName.GROQ, 1),
                timeout_seconds=settings.AI_ENHANCEMENT_TIMEOUT,
                max_retries=settings.AI_ENHANCEMENT_MAX_RETRIES
            ))
            logger.info(f"Loaded Groq provider config with priority {priorities.get(ProviderName.GROQ, 1)}")
        else:
            logger.warning("Groq API key not configured, skipping Groq provider")
        
        # Load DeepSeek config
        if settings.DEEPSEEK_API_KEY:
            configs.append(ProviderConfig(
                name=ProviderName.DEEPSEEK,
                enabled=True,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                model=settings.DEEPSEEK_MODEL,
                vision_model=None,  # DeepSeek doesn't have vision yet
                priority=priorities.get(ProviderName.DEEPSEEK, 2),
                timeout_seconds=settings.AI_ENHANCEMENT_TIMEOUT,
                max_retries=settings.AI_ENHANCEMENT_MAX_RETRIES
            ))
            logger.info(f"Loaded DeepSeek provider config with priority {priorities.get(ProviderName.DEEPSEEK, 2)}")
        else:
            logger.warning("DeepSeek API key not configured, skipping DeepSeek provider")
        
        # Load Gemini config
        if settings.GEMINI_API_KEY:
            configs.append(ProviderConfig(
                name=ProviderName.GEMINI,
                enabled=True,
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
                model=settings.GEMINI_MODEL,
                vision_model=settings.GEMINI_MODEL,  # Gemini models support vision natively
                priority=priorities.get(ProviderName.GEMINI, 3),
                timeout_seconds=settings.AI_ENHANCEMENT_TIMEOUT,
                max_retries=settings.AI_ENHANCEMENT_MAX_RETRIES
            ))
            logger.info(f"Loaded Gemini provider config with priority {priorities.get(ProviderName.GEMINI, 3)}")
        else:
            logger.warning("Gemini API key not configured, skipping Gemini provider")
        
        # Load Ollama config (always available for local use)
        configs.append(ProviderConfig(
            name=ProviderName.OLLAMA,
            enabled=True,
            api_key="",  # Ollama doesn't need API key
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_LLM_MODEL,
            vision_model=settings.OLLAMA_VISION_MODEL,
            priority=priorities.get(ProviderName.OLLAMA, 4),
            timeout_seconds=settings.AI_ENHANCEMENT_TIMEOUT,
            max_retries=settings.AI_ENHANCEMENT_MAX_RETRIES
        ))
        logger.info(f"Loaded Ollama provider config with priority {priorities.get(ProviderName.OLLAMA, 4)}")
        
        # Sort by priority (lower number = higher priority)
        configs.sort(key=lambda x: x.priority)
        
        logger.info(f"Loaded {len(configs)} provider configurations")
        return configs
    
    @staticmethod
    def _parse_priorities(priority_string: str) -> Dict[str, int]:
        """
        Parse priority string into dict
        
        Args:
            priority_string: String like "groq:1,deepseek:2,gemini:3,ollama:4"
            
        Returns:
            Dict mapping provider name to priority number
        """
        priorities = {}
        
        try:
            for pair in priority_string.split(','):
                pair = pair.strip()
                if ':' in pair:
                    name, priority = pair.split(':')
                    priorities[name.strip()] = int(priority.strip())
        except Exception as e:
            logger.error(f"Error parsing provider priorities: {e}")
            # Return defaults - Cloud Code first (strongest & free)
            return {
                ProviderName.CLOUDCODE: 0,
                ProviderName.GROQ: 1,
                ProviderName.DEEPSEEK: 2,
                ProviderName.GEMINI: 3,
                ProviderName.OLLAMA: 4
            }
        
        return priorities
    
    @staticmethod
    def validate_config(config: ProviderConfig) -> bool:
        """
        Validate a provider configuration
        
        Args:
            config: ProviderConfig to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not config.name:
            logger.warning(f"Provider config missing name")
            return False
        
        # Cloud Code doesn't need base_url or api_key
        if config.name == ProviderName.CLOUDCODE:
            if not config.model:
                logger.warning(f"Provider {config.name} missing model")
                return False
            logger.debug(f"Provider {config.name} configuration is valid (Cloud Code)")
            return True
        
        if not config.base_url:
            logger.warning(f"Provider {config.name} missing base_url")
            return False
        
        if not config.model:
            logger.warning(f"Provider {config.name} missing model")
            return False
        
        # Check API key for cloud providers
        if config.name in [ProviderName.GROQ, ProviderName.DEEPSEEK, ProviderName.GEMINI]:
            if not config.api_key:
                logger.warning(f"Provider {config.name} missing API key")
                return False
        
        logger.debug(f"Provider {config.name} configuration is valid")
        return True

"""
Prompt Manager for RAGAnything

Handles loading and switching between different prompt sets (languages, versions).
Ported from upstream RAGAnything v1.2.10.
"""

import logging
from typing import Any, Dict, Optional
from .prompts import PROMPTS

logger = logging.getLogger(__name__)

class PromptManager:
    """Manages the lifecycle and language switching of prompts."""
    
    def __init__(self):
        self.current_language = "en"
        self._registries = {}
        
    def register_language(self, lang_code: str, prompts: Dict[str, Any]):
        """Register a set of prompts for a specific language."""
        self._registries[lang_code] = prompts
        logger.debug(f"Registered prompts for language: {lang_code}")
        
    def switch_language(self, lang_code: str) -> bool:
        """
        Switch the global PROMPTS registry to a different language.
        
        Args:
            lang_code: The ISO language code (e.g., 'en', 'zh').
            
        Returns:
            True if switch was successful, False otherwise.
        """
        if lang_code not in self._registries:
            logger.warning(f"Language {lang_code} not registered. Staying on {self.current_language}")
            return False
            
        PROMPTS.swap(self._registries[lang_code])
        self.current_language = lang_code
        logger.info(f"Switched RAGAnything prompts to: {lang_code}")
        return True

    def get_current_language(self) -> str:
        """Return the currently active language code."""
        return self.current_language

# Global instance
prompt_manager = PromptManager()

def initialize_prompts(lang_code: str = "en"):
    """
    Initialize prompts with a default language.
    Registers the base English prompts automatically.
    """
    # Register base English prompts which are already in PROMPTS
    prompt_manager.register_language("en", PROMPTS.snapshot())
    
    # Switch to requested language if not English
    if lang_code != "en":
        prompt_manager.switch_language(lang_code)

__all__ = ["PromptManager", "prompt_manager", "initialize_prompts"]

"""
Multimodal Content Processors

Processors for analyzing multimodal content:
- ContextExtractor: Extract surrounding context for better understanding
- ImageModalProcessor: Vision model analysis of images
- TableModalProcessor: Structured data extraction from tables
- EquationModalProcessor: Mathematical formula analysis
- GenericModalProcessor: Flexible content analysis
"""

import re
import json
import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

from app.services.rag_patterns.pipeline.types import ContentType, ModalContent
from app.services.rag_patterns.pipeline.config import RAGConfig
from app.services.rag_patterns.pipeline.prompts import PROMPTS

logger = logging.getLogger(__name__)


def compute_hash_id(content: str, prefix: str = "") -> str:
    """Compute a hash-based ID for content."""
    hash_obj = hashlib.md5(content.encode('utf-8'))
    return f"{prefix}{hash_obj.hexdigest()[:16]}"


# ============================================================================
# CONTEXT EXTRACTION
# ============================================================================

@dataclass
class ContextConfig:
    """Configuration for context extraction."""
    
    context_window: int = 1
    context_mode: str = "page"  # "page", "chunk", "token"
    max_context_tokens: int = 2000
    include_headers: bool = True
    include_captions: bool = True
    filter_content_types: List[str] = None
    
    def __post_init__(self):
        if self.filter_content_types is None:
            self.filter_content_types = ["text"]


class ContextExtractor:
    """
    Universal context extractor for multimodal content.
    
    Extracts surrounding context from various content sources to provide
    better understanding for multimodal content processing.
    """
    
    def __init__(self, config: Optional[ContextConfig] = None, tokenizer=None):
        self.config = config or ContextConfig()
        self.tokenizer = tokenizer
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def extract_context(
        self,
        content_source: Any,
        current_item_info: Dict[str, Any],
        content_format: str = "auto",
    ) -> str:
        """
        Extract context for current item from content source.
        
        Args:
            content_source: Source content (list, dict, or string)
            current_item_info: Information about current item
            content_format: Format hint ("minerU", "text_chunks", "auto")
        
        Returns:
            Extracted context text
        """
        if not content_source or not self.config.context_window:
            return ""
        
        try:
            if content_format == "minerU" and isinstance(content_source, list):
                return self._extract_from_content_list(content_source, current_item_info)
            elif content_format == "text_chunks" and isinstance(content_source, list):
                return self._extract_from_text_chunks(content_source, current_item_info)
            elif content_format == "text" and isinstance(content_source, str):
                return self._extract_from_text_source(content_source, current_item_info)
            else:
                if isinstance(content_source, list):
                    return self._extract_from_content_list(content_source, current_item_info)
                elif isinstance(content_source, dict):
                    return self._extract_from_dict_source(content_source, current_item_info)
                elif isinstance(content_source, str):
                    return self._extract_from_text_source(content_source, current_item_info)
                else:
                    self.logger.warning(f"Unsupported content source type: {type(content_source)}")
                    return ""
        except Exception as e:
            self.logger.error(f"Error extracting context: {e}")
            return ""
    
    def _extract_from_content_list(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        if self.config.context_mode == "page":
            return self._extract_page_context(content_list, current_item_info)
        elif self.config.context_mode == "chunk":
            return self._extract_chunk_context(content_list, current_item_info)
        else:
            return self._extract_page_context(content_list, current_item_info)
    
    def _extract_page_context(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        current_page = current_item_info.get("page_idx", 0)
        window_size = self.config.context_window
        
        start_page = max(0, current_page - window_size)
        end_page = current_page + window_size + 1
        
        context_texts = []
        
        for item in content_list:
            item_page = item.get("page_idx", 0)
            item_type = item.get("type", "")
            
            if (start_page <= item_page < end_page and 
                item_type in self.config.filter_content_types):
                text_content = self._extract_text_from_item(item)
                if text_content and text_content.strip():
                    if item_page != current_page:
                        context_texts.append(f"[Page {item_page}] {text_content}")
                    else:
                        context_texts.append(text_content)
        
        context = "\n".join(context_texts)
        return self._truncate_context(context)
    
    def _extract_chunk_context(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        current_index = current_item_info.get("index", 0)
        window_size = self.config.context_window
        
        start_idx = max(0, current_index - window_size)
        end_idx = min(len(content_list), current_index + window_size + 1)
        
        context_texts = []
        
        for i in range(start_idx, end_idx):
            if i != current_index:
                item = content_list[i]
                item_type = item.get("type", "")
                
                if item_type in self.config.filter_content_types:
                    text_content = self._extract_text_from_item(item)
                    if text_content and text_content.strip():
                        context_texts.append(text_content)
        
        context = "\n".join(context_texts)
        return self._truncate_context(context)
    
    def _extract_text_from_item(self, item: Dict) -> str:
        item_type = item.get("type", "")
        
        if item_type == "text":
            text = item.get("text", "")
            text_level = item.get("text_level", 0)
            
            if self.config.include_headers and text_level > 0:
                return f"{'#' * text_level} {text}"
            return text
        
        elif item_type == "image" and self.config.include_captions:
            captions = item.get("image_caption", item.get("img_caption", []))
            if captions:
                if isinstance(captions, list):
                    return f"[Image: {', '.join(captions)}]"
                return f"[Image: {captions}]"
        
        elif item_type == "table" and self.config.include_captions:
            captions = item.get("table_caption", [])
            if captions:
                if isinstance(captions, list):
                    return f"[Table: {', '.join(captions)}]"
                return f"[Table: {captions}]"
        
        return ""
    
    def _extract_from_dict_source(
        self, dict_source: Dict, current_item_info: Dict
    ) -> str:
        if "content" in dict_source:
            context = str(dict_source["content"])
        elif "text" in dict_source:
            context = str(dict_source["text"])
        else:
            text_parts = []
            for value in dict_source.values():
                if isinstance(value, str):
                    text_parts.append(value)
            context = "\n".join(text_parts)
        
        return self._truncate_context(context)
    
    def _extract_from_text_source(
        self, text_source: str, current_item_info: Dict
    ) -> str:
        return self._truncate_context(text_source)
    
    def _extract_from_text_chunks(
        self, text_chunks: List[str], current_item_info: Dict
    ) -> str:
        current_index = current_item_info.get("index", 0)
        window_size = self.config.context_window
        
        start_idx = max(0, current_index - window_size)
        end_idx = min(len(text_chunks), current_index + window_size + 1)
        
        context_texts = []
        for i in range(start_idx, end_idx):
            if i != current_index:
                if i < len(text_chunks):
                    chunk_text = str(text_chunks[i]).strip()
                    if chunk_text:
                        context_texts.append(chunk_text)
        
        context = "\n".join(context_texts)
        return self._truncate_context(context)
    
    def _truncate_context(self, context: str) -> str:
        if not context:
            return ""
        
        if self.tokenizer:
            tokens = self.tokenizer.encode(context)
            if len(tokens) <= self.config.max_context_tokens:
                return context
            
            truncated_tokens = tokens[:self.config.max_context_tokens]
            truncated_text = self.tokenizer.decode(truncated_tokens)
            
            last_period = truncated_text.rfind(".")
            last_newline = truncated_text.rfind("\n")
            
            if last_period > len(truncated_text) * 0.8:
                return truncated_text[:last_period + 1]
            elif last_newline > len(truncated_text) * 0.8:
                return truncated_text[:last_newline]
            else:
                return truncated_text + "..."
        else:
            if len(context) <= self.config.max_context_tokens:
                return context
            
            truncated = context[:self.config.max_context_tokens]
            
            last_period = truncated.rfind(".")
            last_newline = truncated.rfind("\n")
            
            if last_period > len(truncated) * 0.8:
                return truncated[:last_period + 1]
            elif last_newline > len(truncated) * 0.8:
                return truncated[:last_newline]
            else:
                return truncated + "..."


# ============================================================================
# BASE PROCESSOR
# ============================================================================

class BaseModalProcessor(ABC):
    """
    Base class for multimodal content processors.
    
    Provides common functionality for all processors without LightRAG dependency.
    Uses server's AI providers for LLM and vision model calls.
    """
    
    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None,
        context_extractor: Optional[ContextExtractor] = None,
    ):
        self.config = config or RAGConfig.from_server_settings()
        self.llm_func = llm_func
        self.vision_func = vision_func
        self.logger = logging.getLogger(self.__class__.__name__)
        self.prompts = PROMPTS
        
        if context_extractor is None:
            self.context_extractor = ContextExtractor()
        else:
            self.context_extractor = context_extractor
        
        self.content_source = None
        self.content_format = "auto"
    
    def set_content_source(self, content_source: Any, content_format: str = "auto"):
        """Set content source for context extraction."""
        self.content_source = content_source
        self.content_format = content_format
        self.logger.info(f"Content source set with format: {content_format}")
    
    def _get_context_for_item(self, item_info: Dict[str, Any]) -> str:
        """Get context for current processing item."""
        if not self.content_source:
            return ""
        
        try:
            context = self.context_extractor.extract_context(
                self.content_source, item_info, self.content_format
            )
            if context:
                self.logger.debug(
                    f"Extracted context of length {len(context)} for item: {item_info}"
                )
            return context
        except Exception as e:
            self.logger.error(f"Error getting context for item {item_info}: {e}")
            return ""
    
    @abstractmethod
    async def process(
        self,
        content: Dict[str, Any],
        context: Optional[str] = None,
        entity_name: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Process multimodal content.
        
        Args:
            content: Content dictionary from parser
            context: Surrounding context
            entity_name: Optional predefined entity name
        
        Returns:
            Tuple of (description, entity_info)
        """
        pass
    
    @abstractmethod
    def supports_type(self, content_type: str) -> bool:
        """Check if processor supports this content type."""
        pass
    
    def _encode_image_to_base64(self, image_path: Union[str, Path]) -> str:
        """Encode image to base64 string."""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return encoded_string
        except Exception as e:
            self.logger.error(f"Failed to encode image {image_path}: {e}")
            return ""
    
    def _robust_json_parse(self, response: str) -> dict:
        """Robust JSON parsing with multiple fallback strategies."""
        for json_candidate in self._extract_all_json_candidates(response):
            result = self._try_parse_json(json_candidate)
            if result:
                return result
        
        for json_candidate in self._extract_all_json_candidates(response):
            cleaned = self._basic_json_cleanup(json_candidate)
            result = self._try_parse_json(cleaned)
            if result:
                return result
        
        for json_candidate in self._extract_all_json_candidates(response):
            fixed = self._progressive_quote_fix(json_candidate)
            result = self._try_parse_json(fixed)
            if result:
                return result
        
        return self._extract_fields_with_regex(response)
    
    def _extract_all_json_candidates(self, response: str) -> list:
        """Extract all possible JSON candidates from response."""
        candidates = []
        
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        candidates.extend(json_blocks)
        
        brace_count = 0
        start_pos = -1
        
        for i, char in enumerate(response):
            if char == "{":
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    candidates.append(response[start_pos:i + 1])
        
        simple_match = re.search(r"\{.*\}", response, re.DOTALL)
        if simple_match:
            candidates.append(simple_match.group(0))
        
        return candidates
    
    def _try_parse_json(self, json_str: str) -> Optional[dict]:
        """Try to parse JSON string."""
        if not json_str or not json_str.strip():
            return None
        
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None
    
    def _basic_json_cleanup(self, json_str: str) -> str:
        """Basic cleanup for common JSON issues."""
        json_str = json_str.strip()
        json_str = json_str.replace('"', '"').replace('"', '"')
        json_str = json_str.replace("'", "'").replace("'", "'")
        json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
        return json_str
    
    def _progressive_quote_fix(self, json_str: str) -> str:
        """Progressive fixing of quote and escape issues."""
        json_str = re.sub(r'(?<!\\)\\(?=")', r"\\\\", json_str)
        
        def fix_string_content(match):
            content = match.group(1)
            content = re.sub(r"\\(?=[a-zA-Z])", r"\\\\", content)
            return f'"{content}"'
        
        json_str = re.sub(r'"([^"]*(?:\\.[^"]*)*)"', fix_string_content, json_str)
        return json_str
    
    def _extract_fields_with_regex(self, response: str) -> dict:
        """Extract required fields using regex as fallback."""
        self.logger.warning("Using regex fallback for JSON parsing")
        
        desc_match = re.search(
            r'"detailed_description":\s*"([^"]*(?:\\.[^"]*)*)"', response, re.DOTALL
        )
        description = desc_match.group(1) if desc_match else ""
        
        name_match = re.search(r'"entity_name":\s*"([^"]*(?:\\.[^"]*)*)"', response)
        entity_name = name_match.group(1) if name_match else "unknown_entity"
        
        type_match = re.search(r'"entity_type":\s*"([^"]*(?:\\.[^"]*)*)"', response)
        entity_type = type_match.group(1) if type_match else "unknown"
        
        summary_match = re.search(
            r'"summary":\s*"([^"]*(?:\\.[^"]*)*)"', response, re.DOTALL
        )
        summary = summary_match.group(1) if summary_match else description[:100]
        
        return {
            "detailed_description": description,
            "entity_info": {
                "entity_name": entity_name,
                "entity_type": entity_type,
                "summary": summary,
            },
        }
    
    def _parse_response(
        self, response: str, entity_name: Optional[str] = None, content_type: str = "content"
    ) -> Tuple[str, Dict[str, Any]]:
        """Parse model response to extract description and entity info."""
        try:
            response_data = self._robust_json_parse(response)
            
            description = response_data.get("detailed_description", "")
            entity_data = response_data.get("entity_info", {})
            
            if not description or not entity_data:
                raise ValueError("Missing required fields in response")
            
            required_keys = ["entity_name", "entity_type", "summary"]
            if not all(key in entity_data for key in required_keys):
                raise ValueError("Missing required fields in entity_info")
            
            entity_data["entity_name"] = (
                entity_data["entity_name"] + f" ({entity_data['entity_type']})"
            )
            if entity_name:
                entity_data["entity_name"] = entity_name
            
            return description, entity_data
            
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            self.logger.error(f"Error parsing {content_type} analysis response: {e}")
            self.logger.debug(f"Raw response: {response}")
            fallback_entity = {
                "entity_name": entity_name or f"{content_type}_{compute_hash_id(response)}",
                "entity_type": content_type,
                "summary": response[:100] + "..." if len(response) > 100 else response,
            }
            return response, fallback_entity


# ============================================================================
# IMAGE PROCESSOR
# ============================================================================

class ImageModalProcessor(BaseModalProcessor):
    """
    Processor for image content analysis.
    
    Uses vision models to:
    - Generate detailed descriptions
    - Extract entities and relationships
    - Identify objects, text, and visual elements
    """
    
    async def process(
        self,
        content: Dict[str, Any],
        context: Optional[str] = None,
        entity_name: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """Process image content."""
        try:
            image_path = content.get("img_path")
            captions = content.get("image_caption", content.get("img_caption", []))
            footnotes = content.get("image_footnote", content.get("img_footnote", []))
            
            if not image_path:
                raise ValueError(f"No image path in content: {content}")
            
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            item_info = kwargs.get("item_info", {})
            if not context:
                context = self._get_context_for_item(item_info)
            
            if context:
                vision_prompt = PROMPTS["vision_prompt_with_context"].format(
                    context=context,
                    entity_name=entity_name or "unique descriptive name for this image",
                    image_path=image_path,
                    captions=captions if captions else "None",
                    footnotes=footnotes if footnotes else "None",
                )
            else:
                vision_prompt = PROMPTS["vision_prompt"].format(
                    entity_name=entity_name or "unique descriptive name for this image",
                    image_path=image_path,
                    captions=captions if captions else "None",
                    footnotes=footnotes if footnotes else "None",
                )
            
            image_base64 = self._encode_image_to_base64(image_path)
            if not image_base64:
                raise RuntimeError(f"Failed to encode image: {image_path}")
            
            if self.vision_func:
                response = await self.vision_func(
                    vision_prompt,
                    image_data=image_base64,
                    system_prompt=PROMPTS["IMAGE_ANALYSIS_SYSTEM"],
                )
            else:
                response = f"Image at {image_path}. Captions: {captions}"
            
            return self._parse_response(response, entity_name, "image")
            
        except Exception as e:
            self.logger.error(f"Error processing image content: {e}")
            fallback_entity = {
                "entity_name": entity_name or f"image_{compute_hash_id(str(content))}",
                "entity_type": "image",
                "summary": f"Image content: {str(content)[:100]}",
            }
            return str(content), fallback_entity
    
    def supports_type(self, content_type: str) -> bool:
        return content_type == "image"
    
    def format_chunk(
        self, content: Dict[str, Any], enhanced_caption: str
    ) -> str:
        """Format image content as a chunk for storage."""
        image_path = content.get("img_path", "")
        captions = content.get("image_caption", content.get("img_caption", []))
        footnotes = content.get("image_footnote", content.get("img_footnote", []))
        
        return PROMPTS["image_chunk"].format(
            image_path=image_path,
            captions=", ".join(captions) if isinstance(captions, list) else captions or "None",
            footnotes=", ".join(footnotes) if isinstance(footnotes, list) else footnotes or "None",
            enhanced_caption=enhanced_caption,
        )


# ============================================================================
# TABLE PROCESSOR
# ============================================================================

class TableModalProcessor(BaseModalProcessor):
    """
    Processor for table content analysis.
    
    Analyzes tables to:
    - Extract structure and headers
    - Identify patterns and trends
    - Generate statistical insights
    """
    
    async def process(
        self,
        content: Dict[str, Any],
        context: Optional[str] = None,
        entity_name: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """Process table content."""
        try:
            table_img_path = content.get("img_path", "")
            table_caption = content.get("table_caption", [])
            table_body = content.get("table_body", "")
            table_footnote = content.get("table_footnote", [])
            
            item_info = kwargs.get("item_info", {})
            if not context:
                context = self._get_context_for_item(item_info)
            
            if context:
                table_prompt = PROMPTS["table_prompt_with_context"].format(
                    context=context,
                    entity_name=entity_name or "descriptive name for this table",
                    table_img_path=table_img_path,
                    table_caption=table_caption if table_caption else "None",
                    table_body=table_body,
                    table_footnote=table_footnote if table_footnote else "None",
                )
            else:
                table_prompt = PROMPTS["table_prompt"].format(
                    entity_name=entity_name or "descriptive name for this table",
                    table_img_path=table_img_path,
                    table_caption=table_caption if table_caption else "None",
                    table_body=table_body,
                    table_footnote=table_footnote if table_footnote else "None",
                )
            
            if self.llm_func:
                response = await self.llm_func(
                    table_prompt,
                    system_prompt=PROMPTS["TABLE_ANALYSIS_SYSTEM"],
                )
            else:
                response = f"Table content. Caption: {table_caption}. Body: {str(table_body)[:200]}"
            
            return self._parse_response(response, entity_name, "table")
            
        except Exception as e:
            self.logger.error(f"Error processing table content: {e}")
            fallback_entity = {
                "entity_name": entity_name or f"table_{compute_hash_id(str(content))}",
                "entity_type": "table",
                "summary": f"Table content: {str(content)[:100]}",
            }
            return str(content), fallback_entity
    
    def supports_type(self, content_type: str) -> bool:
        return content_type == "table"
    
    def format_chunk(
        self, content: Dict[str, Any], enhanced_caption: str
    ) -> str:
        """Format table content as a chunk for storage."""
        table_img_path = content.get("img_path", "")
        table_caption = content.get("table_caption", [])
        table_body = content.get("table_body", "")
        table_footnote = content.get("table_footnote", [])
        
        return PROMPTS["table_chunk"].format(
            table_img_path=table_img_path,
            table_caption=", ".join(table_caption) if isinstance(table_caption, list) else table_caption or "None",
            table_body=table_body,
            table_footnote=", ".join(table_footnote) if isinstance(table_footnote, list) else table_footnote or "None",
            enhanced_caption=enhanced_caption,
        )


# ============================================================================
# EQUATION PROCESSOR
# ============================================================================

class EquationModalProcessor(BaseModalProcessor):
    """
    Processor for mathematical equation analysis.
    
    Analyzes equations to:
    - Explain mathematical meaning
    - Identify variables and operations
    - Describe applications and significance
    """
    
    async def process(
        self,
        content: Dict[str, Any],
        context: Optional[str] = None,
        entity_name: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """Process equation content."""
        try:
            equation_text = content.get("text", "")
            equation_format = content.get("text_format", "")
            
            item_info = kwargs.get("item_info", {})
            if not context:
                context = self._get_context_for_item(item_info)
            
            if context:
                equation_prompt = PROMPTS["equation_prompt_with_context"].format(
                    context=context,
                    equation_text=equation_text,
                    equation_format=equation_format,
                    entity_name=entity_name or "descriptive name for this equation",
                )
            else:
                equation_prompt = PROMPTS["equation_prompt"].format(
                    equation_text=equation_text,
                    equation_format=equation_format,
                    entity_name=entity_name or "descriptive name for this equation",
                )
            
            if self.llm_func:
                response = await self.llm_func(
                    equation_prompt,
                    system_prompt=PROMPTS["EQUATION_ANALYSIS_SYSTEM"],
                )
            else:
                response = f"Equation: {equation_text}. Format: {equation_format}"
            
            return self._parse_response(response, entity_name, "equation")
            
        except Exception as e:
            self.logger.error(f"Error processing equation content: {e}")
            fallback_entity = {
                "entity_name": entity_name or f"equation_{compute_hash_id(str(content))}",
                "entity_type": "equation",
                "summary": f"Equation content: {str(content)[:100]}",
            }
            return str(content), fallback_entity
    
    def supports_type(self, content_type: str) -> bool:
        return content_type == "equation"
    
    def format_chunk(
        self, content: Dict[str, Any], enhanced_caption: str
    ) -> str:
        """Format equation content as a chunk for storage."""
        equation_text = content.get("text", "")
        equation_format = content.get("text_format", "")
        
        return PROMPTS["equation_chunk"].format(
            equation_text=equation_text,
            equation_format=equation_format,
            enhanced_caption=enhanced_caption,
        )


# ============================================================================
# GENERIC PROCESSOR
# ============================================================================

class GenericModalProcessor(BaseModalProcessor):
    """
    Generic processor for unknown content types.
    
    Provides flexible analysis for:
    - Custom content types
    - Fallback processing
    - Extensible content handling
    """
    
    async def process(
        self,
        content: Dict[str, Any],
        context: Optional[str] = None,
        entity_name: Optional[str] = None,
        content_type: str = "content",
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """Process generic content."""
        try:
            content_str = str(content)
            
            item_info = kwargs.get("item_info", {})
            if not context:
                context = self._get_context_for_item(item_info)
            
            if context:
                generic_prompt = PROMPTS["generic_prompt_with_context"].format(
                    context=context,
                    content_type=content_type,
                    entity_name=entity_name or f"descriptive name for this {content_type}",
                    content=content_str,
                )
            else:
                generic_prompt = PROMPTS["generic_prompt"].format(
                    content_type=content_type,
                    entity_name=entity_name or f"descriptive name for this {content_type}",
                    content=content_str,
                )
            
            if self.llm_func:
                response = await self.llm_func(
                    generic_prompt,
                    system_prompt=PROMPTS["generic_analysis_system"].format(
                        content_type=content_type
                    ),
                )
            else:
                response = f"{content_type.title()} content: {content_str[:200]}"
            
            return self._parse_response(response, entity_name, content_type)
            
        except Exception as e:
            self.logger.error(f"Error processing {content_type} content: {e}")
            fallback_entity = {
                "entity_name": entity_name or f"{content_type}_{compute_hash_id(str(content))}",
                "entity_type": content_type,
                "summary": f"{content_type} content: {str(content)[:100]}",
            }
            return str(content), fallback_entity
    
    def supports_type(self, content_type: str) -> bool:
        return True
    
    def format_chunk(
        self, content: Dict[str, Any], enhanced_caption: str, content_type: str = "content"
    ) -> str:
        """Format generic content as a chunk for storage."""
        return PROMPTS["generic_chunk"].format(
            content_type=content_type.title(),
            content=str(content),
            enhanced_caption=enhanced_caption,
        )


# ============================================================================
# PROCESSOR FACTORY
# ============================================================================

class ProcessorFactory:
    """Factory for creating processor instances."""
    
    @staticmethod
    def create_processor(
        content_type: Union[str, ContentType],
        config: Optional[RAGConfig] = None,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None,
    ) -> BaseModalProcessor:
        """Create a processor instance."""
        if isinstance(content_type, ContentType):
            content_type = content_type.value
        
        content_type = content_type.lower()
        
        if content_type == "image":
            return ImageModalProcessor(config, llm_func, vision_func)
        elif content_type == "table":
            return TableModalProcessor(config, llm_func, vision_func)
        elif content_type == "equation":
            return EquationModalProcessor(config, llm_func, vision_func)
        else:
            return GenericModalProcessor(config, llm_func, vision_func)
    
    @staticmethod
    def create_all_processors(
        config: Optional[RAGConfig] = None,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None,
    ) -> Dict[str, BaseModalProcessor]:
        """Create all processor instances."""
        return {
            "image": ImageModalProcessor(config, llm_func, vision_func),
            "table": TableModalProcessor(config, llm_func, vision_func),
            "equation": EquationModalProcessor(config, llm_func, vision_func),
            "generic": GenericModalProcessor(config, llm_func, vision_func),
        }
    
    @staticmethod
    def get_processor_for_content(
        content: Dict[str, Any],
        processors: Dict[str, BaseModalProcessor]
    ) -> BaseModalProcessor:
        """Get appropriate processor for content."""
        content_type = content.get("type", "generic")
        return processors.get(content_type, processors.get("generic"))


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ContextConfig",
    "ContextExtractor",
    "BaseModalProcessor",
    "ImageModalProcessor",
    "TableModalProcessor",
    "EquationModalProcessor",
    "GenericModalProcessor",
    "ProcessorFactory",
    "compute_hash_id",
]

"""
RAG Service Utilities.
"""
import logging
from typing import Any
from app.services.core.rag.types import RAGResponse, PolicyEvaluationResult

logger = logging.getLogger(__name__)

def convert_to_response(result: Any, pattern: str, ai_manager=None) -> RAGResponse:
    """Convert arbitrary result to RAGResponse."""
    if isinstance(result, RAGResponse):
        return result
    
    # Default values
    answer = ""
    citations = []
    metadata = {}
    policy_eval = PolicyEvaluationResult()
    
    provider = "unknown"
    model = "unknown"
    
    # Helper function để extract answer từ nested objects
    def extract_answer(obj: Any) -> str:
        """Recursively extract answer text from various result types."""
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            # Try common answer keys
            for key in ['answer', 'response', 'final_response', 'result', 'output', 'content', 'text']:
                if key in obj:
                    val = obj[key]
                    # Recursively extract if value is also complex
                    extracted = extract_answer(val)
                    if extracted and isinstance(extracted, str) and len(extracted) > 10:
                        return extracted
            return ""
        # Handle dataclass/object with attributes
        for attr in ['response', 'answer', 'final_response', 'result', 'output', 'content', 'text']:
            if hasattr(obj, attr):
                val = getattr(obj, attr, None)
                if val:
                    extracted = extract_answer(val)
                    if extracted and isinstance(extracted, str) and len(extracted) > 10:
                        return extracted
        return ""
    
    # Helper function để extract provider/model
    def extract_provider_model(obj: Any) -> tuple[str, str]:
        """Extract provider and model from result."""
        prov, mod = "unknown", "unknown"
        if isinstance(obj, dict):
            prov = obj.get("provider", "unknown")
            mod = obj.get("model", "unknown")
            # Check nested result
            if prov == "unknown" and "result" in obj:
                nested = obj.get("result")
                if isinstance(nested, dict):
                    prov = nested.get("provider", prov)
                    mod = nested.get("model", mod)
                elif hasattr(nested, 'provider'):
                    prov = getattr(nested, 'provider', prov)
                    mod = getattr(nested, 'model', mod)
        elif hasattr(obj, 'provider'):
            prov = getattr(obj, 'provider', 'unknown')
            mod = getattr(obj, 'model', 'unknown')
        return prov, mod
    
    if isinstance(result, dict):
        # Extract answer recursively
        answer = extract_answer(result)
        
        # If still no answer, try to get from metadata
        if not answer:
            meta_result = result.get("metadata", {})
            if isinstance(meta_result, dict) and "answer" in meta_result:
                answer = str(meta_result["answer"])
        
        # Extract provider & model
        provider, model = extract_provider_model(result)
            
        # Populate metadata (exclude raw result to avoid duplication)
        safe_keys = ['patterns', 'strategy', 'success', 'latency_ms', 
                     'confidence_score', 'decision_reasoning']
        metadata = {k: v for k, v in result.items() 
                   if k in safe_keys and v is not None}
            
    elif isinstance(result, str):
        answer = result
    else:
        # Handle dataclass objects or other objects
        answer = extract_answer(result)
        provider, model = extract_provider_model(result)
        
        # Build metadata from specific attributes only
        for attr_name in ['confidence_score', 'retrieval_used', 'retrieval_strategy']:
            if hasattr(result, attr_name):
                val = getattr(result, attr_name, None)
                if val is not None:
                    metadata[attr_name] = val
    
    # Final validation - ensure answer is a clean string
    if not isinstance(answer, str) or not answer:
        logger.warning(f"Could not extract answer from {type(result).__name__}, using fallback")
        answer = ""
    
    # Fallback: Lấy model từ AI manager nếu không tìm thấy trong result
    if (provider == "unknown" or model == "unknown") and ai_manager:
        available = ai_manager._get_available_providers()
        if available:
            provider = available[0]  # First available provider có priority cao nhất
            if provider in ai_manager.providers:
                provider_instance = ai_manager.providers[provider]
                model = getattr(provider_instance, 'model', 'unknown')
        
    return RAGResponse(
        answer=answer,
        pattern=pattern,
        provider=provider,
        model=model,
        metadata=metadata,
        policy_evaluation=policy_eval
    )

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

# Configure logger
logger = logging.getLogger("rag_analytics")
# Ensure we have a handler if not already configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class RAGLogger:
    """
    Structured logger for RAG operations.
    Logs events in JSON format for easy parsing and analytics.
    """
    
    @staticmethod
    def log_query(
        query: str,
        workspace_id: UUID,
        intent: str,
        retrieval_count: int,
        answer_length: int,
        latency_ms: int,
        provider: str,
        model: str,
        grounding_score: float = 0.0,
        is_grounded: bool = False,
        session_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        fallback_used: bool = False,
        metadata: Dict[str, Any] = None
    ):
        """
        Log a RAG query event.
        """
        event = {
            "event_type": "rag_query",
            "timestamp": datetime.utcnow().isoformat(),
            "query": query[:500],  # Truncate for safety
            "workspace_id": str(workspace_id),
            "intent": intent,
            "metrics": {
                "retrieval_count": retrieval_count,
                "answer_length": answer_length,
                "latency_ms": latency_ms,
                "grounding_score": grounding_score,
            },
            "flags": {
                "is_grounded": is_grounded,
                "fallback_used": fallback_used,
            },
            "llm": {
                "provider": provider,
                "model": model,
            },
            "context": {
                "session_id": session_id,
                "user_id": str(user_id) if user_id else None,
            },
            "metadata": metadata or {}
        }
        
        # Log as structured JSON
        logger.info(json.dumps(event))

    @staticmethod
    def log_feedback(
        query_id: str,
        score: float,  # -1 to 1 or 1 to 5
        feedback_text: Optional[str] = None,
        user_id: Optional[UUID] = None
    ):
        """Log user feedback."""
        event = {
            "event_type": "user_feedback",
            "timestamp": datetime.utcnow().isoformat(),
            "query_id": query_id,
            "score": score,
            "feedback": feedback_text,
            "user_id": str(user_id) if user_id else None
        }
        logger.info(json.dumps(event))

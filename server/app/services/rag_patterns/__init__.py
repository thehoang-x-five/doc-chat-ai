"""
RAG Patterns - Advanced RAG pattern implementations and orchestration

This module provides:
- Document processing pipeline (multimodal support)
- RAG pattern implementations (Corrective, Self, Adaptive, CORAG, etc.)
- Pattern orchestration and intelligent routing
- Performance monitoring and optimization

Migrated from raganything library and integrated into server architecture.
"""

from app.services.rag_patterns.pipeline.config import RAGConfig
from app.services.rag_patterns.pipeline.pipeline import RAGPipeline

__all__ = ["RAGConfig", "RAGPipeline"]

"""
Specialized Patterns Module.

This module consolidates RAG patterns for specific use cases:
- CORAL: Conversational RAG with context tracking
- REVEAL: Visual-Language RAG with multimodal fusion
- CodeRAG: Code-aware RAG with symbol resolution
"""

# CORAL (Conversational RAG)
from .coral import (
    CORALService,
    ContextManager,
    HistoryManager,
    ConversationRetriever,
)

# REVEAL (Visual-Language RAG)
from .reveal import (
    REVEALService,
    VisionEncoder,
    MultimodalRetrieval,
    VisualTextFusion,
    FusionStrategy,
)

# CodeRAG (Code-aware RAG)
from .code_rag import (
    CodeRAGService,
    CodeParser,
    SymbolResolver,
    DocExtractor,
)

# Models from shared models.py
from .models import (
    # CORAL models
    Turn,
    TurnType,
    ConversationContext,
    ContextPruningStrategy,
    CORALResult,
    # REVEAL models
    VisualContext,
    TextContext,
    MultimodalResult,
    REVEALResult,
    ModalityType,
    FusionConfig,
    # CodeRAG models
    Symbol,
    SymbolType,
    CodeContext,
    CodeAnalysis,
    CodeRAGResult,
)

__all__ = [
    # Services
    "CORALService",
    "REVEALService",
    "CodeRAGService",
    # CORAL components
    "ContextManager",
    "HistoryManager",
    "ConversationRetriever",
    # REVEAL components
    "VisionEncoder",
    "MultimodalRetrieval",
    "VisualTextFusion",
    "FusionStrategy",
    # CodeRAG components
    "CodeParser",
    "SymbolResolver",
    "DocExtractor",
    # CORAL models
    "Turn",
    "TurnType",
    "ConversationContext",
    "ContextPruningStrategy",
    "CORALResult",
    # REVEAL models
    "VisualContext",
    "TextContext",
    "MultimodalResult",
    "REVEALResult",
    "ModalityType",
    "FusionConfig",
    # CodeRAG models
    "Symbol",
    "SymbolType",
    "CodeContext",
    "CodeAnalysis",
    "CodeRAGResult",
]

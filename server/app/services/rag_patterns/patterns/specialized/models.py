"""
Shared data models for Specialized RAG patterns.

Contains models for:
- CORAL (Conversational RAG)
- REVEAL (Visual-Language RAG)
- CodeRAG (Code-aware RAG)
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# =============================================================================
# CORAL (Conversational RAG) Models
# =============================================================================

class TurnType(Enum):
    """Type of conversation turn."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContextPruningStrategy(Enum):
    """Strategy for pruning conversation context."""
    FIFO = "fifo"
    RELEVANCE = "relevance"
    SLIDING_WINDOW = "sliding_window"
    SUMMARIZE = "summarize"


@dataclass
class Turn:
    """A single turn in a conversation."""
    turn_id: str
    turn_type: TurnType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    tokens: int = 0

    def __post_init__(self):
        if self.tokens == 0:
            self.tokens = len(self.content) // 4  # ~4 chars per token


@dataclass
class ConversationContext:
    """Context for a conversation including history and metadata."""
    conversation_id: str
    turns: list[Turn] = field(default_factory=list)
    total_tokens: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None

    def add_turn(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.total_tokens += turn.tokens
        self.updated_at = datetime.now()

    def get_recent_turns(self, n: int) -> list[Turn]:
        return self.turns[-n:] if n > 0 else []


@dataclass
class CORALResult:
    """Result of CORAL conversational RAG processing."""
    conversation_id: str
    response: str
    turn: Turn
    context_used: list[Turn]
    retrieved_docs: list[Any] = field(default_factory=list)
    coherence_score: float = 0.0
    context_tokens: int = 0
    total_tokens: int = 0
    pruning_applied: bool = False
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# REVEAL (Visual-Language RAG) Models
# =============================================================================

class ModalityType(Enum):
    """Types of modalities in multimodal RAG."""
    TEXT = "text"
    VISUAL = "visual"
    MIXED = "mixed"


@dataclass
class VisualContext:
    """Visual context information."""
    image_data: Any
    embedding: list[float] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    caption: str | None = None


@dataclass
class TextContext:
    """Text context information."""
    content: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None


@dataclass
class MultimodalResult:
    """Result from multimodal retrieval."""
    text_results: list[dict[str, Any]] = field(default_factory=list)
    visual_results: list[dict[str, Any]] = field(default_factory=list)
    fused_results: list[dict[str, Any]] = field(default_factory=list)
    text_weight: float = 0.6
    visual_weight: float = 0.4
    fusion_strategy: str = "hybrid"

    @property
    def total_results(self) -> int:
        return len(self.text_results) + len(self.visual_results)


@dataclass
class REVEALResult:
    """Complete result from REVEAL pattern."""
    query: str
    query_embedding: list[float] = field(default_factory=list)
    visual_context: VisualContext | None = None
    text_context: TextContext | None = None
    multimodal_result: MultimodalResult | None = None
    response: str = ""
    modality_type: ModalityType = ModalityType.MIXED
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_multimodal(self) -> bool:
        return self.visual_context is not None and self.text_context is not None


@dataclass
class FusionConfig:
    """Configuration for visual-text fusion."""
    strategy: str = "hybrid"
    visual_weight: float = 0.4
    text_weight: float = 0.6
    attention_enabled: bool = True
    top_k: int = 5


# =============================================================================
# CodeRAG Models
# =============================================================================

class SymbolType(Enum):
    """Type of code symbol."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    MODULE = "module"
    IMPORT = "import"
    PARAMETER = "parameter"
    ATTRIBUTE = "attribute"


@dataclass
class Symbol:
    """Represents a code symbol (function, class, variable, etc.)."""
    name: str
    type: SymbolType
    file_path: str
    line_number: int
    docstring: str | None = None
    signature: str | None = None
    references: list[dict[str, Any]] = field(default_factory=list)
    scope: str = "global"
    parent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeContext:
    """Code context for a query."""
    query: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    code_snippets: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeAnalysis:
    """Result of code analysis."""
    file_path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    complexity: dict[str, Any] = field(default_factory=dict)
    documentation_coverage: float = 0.0
    issues: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeRAGResult:
    """Result from Code RAG query."""
    query: str
    answer: str
    code_context: CodeContext
    relevant_symbols: list[Symbol] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

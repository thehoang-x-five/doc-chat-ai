"""
RAG-Anything Services Module
Organized by domain for better maintainability
"""

# Core RAG Services
from app.services.core import (
    RAGService,
    RetrieverService,
    EmbeddingService,
    RerankerService,
    ContextBudgetManager,
)

# Conversation Services
from app.services.conversation import (
    ChatService,
    MemoryManager,
    IntentDetector,
    IntentCache,
)

# Document Services
from app.services.documents import (
    DocumentService,
    ChunkingService,
    ExtractionService,
    CategoryService,
)

# Search Services
from app.services.search import (
    SearchCache,
    TimelineService,
    RAGCache,
)

# Generation Services
from app.services.generation import (
    PromptBuilder,
    ResponseFormatter,
    SummarizeService,
    CompareService,
    ImageGenerationService,
)

# Quality Services
from app.services.quality import (
    PolicyService,
    GroundingVerifier,
    GuardrailsService,
    EvaluationService,
)

# Auth Services
from app.services.auth import (
    AuthService,
    APIKeyManager,
    OAuthCallbackServer,
)

# Infrastructure Services
from app.services.infrastructure import (
    CloudCodeProviderManager,
    PhoenixTracer,
    HealthMonitor,
    LoggingService,
    PipelineConfigLoader,
)

# Advanced RAG Patterns
from app.services.tools import (
    HybridRetriever,
    FunctionCallingService,
    FunctionRegistry,
    ToolsServiceV2,
)

# Analytics Services
from app.services.analytics import (
    AnalyticsService,
    JobService,
    WorkspaceService,
)

# Memori Services (Memory Management)
from app.services.memori import (
    MemoriManager,
    MemoriRecall,
    MemoriConfig,
)

# Utility Services (Removed - moved to core and generation)

__all__ = [
    # Core
    "RAGService",
    "RetrieverService",
    "EmbeddingService",
    "RerankerService",
    "ContextBudgetManager",  # Moved from Utils
    # Conversation
    "ChatService",
    "MemoryManager",
    "IntentDetector",
    "IntentCache",
    # Documents
    "DocumentService",
    "ChunkingService",
    "ExtractionService",
    "CategoryService",
    # Search
    "SearchCache",
    "TimelineService",
    "RAGCache",
    # Generation
    "PromptBuilder",
    "ResponseFormatter",
    "SummarizeService",
    "CompareService",
    "ImageGenerationService",  # Moved from Utils
    # Quality
    "PolicyService",
    "GroundingVerifier",
    "GuardrailsService",
    "EvaluationService",
    # Auth
    "AuthService",
    "APIKeyManager",
    "OAuthCallbackServer",
    # Infrastructure
    "CloudCodeProviderManager",
    "PhoenixTracer",
    "HealthMonitor",
    "LoggingService",
    "PipelineConfigLoader",
    # Patterns
    "HybridRetriever",
    "FunctionCallingService",
    "FunctionRegistry",
    "ToolsServiceV2",
    # Analytics
    "AnalyticsService",
    "JobService",
    "WorkspaceService",
    # Memori
    "MemoriManager",
    "MemoriRecall",
    "MemoriConfig",
]

"""
Hệ thống Quản lý Bộ nhớ kiểu Memori.
Được chuyển đổi từ dự án Memori để có các khả năng bộ nhớ nâng cao.

Tính năng:
- Entity Facts với embeddings cho semantic search
- Semantic Triples (Knowledge Graph)
- FAISS vector similarity search
- Lexical reranking (hybrid search)
- Pipeline augmentation bất đồng bộ
- Quản lý time-out phiên làm việc
- Ghi database theo batch (Batch database writes)

Cognee-Inspired Features (Phase 1-4):
- Auto-Cognify: Automatic fact/triple extraction from messages
- Graph Search: Triplet and graph traversal search (5 types)
- Memify: Knowledge graph enrichment and inference
"""

# Lazy imports để tránh circular dependencies
def __getattr__(name):
    if name == "MemoriConfig":
        from app.services.memori.models import MemoriConfig
        return MemoriConfig
    elif name == "MemoriManager":
        from app.services.memori.manager_service import MemoriManager
        return MemoriManager
    elif name == "MemoriRecall":
        from app.services.memori.recall_service import MemoriRecall
        return MemoriRecall
    # Cognee-inspired services
    elif name == "AutoCognifyService":
        from app.services.memori.auto_cognify_service import AutoCognifyService
        return AutoCognifyService
    elif name == "GraphSearchService":
        from app.services.memori.graph_search_service import GraphSearchService
        return GraphSearchService
    elif name == "SearchType":
        from app.services.memori.graph_search_service import SearchType
        return SearchType
    elif name == "MemifyService":
        from app.services.memori.memify_service import MemifyService
        return MemifyService
    elif name in ("Conversation", "Entity", "Memories", "Process", "SemanticTriple", "RecalledFact", "AugmentationInput"):
        from app.services.memori import models
        return getattr(models, name)
    elif name in ("AugmentationManager", "AugmentationContext", "get_runtime", "get_db_writer"):
        from app.services.memori import augmentation_service
        return getattr(augmentation_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Config
    "MemoriConfig",
    # Core Manager
    "MemoriManager",
    "MemoriRecall",
    # Cognee-inspired Services
    "AutoCognifyService",
    "GraphSearchService",
    "SearchType",
    "MemifyService",
    # Models (formerly structs)
    "Conversation",
    "Entity",
    "Memories",
    "Process",
    "SemanticTriple",
    "RecalledFact",
    "AugmentationInput",
    # Augmentation
    "AugmentationManager",
    "AugmentationContext",
    "get_runtime",
    "get_db_writer",
]

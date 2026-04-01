# RAG Patterns Service

Advanced RAG pattern implementations integrated into the server architecture.

## Structure

```
rag_patterns/
├── __init__.py              # Main exports
├── README.md                # This file
│
├── pipeline/                # Document processing pipeline
│   ├── __init__.py
│   ├── config.py           # RAG configuration
│   ├── pipeline.py         # Main RAG pipeline (RAGAnything)
│   ├── parsers.py          # Document parsers (Mineru, Docling)
│   ├── processors.py       # Multimodal processors
│   └── prompts.py          # Prompt templates
│
├── orchestration/           # Pattern orchestration
│   ├── __init__.py
│   ├── orchestrator.py     # Pattern orchestrator
│   ├── registry.py         # Pattern registry
│   ├── analyzer.py         # Query analyzer
│   ├── planner.py          # Workflow planner
│   ├── router.py           # Smart router
│   ├── combinations.py     # Pre-defined combinations
│   └── monitoring.py       # Performance monitoring
│
├── corrective/              # Corrective RAG pattern
│   ├── __init__.py
│   ├── service.py          # Main service
│   ├── scorer.py           # Relevance scoring
│   ├── resolver.py         # Conflict resolution
│   └── fallback.py         # Fallback mechanisms
│
├── self_rag/                # Self RAG pattern
│   ├── __init__.py
│   ├── service.py
│   ├── checker.py          # Relevance checking
│   ├── refiner.py          # Response refinement
│   └── rewriter.py         # Query rewriting
│
├── adaptive/                # Adaptive RAG pattern
│   ├── __init__.py
│   ├── service.py
│   └── router.py           # Adaptive routing
│
├── corag/                   # CORAG pattern
│   ├── __init__.py
│   ├── service.py
│   └── optimizer.py        # Cost optimization
│
├── speculative/             # Speculative RAG pattern
│   ├── __init__.py
│   ├── service.py
│   └── draft_generator.py  # Draft generation
│
├── coral/                   # CORAL pattern (Conversational)
│   ├── __init__.py
│   ├── service.py
│   └── context_manager.py  # Context management
│
├── reveal/                  # REVEAL pattern (Multimodal)
│   ├── __init__.py
│   ├── service.py
│   └── fusion.py           # Multimodal fusion
│
├── code/                    # Code RAG pattern
│   ├── __init__.py
│   ├── service.py
│   └── parser.py           # Code parsing
│
└── semantic_highlight/      # Semantic Highlight pattern
    ├── __init__.py
    ├── service.py
    ├── splitter.py         # Sentence splitting
    ├── scorer.py           # Semantic scoring
    └── compressor.py       # Context compression
```

## Integration with Server

### 1. Configuration
```python
from app.services.rag_patterns import RAGConfig

# Create config from server settings
config = RAGConfig.from_server_settings()
```

### 2. Pipeline Usage
```python
from app.services.rag_patterns import RAGPipeline

# Initialize pipeline
pipeline = RAGPipeline(config=config)

# Process document
result = await pipeline.process_document("document.pdf")
```

### 3. Pattern Usage
```python
from app.services.rag_patterns.corrective import CorrectiveRAGService

# Use specific pattern
service = CorrectiveRAGService()
result = await service.retrieve_and_correct(query, documents)
```

### 4. Orchestration
```python
from app.services.rag_patterns.orchestration import PatternOrchestrator

# Use orchestrator for intelligent pattern selection
orchestrator = PatternOrchestrator()
result = await orchestrator.orchestrate(
    query="What is Python?",
    pattern_services=pattern_services,
    strategy="auto"
)
```

## Migration Status

- [x] Phase 1: Config migration
- [ ] Phase 2: Pipeline migration
- [ ] Phase 3: Patterns migration
- [ ] Phase 4: Orchestration migration
- [ ] Phase 5: Integration with RAGService

## Design Principles

1. **Server-first**: All code follows server architecture patterns
2. **Service-based**: Each pattern is a service class
3. **Dependency injection**: Uses server's service registry
4. **Configuration**: Extends server settings
5. **Testing**: Comprehensive test coverage

## Related Services

- `app.services.core.rag_service` - Main RAG service (uses patterns)
- `app.services.core.embedding_service` - Embedding generation
- `app.services.core.retriever_service` - Document retrieval
- `app.services.search` - Search and caching
- `app.services.documents` - Document management

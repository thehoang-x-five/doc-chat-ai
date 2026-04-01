"""
RAG Service Factory.
Handles initialization of RAG components (RAGAnything, Patterns, Orchestration).
"""
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.core.rag.wrappers import (
    create_llm_wrapper,
    create_vision_wrapper,
    create_embedding_wrapper
)

logger = logging.getLogger(__name__)

async def initialize_raganything(
    working_dir: Path,
    parser: str,
    parse_method: str,
    ai_manager: Any,
    embedding_service: Any,
) -> Any:
    """Initialize RAGAnything instance."""
    try:
        from app.services.rag_patterns.pipeline import RAGPipeline as RAGAnything
        from app.services.rag_patterns.pipeline.config import RAGConfig
        from app.services.rag_patterns.pipeline.prompt_manager import initialize_prompts
        initialize_prompts(lang_code="en")

        # Create working directory
        working_dir.mkdir(parents=True, exist_ok=True)

        # Create wrappers
        # Note: We pass ai_manager.generate_completion/stream via partial or wrapper
        # The wrapper factory handles the binding
        
        async def generate_func(**kwargs):
            # Adapter to call AI Manager
            # We assume AI Manager has generate_completion
            return await ai_manager.generate_completion(
                messages=kwargs.get("messages", []), # Messages built inside wrapper
                model=kwargs.get("model"),
                **kwargs
            )
            
        # Bind the generate function to the manager instance method
        generate_bound = ai_manager.generate_completion

        llm_func = create_llm_wrapper(ai_manager, generate_bound)
        vision_func = create_vision_wrapper(generate_bound)
        embedding_func = create_embedding_wrapper(embedding_service)

        # Config
        config = RAGConfig(
            working_dir=working_dir,
            parser=parser,
            parse_method=parse_method,
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )

        raganything = RAGAnything(
            config=config,
            llm_func=llm_func,
            vision_func=vision_func,
            embedding_func=embedding_func,
        )
        
        # Register default MetricsCallback for observability
        from app.services.rag_patterns.pipeline.callbacks import MetricsCallback
        metrics_cb = MetricsCallback()
        raganything.callback_manager.register(metrics_cb)
        raganything._metrics_callback = metrics_cb  # Keep reference for access

        logger.info(f"RAGAnything initialized at {working_dir}")
        return raganything

    except ImportError as e:
        logger.error(f"Failed to import RAGAnything: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize RAGAnything: {e}")
        raise

async def initialize_patterns(
    raganything_instance: Any,
    embedding_service: Any,
    wrappers: dict,
) -> dict:
    """Initialize all RAG pattern services."""
    services = {}
    
    try:
        from app.services.rag_patterns.patterns import (
            AdaptiveRAGService,
            CORAGService,
            CorrectiveRAGService,
            SelfRAGService,
            SpeculativeRAGService,
            CORALService,
            REVEALService,
            SemanticHighlightRAGService,
            CodeRAGService,
        )
        from app.services.rag_patterns.patterns.specialized import FusionConfig
        from app.services.rag_patterns.patterns.hybrid import HybridRAGService

        # Hybrid RAG (Wrapper around RAGAnything)
        services["hybrid"] = HybridRAGService(raganything_instance)
        
        # Corrective RAG
        services["corrective_rag"] = CorrectiveRAGService(
            relevance_threshold=0.6,
            max_correction_attempts=2,
        )

        # Self RAG
        services["self_rag"] = SelfRAGService(
            max_iterations=3,
            min_relevance_score=0.6,
            min_grounding_score=0.5,
        )

        # Adaptive RAG
        services["adaptive_rag"] = AdaptiveRAGService(
            high_confidence_threshold=0.8,
            low_confidence_threshold=0.6,
            lightweight_top_k=3,
            full_top_k=10,
        )

        # CORAG
        services["corag"] = CORAGService(
            cost_weight=0.3,
            mcts_iterations=100,
        )

        # Speculative RAG
        services["speculative_rag"] = SpeculativeRAGService(
            num_drafts=getattr(settings, "SPECULATIVE_RAG_NUM_DRAFTS", 3),
            small_model=getattr(settings, "SPECULATIVE_RAG_SMALL_MODEL", "gpt-3.5-turbo"),
            large_model=getattr(settings, "SPECULATIVE_RAG_LARGE_MODEL", "gpt-4"),
            temperature=getattr(settings, "SPECULATIVE_RAG_TEMPERATURE", 0.7),
            enable_merging=getattr(settings, "SPECULATIVE_RAG_ENABLE_MERGING", False),
        )

        # CORAL
        services["coral"] = CORALService(
            max_history_turns=getattr(settings, "CORAL_MAX_HISTORY_TURNS", 10),
            context_window_size=getattr(settings, "CORAL_CONTEXT_WINDOW_SIZE", 4096),
            use_context_enhancement=getattr(settings, "CORAL_USE_CONTEXT_ENHANCEMENT", True),
            max_context_turns_for_retrieval=getattr(settings, "CORAL_MAX_CONTEXT_TURNS", 3),
        )

        # REVEAL (Multimodal)
        services["reveal"] = REVEALService(
            raganything_instance=raganything_instance,
            vision_model_func=wrappers.get("vision_func"),
            fusion_config=FusionConfig(
                strategy=getattr(settings, "REVEAL_FUSION_STRATEGY", "hybrid"),
                visual_weight=getattr(settings, "REVEAL_VISUAL_WEIGHT", 0.4),
                text_weight=getattr(settings, "REVEAL_TEXT_WEIGHT", 0.6),
                attention_enabled=getattr(settings, "REVEAL_ATTENTION_ENABLED", True),
                top_k=getattr(settings, "REVEAL_TOP_K", 5),
            ),
            embedding_dim=768, 
        )

        # Semantic Highlight
        services["semantic_highlight"] = SemanticHighlightRAGService(
            embedding_service=embedding_service,
            relevance_threshold=getattr(settings, "SEMANTIC_HIGHLIGHT_THRESHOLD", 0.5),
            max_sentences_per_chunk=getattr(settings, "SEMANTIC_HIGHLIGHT_MAX_SENTENCES", 50),
            language=getattr(settings, "SEMANTIC_HIGHLIGHT_LANGUAGE", "multilingual"),
            tokenizer=getattr(settings, "SEMANTIC_HIGHLIGHT_TOKENIZER", "cl100k_base"),
        )

        # Code RAG
        services["code_rag"] = CodeRAGService(
            max_context_symbols=getattr(settings, "CODE_RAG_MAX_SYMBOLS", 50),
        )
        
        logger.info(f"Initialized {len(services)} RAG patterns")
        return services

    except ImportError as e:
        logger.error(f"Failed to import RAG patterns: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize RAG patterns: {e}")
        raise

def initialize_orchestration(pattern_services: dict) -> tuple[Any, Any, Any]:
    """Initialize Orchestration components."""
    try:
        from app.services.rag_patterns.orchestration import (
            PatternRegistry,
            QueryAnalyzer,
            PatternOrchestrator,
            get_registry,
        )

        # Registry singleton
        registry = get_registry()
        
        # Log available patterns
        logger.info(f"Registry patterns: {[p.name for p in registry.list_patterns()]}")

        # Query Analyzer
        analyzer = QueryAnalyzer()

        # Orchestrator
        orchestrator = PatternOrchestrator(
            registry=registry,
            analyzer=analyzer,
        )
        
        return registry, analyzer, orchestrator

    except ImportError as e:
        logger.error(f"Failed to import orchestration: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize orchestration: {e}")
        raise

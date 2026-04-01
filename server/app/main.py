"""
FastAPI OCR Service - Main application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.jobs import job_store
from app.api.v1 import ocr, convert, jobs, rag, cloudcode, analytics, models, health
from app.api.v1 import api_router
from app.middleware.logging import RequestLoggingMiddleware, setup_logging
from app.middleware.error_handler import setup_error_handlers

# Configure structured logging
setup_logging(
    level="DEBUG" if settings.APP_ENV == "dev" else "INFO",
    json_format=settings.APP_ENV == "prod",
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting OCR Service...")
    logger.info(f"Storage directory: {settings.STORAGE_DIR}")
    logger.info(f"Default parser: {settings.DEFAULT_PARSER}")
    
    # Create storage directory
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize API Key Manager (enhanced with quota tracking)
    try:
        from app.services.auth.api_key_service import get_key_manager
        key_manager = get_key_manager()
        stats = key_manager.get_stats()
        logger.info(f"API Key Manager initialized: {stats}")
    except Exception as e:
        logger.warning(f"Could not initialize API Key Manager: {e}")
    
    # Initialize Cloud Code Manager and load accounts
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import init_cloudcode_manager
        cloudcode_manager = await init_cloudcode_manager()
        accounts = cloudcode_manager.list_accounts()
        logger.info(f"Cloud Code Manager initialized with {len(accounts)} accounts")
        for acc in accounts:
            best_model = acc.get_best_available_model()
            logger.info(f"  - {acc.email} ({acc.name}): best model = {best_model}")
    except Exception as e:
        logger.warning(f"Could not initialize Cloud Code Manager: {e}")
    
    # Start Health Monitor for periodic provider health checks
    try:
        from app.services.infrastructure.health_monitor import start_health_monitor
        from app.api.v1.health import set_startup_time
        set_startup_time()
        await start_health_monitor(interval=60)
        logger.info("Health Monitor started")
    except Exception as e:
        logger.warning(f"Could not start Health Monitor: {e}")
    
    # Register all services to ServiceRegistry for dependency injection
    try:
        from app.services.core.service_registry import register_all_services
        register_all_services()
        logger.info("ServiceRegistry: All services registered successfully")
    except Exception as e:
        logger.warning(f"Could not register services: {e}")
    
    # Pre-warm heavy services in a background thread so we don't block lifespan
    # FastAPI won't serve ANY requests until yield, so we must yield first
    import threading
    
    def _background_prewarm():
        """Load models in background thread - runs AFTER Uvicorn is serving."""
        import asyncio
        
        # 1. Pre-warm EmbeddingService (sentence-transformers model)
        try:
            from app.services.core.embedding_service import get_embedding_service
            logger.info("🔥 [Background] Pre-warming EmbeddingService...")
            emb_service = get_embedding_service()
            emb_service.ensure_model_loaded()
            logger.info("✅ [Background] EmbeddingService pre-warmed successfully")
        except Exception as e:
            logger.warning(f"⚠️ [Background] EmbeddingService pre-warm failed: {e}")
        
        # 2. Pre-warm RAGService
        try:
            from app.db.session import AsyncSessionLocal
            from app.services.core.rag import RAGService
            
            logger.info("🔥 [Background] Pre-warming RAGService...")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _warm_rag():
                    async with AsyncSessionLocal() as session:
                        await RAGService.get_instance(session)
                loop.run_until_complete(_warm_rag())
                logger.info("✅ [Background] RAGService pre-warmed successfully")
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"⚠️ [Background] RAGService pre-warm failed: {e}")
            logger.warning("First chat request will be slow due to cold start")
        
        logger.info("🎉 [Background] All pre-warming complete!")
    
    prewarm_thread = threading.Thread(target=_background_prewarm, daemon=True)
    prewarm_thread.start()
    
    yield
    
    # Stop Health Monitor
    try:
        from app.services.infrastructure.health_monitor import stop_health_monitor
        await stop_health_monitor()
        logger.info("Health Monitor stopped")
    except Exception:
        pass
    
    logger.info("Shutting down OCR Service...")
    # Cleanup jobs
    job_store.cleanup_all()


app = FastAPI(
    title="RAG-Anything OCR Service",
    description="""
## OCR and Document Processing Service with RAG Capabilities

### Features
- **OCR Processing**: Extract text from PDF, images, and documents using Docling
- **Document Conversion**: Convert documents to TXT, MD, JSON, PDF, DOCX, HTML, RTF
- **RAG Pipeline**: Retrieval-Augmented Generation for intelligent Q&A
- **Multi-Provider AI**: Cloud Code (FREE Claude/Gemini), DeepSeek, Gemini, Groq, Ollama
- **Smart Model Selection**: Auto-select best model based on quota and request type

### Authentication
All protected endpoints require JWT Bearer token in Authorization header.

### Rate Limiting
- Default: 100 requests/minute per user
- Auth endpoints: 10 requests/minute
- Upload endpoints: 20 requests/minute

### API Versioning
Current version: v1 (prefix: /api/v1)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Health", "description": "Health check and monitoring endpoints"},
        {"name": "Auth", "description": "Authentication and authorization"},
        {"name": "Workspaces", "description": "Workspace management"},
        {"name": "Documents", "description": "Document upload and management"},
        {"name": "Jobs", "description": "Background job management"},
        {"name": "Chat", "description": "Conversation and RAG queries"},
        {"name": "Models", "description": "AI model listing and selection"},
        {"name": "Cloud Code", "description": "Cloud Code account management"},
        {"name": "Analytics", "description": "Usage analytics and statistics"},
        {"name": "OCR", "description": "OCR processing endpoints"},
        {"name": "Convert", "description": "Document conversion endpoints"},
        {"name": "RAG", "description": "RAG pipeline endpoints"},
    ],
)

# Request logging middleware (added first = innermost)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting middleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware (added LAST = outermost in Starlette)
# This ensures ALL responses (including error 500) get CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up global error handlers
setup_error_handlers(app, debug=settings.APP_ENV == "dev")

# Include routers
app.include_router(api_router, prefix="/api/v1")  # Include all v1 API routes
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])
app.include_router(convert.router, prefix="/api/convert", tags=["Convert"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(cloudcode.router, prefix="/api/v1", tags=["Cloud Code"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(models.router, prefix="/api/v1", tags=["Models"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])

# OAuth for adding Google accounts (no Antigravity needed)
from app.api.v1 import oauth
app.include_router(oauth.router, prefix="/api/v1", tags=["OAuth"])

# RAG is always enabled
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    from app.core.ollama_client import check_ollama_connection
    
    ollama_reachable = False
    try:
        ollama_reachable = await check_ollama_connection()
    except Exception as e:
        logger.warning(f"Ollama connection check failed: {e}")
    
    # Check AI provider status
    ai_providers_status = {}
    if settings.AI_ENHANCEMENT_ENABLED:
        try:
            from app.services.infrastructure.ai_providers.manager import provider_manager as manager
            provider_statuses = await manager.get_provider_status()
            
            for name, status in provider_statuses.items():
                ai_providers_status[name] = {
                    "available": status.available,
                    "responseTimeMs": status.response_time_ms,
                    "supportsVision": status.supports_vision,
                    "quotaExceeded": status.quota_exceeded,
                    "unavailableReason": status.unavailable_reason
                }
        except Exception as e:
            logger.warning(f"Could not get AI provider status: {e}")
    
    # Get API Key Manager statistics (enhanced with quota tracking)
    api_key_stats = None
    try:
        from app.services.auth.api_key_service import get_key_manager
        km = get_key_manager()
        api_key_stats = km.get_stats()
    except Exception as e:
        logger.warning(f"Could not get API Key Manager stats: {e}")
    
    # Get Cloud Code Manager statistics
    cloudcode_stats = None
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        ccm = get_cloudcode_manager()
        cloudcode_stats = ccm.get_statistics()
    except Exception as e:
        logger.warning(f"Could not get Cloud Code Manager stats: {e}")
    
    return {
        "ok": True,
        "version": "1.0.0",
        "parserDefault": settings.DEFAULT_PARSER,
        "enableRag": True,  # RAG is always enabled
        "ollamaReachable": ollama_reachable,
        "aiEnhancementEnabled": settings.AI_ENHANCEMENT_ENABLED,
        "aiProviders": ai_providers_status if ai_providers_status else None,
        "apiKeyManager": api_key_stats,
        "cloudCode": cloudcode_stats,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_ENV == "dev"
    )
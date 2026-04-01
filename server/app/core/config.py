"""
Configuration settings
"""
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application settings
    APP_ENV: str = Field(default="dev", description="Application environment")
    HOST: str = Field(default="0.0.0.0", description="Host to bind to")
    PORT: int = Field(default=8000, description="Port to bind to")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:8080,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:8080,http://127.0.0.1:3000", description="CORS origins (comma-separated)")
    
    # Debug mode
    debug: bool = Field(default=False, description="Debug mode")
    
    # Database settings
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ragdb",
        description="PostgreSQL database URL"
    )
    
    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and job queue"
    )
    
    # MinIO/S3 settings
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_bucket: str = Field(default="rag-documents", description="MinIO bucket name")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")
    minio_external_endpoint: str = Field(default="", description="MinIO endpoint reachable by browser (e.g. localhost:9000). If empty, uses minio_endpoint.")
    
    # JWT settings (matching HealthCare config)
    jwt_secret_key: str = Field(default="jQ3h5dMJW6KpPZJ3+fFjV2Zs5cP1y4qZbmzZruXun9VdZFXmGx7X1A==", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_issuer: str = Field(default="https://localhost:8000", description="JWT issuer")
    jwt_audience: str = Field(default="rag-platform-api", description="JWT audience")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiry in minutes")
    refresh_token_expire_days: int = Field(default=14, description="Refresh token expiry in days")
    
    # SMTP Email settings (matching HealthCare config)
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_enable_ssl: bool = Field(default=True, description="Enable SSL for SMTP")
    smtp_user: str = Field(default="thehoang.acc@gmail.com", description="SMTP username")
    smtp_password: str = Field(default="gbyb eqvm wuau qhgb", description="SMTP password (app password)")
    smtp_from: str = Field(default="thehoang.acc@gmail.com", description="From email address")
    smtp_display_name: str = Field(default="RAG Platform", description="Display name for emails")
    
    # OTP settings (matching HealthCare config)
    otp_code_length: int = Field(default=6, description="OTP code length")
    otp_expire_minutes: int = Field(default=5, description="OTP expiry in minutes")
    otp_resend_cooldown_seconds: int = Field(default=60, description="OTP resend cooldown in seconds")
    otp_max_verify_attempts: int = Field(default=5, description="Max OTP verification attempts")
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=100, description="Rate limit per minute per user")
    
    # Storage settings
    STORAGE_DIR: Path = Field(default=Path("./storage"), description="Storage directory")
    
    # Parser settings
    DEFAULT_PARSER: str = Field(default="docling", description="Default parser (docling|mineru)")
    DEFAULT_PARSE_METHOD: str = Field(default="auto", description="Default parse method (auto|ocr|txt)")
    DEFAULT_LANG: str = Field(default="auto", description="Default language (auto|vi|en|...)")
    DEFAULT_DEVICE: str = Field(default="cpu", description="Default device (cpu|cuda|mps)")
    
    # Multimodal processing settings
    ENABLE_IMAGE_PROCESSING: bool = Field(default=True, description="Enable image content processing")
    ENABLE_TABLE_PROCESSING: bool = Field(default=True, description="Enable table content processing")
    ENABLE_EQUATION_PROCESSING: bool = Field(default=True, description="Enable equation content processing")
    
    # Batch processing settings
    MAX_CONCURRENT_FILES: int = Field(default=3, description="Max concurrent files in batch processing")
    RECURSIVE_FOLDER_PROCESSING: bool = Field(default=True, description="Recursively process subfolders")
    
    # Context extraction settings
    CONTEXT_WINDOW: int = Field(default=1, description="Number of pages/chunks for context")
    CONTEXT_MODE: str = Field(default="page", description="Context mode: page or chunk")
    MAX_CONTEXT_TOKENS: int = Field(default=2000, description="Max tokens in extracted context")
    INCLUDE_HEADERS: bool = Field(default=True, description="Include headers in context")
    INCLUDE_CAPTIONS: bool = Field(default=True, description="Include captions in context")
    
    # ==========================================================================
    # HYBRID RAG FEATURE FLAGS (Always enabled by default)
    # ==========================================================================
    # Phase 1: RAGAnything parsing (Graph RAG document processing)
    ENABLE_RAGANYTHING_PARSING: bool = Field(
        default=True, 
        description="Enable RAGAnything for document parsing (Graph RAG)"
    )
    # Phase 2: Hybrid retrieval (Graph + Vector + BM25)
    ENABLE_HYBRID_RAG: bool = Field(
        default=True, 
        description="Enable Hybrid RAG retrieval (Graph + Vector + BM25)"
    )
    # Phase 3: Memory management
    ENABLE_MEMORY_MANAGEMENT: bool = Field(
        default=True, 
        description="Enable conversation memory management"
    )
    # Hybrid RAG weights (for RRF fusion)
    HYBRID_RAG_GRAPH_WEIGHT: float = Field(default=0.4, description="Weight for Graph RAG results in RRF fusion")
    HYBRID_RAG_VECTOR_WEIGHT: float = Field(default=0.4, description="Weight for Vector RAG results in RRF fusion")
    HYBRID_RAG_BM25_WEIGHT: float = Field(default=0.2, description="Weight for BM25 keyword results in RRF fusion")
    
    # ==========================================================================
    # VECTOR DATABASE CONFIGURATION
    # ==========================================================================
    # Vector storage backend selection
    VECTOR_DB_TYPE: str = Field(
        default="pgvector",
        description="Vector database type: 'pgvector' (default) or 'qdrant'"
    )
    # Qdrant settings (for VECTOR_DB_TYPE=qdrant)
    QDRANT_URL: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL (local or cloud)"
    )
    QDRANT_API_KEY: str = Field(
        default="",
        description="Qdrant API key (required for Qdrant Cloud)"
    )
    QDRANT_COLLECTION_NAME: str = Field(
        default="rag_chunks",
        description="Qdrant collection name for storing chunks"
    )
    QDRANT_PREFER_GRPC: bool = Field(
        default=False,
        description="Use gRPC instead of HTTP for Qdrant"
    )
    
    # ==========================================================================
    # EMBEDDING MODEL CONFIGURATION
    # ==========================================================================
    # Embedding model selection
    EMBEDDING_MODEL: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="Embedding model name (sentence-transformers or custom)"
    )
    EMBEDDING_PROVIDER: str = Field(
        default="sentence-transformers",
        description="Embedding provider: 'sentence-transformers', 'ollama', 'openai'"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Embedding vector dimension"
    )
    # High-quality embedding models (alternatives)
    # BGE models - excellent for multilingual
    BGE_MODEL: str = Field(
        default="BAAI/bge-m3",
        description="BGE embedding model (multilingual, high quality)"
    )
    # E5 models - good balance of quality and speed
    E5_MODEL: str = Field(
        default="intfloat/multilingual-e5-large",
        description="E5 embedding model (multilingual)"
    )
    # OpenAI embeddings (requires API key)
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for embeddings"
    )
    
    # ==========================================================================
    # QUERY EXPANSION CONFIGURATION
    # ==========================================================================
    ENABLE_QUERY_EXPANSION: bool = Field(
        default=False,
        description="Enable query expansion (HyDE, rewriting)"
    )
    QUERY_EXPANSION_METHOD: str = Field(
        default="hyde",
        description="Query expansion method: 'hyde', 'rewriting', 'synonyms', 'none'"
    )
    
    # ==========================================================================
    # RERANKER CONFIGURATION
    # ==========================================================================
    ENABLE_RERANKING: bool = Field(
        default=False,
        description="Enable cross-encoder reranking after RRF fusion"
    )
    RERANKER_MODEL: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Cross-encoder model for reranking (multilingual)"
    )
    RERANKER_TOP_K: int = Field(
        default=10,
        description="Number of results to keep after reranking"
    )
    
    # Ollama settings
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434/api", description="Ollama API base URL")
    OLLAMA_LLM_MODEL: str = Field(default="qwen2.5:7b", description="Ollama LLM model")
    OLLAMA_EMBED_MODEL: str = Field(default="nomic-embed-text", description="Ollama embedding model")
    OLLAMA_VISION_MODEL: str = Field(default="llava:7b", description="Ollama vision model")
    
    # ==========================================================================
    # AI Enhancement settings
    AI_ENHANCEMENT_ENABLED: bool = Field(default=True, description="Enable AI enhancement of OCR results")
    AI_ENHANCEMENT_TIMEOUT: int = Field(default=30, description="Timeout for AI enhancement in seconds")
    AI_ENHANCEMENT_MAX_RETRIES: int = Field(default=2, description="Max retries for AI enhancement")
    AI_USE_VISION_WHEN_AVAILABLE: bool = Field(default=True, description="Use vision models when available")
    AI_PROVIDER_PRIORITY: str = Field(default="antigravity:0,cloudcode:1,deepseek:2,gemini:3,groq:4,ollama:10", description="Provider priority (name:priority) - strongest first")
    
    # ==========================================================================
    # FREE TIER PROVIDERS (with generous free quotas)
    # ==========================================================================
    
    # Groq settings (supports multiple keys separated by comma)
    # Get API key: https://console.groq.com/keys
    # Free tier: 14,400 requests/day
    GROQ_API_KEY: str = Field(default="", description="Groq API key(s) - comma separated for multiple")
    GROQ_API_KEYS: str = Field(default="", description="Additional Groq API keys (comma separated)")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Groq LLM model")
    GROQ_VISION_MODEL: str = Field(default="llama-3.2-90b-vision-preview", description="Groq vision model")
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1", description="Groq API base URL")
    
    # DeepSeek settings (supports multiple keys separated by comma)
    # Get API key: https://platform.deepseek.com/api_keys
    # Free tier: $5 credit for new accounts
    DEEPSEEK_API_KEY: str = Field(default="", description="DeepSeek API key(s) - comma separated for multiple")
    DEEPSEEK_API_KEYS: str = Field(default="", description="Additional DeepSeek API keys (comma separated)")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat", description="DeepSeek chat model")
    DEEPSEEK_CODER_MODEL: str = Field(default="deepseek-coder", description="DeepSeek coder model")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1", description="DeepSeek API base URL")
    
    # Gemini settings (supports multiple keys separated by comma)
    # Get API key: https://aistudio.google.com/apikey
    # Free tier: 1,500 requests/day
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key(s) - comma separated for multiple")
    GEMINI_API_KEYS: str = Field(default="", description="Additional Gemini API keys (comma separated)")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Gemini model")
    GEMINI_PRO_MODEL: str = Field(default="gemini-2.5-pro", description="Gemini Pro model")
    GEMINI_BASE_URL: str = Field(default="https://generativelanguage.googleapis.com/v1beta", description="Gemini API base URL")
    
    # ==========================================================================
    # IMAGE GENERATION PROVIDERS (FREE TIERS)
    # ==========================================================================
    
    # Together.ai - FLUX.1-schnell (STRONGEST FREE)
    # Get API key: https://api.together.xyz/
    # Free tier: 60 requests/minute
    TOGETHER_API_KEY: str = Field(default="", description="Together.ai API key(s) - comma separated")
    TOGETHER_API_KEYS: str = Field(default="", description="Additional Together.ai API keys")
    
    # Hugging Face - Stable Diffusion XL
    # Get token: https://huggingface.co/settings/tokens
    # Free tier: Rate limited
    HUGGINGFACE_API_KEY: str = Field(default="", description="Hugging Face token(s) - comma separated")
    HUGGINGFACE_API_KEYS: str = Field(default="", description="Additional Hugging Face tokens")
    
    # Stability AI - Stable Diffusion
    # Get API key: https://platform.stability.ai/
    # Free tier: 25 credits
    STABILITY_API_KEY: str = Field(default="", description="Stability AI API key(s) - comma separated")
    STABILITY_API_KEYS: str = Field(default="", description="Additional Stability AI API keys")
    
    # Prompt settings
    CUSTOM_PROMPTS_PATH: str = Field(default="./prompts", description="Path to custom prompt templates")
    DEFAULT_DOCUMENT_TYPE: str = Field(default="general", description="Default document type for prompts")
    
    # File constraints
    MAX_FILE_SIZE: int = Field(default=15 * 1024 * 1024, description="Max file size in bytes (15MB)")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[
            "pdf",
            "docx", "pptx", "xlsx",
            "jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp", "gif",
            "txt", "md", "csv", "html", "xhtml",
        ],
        description="Allowed file extensions (strict 17-type whitelist)"
    )
    
    # ==========================================================================
    # RAG PATTERNS CONFIGURATION
    # ==========================================================================
    
    # Speculative RAG Pattern
    SPECULATIVE_RAG_NUM_DRAFTS: int = Field(default=3, description="Number of parallel drafts for Speculative RAG")
    SPECULATIVE_RAG_SMALL_MODEL: str = Field(default="gpt-3.5-turbo", description="Small model for draft generation")
    SPECULATIVE_RAG_LARGE_MODEL: str = Field(default="gpt-4", description="Large model for verification")
    SPECULATIVE_RAG_TEMPERATURE: float = Field(default=0.7, description="Temperature for draft generation")
    SPECULATIVE_RAG_ENABLE_MERGING: bool = Field(default=False, description="Enable draft merging")
    
    # CORAL Pattern (Conversational RAG)
    CORAL_MAX_HISTORY_TURNS: int = Field(default=10, description="Maximum conversation history turns")
    CORAL_CONTEXT_WINDOW_SIZE: int = Field(default=4096, description="Context window size for CORAL")
    CORAL_USE_CONTEXT_ENHANCEMENT: bool = Field(default=True, description="Enable context enhancement")
    CORAL_MAX_CONTEXT_TURNS: int = Field(default=3, description="Max context turns for retrieval")
    
    # REVEAL Pattern (Visual-Language RAG)
    REVEAL_ENABLED: bool = Field(default=True, description="Enable REVEAL multimodal pattern")
    REVEAL_FUSION_STRATEGY: str = Field(default="hybrid", description="Fusion strategy: early, late, or hybrid")
    REVEAL_VISUAL_WEIGHT: float = Field(default=0.4, description="Weight for visual information (0-1)")
    REVEAL_TEXT_WEIGHT: float = Field(default=0.6, description="Weight for text information (0-1)")
    REVEAL_ATTENTION_ENABLED: bool = Field(default=True, description="Enable attention mechanism")
    REVEAL_TOP_K: int = Field(default=5, description="Number of top results to retrieve")
    
    # ==========================================================================
    # SERVICE INTEGRATION FEATURE FLAGS
    # ==========================================================================
    
    # Function Calling Service
    ENABLE_FUNCTION_CALLING: bool = Field(
        default=True,
        description="Enable function calling for metadata queries"
    )
    FUNCTION_CALLING_TIMEOUT_MS: int = Field(
        default=500,
        description="Timeout for function calling detection and execution (milliseconds)"
    )
    
    # Timeline Service
    ENABLE_TIMELINE_SERVICE: bool = Field(
        default=True,
        description="Enable timeline context enrichment around citations"
    )
    TIMELINE_DEPTH_BEFORE: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of chunks before anchor in timeline"
    )
    TIMELINE_DEPTH_AFTER: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of chunks after anchor in timeline"
    )
    TIMELINE_SAME_DOCUMENT: bool = Field(
        default=True,
        description="Restrict timeline to same document as anchor chunk"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()

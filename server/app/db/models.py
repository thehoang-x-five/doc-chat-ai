"""
SQLAlchemy models for Hybrid RAG Platform.
All entities: User, Workspace, Document, Chunk, Job, Conversation, Message, Citation, AIUsage
"""
import uuid as uuid_module
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey, 
    Index, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# =============================================================================
# USER & AUTHENTICATION MODELS
# =============================================================================

class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role_global: Mapped[str] = mapped_column(String(50), default="USER")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    workspaces: Mapped[List["WorkspaceUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    owned_workspaces: Mapped[List["Workspace"]] = relationship(
        back_populates="owner", foreign_keys="Workspace.owner_id"
    )


class RefreshToken(Base):
    """Refresh token for JWT authentication."""
    __tablename__ = "refresh_tokens"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    user_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


# =============================================================================
# WORKSPACE MODELS
# =============================================================================

class Workspace(Base):
    """Workspace for organizing documents and team collaboration."""
    __tablename__ = "workspaces"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(50), default="free")
    answer_policy: Mapped[str] = mapped_column(String(20), default="balanced")
    evidence_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    owner: Mapped["User"] = relationship(
        back_populates="owned_workspaces", foreign_keys=[owner_id]
    )
    members: Mapped[List["WorkspaceUser"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    categories: Mapped[List["DocumentCategory"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    ai_usages: Mapped[List["AIUsage"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceUser(Base):
    """Many-to-many relationship between workspaces and users with roles."""
    __tablename__ = "workspace_users"
    
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), default="VIEWER")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="workspaces")


# =============================================================================
# DOCUMENT CATEGORY MODEL
# =============================================================================

class DocumentCategory(Base):
    """
    Category for organizing documents by topic/theme.
    Auto-generated by LLM based on document content.
    """
    __tablename__ = "document_categories"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # AI-generated summary of category content for intent detection
    content_summary: Mapped[Optional[str]] = mapped_column(Text)
    # Main topics/keywords in this category
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])
    # Icon/color for UI
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(String(20))
    # Order for display
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    # Auto-generated or manually created
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="categories")
    documents: Mapped[List["Document"]] = relationship(back_populates="category")
    
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_category_workspace_slug"),
        Index("idx_category_workspace", "workspace_id"),
    )


# =============================================================================
# DOCUMENT MODELS
# =============================================================================

class Document(Base):
    """Document metadata and status tracking."""
    __tablename__ = "documents"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    # Category for organizing documents
    category_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_categories.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    # Processing progress (0-100) for background processing UI
    processing_progress: Mapped[int] = mapped_column(Integer, default=0)
    # Current processing step description
    processing_step: Mapped[Optional[str]] = mapped_column(String(500))
    # AI-generated summary of document content
    content_summary: Mapped[Optional[str]] = mapped_column(Text)
    # Main headings extracted from document
    main_headings: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])
    created_by: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    category: Mapped[Optional["DocumentCategory"]] = relationship(back_populates="documents")
    versions: Mapped[List["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_documents_workspace_status", "workspace_id", "status"),
        Index("idx_documents_category", "category_id"),
    )


class DocumentVersion(Base):
    """Version of a document with parsing outputs."""
    __tablename__ = "document_versions"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    document_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    original_file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    parser: Mapped[str] = mapped_column(String(50), default="docling")
    parse_method: Mapped[str] = mapped_column(String(20), default="auto")
    language_detected: Mapped[Optional[str]] = mapped_column(String(10))
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    extracted_text_key: Mapped[Optional[str]] = mapped_column(String(500))
    extracted_md_key: Mapped[Optional[str]] = mapped_column(String(500))
    structured_json_key: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    document: Mapped["Document"] = relationship(back_populates="versions")
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship(back_populates="document_version")
    
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
    )


class Chunk(Base):
    """Text chunk with embedding for vector search."""
    __tablename__ = "chunks"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    document_version_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    page_start: Mapped[Optional[int]] = mapped_column(Integer)
    page_end: Mapped[Optional[int]] = mapped_column(Integer)
    bbox_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    section_title: Mapped[Optional[str]] = mapped_column(String(500))
    hash: Mapped[Optional[str]] = mapped_column(String(64))
    
    # NEW: Structured metadata fields for better search/prompting
    chunk_type: Mapped[Optional[str]] = mapped_column(String(50), default="text")  # text, code, table, heading
    entities: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])  # Extracted entities
    topics: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])  # Main topics/tags
    summary: Mapped[Optional[str]] = mapped_column(String(500))  # 1-sentence summary
    importance_score: Mapped[Optional[float]] = mapped_column(Float, default=0.5)  # 0-1 relevance score
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    citations: Mapped[List["Citation"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    embeddings: Mapped[List["ChunkEmbedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_chunk_index"),
        Index("idx_chunks_doc_version", "document_version_id"),
    )



# Add embedding column conditionally (pgvector may not be available)
if PGVECTOR_AVAILABLE and Vector is not None:
    Chunk.embedding = mapped_column(Vector(768), nullable=True)


# =============================================================================
# JOB MODELS
# =============================================================================

class Job(Base):
    """Background job for OCR, indexing, conversion."""
    __tablename__ = "jobs"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    step: Mapped[str] = mapped_column(String(100), default="queued")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="jobs")
    document_version: Mapped[Optional["DocumentVersion"]] = relationship(back_populates="jobs")
    ai_usages: Mapped[List["AIUsage"]] = relationship(back_populates="job")
    
    __table_args__ = (
        Index("idx_jobs_workspace_status", "workspace_id", "status"),
        Index("idx_jobs_status", "status"),
    )


# =============================================================================
# CONVERSATION & MESSAGE MODELS
# =============================================================================

class Conversation(Base):
    """Chat conversation/session."""
    __tablename__ = "conversations"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(500))
    # Scope tags for filtering documents in RAG retrieval
    # Empty array = search all documents in workspace
    # Non-empty = only search documents with matching tags
    scope_tags: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])
    created_by: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_conversations_workspace", "workspace_id"),
    )


class Message(Base):
    """Chat message with RAG metadata."""
    __tablename__ = "messages"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    conversation_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    policy_mode: Mapped[Optional[str]] = mapped_column(String(20))
    best_retrieval_score: Mapped[Optional[float]] = mapped_column(Float)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    citations: Mapped[List["Citation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    ai_usages: Mapped[List["AIUsage"]] = relationship(back_populates="message")
    
    __table_args__ = (
        Index("idx_messages_conversation", "conversation_id"),
    )


class Citation(Base):
    """Link between message and source chunk."""
    __tablename__ = "citations"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    message_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    quote: Mapped[Optional[str]] = mapped_column(Text)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    message: Mapped["Message"] = relationship(back_populates="citations")
    chunk: Mapped["Chunk"] = relationship(back_populates="citations")


# =============================================================================
# AI USAGE TRACKING
# =============================================================================

class AIUsage(Base):
    """Track AI provider usage for analytics and billing."""
    __tablename__ = "ai_usage"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    message_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="ai_usages")
    job: Mapped[Optional["Job"]] = relationship(back_populates="ai_usages")
    message: Mapped[Optional["Message"]] = relationship(back_populates="ai_usages")
    
    __table_args__ = (
        Index("idx_ai_usage_workspace", "workspace_id"),
        Index("idx_ai_usage_created", "created_at"),
    )


# =============================================================================
# ENUMS (for reference, actual validation in Pydantic schemas)
# =============================================================================

class UserRole:
    ADMIN = "ADMIN"
    USER = "USER"


class WorkspaceRole:
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class DocumentStatus:
    UPLOADING = "UPLOADING"
    NEW = "NEW"
    INDEXING = "INDEXING"
    READY = "READY"
    READY_BASIC = "READY_BASIC"        # Searchable (after index, before enrichment)
    READY_ENRICHED = "READY_ENRICHED"  # Fully enriched (after RAG-Anything)
    FAILED = "FAILED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
    CANCELED = "CANCELED"


class JobType:
    OCR = "OCR"
    INDEX = "INDEX"
    CONVERT = "CONVERT"
    ENRICHMENT = "ENRICHMENT"


class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"
    CANCELED = "CANCELED"


class AnswerPolicy:
    STRICT = "strict"
    BALANCED = "balanced"
    OPEN = "open"


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# =============================================================================
# EMBEDDING MODEL REGISTRY
# =============================================================================

class EmbeddingModel(Base):
    """Registry of embedding models with their configurations."""
    __tablename__ = "embedding_models"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # sentence-transformers, ollama, openai
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    embeddings: Mapped[List["ChunkEmbedding"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ChunkEmbedding(Base):
    """Embedding vector for a chunk, linked to specific model version."""
    __tablename__ = "chunk_embeddings"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    chunk_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    embedding_model_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("embedding_models.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    chunk: Mapped["Chunk"] = relationship(back_populates="embeddings")
    model: Mapped["EmbeddingModel"] = relationship(back_populates="embeddings")
    
    __table_args__ = (
        UniqueConstraint("chunk_id", "embedding_model_id", name="uq_chunk_embedding_model"),
        Index("idx_chunk_embeddings_model", "embedding_model_id"),
        Index("idx_chunk_embeddings_chunk", "chunk_id"),
    )


# Add embedding column to ChunkEmbedding conditionally (pgvector may not be available)
if PGVECTOR_AVAILABLE and Vector is not None:
    ChunkEmbedding.embedding = mapped_column(Vector(768), nullable=False)


class EmbeddingProvider:
    """Embedding provider types."""
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    OLLAMA = "ollama"
    OPENAI = "openai"


# =============================================================================
# EXTRACTION TEMPLATE MODELS
# =============================================================================

class ExtractionTemplate(Base):
    """Template for extracting structured data from documents."""
    __tablename__ = "extraction_templates"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # Fields definition stored as JSON array
    fields_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=[])
    created_by: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    results: Mapped[List["ExtractionResult"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_extraction_templates_workspace", "workspace_id"),
    )


class ExtractionResult(Base):
    """Result of extracting data from a document using a template."""
    __tablename__ = "extraction_results"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_templates.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # Extracted fields stored as JSON array
    fields_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=[])
    overall_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    fields_extracted: Mapped[int] = mapped_column(Integer, default=0)
    fields_failed: Mapped[int] = mapped_column(Integer, default=0)
    fields_need_review: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    template: Mapped["ExtractionTemplate"] = relationship(back_populates="results")
    document: Mapped["Document"] = relationship(foreign_keys=[document_id])
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_extraction_results_workspace", "workspace_id"),
        Index("idx_extraction_results_template", "template_id"),
        Index("idx_extraction_results_document", "document_id"),
    )


# =============================================================================
# SUMMARY MODELS
# =============================================================================

class ConversationSummary(Base):
    """Long-term memory summary for a conversation."""
    __tablename__ = "conversation_summaries"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    conversation_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    messages_summarized: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(foreign_keys=[conversation_id])
    
    __table_args__ = (
        Index("idx_conversation_summaries_conversation", "conversation_id"),
    )


class Summary(Base):
    """Generated summary with audience/format options."""
    __tablename__ = "summaries"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    # Document IDs stored as JSON array
    document_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="general")
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="paragraph")
    language: Mapped[str] = mapped_column(String(10), default="en")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Citations stored as JSON array
    citations_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=[])
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_topics: Mapped[Optional[list]] = mapped_column(ARRAY(String), default=[])
    created_by: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_summaries_workspace", "workspace_id"),
    )


# =============================================================================
# FUNCTION CALLING MODELS
# =============================================================================

class FunctionCallLog(Base):
    """Log of function calls made by LLM during conversations.
    
    Requirements: 6.3
    """
    __tablename__ = "function_calls"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    message_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    workspace_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    function_name: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    message: Mapped[Optional["Message"]] = relationship(foreign_keys=[message_id])
    
    __table_args__ = (
        Index("idx_function_calls_message", "message_id"),
        Index("idx_function_calls_workspace", "workspace_id"),
        Index("idx_function_calls_status", "status"),
        Index("idx_function_calls_created", "created_at"),
    )


class FunctionCallStatus:
    """Function call status types."""
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


# =============================================================================
# MEMORI-STYLE MEMORY MODELS (Entity Facts, Semantic Triples, Sessions)
# Copied from Memori project for advanced memory management
# =============================================================================

class MemoriEntity(Base):
    """Entity for storing user/topic information with facts.
    
    Copied from Memori: Represents a unique entity (user, topic, etc.)
    that can have associated facts and knowledge graph relationships.
    """
    __tablename__ = "memori_entities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    workspace_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    facts: Mapped[List["MemoriEntityFact"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    knowledge_graph: Mapped[List["MemoriKnowledgeGraph"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["MemoriSession"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    preferences: Mapped[List["MemoriEntityPreference"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    attributes: Mapped[List["MemoriEntityAttribute"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_memori_entities_workspace", "workspace_id"),
    )


class MemoriEntityFact(Base):
    """Facts about an entity with embeddings for semantic search.
    
    Copied from Memori: Stores extracted facts about entities
    with vector embeddings for similarity search.
    """
    __tablename__ = "memori_entity_facts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_entities.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as binary (LargeBinary) for FAISS compatibility
    content_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    conversation_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    importance_score: Mapped[float] = mapped_column(Float, default=1.0)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    entity: Mapped["MemoriEntity"] = relationship(back_populates="facts")
    
    __table_args__ = (
        Index("idx_memori_entity_facts_entity", "entity_id"),
        Index("idx_memori_entity_facts_importance", "importance_score"),
    )


class MemoriEntityPreference(Base):
    """User preferences (UI, language, format, etc.)
    
    Phase 2 Enhancement: Stores user preferences extracted from conversations.
    Examples: dark mode, language preference, response format, etc.
    """
    __tablename__ = "memori_entity_preferences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_entities.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # ui, language, format, etc.
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    preference_value: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=8.0)  # High importance for preferences
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    entity: Mapped["MemoriEntity"] = relationship(back_populates="preferences")
    
    __table_args__ = (
        Index("idx_memori_preferences_entity_id", "entity_id"),
        Index("idx_memori_preferences_category", "category"),
        Index("idx_memori_preferences_key", "preference_key"),
    )


class MemoriEntityAttribute(Base):
    """Entity attributes (role, skills, location, etc.)
    
    Phase 2 Enhancement: Stores entity attributes extracted from conversations.
    Examples: job role, programming skills, location, expertise areas, etc.
    """
    __tablename__ = "memori_entity_attributes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_entities.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # role, skill, location, etc.
    attribute_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    attribute_value: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=7.0)  # Medium-high importance
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    entity: Mapped["MemoriEntity"] = relationship(back_populates="attributes")
    
    __table_args__ = (
        Index("idx_memori_attributes_entity_id", "entity_id"),
        Index("idx_memori_attributes_category", "category"),
        Index("idx_memori_attributes_key", "attribute_key"),
    )


class MemoriKnowledgeGraph(Base):
    """Semantic triples for knowledge graph.
    
    Copied from Memori: Stores Subject-Predicate-Object relationships
    extracted from conversations.
    
    Temporal Model (inspired by Graphiti):
    - created_at: When the triple was added to the system
    - valid_at: When the fact became true in reality
    - invalid_at: When the fact stopped being true in reality
    - expired_at: When the triple was invalidated by a contradiction
    """
    __tablename__ = "memori_knowledge_graph"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_entities.id", ondelete="CASCADE"), nullable=False
    )
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_type: Mapped[Optional[str]] = mapped_column(String(100))
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type: Mapped[Optional[str]] = mapped_column(String(100))
    conversation_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    
    # Temporal fields (Graphiti-inspired bi-temporal model)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the fact became true in reality"
    )
    invalid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the fact stopped being true in reality"
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the triple was invalidated by a contradiction"
    )
    
    # Relationships
    entity: Mapped["MemoriEntity"] = relationship(back_populates="knowledge_graph")
    
    __table_args__ = (
        Index("idx_memori_kg_entity", "entity_id"),
        Index("idx_memori_kg_subject", "subject_name"),
        Index("idx_memori_kg_object", "object_name"),
    )


class MemoriProcess(Base):
    """Process/workflow tracking.
    
    Copied from Memori: Tracks processes/workflows with attributes.
    """
    __tablename__ = "memori_processes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    workspace_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    attributes: Mapped[List["MemoriProcessAttribute"]] = relationship(
        back_populates="process", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["MemoriSession"]] = relationship(
        back_populates="process", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_memori_processes_workspace", "workspace_id"),
    )


class MemoriProcessAttribute(Base):
    """Attributes for a process.
    
    Copied from Memori: Stores attributes extracted from process workflows.
    """
    __tablename__ = "memori_process_attributes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    process_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_processes.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    process: Mapped["MemoriProcess"] = relationship(back_populates="attributes")
    
    __table_args__ = (
        Index("idx_memori_process_attrs_process", "process_id"),
    )


class MemoriSession(Base):
    """Session management with timeout support.
    
    Copied from Memori: Tracks sessions with entity/process associations
    and timeout management.
    """
    __tablename__ = "memori_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("memori_entities.id", ondelete="SET NULL")
    )
    process_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("memori_processes.id", ondelete="SET NULL")
    )
    workspace_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    entity: Mapped[Optional["MemoriEntity"]] = relationship(back_populates="sessions")
    process: Mapped[Optional["MemoriProcess"]] = relationship(back_populates="sessions")
    conversations: Mapped[List["MemoriConversation"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_memori_sessions_workspace", "workspace_id"),
        Index("idx_memori_sessions_last_activity", "last_activity_at"),
    )


class MemoriConversation(Base):
    """Memori-style conversation with session timeout support.
    
    Copied from Memori: Links to session and tracks conversation summary.
    """
    __tablename__ = "memori_conversations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # Link to existing conversation model
    conversation_id: Mapped[Optional[uuid_module.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    session: Mapped["MemoriSession"] = relationship(back_populates="conversations")
    messages: Mapped[List["MemoriConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_memori_conversations_session", "session_id"),
    )


class MemoriConversationMessage(Base):
    """Message in a Memori conversation.
    
    Copied from Memori: Stores messages with role and type information.
    """
    __tablename__ = "memori_conversation_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memori_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    message_type: Mapped[Optional[str]] = mapped_column(String(50))  # text, tool_call, etc.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    conversation: Mapped["MemoriConversation"] = relationship(back_populates="messages")
    
    __table_args__ = (
        Index("idx_memori_conv_messages_conversation", "conversation_id"),
    )


# =============================================================================
# PATTERN ORCHESTRATION MODELS
# =============================================================================

class PatternFeedback(Base):
    """User feedback for RAG pattern responses.
    
    Stores likes, dislikes, reports, and edits to improve pattern routing.
    """
    __tablename__ = "pattern_feedback"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_used: Mapped[str] = mapped_column(String(100), nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="all")
    
    # Feedback details
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)  # like, dislike, edit, report
    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 rating
    comment: Mapped[Optional[str]] = mapped_column(Text)
    issue_type: Mapped[Optional[str]] = mapped_column(String(50))  # hallucination, irrelevant, etc.
    
    # Response data
    response_text: Mapped[Optional[str]] = mapped_column(Text)
    edited_response: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_pattern_feedback_pattern", "pattern_used"),
        Index("idx_pattern_feedback_type", "feedback_type"),
        Index("idx_pattern_feedback_created", "created_at"),
    )


class PatternMetricsAggregate(Base):
    """Aggregated metrics for pattern performance.
    
    Stores pre-computed statistics for fast querying.
    """
    __tablename__ = "pattern_metrics"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="all")
    
    # Latency metrics
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p50_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p99_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Quality metrics
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Cost metrics
    avg_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Sample info
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    time_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        UniqueConstraint("pattern_name", "query_type", "time_window_start", name="uq_pattern_metrics_window"),
        Index("idx_pattern_metrics_pattern", "pattern_name"),
        Index("idx_pattern_metrics_time", "time_window_start"),
    )


class RoutingAdjustmentRecord(Base):
    """Record of routing priority adjustments.
    
    Tracks changes to pattern routing based on feedback analysis.
    """
    __tablename__ = "routing_adjustments"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    adjustment_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="all")
    
    # Priority change
    old_priority: Mapped[float] = mapped_column(Float, nullable=False)
    new_priority: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, testing, promoted, rejected
    
    # A/B testing
    test_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    test_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    test_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    test_results_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_routing_adjustments_pattern", "pattern_name"),
        Index("idx_routing_adjustments_status", "status"),
    )


class MetaPatternUsage(Base):
    """Usage log for meta-pattern executions.
    
    Tracks composite pattern executions for optimization.
    """
    __tablename__ = "meta_pattern_usage"
    
    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4
    )
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    meta_pattern_id: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Execution details
    patterns_executed: Mapped[list] = mapped_column(ARRAY(String), default=[])
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Node-level metrics
    node_metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_meta_pattern_usage_meta_pattern", "meta_pattern_id"),
        Index("idx_meta_pattern_usage_created", "created_at"),
    )


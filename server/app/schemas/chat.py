"""
Pydantic schemas for chat/conversation endpoints.
"""
from datetime import datetime
from typing import List, Optional, Dict
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# CONVERSATION SCHEMAS
# =============================================================================

class ConversationCreate(BaseModel):
    """Request to create a conversation."""
    title: Optional[str] = Field(None, max_length=500)
    scope_tags: Optional[List[str]] = Field(
        None, 
        description="Tags to filter documents for RAG. Empty = search all documents in workspace"
    )


class ConversationUpdate(BaseModel):
    """Request to update a conversation."""
    title: Optional[str] = Field(None, max_length=500)
    scope_tags: Optional[List[str]] = Field(
        None,
        description="Tags to filter documents for RAG. Empty = search all documents in workspace"
    )


class ConversationResponse(BaseModel):
    """Conversation response."""
    id: UUID
    workspace_id: UUID
    title: Optional[str]
    scope_tags: Optional[List[str]] = []
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    message_count: int = 0
    
    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    """List of conversations."""
    items: List[ConversationResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# CITATION SCHEMAS
# =============================================================================

class CitationResponse(BaseModel):
    """Citation in a message."""
    id: UUID
    chunk_id: UUID
    document_id: Optional[UUID] = None
    document_title: Optional[str] = None
    score: float
    quote: Optional[str]
    page: Optional[int]
    
    model_config = {"from_attributes": True}


# =============================================================================
# MESSAGE SCHEMAS
# =============================================================================

class MessageCreate(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=10000)
    document_ids: Optional[List[UUID]] = Field(None, description="Filter by document IDs")
    tags: Optional[List[str]] = Field(None, description="Filter by document tags (overrides conversation scope_tags)")
    model: Optional[str] = Field(None, description="Specific model to use (e.g., 'claude-sonnet-4-5')")
    has_image: bool = Field(False, description="Whether the request contains an image")


class MessageResponse(BaseModel):
    """Message response."""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    provider: Optional[str]
    model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    latency_ms: Optional[int]
    policy_mode: Optional[str]
    best_retrieval_score: Optional[float]
    fallback_used: bool = False
    citations: List[CitationResponse] = []
    context_stats: Optional[Dict[str, int]] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """List of messages."""
    items: List[MessageResponse]
    conversation_id: UUID


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    user_message: MessageResponse
    assistant_message: MessageResponse


# =============================================================================
# STATELESS QUERY SCHEMAS
# =============================================================================

class StatelessQueryRequest(BaseModel):
    """Request for stateless RAG query."""
    question: str = Field(..., min_length=1, max_length=10000)
    workspace_id: UUID
    document_ids: Optional[List[UUID]] = Field(None, description="Filter by document IDs")
    tags: Optional[List[str]] = Field(None, description="Filter by document tags")
    top_k: int = Field(5, ge=1, le=20)
    model: Optional[str] = Field(None, description="Specific model to use (e.g., 'claude-sonnet-4-5')")
    has_image: bool = Field(False, description="Whether the request contains an image")
    rag_only: bool = Field(False, description="If true, only answer from documents, no LLM fallback")
    # Image input support
    image_data: Optional[str] = Field(None, description="Base64 encoded image data")
    image_mime_type: Optional[str] = Field("image/jpeg", description="MIME type of the image")
    # Contextual streaming support
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID for contextual streaming")


class DirectChatRequest(BaseModel):
    """Request for direct LLM chat without RAG."""
    question: str = Field(..., min_length=1, max_length=10000)
    model: Optional[str] = Field(None, description="Specific model to use")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    max_tokens: int = Field(2048, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0, le=2)
    # Image input support
    image_data: Optional[str] = Field(None, description="Base64 encoded image data")
    image_mime_type: Optional[str] = Field("image/jpeg", description="MIME type of the image")


class DirectChatResponse(BaseModel):
    """Response for direct LLM chat."""
    answer: str
    model: str
    provider: str
    latency_ms: int
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    # Image generation fields
    images: Optional[List[str]] = Field(None, description="Base64 encoded images if image generation was requested")
    is_image_response: bool = Field(False, description="Whether this response contains generated images")


class StatelessQueryCitation(BaseModel):
    """Citation in stateless query response."""
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    page: Optional[int]
    quote: Optional[str]


class PolicyEvaluationResponse(BaseModel):
    """Policy evaluation details."""
    policy: str
    threshold: float
    best_score: float
    should_answer: bool
    is_grounded: bool
    is_fallback: bool
    disclaimer: Optional[str]


class StatelessQueryResponse(BaseModel):
    """Response for stateless RAG query."""
    answer: str
    citations: List[StatelessQueryCitation]
    policy_evaluation: PolicyEvaluationResponse
    provider: Optional[str]
    model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    latency_ms: Optional[int]
    # Image generation support
    images: Optional[List[str]] = Field(None, description="Base64 encoded images if image generation was requested")
    is_image_response: bool = Field(False, description="Whether this response contains generated images")
    # Function calling support
    tool_calls_made: Optional[List[Dict]] = Field(None, description="Tools that were called to answer the question")


# =============================================================================
# CONVERSATION STATS
# =============================================================================

class ConversationStatsResponse(BaseModel):
    """Statistics for a conversation."""
    conversation_id: UUID
    total_messages: int
    user_messages: int
    assistant_messages: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_latency_ms: int
    fallback_count: int

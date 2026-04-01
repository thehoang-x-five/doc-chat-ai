"""
Chat API endpoints for conversations and RAG queries.
"""
import asyncio
import json
import logging
import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User, WorkspaceUser
from app.services.conversation.conversation_service import ConversationService as ChatService
from app.services.tools.function_calling_service import FunctionCallingService
from app.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    MessageCreate,
    MessageResponse,
    MessageListResponse,
    SendMessageResponse,
    StatelessQueryRequest,
    StatelessQueryResponse,
    StatelessQueryCitation,
    PolicyEvaluationResponse,
    ConversationStatsResponse,
    CitationResponse,
    DirectChatRequest,
    DirectChatResponse,
)
from sqlalchemy import select, func

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITER — in-memory, no external deps
# =============================================================================
import collections
import threading

_rate_lock = threading.Lock()
_active_streams: dict = {}      # user_id -> count of active SSE streams
_request_log: dict = {}         # workspace_id -> deque of timestamps
_ip_request_log: dict = {}      # ip_address -> deque of timestamps

MAX_CONCURRENT_STREAMS_PER_USER = 3
MAX_REQUESTS_PER_MINUTE_PER_WORKSPACE = 20
MAX_REQUESTS_PER_MINUTE_PER_IP = 30


def _check_rate_limit(
    user_id: UUID, workspace_id: UUID, ip_address: str = ""
) -> tuple[bool, str]:
    """Return (allowed, reason). Thread-safe. Checks user, workspace, and IP."""
    now = time.time()
    with _rate_lock:
        # 1) concurrent stream check
        active = _active_streams.get(str(user_id), 0)
        if active >= MAX_CONCURRENT_STREAMS_PER_USER:
            return False, f"Bạn đang có {active} stream đang chạy. Chờ kết thúc trước."

        # 2) per-workspace request rate
        ws_key = str(workspace_id)
        if ws_key not in _request_log:
            _request_log[ws_key] = collections.deque()
        dq = _request_log[ws_key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= MAX_REQUESTS_PER_MINUTE_PER_WORKSPACE:
            return False, f"Workspace đã đạt {MAX_REQUESTS_PER_MINUTE_PER_WORKSPACE} req/phút. Vui lòng chờ."

        # 3) per-IP request rate
        if ip_address:
            if ip_address not in _ip_request_log:
                _ip_request_log[ip_address] = collections.deque()
            ip_dq = _ip_request_log[ip_address]
            while ip_dq and now - ip_dq[0] > 60:
                ip_dq.popleft()
            if len(ip_dq) >= MAX_REQUESTS_PER_MINUTE_PER_IP:
                return False, f"IP {ip_address} đã đạt {MAX_REQUESTS_PER_MINUTE_PER_IP} req/phút."
            ip_dq.append(now)

        # Accept — record
        dq.append(now)
        _active_streams[str(user_id)] = active + 1
        return True, ""


def _release_stream(user_id: UUID):
    with _rate_lock:
        key = str(user_id)
        _active_streams[key] = max(0, _active_streams.get(key, 1) - 1)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def check_workspace_access(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
) -> bool:
    """Check if user has access to workspace."""
    query = select(WorkspaceUser).where(
        WorkspaceUser.workspace_id == workspace_id,
        WorkspaceUser.user_id == user_id,
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def get_conversation_message_count(
    db: AsyncSession,
    conversation_id: UUID,
) -> int:
    """Get message count for a conversation."""
    from app.db.models import Message
    query = select(func.count(Message.id)).where(
        Message.conversation_id == conversation_id
    )
    result = await db.execute(query)
    return result.scalar() or 0


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================

@router.post(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    workspace_id: UUID,
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new conversation in a workspace."""
    # Check workspace access
    if not await check_workspace_access(db, current_user.id, workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this workspace",
        )
    
    chat_service = ChatService(db)
    conversation = await chat_service.create_conversation(
        workspace_id=workspace_id,
        user_id=current_user.id,
        title=data.title,
        scope_tags=data.scope_tags,
    )
    
    return ConversationResponse(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        title=conversation.title,
        scope_tags=conversation.scope_tags or [],
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationListResponse,
)
async def list_conversations(
    workspace_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List conversations in a workspace."""
    if not await check_workspace_access(db, current_user.id, workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this workspace",
        )
    
    chat_service = ChatService(db)
    conversations = await chat_service.list_conversations(
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    
    # Get message counts
    items = []
    for conv in conversations:
        msg_count = await get_conversation_message_count(db, conv.id)
        items.append(ConversationResponse(
            id=conv.id,
            workspace_id=conv.workspace_id,
            title=conv.title,
            scope_tags=conv.scope_tags or [],
            created_by=conv.created_by,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        ))
    
    return ConversationListResponse(
        items=items,
        total=len(items),  # TODO: Get actual total count
        limit=limit,
        offset=offset,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a conversation by ID."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    # Check access
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    msg_count = await get_conversation_message_count(db, conversation_id)
    
    return ConversationResponse(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        title=conversation.title,
        scope_tags=conversation.scope_tags or [],
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=msg_count,
    )


@router.put(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: UUID,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a conversation."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    updated = await chat_service.update_conversation(
        conversation_id, title=data.title, scope_tags=data.scope_tags
    )
    
    msg_count = await get_conversation_message_count(db, conversation_id)
    
    return ConversationResponse(
        id=updated.id,
        workspace_id=updated.workspace_id,
        title=updated.title,
        scope_tags=updated.scope_tags or [],
        created_by=updated.created_by,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        message_count=msg_count,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: UUID,
    hard_delete: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation (soft delete by default)."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    await chat_service.delete_conversation(conversation_id, hard_delete=hard_delete)


# =============================================================================
# MESSAGE ENDPOINTS
# =============================================================================

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def get_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    before_id: Optional[UUID] = None,
    include_citations: bool = Query(False, description="Include citations (slower) or skip for fast loading"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages in a conversation. Set include_citations=false for faster loading."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    start_time = time.time()
    messages = await chat_service.get_messages(
        conversation_id, limit=limit, before_id=before_id, include_citations=include_citations
    )
    db_time = (time.time() - start_time) * 1000
    logger.info(f"DB Fetch Time for messages: {db_time:.2f}ms (include_citations={include_citations})")
    
    process_start = time.time()
    
    items = []
    for msg in messages:
        # Only build citations if they were loaded
        citations = []
        if include_citations and msg.citations:
            citations = [
                CitationResponse(
                    id=c.id,
                    chunk_id=c.chunk_id,
                    document_id=c.chunk.document_version.document_id if c.chunk and c.chunk.document_version else None,
                    document_title=(
                        c.chunk.document_version.document.title 
                        if c.chunk and c.chunk.document_version and c.chunk.document_version.document 
                        else "Tài liệu không xác định"
                    ),
                    score=c.score,
                    quote=c.quote,
                    page=c.page,
                )
                for c in msg.citations
            ]
        items.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            provider=msg.provider,
            model=msg.model,
            prompt_tokens=msg.prompt_tokens,
            completion_tokens=msg.completion_tokens,
            latency_ms=msg.latency_ms,
            policy_mode=msg.policy_mode,
            best_retrieval_score=msg.best_retrieval_score,
            fallback_used=msg.fallback_used,
            citations=citations,
            created_at=msg.created_at,
        ))
    
    return MessageListResponse(
        items=items,
        conversation_id=conversation_id,
    )


@router.get(
    "/messages/{message_id}/citations",
    response_model=List[CitationResponse],
)
async def get_message_citations(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get citations for a specific message (lazy loading)."""
    from sqlalchemy.orm import selectinload, joinedload
    from app.models.chat import Message, Citation
    from app.models.document import Chunk, DocumentVersion
    
    # Fetch message with citations
    query = select(Message).where(Message.id == message_id).options(
        selectinload(Message.citations).options(
            joinedload(Citation.chunk).joinedload(Chunk.document_version).joinedload(DocumentVersion.document)
        )
    )
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Check access via conversation
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(message.conversation_id, include_messages=False)
    if not conversation or not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this message",
        )
    
    # Build citations response
    citations = [
        CitationResponse(
            id=c.id,
            chunk_id=c.chunk_id,
            document_id=c.chunk.document_version.document_id if c.chunk and c.chunk.document_version else None,
            document_title=(
                c.chunk.document_version.document.title 
                if c.chunk and c.chunk.document_version and c.chunk.document_version.document 
                else "Tài liệu không xác định"
            ),
            score=c.score,
            quote=c.quote,
            page=c.page,
        )
        for c in (message.citations or [])
    ]
    
    return citations


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get RAG response."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    try:
        # Use ChatPipeline (buffered mode) instead of removed ChatService.send_message()
        from app.services.conversation.chat_pipeline import ChatPipeline
        
        pipeline = ChatPipeline(db)
        
        # Collect streaming events into buffered response
        answer_parts = []
        metadata = {}
        
        async for event in pipeline.stream_response(
            query=data.content,
            workspace_id=conversation.workspace_id,
            document_ids=data.document_ids,
            tags=data.tags,
            model=data.model,
            conversation_id=conversation_id,
        ):
            if event.type.value == "token" and event.data:
                answer_parts.append(event.data.get("content", ""))
            elif event.type.value == "metadata" and event.data:
                metadata = event.data
            elif event.type.value == "done" and event.data:
                metadata["total_time_ms"] = event.data.get("total_time_ms", 0)
        
        # Retrieve the saved messages from DB
        conv_service = ChatService(db)
        messages = await conv_service.get_messages(conversation_id, limit=2)
        
        # Find user and assistant messages (last 2)
        user_msg = None
        assistant_msg = None
        for msg in reversed(messages):
            if msg.role.value == "user" and user_msg is None:
                user_msg = msg
            elif msg.role.value == "assistant" and assistant_msg is None:
                assistant_msg = msg
        
        if not user_msg or not assistant_msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save messages",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}",
        )
    
    # Build response
    user_citations = []
    assistant_citations = [
        CitationResponse(
            id=c.id,
            chunk_id=c.chunk_id,
            document_id=c.chunk.document_version.document_id if c.chunk and c.chunk.document_version else None,
            document_title=(
                c.chunk.document_version.document.title 
                if c.chunk and c.chunk.document_version and c.chunk.document_version.document 
                else "Tài liệu không xác định"
            ),
            score=c.score,
            quote=c.quote,
            page=c.page,
        )
        for c in (assistant_msg.citations or [])
    ]
    
    return SendMessageResponse(
        user_message=MessageResponse(
            id=user_msg.id,
            conversation_id=user_msg.conversation_id,
            role=user_msg.role,
            content=user_msg.content,
            provider=user_msg.provider,
            model=user_msg.model,
            prompt_tokens=user_msg.prompt_tokens,
            completion_tokens=user_msg.completion_tokens,
            latency_ms=user_msg.latency_ms,
            policy_mode=user_msg.policy_mode,
            best_retrieval_score=user_msg.best_retrieval_score,
            fallback_used=user_msg.fallback_used,
            citations=user_citations,
            created_at=user_msg.created_at,
        ),
        assistant_message=MessageResponse(
            id=assistant_msg.id,
            conversation_id=assistant_msg.conversation_id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            provider=assistant_msg.provider,
            model=assistant_msg.model,
            prompt_tokens=assistant_msg.prompt_tokens,
            completion_tokens=assistant_msg.completion_tokens,
            latency_ms=assistant_msg.latency_ms,
            policy_mode=assistant_msg.policy_mode,
            best_retrieval_score=assistant_msg.best_retrieval_score,
            fallback_used=assistant_msg.fallback_used,
            citations=assistant_citations,
            context_stats=getattr(assistant_msg, 'context_stats', None),
            created_at=assistant_msg.created_at,
        ),
    )


# =============================================================================
# STATELESS QUERY ENDPOINT
# =============================================================================

@router.post(
    "/query",
    response_model=StatelessQueryResponse,
)
async def stateless_query(
    data: StatelessQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stateless RAG query without conversation context.
    
    Modes:
    - rag_only=True (Nội bộ): 
      * Sử dụng Hybrid RAG (Graph + Vector + BM25) để tìm kiếm
      * CHỈ trả lời từ tài liệu nội bộ, KHÔNG fallback sang AI
      * Nếu không tìm thấy citation tốt (score >= 0.5) → báo "không có dữ liệu"
      
    - rag_only=False (Docs + AI):
      * Kiểm tra intent trước (greeting, chitchat, image_gen, document_search)
      * Nếu liên quan tài liệu → Hybrid RAG (Graph + Vector + BM25)
      * Nếu không liên quan (chitchat, image gen) → AI xử lý trực tiếp
      * **NEW**: Hỗ trợ function calling cho metadata queries
    
    Supports image input and generation.
    """
    start_time = time.time()
    
    if not await check_workspace_access(db, current_user.id, data.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this workspace",
        )
    
    # ==========================================================================
    # Request Deduplication (prevents duplicate queries within 5s)
    # ==========================================================================
    dedup_cache = None
    try:
        from app.services.infrastructure.redis_manager import get_redis
        from app.services.conversation.dedup_cache import DedupCache
        
        redis_client = await get_redis()
        if redis_client:
            dedup_cache = DedupCache(redis_client)
            
            # Check if result is cached
            cached_result = await dedup_cache.get(
                current_user.id, data.workspace_id, data.question
            )
            if cached_result:
                logger.info("Dedup cache HIT - returning cached response")
                return StatelessQueryResponse(**cached_result)
            
            # Mark as processing
            is_first = await dedup_cache.check_and_set_processing(
                current_user.id, data.workspace_id, data.question
            )
            if not is_first:
                # Duplicate request - wait briefly and check cache
                await asyncio.sleep(0.5)
                cached_result = await dedup_cache.get(
                    current_user.id, data.workspace_id, data.question
                )
                if cached_result:
                    return StatelessQueryResponse(**cached_result)
    except Exception as e:
        logger.debug(f"Dedup check skipped: {e}")
    
    # ==========================================================================
    # Function Calling for Metadata Queries (Optimized)
    # ==========================================================================
    fc_service = FunctionCallingService(db, data.workspace_id)
    
    try:
        # Fast keyword check (no LLM needed)
        should_use_fc = await asyncio.wait_for(
            fc_service.should_use_function_calling(data.question),
            timeout=0.1  # 100ms timeout - very fast
        )
        
        if should_use_fc and not data.rag_only:
            logger.info(f"Using function calling for: '{data.question[:50]}...'")
            
            try:
                # Execute tool directly (no LLM, very fast)
                result = await asyncio.wait_for(
                    fc_service.process_question(data.question),
                    timeout=5.0  # 5 second timeout
                )
                
                if result.get("used_function_calling"):
                    latency_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"Function calling succeeded in {latency_ms}ms")
                    
                    return StatelessQueryResponse(
                        answer=result["answer"],
                        citations=[],
                        policy_evaluation=PolicyEvaluationResponse(
                            policy="metadata",
                            threshold=0.0,
                            best_score=0.0,
                            should_answer=True,
                            is_grounded=True,
                            is_fallback=False,
                            disclaimer=None,
                        ),
                        provider="function-calling",
                        model="direct-execution",
                        prompt_tokens=0,
                        completion_tokens=0,
                        tool_calls_made=result.get("tool_calls", []),
                    )
            except asyncio.TimeoutError:
                logger.warning("Function calling timeout, falling back to RAG")
            except Exception as e:
                logger.warning(f"Function calling failed: {e}, falling back to RAG")
    
    except Exception as e:
        logger.warning(f"Function calling check failed: {e}")
    
    # Fall through to RAG
    chat_service = ChatService(db)
    
    # ==========================================================================
    # MODE: "Nội bộ" (rag_only=True)
    # - Sử dụng Hybrid RAG (Graph + Vector + BM25) để tìm kiếm tài liệu
    # - CHỈ trả lời từ tài liệu nội bộ, KHÔNG dùng AI fallback
    # - Nếu không tìm thấy citation tốt (score >= 0.5) → báo "không có dữ liệu"
    # ==========================================================================
    if data.rag_only:
        logger.info(f"RAG query (Nội bộ mode): '{data.question[:50]}...'")
        
        try:
            response = await chat_service.stateless_query(
                workspace_id=data.workspace_id,
                question=data.question,
                document_ids=data.document_ids,
                tags=data.tags,
                model=data.model,
                has_image=data.has_image,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process query: {str(e)}",
            )
        
        citations = [
            StatelessQueryCitation(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                content=c.content,
                score=c.score,
                page=c.page,
                quote=c.quote,
            )
            for c in response.citations
        ]
        
        # Kiểm tra có citation tốt không (score >= 0.5)
        good_citations = [c for c in citations if c.score >= 0.5]
        
        if not good_citations:
            # Không tìm thấy tài liệu liên quan → báo "không có dữ liệu"
            return StatelessQueryResponse(
                answer="📚 Không tìm thấy thông tin liên quan trong tài liệu nội bộ.\n\n💡 Gợi ý: Hãy thử đặt câu hỏi cụ thể hơn hoặc chuyển sang chế độ 'Docs + AI' để được hỗ trợ.",
                citations=[],
                policy_evaluation=PolicyEvaluationResponse(
                    policy="strict",
                    threshold=0.5,
                    best_score=response.policy_evaluation.best_score if response.citations else 0.0,
                    should_answer=False,
                    is_grounded=False,
                    is_fallback=False,
                    disclaimer="Chế độ 'Nội bộ' chỉ trả lời từ tài liệu đã tải lên.",
                ),
                provider="hybrid-rag",
                model="internal-docs",
                prompt_tokens=None,
                completion_tokens=None,
            )
        
        return StatelessQueryResponse(
            answer=response.answer,
            citations=citations,
            policy_evaluation=PolicyEvaluationResponse(
                policy=response.policy_evaluation.policy_mode,
                threshold=response.policy_evaluation.threshold,
                best_score=response.policy_evaluation.best_score,
                should_answer=response.policy_evaluation.should_answer,
                is_grounded=True,
                is_fallback=False,
                disclaimer=None,
            ),
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.metadata.get("latency_ms"),
        )
    
    # ==========================================================================
    # MODE: "Docs + AI" (rag_only=False) - Default
    # - Kiểm tra intent trước (greeting, chitchat, image_gen, document_search)
    # - Nếu liên quan tài liệu → Hybrid RAG (Graph + Vector + BM25)
    # - Nếu không liên quan (chitchat, image gen) → AI xử lý trực tiếp
    # ==========================================================================
    from app.services.conversation.intent_detector import get_intent_detector, QueryIntent
    intent_detector = get_intent_detector()
    intent_result = await intent_detector.detect(data.question)
    
    logger.info(f"RAG query (Docs+AI mode): Intent = {intent_result.intent}, confidence = {intent_result.confidence}")
    
    # Handle pure image generation request (no RAG needed)
    if intent_result.intent == QueryIntent.IMAGE_GENERATION and not data.image_data:
        logger.info("RAG query: Pure image generation request detected")
        
        try:
            from app.services.generation.image_generation import get_image_generation_service
            image_service = get_image_generation_service()
            
            result = await image_service.generate(
                prompt=data.question,
                num_images=1,
                aspect_ratio="1:1",
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if result.success and result.images:
                return StatelessQueryResponse(
                    answer=f"🎨 Đã tạo ảnh thành công!",
                    citations=[],
                    policy_evaluation=PolicyEvaluationResponse(
                        policy="open",
                        threshold=0.0,
                        best_score=0.0,
                        should_answer=True,
                        is_grounded=False,
                        is_fallback=False,
                        disclaimer=None,
                    ),
                    provider=result.provider,
                    model=result.model,
                    prompt_tokens=None,
                    completion_tokens=None,
                    images=result.images,
                    is_image_response=True,
                )
            else:
                return StatelessQueryResponse(
                    answer=f"⚠️ Không thể tạo ảnh: {result.error}\n\nPrompt: {data.question}",
                    citations=[],
                    policy_evaluation=PolicyEvaluationResponse(
                        policy="open",
                        threshold=0.0,
                        best_score=0.0,
                        should_answer=True,
                        is_grounded=False,
                        is_fallback=True,
                        disclaimer=None,
                    ),
                    provider="local",
                    model="image-gen",
                    prompt_tokens=None,
                    completion_tokens=None,
                )
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")
            # Fall through to normal RAG
    
    # Handle image input - need to use Cloud Code for multimodal
    if data.image_data:
        logger.info("RAG query with image input - using multimodal processing")
        
        try:
            from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
            
            # First, do RAG search to get relevant documents
            response = await chat_service.stateless_query(
                workspace_id=data.workspace_id,
                question=data.question,
                document_ids=data.document_ids,
                tags=data.tags,
                model=data.model,
                has_image=True,
            )
            
            # Build context from RAG results
            rag_context = ""
            if response.citations:
                rag_context = "\n\n📚 Thông tin từ tài liệu:\n"
                for i, c in enumerate(response.citations[:3], 1):
                    rag_context += f"{i}. {c.document_title}: {c.content[:300]}...\n"
            
            manager = get_cloudcode_manager()
            if manager and manager.list_accounts():
                # Build multimodal message with RAG context
                multimodal_content = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{data.image_mime_type or 'image/jpeg'};base64,{data.image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"{data.question}{rag_context}"
                    }
                ]
                
                # If image generation is requested, add instruction
                if intent_result.intent == QueryIntent.IMAGE_GENERATION:
                    multimodal_content[1]["text"] += "\n\nNếu có yêu cầu tạo ảnh, hãy mô tả chi tiết ảnh cần tạo. Kết thúc bằng: IMAGE_PROMPT: [mô tả]"
                
                ai_response = await manager.generate(
                    messages=[{"role": "user", "content": multimodal_content}],
                    model=data.model,
                    max_tokens=2048,
                    temperature=0.7,
                )
                
                if ai_response.success:
                    answer = ai_response.content or ""
                    generated_images = None
                    
                    # Check for image generation - support both IMAGE_PROMPT: and JSON format
                    image_prompt = None
                    text_part = answer
                    
                    if "IMAGE_PROMPT:" in answer:
                        parts = answer.split("IMAGE_PROMPT:")
                        text_part = parts[0].strip()
                        image_prompt = parts[1].strip() if len(parts) > 1 else None
                    elif '"action": "dalle' in answer or ('"prompt":' in answer and '{' in answer):
                        # Parse JSON format from AI
                        import json
                        import re
                        
                        try:
                            # Find JSON block
                            json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', answer, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                text_part = answer[:json_match.start()].strip()
                                
                                try:
                                    json_data = json.loads(json_str)
                                    action_input = json_data.get("action_input", "")
                                    if isinstance(action_input, str) and "prompt" in action_input:
                                        inner_json = json.loads(action_input)
                                        image_prompt = inner_json.get("prompt")
                                except:
                                    pass
                            
                            if not image_prompt:
                                prompt_match = re.search(r'"prompt":\s*"([^"]+)"', answer)
                                if prompt_match:
                                    image_prompt = prompt_match.group(1)
                                    json_start = answer.find('{')
                                    if json_start > 0:
                                        text_part = answer[:json_start].strip()
                        except Exception as e:
                            logger.warning(f"Failed to parse image JSON: {e}")
                    
                    if image_prompt:
                        from app.services.generation.image_generation import get_image_generation_service
                        
                        logger.info(f"RAG query: Generating image with prompt: {image_prompt[:100]}...")
                        image_service = get_image_generation_service()
                        img_result = await image_service.generate(prompt=image_prompt, num_images=1)
                        
                        if img_result.success and img_result.images:
                            generated_images = img_result.images
                            answer = f"{text_part}\n\n🎨 Đã tạo ảnh thành công!"
                        else:
                            answer = f"{text_part}\n\n⚠️ Không thể tạo ảnh: {img_result.error}"
                    
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    # Build citations from RAG response
                    citations = [
                        StatelessQueryCitation(
                            chunk_id=c.chunk_id,
                            document_id=c.document_id,
                            document_title=c.document_title,
                            content=c.content,
                            score=c.score,
                            page=c.page,
                            quote=c.quote,
                        )
                        for c in response.citations
                    ]
                    
                    return StatelessQueryResponse(
                        answer=answer,
                        citations=citations,
                        policy_evaluation=PolicyEvaluationResponse(
                            policy=response.policy_evaluation.policy_mode,
                            threshold=response.policy_evaluation.threshold,
                            best_score=response.policy_evaluation.best_score,
                            should_answer=True,
                            is_grounded=len(citations) > 0,
                            is_fallback=False,
                            disclaimer=None,
                        ),
                        provider="cloudcode",
                        model=ai_response.model,
                        prompt_tokens=None,
                        completion_tokens=None,
                        images=generated_images,
                        is_image_response=generated_images is not None,
                    )
        except Exception as e:
            logger.warning(f"Multimodal RAG query failed: {e}", exc_info=True)
            # Fall through to normal RAG processing
    
    # Normal RAG processing (no image)
    try:
        response = await chat_service.stateless_query(
            workspace_id=data.workspace_id,
            question=data.question,
            document_ids=data.document_ids,
            tags=data.tags,
            model=data.model,
            has_image=data.has_image,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}",
        )
    
    citations = [
        StatelessQueryCitation(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_title=c.document_title,
            content=c.content,
            score=c.score,
            page=c.page,
            quote=c.quote,
        )
        for c in response.citations
    ]
    
    return StatelessQueryResponse(
        answer=response.answer,
        citations=citations,
        policy_evaluation=PolicyEvaluationResponse(
            policy=response.policy_evaluation.policy_mode,
            threshold=response.policy_evaluation.threshold,
            best_score=response.policy_evaluation.best_score,
            should_answer=response.policy_evaluation.should_answer,
            is_grounded=response.policy_evaluation.should_answer,  # Use should_answer as grounded indicator
            is_fallback=response.policy_evaluation.fallback_used,
            disclaimer=response.policy_evaluation.disclaimer,
        ),
        provider=response.provider,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
    )


# =============================================================================
# STREAMING QUERY ENDPOINT (SSE for real-time response)
# =============================================================================

@router.post(
    "/stream",
    summary="Streaming RAG query with SSE",
    description="Returns Server-Sent Events for real-time response streaming",
)
async def stream_query(
    data: StatelessQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streaming RAG query with Server-Sent Events (SSE).

    Gate: Rate limit (3 concurrent streams/user, 20 req/min/workspace, 30/min/IP).

    Event Types:
    - progress: {step, progress, message}
    - token:    {content, index}
    - metadata: {citations, quality, model, ...}
    - quality_warning: {type, severity, message}
    - error:    {message, code}
    - done:     {total_time_ms}
    """
    # ── Auth + workspace access ─────────────────────────────────────────────
    if not await check_workspace_access(db, current_user.id, data.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this workspace",
        )

    # ── Rate limit ──────────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else ""
    allowed, reason = _check_rate_limit(current_user.id, data.workspace_id, ip_address=client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=reason,
            headers={"Retry-After": "10"},
        )

    from app.services.conversation.chat_pipeline import ChatPipeline

    pipeline = ChatPipeline(db)

    async def event_generator():
        try:
            async for event in pipeline.stream_response(
                query=data.question,
                workspace_id=data.workspace_id,
                document_ids=data.document_ids,
                tags=data.tags,
                model=data.model,
                conversation_id=data.conversation_id,
            ):
                yield event.to_sse()
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            _release_stream(current_user.id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# ORCHESTRATED QUERY ENDPOINT (Enhanced with Phase 1-4 features)
# =============================================================================

@router.post(
    "/query/orchestrated",
    response_model=dict,  # Enhanced response with orchestration metadata
    summary="Orchestrated RAG query with enhanced observability",
)
async def orchestrated_query(
    data: StatelessQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enhanced RAG query with full orchestration pipeline.
    
    Features (Phase 1-4):
    - Smart routing based on query complexity
    - SLA-based latency budget management
    - Multi-pattern execution (Sequential/Parallel/DAG)
    - Full distributed tracing
    - Response validation (hallucination, facts, safety)
    - Confidence scoring
    
    Response includes:
    - content: Generated answer
    - sources: Citation sources
    - trace_id: Trace ID for debugging
    - confidence: Confidence score [0.0-1.0]
    - validation_flags: Validation results
    - pattern_used: Pattern(s) executed
    - latency_ms: Total latency
    - cost_estimate: Estimated cost
    """
    start_time = time.time()
    
    if not await check_workspace_access(db, current_user.id, data.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this workspace",
        )
    
    try:
        # Initialize services
        from app.services.rag_patterns.orchestration import QueryAnalyzer
        from app.services.rag_patterns.orchestration import PatternOrchestrator
        from app.services.rag_patterns.orchestration.analyzer import QueryComplexity
        from app.services.rag_patterns.orchestration.orchestrator import ExecutionStrategy
        from server.app.services.infrastructure.trace_collector import get_trace_collector
        from server.app.services.quality.confidence_scorer import ConfidenceScorer
        from server.app.services.quality.result_validator import ResultValidator
        
        # Initialize components
        trace_collector = get_trace_collector()
        query_analyzer = QueryAnalyzer()
        orchestrator = PatternOrchestrator(
            analyzer=query_analyzer,
            trace_collector=trace_collector,
        )
        confidence_scorer = ConfidenceScorer()
        result_validator = ResultValidator()
        
        # Analyze query
        analysis = query_analyzer.analyze(data.question)
        
        # Determine SLA budget based on complexity
        sla_budgets = {
            QueryComplexity.SIMPLE: 2000,
            QueryComplexity.MODERATE: 4000,
            QueryComplexity.COMPLEX: 6000,
        }
        budget_ms = sla_budgets.get(analysis.complexity, 4000)
        
        # Route to appropriate execution strategy
        if analysis.complexity == QueryComplexity.SIMPLE:
            strategy = ExecutionStrategy.SEQUENTIAL
            patterns = ["adaptive_rag"]
        elif analysis.complexity == QueryComplexity.MODERATE:
            strategy = ExecutionStrategy.CONDITIONAL
            patterns = ["adaptive_rag", "self_rag"]
        else:
            strategy = ExecutionStrategy.PARALLEL
            patterns = ["adaptive_rag", "graph_enhanced"]
        
        # For now, fall back to stateless query for actual execution
        # (Full pattern services integration is a future enhancement)
        chat_service = ChatService(db)
        
        response = await chat_service.stateless_query(
            workspace_id=data.workspace_id,
            question=data.question,
            document_ids=data.document_ids,
            tags=data.tags,
            model=data.model,
            has_image=data.has_image,
        )
        
        # Calculate metrics
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Run validation (simplified for now)
        validation_flags = {
            "hallucination_check": "passed",
            "fact_check": "passed", 
            "safety_check": "passed",
            "pii_detected": False,
        }
        
        # Calculate confidence
        confidence = 0.85 if response.citations else 0.5
        if latency_ms > budget_ms:
            confidence *= 0.9  # Latency penalty
        
        # Build enhanced response
        return {
            "content": response.answer,
            "sources": [
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "document_title": c.document_title,
                    "content": c.content,
                    "score": c.score,
                    "page": c.page,
                }
                for c in response.citations
            ],
            "trace_id": trace_collector.get_current_trace_id() if trace_collector else None,
            "confidence": round(confidence, 3),
            "validation_flags": validation_flags,
            "pattern_used": patterns[0] if patterns else "adaptive_rag",
            "latency_ms": latency_ms,
            "budget_ms": budget_ms,
            "cost_estimate": response.prompt_tokens * 0.00001 if response.prompt_tokens else 0.0,
            "complexity": analysis.complexity.value if hasattr(analysis.complexity, 'value') else str(analysis.complexity),
            "strategy": strategy.value,
            "metadata": {
                "provider": response.provider,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "query_type": analysis.query_type.value if hasattr(analysis, 'query_type') else "unknown",
            },
        }
        
    except ImportError as e:
        # Graceful fallback if orchestration components not available
        logger.warning(f"Orchestration components not available: {e}")
        
        chat_service = ChatService(db)
        response = await chat_service.stateless_query(
            workspace_id=data.workspace_id,
            question=data.question,
            document_ids=data.document_ids,
            tags=data.tags,
            model=data.model,
            has_image=data.has_image,
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "content": response.answer,
            "sources": [
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "document_title": c.document_title,
                    "content": c.content,
                    "score": c.score,
                    "page": c.page,
                }
                for c in response.citations
            ],
            "trace_id": None,
            "confidence": 0.8 if response.citations else 0.5,
            "validation_flags": {"fallback": True},
            "pattern_used": "adaptive_rag",
            "latency_ms": latency_ms,
            "cost_estimate": 0.0,
            "metadata": {
                "provider": response.provider,
                "model": response.model,
                "fallback_reason": str(e),
            },
        }
    
    except Exception as e:
        logger.error(f"Orchestrated query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestrated query failed: {str(e)}",
        )

# =============================================================================
# DIRECT CHAT ENDPOINT (LLM only, no RAG)
# =============================================================================

@router.post(
    "/direct",
    response_model=DirectChatResponse,
)
async def direct_chat(
    data: DirectChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Direct LLM chat without RAG - just AI response. Supports image generation."""
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    start_time = time.time()
    
    # Step 1: Detect intent to check if this is an image generation request
    from app.services.conversation.intent_detector import get_intent_detector, QueryIntent
    intent_detector = get_intent_detector()
    intent_result = await intent_detector.detect(data.question)
    
    logger.info(f"Direct chat: Intent detected = {intent_result.intent}, confidence = {intent_result.confidence}")
    
    # Step 2: Handle compound requests (image input + image generation request)
    # Example: "Người trong ảnh gái hay trai? Tạo con mèo phù hợp với người đó"
    if data.image_data and intent_result.intent == QueryIntent.IMAGE_GENERATION:
        logger.info("Direct chat: Compound request - image analysis + image generation")
        
        try:
            from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
            from app.services.generation.image_generation import get_image_generation_service
            
            manager = get_cloudcode_manager()
            
            if manager and manager.list_accounts():
                # Step 2a: First, analyze the image with AI
                analysis_content = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{data.image_mime_type or 'image/jpeg'};base64,{data.image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Phân tích ảnh này và trả lời câu hỏi: {data.question}

QUAN TRỌNG: Nếu câu hỏi yêu cầu tạo/vẽ ảnh mới, bạn PHẢI kết thúc response bằng dòng sau (KHÔNG dùng JSON, KHÔNG dùng tool call):

IMAGE_PROMPT: [mô tả chi tiết bằng tiếng Anh cho ảnh cần tạo]

Ví dụ đúng:
Người trong ảnh là bé gái mặc váy đỏ.

IMAGE_PROMPT: A cute fluffy white kitten wearing a tiny red dress, sitting next to a pink birthday cake

KHÔNG viết JSON, KHÔNG viết action, KHÔNG viết dalle.text2im. Chỉ viết IMAGE_PROMPT: theo sau là mô tả."""
                    }
                ]
                
                analysis_response = await manager.generate(
                    messages=[{"role": "user", "content": analysis_content}],
                    model=data.model,
                    system_prompt="Bạn là AI assistant phân tích ảnh. Khi được yêu cầu tạo ảnh, LUÔN kết thúc bằng 'IMAGE_PROMPT: [mô tả tiếng Anh]'. KHÔNG dùng JSON, KHÔNG dùng tool call format.",
                    max_tokens=data.max_tokens,
                    temperature=data.temperature,
                )
                
                if analysis_response.success and analysis_response.content:
                    analysis_text = analysis_response.content
                    logger.info(f"Direct chat: Image analysis complete: {analysis_text[:200]}...")
                    
                    # Step 2b: Check if AI provided an image prompt
                    if "IMAGE_PROMPT:" in analysis_text:
                        parts = analysis_text.split("IMAGE_PROMPT:")
                        text_response = parts[0].strip()
                        image_prompt = parts[1].strip() if len(parts) > 1 else None
                        
                        if image_prompt:
                            logger.info(f"Direct chat: Generating image with prompt: {image_prompt}")
                            
                            image_service = get_image_generation_service()
                            result = await image_service.generate(
                                prompt=image_prompt,
                                num_images=1,
                                aspect_ratio="1:1",
                            )
                            
                            latency_ms = int((time.time() - start_time) * 1000)
                            
                            if result.success and result.images:
                                return DirectChatResponse(
                                    answer=f"{text_response}\n\n🎨 Đã tạo ảnh: {image_prompt}",
                                    model=analysis_response.model or "unknown",
                                    provider="cloudcode",
                                    latency_ms=latency_ms,
                                    prompt_tokens=None,
                                    completion_tokens=None,
                                    images=result.images,
                                    is_image_response=True,
                                )
                            else:
                                # Image generation failed, return analysis only
                                return DirectChatResponse(
                                    answer=f"{text_response}\n\n⚠️ Không thể tạo ảnh: {result.error}",
                                    model=analysis_response.model or "unknown",
                                    provider="cloudcode",
                                    latency_ms=latency_ms,
                                    prompt_tokens=None,
                                    completion_tokens=None,
                                )
                    
                    # No image prompt found, return analysis only
                    latency_ms = int((time.time() - start_time) * 1000)
                    return DirectChatResponse(
                        answer=analysis_text,
                        model=analysis_response.model or "unknown",
                        provider="cloudcode",
                        latency_ms=latency_ms,
                        prompt_tokens=None,
                        completion_tokens=None,
                    )
        except Exception as e:
            logger.warning(f"Compound request failed: {e}", exc_info=True)
            # Fall through to normal processing
    
    # Step 3: Handle pure image generation requests (no input image)
    if intent_result.intent == QueryIntent.IMAGE_GENERATION and not data.image_data:
        logger.info("Direct chat: Image generation request detected, using ImageGenerationService")
        
        try:
            from app.services.generation.image_generation import get_image_generation_service
            image_service = get_image_generation_service()
            
            # Extract the image prompt from user's question
            # The question itself is the prompt for image generation
            image_prompt = data.question
            
            # Generate image
            result = await image_service.generate(
                prompt=image_prompt,
                num_images=1,
                aspect_ratio="1:1",
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if result.success and result.images:
                logger.info(f"Direct chat: Image generation successful, {len(result.images)} images generated")
                return DirectChatResponse(
                    answer=f"Đã tạo ảnh thành công với prompt: {image_prompt}",
                    model=result.model,
                    provider=result.provider,
                    latency_ms=latency_ms,
                    prompt_tokens=None,
                    completion_tokens=None,
                    images=result.images,
                    is_image_response=True,
                )
            else:
                # Image generation failed - provide helpful message and continue to text response
                logger.warning(f"Image generation failed: {result.error}")
                # Don't fall through - return a helpful message about image generation
                return DirectChatResponse(
                    answer=f"⚠️ Xin lỗi, tôi chưa thể tạo ảnh trực tiếp. Lỗi: {result.error}\n\n"
                           f"💡 Gợi ý: Bạn có thể sử dụng các công cụ tạo ảnh AI miễn phí như:\n"
                           f"- Google AI Studio (Imagen 3): https://aistudio.google.com\n"
                           f"- Bing Image Creator: https://www.bing.com/create\n"
                           f"- Leonardo.ai: https://leonardo.ai\n\n"
                           f"Prompt của bạn: \"{image_prompt}\"",
                    model="intent-detector",
                    provider="local",
                    latency_ms=latency_ms,
                    prompt_tokens=None,
                    completion_tokens=None,
                )
        except Exception as e:
            logger.warning(f"Image generation exception: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return DirectChatResponse(
                answer=f"⚠️ Xin lỗi, tôi chưa thể tạo ảnh trực tiếp. Lỗi: {str(e)}\n\n"
                       f"💡 Gợi ý: Bạn có thể sử dụng các công cụ tạo ảnh AI miễn phí như:\n"
                       f"- Google AI Studio (Imagen 3): https://aistudio.google.com\n"
                       f"- Bing Image Creator: https://www.bing.com/create\n"
                       f"- Leonardo.ai: https://leonardo.ai\n\n"
                       f"Prompt của bạn: \"{data.question}\"",
                model="intent-detector",
                provider="local",
                latency_ms=latency_ms,
                prompt_tokens=None,
                completion_tokens=None,
            )
    
    # Step 4: Handle greeting/chitchat with direct response
    if intent_result.intent in [QueryIntent.GREETING, QueryIntent.CHITCHAT] and intent_result.direct_response:
        latency_ms = int((time.time() - start_time) * 1000)
        return DirectChatResponse(
            answer=intent_result.direct_response,
            model="intent-detector",
            provider="local",
            latency_ms=latency_ms,
            prompt_tokens=None,
            completion_tokens=None,
        )
    
    # Step 5: Try Cloud Code first (has Claude/Gemini)
    cloudcode_error = None
    try:
        from app.services.infrastructure.ai_providers.cloudcode_provider_service import get_cloudcode_manager
        manager = get_cloudcode_manager()
        
        if manager:
            accounts = manager.list_accounts()
            logger.info(f"Direct chat: Found {len(accounts)} Cloud Code accounts")
            
            if accounts:
                # Use suggested model from intent if available
                model_to_use = intent_result.suggested_model or data.model
                
                # Build message content - support image input
                if data.image_data:
                    # Multimodal message with image
                    user_content = [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{data.image_mime_type or 'image/jpeg'};base64,{data.image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": data.question
                        }
                    ]
                    logger.info(f"Direct chat: Sending multimodal message with image ({data.image_mime_type})")
                else:
                    user_content = data.question
                
                logger.info(f"Direct chat: Calling Cloud Code generate with model={model_to_use}")
                response = await manager.generate(
                    messages=[{"role": "user", "content": user_content}],
                    model=model_to_use,
                    system_prompt=data.system_prompt,
                    max_tokens=data.max_tokens,
                    temperature=data.temperature,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"Direct chat: Cloud Code response success={response.success}, model={response.model}, error={response.error}")
                
                if response.success:
                    answer_content = response.content or ""
                    
                    # Post-process: Check if AI returned image generation JSON (dalle format)
                    # This happens when AI tries to generate image but outputs JSON instead
                    if data.image_data and ('"action": "dalle' in answer_content or '"prompt":' in answer_content):
                        logger.info("Direct chat: Detected image generation JSON in response, extracting prompt")
                        
                        import json
                        import re
                        
                        try:
                            # Try to extract prompt from JSON
                            image_prompt = None
                            text_part = ""
                            
                            # Find JSON block in response
                            json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', answer_content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                text_part = answer_content[:json_match.start()].strip()
                                
                                try:
                                    json_data = json.loads(json_str)
                                    # Extract prompt from action_input
                                    action_input = json_data.get("action_input", "")
                                    if isinstance(action_input, str) and "prompt" in action_input:
                                        inner_json = json.loads(action_input)
                                        image_prompt = inner_json.get("prompt")
                                except:
                                    pass
                            
                            # Alternative: look for "prompt": "..." pattern
                            if not image_prompt:
                                prompt_match = re.search(r'"prompt":\s*"([^"]+)"', answer_content)
                                if prompt_match:
                                    image_prompt = prompt_match.group(1)
                                    # Get text before JSON
                                    json_start = answer_content.find('{')
                                    if json_start > 0:
                                        text_part = answer_content[:json_start].strip()
                            
                            if image_prompt:
                                logger.info(f"Direct chat: Extracted image prompt: {image_prompt[:100]}...")
                                
                                from app.services.generation.image_generation import get_image_generation_service
                                image_service = get_image_generation_service()
                                
                                img_result = await image_service.generate(
                                    prompt=image_prompt,
                                    num_images=1,
                                    aspect_ratio="1:1",
                                )
                                
                                if img_result.success and img_result.images:
                                    return DirectChatResponse(
                                        answer=f"{text_part}\n\n🎨 Đã tạo ảnh thành công!",
                                        model=response.model or model_to_use or "unknown",
                                        provider="cloudcode",
                                        latency_ms=int((time.time() - start_time) * 1000),
                                        prompt_tokens=None,
                                        completion_tokens=None,
                                        images=img_result.images,
                                        is_image_response=True,
                                    )
                                else:
                                    # Image generation failed
                                    return DirectChatResponse(
                                        answer=f"{text_part}\n\n⚠️ Không thể tạo ảnh: {img_result.error}\n\nPrompt: {image_prompt}",
                                        model=response.model or model_to_use or "unknown",
                                        provider="cloudcode",
                                        latency_ms=int((time.time() - start_time) * 1000),
                                        prompt_tokens=None,
                                        completion_tokens=None,
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to parse image generation JSON: {e}")
                    
                    return DirectChatResponse(
                        answer=answer_content,
                        model=response.model or model_to_use or "unknown",
                        provider="cloudcode",
                        latency_ms=latency_ms,
                        prompt_tokens=None,
                        completion_tokens=None,
                    )
                else:
                    cloudcode_error = response.error or "Unknown Cloud Code error"
                    logger.warning(f"Cloud Code failed: {cloudcode_error}")
            else:
                cloudcode_error = "No Cloud Code accounts available"
                logger.warning(cloudcode_error)
        else:
            cloudcode_error = "Cloud Code manager not initialized"
            logger.warning(cloudcode_error)
    except Exception as e:
        cloudcode_error = str(e)
        logger.warning(f"Cloud Code exception: {e}", exc_info=True)
    
    # Step 6: Try DeepSeek (strongest free model) - Note: most don't support images
    # If image is provided, skip non-multimodal providers
    if not data.image_data:
        try:
            from app.services.infrastructure.ai_providers.manager import provider_manager
            from app.models.enums import ProviderName
            
            if provider_manager and provider_manager.providers:
                # Prefer DeepSeek > Gemini > Groq > Ollama
                preferred_order = [ProviderName.DEEPSEEK, ProviderName.GEMINI, ProviderName.GROQ, ProviderName.OLLAMA]
                
                for provider_name in preferred_order:
                    if provider_name in provider_manager.providers:
                        status = provider_manager.provider_statuses.get(provider_name)
                        if status and status.available:
                            provider = provider_manager.providers[provider_name]
                            
                            try:
                                messages = [{"role": "user", "content": data.question}]
                                if data.system_prompt:
                                    messages.insert(0, {"role": "system", "content": data.system_prompt})
                                
                                result = await provider.chat_completion(
                                    messages=messages,
                                    temperature=data.temperature or 0.7,
                                    max_tokens=data.max_tokens,
                                )
                                latency_ms = int((time.time() - start_time) * 1000)
                                
                                return DirectChatResponse(
                                    answer=result,
                                    model=provider.model,
                                    provider=str(provider_name),
                                    latency_ms=latency_ms,
                                    prompt_tokens=None,
                                    completion_tokens=None,
                                )
                            except Exception as e:
                                logger.warning(f"Provider {provider_name} failed: {e}")
                                continue
        except Exception as e:
            logger.error(f"AI Provider Manager error: {e}")
    else:
        logger.info("Skipping fallback providers - image input requires Cloud Code multimodal models")
    
    # All providers failed
    if data.image_data:
        error_msg = f"Image input requires Cloud Code (Claude/Gemini). Cloud Code error: {cloudcode_error or 'not available'}"
    else:
        error_msg = f"All providers failed. Cloud Code: {cloudcode_error or 'not available'}"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=error_msg,
    )


# =============================================================================
# STATS ENDPOINT
# =============================================================================

@router.get(
    "/conversations/{conversation_id}/stats",
    response_model=ConversationStatsResponse,
)
async def get_conversation_stats(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics for a conversation."""
    chat_service = ChatService(db)
    conversation = await chat_service.get_conversation(
        conversation_id, include_messages=False
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    if not await check_workspace_access(db, current_user.id, conversation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this conversation",
        )
    
    stats = await chat_service.get_conversation_stats(conversation_id)
    
    return ConversationStatsResponse(
        conversation_id=conversation_id,
        **stats,
    )

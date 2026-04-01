"""
Conversation Service — CRUD layer cho quản lý cuộc trò chuyện và tin nhắn.

Chỉ chứa các thao tác cơ sở dữ liệu (Create/Read/Update/Delete).
Pipeline RAG xử lý bởi ChatPipeline (chat_pipeline.py).

Các chức năng:
- CRUD Conversation: create, list, get, update, delete
- Message Handling: get_messages, add_user_message, add_assistant_message
- Utility: auto_title_conversation, get_conversation_stats, _track_usage
"""
import logging
import time
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from app.db.models import (
    Conversation, Message, Citation, AIUsage, Workspace,
    MessageRole, JobStatus, Chunk, DocumentVersion, Document
)

if TYPE_CHECKING:
    from app.services.core.rag.types import RAGResponse

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service CRUD cho quản lý cuộc trò chuyện và tin nhắn.
    Không chứa logic pipeline RAG — chỉ thao tác cơ sở dữ liệu.
    """
    
    def __init__(self, session: AsyncSession):
        """Khởi tạo conversation service với database session."""
        self.session = session
    
    async def _ensure_valid_session(self) -> None:
        """
        Đảm bảo session ở trạng thái valid trước khi thực hiện operations.
        
        Nếu session bị tainted do lỗi trước đó, tự động rollback để clear state.
        Đây là giải pháp triệt để cho lỗi "Can't reconnect until invalid transaction is rolled back".
        
        IMPORTANT: Không gọi in_transaction() hoặc is_active vì chúng có thể trigger
        greenlet_spawn error trong một số context. Chỉ đơn giản try rollback.
        """
        if self.session is None:
            return
        
        # Đơn giản: cố gắng rollback
        # Rollback trên clean session là no-op an toàn
        # Rollback trên dirty session sẽ clear nó
        try:
            await self.session.rollback()
        except Exception as e:
            # Một số session states không cho phép rollback - log và tiếp tục
            logger.debug(f"Session rollback attempt: {e}")
    
    # =========================================================================
    # CONVERSATION CRUD
    # =========================================================================
    
    async def create_conversation(
        self,
        workspace_id: UUID,
        user_id: UUID,
        title: Optional[str] = None,
        scope_tags: Optional[List[str]] = None,
    ) -> Conversation:
        """
        Tạo cuộc trò chuyện mới.
        
        Args:
            workspace_id: ID Workspace
            user_id: User tạo cuộc trò chuyện
            title: Tiêu đề cuộc trò chuyện (tùy chọn)
            scope_tags: Các tag tùy chọn để lọc tài liệu cho RAG
            
        Returns:
            Conversation đã tạo
        """
        conversation = Conversation(
            workspace_id=workspace_id,
            created_by=user_id,
            title=title or "Cuộc hội thoại mới",
            scope_tags=scope_tags or [],
        )
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        
        logger.info(f"Đã tạo cuộc trò chuyện {conversation.id} trong workspace {workspace_id}")
        return conversation
    
    async def list_conversations(
        self,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> List[Conversation]:
        """
        Liệt kê các cuộc trò chuyện trong một workspace.
        
        Args:
            workspace_id: ID Workspace
            limit: Số lượng kết quả tối đa
            offset: Offset phân trang
            include_deleted: Bao gồm các cuộc trò chuyện đã xóa mềm (soft-deleted)
            
        Returns:
            Danh sách các cuộc trò chuyện
        """
        query = select(Conversation).where(
            Conversation.workspace_id == workspace_id
        )
        
        if not include_deleted:
            query = query.where(Conversation.deleted_at.is_(None))
        
        query = query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_conversation(
        self,
        conversation_id: UUID,
        include_messages: bool = True,
    ) -> Optional[Conversation]:
        """
        Lấy một cuộc trò chuyện theo ID.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            include_messages: Load danh sách tin nhắn (eagerly)
            
        Returns:
            Conversation hoặc None
        """
        query = select(Conversation).where(Conversation.id == conversation_id)
        
        if include_messages:
            query = query.options(
                selectinload(Conversation.messages).selectinload(Message.citations)
            )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_conversation(
        self,
        conversation_id: UUID,
        title: Optional[str] = None,
        scope_tags: Optional[List[str]] = None,
    ) -> Optional[Conversation]:
        """
        Cập nhật tiêu đề cuộc trò chuyện và/hoặc scope_tags.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            title: Tiêu đề mới
            scope_tags: Scope tags mới để lọc
            
        Returns:
            Conversation đã cập nhật hoặc None
        """
        conversation = await self.get_conversation(conversation_id, include_messages=False)
        if not conversation:
            return None
        
        if title is not None:
            conversation.title = title
        
        if scope_tags is not None:
            conversation.scope_tags = scope_tags
        
        conversation.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(conversation)
        
        return conversation
    
    async def delete_conversation(
        self,
        conversation_id: UUID,
        hard_delete: bool = False,
    ) -> bool:
        """
        Xóa cuộc trò chuyện (xóa mềm hoặc xóa cứng).
        
        Args:
            conversation_id: ID cuộc trò chuyện
            hard_delete: Nếu True, xóa vĩnh viễn
            
        Returns:
            True nếu đã xóa
        """
        conversation = await self.get_conversation(conversation_id, include_messages=False)
        if not conversation:
            return False
        
        if hard_delete:
            await self.session.delete(conversation)
        else:
            conversation.deleted_at = datetime.utcnow()
        
        await self.session.commit()
        logger.info(f"Đã xóa cuộc trò chuyện {conversation_id} (hard={hard_delete})")
        return True
    
    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================
    
    async def get_messages(
        self,
        conversation_id: UUID,
        limit: int = 100,
        before_id: Optional[UUID] = None,
        include_citations: bool = True,
    ) -> List[Message]:
        """
        Lấy các tin nhắn trong cuộc trò chuyện, sắp xếp theo thời gian tạo.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            limit: Số lượng tin nhắn tối đa
            before_id: Lấy tin nhắn trước ID này (để phân trang)
            include_citations: Có load citations hay không (False = faster loading)
            
        Returns:
            Danh sách tin nhắn theo thứ tự thời gian
        """
        query = select(Message).where(
            Message.conversation_id == conversation_id
        )
        
        # Only load citations if requested (expensive JOINs)
        if include_citations:
            query = query.options(
                selectinload(Message.citations).options(
                    joinedload(Citation.chunk).joinedload(Chunk.document_version).joinedload(DocumentVersion.document)
                )
            )
        
        if before_id:
            # Lấy created_at của tin nhắn tham chiếu
            ref_query = select(Message.created_at).where(Message.id == before_id)
            ref_result = await self.session.execute(ref_query)
            ref_time = ref_result.scalar_one_or_none()
            if ref_time:
                query = query.where(Message.created_at < ref_time)
        
        # Sắp xếp theo created_at tăng dần để có thứ tự thời gian
        query = query.order_by(Message.created_at.asc()).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def add_user_message(
        self,
        conversation_id: UUID,
        content: str,
    ) -> Message:
        """
        Thêm tin nhắn người dùng vào cuộc trò chuyện.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            content: Nội dung tin nhắn
            
        Returns:
            Message đã tạo
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=content,
            )
            self.session.add(message)
            
            # Cập nhật timestamp của cuộc trò chuyện
            conversation = await self.get_conversation(conversation_id, include_messages=False)
            if conversation:
                conversation.updated_at = datetime.utcnow()
            
            # Flush để lấy message ID trước khi commit
            await self.session.flush()
            
            # Lưu message ID trước khi commit (để tránh vấn đề lazy loading)
            message_id = message.id
            
            await self.session.commit()
            
            # Reload message sử dụng ID đã lưu để tránh vấn đề lazy loading trong ngữ cảnh async
            result = await self.session.execute(
                select(Message).where(Message.id == message_id)
            )
            message = result.scalar_one()
            
            return message
        except Exception as e:
            logger.error(f"Lỗi khi thêm tin nhắn người dùng: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            raise
    
    async def add_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        policy_mode: Optional[str] = None,
        best_retrieval_score: float = 0.0,
        fallback_used: bool = False,
        citations_data: Optional[list] = None,
    ) -> Message:
        """
        Thêm tin nhắn trợ lý (assistant) với metadata.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            content: Nội dung trả lời
            provider: Provider name (e.g. "groq", "deepseek")
            model: Model name
            prompt_tokens: Số token prompt
            completion_tokens: Số token completion
            latency_ms: Độ trễ phản hồi (ms)
            policy_mode: Chế độ policy
            best_retrieval_score: Điểm retrieval tốt nhất
            fallback_used: Có dùng fallback không
            citations_data: Danh sách citation dicts [{chunk_id, score, quote, page}, ...]
            
        Returns:
            Message đã tạo kèm trích dẫn (citations)
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=content,
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                policy_mode=policy_mode,
                best_retrieval_score=best_retrieval_score,
                fallback_used=fallback_used,
            )
            self.session.add(message)
            await self.session.flush()  # Lấy message ID
            
            # Lưu message ID trước khi thêm citations
            message_id = message.id
            
            # Thêm citations - BATCH INSERT để hiệu năng tốt hơn
            if citations_data:
                citations = [
                    Citation(
                        message_id=message_id,
                        chunk_id=c.get('chunk_id') if isinstance(c, dict) else getattr(c, 'chunk_id', None),
                        score=c.get('score') if isinstance(c, dict) else getattr(c, 'score', None),
                        quote=c.get('quote') if isinstance(c, dict) else getattr(c, 'quote', None),
                        page=c.get('page') if isinstance(c, dict) else getattr(c, 'page', None),
                    )
                    for c in citations_data
                ]
                self.session.add_all(citations)  # Single batch operation
            
            await self.session.commit()
            
            # Reload message với citations được load eagerly sử dụng ID đã lưu
            # Lưu ý: Chunk -> DocumentVersion -> Document (không phải Chunk.document trực tiếp)
            result = await self.session.execute(
                select(Message)
                .where(Message.id == message_id)
                .options(
                    selectinload(Message.citations)
                    .selectinload(Citation.chunk)
                    .selectinload(Chunk.document_version)
                    .selectinload(DocumentVersion.document)
                )
            )
            message = result.scalar_one()
            
            return message
        except Exception as e:
            # Rollback khi có lỗi để xóa trạng thái transaction
            logger.error(f"Lỗi khi thêm tin nhắn trợ lý: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            raise
    
    # =========================================================================
    # USAGE TRACKING
    # =========================================================================
    
    async def track_usage(
        self,
        workspace_id: UUID,
        message_id: UUID,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> Optional[AIUsage]:
        """Theo dõi việc sử dụng AI (AI usage) để phân tích."""
        try:
            # Tính toán chi phí (giá đơn giản hóa)
            cost_per_1k_in = {
                "groq": 0.0001,
                "deepseek": 0.0002,
                "gemini": 0.0003,
                "ollama": 0.0,
            }
            cost_per_1k_out = {
                "groq": 0.0002,
                "deepseek": 0.0004,
                "gemini": 0.0006,
                "ollama": 0.0,
            }
            
            cost_in = (tokens_in / 1000) * cost_per_1k_in.get(provider, 0.0001)
            cost_out = (tokens_out / 1000) * cost_per_1k_out.get(provider, 0.0002)
            
            usage = AIUsage(
                workspace_id=workspace_id,
                message_id=message_id,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_in + cost_out,
            )
            self.session.add(usage)
            await self.session.commit()
            
            return usage
        except Exception as e:
            logger.warning(f"Lỗi khi theo dõi sử dụng AI: {e}")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return None
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def auto_title_conversation(
        self,
        conversation_id: UUID,
    ) -> Optional[str]:
        """
        Tự động tạo tiêu đề từ tin nhắn đầu tiên của người dùng.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            
        Returns:
            Tiêu đề đã tạo hoặc None
        """
        messages = await self.get_messages(conversation_id, limit=1)
        if not messages:
            return None
        
        first_message = messages[0]
        if first_message.role != MessageRole.USER:
            return None
        
        # Cắt bớt để tạo tiêu đề
        content = first_message.content.strip()
        title = content[:50] + "..." if len(content) > 50 else content
        
        await self.update_conversation(conversation_id, title=title)
        return title
    
    async def get_conversation_stats(
        self,
        conversation_id: UUID,
    ) -> dict:
        """
        Lấy thống kê cho một cuộc trò chuyện.
        
        Args:
            conversation_id: ID cuộc trò chuyện
            
        Returns:
            Dict thống kê với số lượng tin nhắn, tokens, v.v.
        """
        messages = await self.get_messages(conversation_id, limit=1000)
        
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]
        
        total_prompt_tokens = sum(m.prompt_tokens or 0 for m in assistant_messages)
        total_completion_tokens = sum(m.completion_tokens or 0 for m in assistant_messages)
        total_latency = sum(m.latency_ms or 0 for m in assistant_messages)
        
        return {
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "avg_latency_ms": total_latency // len(assistant_messages) if assistant_messages else 0,
            "fallback_count": sum(1 for m in assistant_messages if m.fallback_used),
        }


# Backward compatibility alias
ChatService = ConversationService

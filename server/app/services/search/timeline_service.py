"""
Timeline service để cung cấp chronological context xung quanh search results.

Pattern từ claude-mem:
- Hiển thị chunks trước/sau một anchor point
- Giúp hiểu sự phát triển của content
- Cung cấp temporal context để hiểu rõ hơn
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, DocumentVersion

logger = logging.getLogger(__name__)


class TimelineItem:
    """Một item đơn lẻ trong timeline."""
    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        document_title: str,
        content: str,
        created_at: datetime,
        page_start: Optional[int] = None,
        is_anchor: bool = False,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_title = document_title
        self.content = content
        self.created_at = created_at
        self.page_start = page_start
        self.is_anchor = is_anchor


class TimelineService:
    """Service để xây dựng timelines xung quanh chunks."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_timeline(
        self,
        anchor_chunk_id: UUID,
        depth_before: int = 3,
        depth_after: int = 3,
        same_document: bool = True
    ) -> List[TimelineItem]:
        """
        Lấy chunks trước/sau anchor theo thứ tự chronological.
        
        Args:
            anchor_chunk_id: ID của anchor chunk
            depth_before: Số lượng chunks trước anchor
            depth_after: Số lượng chunks sau anchor
            same_document: Chỉ lấy chunks từ cùng document
            
        Returns:
            List TimelineItem theo thứ tự chronological
        """
        # Lấy anchor chunk
        anchor = await self._get_chunk(anchor_chunk_id)
        if not anchor:
            logger.warning(f"Anchor chunk not found: {anchor_chunk_id}")
            return []
        
        # Xây dựng base query
        query = select(Chunk, Document).join(
            DocumentVersion, Chunk.document_version_id == DocumentVersion.id
        ).join(
            Document, DocumentVersion.document_id == Document.id
        )
        
        # Filter theo document nếu được yêu cầu
        if same_document:
            # Lấy document_id từ anchor
            anchor_doc_result = await self.session.execute(
                select(Document.id).join(
                    DocumentVersion, Document.id == DocumentVersion.document_id
                ).join(
                    Chunk, DocumentVersion.id == Chunk.document_version_id
                ).where(Chunk.id == anchor_chunk_id)
            )
            anchor_doc_id = anchor_doc_result.scalar_one()
            query = query.where(Document.id == anchor_doc_id)
        
        # Lấy chunks trước (cũ hơn)
        before_query = query.where(
            Chunk.created_at < anchor.created_at
        ).order_by(Chunk.created_at.desc()).limit(depth_before)
        
        before_result = await self.session.execute(before_query)
        before_chunks = before_result.all()
        
        # Lấy chunks sau (mới hơn)
        after_query = query.where(
            Chunk.created_at > anchor.created_at
        ).order_by(Chunk.created_at.asc()).limit(depth_after)
        
        after_result = await self.session.execute(after_query)
        after_chunks = after_result.all()
        
        # Xây dựng timeline
        timeline = []
        
        # Thêm before chunks (reverse để có thứ tự chronological)
        for chunk, doc in reversed(before_chunks):
            timeline.append(TimelineItem(
                chunk_id=chunk.id,
                document_id=doc.id,
                document_title=doc.title,
                content=chunk.content,
                created_at=chunk.created_at,
                page_start=chunk.page_start,
                is_anchor=False
            ))
        
        # Thêm anchor
        anchor_doc_result = await self.session.execute(
            select(Document).join(
                DocumentVersion, Document.id == DocumentVersion.document_id
            ).join(
                Chunk, DocumentVersion.id == Chunk.document_version_id
            ).where(Chunk.id == anchor_chunk_id)
        )
        anchor_doc = anchor_doc_result.scalar_one()
        
        timeline.append(TimelineItem(
            chunk_id=anchor.id,
            document_id=anchor_doc.id,
            document_title=anchor_doc.title,
            content=anchor.content,
            created_at=anchor.created_at,
            page_start=anchor.page_start,
            is_anchor=True
        ))
        
        # Thêm after chunks
        for chunk, doc in after_chunks:
            timeline.append(TimelineItem(
                chunk_id=chunk.id,
                document_id=doc.id,
                document_title=doc.title,
                content=chunk.content,
                created_at=chunk.created_at,
                page_start=chunk.page_start,
                is_anchor=False
            ))
        
        logger.debug(f"Built timeline with {len(timeline)} items around {anchor_chunk_id}")
        return timeline
    
    async def _get_chunk(self, chunk_id: UUID) -> Optional[Chunk]:
        """Lấy một chunk theo ID."""
        result = await self.session.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

"""
Service tìm kiếm (Retriever) cho RAG pipeline.
Thực hiện tìm kiếm vector (Vector Search) sử dụng pgvector và độ tương đồng Cosine.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, DocumentVersion
from app.services.core.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Kết quả trả về từ quá trình tìm kiếm (Retrieval)."""
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    rerank_score: Optional[float] = None  # MỚI: Điểm số sau khi Rerank (Cross-encoder)


class RetrieverService:
    """
    Service chịu trách nhiệm tìm kiếm các đoạn văn bản (chunks) liên quan
    dựa trên vector similarity (tìm kiếm ngữ nghĩa).
    """
    
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService = None,
    ):
        """
        Khởi tạo retriever service.
        
        Args:
            session: DB session
            embedding_service: Instance của Embedding service
        """
        self.session = session
        self.embedding_service = embedding_service or get_embedding_service()
    
    async def search(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int = 5,
        min_score: float = 0.0,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[RetrievalResult]:
        """
        Tìm kiếm các chunks liên quan dùng vector similarity.
        
        Quy trình:
        1. Tạo embedding cho câu query.
        2. So khớp vector với data trong DB dùng pgvector.
        3. Nếu lỗi vector search -> Fallback về tìm kiếm text cơ bản.
        
        Args:
            query: Câu hỏi người dùng
            workspace_id: ID workspace cần tìm
            top_k: Số lượng kết quả trả về
            min_score: Ngưỡng điểm tương đồng tối thiểu
            document_ids: Lọc theo danh sách tài liệu cụ thể (nếu có)
            tags: Lọc theo tags (nếu có)
            
        Returns:
            Danh sách RetrievalResult sắp xếp theo điểm giảm dần
        """
        if not query or not query.strip():
            return []
        
        # Tạo embedding cho query - hàm embed_text trả về tuple (embedding, model_info)
        query_embedding, _ = self.embedding_service.embed_text(query)
        
        # Xây dựng query với pgvector cosine similarity
        # Lưu ý: pgvector dùng toán tử <=> để tính khoảng cách (distance),
        # nhưng ta cần độ tương đồng (similarity) nên phải convert lại.
        try:
            results = await self._search_with_pgvector(
                query_embedding=query_embedding,
                workspace_id=workspace_id,
                top_k=top_k,
                min_score=min_score,
                document_ids=document_ids,
                tags=tags,
            )
            return results
        except Exception as e:
            logger.warning(f"Lỗi pgvector search: {e}, đang fallback về tìm kiếm cơ bản")
            # Cần rollback để clear transaction bị lỗi trước khi chạy fallback
            try:
                await self.session.rollback()
            except Exception:
                pass
            
            try:
                results = await self._search_basic(
                    query=query,
                    workspace_id=workspace_id,
                    top_k=top_k,
                )
                return results
            except Exception as e2:
                logger.warning(f"Tìm kiếm cơ bản cũng thất bại: {e2}")
                # Rollback tiếp nếu fallback cũng fail
                try:
                    await self.session.rollback()
                except Exception:
                    pass
                return []
    
    async def _search_with_pgvector(
        self,
        query_embedding: List[float],
        workspace_id: UUID,
        top_k: int,
        min_score: float,
        document_ids: List[UUID] = None,
        tags: List[str] = None,
    ) -> List[RetrievalResult]:
        """
        Thực hiện search vector dùng toán tử cosine similarity của pgvector.
        Hỗ trợ filter theo document_ids và tags.
        """
        try:
            # Build chuỗi vector để đưa vào SQL (string interpolation an toàn với internal values)
            embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
            
            # Xây dựng điều kiện WHERE
            conditions = [
                f"d.workspace_id = '{str(workspace_id)}'",
                "d.status IN ('READY', 'READY_BASIC', 'READY_ENRICHED')",
                "c.embedding IS NOT NULL",
            ]
            
            # Thêm filter document_ids nếu có
            if document_ids:
                doc_ids_str = ",".join(f"'{str(did)}'" for did in document_ids)
                conditions.append(f"d.id IN ({doc_ids_str})")
            
            # Thêm filter tags (document phải có ít nhất 1 tag khớp)
            if tags:
                tags_str = ",".join(f"'{t}'" for t in tags)
                conditions.append(f"d.tags && ARRAY[{tags_str}]::varchar[]")
            
            where_clause = " AND ".join(conditions)
            
            # Dùng raw SQL để tối ưu performace với pgvector
            sql = text(f"""
                SELECT 
                    c.id as chunk_id,
                    d.id as document_id,
                    d.title as document_title,
                    c.content,
                    c.page_start,
                    c.page_end,
                    c.section_title,
                    1 - (c.embedding <=> '{embedding_str}'::vector) as score
                FROM chunks c
                JOIN document_versions dv ON c.document_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE {where_clause}
                AND 1 - (c.embedding <=> '{embedding_str}'::vector) >= {min_score}
                ORDER BY c.embedding <=> '{embedding_str}'::vector
                LIMIT {top_k}
            """)
            
            result = await self.session.execute(sql)
            rows = result.fetchall()
            
            return [
                RetrievalResult(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    document_title=row.document_title,
                    content=row.content,
                    score=float(row.score),
                    page_start=row.page_start,
                    page_end=row.page_end,
                    section_title=row.section_title,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Lỗi query pgvector: {e}")
            raise
    
    async def _search_basic(
        self,
        query: str,
        workspace_id: UUID,
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        Tìm kiếm text cơ bản (Fallback) khi pgvector không khả dụng.
        Sử dụng thuật toán so khớp từ khóa đơn giản (Keyword Matching).
        """
        try:
            # Lấy tất cả chunks trong workspace (giới hạn số lượng để tránh OOM)
            result = await self.session.execute(
                select(Chunk, Document)
                .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
                .join(Document, DocumentVersion.document_id == Document.id)
                .where(Document.workspace_id == workspace_id)
                .where(Document.status.in_(["READY", "READY_BASIC", "READY_ENRICHED"]))
                .limit(top_k * 10)  # Lấy dư ra 1 chút để lọc
            )
            
            rows = result.all()
            
            # Tính điểm keyword đơn giản
            query_words = set(query.lower().split())
            scored_results = []
            
            for chunk, document in rows:
                if not chunk.content:
                    continue
                
                content_words = set(chunk.content.lower().split())
                overlap = len(query_words & content_words)
                score = overlap / max(len(query_words), 1)
                
                if score > 0:
                    scored_results.append(RetrievalResult(
                        chunk_id=chunk.id,
                        document_id=document.id,
                        document_title=document.title,
                        content=chunk.content,
                        score=score,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        section_title=chunk.section_title,
                    ))
            
            # Sắp xếp theo điểm và lấy top_k
            scored_results.sort(key=lambda x: x.score, reverse=True)
            return scored_results[:top_k]
        except Exception as e:
            logger.warning(f"Lỗi basic search: {e}")
            raise
    
    async def get_chunk_by_id(self, chunk_id: UUID) -> Optional[Chunk]:
        """Lấy thông tin chi tiết của một chunk theo ID."""
        result = await self.session.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

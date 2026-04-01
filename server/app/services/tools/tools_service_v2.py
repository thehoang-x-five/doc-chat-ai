"""
Production-Ready Tools Service sử dụng Pydantic + FastAPI patterns.

Phiên bản này sử dụng:
- Pydantic cho validation
- Lazy imports để tối ưu hiệu năng
- Dependency injection pattern
- Type safety
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL SCHEMAS (Pydantic Models)
# =============================================================================

class CountDocumentsInput(BaseModel):
    """Input schema cho count_documents tool."""
    status: Optional[str] = Field(default="READY", description="Lọc theo status")
    tags: Optional[List[str]] = Field(default=None, description="Lọc theo tags")


class CountDocumentsOutput(BaseModel):
    """Output schema cho count_documents tool."""
    total: int
    status_filter: str
    tags_filter: List[str]
    workspace_id: str


class ListDocumentsInput(BaseModel):
    """Input schema cho list_documents tool."""
    limit: int = Field(default=50, ge=1, le=100, description="Số documents tối đa trả về")
    status: Optional[str] = Field(default="READY", description="Lọc theo status")
    tags: Optional[List[str]] = Field(default=None, description="Lọc theo tags")


class DocumentInfo(BaseModel):
    """Thông tin document."""
    id: str
    title: str
    status: str
    created_at: datetime
    tags: List[str]
    chunk_count: int


class ListDocumentsOutput(BaseModel):
    """Output schema cho list_documents tool."""
    documents: List[DocumentInfo]
    total: int
    limit: int


# =============================================================================
# TOOLS SERVICE (Dependency Injection Pattern)
# =============================================================================

class ToolsServiceV2:
    """
    Tools service production-ready.
    
    Tính năng:
    - Lazy model imports (khởi động nhanh)
    - Pydantic validation (type safety)
    - Dependency injection (dễ test)
    - Async/await (non-blocking)
    """
    
    def __init__(self, session: AsyncSession, workspace_id: UUID):
        """Khởi tạo với database session và workspace."""
        self.session = session
        self.workspace_id = workspace_id
        self._models = None
    
    def _get_models(self):
        """Lazy import models chỉ khi cần."""
        if self._models is None:
            from app.db.models import Document, DocumentVersion, Chunk
            self._models = {
                'Document': Document,
                'DocumentVersion': DocumentVersion,
                'Chunk': Chunk,
            }
        return self._models
    
    async def count_documents(
        self,
        input_data: CountDocumentsInput
    ) -> CountDocumentsOutput:
        """
        Đếm documents trong workspace.
        
        Args:
            input_data: Input parameters đã được validate
            
        Returns:
            CountDocumentsOutput với count và filters
        """
        from sqlalchemy import select, func
        
        models = self._get_models()
        Document = models['Document']
        
        # Build query
        query = select(func.count(Document.id)).where(
            Document.workspace_id == self.workspace_id
        )
        
        # Áp dụng status filter
        if input_data.status and input_data.status != "all":
            query = query.where(Document.status == input_data.status)
        
        # Áp dụng tags filter
        if input_data.tags:
            query = query.where(Document.tags.overlap(input_data.tags))
        
        # Thực thi
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        return CountDocumentsOutput(
            total=count,
            status_filter=input_data.status or "all",
            tags_filter=input_data.tags or [],
            workspace_id=str(self.workspace_id)
        )
    
    async def list_documents(
        self,
        input_data: ListDocumentsInput
    ) -> ListDocumentsOutput:
        """
        Liệt kê documents trong workspace.
        
        Args:
            input_data: Input parameters đã được validate
            
        Returns:
            ListDocumentsOutput với danh sách document
        """
        from sqlalchemy import select, func, desc
        
        models = self._get_models()
        Document = models['Document']
        Chunk = models['Chunk']
        
        # Build query
        query = select(Document).where(
            Document.workspace_id == self.workspace_id
        )
        
        # Áp dụng filters
        if input_data.status and input_data.status != "all":
            query = query.where(Document.status == input_data.status)
        
        if input_data.tags:
            query = query.where(Document.tags.overlap(input_data.tags))
        
        # Sắp xếp và giới hạn
        query = query.order_by(desc(Document.created_at)).limit(input_data.limit)
        
        # Thực thi
        result = await self.session.execute(query)
        documents = result.scalars().all()
        
        # Lấy số lượng chunks
        doc_infos = []
        for doc in documents:
            # Đếm chunks cho document này
            chunk_query = select(func.count(Chunk.id)).where(
                Chunk.document_id == doc.id
            )
            chunk_result = await self.session.execute(chunk_query)
            chunk_count = chunk_result.scalar() or 0
            
            doc_infos.append(DocumentInfo(
                id=str(doc.id),
                title=doc.title,
                status=doc.status,
                created_at=doc.created_at,
                tags=doc.tags or [],
                chunk_count=chunk_count
            ))
        
        return ListDocumentsOutput(
            documents=doc_infos,
            total=len(doc_infos),
            limit=input_data.limit
        )


# =============================================================================
# TOOL REGISTRY (OpenAI Format)
# =============================================================================

def get_tools_definitions() -> List[Dict[str, Any]]:
    """
    Lấy định nghĩa tools theo format OpenAI function calling.
    
    Returns:
        Danh sách định nghĩa tools
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "count_documents",
                "description": "Đếm số lượng tài liệu trong workspace. Dùng khi người dùng hỏi 'có bao nhiêu tài liệu', 'đếm số file', 'tổng số documents'.",
                "parameters": CountDocumentsInput.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_documents",
                "description": "Liệt kê danh sách tài liệu với thông tin chi tiết. Dùng khi người dùng hỏi 'liệt kê file', 'danh sách tài liệu', 'có những file nào'.",
                "parameters": ListDocumentsInput.model_json_schema()
            }
        }
    ]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    session: AsyncSession,
    workspace_id: UUID
) -> Dict[str, Any]:
    """
    Thực thi một tool theo tên.
    
    Args:
        tool_name: Tên tool cần thực thi
        arguments: Arguments cho tool (sẽ được validate)
        session: Database session
        workspace_id: Workspace ID
        
    Returns:
        Kết quả thực thi tool
        
    Raises:
        ValueError: Nếu tool không tìm thấy hoặc validation thất bại
    """
    service = ToolsServiceV2(session, workspace_id)
    
    if tool_name == "count_documents":
        input_data = CountDocumentsInput(**arguments)
        result = await service.count_documents(input_data)
        return result.model_dump()
    
    elif tool_name == "list_documents":
        input_data = ListDocumentsInput(**arguments)
        result = await service.list_documents(input_data)
        return result.model_dump()
    
    else:
        raise ValueError(f"Tool không rõ: {tool_name}")

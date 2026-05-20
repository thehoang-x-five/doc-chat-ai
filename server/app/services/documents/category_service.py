"""
Dịch vụ Quản lý Danh mục Tài liệu.

Tự động phân loại tài liệu sử dụng LLM và quản lý các danh mục.
Cung cấp ngữ cảnh cho việc nhận diện ý định (intent detection).
"""
import logging
import json
import re
from typing import Optional, List, Dict
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentCategory, Chunk, DocumentStatus

logger = logging.getLogger(__name__)

READY_DOCUMENT_STATUSES = (
    DocumentStatus.READY,
    DocumentStatus.READY_BASIC,
    DocumentStatus.READY_ENRICHED,
)


@dataclass
class CategorySuggestion:
    """Đề xuất danh mục cho một tài liệu."""
    name: str
    slug: str
    description: str
    keywords: List[str]
    confidence: float


@dataclass
class DocumentSummary:
    """Tóm tắt nội dung tài liệu."""
    summary: str
    main_headings: List[str]
    keywords: List[str]
    suggested_category: str


class CategoryService:
    """
    Dịch vụ quản lý danh mục tài liệu.
    
    Tính năng:
    - Tự động phân loại tài liệu sử dụng LLM
    - Tạo tóm tắt danh mục cho nhận diện ý định
    - Quản lý các thao tác CRUD danh mục
    """
    
    CATEGORIZE_PROMPT = """Phân tích tài liệu và đề xuất category phù hợp.

Tiêu đề tài liệu: {title}
Nội dung mẫu (500 ký tự đầu):
{content_sample}

Categories hiện có trong workspace:
{existing_categories}

Trả lời theo format JSON:
{{
    "suggested_category": "<tên category phù hợp nhất, hoặc tên mới nếu không có category phù hợp>",
    "is_new_category": <true nếu cần tạo category mới, false nếu dùng category có sẵn>,
    "category_description": "<mô tả ngắn về category nếu là category mới>",
    "document_summary": "<tóm tắt 1-2 câu về nội dung tài liệu>",
    "main_headings": ["<tiêu đề chính 1>", "<tiêu đề chính 2>", ...],
    "keywords": ["<từ khóa 1>", "<từ khóa 2>", ...]
}}

Lưu ý:
- Tên category nên ngắn gọn, dễ hiểu (VD: "Hợp đồng", "Quy chế", "Báo cáo tài chính")
- Nếu tài liệu phù hợp với category có sẵn, ưu tiên dùng category đó
- Keywords nên là các từ khóa chính trong tài liệu"""

    SUMMARY_PROMPT = """Tóm tắt nội dung category dựa trên các tài liệu bên trong.

Category: {category_name}
Mô tả: {category_description}

Danh sách tài liệu:
{documents_info}

Tạo một đoạn tóm tắt ngắn (2-3 câu) mô tả:
1. Loại tài liệu trong category này
2. Các chủ đề chính được đề cập
3. Ai có thể cần tìm kiếm trong category này

Trả lời bằng tiếng Việt, ngắn gọn và rõ ràng."""

    def __init__(self, session: AsyncSession):
        """Khởi tạo category service."""
        self.session = session
        self._timeout = 15.0
    
    async def get_or_create_category(
        self, 
        workspace_id: UUID, 
        name: str,
        description: str = None,
        keywords: List[str] = None,
    ) -> DocumentCategory:
        """Lấy danh mục hiện có hoặc tạo mới."""
        slug = self._slugify(name)
        
        # Kiểm tra xem đã tồn tại chưa
        query = select(DocumentCategory).where(
            DocumentCategory.workspace_id == workspace_id,
            DocumentCategory.slug == slug
        )
        result = await self.session.execute(query)
        category = result.scalar_one_or_none()
        
        if category:
            return category
        
        # Tạo mới
        category = DocumentCategory(
            workspace_id=workspace_id,
            name=name,
            slug=slug,
            description=description,
            keywords=keywords or [],
            is_auto_generated=True,
        )
        self.session.add(category)
        await self.session.flush()
        
        logger.info(f"Đã tạo category mới: {name} (workspace: {workspace_id})")
        return category
    
    async def auto_categorize_document(
        self, 
        document: Document,
        content_sample: str = None,
    ) -> Optional[DocumentCategory]:
        """
        Tự động phân loại tài liệu sử dụng LLM.
        
        Args:
            document: Tài liệu cần phân loại
            content_sample: Nội dung mẫu để phân tích (nếu không cung cấp, sẽ lấy từ chunks)
            
        Returns:
            Danh mục được gán hoặc None nếu thất bại
        """
        try:
            # Lấy nội dung mẫu nếu chưa có
            if not content_sample:
                content_sample = await self._get_document_content_sample(document.id)
            
            if not content_sample:
                logger.warning(f"Không có nội dung mẫu cho tài liệu {document.id}")
                return None
            
            # Lấy danh sách danh mục hiện có
            existing_categories = await self.list_categories(document.workspace_id)
            categories_str = "\n".join([
                f"- {c.name}: {c.description or 'Không có mô tả'}"
                for c in existing_categories
            ]) or "Chưa có category nào"
            
            # Gọi LLM để phân loại
            result = await self._call_llm_categorize(
                title=document.title,
                content_sample=content_sample[:1000],  # Giới hạn 1000 ký tự
                existing_categories=categories_str,
            )
            
            if not result:
                return None
            
            # Lấy hoặc tạo danh mục
            category = await self.get_or_create_category(
                workspace_id=document.workspace_id,
                name=result.get("suggested_category", "Khác"),
                description=result.get("category_description"),
                keywords=result.get("keywords", []),
            )
            
            # Cập nhật tài liệu với tóm tắt và tiêu đề chính
            document.category_id = category.id
            document.content_summary = result.get("document_summary")
            document.main_headings = result.get("main_headings", [])
            
            await self.session.flush()
            
            logger.info(f"Tài liệu {document.id} được phân loại vào: {category.name}")
            
            # Tự động cập nhật tóm tắt danh mục sau khi phân loại
            try:
                await self.update_category_summary(category.id)
            except Exception as e:
                logger.warning(f"Không thể cập nhật tóm tắt danh mục {category.name}: {e}")
            
            return category
            
        except Exception as e:
            logger.error(f"Tự động phân loại thất bại cho tài liệu {document.id}: {e}")
            return None
    
    async def update_category_summary(self, category_id: UUID) -> Optional[str]:
        """
        Cập nhật tóm tắt danh mục dựa trên các tài liệu bên trong.
        Được gọi sau khi tài liệu được thêm/xóa.
        """
        try:
            # Lấy category
            query = select(DocumentCategory).where(DocumentCategory.id == category_id)
            result = await self.session.execute(query)
            category = result.scalar_one_or_none()
            
            if not category:
                return None
            
            # Lấy tài liệu trong category
            docs_query = select(Document).where(
                Document.category_id == category_id,
                Document.status.in_(READY_DOCUMENT_STATUSES),
            ).limit(10)
            docs_result = await self.session.execute(docs_query)
            documents = docs_result.scalars().all()
            
            if not documents:
                return None
            
            # Xây dựng thông tin tài liệu
            docs_info = "\n".join([
                f"- {d.title}: {d.content_summary or 'Không có tóm tắt'}"
                for d in documents
            ])
            
            # Gọi LLM để tóm tắt
            summary = await self._call_llm_summary(
                category_name=category.name,
                category_description=category.description or "",
                documents_info=docs_info,
            )
            if not summary:
                doc_titles = ", ".join(d.title for d in documents[:5])
                summary = (
                    f'Category "{category.name}" hiện có {len(documents)} tài liệu đã xử lý'
                    f"{': ' + doc_titles if doc_titles else ''}. "
                    "Chưa tạo được tóm tắt AI chi tiết do provider tạm thời không khả dụng."
                )
            
            if summary:
                category.content_summary = summary
                # Trích xuất từ khóa từ tài liệu
                all_keywords = []
                for d in documents:
                    if d.main_headings:
                        all_keywords.extend(d.main_headings[:3])
                category.keywords = list(set(all_keywords))[:10]
                
                await self.session.flush()
            
            return summary
            
        except Exception as e:
            logger.error(f"Cập nhật tóm tắt danh mục thất bại: {e}")
            return None
    
    async def list_categories(self, workspace_id: UUID) -> List[DocumentCategory]:
        """Liệt kê tất cả danh mục trong workspace."""
        try:
            query = select(DocumentCategory).where(
                DocumentCategory.workspace_id == workspace_id
            ).order_by(DocumentCategory.display_order, DocumentCategory.name)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            # Bảng có thể chưa tồn tại
            logger.debug(f"Không thể liệt kê danh mục (bảng có thể chưa tồn tại): {e}")
            return []
    
    async def get_category_names(self, workspace_id: UUID) -> List[str]:
        """
        Lấy danh sách tên danh mục (để nhận diện ý định nhanh).
        
        Returns:
            Danh sách tên danh mục có chứa tài liệu
        """
        try:
            categories = await self.list_categories(workspace_id)
            
            names = []
            for cat in categories:
                # Chỉ bao gồm danh mục có tài liệu
                try:
                    count_query = select(func.count(Document.id)).where(
                        Document.category_id == cat.id,
                        Document.status.in_(READY_DOCUMENT_STATUSES),
                    )
                    count_result = await self.session.execute(count_query)
                    doc_count = count_result.scalar() or 0
                    
                    if doc_count > 0:
                        names.append(cat.name)
                except Exception as e:
                    # Nếu đếm thất bại, vẫn bao gồm danh mục
                    logger.debug(f"Không thể đếm tài liệu cho danh mục {cat.name}: {e}")
                    names.append(cat.name)
            
            return names
        except Exception as e:
            logger.warning(f"Lỗi khi lấy tên danh mục: {e}")
            return []
    
    async def get_category_context_for_intent(self, workspace_id: UUID) -> str:
        """
        Lấy chuỗi ngữ cảnh danh mục cho nhận diện ý định.
        
        Trả về chuỗi định dạng mô tả tất cả danh mục và nội dung của chúng.
        """
        categories = await self.list_categories(workspace_id)
        
        if not categories:
            return ""
        
        context_parts = ["Các nhóm tài liệu trong hệ thống:"]
        
        for cat in categories:
            # Đếm tài liệu
            count_query = select(func.count(Document.id)).where(
                Document.category_id == cat.id,
                Document.status.in_(READY_DOCUMENT_STATUSES),
            )
            count_result = await self.session.execute(count_query)
            doc_count = count_result.scalar() or 0
            
            if doc_count == 0:
                continue
            
            part = f"\n📁 {cat.name} ({doc_count} tài liệu)"
            if cat.content_summary:
                part += f"\n   {cat.content_summary}"
            if cat.keywords:
                part += f"\n   Từ khóa: {', '.join(cat.keywords[:5])}"
            
            context_parts.append(part)
        
        return "\n".join(context_parts)
    
    async def _get_document_content_sample(self, document_id: UUID) -> Optional[str]:
        """Lấy mẫu nội dung từ các chunks của tài liệu."""
        from app.db.models import DocumentVersion
        
        # Lấy phiên bản mới nhất
        version_query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        ).order_by(DocumentVersion.version.desc()).limit(1)
        
        version_result = await self.session.execute(version_query)
        version = version_result.scalar_one_or_none()
        
        if not version:
            return None
        
        # Lấy một vài chunks đầu tiên
        chunks_query = select(Chunk.content).where(
            Chunk.document_version_id == version.id
        ).order_by(Chunk.chunk_index).limit(3)
        
        chunks_result = await self.session.execute(chunks_query)
        chunks = [row[0] for row in chunks_result.fetchall() if row[0]]
        
        return "\n\n".join(chunks) if chunks else None
    
    async def _call_llm_categorize(
        self, 
        title: str, 
        content_sample: str,
        existing_categories: str,
    ) -> Optional[Dict]:
        """Gọi LLM để phân loại tài liệu sử dụng AIProviderManager với fallback."""
        from app.services.infrastructure.ai_providers.manager import provider_manager
        
        prompt = self.CATEGORIZE_PROMPT.format(
            title=title,
            content_sample=content_sample,
            existing_categories=existing_categories,
        )
        
        try:
            # Lấy các provider khả dụng theo thứ tự ưu tiên
            available_providers = provider_manager._get_available_providers()
            
            if not available_providers:
                logger.warning("Không có provider khả dụng cho phân loại")
                return None
            
            for provider_name in available_providers:
                try:
                    provider = provider_manager.providers.get(provider_name)
                    if not provider:
                        continue
                    
                    logger.info(f"Đang thử phân loại với {provider_name}")
                    
                    messages = [{"role": "user", "content": prompt}]
                    response = await provider.chat_completion(messages)
                    
                    if response:
                        # Parse JSON từ response
                        if "{" in response and "}" in response:
                            json_str = response[response.find("{"):response.rfind("}")+1]
                            result = json.loads(json_str)
                            logger.info(f"Phân loại thành công với {provider_name}")
                            return result
                            
                except Exception as e:
                    logger.warning(f"Phân loại với {provider_name} thất bại: {e}")
                    continue
            
            logger.error("Tất cả provider đều thất bại khi phân loại")
            return None
            
        except Exception as e:
            logger.error(f"LLM categorize thất bại: {e}")
            return None
    
    async def _call_llm_summary(
        self,
        category_name: str,
        category_description: str,
        documents_info: str,
    ) -> Optional[str]:
        """Gọi LLM để tạo tóm tắt danh mục sử dụng AIProviderManager."""
        from app.services.infrastructure.ai_providers.manager import provider_manager
        
        prompt = self.SUMMARY_PROMPT.format(
            category_name=category_name,
            category_description=category_description,
            documents_info=documents_info,
        )
        
        try:
            available_providers = provider_manager._get_available_providers()
            
            for provider_name in available_providers:
                try:
                    provider = provider_manager.providers.get(provider_name)
                    if not provider:
                        continue
                    
                    messages = [{"role": "user", "content": prompt}]
                    response = await provider.chat_completion(messages)
                    
                    if response:
                        return response.strip()
                        
                except Exception as e:
                    logger.warning(f"Tóm tắt với {provider_name} thất bại: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"LLM summary thất bại: {e}")
            return None
    
    def _slugify(self, text: str) -> str:
        """Chuyển đổi văn bản thành slug."""
        # Slugify đơn giản cho tiếng Việt
        slug = text.lower().strip()
        slug = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', slug)
        slug = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', slug)
        slug = re.sub(r'[ìíịỉĩ]', 'i', slug)
        slug = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', slug)
        slug = re.sub(r'[ùúụủũưừứựửữ]', 'u', slug)
        slug = re.sub(r'[ỳýỵỷỹ]', 'y', slug)
        slug = re.sub(r'[đ]', 'd', slug)
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

"""
Analytics service theo dõi việc sử dụng và báo cáo.
Tổng hợp mức sử dụng AI, chi phí, và cung cấp dữ liệu dashboard.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AIUsage, Job, Message, Document, Conversation, Workspace,
    JobStatus, DocumentStatus
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service cho analytics và báo cáo sử dụng.
    """
    
    def __init__(self, session: AsyncSession):
        """Khởi tạo analytics service."""
        self.session = session
    
    # =========================================================================
    # TỔNG HỢP MỨC SỬ DỤNG (USAGE AGGREGATION)
    # =========================================================================
    
    async def get_usage_summary(
        self,
        workspace_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Lấy tóm tắt mức sử dụng cho một workspace.
        
        Args:
            workspace_id: ID Workspace
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            
        Returns:
            Dict tóm tắt mức sử dụng
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Truy vấn tổng hợp usage
        query = select(
            func.sum(AIUsage.tokens_in).label("total_tokens_in"),
            func.sum(AIUsage.tokens_out).label("total_tokens_out"),
            func.sum(AIUsage.cost_usd).label("total_cost"),
            func.count(AIUsage.id).label("total_requests"),
        ).where(
            and_(
                AIUsage.workspace_id == workspace_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        )
        
        result = await self.session.execute(query)
        row = result.one()
        
        return {
            "workspace_id": str(workspace_id),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "totals": {
                "tokens_in": row.total_tokens_in or 0,
                "tokens_out": row.total_tokens_out or 0,
                "total_tokens": (row.total_tokens_in or 0) + (row.total_tokens_out or 0),
                "cost_usd": float(row.total_cost or 0),
                "requests": row.total_requests or 0,
            },
        }
    
    async def get_usage_by_provider(
        self,
        workspace_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lấy thống kê mức sử dụng theo AI provider.
        
        Args:
            workspace_id: ID Workspace
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            
        Returns:
            List các dict usage theo provider
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = select(
            AIUsage.provider,
            func.sum(AIUsage.tokens_in).label("tokens_in"),
            func.sum(AIUsage.tokens_out).label("tokens_out"),
            func.sum(AIUsage.cost_usd).label("cost"),
            func.count(AIUsage.id).label("requests"),
        ).where(
            and_(
                AIUsage.workspace_id == workspace_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        ).group_by(AIUsage.provider).order_by(desc("cost"))
        
        result = await self.session.execute(query)
        
        return [
            {
                "provider": row.provider,
                "tokens_in": row.tokens_in or 0,
                "tokens_out": row.tokens_out or 0,
                "total_tokens": (row.tokens_in or 0) + (row.tokens_out or 0),
                "cost_usd": float(row.cost or 0),
                "requests": row.requests or 0,
            }
            for row in result.all()
        ]
    
    async def get_usage_by_model(
        self,
        workspace_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lấy thống kê mức sử dụng theo AI model.
        
        Args:
            workspace_id: ID Workspace
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            
        Returns:
            List các dict usage theo model
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = select(
            AIUsage.provider,
            AIUsage.model,
            func.sum(AIUsage.tokens_in).label("tokens_in"),
            func.sum(AIUsage.tokens_out).label("tokens_out"),
            func.sum(AIUsage.cost_usd).label("cost"),
            func.count(AIUsage.id).label("requests"),
        ).where(
            and_(
                AIUsage.workspace_id == workspace_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        ).group_by(AIUsage.provider, AIUsage.model).order_by(desc("cost"))
        
        result = await self.session.execute(query)
        
        return [
            {
                "provider": row.provider,
                "model": row.model,
                "tokens_in": row.tokens_in or 0,
                "tokens_out": row.tokens_out or 0,
                "total_tokens": (row.tokens_in or 0) + (row.tokens_out or 0),
                "cost_usd": float(row.cost or 0),
                "requests": row.requests or 0,
            }
            for row in result.all()
        ]
    
    async def get_daily_usage(
        self,
        workspace_id: UUID,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Lấy mức sử dụng hàng ngày trong N ngày qua.
        
        Args:
            workspace_id: ID Workspace
            days: Số ngày cần lấy
            
        Returns:
            List các dict usage hàng ngày
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.date(AIUsage.created_at).label("date"),
            func.sum(AIUsage.tokens_in).label("tokens_in"),
            func.sum(AIUsage.tokens_out).label("tokens_out"),
            func.sum(AIUsage.cost_usd).label("cost"),
            func.count(AIUsage.id).label("requests"),
        ).where(
            and_(
                AIUsage.workspace_id == workspace_id,
                AIUsage.created_at >= start_date,
            )
        ).group_by(func.date(AIUsage.created_at)).order_by("date")
        
        result = await self.session.execute(query)
        
        return [
            {
                "date": str(row.date),
                "tokens_in": row.tokens_in or 0,
                "tokens_out": row.tokens_out or 0,
                "total_tokens": (row.tokens_in or 0) + (row.tokens_out or 0),
                "cost_usd": float(row.cost or 0),
                "requests": row.requests or 0,
            }
            for row in result.all()
        ]
    
    # =========================================================================
    # DỮ LIỆU DASHBOARD
    # =========================================================================
    
    async def get_dashboard_stats(
        self,
        workspace_id: UUID,
    ) -> Dict[str, Any]:
        """
        Lấy thống kê dashboard cho một workspace.
        
        Args:
            workspace_id: ID Workspace
            
        Returns:
            Dict thống kê dashboard
        """
        # Đếm Document
        doc_query = select(
            func.count(Document.id).label("total"),
            func.sum(
                func.cast(Document.status.in_([DocumentStatus.READY, DocumentStatus.READY_BASIC, DocumentStatus.READY_ENRICHED]), Integer)
            ).label("ready"),
            func.sum(
                func.cast(Document.status == DocumentStatus.INDEXING, Integer)
            ).label("indexing"),
            func.sum(
                func.cast(Document.status == DocumentStatus.FAILED, Integer)
            ).label("failed"),
        ).where(Document.workspace_id == workspace_id)
        
        # Sử dụng count queries đơn giản hơn
        total_docs = await self.session.execute(
            select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
        )
        ready_docs = await self.session.execute(
            select(func.count(Document.id)).where(
                and_(Document.workspace_id == workspace_id, Document.status.in_(["READY", "READY_BASIC", "READY_ENRICHED"]))
            )
        )
        
        # Đếm Job
        total_jobs = await self.session.execute(
            select(func.count(Job.id)).where(Job.workspace_id == workspace_id)
        )
        running_jobs = await self.session.execute(
            select(func.count(Job.id)).where(
                and_(Job.workspace_id == workspace_id, Job.status == "RUNNING")
            )
        )
        
        # Đếm Conversation
        total_convs = await self.session.execute(
            select(func.count(Conversation.id)).where(
                and_(
                    Conversation.workspace_id == workspace_id,
                    Conversation.deleted_at.is_(None),
                )
            )
        )
        
        # Đếm Message
        total_msgs = await self.session.execute(
            select(func.count(Message.id)).select_from(Message).join(
                Conversation, Message.conversation_id == Conversation.id
            ).where(Conversation.workspace_id == workspace_id)
        )
        
        # Usage gần đây (24h qua)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_usage = await self.session.execute(
            select(
                func.sum(AIUsage.tokens_in + AIUsage.tokens_out).label("tokens"),
                func.sum(AIUsage.cost_usd).label("cost"),
            ).where(
                and_(
                    AIUsage.workspace_id == workspace_id,
                    AIUsage.created_at >= yesterday,
                )
            )
        )
        usage_row = recent_usage.one()
        
        return {
            "documents": {
                "total": total_docs.scalar() or 0,
                "ready": ready_docs.scalar() or 0,
            },
            "jobs": {
                "total": total_jobs.scalar() or 0,
                "running": running_jobs.scalar() or 0,
            },
            "conversations": {
                "total": total_convs.scalar() or 0,
            },
            "messages": {
                "total": total_msgs.scalar() or 0,
            },
            "usage_24h": {
                "tokens": usage_row.tokens or 0,
                "cost_usd": float(usage_row.cost or 0),
            },
        }
    
    async def get_recent_activity(
        self,
        workspace_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Lấy các hoạt động gần đây trong workspace.
        
        Args:
            workspace_id: ID Workspace
            limit: Số lượng tối đa trả về
            
        Returns:
            List các activities
        """
        activities = []
        
        # Jobs gần đây
        jobs_query = select(Job).where(
            Job.workspace_id == workspace_id
        ).order_by(desc(Job.created_at)).limit(limit)
        
        jobs_result = await self.session.execute(jobs_query)
        for job in jobs_result.scalars():
            activities.append({
                "type": "job",
                "id": str(job.id),
                "action": f"{job.type} job {job.status.lower()}",
                "status": job.status,
                "created_at": job.created_at.isoformat(),
            })
        
        # Conversations gần đây
        convs_query = select(Conversation).where(
            and_(
                Conversation.workspace_id == workspace_id,
                Conversation.deleted_at.is_(None),
            )
        ).order_by(desc(Conversation.created_at)).limit(limit)
        
        convs_result = await self.session.execute(convs_query)
        for conv in convs_result.scalars():
            activities.append({
                "type": "conversation",
                "id": str(conv.id),
                "action": f"Conversation: {conv.title or 'Untitled'}",
                "created_at": conv.created_at.isoformat(),
            })
        
        # Sắp xếp theo created_at và giới hạn
        activities.sort(key=lambda x: x["created_at"], reverse=True)
        return activities[:limit]
    
    # =========================================================================
    # TÍNH TOÁN CHI PHÍ (COST CALCULATION)
    # =========================================================================
    
    async def calculate_estimated_cost(
        self,
        workspace_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Tính toán chi phí ước tính với breakdown chi tiết.
        
        Args:
            workspace_id: ID Workspace
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            
        Returns:
            Dict breakdown chi phí
        """
        usage_by_provider = await self.get_usage_by_provider(
            workspace_id, start_date, end_date
        )
        
        total_cost = sum(p["cost_usd"] for p in usage_by_provider)
        
        return {
            "total_cost_usd": total_cost,
            "by_provider": usage_by_provider,
            "period": {
                "start": (start_date or datetime.utcnow() - timedelta(days=30)).isoformat(),
                "end": (end_date or datetime.utcnow()).isoformat(),
            },
        }

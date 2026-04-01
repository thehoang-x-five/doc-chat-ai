"""
Analytics API endpoints.
Provides usage statistics, cost breakdown, and dashboard data.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.services.analytics.analytics_service import AnalyticsService
from app.schemas.analytics import (
    UsageSummaryResponse,
    UsageByProviderResponse,
    UsageByModelResponse,
    DailyUsageResponse,
    DashboardStatsResponse,
    RecentActivityResponse,
    CostBreakdownResponse,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage_summary(
    workspace_id: UUID,
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get usage summary for a workspace.
    
    Returns total tokens, costs, and request counts for the specified period.
    Default period is last 30 days.
    """
    service = AnalyticsService(db)
    return await service.get_usage_summary(workspace_id, start_date, end_date)


@router.get("/usage/by-provider", response_model=UsageByProviderResponse)
async def get_usage_by_provider(
    workspace_id: UUID,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get usage breakdown by AI provider.
    
    Returns usage statistics grouped by provider (OpenAI, Anthropic, etc.).
    """
    service = AnalyticsService(db)
    data = await service.get_usage_by_provider(workspace_id, start_date, end_date)
    return {"providers": data}


@router.get("/usage/by-model", response_model=UsageByModelResponse)
async def get_usage_by_model(
    workspace_id: UUID,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get usage breakdown by AI model.
    
    Returns usage statistics grouped by model (gpt-4, claude-3, etc.).
    """
    service = AnalyticsService(db)
    data = await service.get_usage_by_model(workspace_id, start_date, end_date)
    return {"models": data}


@router.get("/usage/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    workspace_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get daily usage for the last N days.
    
    Returns daily token counts, costs, and request counts.
    """
    service = AnalyticsService(db)
    data = await service.get_daily_usage(workspace_id, days)
    return {"days": data}


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard statistics for a workspace.
    
    Returns document counts, job counts, conversation counts,
    and recent usage statistics.
    """
    service = AnalyticsService(db)
    return await service.get_dashboard_stats(workspace_id)


@router.get("/activity", response_model=RecentActivityResponse)
async def get_recent_activity(
    workspace_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent activity in a workspace.
    
    Returns recent jobs, conversations, and other activities.
    """
    service = AnalyticsService(db)
    data = await service.get_recent_activity(workspace_id, limit)
    return {"activities": data}


@router.get("/costs", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    workspace_id: UUID,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get cost breakdown for a workspace.
    
    Returns estimated costs with breakdown by provider.
    """
    service = AnalyticsService(db)
    return await service.calculate_estimated_cost(workspace_id, start_date, end_date)

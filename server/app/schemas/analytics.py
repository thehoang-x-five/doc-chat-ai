"""
Pydantic schemas for analytics endpoints.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# USAGE SCHEMAS
# =============================================================================

class UsagePeriod(BaseModel):
    """Date range for usage query."""
    start: datetime
    end: datetime


class UsageTotals(BaseModel):
    """Total usage metrics."""
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost_usd: float
    requests: int


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""
    workspace_id: str
    period: UsagePeriod
    totals: UsageTotals


class ProviderUsage(BaseModel):
    """Usage by provider."""
    provider: str
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost_usd: float
    requests: int


class ModelUsage(BaseModel):
    """Usage by model."""
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost_usd: float
    requests: int


class DailyUsage(BaseModel):
    """Daily usage metrics."""
    date: str
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost_usd: float
    requests: int


class UsageByProviderResponse(BaseModel):
    """Usage breakdown by provider."""
    providers: List[ProviderUsage]


class UsageByModelResponse(BaseModel):
    """Usage breakdown by model."""
    models: List[ModelUsage]


class DailyUsageResponse(BaseModel):
    """Daily usage response."""
    days: List[DailyUsage]


# =============================================================================
# DASHBOARD SCHEMAS
# =============================================================================

class DocumentStats(BaseModel):
    """Document statistics."""
    total: int
    ready: int


class JobStats(BaseModel):
    """Job statistics."""
    total: int
    running: int


class ConversationStats(BaseModel):
    """Conversation statistics."""
    total: int


class MessageStats(BaseModel):
    """Message statistics."""
    total: int


class Usage24h(BaseModel):
    """Usage in last 24 hours."""
    tokens: int
    cost_usd: float


class DashboardStatsResponse(BaseModel):
    """Dashboard statistics response."""
    documents: DocumentStats
    jobs: JobStats
    conversations: ConversationStats
    messages: MessageStats
    usage_24h: Usage24h


class ActivityItem(BaseModel):
    """Recent activity item."""
    type: str
    id: str
    action: str
    status: Optional[str] = None
    created_at: str


class RecentActivityResponse(BaseModel):
    """Recent activity response."""
    activities: List[ActivityItem]


# =============================================================================
# COST SCHEMAS
# =============================================================================

class CostBreakdownResponse(BaseModel):
    """Cost breakdown response."""
    total_cost_usd: float
    by_provider: List[ProviderUsage]
    period: UsagePeriod

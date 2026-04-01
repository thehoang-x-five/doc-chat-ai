"""
Dashboard API - Performance monitoring and visualization endpoints.

Provides REST API endpoints for:
- Pattern performance dashboards
- System overview dashboards
- Pattern comparison dashboards
- Dashboard data export (JSON, HTML)

Author: AI Engineering Team
Date: January 26, 2026
"""
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

# Dashboard and monitoring modules - migrated from raganything
from app.services.rag_patterns.monitoring import get_dashboard_generator, get_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# Request/Response Models

class DashboardRequest(BaseModel):
    """Request for dashboard generation."""
    
    time_range_hours: float = Field(
        default=1.0,
        description="Time range in hours for metrics",
        ge=0.1,
        le=168.0,  # Max 1 week
    )


class PatternDashboardRequest(DashboardRequest):
    """Request for pattern-specific dashboard."""
    
    pattern_name: str = Field(description="Pattern name")


class ComparisonDashboardRequest(DashboardRequest):
    """Request for pattern comparison dashboard."""
    
    pattern_names: List[str] = Field(
        description="List of patterns to compare",
        min_items=2,
    )


class ChartDataResponse(BaseModel):
    """Chart data response."""
    
    chart_type: str
    title: str
    labels: List[str]
    datasets: List[Dict[str, Any]]
    options: Dict[str, Any]


class AlertResponse(BaseModel):
    """Alert response."""
    
    timestamp: str
    severity: str
    pattern_name: str
    metric_type: str
    message: str
    current_value: float
    threshold: float


class DashboardResponse(BaseModel):
    """Dashboard response."""
    
    title: str
    timestamp: str
    charts: List[ChartDataResponse]
    summary: Dict[str, Any]
    alerts: List[AlertResponse]
    metadata: Dict[str, Any]


# API Endpoints

@router.get("/patterns/{pattern_name}", response_model=DashboardResponse)
async def get_pattern_dashboard(
    pattern_name: str,
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Get performance dashboard for a specific pattern.
    
    Args:
        pattern_name: Pattern to visualize
        time_range_hours: Time range for metrics (default: 1 hour)
        
    Returns:
        Dashboard with charts and metrics
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_pattern_dashboard(pattern_name, time_range)
        
        # Convert to response model
        return DashboardResponse(
            title=dashboard.title,
            timestamp=dashboard.timestamp.isoformat(),
            charts=[
                ChartDataResponse(
                    chart_type=chart.chart_type,
                    title=chart.title,
                    labels=chart.labels,
                    datasets=chart.datasets,
                    options=chart.options,
                )
                for chart in dashboard.charts
            ],
            summary=dashboard.summary,
            alerts=[
                AlertResponse(
                    timestamp=alert.timestamp.isoformat(),
                    severity=alert.severity.value,
                    pattern_name=alert.pattern_name,
                    metric_type=alert.metric_type.value,
                    message=alert.message,
                    current_value=alert.current_value,
                    threshold=alert.threshold,
                )
                for alert in dashboard.alerts
            ],
            metadata=dashboard.metadata,
        )
    except Exception as e:
        logger.error(f"Error generating pattern dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/system", response_model=DashboardResponse)
async def get_system_dashboard(
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Get system-wide performance dashboard.
    
    Args:
        time_range_hours: Time range for metrics (default: 1 hour)
        
    Returns:
        System dashboard with charts and metrics
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_system_overview(time_range)
        
        # Convert to response model
        return DashboardResponse(
            title=dashboard.title,
            timestamp=dashboard.timestamp.isoformat(),
            charts=[
                ChartDataResponse(
                    chart_type=chart.chart_type,
                    title=chart.title,
                    labels=chart.labels,
                    datasets=chart.datasets,
                    options=chart.options,
                )
                for chart in dashboard.charts
            ],
            summary=dashboard.summary,
            alerts=[
                AlertResponse(
                    timestamp=alert.timestamp.isoformat(),
                    severity=alert.severity.value,
                    pattern_name=alert.pattern_name,
                    metric_type=alert.metric_type.value,
                    message=alert.message,
                    current_value=alert.current_value,
                    threshold=alert.threshold,
                )
                for alert in dashboard.alerts
            ],
            metadata=dashboard.metadata,
        )
    except Exception as e:
        logger.error(f"Error generating system dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=DashboardResponse)
async def get_comparison_dashboard(request: ComparisonDashboardRequest):
    """
    Get comparison dashboard for multiple patterns.
    
    Args:
        request: Comparison request with pattern names and time range
        
    Returns:
        Comparison dashboard with charts
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=request.time_range_hours)
        
        dashboard = generator.generate_comparison_dashboard(
            request.pattern_names, time_range
        )
        
        # Convert to response model
        return DashboardResponse(
            title=dashboard.title,
            timestamp=dashboard.timestamp.isoformat(),
            charts=[
                ChartDataResponse(
                    chart_type=chart.chart_type,
                    title=chart.title,
                    labels=chart.labels,
                    datasets=chart.datasets,
                    options=chart.options,
                )
                for chart in dashboard.charts
            ],
            summary=dashboard.summary,
            alerts=[],  # No alerts for comparison
            metadata=dashboard.metadata,
        )
    except Exception as e:
        logger.error(f"Error generating comparison dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/patterns/{pattern_name}/export/json")
async def export_pattern_dashboard_json(
    pattern_name: str,
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Export pattern dashboard as JSON.
    
    Args:
        pattern_name: Pattern to export
        time_range_hours: Time range for metrics
        
    Returns:
        JSON file download
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_pattern_dashboard(pattern_name, time_range)
        json_data = generator.export_to_json(dashboard)
        
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={pattern_name}_dashboard.json"
            },
        )
    except Exception as e:
        logger.error(f"Error exporting pattern dashboard to JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns/{pattern_name}/export/html")
async def export_pattern_dashboard_html(
    pattern_name: str,
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Export pattern dashboard as HTML.
    
    Args:
        pattern_name: Pattern to export
        time_range_hours: Time range for metrics
        
    Returns:
        HTML file download
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_pattern_dashboard(pattern_name, time_range)
        html_data = generator.export_to_html(dashboard)
        
        return Response(
            content=html_data,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={pattern_name}_dashboard.html"
            },
        )
    except Exception as e:
        logger.error(f"Error exporting pattern dashboard to HTML: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/export/json")
async def export_system_dashboard_json(
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Export system dashboard as JSON.
    
    Args:
        time_range_hours: Time range for metrics
        
    Returns:
        JSON file download
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_system_overview(time_range)
        json_data = generator.export_to_json(dashboard)
        
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=system_dashboard.json"
            },
        )
    except Exception as e:
        logger.error(f"Error exporting system dashboard to JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/export/html")
async def export_system_dashboard_html(
    time_range_hours: float = Query(
        default=1.0,
        description="Time range in hours",
        ge=0.1,
        le=168.0,
    ),
):
    """
    Export system dashboard as HTML.
    
    Args:
        time_range_hours: Time range for metrics
        
    Returns:
        HTML file download
    """
    try:
        generator = get_dashboard_generator()
        time_range = timedelta(hours=time_range_hours)
        
        dashboard = generator.generate_system_overview(time_range)
        html_data = generator.export_to_html(dashboard)
        
        return Response(
            content=html_data,
            media_type="text/html",
            headers={
                "Content-Disposition": "attachment; filename=system_dashboard.html"
            },
        )
    except Exception as e:
        logger.error(f"Error exporting system dashboard to HTML: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health_summary():
    """
    Get health summary for all patterns.
    
    Returns:
        Health summary with system and pattern-level metrics
    """
    try:
        monitor = get_monitor()
        summary = monitor.get_health_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
async def list_patterns():
    """
    List all monitored patterns.
    
    Returns:
        List of pattern names with basic metrics
    """
    try:
        monitor = get_monitor()
        patterns = list(monitor._metrics.keys())
        
        pattern_info = []
        for pattern_name in patterns:
            snapshot = monitor.get_snapshot(pattern_name)
            pattern_info.append({
                "name": pattern_name,
                "total_queries": snapshot.total_queries,
                "avg_latency_ms": round(snapshot.avg_latency_ms, 2),
                "avg_accuracy": round(snapshot.avg_accuracy, 3),
                "error_rate": round(snapshot.error_rate * 100, 2),
            })
        
        return {"patterns": pattern_info}
    except Exception as e:
        logger.error(f"Error listing patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
Monitoring Module for RAG Patterns.

Provides monitoring, metrics collection, and dashboard generation capabilities.
This is a minimal implementation to support the dashboard API endpoints.

Future enhancements:
- Full metrics collection
- Alert management
- Dashboard generation with charts
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class MetricType(Enum):
    LATENCY = "latency"
    ACCURACY = "accuracy"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class MetricSnapshot:
    """Snapshot of metrics for a pattern."""
    pattern_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    total_queries: int = 0
    avg_latency_ms: float = 0.0
    avg_accuracy: float = 0.0
    error_rate: float = 0.0
    throughput_qps: float = 0.0


@dataclass
class Alert:
    """Alert for pattern metrics."""
    timestamp: datetime
    severity: AlertSeverity
    pattern_name: str
    metric_type: MetricType
    message: str
    current_value: float
    threshold: float


@dataclass
class ChartData:
    """Chart data for dashboard."""
    chart_type: str
    title: str
    labels: list[str]
    datasets: list[dict[str, Any]]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Dashboard:
    """Dashboard with charts and metrics."""
    title: str
    timestamp: datetime
    charts: list[ChartData]
    summary: dict[str, Any]
    alerts: list[Alert]
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Pattern Monitor (Singleton)
# =============================================================================

class PatternMonitor:
    """Monitors pattern performance and collects metrics."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._metrics: dict[str, list[MetricSnapshot]] = {}
        self._alerts: list[Alert] = []
        self._initialized = True
        logger.info("PatternMonitor initialized")
    
    def record_query(
        self,
        pattern_name: str,
        latency_ms: float,
        accuracy: float = 1.0,
        success: bool = True,
    ) -> None:
        """Record a query execution."""
        if pattern_name not in self._metrics:
            self._metrics[pattern_name] = []
        
        # Create snapshot (simplified - would aggregate in production)
        snapshot = MetricSnapshot(
            pattern_name=pattern_name,
            total_queries=1,
            avg_latency_ms=latency_ms,
            avg_accuracy=accuracy,
            error_rate=0.0 if success else 1.0,
        )
        self._metrics[pattern_name].append(snapshot)
    
    def get_snapshot(self, pattern_name: str) -> MetricSnapshot:
        """Get aggregated snapshot for a pattern."""
        if pattern_name not in self._metrics or not self._metrics[pattern_name]:
            return MetricSnapshot(pattern_name=pattern_name)
        
        snapshots = self._metrics[pattern_name]
        total = len(snapshots)
        
        return MetricSnapshot(
            pattern_name=pattern_name,
            total_queries=total,
            avg_latency_ms=sum(s.avg_latency_ms for s in snapshots) / total,
            avg_accuracy=sum(s.avg_accuracy for s in snapshots) / total,
            error_rate=sum(s.error_rate for s in snapshots) / total,
        )
    
    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all patterns."""
        patterns = {}
        for name in self._metrics:
            snapshot = self.get_snapshot(name)
            patterns[name] = {
                "status": "healthy" if snapshot.error_rate < 0.1 else "degraded",
                "total_queries": snapshot.total_queries,
                "avg_latency_ms": round(snapshot.avg_latency_ms, 2),
                "error_rate": round(snapshot.error_rate * 100, 2),
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "patterns": patterns,
        }
    
    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
        self._alerts.clear()


# =============================================================================
# Dashboard Generator
# =============================================================================

class DashboardGenerator:
    """Generates dashboards from metrics."""
    
    def __init__(self, monitor: PatternMonitor):
        self.monitor = monitor
    
    def generate_pattern_dashboard(
        self,
        pattern_name: str,
        time_range: timedelta = timedelta(hours=1),
    ) -> Dashboard:
        """Generate dashboard for a specific pattern."""
        snapshot = self.monitor.get_snapshot(pattern_name)
        
        return Dashboard(
            title=f"{pattern_name} Dashboard",
            timestamp=datetime.now(),
            charts=[
                ChartData(
                    chart_type="line",
                    title="Latency Over Time",
                    labels=["Now"],
                    datasets=[{"label": "Latency (ms)", "data": [snapshot.avg_latency_ms]}],
                ),
                ChartData(
                    chart_type="bar",
                    title="Accuracy",
                    labels=["Accuracy"],
                    datasets=[{"label": "Score", "data": [snapshot.avg_accuracy]}],
                ),
            ],
            summary={
                "total_queries": snapshot.total_queries,
                "avg_latency_ms": round(snapshot.avg_latency_ms, 2),
                "avg_accuracy": round(snapshot.avg_accuracy, 3),
                "error_rate": round(snapshot.error_rate * 100, 2),
            },
            alerts=[],
            metadata={"pattern": pattern_name, "time_range_hours": time_range.total_seconds() / 3600},
        )
    
    def generate_system_overview(self, time_range: timedelta = timedelta(hours=1)) -> Dashboard:
        """Generate system-wide dashboard."""
        patterns = list(self.monitor._metrics.keys())
        
        return Dashboard(
            title="System Overview",
            timestamp=datetime.now(),
            charts=[
                ChartData(
                    chart_type="pie",
                    title="Queries by Pattern",
                    labels=patterns or ["No data"],
                    datasets=[{
                        "data": [self.monitor.get_snapshot(p).total_queries for p in patterns] or [0]
                    }],
                ),
            ],
            summary=self.monitor.get_health_summary(),
            alerts=[],
            metadata={"patterns_monitored": len(patterns)},
        )
    
    def generate_comparison_dashboard(
        self,
        pattern_names: list[str],
        time_range: timedelta = timedelta(hours=1),
    ) -> Dashboard:
        """Generate comparison dashboard."""
        data = []
        for name in pattern_names:
            snapshot = self.monitor.get_snapshot(name)
            data.append({
                "pattern": name,
                "latency": snapshot.avg_latency_ms,
                "accuracy": snapshot.avg_accuracy,
            })
        
        return Dashboard(
            title="Pattern Comparison",
            timestamp=datetime.now(),
            charts=[
                ChartData(
                    chart_type="bar",
                    title="Latency Comparison",
                    labels=pattern_names,
                    datasets=[{"label": "Latency (ms)", "data": [d["latency"] for d in data]}],
                ),
                ChartData(
                    chart_type="bar",
                    title="Accuracy Comparison",
                    labels=pattern_names,
                    datasets=[{"label": "Accuracy", "data": [d["accuracy"] for d in data]}],
                ),
            ],
            summary={"patterns_compared": len(pattern_names)},
            alerts=[],
            metadata={"comparison_type": "side_by_side"},
        )
    
    def export_to_json(self, dashboard: Dashboard) -> str:
        """Export dashboard to JSON."""
        import json
        return json.dumps({
            "title": dashboard.title,
            "timestamp": dashboard.timestamp.isoformat(),
            "summary": dashboard.summary,
            "charts": [
                {"type": c.chart_type, "title": c.title, "labels": c.labels, "datasets": c.datasets}
                for c in dashboard.charts
            ],
        }, indent=2)
    
    def export_to_html(self, dashboard: Dashboard) -> str:
        """Export dashboard to simple HTML."""
        html = f"""<!DOCTYPE html>
<html><head><title>{dashboard.title}</title></head>
<body>
<h1>{dashboard.title}</h1>
<p>Generated: {dashboard.timestamp.isoformat()}</p>
<h2>Summary</h2>
<pre>{dashboard.summary}</pre>
</body></html>"""
        return html


# =============================================================================
# Singleton Accessors
# =============================================================================

_monitor: PatternMonitor | None = None
_dashboard_generator: DashboardGenerator | None = None


def get_monitor() -> PatternMonitor:
    """Get singleton PatternMonitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PatternMonitor()
    return _monitor


def get_dashboard_generator() -> DashboardGenerator:
    """Get singleton DashboardGenerator instance."""
    global _dashboard_generator
    if _dashboard_generator is None:
        _dashboard_generator = DashboardGenerator(get_monitor())
    return _dashboard_generator

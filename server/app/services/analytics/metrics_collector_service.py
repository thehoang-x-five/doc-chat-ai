"""
Metrics Collector Service - Performance metrics collection and aggregation.

This module provides:
1. Pattern execution metrics recording
2. Aggregation with percentile calculations
3. Anomaly detection for performance degradation
4. Historical trend analysis

"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import heapq

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics tracked."""
    LATENCY = "latency"
    CONFIDENCE = "confidence"
    COST = "cost"
    SUCCESS_RATE = "success_rate"
    TOKEN_USAGE = "token_usage"


@dataclass
class ExecutionMetric:
    """Single execution metric record."""
    pattern_name: str
    query_type: str
    timestamp: datetime
    latency_ms: float
    confidence: float
    success: bool
    cost: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternMetrics:
    """Aggregated metrics for a pattern."""
    pattern_name: str
    query_type: str
    sample_size: int
    
    # Latency metrics
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    
    # Quality metrics
    avg_confidence: float
    success_rate: float
    
    # Cost metrics
    avg_cost: float
    total_cost: float
    
    # Time window
    time_window_start: datetime
    time_window_end: datetime
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "query_type": self.query_type,
            "sample_size": self.sample_size,
            "latency": {
                "avg": self.avg_latency_ms,
                "p50": self.p50_latency_ms,
                "p95": self.p95_latency_ms,
                "p99": self.p99_latency_ms,
                "min": self.min_latency_ms,
                "max": self.max_latency_ms,
            },
            "avg_confidence": self.avg_confidence,
            "success_rate": self.success_rate,
            "cost": {
                "avg": self.avg_cost,
                "total": self.total_cost,
            },
            "time_window": {
                "start": self.time_window_start.isoformat(),
                "end": self.time_window_end.isoformat(),
            },
        }


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    metric_type: MetricType
    current_value: float
    baseline_value: float
    deviation_percent: float
    severity: str  # "low", "medium", "high"
    message: str


class MetricsCollector:
    """
    Metrics Collector for pattern performance tracking.
    
    Collects execution metrics, aggregates them over time windows,
    and provides anomaly detection for performance degradation.
    
    Usage:
        collector = MetricsCollector()
        
        # Record execution
        collector.record_execution(
            pattern_name="adaptive_rag",
            query_type="factual",
            latency_ms=1500,
            confidence=0.85,
            success=True,
            cost=0.002,
        )
        
        # Get aggregated metrics
        metrics = collector.get_metrics("adaptive_rag", "factual")
        
        # Check for anomalies
        is_anomaly = collector.detect_anomaly("adaptive_rag", current_latency_ms=5000)
    """
    
    # Default anomaly thresholds
    ANOMALY_THRESHOLD_PERCENT = 20  # 20% degradation
    HIGH_SEVERITY_THRESHOLD = 50  # 50% degradation
    
    def __init__(
        self,
        max_samples_per_pattern: int = 10000,
        default_window_hours: int = 24,
        persistence_fn: Optional[Any] = None,
    ):
        """
        Initialize Metrics Collector.
        
        Args:
            max_samples_per_pattern: Maximum samples to keep per pattern
            default_window_hours: Default time window for aggregation
            persistence_fn: Optional function to persist metrics to database
        """
        self.max_samples = max_samples_per_pattern
        self.default_window_hours = default_window_hours
        self.persistence_fn = persistence_fn
        
        # In-memory storage: {(pattern_name, query_type): [ExecutionMetric]}
        self._metrics: Dict[Tuple[str, str], List[ExecutionMetric]] = defaultdict(list)
        
        # Cached aggregations
        self._cached_aggregations: Dict[Tuple[str, str], PatternMetrics] = {}
        self._cache_ttl_seconds = 60
        self._cache_timestamps: Dict[Tuple[str, str], datetime] = {}
        
        logger.info(f"MetricsCollector initialized (max_samples={max_samples_per_pattern})")
    
    def record_execution(
        self,
        pattern_name: str,
        query_type: str,
        latency_ms: float,
        confidence: float,
        success: bool,
        cost: float = 0.0,
        tokens_used: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a pattern execution metric.
        
        Args:
            pattern_name: Name of the pattern executed
            query_type: Type of query (factual, analytical, etc.)
            latency_ms: Execution latency in milliseconds
            confidence: Confidence score (0-1)
            success: Whether execution was successful
            cost: Cost in dollars
            tokens_used: Number of tokens used
            metadata: Additional metadata
        """
        metric = ExecutionMetric(
            pattern_name=pattern_name,
            query_type=query_type,
            timestamp=datetime.utcnow(),
            latency_ms=latency_ms,
            confidence=confidence,
            success=success,
            cost=cost,
            tokens_used=tokens_used,
            metadata=metadata or {},
        )
        
        key = (pattern_name, query_type)
        self._metrics[key].append(metric)
        
        # Trim if exceeds max samples
        if len(self._metrics[key]) > self.max_samples:
            self._metrics[key] = self._metrics[key][-self.max_samples:]
        
        # Invalidate cache
        if key in self._cached_aggregations:
            del self._cached_aggregations[key]
        
        # Persist if configured
        if self.persistence_fn:
            try:
                self.persistence_fn(metric)
            except Exception as e:
                logger.warning(f"Failed to persist metric: {e}")
    
    def get_metrics(
        self,
        pattern_name: str,
        query_type: str,
        time_window_hours: Optional[int] = None,
    ) -> Optional[PatternMetrics]:
        """
        Get aggregated metrics for a pattern.
        
        Args:
            pattern_name: Pattern to get metrics for
            query_type: Query type
            time_window_hours: Time window for aggregation
            
        Returns:
            PatternMetrics or None if no data
        """
        key = (pattern_name, query_type)
        window_hours = time_window_hours or self.default_window_hours
        
        # Check cache
        if key in self._cached_aggregations:
            cache_time = self._cache_timestamps.get(key)
            if cache_time and (datetime.utcnow() - cache_time).seconds < self._cache_ttl_seconds:
                return self._cached_aggregations[key]
        
        # Get recent metrics
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent = [m for m in self._metrics.get(key, []) if m.timestamp >= cutoff]
        
        if not recent:
            return None
        
        # Calculate aggregations
        latencies = [m.latency_ms for m in recent]
        confidences = [m.confidence for m in recent]
        successes = [m.success for m in recent]
        costs = [m.cost for m in recent]
        
        metrics = PatternMetrics(
            pattern_name=pattern_name,
            query_type=query_type,
            sample_size=len(recent),
            avg_latency_ms=mean(latencies),
            p50_latency_ms=self._percentile(latencies, 50),
            p95_latency_ms=self._percentile(latencies, 95),
            p99_latency_ms=self._percentile(latencies, 99),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            avg_confidence=mean(confidences),
            success_rate=sum(1 for s in successes if s) / len(successes),
            avg_cost=mean(costs) if costs else 0.0,
            total_cost=sum(costs),
            time_window_start=cutoff,
            time_window_end=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        
        # Cache
        self._cached_aggregations[key] = metrics
        self._cache_timestamps[key] = datetime.utcnow()
        
        return metrics
    
    def detect_anomaly(
        self,
        pattern_name: str,
        current_latency_ms: Optional[float] = None,
        current_confidence: Optional[float] = None,
        query_type: str = "all",
    ) -> Optional[AnomalyResult]:
        """
        Detect performance anomalies.
        
        Args:
            pattern_name: Pattern to check
            current_latency_ms: Current latency to compare
            current_confidence: Current confidence to compare
            query_type: Query type
            
        Returns:
            AnomalyResult if anomaly detected, None otherwise
        """
        metrics = self.get_metrics(pattern_name, query_type)
        
        if not metrics or metrics.sample_size < 10:
            return None  # Not enough data
        
        # Check latency anomaly
        if current_latency_ms is not None:
            baseline = metrics.p95_latency_ms
            deviation = ((current_latency_ms - baseline) / baseline) * 100
            
            if deviation > self.ANOMALY_THRESHOLD_PERCENT:
                severity = "high" if deviation > self.HIGH_SEVERITY_THRESHOLD else "medium" if deviation > 35 else "low"
                return AnomalyResult(
                    is_anomaly=True,
                    metric_type=MetricType.LATENCY,
                    current_value=current_latency_ms,
                    baseline_value=baseline,
                    deviation_percent=deviation,
                    severity=severity,
                    message=f"Latency {deviation:.1f}% above p95 baseline ({baseline:.0f}ms)",
                )
        
        # Check confidence anomaly
        if current_confidence is not None:
            baseline = metrics.avg_confidence
            deviation = ((baseline - current_confidence) / baseline) * 100  # Lower is worse
            
            if deviation > self.ANOMALY_THRESHOLD_PERCENT:
                severity = "high" if deviation > self.HIGH_SEVERITY_THRESHOLD else "medium" if deviation > 35 else "low"
                return AnomalyResult(
                    is_anomaly=True,
                    metric_type=MetricType.CONFIDENCE,
                    current_value=current_confidence,
                    baseline_value=baseline,
                    deviation_percent=deviation,
                    severity=severity,
                    message=f"Confidence {deviation:.1f}% below baseline ({baseline:.2f})",
                )
        
        return None
    
    def get_all_patterns(self) -> List[Tuple[str, str]]:
        """Get all tracked pattern/query_type combinations."""
        return list(self._metrics.keys())
    
    def get_trend(
        self,
        pattern_name: str,
        query_type: str,
        metric_type: MetricType,
        num_periods: int = 7,
        period_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Get trend data for a metric.
        
        Args:
            pattern_name: Pattern name
            query_type: Query type
            metric_type: Which metric to trend
            num_periods: Number of periods to return
            period_hours: Hours per period
            
        Returns:
            List of period data points
        """
        key = (pattern_name, query_type)
        all_metrics = self._metrics.get(key, [])
        
        if not all_metrics:
            return []
        
        trend = []
        now = datetime.utcnow()
        
        for i in range(num_periods):
            period_end = now - timedelta(hours=i * period_hours)
            period_start = period_end - timedelta(hours=period_hours)
            
            period_metrics = [m for m in all_metrics if period_start <= m.timestamp < period_end]
            
            if not period_metrics:
                continue
            
            if metric_type == MetricType.LATENCY:
                value = mean([m.latency_ms for m in period_metrics])
            elif metric_type == MetricType.CONFIDENCE:
                value = mean([m.confidence for m in period_metrics])
            elif metric_type == MetricType.SUCCESS_RATE:
                value = sum(1 for m in period_metrics if m.success) / len(period_metrics)
            elif metric_type == MetricType.COST:
                value = sum(m.cost for m in period_metrics)
            else:
                value = 0
            
            trend.append({
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "value": value,
                "sample_size": len(period_metrics),
            })
        
        return list(reversed(trend))
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (len(sorted_data) - 1) * percentile / 100
        
        lower = int(index)
        upper = lower + 1
        
        if upper >= len(sorted_data):
            return sorted_data[-1]
        
        # Linear interpolation
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


# Default instance
metrics_collector = MetricsCollector()

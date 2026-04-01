"""
Trace Collector - Structured observability for RAG orchestration.

This module provides:
1. Span-based tracing for orchestration flows
2. Structured logging with context propagation
3. Integration with OpenTelemetry, LangSmith, and LangFuse
4. Performance metrics collection per component

Traces are organized hierarchically:
- Trace: Complete request lifecycle
  - Span: Individual component execution (QueryAnalyzer, Router, Pattern, etc.)
    - Events: Actions within a span (log entries, checkpoints)

"""
import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class SpanKind(Enum):
    """Type of span in the trace."""
    ROOT = "root"  # Root span for the entire request
    QUERY_ANALYSIS = "query_analysis"  # Query analyzer span
    ROUTING = "routing"  # Router decision span
    WORKFLOW_PLANNING = "workflow_planning"  # Workflow planner span
    PATTERN_EXECUTION = "pattern_execution"  # Pattern execution span
    RETRIEVAL = "retrieval"  # Retrieval operation span
    GENERATION = "generation"  # LLM generation span
    VALIDATION = "validation"  # Result validation span
    POST_PROCESSING = "post_processing"  # Post-processing span


class SpanStatus(Enum):
    """Status of a span."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """Event within a span (log entry, checkpoint)."""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """
    Individual span representing a component execution.
    
    Attributes:
        span_id: Unique identifier for this span
        trace_id: Parent trace identifier
        parent_span_id: Parent span for nested spans
        kind: Type of span
        name: Human-readable name
        start_time: When span started
        end_time: When span ended (None if still running)
        status: Final status of span
        attributes: Key-value attributes
        events: List of events within span
        latency_ms: Total latency in milliseconds
    """
    span_id: str
    trace_id: str
    kind: SpanKind
    name: str
    start_time: datetime
    parent_span_id: Optional[str] = None
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class Trace:
    """
    Complete trace for a request.
    
    Attributes:
        trace_id: Unique identifier for this trace
        root_span: Root span for the request
        spans: All spans in the trace
        start_time: When trace started
        end_time: When trace ended
        metadata: Additional trace metadata
    """
    trace_id: str
    start_time: datetime
    root_span: Optional[Span] = None
    spans: List[Span] = field(default_factory=list)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_span(self, span: Span) -> None:
        """Add a span to this trace."""
        self.spans.append(span)
        if span.kind == SpanKind.ROOT:
            self.root_span = span
    
    def get_total_latency_ms(self) -> float:
        """Get total trace latency in milliseconds."""
        if self.root_span:
            return self.root_span.latency_ms
        return sum(s.latency_ms for s in self.spans)
    
    def get_spans_by_kind(self, kind: SpanKind) -> List[Span]:
        """Get all spans of a specific kind."""
        return [s for s in self.spans if s.kind == kind]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_latency_ms": self.get_total_latency_ms(),
            "metadata": self.metadata,
            "spans": [
                {
                    "span_id": s.span_id,
                    "kind": s.kind.value,
                    "name": s.name,
                    "parent_span_id": s.parent_span_id,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "status": s.status.value,
                    "latency_ms": s.latency_ms,
                    "attributes": s.attributes,
                    "error_message": s.error_message,
                    "events": [
                        {
                            "name": e.name,
                            "timestamp": e.timestamp.isoformat(),
                            "attributes": e.attributes,
                        }
                        for e in s.events
                    ],
                }
                for s in self.spans
            ],
        }


class TraceCollector:
    """
    Trace Collector for structured observability.
    
    Collects and manages traces for RAG orchestration flows.
    Supports integration with external observability platforms.
    
    Usage:
        collector = TraceCollector()
        
        async with collector.start_trace("my-query") as trace:
            with collector.start_span(trace, SpanKind.QUERY_ANALYSIS, "Analyze Query"):
                # Do query analysis
                pass
    """
    
    def __init__(
        self,
        enabled: bool = True,
        export_fn: Optional[Callable[[Trace], None]] = None,
        max_traces: int = 1000,
    ):
        """
        Initialize the Trace Collector.
        
        Args:
            enabled: Whether tracing is enabled
            export_fn: Optional function to export completed traces
            max_traces: Maximum number of traces to keep in memory
        """
        self.enabled = enabled
        self.export_fn = export_fn
        self.max_traces = max_traces
        
        # Active traces being collected
        self._active_traces: Dict[str, Trace] = {}
        
        # Completed traces (ring buffer)
        self._completed_traces: List[Trace] = []
        
        # Current trace context (for nested spans)
        self._current_trace_id: Optional[str] = None
        self._current_span_stack: List[str] = []
        
        logger.info(f"TraceCollector initialized (enabled={enabled})")
    
    def _generate_id(self) -> str:
        """Generate a unique ID for trace or span."""
        return str(uuid.uuid4())
    
    @asynccontextmanager
    async def start_trace(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Start a new trace as an async context manager.
        
        Args:
            name: Human-readable name for the trace
            metadata: Optional metadata to attach
            
        Yields:
            Trace: The active trace object
        """
        if not self.enabled:
            yield None
            return
        
        trace_id = self._generate_id()
        trace = Trace(
            trace_id=trace_id,
            start_time=datetime.utcnow(),
            metadata=metadata or {"name": name},
        )
        
        self._active_traces[trace_id] = trace
        self._current_trace_id = trace_id
        
        try:
            logger.debug(f"Started trace {trace_id}: {name}")
            yield trace
        finally:
            # Complete the trace
            trace.end_time = datetime.utcnow()
            
            # Export if configured
            if self.export_fn:
                try:
                    self.export_fn(trace)
                except Exception as e:
                    logger.error(f"Failed to export trace {trace_id}: {e}")
            
            # Move to completed traces
            del self._active_traces[trace_id]
            self._add_completed_trace(trace)
            
            # Clear current context
            self._current_trace_id = None
            self._current_span_stack.clear()
            
            logger.debug(f"Completed trace {trace_id}")
    
    @contextmanager
    def start_span(
        self,
        trace: Optional[Trace],
        kind: SpanKind,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Start a new span within a trace.
        
        Args:
            trace: Parent trace (from start_trace)
            kind: Type of span
            name: Human-readable name
            attributes: Optional attributes
            
        Yields:
            Span: The active span object
        """
        if not self.enabled or trace is None:
            yield None
            return
        
        span_id = self._generate_id()
        parent_span_id = self._current_span_stack[-1] if self._current_span_stack else None
        
        span = Span(
            span_id=span_id,
            trace_id=trace.trace_id,
            kind=kind,
            name=name,
            start_time=datetime.utcnow(),
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        
        trace.add_span(span)
        self._current_span_stack.append(span_id)
        
        try:
            logger.debug(f"Started span {span_id}: {name}")
            yield span
        except Exception as e:
            span.status = SpanStatus.ERROR
            span.error_message = str(e)
            raise
        finally:
            # Complete the span
            span.end_time = datetime.utcnow()
            span.latency_ms = (span.end_time - span.start_time).total_seconds() * 1000
            
            if span.status == SpanStatus.UNSET:
                span.status = SpanStatus.OK
            
            # Pop from stack
            if self._current_span_stack and self._current_span_stack[-1] == span_id:
                self._current_span_stack.pop()
            
            logger.debug(f"Completed span {span_id}: {span.latency_ms:.2f}ms")
    
    def add_event(
        self,
        span: Optional[Span],
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an event to a span.
        
        Args:
            span: Parent span
            name: Event name
            attributes: Optional event attributes
        """
        if not self.enabled or span is None:
            return
        
        event = SpanEvent(
            name=name,
            timestamp=datetime.utcnow(),
            attributes=attributes or {},
        )
        span.events.append(event)
    
    def set_attribute(
        self,
        span: Optional[Span],
        key: str,
        value: Any,
    ) -> None:
        """
        Set an attribute on a span.
        
        Args:
            span: Target span
            key: Attribute key
            value: Attribute value
        """
        if not self.enabled or span is None:
            return
        
        span.attributes[key] = value
    
    def set_status(
        self,
        span: Optional[Span],
        status: SpanStatus,
        message: Optional[str] = None,
    ) -> None:
        """
        Set the status of a span.
        
        Args:
            span: Target span
            status: New status
            message: Optional status message (for errors)
        """
        if not self.enabled or span is None:
            return
        
        span.status = status
        if message:
            span.error_message = message
    
    def _add_completed_trace(self, trace: Trace) -> None:
        """Add a completed trace to the ring buffer."""
        self._completed_traces.append(trace)
        
        # Trim if exceeds max
        while len(self._completed_traces) > self.max_traces:
            self._completed_traces.pop(0)
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        # Check active traces
        if trace_id in self._active_traces:
            return self._active_traces[trace_id]
        
        # Check completed traces
        for trace in self._completed_traces:
            if trace.trace_id == trace_id:
                return trace
        
        return None
    
    def get_recent_traces(self, count: int = 10) -> List[Trace]:
        """Get the most recent completed traces."""
        return self._completed_traces[-count:]
    
    def get_traces_summary(self) -> Dict[str, Any]:
        """Get a summary of trace statistics."""
        if not self._completed_traces:
            return {
                "total_traces": 0,
                "avg_latency_ms": 0,
                "error_rate": 0,
            }
        
        total = len(self._completed_traces)
        latencies = [t.get_total_latency_ms() for t in self._completed_traces]
        errors = sum(
            1 for t in self._completed_traces
            if any(s.status == SpanStatus.ERROR for s in t.spans)
        )
        
        return {
            "total_traces": total,
            "avg_latency_ms": sum(latencies) / total if total > 0 else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "error_rate": errors / total if total > 0 else 0,
            "active_traces": len(self._active_traces),
        }
    
    def clear_traces(self) -> None:
        """Clear all completed traces."""
        self._completed_traces.clear()
        logger.info("Cleared all completed traces")


# OpenTelemetry Integration
class OpenTelemetryExporter:
    """
    Exporter for OpenTelemetry.
    
    Converts TraceCollector traces to OpenTelemetry format and exports them.
    """
    
    def __init__(
        self,
        service_name: str = "rag-orchestration",
        endpoint: str = "http://localhost:4317",
    ):
        """
        Initialize OpenTelemetry exporter.
        
        Args:
            service_name: Name of the service for tracing
            endpoint: OTLP endpoint URL
        """
        self.service_name = service_name
        self.endpoint = endpoint
        self._tracer = None
        self._initialized = False
    
    def _init_tracer(self) -> None:
        """Lazily initialize OpenTelemetry tracer."""
        if self._initialized:
            return
        
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            
            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            
            exporter = OTLPSpanExporter(endpoint=self.endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(__name__)
            self._initialized = True
            
            logger.info(f"OpenTelemetry tracer initialized for {self.service_name}")
            
        except ImportError:
            logger.warning("OpenTelemetry SDK not installed, tracing disabled")
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
    
    def export(self, trace_data: Trace) -> None:
        """
        Export a trace to OpenTelemetry.
        
        Args:
            trace_data: Trace to export
        """
        self._init_tracer()
        
        if not self._tracer:
            return
        
        try:
            # Export each span
            for span_data in trace_data.spans:
                with self._tracer.start_as_current_span(
                    span_data.name,
                    kind=self._map_span_kind(span_data.kind),
                ) as otel_span:
                    # Set attributes
                    for key, value in span_data.attributes.items():
                        otel_span.set_attribute(key, str(value))
                    
                    # Add events
                    for event in span_data.events:
                        otel_span.add_event(
                            event.name,
                            attributes=event.attributes,
                        )
                    
                    # Set status
                    if span_data.status == SpanStatus.ERROR:
                        otel_span.set_status(
                            trace.Status(
                                trace.StatusCode.ERROR,
                                span_data.error_message or "Error",
                            )
                        )
                        
        except Exception as e:
            logger.error(f"Failed to export trace to OpenTelemetry: {e}")
    
    def _map_span_kind(self, kind: SpanKind):
        """Map internal SpanKind to OpenTelemetry SpanKind."""
        try:
            from opentelemetry.trace import SpanKind as OTelSpanKind
            return OTelSpanKind.INTERNAL
        except ImportError:
            return None


# LangSmith Integration  
class LangSmithExporter:
    """
    Exporter for LangSmith.
    
    Converts TraceCollector traces to LangSmith format and exports them.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_name: str = "rag-orchestration",
    ):
        """
        Initialize LangSmith exporter.
        
        Args:
            api_key: LangSmith API key (or from env LANGSMITH_API_KEY)
            project_name: LangSmith project name
        """
        import os
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        self.project_name = project_name
        self._client = None
    
    def _init_client(self) -> None:
        """Lazily initialize LangSmith client."""
        if self._client:
            return
        
        if not self.api_key:
            logger.warning("No LangSmith API key provided, export disabled")
            return
        
        try:
            from langsmith import Client
            self._client = Client(api_key=self.api_key)
            logger.info(f"LangSmith client initialized for project {self.project_name}")
        except ImportError:
            logger.warning("LangSmith SDK not installed, export disabled")
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}")
    
    def export(self, trace_data: Trace) -> None:
        """
        Export a trace to LangSmith.
        
        Args:
            trace_data: Trace to export
        """
        self._init_client()
        
        if not self._client:
            return
        
        try:
            # Create a run for the trace
            run = self._client.create_run(
                name=trace_data.metadata.get("name", "RAG Query"),
                run_type="chain",
                project_name=self.project_name,
                inputs=trace_data.metadata,
            )
            
            # Add child runs for each span
            for span_data in trace_data.spans:
                self._client.create_run(
                    name=span_data.name,
                    run_type="chain",
                    project_name=self.project_name,
                    parent_run_id=run.id,
                    inputs=span_data.attributes,
                )
            
            logger.debug(f"Exported trace {trace_data.trace_id} to LangSmith")
            
        except Exception as e:
            logger.error(f"Failed to export trace to LangSmith: {e}")


# Default instance
trace_collector = TraceCollector()

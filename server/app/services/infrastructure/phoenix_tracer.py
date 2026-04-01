"""
Phoenix Tracer cho Distributed Tracing và Observability

Đây là implementation nhẹ cung cấp chức năng tracing mà không cần
thư viện Phoenix/Arize đầy đủ. Có thể dễ dàng nâng cấp lên Phoenix
thật khi cần thiết.

Tính năng:
- Distributed tracing với span tracking
- Tracing LLM calls với token usage và chi phí
- Tracing các thao tác retrieval
- Phát hiện bất thường (latency spikes, error rates, cost spikes)
- Hỗ trợ sampling để kiểm soát overhead
- Export sang JSON để visualize
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
import logging
import uuid
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Trace span đại diện cho một thao tác đơn lẻ."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # "ok", "error"
    error_message: Optional[str] = None
    
    def duration_ms(self) -> float:
        """Lấy thời gian thực thi span tính bằng milliseconds."""
        if self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() * 1000
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển span sang dictionary để export."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass
class Anomaly:
    """Bất thường được phát hiện trong traces."""
    type: str  # "latency_spike", "error_rate", "cost_spike"
    severity: str  # "critical", "warning"
    trace_id: str
    span_id: str
    message: str
    detected_at: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)


class PhoenixTracer:
    """
    Distributed tracer nhẹ cho AI pipeline observability.
    
    Implementation này cung cấp chức năng tracing cốt lõi mà không cần
    thư viện Phoenix/Arize đầy đủ. Có thể dễ dàng nâng cấp sau.
    
    Tính năng:
    - Tracing dựa trên span
    - Tracking LLM và retrieval operations
    - Phát hiện bất thường
    - Hỗ trợ sampling
    - Export JSON để visualize
    """
    
    def __init__(
        self,
        project_name: str,
        sampling_rate: float = 1.0,
        export_dir: Optional[str] = None,
    ):
        """
        Khởi tạo Phoenix tracer.
        
        Args:
            project_name: Tên project đang được trace
            sampling_rate: Tỷ lệ sampling (0-1), 1.0 = trace tất cả
            export_dir: Thư mục để export traces (tùy chọn)
        """
        self.project_name = project_name
        self.sampling_rate = sampling_rate
        self.export_dir = Path(export_dir) if export_dir else None
        
        # Lưu trữ
        self._traces: Dict[str, List[Span]] = {}  # trace_id -> spans
        self._current_trace_id: Optional[str] = None
        self._current_span_stack: List[Span] = []
        self._anomalies: List[Anomaly] = []
        
        # Metrics
        self._total_traces = 0
        self._total_spans = 0
        self._total_errors = 0
        
        # Ngưỡng phát hiện bất thường
        self.latency_threshold_ms = 5000  # 5 giây
        self.error_rate_threshold = 0.1  # 10%
        self.cost_threshold = 1.0  # $1 mỗi request
        
        logger.info(
            f"PhoenixTracer initialized: project={project_name}, "
            f"sampling={sampling_rate:.0%}"
        )
    
    def start_trace(self, trace_id: Optional[str] = None) -> str:
        """
        Bắt đầu một trace mới.
        
        Args:
            trace_id: Trace ID tùy chọn, sẽ tự tạo nếu không có
            
        Returns:
            Trace ID
        """
        import random
        
        # Kiểm tra sampling
        if random.random() > self.sampling_rate:
            return None  # Không được sample
        
        trace_id = trace_id or str(uuid.uuid4())
        self._current_trace_id = trace_id
        self._traces[trace_id] = []
        self._total_traces += 1
        
        logger.debug(f"Started trace: {trace_id}")
        return trace_id
    
    @contextmanager
    def trace_span(
        self,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Tạo context manager cho trace span.
        
        Args:
            span_name: Tên của span
            attributes: Attributes tùy chọn để gắn vào span
            
        Yields:
            Span object
        """
        # Kiểm tra có trace đang active không
        if self._current_trace_id is None:
            # Tự động start trace nếu chưa có
            self.start_trace()
        
        if self._current_trace_id is None:
            # Không được sample, yield dummy span
            yield None
            return
        
        # Tạo span
        span = Span(
            span_id=str(uuid.uuid4()),
            trace_id=self._current_trace_id,
            parent_span_id=self._current_span_stack[-1].span_id if self._current_span_stack else None,
            name=span_name,
            start_time=datetime.now(),
            attributes=attributes or {},
        )
        
        # Push vào stack
        self._current_span_stack.append(span)
        self._total_spans += 1
        
        try:
            yield span
            
            # Đánh dấu hoàn thành
            span.end_time = datetime.now()
            span.status = "ok"
            
            # Kiểm tra bất thường
            self._check_span_anomalies(span)
            
        except Exception as e:
            # Đánh dấu lỗi
            span.end_time = datetime.now()
            span.status = "error"
            span.error_message = str(e)
            self._total_errors += 1
            
            logger.error(f"Span error: {span_name} - {e}")
            raise
            
        finally:
            # Pop khỏi stack
            self._current_span_stack.pop()
            
            # Lưu span
            if self._current_trace_id in self._traces:
                self._traces[self._current_trace_id].append(span)
    
    def trace_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        tokens_used: int,
        latency_ms: float,
        cost: Optional[float] = None,
    ) -> None:
        """
        Trace một LLM call với metrics.
        
        Args:
            model: Tên model
            prompt: Input prompt
            response: Response từ model
            tokens_used: Tổng số tokens đã dùng
            latency_ms: Độ trễ tính bằng milliseconds
            cost: Chi phí tùy chọn tính bằng dollars
        """
        attributes = {
            "model": model,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "cost": cost,
        }
        
        with self.trace_span("llm_call", attributes) as span:
            if span:
                span.attributes.update(attributes)
                
                # Kiểm tra bất thường về chi phí
                if cost and cost > self.cost_threshold:
                    self._record_anomaly(
                        anomaly_type="cost_spike",
                        severity="warning",
                        span=span,
                        message=f"Chi phí cao: ${cost:.2f} > ${self.cost_threshold:.2f}",
                        metrics={"cost": cost, "threshold": self.cost_threshold},
                    )
    
    def trace_retrieval(
        self,
        query: str,
        results: List[Any],
        latency_ms: float,
        strategy: Optional[str] = None,
    ) -> None:
        """
        Trace một thao tác retrieval.
        
        Args:
            query: Search query
            results: Kết quả đã retrieve
            latency_ms: Độ trễ tính bằng milliseconds
            strategy: Chiến lược retrieval đã dùng (tùy chọn)
        """
        attributes = {
            "query_length": len(query),
            "results_count": len(results),
            "latency_ms": latency_ms,
            "strategy": strategy,
        }
        
        with self.trace_span("retrieval", attributes) as span:
            if span:
                span.attributes.update(attributes)
    
    def _check_span_anomalies(self, span: Span) -> None:
        """Kiểm tra span có bất thường không."""
        duration = span.duration_ms()
        
        # Kiểm tra latency spike
        if duration > self.latency_threshold_ms:
            self._record_anomaly(
                anomaly_type="latency_spike",
                severity="warning",
                span=span,
                message=f"Độ trễ cao: {duration:.0f}ms > {self.latency_threshold_ms}ms",
                metrics={"duration_ms": duration, "threshold_ms": self.latency_threshold_ms},
            )
        
        # Kiểm tra error rate
        if self._total_spans > 0:
            error_rate = self._total_errors / self._total_spans
            if error_rate > self.error_rate_threshold:
                self._record_anomaly(
                    anomaly_type="error_rate",
                    severity="critical",
                    span=span,
                    message=f"Tỷ lệ lỗi cao: {error_rate:.1%} > {self.error_rate_threshold:.1%}",
                    metrics={"error_rate": error_rate, "threshold": self.error_rate_threshold},
                )
    
    def _record_anomaly(
        self,
        anomaly_type: str,
        severity: str,
        span: Span,
        message: str,
        metrics: Dict[str, Any],
    ) -> None:
        """Ghi lại một bất thường."""
        anomaly = Anomaly(
            type=anomaly_type,
            severity=severity,
            trace_id=span.trace_id,
            span_id=span.span_id,
            message=message,
            detected_at=datetime.now(),
            metrics=metrics,
        )
        
        self._anomalies.append(anomaly)
        
        logger.warning(
            f"Phát hiện bất thường: {anomaly_type} - {message} "
            f"(trace: {span.trace_id}, span: {span.span_id})"
        )
    
    async def detect_anomalies(self) -> List[Anomaly]:
        """
        Phát hiện bất thường trong các traces gần đây.
        
        Returns:
            Danh sách các bất thường đã phát hiện
        """
        # Trả về các bất thường gần đây (100 cái cuối)
        return self._anomalies[-100:]
    
    def get_trace(self, trace_id: str) -> Optional[List[Span]]:
        """Lấy tất cả spans cho một trace."""
        return self._traces.get(trace_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê của tracer."""
        return {
            "project_name": self.project_name,
            "sampling_rate": self.sampling_rate,
            "total_traces": self._total_traces,
            "total_spans": self._total_spans,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / self._total_spans if self._total_spans > 0 else 0,
            "total_anomalies": len(self._anomalies),
            "active_traces": len([t for t in self._traces.values() if t]),
        }
    
    def export_traces(self, output_file: Optional[str] = None) -> str:
        """
        Export traces sang file JSON.
        
        Args:
            output_file: Đường dẫn file output tùy chọn
            
        Returns:
            Đường dẫn đến file đã export
        """
        if output_file is None:
            if self.export_dir:
                self.export_dir.mkdir(parents=True, exist_ok=True)
                output_file = self.export_dir / f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            else:
                output_file = f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Chuyển traces sang dict
        export_data = {
            "project_name": self.project_name,
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "traces": {
                trace_id: [span.to_dict() for span in spans]
                for trace_id, spans in self._traces.items()
            },
            "anomalies": [
                {
                    "type": a.type,
                    "severity": a.severity,
                    "trace_id": a.trace_id,
                    "span_id": a.span_id,
                    "message": a.message,
                    "detected_at": a.detected_at.isoformat(),
                    "metrics": a.metrics,
                }
                for a in self._anomalies
            ],
        }
        
        # Ghi vào file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Traces exported to: {output_file}")
        return str(output_file)
    
    def clear_traces(self) -> None:
        """Xóa tất cả traces đã lưu (để quản lý memory)."""
        self._traces.clear()
        self._anomalies.clear()
        logger.info("Traces cleared")
    
    def end_trace(self) -> None:
        """Kết thúc trace hiện tại."""
        if self._current_trace_id:
            logger.debug(f"Ended trace: {self._current_trace_id}")
            self._current_trace_id = None
            self._current_span_stack.clear()

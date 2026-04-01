"""
Comprehensive Logging Service
Service logging có cấu trúc JSON cho tất cả giai đoạn pipeline với correlation IDs.

Tính năng:
- Logging JSON có cấu trúc cho tất cả stages
- Correlation IDs để trace từng request
- Ghi nhận performance metrics
- Error logging với đầy đủ context
- Log sampling cho khối lượng lớn
- Tích hợp với hệ thống monitoring (Prometheus/Grafana)

"""

import logging
import json
import uuid
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
import traceback

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Một entry log có cấu trúc"""
    timestamp: str
    correlation_id: str
    stage: str
    level: str  # "INFO", "WARNING", "ERROR", "DEBUG"
    message: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PerformanceMetrics:
    """Metrics hiệu năng để theo dõi"""
    stage: str
    latency_ms: float
    timestamp: str
    correlation_id: str
    success: bool
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LoggingService:
    """
    Service logging toàn diện cho AI pipeline.
    
    Cung cấp:
    - Logging JSON có cấu trúc rõ ràng
    - Tracking correlation ID để trace request
    - Thu thập performance metrics
    - Error logging kèm đầy đủ context
    - Log sampling cho khối lượng lớn
    """
    
    def __init__(
        self,
        service_name: str = "rag-anything",
        enable_sampling: bool = False,
        sampling_rate: float = 0.1,
        high_volume_threshold: int = 1000,
        performance_threshold_ms: float = 5000.0
    ):
        """
        Khởi tạo logging service.
        
        Args:
            service_name: Tên service
            enable_sampling: Có bật log sampling không
            sampling_rate: Tỷ lệ sampling (0.1 = 10%)
            high_volume_threshold: Ngưỡng logs/phút để bật sampling
            performance_threshold_ms: Ngưỡng latency để alert (ms)
        """
        self.service_name = service_name
        self.enable_sampling = enable_sampling
        self.sampling_rate = sampling_rate
        self.high_volume_threshold = high_volume_threshold
        self.performance_threshold_ms = performance_threshold_ms
        
        # Tracking metrics
        self.log_count = 0
        self.log_count_window_start = time.time()
        self.performance_metrics: List[PerformanceMetrics] = []
        
        logger.info(
            f"LoggingService đã khởi tạo: service={service_name}, "
            f"sampling={enable_sampling}, rate={sampling_rate}"
        )
    
    def generate_correlation_id(self) -> str:
        """Tạo correlation ID unique để trace request."""
        return str(uuid.uuid4())
    
    def should_log(self) -> bool:
        """
        Quyết định có nên ghi log hay không dựa trên sampling.
        
        Returns:
            True nếu nên ghi log
        """
        if not self.enable_sampling:
            return True
        
        # Check xem có đang high volume không
        current_time = time.time()
        time_window = current_time - self.log_count_window_start
        
        if time_window >= 60:  # Reset window mỗi phút
            logs_per_minute = self.log_count / (time_window / 60)
            
            if logs_per_minute > self.high_volume_threshold:
                # High volume - áp dụng sampling
                import random
                return random.random() < self.sampling_rate
            
            # Reset counter
            self.log_count = 0
            self.log_count_window_start = current_time
        
        return True
    
    def log_stage(
        self,
        stage: str,
        message: str,
        correlation_id: str,
        level: str = "INFO",
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Log một lần thực thi pipeline stage.
        
        Args:
            stage: Tên stage (vd: "validation", "retrieval")
            message: Message log
            correlation_id: Correlation ID để tracing
            level: Log level
            input_data: Input data (đã sanitize)
            output_data: Output data (đã sanitize)
            latency_ms: Latency thực thi (milliseconds)
            error: Error message nếu có
            metadata: Metadata bổ sung
        """
        if not self.should_log():
            return
        
        self.log_count += 1
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            stage=stage,
            level=level,
            message=message,
            input_data=self._sanitize_data(input_data),
            output_data=self._sanitize_data(output_data),
            latency_ms=latency_ms,
            error=error,
            metadata=metadata
        )
        
        # Log dưới dạng JSON
        log_json = json.dumps(asdict(entry), default=str)
        
        if level == "ERROR":
            logger.error(log_json)
        elif level == "WARNING":
            logger.warning(log_json)
        elif level == "DEBUG":
            logger.debug(log_json)
        else:
            logger.info(log_json)
        
        # Check ngưỡng performance
        if latency_ms and latency_ms > self.performance_threshold_ms:
            self.emit_performance_alert(stage, latency_ms, correlation_id)
    
    def log_error(
        self,
        stage: str,
        error: Exception,
        correlation_id: str,
        context: Optional[Dict] = None
    ) -> None:
        """
        Log error với full context và stack trace.
        
        Args:
            stage: Stage nơi xảy ra lỗi
            error: Exception object
            correlation_id: Correlation ID để tracing
            context: Context bổ sung
        """
        stack_trace = traceback.format_exc()
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            stage=stage,
            level="ERROR",
            message=str(error),
            error=error.__class__.__name__,
            stack_trace=stack_trace,
            metadata=context
        )
        
        log_json = json.dumps(asdict(entry), default=str)
        logger.error(log_json)
    
    @contextmanager
    def trace_stage(
        self,
        stage: str,
        correlation_id: str,
        input_data: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Context manager để trace một pipeline stage.
        
        Cách dùng:
            with logging_service.trace_stage("retrieval", correlation_id):
                # Code của bạn ở đây
                pass
        
        Args:
            stage: Tên stage
            correlation_id: Correlation ID
            input_data: Input data
            metadata: Metadata bổ sung
        """
        start_time = time.time()
        error = None
        output_data = None
        
        try:
            yield
        except Exception as e:
            error = e
            self.log_error(stage, e, correlation_id, metadata)
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            
            self.log_stage(
                stage=stage,
                message=f"Stage {stage} hoàn thành" if not error else f"Stage {stage} thất bại",
                correlation_id=correlation_id,
                level="INFO" if not error else "ERROR",
                input_data=input_data,
                output_data=output_data,
                latency_ms=latency_ms,
                error=str(error) if error else None,
                metadata=metadata
            )
            
            # Track performance metrics
            self.track_performance(
                stage=stage,
                latency_ms=latency_ms,
                correlation_id=correlation_id,
                success=error is None,
                error_type=error.__class__.__name__ if error else None,
                metadata=metadata
            )
    
    def track_performance(
        self,
        stage: str,
        latency_ms: float,
        correlation_id: str,
        success: bool,
        error_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Ghi nhận performance metrics cho một stage.
        
        Args:
            stage: Tên stage
            latency_ms: Độ trễ thực thi
            correlation_id: Correlation ID
            success: Stage có thành công không
            error_type: Loại lỗi nếu thất bại
            metadata: Metadata bổ sung
        """
        metric = PerformanceMetrics(
            stage=stage,
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            success=success,
            error_type=error_type,
            metadata=metadata
        )
        
        self.performance_metrics.append(metric)
        
        # Chỉ giữ lại metrics gần đây (1000 cái cuối)
        if len(self.performance_metrics) > 1000:
            self.performance_metrics = self.performance_metrics[-1000:]
    
    def emit_performance_alert(
        self,
        stage: str,
        latency_ms: float,
        correlation_id: str
    ) -> None:
        """
        Phát cảnh báo khi hiệu năng giảm.
        
        Args:
            stage: Tên stage
            latency_ms: Độ trễ vượt ngưỡng
            correlation_id: Correlation ID
        """
        alert = {
            "alert_type": "performance_degradation",
            "stage": stage,
            "latency_ms": latency_ms,
            "threshold_ms": self.performance_threshold_ms,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            "service": self.service_name
        }
        
        logger.warning(f"PERFORMANCE_ALERT: {json.dumps(alert)}")
        
        # Trong production, gửi đến hệ thống monitoring (Prometheus/Grafana)
        # self._send_to_prometheus(alert)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Lấy tổng hợp các performance metrics.
        
        Returns:
            Dictionary chứa tổng hợp metrics
        """
        if not self.performance_metrics:
            return {
                "total_requests": 0,
                "avg_latency_ms": 0.0,
                "success_rate": 0.0,
                "stages": {}
            }
        
        total = len(self.performance_metrics)
        successful = sum(1 for m in self.performance_metrics if m.success)
        avg_latency = sum(m.latency_ms for m in self.performance_metrics) / total
        
        # Metrics theo từng stage
        stages = {}
        for metric in self.performance_metrics:
            if metric.stage not in stages:
                stages[metric.stage] = {
                    "count": 0,
                    "total_latency": 0.0,
                    "successes": 0,
                    "errors": {}
                }
            
            stages[metric.stage]["count"] += 1
            stages[metric.stage]["total_latency"] += metric.latency_ms
            if metric.success:
                stages[metric.stage]["successes"] += 1
            elif metric.error_type:
                error_count = stages[metric.stage]["errors"].get(metric.error_type, 0)
                stages[metric.stage]["errors"][metric.error_type] = error_count + 1
        
        # Tính trung bình
        for stage_name, stage_data in stages.items():
            stage_data["avg_latency_ms"] = stage_data["total_latency"] / stage_data["count"]
            stage_data["success_rate"] = stage_data["successes"] / stage_data["count"]
            del stage_data["total_latency"]
        
        return {
            "total_requests": total,
            "avg_latency_ms": avg_latency,
            "success_rate": successful / total,
            "stages": stages,
            "timestamp": datetime.now().isoformat()
        }
    
    def _sanitize_data(self, data: Optional[Dict]) -> Optional[Dict]:
        """
        Làm sạch data trước khi log (xóa PII, cắt giá trị lớn).
        
        Args:
            data: Data cần làm sạch
        
        Returns:
            Data đã được làm sạch
        """
        if data is None:
            return None
        
        sanitized = {}
        for key, value in data.items():
            # Bỏ qua các trường PII
            if key.lower() in ['password', 'token', 'api_key', 'secret']:
                sanitized[key] = "***REDACTED***"
                continue
            
            # Cắt ngắn string dài
            if isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "...[truncated]"
            elif isinstance(value, (list, dict)):
                # Cắt ngắn collection lớn
                sanitized[key] = str(value)[:500] + "...[truncated]" if len(str(value)) > 500 else value
            else:
                sanitized[key] = value
        
        return sanitized
    
    def export_metrics_prometheus(self) -> str:
        """
        Export metrics sang định dạng Prometheus.
        
        Returns:
            String metrics theo format Prometheus
        """
        summary = self.get_metrics_summary()
        
        lines = [
            f"# HELP {self.service_name}_requests_total Total number of requests",
            f"# TYPE {self.service_name}_requests_total counter",
            f"{self.service_name}_requests_total {summary['total_requests']}",
            "",
            f"# HELP {self.service_name}_latency_ms Average latency in milliseconds",
            f"# TYPE {self.service_name}_latency_ms gauge",
            f"{self.service_name}_latency_ms {summary['avg_latency_ms']:.2f}",
            "",
            f"# HELP {self.service_name}_success_rate Success rate (0-1)",
            f"# TYPE {self.service_name}_success_rate gauge",
            f"{self.service_name}_success_rate {summary['success_rate']:.4f}",
            ""
        ]
        
        # Metrics theo từng stage
        for stage_name, stage_data in summary['stages'].items():
            stage_label = stage_name.replace("-", "_")
            lines.extend([
                f"# HELP {self.service_name}_stage_latency_ms_{stage_label} Stage latency",
                f"# TYPE {self.service_name}_stage_latency_ms_{stage_label} gauge",
                f"{self.service_name}_stage_latency_ms_{stage_label} {stage_data['avg_latency_ms']:.2f}",
                ""
            ])
        
        return "\n".join(lines)


# Instance global của logging service
_logging_service: Optional[LoggingService] = None


def get_logging_service() -> LoggingService:
    """Lấy hoặc tạo instance global của logging service."""
    global _logging_service
    if _logging_service is None:
        _logging_service = LoggingService()
    return _logging_service


def set_logging_service(service: LoggingService) -> None:
    """Set instance global của logging service."""
    global _logging_service
    _logging_service = service


# Ví dụ sử dụng
if __name__ == "__main__":
    # Khởi tạo service
    service = LoggingService(
        service_name="rag-anything",
        enable_sampling=True,
        sampling_rate=0.1,
        performance_threshold_ms=5000.0
    )
    
    # Tạo correlation ID
    correlation_id = service.generate_correlation_id()
    
    # Ví dụ 1: Logging thủ công
    service.log_stage(
        stage="validation",
        message="Input validation completed",
        correlation_id=correlation_id,
        input_data={"query": "test query"},
        output_data={"is_valid": True},
        latency_ms=50.0
    )
    
    # Ví dụ 2: Dùng context manager
    with service.trace_stage("retrieval", correlation_id, input_data={"query": "test"}):
        # Giả lập công việc
        time.sleep(0.1)
    
    # Ví dụ 3: Logging lỗi
    try:
        raise ValueError("Test error")
    except Exception as e:
        service.log_error("generation", e, correlation_id, context={"query": "test"})
    
    # Lấy tổng hợp metrics
    summary = service.get_metrics_summary()
    print(json.dumps(summary, indent=2))
    
    # Export metrics Prometheus
    print("\nPrometheus Metrics:")
    print(service.export_metrics_prometheus())

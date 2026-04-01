from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging
from uuid import UUID
from datetime import datetime
import random

import pandas as pd

try:
    from datasets import Dataset
    DATASETS_AVAILABLE = True
except ImportError:
    DATASETS_AVAILABLE = False
    Dataset = None

# RAGAS imports
try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class TestCase:
    """Test case cho đánh giá RAG."""
    question: str
    generated_answer: str
    retrieved_context: List[str]
    expected_answer: Optional[str] = None
    
@dataclass
class EvaluationReport:
    """Báo cáo các chỉ số đánh giá."""
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    overall_score: float
    details: Dict[str, Any]


@dataclass
class EvaluationMetrics:
    """Các chỉ số đánh giá nâng cao với timestamp."""
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    workspace_id: Optional[str] = None


@dataclass
class Alert:
    """Cảnh báo khi chỉ số giảm sút."""
    metric_name: str
    current_value: float
    threshold: float
    severity: str  # "critical", "warning"
    message: str
    workspace_id: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TimeSeriesMetrics:
    """Các chỉ số theo thời gian cho dashboard."""
    timestamps: List[datetime]
    faithfulness_scores: List[float]
    relevancy_scores: List[float]
    precision_scores: List[float]
    recall_scores: List[float]
    workspace_id: str

class EvaluationService:
    """
    Service đánh giá chất lượng RAG pipeline sử dụng RAGAS.
    
    Các chỉ số:
    - Faithfulness: Câu trả lời có dựa trên context không?
    - Answer Relevancy: Câu trả lời có liên quan đến câu hỏi không?
    - Context Precision: Context được retrieve có liên quan không?
    
    Tính năng nâng cao:
    - Đánh giá real-time với sampling (10%)
    - Cảnh báo tự động khi chỉ số giảm sút
    - Lưu trữ time-series để phân tích xu hướng
    - Tự động trigger retraining
    """
    
    def __init__(self, sample_rate: float = 0.1):
        if not RAGAS_AVAILABLE:
            logger.warning("RAGAS not installed. EvaluationService will not work.")
        
        self.sample_rate = sample_rate
        
        # Lưu trữ metrics (trong production, dùng time-series database)
        self._metrics_history: Dict[str, List[EvaluationMetrics]] = {}
        self._alerts: List[Alert] = []
        self._degradation_count: Dict[str, int] = {}  # Theo dõi số lần giảm sút liên tiếp
        
        # Ngưỡng cảnh báo
        self.alert_thresholds = {
            "faithfulness": 0.7,
            "answer_relevancy": 0.6,
        }
        
        # Callback cho notification
        self._alert_callback: Optional[callable] = None
    
    async def evaluate_rag_quality(
        self, 
        test_cases: List[TestCase]
    ) -> EvaluationReport:
        """Đánh giá chất lượng RAG sử dụng các metrics của RAGAS."""
        
        if not RAGAS_AVAILABLE:
            raise ImportError("ragas package is required for evaluation")
            
        if not test_cases:
            return EvaluationReport(0, 0, 0, 0, {})
            
        # Chuẩn bị dữ liệu cho RAGAS
        data = {
            "question": [tc.question for tc in test_cases],
            "answer": [tc.generated_answer for tc in test_cases],
            "contexts": [tc.retrieved_context for tc in test_cases],
        }
        
        # Thêm ground truth nếu có
        if any(tc.expected_answer for tc in test_cases):
            # Thay None bằng empty string để đồng nhất
            data["ground_truth"] = [tc.expected_answer or "" for tc in test_cases]
            
        dataset = Dataset.from_dict(data)
        
        # Định nghĩa các metrics cần chạy
        metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
        ]
        
        if "ground_truth" in data:
            metrics.append(context_recall)
            
        # Chạy evaluation
        # Lưu ý: Có thể gọi API đến OpenAI/LLM provider được cấu hình trong RAGAS
        # Giả định các biến môi trường (OPENAI_API_KEY) đã được set
        results = evaluate(
            dataset=dataset,
            metrics=metrics,
        )
        
        # Trích xuất điểm số
        scores = results.to_pandas()
        avg_scores = scores.mean(numeric_only=True)
        
        return EvaluationReport(
            faithfulness=avg_scores.get('faithfulness', 0.0),
            answer_relevancy=avg_scores.get('answer_relevancy', 0.0),
            context_precision=avg_scores.get('context_precision', 0.0),
            overall_score=avg_scores.mean(),
            details=results.to_dict()
        )

    def create_test_case(
        self,
        question: str,
        answer: str,
        retrieved_chunks: List[Any], # List of RetrievalResult or Chunk
        expected: str = None
    ) -> TestCase:
        """Helper để tạo test case từ các thành phần của RAG response."""
        
        # Trích xuất text content từ chunks
        contexts = []
        for chunk in retrieved_chunks:
            if hasattr(chunk, 'content'):
                contexts.append(chunk.content)
            elif isinstance(chunk, str):
                contexts.append(chunk)
                
        return TestCase(
            question=question,
            generated_answer=answer,
            retrieved_context=contexts,
            expected_answer=expected
        )
    
    # ========== PHASE 4: REAL-TIME EVALUATION ==========
    
    async def evaluate_realtime(
        self,
        query: str,
        answer: str,
        context: List[str],
        workspace_id: str = "default",
        sample_rate: Optional[float] = None,
    ) -> Optional[EvaluationMetrics]:
        """
        Đánh giá với sampling cho real-time monitoring.
        
        Args:
            query: Câu hỏi của user
            answer: Câu trả lời được generate
            context: Context được retrieve
            workspace_id: Định danh workspace
            sample_rate: Override sample rate mặc định
            
        Returns:
            EvaluationMetrics nếu được sample, None nếu không
        """
        # Sử dụng sample rate được cung cấp hoặc mặc định
        rate = sample_rate if sample_rate is not None else self.sample_rate
        
        # Quyết định sample
        if random.random() > rate:
            # Không được sample
            return None
        
        logger.info(f"Real-time evaluation sampled for workspace {workspace_id}")
        
        try:
            # Tạo test case
            test_case = TestCase(
                question=query,
                generated_answer=answer,
                retrieved_context=context,
            )
            
            # Chạy evaluation
            report = await self.evaluate_rag_quality([test_case])
            
            # Tạo metrics
            metrics = EvaluationMetrics(
                faithfulness=report.faithfulness,
                answer_relevancy=report.answer_relevancy,
                context_precision=report.context_precision,
                context_recall=0.0,  # Không có nếu thiếu ground truth
                overall_score=report.overall_score,
                workspace_id=workspace_id,
            )
            
            # Lưu trữ metrics
            self._store_metrics(workspace_id, metrics)
            
            # Kiểm tra cảnh báo
            alerts = await self.check_and_alert(metrics, self.alert_thresholds)
            
            if alerts:
                logger.warning(
                    f"Metric degradation detected for workspace {workspace_id}: "
                    f"{len(alerts)} alerts"
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error in real-time evaluation: {e}")
            return None
    
    def _store_metrics(
        self,
        workspace_id: str,
        metrics: EvaluationMetrics,
    ) -> None:
        """Lưu trữ metrics vào time-series storage."""
        if workspace_id not in self._metrics_history:
            self._metrics_history[workspace_id] = []
        
        self._metrics_history[workspace_id].append(metrics)
        
        # Chỉ giữ 1000 records gần nhất cho mỗi workspace
        if len(self._metrics_history[workspace_id]) > 1000:
            self._metrics_history[workspace_id] = self._metrics_history[workspace_id][-1000:]
        
        logger.debug(
            f"Stored metrics for workspace {workspace_id}: "
            f"faithfulness={metrics.faithfulness:.2f}, "
            f"relevancy={metrics.answer_relevancy:.2f}"
        )
    
    async def check_and_alert(
        self,
        metrics: EvaluationMetrics,
        thresholds: Dict[str, float],
    ) -> List[Alert]:
        """
        Kiểm tra metrics và tạo cảnh báo.
        
        Args:
            metrics: EvaluationMetrics cần kiểm tra
            thresholds: Dict từ metric_name -> threshold
            
        Returns:
            List các Alert objects
        """
        alerts = []
        
        # Kiểm tra faithfulness
        if metrics.faithfulness < thresholds.get("faithfulness", 0.7):
            alert = Alert(
                metric_name="faithfulness",
                current_value=metrics.faithfulness,
                threshold=thresholds["faithfulness"],
                severity="critical",
                message=(
                    f"Faithfulness score {metrics.faithfulness:.2f} "
                    f"below threshold {thresholds['faithfulness']:.2f}"
                ),
                workspace_id=metrics.workspace_id or "default",
            )
            alerts.append(alert)
            self._alerts.append(alert)
        
        # Kiểm tra answer relevancy
        if metrics.answer_relevancy < thresholds.get("answer_relevancy", 0.6):
            alert = Alert(
                metric_name="answer_relevancy",
                current_value=metrics.answer_relevancy,
                threshold=thresholds["answer_relevancy"],
                severity="warning",
                message=(
                    f"Answer relevancy {metrics.answer_relevancy:.2f} "
                    f"below threshold {thresholds['answer_relevancy']:.2f}"
                ),
                workspace_id=metrics.workspace_id or "default",
            )
            alerts.append(alert)
            self._alerts.append(alert)
        
        # Gửi cảnh báo qua callback
        if alerts and self._alert_callback:
            try:
                for alert in alerts:
                    self._alert_callback(alert)
            except Exception as e:
                logger.error(f"Error calling alert callback: {e}")
        
        # Theo dõi số lần giảm sút liên tiếp
        workspace_id = metrics.workspace_id or "default"
        if alerts:
            self._degradation_count[workspace_id] = self._degradation_count.get(workspace_id, 0) + 1
            
            # Kiểm tra trigger tự động retraining
            if self._degradation_count[workspace_id] >= 3:
                logger.critical(
                    f"3+ lần giảm sút liên tiếp cho workspace {workspace_id}. "
                    f"Triggering automatic retraining."
                )
                await self._trigger_retraining(workspace_id)
                # Reset counter
                self._degradation_count[workspace_id] = 0
        else:
            # Reset counter khi metrics tốt
            self._degradation_count[workspace_id] = 0
        
        return alerts
    
    def get_metrics_timeseries(
        self,
        workspace_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> TimeSeriesMetrics:
        """
        Lấy metrics theo thời gian cho dashboards.
        
        Args:
            workspace_id: Định danh workspace
            start_date: Filter ngày bắt đầu (optional)
            end_date: Filter ngày kết thúc (optional)
            
        Returns:
            TimeSeriesMetrics để visualization
        """
        if workspace_id not in self._metrics_history:
            return TimeSeriesMetrics(
                timestamps=[],
                faithfulness_scores=[],
                relevancy_scores=[],
                precision_scores=[],
                recall_scores=[],
                workspace_id=workspace_id,
            )
        
        # Lấy metrics
        metrics_list = self._metrics_history[workspace_id]
        
        # Filter theo khoảng thời gian
        if start_date or end_date:
            filtered = []
            for m in metrics_list:
                if start_date and m.timestamp < start_date:
                    continue
                if end_date and m.timestamp > end_date:
                    continue
                filtered.append(m)
            metrics_list = filtered
        
        # Trích xuất time series
        return TimeSeriesMetrics(
            timestamps=[m.timestamp for m in metrics_list],
            faithfulness_scores=[m.faithfulness for m in metrics_list],
            relevancy_scores=[m.answer_relevancy for m in metrics_list],
            precision_scores=[m.context_precision for m in metrics_list],
            recall_scores=[m.context_recall for m in metrics_list],
            workspace_id=workspace_id,
        )
    
    async def _trigger_retraining(self, workspace_id: str) -> None:
        """
        Trigger tự động retraining model hoặc tuning retrieval.
        
        Args:
            workspace_id: Định danh workspace
        """
        logger.critical(
            f"🔄 Automatic retraining triggered for workspace {workspace_id}"
        )
        
        # Trong production, sẽ:
        # 1. Tạo retraining job
        # 2. Thông báo cho ML team
        # 3. Cập nhật model registry
        # 4. Schedule deployment
        
        # Hiện tại chỉ log
        # TODO: Implement actual retraining pipeline
    
    def set_alert_callback(self, callback: callable) -> None:
        """
        Set callback function cho alerts.
        
        Args:
            callback: Function được gọi khi alert được trigger
                     Signature: callback(alert: Alert)
        """
        self._alert_callback = callback
        logger.info("Alert callback registered")
    
    def get_alerts(
        self,
        workspace_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """
        Lấy các cảnh báo gần đây.
        
        Args:
            workspace_id: Filter theo workspace (optional)
            severity: Filter theo severity ("critical", "warning") (optional)
            limit: Số lượng cảnh báo tối đa trả về
            
        Returns:
            List các Alert objects
        """
        alerts = self._alerts[-limit:]
        
        # Filter theo workspace
        if workspace_id:
            alerts = [a for a in alerts if a.workspace_id == workspace_id]
        
        # Filter theo severity
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts

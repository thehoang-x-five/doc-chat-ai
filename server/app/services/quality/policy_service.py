"""
Answer policy service cho RAG pipeline - Dịch vụ chính sách trả lời cho RAG pipeline.
Đánh giá xem có nên trả lời dựa trên retrieval scores và policy mode.

Nâng cao với:
- Điều chỉnh threshold động dựa trên độ chính xác lịch sử
- Hỗ trợ A/B testing cho các policy variants
- Logging quyết định policy để giải thích
- Thông báo admin khi thay đổi threshold
- Phân tích ý nghĩa thống kê cho A/B tests
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import statistics

from app.services.core.retriever_service import RetrievalResult

logger = logging.getLogger(__name__)


class AnswerPolicy(str, Enum):
    """Các chế độ answer policy."""
    STRICT = "strict"
    BALANCED = "balanced"
    OPEN = "open"


@dataclass
class PolicyEvaluation:
    """Kết quả đánh giá policy."""
    should_answer: bool
    fallback_used: bool
    best_score: float
    threshold: float
    policy_mode: str
    disclaimer: Optional[str] = None


@dataclass
class PolicyDecision:
    """Quyết định policy nâng cao với reasoning."""
    approved: bool
    policy_mode: str
    thresholds_used: Dict[str, float]
    reasoning: str
    variant_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ThresholdAdjustment:
    """Bản ghi điều chỉnh threshold."""
    workspace_id: str
    old_thresholds: Dict[str, float]
    new_thresholds: Dict[str, float]
    reason: str
    effective_date: datetime
    historical_accuracy: float


@dataclass
class PolicyConfig:
    """Cấu hình cho một policy variant."""
    variant_id: str
    policy_mode: str
    threshold: float
    description: str


@dataclass
class ABTestResult:
    """Kết quả A/B test giữa các policy variants."""
    workspace_id: str
    variant_a_id: str
    variant_b_id: str
    variant_a_performance: float
    variant_b_performance: float
    winner: str
    statistical_significance: float
    sample_size: int
    confidence_interval: tuple
    p_value: float
    timestamp: datetime = field(default_factory=datetime.now)


class PolicyService:
    """
    Service đánh giá answer policies.
    
    Policies:
    - STRICT: Từ chối trả lời nếu best score < threshold
    - BALANCED: Trả lời với disclaimer nếu best score < threshold
    - OPEN: Luôn trả lời bất kể score
    
    Tính năng nâng cao:
    - Điều chỉnh threshold động dựa trên độ chính xác lịch sử
    - Hỗ trợ A/B testing cho policy variants
    - Logging quyết định để giải thích
    - Thông báo admin khi thay đổi threshold
    """
    
    DISCLAIMER_TEMPLATE = (
        "⚠️ Lưu ý: Câu trả lời này có thể không hoàn toàn chính xác "
        "do không tìm thấy đủ thông tin liên quan trong tài liệu. "
        "Vui lòng xác minh lại thông tin."
    )
    
    def __init__(
        self,
        policy: AnswerPolicy = AnswerPolicy.BALANCED,
        threshold: float = 0.7,
    ):
        """
        Initialize policy service.
        
        Args:
            policy: Answer policy mode
            threshold: Evidence threshold (0-1)
        """
        self.policy = policy
        self.threshold = threshold
        
        # Lưu trữ dữ liệu lịch sử (trong production, dùng database)
        self._workspace_history: Dict[str, List[float]] = {}
        self._workspace_thresholds: Dict[str, float] = {}
        self._policy_decisions: List[PolicyDecision] = []
        self._threshold_adjustments: List[ThresholdAdjustment] = []
        self._ab_tests: Dict[str, Dict[str, Any]] = {}  # workspace_id -> test data
    
    def evaluate(
        self,
        retrieval_results: List[RetrievalResult],
    ) -> PolicyEvaluation:
        """
        Đánh giá xem có nên trả lời dựa trên retrieval results.
        
        Args:
            retrieval_results: List các retrieval results
            
        Returns:
            PolicyEvaluation với quyết định
        """
        # Lấy best score
        best_score = 0.0
        if retrieval_results:
            best_score = max(r.score for r in retrieval_results)
        
        # Đánh giá dựa trên policy
        if self.policy == AnswerPolicy.STRICT:
            return self._evaluate_strict(best_score)
        elif self.policy == AnswerPolicy.BALANCED:
            return self._evaluate_balanced(best_score)
        else:  # OPEN
            return self._evaluate_open(best_score)
    
    def _evaluate_strict(self, best_score: float) -> PolicyEvaluation:
        """
        STRICT mode: Từ chối nếu score < threshold.
        """
        should_answer = best_score >= self.threshold
        
        return PolicyEvaluation(
            should_answer=should_answer,
            fallback_used=False,
            best_score=best_score,
            threshold=self.threshold,
            policy_mode=AnswerPolicy.STRICT.value,
            disclaimer=None if should_answer else (
                "Không thể trả lời câu hỏi này do không tìm thấy "
                "đủ thông tin liên quan trong tài liệu."
            ),
        )
    
    def _evaluate_balanced(self, best_score: float) -> PolicyEvaluation:
        """
        BALANCED mode: Trả lời với disclaimer nếu score < threshold.
        """
        below_threshold = best_score < self.threshold
        
        return PolicyEvaluation(
            should_answer=True,
            fallback_used=below_threshold,
            best_score=best_score,
            threshold=self.threshold,
            policy_mode=AnswerPolicy.BALANCED.value,
            disclaimer=self.DISCLAIMER_TEMPLATE if below_threshold else None,
        )
    
    def _evaluate_open(self, best_score: float) -> PolicyEvaluation:
        """
        OPEN mode: Luôn trả lời.
        """
        return PolicyEvaluation(
            should_answer=True,
            fallback_used=False,
            best_score=best_score,
            threshold=self.threshold,
            policy_mode=AnswerPolicy.OPEN.value,
            disclaimer=None,
        )
    
    @staticmethod
    def from_workspace_settings(
        answer_policy: str,
        evidence_threshold: float,
    ) -> "PolicyService":
        """
        Tạo PolicyService từ workspace settings.
        
        Args:
            answer_policy: Policy string (strict, balanced, open)
            evidence_threshold: Giá trị threshold
            
        Returns:
            PolicyService instance
        """
        try:
            policy = AnswerPolicy(answer_policy.lower())
        except ValueError:
            policy = AnswerPolicy.BALANCED
        
        return PolicyService(
            policy=policy,
            threshold=evidence_threshold,
        )
    
    # ========== PHASE 4: DYNAMIC THRESHOLD ADJUSTMENT ==========
    
    def evaluate_with_dynamic_thresholds(
        self,
        workspace_id: str,
        grounding_score: float,
        relevance_score: float,
    ) -> PolicyDecision:
        """
        Đánh giá policy với dynamic thresholds dựa trên độ chính xác lịch sử.
        
        Args:
            workspace_id: Định danh workspace
            grounding_score: Điểm xác minh grounding (0-1)
            relevance_score: Điểm relevance (0-1)
            
        Returns:
            PolicyDecision với trạng thái approval và reasoning
        """
        # Lấy workspace-specific threshold (hoặc dùng default)
        threshold = self._workspace_thresholds.get(workspace_id, self.threshold)
        
        # Tính combined score
        combined_score = (grounding_score + relevance_score) / 2.0
        
        # Đánh giá dựa trên policy mode
        approved = False
        reasoning = ""
        
        if self.policy == AnswerPolicy.STRICT:
            approved = combined_score >= threshold
            reasoning = (
                f"STRICT mode: Combined score {combined_score:.2f} "
                f"{'meets' if approved else 'below'} threshold {threshold:.2f}"
            )
        elif self.policy == AnswerPolicy.BALANCED:
            approved = True  # Luôn approve trong BALANCED mode
            if combined_score < threshold:
                reasoning = (
                    f"BALANCED mode: Combined score {combined_score:.2f} dưới "
                    f"threshold {threshold:.2f}, trả lời với disclaimer"
                )
            else:
                reasoning = (
                    f"BALANCED mode: Combined score {combined_score:.2f} "
                    f"đạt threshold {threshold:.2f}"
                )
        else:  # OPEN
            approved = True
            reasoning = f"OPEN mode: Luôn approve (score: {combined_score:.2f})"
        
        # Tạo decision
        decision = PolicyDecision(
            approved=approved,
            policy_mode=self.policy.value,
            thresholds_used={
                "grounding": threshold,
                "relevance": threshold,
                "combined": threshold,
            },
            reasoning=reasoning,
            variant_id=None,
        )
        
        # Log decision
        self._policy_decisions.append(decision)
        logger.info(
            f"Quyết định policy cho workspace {workspace_id}: "
            f"approved={approved}, reasoning={reasoning}"
        )
        
        return decision
    
    def adjust_thresholds(
        self,
        workspace_id: str,
        historical_accuracy: float,
    ) -> ThresholdAdjustment:
        """
        Điều chỉnh thresholds dựa trên độ chính xác lịch sử.
        
        Logic điều chỉnh:
        - Nếu accuracy > 90%: Tăng threshold 0.05 (nghiêm ngặt hơn)
        - Nếu accuracy < 70%: Giảm threshold 0.05 (dễ dàng hơn)
        - Ngược lại: Giữ nguyên threshold hiện tại
        
        Args:
            workspace_id: Định danh workspace
            historical_accuracy: Độ chính xác lịch sử (0-1)
            
        Returns:
            ThresholdAdjustment record
        """
        # Lấy threshold hiện tại
        old_threshold = self._workspace_thresholds.get(workspace_id, self.threshold)
        
        # Xác định điều chỉnh
        new_threshold = old_threshold
        reason = "Không cần điều chỉnh"
        
        if historical_accuracy > 0.90:
            # Độ chính xác cao: tăng threshold (nghiêm ngặt hơn)
            new_threshold = min(old_threshold + 0.05, 0.95)
            reason = (
                f"Độ chính xác cao ({historical_accuracy:.1%}): "
                f"Tăng threshold để nghiêm ngặt hơn"
            )
        elif historical_accuracy < 0.70:
            # Độ chính xác thấp: giảm threshold (dễ dàng hơn)
            new_threshold = max(old_threshold - 0.05, 0.50)
            reason = (
                f"Độ chính xác thấp ({historical_accuracy:.1%}): "
                f"Giảm threshold để dễ dàng hơn"
            )
        else:
            reason = (
                f"Độ chính xác ({historical_accuracy:.1%}) trong khoảng chấp nhận được: "
                f"Giữ threshold ở {old_threshold:.2f}"
            )
        
        # Kiểm tra xem điều chỉnh có đáng kể không (>10% thay đổi)
        threshold_change = abs(new_threshold - old_threshold)
        threshold_change_pct = (threshold_change / old_threshold) * 100 if old_threshold > 0 else 0
        
        if threshold_change_pct > 10:
            # Thay đổi đáng kể: cập nhật threshold
            self._workspace_thresholds[workspace_id] = new_threshold
            
            # Tạo adjustment record
            adjustment = ThresholdAdjustment(
                workspace_id=workspace_id,
                old_thresholds={"threshold": old_threshold},
                new_thresholds={"threshold": new_threshold},
                reason=reason,
                effective_date=datetime.now(),
                historical_accuracy=historical_accuracy,
            )
            
            # Lưu adjustment
            self._threshold_adjustments.append(adjustment)
            
            # Gửi notification
            self._send_notification(adjustment)
            
            logger.warning(
                f"Threshold được điều chỉnh cho workspace {workspace_id}: "
                f"{old_threshold:.2f} -> {new_threshold:.2f} "
                f"(thay đổi: {threshold_change_pct:.1f}%)"
            )
        else:
            # Không có thay đổi đáng kể
            adjustment = ThresholdAdjustment(
                workspace_id=workspace_id,
                old_thresholds={"threshold": old_threshold},
                new_thresholds={"threshold": old_threshold},  # Không thay đổi
                reason=reason,
                effective_date=datetime.now(),
                historical_accuracy=historical_accuracy,
            )
            
            logger.info(
                f"Không điều chỉnh threshold cho workspace {workspace_id}: "
                f"thay đổi {threshold_change_pct:.1f}% dưới ngưỡng 10%"
            )
        
        return adjustment
    
    def track_accuracy(
        self,
        workspace_id: str,
        accuracy: float,
    ) -> None:
        """
        Theo dõi độ chính xác lịch sử cho một workspace.
        
        Args:
            workspace_id: Định danh workspace
            accuracy: Điểm accuracy (0-1)
        """
        if workspace_id not in self._workspace_history:
            self._workspace_history[workspace_id] = []
        
        self._workspace_history[workspace_id].append(accuracy)
        
        # Chỉ giữ 100 records gần nhất
        if len(self._workspace_history[workspace_id]) > 100:
            self._workspace_history[workspace_id] = self._workspace_history[workspace_id][-100:]
        
        # Kiểm tra xem có nên điều chỉnh thresholds không
        if len(self._workspace_history[workspace_id]) >= 10:
            # Tính average accuracy
            avg_accuracy = statistics.mean(self._workspace_history[workspace_id])
            
            # Điều chỉnh thresholds nếu cần
            self.adjust_thresholds(workspace_id, avg_accuracy)
    
    def get_workspace_threshold(self, workspace_id: str) -> float:
        """Lấy threshold hiện tại cho một workspace."""
        return self._workspace_thresholds.get(workspace_id, self.threshold)
    
    def get_threshold_history(self, workspace_id: str) -> List[ThresholdAdjustment]:
        """Lấy lịch sử điều chỉnh threshold cho một workspace."""
        return [
            adj for adj in self._threshold_adjustments
            if adj.workspace_id == workspace_id
        ]
    
    # ========== POLICY DECISION LOGGING ==========
    
    def get_policy_decisions(
        self,
        workspace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PolicyDecision]:
        """
        Lấy policy decision logs.
        
        Args:
            workspace_id: Filter theo workspace (optional)
            limit: Số lượng decisions tối đa trả về
            
        Returns:
            List các PolicyDecision records
        """
        decisions = self._policy_decisions[-limit:]
        
        logger.info(
            f"Retrieved {len(decisions)} policy decisions"
            + (f" for workspace {workspace_id}" if workspace_id else "")
        )
        
        return decisions
    
    def log_policy_decision(
        self,
        workspace_id: str,
        decision: PolicyDecision,
    ) -> None:
        """
        Ghi log một policy decision một cách rõ ràng.
        
        Args:
            workspace_id: Định danh workspace
            decision: PolicyDecision cần log
        """
        logger.info(
            f"Policy decision được log cho workspace {workspace_id}: "
            f"approved={decision.approved}, "
            f"mode={decision.policy_mode}, "
            f"thresholds={decision.thresholds_used}, "
            f"reasoning={decision.reasoning}"
        )
        
        # Decision đã được lưu trong _policy_decisions bởi evaluate_with_dynamic_thresholds
    
    # ========== A/B TESTING SUPPORT ==========
    
    def run_ab_test(
        self,
        workspace_id: str,
        variant_a: PolicyConfig,
        variant_b: PolicyConfig,
        traffic_split: float = 0.5,
    ) -> ABTestResult:
        """
        Chạy A/B test giữa hai policy variants.
        
        Args:
            workspace_id: Định danh workspace
            variant_a: Policy variant đầu tiên
            variant_b: Policy variant thứ hai
            traffic_split: Phần trăm traffic cho variant A (0-1)
            
        Returns:
            ABTestResult với phân tích thống kê
        """
        # Khởi tạo test nếu chưa tồn tại
        if workspace_id not in self._ab_tests:
            self._ab_tests[workspace_id] = {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "variant_a_results": [],
                "variant_b_results": [],
                "traffic_split": traffic_split,
            }
            logger.info(
                f"A/B test được khởi tạo cho workspace {workspace_id}: "
                f"{variant_a.variant_id} vs {variant_b.variant_id}"
            )
        
        # Lấy test data
        test_data = self._ab_tests[workspace_id]
        variant_a_results = test_data["variant_a_results"]
        variant_b_results = test_data["variant_b_results"]
        
        # Tính performance metrics
        variant_a_performance = (
            statistics.mean(variant_a_results) if variant_a_results else 0.0
        )
        variant_b_performance = (
            statistics.mean(variant_b_results) if variant_b_results else 0.0
        )
        
        # Xác định winner
        winner = variant_a.variant_id if variant_a_performance > variant_b_performance else variant_b.variant_id
        
        # Tính statistical significance
        sample_size = len(variant_a_results) + len(variant_b_results)
        
        if sample_size >= 30 and len(variant_a_results) >= 10 and len(variant_b_results) >= 10:
            # Tính p-value và confidence interval
            p_value, confidence_interval = self._calculate_statistical_significance(
                variant_a_results, variant_b_results
            )
            statistical_significance = 1.0 - p_value
        else:
            # Không đủ dữ liệu cho phân tích thống kê
            p_value = 1.0
            confidence_interval = (0.0, 0.0)
            statistical_significance = 0.0
            logger.warning(
                f"Dữ liệu không đủ cho phân tích thống kê: "
                f"sample_size={sample_size}, cần ít nhất 30 tổng và 10 mỗi variant"
            )
        
        # Tạo result
        result = ABTestResult(
            workspace_id=workspace_id,
            variant_a_id=variant_a.variant_id,
            variant_b_id=variant_b.variant_id,
            variant_a_performance=variant_a_performance,
            variant_b_performance=variant_b_performance,
            winner=winner,
            statistical_significance=statistical_significance,
            sample_size=sample_size,
            confidence_interval=confidence_interval,
            p_value=p_value,
        )
        
        logger.info(
            f"Kết quả A/B test cho workspace {workspace_id}: "
            f"winner={winner}, "
            f"significance={statistical_significance:.2%}, "
            f"sample_size={sample_size}"
        )
        
        return result
    
    def record_ab_test_result(
        self,
        workspace_id: str,
        variant_id: str,
        performance_score: float,
    ) -> None:
        """
        Ghi lại kết quả cho một A/B test variant.
        
        Args:
            workspace_id: Định danh workspace
            variant_id: Định danh variant
            performance_score: Điểm performance (0-1)
        """
        if workspace_id not in self._ab_tests:
            logger.warning(
                f"Không tìm thấy A/B test cho workspace {workspace_id}, "
                f"không thể ghi kết quả cho variant {variant_id}"
            )
            return
        
        test_data = self._ab_tests[workspace_id]
        variant_a = test_data["variant_a"]
        variant_b = test_data["variant_b"]
        
        if variant_id == variant_a.variant_id:
            test_data["variant_a_results"].append(performance_score)
        elif variant_id == variant_b.variant_id:
            test_data["variant_b_results"].append(performance_score)
        else:
            logger.warning(
                f"Variant không xác định {variant_id} cho workspace {workspace_id}"
            )
            return
        
        logger.debug(
            f"Đã ghi kết quả A/B test: workspace={workspace_id}, "
            f"variant={variant_id}, score={performance_score:.2f}"
        )
    
    def _calculate_statistical_significance(
        self,
        variant_a_results: List[float],
        variant_b_results: List[float],
    ) -> tuple:
        """
        Tính p-value và confidence interval cho A/B test.
        
        Sử dụng Welch's t-test cho variances không bằng nhau.
        
        Args:
            variant_a_results: Kết quả cho variant A
            variant_b_results: Kết quả cho variant B
            
        Returns:
            Tuple của (p_value, confidence_interval)
        """
        try:
            from scipy import stats
            
            # Thực hiện Welch's t-test
            t_stat, p_value = stats.ttest_ind(
                variant_a_results,
                variant_b_results,
                equal_var=False,  # Welch's t-test
            )
            
            # Tính 95% confidence interval cho sự khác biệt trong means
            mean_a = statistics.mean(variant_a_results)
            mean_b = statistics.mean(variant_b_results)
            std_a = statistics.stdev(variant_a_results) if len(variant_a_results) > 1 else 0
            std_b = statistics.stdev(variant_b_results) if len(variant_b_results) > 1 else 0
            
            n_a = len(variant_a_results)
            n_b = len(variant_b_results)
            
            # Standard error của sự khác biệt
            se_diff = ((std_a ** 2 / n_a) + (std_b ** 2 / n_b)) ** 0.5
            
            # 95% confidence interval (z = 1.96 cho 95%)
            diff = mean_a - mean_b
            margin = 1.96 * se_diff
            confidence_interval = (diff - margin, diff + margin)
            
            return p_value, confidence_interval
            
        except ImportError:
            logger.warning("scipy chưa cài đặt, sử dụng tính toán đơn giản hóa")
            # Fallback: tính toán đơn giản hóa không có scipy
            mean_a = statistics.mean(variant_a_results)
            mean_b = statistics.mean(variant_b_results)
            diff = abs(mean_a - mean_b)
            
            # Ước lượng p-value đơn giản hóa
            p_value = max(0.05, 1.0 - diff)
            confidence_interval = (diff - 0.1, diff + 0.1)
            
            return p_value, confidence_interval
        except Exception as e:
            logger.error(f"Lỗi khi tính statistical significance: {e}")
            return 1.0, (0.0, 0.0)
    
    def get_ab_test_status(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Lấy trạng thái A/B test hiện tại cho một workspace."""
        if workspace_id not in self._ab_tests:
            return None
        
        test_data = self._ab_tests[workspace_id]
        return {
            "variant_a": test_data["variant_a"].variant_id,
            "variant_b": test_data["variant_b"].variant_id,
            "variant_a_samples": len(test_data["variant_a_results"]),
            "variant_b_samples": len(test_data["variant_b_results"]),
            "traffic_split": test_data["traffic_split"],
        }
    
    # ========== THRESHOLD CHANGE NOTIFICATIONS ==========
    
    def notify_threshold_change(
        self,
        adjustment: ThresholdAdjustment,
        notification_callback: Optional[callable] = None,
    ) -> None:
        """
        Thông báo cho administrators về thay đổi threshold.
        
        Args:
            adjustment: ThresholdAdjustment record
            notification_callback: Callback function cho notifications (optional)
        """
        # Tạo notification message
        message = (
            f"🔔 Policy Threshold Adjusted\n"
            f"Workspace: {adjustment.workspace_id}\n"
            f"Old Threshold: {adjustment.old_thresholds['threshold']:.2f}\n"
            f"New Threshold: {adjustment.new_thresholds['threshold']:.2f}\n"
            f"Reason: {adjustment.reason}\n"
            f"Historical Accuracy: {adjustment.historical_accuracy:.1%}\n"
            f"Effective Date: {adjustment.effective_date.isoformat()}"
        )
        
        # Log notification
        logger.warning(f"Thông báo thay đổi threshold: {message}")
        
        # Gọi notification callback nếu được cung cấp
        if notification_callback:
            try:
                notification_callback(
                    workspace_id=adjustment.workspace_id,
                    message=message,
                    adjustment=adjustment,
                )
            except Exception as e:
                logger.error(f"Lỗi khi gọi notification callback: {e}")
        
        # Trong production, sẽ gửi email/webhook/Slack notification
        # Hiện tại chỉ log
    
    def set_notification_callback(self, callback: callable) -> None:
        """
        Set callback function cho thông báo thay đổi threshold.
        
        Args:
            callback: Function được gọi khi threshold thay đổi
                     Signature: callback(workspace_id: str, message: str, adjustment: ThresholdAdjustment)
        """
        self._notification_callback = callback
        logger.info("Notification callback registered")
    
    def _send_notification(self, adjustment: ThresholdAdjustment) -> None:
        """Internal method để gửi notifications."""
        if hasattr(self, "_notification_callback"):
            self.notify_threshold_change(adjustment, self._notification_callback)
        else:
            self.notify_threshold_change(adjustment)

"""
Learning Pipeline Service - Feedback-based routing optimization.

This module provides:
1. Analysis of pattern performance from feedback
2. Routing adjustment recommendations
3. A/B testing framework for changes
4. Scheduled learning cycles

"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import random
import uuid

logger = logging.getLogger(__name__)


class AdjustmentStatus(str, Enum):
    """Status of a routing adjustment."""
    PENDING = "pending"
    TESTING = "testing"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class RoutingAdjustment:
    """A routing adjustment recommendation."""
    adjustment_id: str
    pattern_name: str
    query_type: str
    old_priority: float
    new_priority: float
    reason: str
    confidence: float
    status: AdjustmentStatus = AdjustmentStatus.PENDING
    
    # A/B testing fields
    test_percentage: float = 0.0
    test_start_date: Optional[datetime] = None
    test_end_date: Optional[datetime] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "pattern_name": self.pattern_name,
            "query_type": self.query_type,
            "old_priority": self.old_priority,
            "new_priority": self.new_priority,
            "reason": self.reason,
            "confidence": self.confidence,
            "status": self.status.value,
            "test_percentage": self.test_percentage,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PatternAnalysis:
    """Analysis results for a pattern."""
    pattern_name: str
    query_type: str
    sample_size: int
    
    # Performance metrics
    avg_rating: float
    approval_rate: float  # likes / (likes + dislikes)
    issue_rate: float  # reports / total
    
    # Feedback breakdown
    likes: int
    dislikes: int
    reports: int
    edits: int
    
    # Common issues
    common_issues: List[Tuple[str, int]] = field(default_factory=list)
    
    # Trend
    trend: str = "stable"  # "improving", "degrading", "stable"
    trend_change_percent: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "query_type": self.query_type,
            "sample_size": self.sample_size,
            "avg_rating": self.avg_rating,
            "approval_rate": self.approval_rate,
            "issue_rate": self.issue_rate,
            "trend": self.trend,
        }


class LearningPipeline:
    """
    Learning Pipeline for feedback-based routing optimization.
    
    Analyzes user feedback and pattern metrics to generate
    routing adjustments. Supports A/B testing for safe rollout.
    
    Usage:
        pipeline = LearningPipeline(
            feedback_collector=feedback_collector,
            metrics_collector=metrics_collector,
        )
        
        # Run learning cycle (usually scheduled)
        adjustments = await pipeline.run_learning_cycle()
        
        # Start A/B test for an adjustment
        await pipeline.start_ab_test(adjustment, test_percentage=0.5)
        
        # Check if adjustment should be promoted
        should_promote = await pipeline.evaluate_ab_test(adjustment)
    """
    
    # Minimum samples for analysis
    MIN_SAMPLES = 20
    
    # A/B test settings
    DEFAULT_TEST_PERCENTAGE = 0.5
    DEFAULT_TEST_DURATION_DAYS = 7
    PROMOTION_IMPROVEMENT_THRESHOLD = 0.10  # 10% improvement
    
    def __init__(
        self,
        feedback_collector: Any = None,
        metrics_collector: Any = None,
        min_samples: int = MIN_SAMPLES,
        promotion_threshold: float = PROMOTION_IMPROVEMENT_THRESHOLD,
    ):
        """
        Initialize Learning Pipeline.
        
        Args:
            feedback_collector: FeedbackCollector instance
            metrics_collector: MetricsCollector instance
            min_samples: Minimum samples for analysis
            promotion_threshold: Improvement threshold for promotion
        """
        self.feedback_collector = feedback_collector
        self.metrics_collector = metrics_collector
        self.min_samples = min_samples
        self.promotion_threshold = promotion_threshold
        
        # In-memory storage for adjustments
        self._adjustments: Dict[str, RoutingAdjustment] = {}
        self._active_tests: Dict[str, RoutingAdjustment] = {}
        
        # Pattern priorities (would be persisted in real implementation)
        self._pattern_priorities: Dict[Tuple[str, str], float] = defaultdict(lambda: 1.0)
        
        logger.info("LearningPipeline initialized")
    
    async def run_learning_cycle(self) -> List[RoutingAdjustment]:
        """
        Run a full learning cycle.
        
        Analyzes feedback, generates adjustments, and returns
        recommendations for routing changes.
        
        Returns:
            List of recommended adjustments
        """
        logger.info("Starting learning cycle")
        
        adjustments = []
        
        # Get all patterns with feedback
        patterns = await self._get_patterns_with_feedback()
        
        for pattern_name, query_type in patterns:
            # Analyze pattern performance
            analysis = await self._analyze_pattern(pattern_name, query_type)
            
            if not analysis or analysis.sample_size < self.min_samples:
                continue
            
            # Generate adjustments based on analysis
            adjustment = self._generate_adjustment(analysis)
            
            if adjustment:
                self._adjustments[adjustment.adjustment_id] = adjustment
                adjustments.append(adjustment)
        
        logger.info(f"Learning cycle complete: {len(adjustments)} adjustments")
        return adjustments
    
    async def _get_patterns_with_feedback(self) -> List[Tuple[str, str]]:
        """Get all pattern/query_type combinations with feedback."""
        if self.feedback_collector:
            try:
                # Get from feedback collector
                entries = await self.feedback_collector.get_all_entries()
                patterns = set()
                for entry in entries:
                    patterns.add((entry.pattern_used, "all"))
                return list(patterns)
            except Exception as e:
                logger.warning(f"Failed to get patterns from feedback: {e}")
        
        if self.metrics_collector:
            return self.metrics_collector.get_all_patterns()
        
        return []
    
    async def _analyze_pattern(
        self,
        pattern_name: str,
        query_type: str,
    ) -> Optional[PatternAnalysis]:
        """Analyze pattern performance from feedback."""
        if not self.feedback_collector:
            return None
        
        try:
            summary = await self.feedback_collector.get_summary(
                pattern_name=pattern_name,
                since=datetime.utcnow() - timedelta(days=30),
            )
        except Exception as e:
            logger.warning(f"Failed to get feedback summary: {e}")
            return None
        
        total = summary.likes + summary.dislikes + summary.reports
        
        if total < self.min_samples:
            return None
        
        # Calculate metrics
        approval_rate = summary.likes / (summary.likes + summary.dislikes) if (summary.likes + summary.dislikes) > 0 else 0.5
        issue_rate = summary.reports / total if total > 0 else 0.0
        
        # Determine trend
        trend = "stable"
        trend_change = 0.0
        
        # Compare to previous period (simplified)
        if hasattr(summary, 'previous_approval_rate'):
            change = approval_rate - summary.previous_approval_rate
            if change > 0.05:
                trend = "improving"
            elif change < -0.05:
                trend = "degrading"
            trend_change = change * 100
        
        return PatternAnalysis(
            pattern_name=pattern_name,
            query_type=query_type,
            sample_size=total,
            avg_rating=summary.average_rating or 3.0,
            approval_rate=approval_rate,
            issue_rate=issue_rate,
            likes=summary.likes,
            dislikes=summary.dislikes,
            reports=summary.reports,
            edits=getattr(summary, 'edits', 0),
            common_issues=[(k, v) for k, v in summary.common_issues.items()] if summary.common_issues else [],
            trend=trend,
            trend_change_percent=trend_change,
        )
    
    def _generate_adjustment(
        self,
        analysis: PatternAnalysis,
    ) -> Optional[RoutingAdjustment]:
        """Generate routing adjustment from analysis."""
        key = (analysis.pattern_name, analysis.query_type)
        current_priority = self._pattern_priorities[key]
        
        # Determine adjustment
        new_priority = current_priority
        reason = ""
        confidence = 0.0
        
        # Low approval rate -> decrease priority
        if analysis.approval_rate < 0.6:
            decrease = (0.6 - analysis.approval_rate) * 0.5
            new_priority = max(0.1, current_priority - decrease)
            reason = f"Low approval rate ({analysis.approval_rate:.1%})"
            confidence = min(0.9, analysis.sample_size / 100)
        
        # High issue rate -> decrease priority
        elif analysis.issue_rate > 0.1:
            decrease = analysis.issue_rate * 0.3
            new_priority = max(0.1, current_priority - decrease)
            reason = f"High issue rate ({analysis.issue_rate:.1%})"
            confidence = min(0.9, analysis.sample_size / 100)
        
        # Degrading trend -> slight decrease
        elif analysis.trend == "degrading":
            new_priority = max(0.1, current_priority * 0.95)
            reason = f"Degrading performance trend ({analysis.trend_change_percent:.1f}%)"
            confidence = 0.5
        
        # High approval rate -> increase priority
        elif analysis.approval_rate > 0.85:
            increase = (analysis.approval_rate - 0.85) * 0.3
            new_priority = min(2.0, current_priority + increase)
            reason = f"High approval rate ({analysis.approval_rate:.1%})"
            confidence = min(0.9, analysis.sample_size / 100)
        
        # Improving trend -> slight increase
        elif analysis.trend == "improving":
            new_priority = min(2.0, current_priority * 1.05)
            reason = f"Improving performance trend (+{analysis.trend_change_percent:.1f}%)"
            confidence = 0.5
        
        else:
            return None  # No adjustment needed
        
        # Only return if significant change
        if abs(new_priority - current_priority) < 0.05:
            return None
        
        return RoutingAdjustment(
            adjustment_id=str(uuid.uuid4()),
            pattern_name=analysis.pattern_name,
            query_type=analysis.query_type,
            old_priority=current_priority,
            new_priority=new_priority,
            reason=reason,
            confidence=confidence,
        )
    
    async def start_ab_test(
        self,
        adjustment: RoutingAdjustment,
        test_percentage: float = DEFAULT_TEST_PERCENTAGE,
        duration_days: int = DEFAULT_TEST_DURATION_DAYS,
    ) -> None:
        """
        Start A/B test for an adjustment.
        
        Args:
            adjustment: The adjustment to test
            test_percentage: Percentage of traffic for test group
            duration_days: Duration of test in days
        """
        adjustment.status = AdjustmentStatus.TESTING
        adjustment.test_percentage = test_percentage
        adjustment.test_start_date = datetime.utcnow()
        adjustment.test_end_date = datetime.utcnow() + timedelta(days=duration_days)
        
        self._active_tests[adjustment.adjustment_id] = adjustment
        
        logger.info(
            f"Started A/B test for {adjustment.pattern_name}: "
            f"{test_percentage:.0%} traffic, {duration_days} days"
        )
    
    def is_in_test_group(self, adjustment_id: str, user_id: str) -> bool:
        """
        Check if a user should be in the test group.
        
        Args:
            adjustment_id: The adjustment being tested
            user_id: User identifier
            
        Returns:
            True if user should receive test treatment
        """
        adjustment = self._active_tests.get(adjustment_id)
        if not adjustment or adjustment.status != AdjustmentStatus.TESTING:
            return False
        
        # Consistent hashing for user assignment
        hash_val = hash(f"{adjustment_id}:{user_id}") % 100
        return hash_val < (adjustment.test_percentage * 100)
    
    async def evaluate_ab_test(
        self,
        adjustment: RoutingAdjustment,
    ) -> bool:
        """
        Evaluate A/B test results.
        
        Args:
            adjustment: The adjustment being tested
            
        Returns:
            True if test shows improvement above threshold
        """
        if not adjustment.test_start_date:
            return False
        
        # Check if test duration completed
        if datetime.utcnow() < adjustment.test_end_date:
            return False  # Test still running
        
        # Get metrics for control and test groups
        # (In real implementation, this would query segmented metrics)
        
        control_metrics = adjustment.test_results.get("control", {})
        test_metrics = adjustment.test_results.get("test", {})
        
        if not control_metrics or not test_metrics:
            # If no results yet, simulate for demonstration
            control_approval = 0.7
            test_approval = 0.75
        else:
            control_approval = control_metrics.get("approval_rate", 0.7)
            test_approval = test_metrics.get("approval_rate", 0.7)
        
        # Calculate improvement
        improvement = (test_approval - control_approval) / control_approval
        
        adjustment.test_results["improvement"] = improvement
        adjustment.test_results["evaluated_at"] = datetime.utcnow().isoformat()
        
        return improvement >= self.promotion_threshold
    
    async def promote_adjustment(
        self,
        adjustment: RoutingAdjustment,
    ) -> None:
        """
        Promote an adjustment to production.
        
        Args:
            adjustment: The adjustment to promote
        """
        key = (adjustment.pattern_name, adjustment.query_type)
        
        # Apply new priority
        self._pattern_priorities[key] = adjustment.new_priority
        
        # Update status
        adjustment.status = AdjustmentStatus.PROMOTED
        
        # Remove from active tests
        if adjustment.adjustment_id in self._active_tests:
            del self._active_tests[adjustment.adjustment_id]
        
        logger.info(
            f"Promoted adjustment for {adjustment.pattern_name}: "
            f"priority {adjustment.old_priority:.2f} -> {adjustment.new_priority:.2f}"
        )
    
    async def reject_adjustment(
        self,
        adjustment: RoutingAdjustment,
        reason: str = "",
    ) -> None:
        """
        Reject an adjustment.
        
        Args:
            adjustment: The adjustment to reject
            reason: Reason for rejection
        """
        adjustment.status = AdjustmentStatus.REJECTED
        adjustment.test_results["rejection_reason"] = reason
        
        if adjustment.adjustment_id in self._active_tests:
            del self._active_tests[adjustment.adjustment_id]
        
        logger.info(f"Rejected adjustment for {adjustment.pattern_name}: {reason}")
    
    def get_pattern_priority(
        self,
        pattern_name: str,
        query_type: str = "all",
    ) -> float:
        """Get current pattern priority."""
        return self._pattern_priorities[(pattern_name, query_type)]
    
    def get_active_tests(self) -> List[RoutingAdjustment]:
        """Get all currently active A/B tests."""
        return list(self._active_tests.values())
    
    def get_adjustment(self, adjustment_id: str) -> Optional[RoutingAdjustment]:
        """Get adjustment by ID."""
        return self._adjustments.get(adjustment_id) or self._active_tests.get(adjustment_id)


# Default instance
learning_pipeline = LearningPipeline()

"""
Feedback Collector - User feedback collection and storage for RAG responses.

This module provides:
1. Structured feedback collection (likes, dislikes, edits, reports)
2. Async storage with pluggable backends
3. Feedback analysis for pattern improvement
4. A/B testing support for routing adjustments

Feedback is stored with trace context for correlation with
orchestration decisions and performance metrics.

"""
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Type of user feedback."""
    LIKE = "like"  # Positive feedback
    DISLIKE = "dislike"  # Negative feedback
    EDIT = "edit"  # User edited the response
    REPORT = "report"  # User reported an issue
    RATING = "rating"  # Numeric rating (1-5)


class IssueType(Enum):
    """Type of issue reported."""
    HALLUCINATION = "hallucination"  # Response contains fabricated information
    IRRELEVANT = "irrelevant"  # Response doesn't answer the question
    INCOMPLETE = "incomplete"  # Response is missing information
    INCORRECT = "incorrect"  # Response contains errors
    INAPPROPRIATE = "inappropriate"  # Response is inappropriate
    TOO_VERBOSE = "too_verbose"  # Response is too long
    TOO_BRIEF = "too_brief"  # Response is too short
    OTHER = "other"  # Other issue


@dataclass
class FeedbackEntry:
    """
    Individual feedback entry.
    
    Attributes:
        feedback_id: Unique identifier for this feedback
        trace_id: Related trace ID from orchestration
        query: Original user query
        response: Generated response
        pattern_used: Pattern(s) used for generation
        feedback_type: Type of feedback
        rating: Numeric rating (1-5) if provided
        issue_type: Type of issue if reporting
        comment: User's text comment
        edited_response: User's edited version if provided
        timestamp: When feedback was submitted
        metadata: Additional metadata
    """
    feedback_id: str
    trace_id: str
    query: str
    response: str
    pattern_used: str
    feedback_type: FeedbackType
    rating: Optional[int] = None
    issue_type: Optional[IssueType] = None
    comment: Optional[str] = None
    edited_response: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feedback_id": self.feedback_id,
            "trace_id": self.trace_id,
            "query": self.query,
            "response": self.response,
            "pattern_used": self.pattern_used,
            "feedback_type": self.feedback_type.value,
            "rating": self.rating,
            "issue_type": self.issue_type.value if self.issue_type else None,
            "comment": self.comment,
            "edited_response": self.edited_response,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class FeedbackSummary:
    """Summary of feedback for a pattern or period."""
    pattern_name: str
    total_feedback: int
    likes: int
    dislikes: int
    edits: int
    reports: int
    avg_rating: Optional[float]
    common_issues: List[tuple[IssueType, int]]
    approval_rate: float  # likes / (likes + dislikes)


class FeedbackStorage:
    """
    Base class for feedback storage backends.
    
    Implement this class to add custom storage (e.g., PostgreSQL, MongoDB).
    """
    
    async def store(self, feedback: FeedbackEntry) -> bool:
        """Store a feedback entry. Returns True on success."""
        raise NotImplementedError
    
    async def get_by_trace(self, trace_id: str) -> List[FeedbackEntry]:
        """Get all feedback for a trace."""
        raise NotImplementedError
    
    async def get_by_pattern(
        self,
        pattern_name: str,
        since: Optional[datetime] = None,
    ) -> List[FeedbackEntry]:
        """Get all feedback for a pattern."""
        raise NotImplementedError
    
    async def get_summary(
        self,
        pattern_name: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> FeedbackSummary:
        """Get feedback summary."""
        raise NotImplementedError


class InMemoryFeedbackStorage(FeedbackStorage):
    """
    In-memory feedback storage for development/testing.
    
    Note: Data is lost on restart. Use PostgreSQL storage for production.
    """
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._entries: List[FeedbackEntry] = []
    
    async def store(self, feedback: FeedbackEntry) -> bool:
        """Store a feedback entry."""
        self._entries.append(feedback)
        
        # Trim if exceeds max
        while len(self._entries) > self.max_entries:
            self._entries.pop(0)
        
        return True
    
    async def get_by_trace(self, trace_id: str) -> List[FeedbackEntry]:
        """Get all feedback for a trace."""
        return [e for e in self._entries if e.trace_id == trace_id]
    
    async def get_by_pattern(
        self,
        pattern_name: str,
        since: Optional[datetime] = None,
    ) -> List[FeedbackEntry]:
        """Get all feedback for a pattern."""
        result = [e for e in self._entries if e.pattern_used == pattern_name]
        if since:
            result = [e for e in result if e.timestamp >= since]
        return result
    
    async def get_summary(
        self,
        pattern_name: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> FeedbackSummary:
        """Get feedback summary."""
        entries = self._entries
        
        if pattern_name:
            entries = [e for e in entries if e.pattern_used == pattern_name]
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        
        if not entries:
            return FeedbackSummary(
                pattern_name=pattern_name or "all",
                total_feedback=0,
                likes=0,
                dislikes=0,
                edits=0,
                reports=0,
                avg_rating=None,
                common_issues=[],
                approval_rate=0.0,
            )
        
        likes = sum(1 for e in entries if e.feedback_type == FeedbackType.LIKE)
        dislikes = sum(1 for e in entries if e.feedback_type == FeedbackType.DISLIKE)
        edits = sum(1 for e in entries if e.feedback_type == FeedbackType.EDIT)
        reports = sum(1 for e in entries if e.feedback_type == FeedbackType.REPORT)
        
        ratings = [e.rating for e in entries if e.rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        
        # Count issues
        issue_counts: Dict[IssueType, int] = {}
        for e in entries:
            if e.issue_type:
                issue_counts[e.issue_type] = issue_counts.get(e.issue_type, 0) + 1
        
        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        approval = likes / (likes + dislikes) if (likes + dislikes) > 0 else 0.0
        
        return FeedbackSummary(
            pattern_name=pattern_name or "all",
            total_feedback=len(entries),
            likes=likes,
            dislikes=dislikes,
            edits=edits,
            reports=reports,
            avg_rating=avg_rating,
            common_issues=common_issues,
            approval_rate=approval,
        )


class FeedbackCollector:
    """
    Feedback Collector for user feedback on RAG responses.
    
    Features:
    - Structured feedback collection
    - Async storage with pluggable backends
    - Feedback analysis for improvement
    - Integration with trace context
    
    Usage:
        collector = FeedbackCollector()
        
        # Collect like/dislike
        await collector.like(trace_id="...", query="...", ...)
        
        # Collect report
        await collector.report(
            trace_id="...",
            issue_type=IssueType.HALLUCINATION,
            comment="The response fabricated this fact...",
        )
        
        # Get summary
        summary = await collector.get_summary(pattern_name="adaptive_rag")
    """
    
    def __init__(
        self,
        storage: Optional[FeedbackStorage] = None,
        on_feedback: Optional[Callable[[FeedbackEntry], None]] = None,
    ):
        """
        Initialize the Feedback Collector.
        
        Args:
            storage: Storage backend (defaults to in-memory)
            on_feedback: Optional callback when feedback is received
        """
        self.storage = storage or InMemoryFeedbackStorage()
        self.on_feedback = on_feedback
        
        logger.info("FeedbackCollector initialized")
    
    def _generate_id(self) -> str:
        """Generate a unique feedback ID."""
        return str(uuid4())
    
    async def like(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a like (positive feedback).
        
        Returns feedback_id.
        """
        return await self._record_feedback(
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=FeedbackType.LIKE,
            metadata=metadata,
        )
    
    async def dislike(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a dislike (negative feedback).
        
        Returns feedback_id.
        """
        return await self._record_feedback(
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=FeedbackType.DISLIKE,
            comment=comment,
            metadata=metadata,
        )
    
    async def rate(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        rating: int,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a rating (1-5 scale).
        
        Returns feedback_id.
        """
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        
        return await self._record_feedback(
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=FeedbackType.RATING,
            rating=rating,
            comment=comment,
            metadata=metadata,
        )
    
    async def edit(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        edited_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record user edit of response.
        
        Returns feedback_id.
        """
        return await self._record_feedback(
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=FeedbackType.EDIT,
            edited_response=edited_response,
            metadata=metadata,
        )
    
    async def report(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        issue_type: IssueType,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record an issue report.
        
        Returns feedback_id.
        """
        return await self._record_feedback(
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=FeedbackType.REPORT,
            issue_type=issue_type,
            comment=comment,
            metadata=metadata,
        )
    
    async def _record_feedback(
        self,
        trace_id: str,
        query: str,
        response: str,
        pattern_used: str,
        feedback_type: FeedbackType,
        rating: Optional[int] = None,
        issue_type: Optional[IssueType] = None,
        comment: Optional[str] = None,
        edited_response: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record feedback internally."""
        feedback_id = self._generate_id()
        
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            trace_id=trace_id,
            query=query,
            response=response,
            pattern_used=pattern_used,
            feedback_type=feedback_type,
            rating=rating,
            issue_type=issue_type,
            comment=comment,
            edited_response=edited_response,
            metadata=metadata or {},
        )
        
        # Store
        success = await self.storage.store(entry)
        
        if not success:
            logger.error(f"Failed to store feedback {feedback_id}")
            raise RuntimeError("Failed to store feedback")
        
        # Callback
        if self.on_feedback:
            try:
                self.on_feedback(entry)
            except Exception as e:
                logger.error(f"Feedback callback failed: {e}")
        
        logger.debug(f"Recorded {feedback_type.value} feedback: {feedback_id}")
        
        return feedback_id
    
    async def get_by_trace(self, trace_id: str) -> List[FeedbackEntry]:
        """Get all feedback for a trace."""
        return await self.storage.get_by_trace(trace_id)
    
    async def get_by_pattern(
        self,
        pattern_name: str,
        since: Optional[datetime] = None,
    ) -> List[FeedbackEntry]:
        """Get all feedback for a pattern."""
        return await self.storage.get_by_pattern(pattern_name, since)
    
    async def get_summary(
        self,
        pattern_name: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> FeedbackSummary:
        """Get feedback summary."""
        return await self.storage.get_summary(pattern_name, since)
    
    async def analyze_for_improvement(
        self,
        pattern_name: str,
        min_samples: int = 100,
    ) -> Dict[str, Any]:
        """
        Analyze feedback to suggest improvements.
        
        Args:
            pattern_name: Pattern to analyze
            min_samples: Minimum samples required for analysis
            
        Returns:
            Analysis results with suggestions
        """
        summary = await self.get_summary(pattern_name)
        
        if summary.total_feedback < min_samples:
            return {
                "pattern": pattern_name,
                "status": "insufficient_data",
                "samples": summary.total_feedback,
                "required": min_samples,
            }
        
        # Analyze approval rate
        analysis = {
            "pattern": pattern_name,
            "status": "analyzed",
            "samples": summary.total_feedback,
            "approval_rate": summary.approval_rate,
            "avg_rating": summary.avg_rating,
            "common_issues": [
                {"issue": issue.value, "count": count}
                for issue, count in summary.common_issues
            ],
            "suggestions": [],
        }
        
        # Generate suggestions based on analysis
        if summary.approval_rate < 0.5:
            analysis["suggestions"].append({
                "type": "low_approval",
                "message": f"Pattern has low approval rate ({summary.approval_rate:.1%}). Consider adjusting routing.",
                "priority": "high",
            })
        
        # Check for common issues
        for issue, count in summary.common_issues:
            if count >= summary.total_feedback * 0.1:  # Issue in >10% of feedback
                analysis["suggestions"].append({
                    "type": "common_issue",
                    "message": f"'{issue.value}' reported in {count} cases ({count/summary.total_feedback:.1%})",
                    "priority": "medium" if issue != IssueType.HALLUCINATION else "high",
                })
        
        # Check edit rate
        edit_rate = summary.edits / summary.total_feedback if summary.total_feedback > 0 else 0
        if edit_rate > 0.2:
            analysis["suggestions"].append({
                "type": "high_edit_rate",
                "message": f"High edit rate ({edit_rate:.1%}) suggests responses need refinement",
                "priority": "medium",
            })
        
        return analysis


# Default instance
feedback_collector = FeedbackCollector()

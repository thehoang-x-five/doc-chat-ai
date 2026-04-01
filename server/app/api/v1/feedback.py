"""
Feedback API endpoints - User feedback collection for RAG responses.

Endpoints:
- POST /api/v1/feedback/like - Like a response
- POST /api/v1/feedback/dislike - Dislike a response
- POST /api/v1/feedback/report - Report an issue
- GET /api/v1/feedback/summary - Get feedback summary
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


# =============================================================================
# Request/Response Models
# =============================================================================

class LikeFeedbackRequest(BaseModel):
    """Request to like a response."""
    message_id: UUID
    conversation_id: UUID
    metadata: Optional[dict] = None


class DislikeFeedbackRequest(BaseModel):
    """Request to dislike a response."""
    message_id: UUID
    conversation_id: UUID
    reason: Optional[str] = None
    issue_type: Optional[str] = Field(
        None,
        description="Type of issue: hallucination, irrelevant, incomplete, incorrect, inappropriate, too_verbose, too_brief, other"
    )
    metadata: Optional[dict] = None


class ReportFeedbackRequest(BaseModel):
    """Request to report a problematic response."""
    message_id: UUID
    conversation_id: UUID
    issue_type: str = Field(
        ...,
        description="Type of issue being reported"
    )
    description: str = Field(
        ...,
        description="Detailed description of the issue"
    )
    expected_response: Optional[str] = Field(
        None,
        description="What was the expected response"
    )
    metadata: Optional[dict] = None


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    success: bool
    feedback_id: str
    message: str


class FeedbackSummaryResponse(BaseModel):
    """Feedback summary statistics."""
    total_feedback: int
    likes: int
    dislikes: int
    reports: int
    approval_rate: float
    common_issues: list[tuple[str, int]]


# =============================================================================
# Global FeedbackCollector instance
# =============================================================================

_feedback_collector = None


def _get_feedback_collector():
    """Get or create FeedbackCollector singleton."""
    global _feedback_collector
    if _feedback_collector is None:
        try:
            from app.services.quality.feedback_collector import FeedbackCollector
            _feedback_collector = FeedbackCollector()
            logger.info("FeedbackCollector initialized")
        except ImportError as e:
            logger.warning(f"FeedbackCollector not available: {e}")
    return _feedback_collector


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/like", response_model=FeedbackResponse)
async def like_response(
    request: LikeFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Like a response.
    
    Records positive feedback for a RAG response to track quality.
    """
    collector = _get_feedback_collector()
    if not collector:
        raise HTTPException(
            status_code=503,
            detail="Feedback service not available"
        )
    
    try:
        from app.services.quality.feedback_collector import FeedbackType
        
        feedback = await collector.collect(
            feedback_type=FeedbackType.LIKE,
            trace_id=str(request.message_id),
            query=str(request.conversation_id),
            response="",  # Can be fetched from DB if needed
            pattern_name="unknown",
            metadata=request.metadata or {},
        )
        
        logger.info(f"✅ Like recorded for message {request.message_id}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=str(feedback.feedback_id),
            message="Thank you for your feedback!"
        )
        
    except Exception as e:
        logger.error(f"Failed to record like: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dislike", response_model=FeedbackResponse)
async def dislike_response(
    request: DislikeFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Dislike a response with optional reason.
    
    Records negative feedback with issue categorization.
    """
    collector = _get_feedback_collector()
    if not collector:
        raise HTTPException(
            status_code=503,
            detail="Feedback service not available"
        )
    
    try:
        from app.services.quality.feedback_collector import FeedbackType, IssueType
        
        # Map issue type string to enum
        issue = None
        if request.issue_type:
            try:
                issue = IssueType(request.issue_type)
            except ValueError:
                issue = IssueType.OTHER
        
        metadata = request.metadata or {}
        if request.reason:
            metadata["reason"] = request.reason
        
        feedback = await collector.collect(
            feedback_type=FeedbackType.DISLIKE,
            trace_id=str(request.message_id),
            query=str(request.conversation_id),
            response="",
            pattern_name="unknown",
            issue_type=issue,
            metadata=metadata,
        )
        
        logger.info(f"👎 Dislike recorded for message {request.message_id}: {request.issue_type}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=str(feedback.feedback_id),
            message="Thank you for helping us improve!"
        )
        
    except Exception as e:
        logger.error(f"Failed to record dislike: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report", response_model=FeedbackResponse)
async def report_response(
    request: ReportFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Report a problematic response.
    
    Records detailed report for review and improvement.
    """
    collector = _get_feedback_collector()
    if not collector:
        raise HTTPException(
            status_code=503,
            detail="Feedback service not available"
        )
    
    try:
        from app.services.quality.feedback_collector import FeedbackType, IssueType
        
        # Map issue type
        try:
            issue = IssueType(request.issue_type)
        except ValueError:
            issue = IssueType.OTHER
        
        metadata = request.metadata or {}
        metadata["description"] = request.description
        if request.expected_response:
            metadata["expected_response"] = request.expected_response
        
        feedback = await collector.collect(
            feedback_type=FeedbackType.REPORT,
            trace_id=str(request.message_id),
            query=str(request.conversation_id),
            response="",
            pattern_name="unknown",
            issue_type=issue,
            metadata=metadata,
        )
        
        logger.warning(f"🚨 Report recorded for message {request.message_id}: {request.issue_type} - {request.description[:100]}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=str(feedback.feedback_id),
            message="Thank you for reporting. We'll review this issue."
        )
        
    except Exception as e:
        logger.error(f"Failed to record report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    pattern_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get feedback summary statistics.
    
    Returns aggregated feedback data for monitoring.
    """
    collector = _get_feedback_collector()
    if not collector:
        return FeedbackSummaryResponse(
            total_feedback=0,
            likes=0,
            dislikes=0,
            reports=0,
            approval_rate=0.0,
            common_issues=[],
        )
    
    try:
        summary = await collector.get_summary(pattern_name=pattern_name)
        
        return FeedbackSummaryResponse(
            total_feedback=summary.total_feedback,
            likes=summary.likes,
            dislikes=summary.dislikes,
            reports=summary.reports,
            approval_rate=summary.approval_rate,
            common_issues=[(issue.value, count) for issue, count in summary.common_issues],
        )
        
    except Exception as e:
        logger.error(f"Failed to get feedback summary: {e}")
        return FeedbackSummaryResponse(
            total_feedback=0,
            likes=0,
            dislikes=0,
            reports=0,
            approval_rate=0.0,
            common_issues=[],
        )

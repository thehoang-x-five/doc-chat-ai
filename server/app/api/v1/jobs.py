"""
Job management API endpoints.
"""
import asyncio
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.job import (
    JobResponse, JobListResponse, JobCancelRequest
)
from app.services.analytics.job_service import (
    JobService, JobNotFoundError, JobServiceError
)
from app.services.analytics.workspace_service import PermissionDeniedError

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List jobs in a workspace."""
    try:
        job_service = JobService(db)
        jobs = await job_service.list(
            workspace_id=workspace_id,
            user_id=current_user.id,
            status=status,
            job_type=job_type,
            skip=skip,
            limit=limit,
        )
        return JobListResponse(
            jobs=[JobResponse.model_validate(j) for j in jobs],
            total=len(jobs),
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get job details."""
    try:
        job_service = JobService(db)
        job = await job_service.get(job_id, current_user.id)
        return JobResponse.model_validate(job)
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a job."""
    try:
        job_service = JobService(db)
        job = await job_service.cancel(job_id, current_user.id)
        await db.commit()
        return JobResponse.model_validate(job)
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except JobServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}/events")
async def job_events(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events for job progress updates.
    
    Returns a stream of events with job status updates.
    """
    try:
        job_service = JobService(db)
        # Verify access
        await job_service.get(job_id, current_user.id)
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    
    async def event_generator():
        """Generate SSE events for job progress."""
        last_status = None
        last_progress = None
        
        while True:
            try:
                # Get fresh job data
                job = await job_service.get(job_id)
                
                # Send update if changed
                if job.status != last_status or job.progress != last_progress:
                    last_status = job.status
                    last_progress = job.progress
                    
                    data = {
                        "id": str(job.id),
                        "status": job.status,
                        "progress": job.progress,
                        "step": job.step,
                        "error_message": job.error_message,
                    }
                    
                    yield f"data: {data}\n\n"
                
                # Stop if job is complete
                if job.status in ["DONE", "ERROR", "CANCELED"]:
                    yield f"event: complete\ndata: {{'status': '{job.status}'}}\n\n"
                    break
                
                # Wait before next poll
                await asyncio.sleep(1)
                
            except Exception as e:
                yield f"event: error\ndata: {{'error': '{str(e)}'}}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

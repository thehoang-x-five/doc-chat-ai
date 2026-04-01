"""
In-memory job store and progress tracking
"""
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobStep(str, Enum):
    UPLOAD = "upload"
    PREPROCESS = "preprocess"
    PARSE = "parse"
    POSTPROCESS = "postprocess"
    DONE = "done"


class Job:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = JobStatus.QUEUED
        self.step = JobStep.UPLOAD
        self.percent = 0
        self.message = "Job created"
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def update(self, status: Optional[JobStatus] = None, step: Optional[JobStep] = None, 
               percent: Optional[int] = None, message: Optional[str] = None,
               result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Update job state"""
        if status is not None:
            self.status = status
        if step is not None:
            self.step = step
        if percent is not None:
            self.percent = percent
        if message is not None:
            self.message = message
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error
        self.updated_at = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        data = {
            "jobId": self.job_id,
            "status": self.status.value,
            "step": self.step.value,
            "percent": self.percent,
            "message": self.message,
            "error": self.error
        }
        
        # Include result if job is done
        if self.status == JobStatus.DONE and self.result:
            data["result"] = self.result
            
        return data


class JobStore:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.cleanup_interval = 3600  # 1 hour
        self.job_ttl = 24 * 3600  # 24 hours
        self._cleanup_task: Optional[asyncio.Task] = None
        
    def create_job(self) -> str:
        """Create a new job and return job ID"""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = Job(job_id)
        logger.info(f"Created job {job_id}")
        return job_id
        
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)
        
    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job state"""
        job = self.jobs.get(job_id)
        if job:
            job.update(**kwargs)
            logger.debug(f"Updated job {job_id}: {job.status.value} - {job.message}")
            return True
        return False
        
    def delete_job(self, job_id: str) -> bool:
        """Delete job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Deleted job {job_id}")
            return True
        return False
        
    def cleanup_old_jobs(self):
        """Clean up old jobs"""
        cutoff_time = datetime.now() - timedelta(seconds=self.job_ttl)
        old_jobs = [
            job_id for job_id, job in self.jobs.items()
            if job.updated_at < cutoff_time
        ]
        
        for job_id in old_jobs:
            self.delete_job(job_id)
            
        if old_jobs:
            logger.info(f"Cleaned up {len(old_jobs)} old jobs")
            
    def cleanup_all(self):
        """Clean up all jobs"""
        count = len(self.jobs)
        self.jobs.clear()
        if count > 0:
            logger.info(f"Cleaned up all {count} jobs")
            
    async def start_cleanup_task(self):
        """Start periodic cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
    async def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
    async def _cleanup_loop(self):
        """Periodic cleanup loop"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self.cleanup_old_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")


# Global job store instance
job_store = JobStore()
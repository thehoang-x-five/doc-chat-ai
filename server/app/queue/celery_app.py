"""
Celery application configuration.
"""
from celery import Celery
from kombu import Queue

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "rag_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 min soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # Number of concurrent workers
    
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute default retry delay
    task_max_retries=3,  # Max 3 retries
    
    # Task routing
    task_routes={
        "app.queue.tasks.ocr.*": {"queue": "ocr"},
        "app.queue.tasks.index.*": {"queue": "index"},
        "app.queue.tasks.convert.*": {"queue": "convert"},
        "app.queue.tasks.enrichment.*": {"queue": "enrichment"},
    },
    
    # Queue definitions
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("ocr", routing_key="ocr"),
        Queue("index", routing_key="index"),
        Queue("convert", routing_key="convert"),
        Queue("enrichment", routing_key="enrichment"),
    ),
    
    # Default queue
    task_default_queue="default",
    task_default_routing_key="default",
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.queue.tasks"])

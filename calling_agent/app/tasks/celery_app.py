"""
Celery Configuration for High-Throughput Call Processing
"""
import os
from celery import Celery

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "calling_agent",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.call_tasks"]
)

# Celery configuration for high throughput
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Concurrency settings
    worker_prefetch_multiplier=4,  # Prefetch 4 tasks per worker
    worker_concurrency=8,  # 8 concurrent tasks per worker process

    # Task routing
    task_routes={
        "app.tasks.call_tasks.initiate_call_task": {"queue": "calls"},
        "app.tasks.call_tasks.process_webhook_task": {"queue": "webhooks"},
    },

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_time_limit=300,  # 5 minute hard limit
    task_soft_time_limit=240,  # 4 minute soft limit

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Rate limiting at broker level
    task_default_rate_limit="1000/m",  # 1000 tasks per minute default

    # Connection pooling
    broker_pool_limit=50,
    broker_connection_timeout=10,
    broker_connection_retry_on_startup=True,
)

# Define task queues
celery_app.conf.task_queues = {
    "calls": {
        "exchange": "calls",
        "routing_key": "calls",
    },
    "webhooks": {
        "exchange": "webhooks",
        "routing_key": "webhooks",
    },
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
}

"""Celery app for the API Gateway.

Broker: Redis (DB 2 to avoid collision with Feast DB 0/1).
Result backend: Redis (DB 3).
Used for asynchronous decision triggering, audit sinks, and drift runs.

No fixed-delay retries (ADR-016) — the default retry backoff uses Celery's
exponential-with-jitter setting.
"""

from __future__ import annotations

import os

from celery import Celery

BROKER_URL = os.environ.get("SYNAPSE_CELERY_BROKER", "redis://redis:6379/2")
BACKEND_URL = os.environ.get("SYNAPSE_CELERY_BACKEND", "redis://redis:6379/3")

celery_app = Celery(
    "synapse",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["api.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="synapse.default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_retry_jitter=True,
    broker_connection_retry_on_startup=True,
)

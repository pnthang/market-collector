"""Compatibility wrapper: expose Celery app from `app.queue.celery_app`."""
from .queue.celery_app import celery  # noqa: F401

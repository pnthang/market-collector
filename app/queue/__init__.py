"""Queue package.

Re-exports the existing Celery application for `app.queue` namespace.
"""
from ..celery_app import celery  # noqa: F401

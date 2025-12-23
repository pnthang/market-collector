
"""Deprecated compatibility wrapper for the ML package.

This module re-exports the canonical ML implementation from ``app.ml.core``
and emits a deprecation warning. Callers should import from
``app.ml.core`` instead.
"""
from warnings import warn

warn("app.ml is deprecated — import from app.ml.core instead", DeprecationWarning)

from .ml.core import *  # noqa: F401,F403

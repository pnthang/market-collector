"""ML package.

This package re-exports the ML core implementation and provides a
compatibility shim for callers importing ``app.ml``. The shim emits a
deprecation warning to encourage importing from ``app.ml.core``.
"""
from warnings import warn

warn("app.ml is deprecated — import from app.ml.core instead", DeprecationWarning)

from .core import *  # re-export core functions at package level


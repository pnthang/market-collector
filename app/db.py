"""Compatibility wrapper: re-export new `app.db.db` module objects."""
from .db.db import engine, SessionLocal, Base, init_db  # noqa: F401


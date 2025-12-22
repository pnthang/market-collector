from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_PRE_PING

# Create engine with sensible defaults for Postgres
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=DB_POOL_PRE_PING,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    # Import models here to ensure they are registered on Base
    from . import models
    Base.metadata.create_all(bind=engine)

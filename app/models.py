from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint, Index, func
from .db import Base


class Index(Base):
    __tablename__ = "indexes"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(255))
    source = Column(String(64), nullable=True)


class IndexPrice(Base):
    __tablename__ = "index_prices"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    source = Column(String(64), nullable=True)
    price = Column(Float, nullable=False)
    change = Column(Float)
    change_percent = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_index_time", "index_code", "timestamp"),
        UniqueConstraint("index_code", "timestamp", name="u_index_time"),
    )


class IndexMetadata(Base):
    __tablename__ = "index_metadata"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(255))
    description = Column(String(1024))
    source = Column(String(64), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IndexConstituent(Base):
    __tablename__ = "index_constituents"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    symbol = Column(String(64), nullable=False)
    name = Column(String(255))
    weight = Column(Float)
    shares = Column(Float)
    market_cap = Column(Float)
    price = Column(Float)
    change = Column(Float)
    change_percent = Column(Float)
    __table_args__ = (
        Index("ix_constituent_index_symbol", "index_code", "symbol"),
    )

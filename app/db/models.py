from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint, Index, func
from sqlalchemy import JSON
from .db import Base


class IndexModel(Base):
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


class IndexAnalysis(Base):
    __tablename__ = "index_analysis"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    title = Column(String(1024))
    summary = Column(String(2048))
    source = Column(String(255))
    url = Column(String(1024), unique=True)
    published_at = Column(DateTime(timezone=True))


class IndexNews(Base):
    __tablename__ = "index_news"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    headline = Column(String(1024))
    summary = Column(String(2048))
    publisher = Column(String(255))
    url = Column(String(1024), unique=True)
    published_at = Column(DateTime(timezone=True))


class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level = Column(String(32), index=True)
    logger = Column(String(255))
    message = Column(String(4096))



class IndexTracking(Base):
    __tablename__ = "index_tracking"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class IndexIndicator(Base):
    __tablename__ = "index_indicators"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    data = Column(JSON)
    source = Column(String(64), default='ml')


class IndexPrediction(Base):
    __tablename__ = "index_predictions"
    id = Column(Integer, primary_key=True)
    index_code = Column(String(64), nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    horizon_days = Column(Integer, nullable=False)
    predicted_price = Column(Float, nullable=False)
    change_percent = Column(Float)
    model_version = Column(String(255))
    metadata_json = Column("metadata", JSON)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(128), nullable=False, index=True)
    model_path = Column(String(1024), nullable=False)
    model_name = Column(String(255))
    trained_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metrics = Column(JSON)
    features = Column(JSON)
    notes = Column(String(1024))


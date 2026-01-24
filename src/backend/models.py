"""
SQLAlchemy models for the Polymarket News Tracker.

Defines Market, NewsArticle, PriceHistory, and AppState tables with proper indexing.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.database import Base


class Market(Base):
    """Model representing a Polymarket prediction market."""

    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    slug: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume_24h: Mapped[float] = mapped_column(Float, default=0.0)
    volume_7d: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    yes_percentage: Mapped[float] = mapped_column(Float, default=50.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    clob_token_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_markets_volume_7d", "volume_7d"),
        Index("idx_markets_is_active", "is_active"),
        Index("idx_markets_slug", "slug"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "volume_24h": self.volume_24h,
            "volume_7d": self.volume_7d,
            "liquidity": self.liquidity,
            "yes_percentage": self.yes_percentage,
            "is_active": self.is_active,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "image_url": self.image_url,
            "clob_token_ids": self.clob_token_ids,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class PriceHistory(Base):
    """Model for storing market price/percentage history over time."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    yes_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_price_history_market_time", "market_id", "timestamp"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "market_id": self.market_id,
            "yes_percentage": self.yes_percentage,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class NewsArticle(Base):
    """Model representing a news article related to a market."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_news_market_id", "market_id"),
        Index("idx_news_published_at", "published_at"),
        Index("idx_news_market_published", "market_id", "published_at"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "market_id": self.market_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "author": self.author,
            "image_url": self.image_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "sentiment_score": self.sentiment_score,
        }


class AppState(Base):
    """Model for storing application state like last update times."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

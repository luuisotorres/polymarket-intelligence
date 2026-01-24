"""
Pydantic schemas for Polymarket API responses.

Defines data models for markets and related data structures.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TokenInfo(BaseModel):
    """Token information from Polymarket."""

    token_id: str = Field(alias="token_id", default="")
    outcome: str = Field(default="")
    price: float = Field(default=0.5)
    winner: bool = Field(default=False)

    class Config:
        """Pydantic config."""

        populate_by_name = True
        extra = "ignore"


class MarketResponse(BaseModel):
    """Response model for a single market from the API."""

    # Use Field with alias for camelCase API fields
    id: str = Field(default="", alias="id")
    condition_id: str = Field(default="", alias="conditionId")
    question: str = Field(default="")
    description: str = Field(default="")
    slug: str = Field(default="")
    market_slug: str = Field(default="", alias="slug")  # Backup alias
    end_date_iso: str | None = Field(default=None, alias="endDateIso")
    game_start_time: str | None = Field(default=None, alias="gameStartTime")
    active: bool = Field(default=True)
    closed: bool = Field(default=False)
    archived: bool = Field(default=False)
    accepting_orders: bool = Field(default=True, alias="acceptingOrders")

    # Volume fields - use the direct API fields
    volume: str = Field(default="0")
    volume_num: float = Field(default=0.0, alias="volumeNum")
    volume_24hr: float = Field(default=0.0, alias="volume24hr")
    volume_1wk: float = Field(default=0.0, alias="volume1wk")
    volume_1mo: float = Field(default=0.0, alias="volume1mo")

    # Liquidity
    liquidity: str = Field(default="0")
    liquidity_num: float = Field(default=0.0, alias="liquidityNum")

    # Outcomes and prices
    outcomes: str = Field(default="")
    outcome_prices: str = Field(default="", alias="outcomePrices")

    # Other fields
    tokens: list[TokenInfo] = Field(default_factory=list)
    rewards: dict | None = Field(default=None)
    image: str = Field(default="")
    icon: str = Field(default="")
    clob_token_ids: str = Field(default="", alias="clobTokenIds")

    class Config:
        """Pydantic config."""

        populate_by_name = True
        extra = "ignore"


class MarketOut(BaseModel):
    """Output model for a market sent to the frontend."""

    id: str
    slug: str
    title: str
    description: str | None = None
    volume_24h: float = 0.0
    volume_7d: float = 0.0
    liquidity: float = 0.0
    yes_percentage: float = 50.0
    is_active: bool = True
    end_date: datetime | None = None
    image_url: str | None = None
    clob_token_ids: str | None = None
    last_updated: datetime | None = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class MarketListResponse(BaseModel):
    """Response containing a list of markets."""

    markets: list[MarketOut]
    total: int
    last_updated: datetime | None = None


class MarketStatusResponse(BaseModel):
    """Response for market update status."""

    last_updated: datetime | None = None
    market_count: int = 0
    status: str = "ok"

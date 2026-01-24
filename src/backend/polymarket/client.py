"""
Polymarket API client.

Fetches market data from the Polymarket CLOB API using the official SDK.
"""

import logging
import json
from datetime import datetime

import httpx
import httpx

from src.backend.config import settings
from src.backend.polymarket.schemas import MarketResponse

from src.backend.config import settings
from src.backend.polymarket.schemas import MarketResponse

logger = logging.getLogger(__name__)

# Polymarket API endpoints
POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"
MARKETS_ENDPOINT = f"{POLYMARKET_API_BASE}/markets"


class PolymarketClient:
    """Client for interacting with the Polymarket API."""

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the Polymarket client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._clob_client = None  # Typed as ClobClient | None implicitly

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _get_clob_client(self):
        """Get or create the CLOB client."""
        if self._clob_client is None:
            if settings.POLYMARKET_API_KEY and settings.POLYMARKET_SECRET and settings.POLYMARKET_PASSPHRASE:
                try:
                    from py_clob_client.client import ClobClient
                    from py_clob_client.constants import POLYGON
                    from py_clob_client.clob_types import ApiCreds

                    creds = ApiCreds(
                        api_key=settings.POLYMARKET_API_KEY,
                        api_secret=settings.POLYMARKET_SECRET,
                        api_passphrase=settings.POLYMARKET_PASSPHRASE,
                    )
                    self._clob_client = ClobClient(
                        host="https://clob.polymarket.com",
                        creds=creds,
                        chain_id=POLYGON,
                        signature_type=2, 
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize ClobClient: {e}")
                    return None
        return self._clob_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[MarketResponse]:
        """
        Fetch markets from Polymarket API.

        Args:
            limit: Maximum number of markets to fetch.
            offset: Offset for pagination.
            active: Filter for active markets only.
            closed: Include closed markets.
            order: Field to order by.
            ascending: Sort order.

        Returns:
            List of market responses.
        """
        client = await self._get_client()

        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }

        try:
            response = await client.get(MARKETS_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()

            markets = []
            for item in data:
                try:
                    market = MarketResponse.model_validate(item)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            return markets

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching markets: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            raise

    async def get_top_markets_by_volume(self, limit: int = 100) -> list[dict]:
        """
        Get the top active markets by 7-day volume.

        Args:
            limit: Number of markets to return.

        Returns:
            List of market dictionaries ready for database storage.
        """
        all_markets: list[MarketResponse] = []
        offset = 0
        fetch_limit = 100

        # Fetch enough markets to get requested number of active ones
        # We fetch more because some might be inactive/closed
        while len(all_markets) < limit * 2:
            try:
                batch = await self.fetch_markets(
                    limit=fetch_limit,
                    offset=offset,
                    active=True,
                    closed=False,
                    order="volume24hr", # standard ordering
                    ascending=False,
                )
                if not batch:
                    break
                all_markets.extend(batch)
                offset += fetch_limit
                
                # Break early if we got fewer than limit (no more data)
                if len(batch) < fetch_limit:
                    break
            except Exception as e:
                logger.error(f"Error fetching markets batch: {e}")
                break

        # Filter and transform markets
        processed_markets = []
        for market in all_markets:
            if not market.active or market.closed or market.archived:
                continue

            # Parse yes percentage from outcome_prices
            yes_percentage = 50.0
            try:
                if market.outcome_prices:
                    prices = json.loads(market.outcome_prices)
                    if prices and len(prices) > 0:
                        # First price is typically the "Yes" outcome
                        price_val = float(prices[0])
                        if 0 <= price_val <= 1:
                            yes_percentage = price_val * 100
            except Exception as e:
                logger.debug(f"Could not parse outcome_prices: {e}")

            # Parse end date
            end_date = None
            try:
                if market.end_date_iso:
                    # Handle various date formats
                    date_str = market.end_date_iso
                    if "T" in date_str:
                        end_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    else:
                        end_date = datetime.fromisoformat(date_str)
            except Exception as e:
                logger.debug(f"Could not parse end_date: {e}")

            # Use actual volume fields from API
            volume_24h = market.volume_24hr if market.volume_24hr else 0.0
            volume_7d = market.volume_1wk if market.volume_1wk else 0.0
            liquidity = market.liquidity_num if market.liquidity_num else 0.0
            
            # Fallback to volume_num if specific fields are zero
            if volume_24h == 0 and market.volume_num:
                volume_24h = market.volume_num
            if volume_7d == 0 and market.volume_num:
                volume_7d = market.volume_num
            
            # Additional check for volume_7d being 0 but volume_24h > 0
            if volume_7d == 0 and volume_24h > 0:
                volume_7d = volume_24h

            # Get market ID - prefer condition_id, fallback to id or slug
            market_id = market.condition_id or market.id or market.slug

            processed_markets.append(
                {
                    "id": market_id,
                    "slug": market.slug or market.market_slug,
                    "title": market.question,
                    "description": market.description,
                    "volume_24h": volume_24h,
                    "volume_7d": volume_7d,
                    "liquidity": liquidity,
                    "yes_percentage": round(yes_percentage, 2),
                    "is_active": market.active and not market.closed,
                    "end_date": end_date,
                    "image_url": market.image or market.icon or None,
                    "clob_token_ids": market.clob_token_ids or None,
                }
            )

        # Sort by 7d volume (or 24h if 7d is zero)
        processed_markets.sort(
            key=lambda x: (x["volume_7d"], x["volume_24h"]), 
            reverse=True
        )
        return processed_markets[:limit]

    async def fetch_trades(self, market_slug: str, limit: int = 500) -> list[dict]:
        """
        Fetch recent trades for a market using Data API.
        
        Args:
            market_slug: The market slug (e.g. "will-ethereum-reach-6000-in-january-2026").
            limit: Number of trades to fetch.
            
        Returns:
            List of trade dictionaries.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                "https://data-api.polymarket.com/trades",
                params={"market": market_slug, "limit": limit}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Data API returned status {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching trades from Data API: {e}")
            return []



# Global client instance
polymarket_client = PolymarketClient()

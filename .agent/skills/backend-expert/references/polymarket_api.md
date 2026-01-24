# Polymarket API Reference

## Overview

Polymarket provides REST APIs for accessing prediction market data including markets, prices, volumes, and order books.

## Base URLs

```
CLOB API: https://clob.polymarket.com
Gamma API: https://gamma-api.polymarket.com
```

## Common Endpoints

### Markets

```http
GET /markets
```

Query parameters:
- `limit` (int): Max results (default: 100)
- `offset` (int): Pagination offset
- `active` (bool): Filter active markets only
- `closed` (bool): Filter closed markets

Response model:
```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Market(BaseModel):
    id: str
    question: str
    description: Optional[str]
    outcomes: list[str]
    outcomePrices: list[float]
    volume: float
    liquidity: float
    endDate: datetime
    active: bool
    closed: bool
```

### Market Details

```http
GET /markets/{market_id}
```

### Price History

```http
GET /prices-history
```

Query parameters:
- `market` (str): Market ID (required)
- `interval` (str): `1m`, `5m`, `1h`, `1d`
- `startTs` (int): Unix timestamp
- `endTs` (int): Unix timestamp

### Order Book

```http
GET /book
```

Query parameters:
- `token_id` (str): Token ID for the outcome

## FastAPI Integration Pattern

```python
import httpx
from pydantic import BaseModel
from functools import lru_cache

class PolymarketService:
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
    
    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
                headers={"Accept": "application/json"}
            )
        return self._client
    
    async def get_markets(
        self, 
        limit: int = 100, 
        active: bool = True
    ) -> list[dict]:
        client = await self.get_client()
        response = await client.get(
            "/markets",
            params={"limit": limit, "active": active}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_market(self, market_id: str) -> dict:
        client = await self.get_client()
        response = await client.get(f"/markets/{market_id}")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

# Dependency injection
@lru_cache
def get_polymarket_service() -> PolymarketService:
    return PolymarketService()
```

## Error Handling

```python
from fastapi import HTTPException
import httpx

async def safe_polymarket_call(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(503, "Polymarket API timeout")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(429, "Rate limited by Polymarket")
        raise HTTPException(502, f"Polymarket API error: {e.response.status_code}")
```

## Common Issues

### Rate Limiting
- No official rate limits published
- Implement exponential backoff
- Cache frequently accessed data (markets list) for 60s minimum

### Data Freshness
- Prices update in real-time via websockets
- REST endpoints may have 1-5s delay
- Use CLOB API for trading, Gamma API for analytics

### Token IDs vs Market IDs
- Each outcome has a unique `token_id`
- Market has a `market_id` (condition ID)
- Price feeds require `token_id`

# News API Reference

## Overview

News API (newsapi.org) provides access to real-time news articles from various sources worldwide. Useful for market sentiment and event tracking.

## Base URL

```
https://newsapi.org/v2
```

## Authentication

API key required in header or query parameter:
```http
Authorization: Bearer YOUR_API_KEY
# or
?apiKey=YOUR_API_KEY
```

## Endpoints

### Top Headlines

```http
GET /top-headlines
```

Parameters:
- `country` (str): 2-letter ISO code (e.g., `us`, `gb`)
- `category` (str): `business`, `technology`, `politics`, etc.
- `q` (str): Search query
- `pageSize` (int): Results per page (max 100)
- `page` (int): Page number

### Everything (Search)

```http
GET /everything
```

Parameters:
- `q` (str): Search query (required)
- `sources` (str): Comma-separated source IDs
- `from` (str): Date in ISO format
- `to` (str): Date in ISO format
- `language` (str): `en`, `es`, `fr`, etc.
- `sortBy` (str): `relevancy`, `popularity`, `publishedAt`
- `pageSize` (int): Max 100
- `page` (int): Page number

## Response Models

```python
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class Source(BaseModel):
    id: Optional[str]
    name: str

class Article(BaseModel):
    source: Source
    author: Optional[str]
    title: str
    description: Optional[str]
    url: HttpUrl
    urlToImage: Optional[HttpUrl]
    publishedAt: datetime
    content: Optional[str]

class NewsResponse(BaseModel):
    status: str
    totalResults: int
    articles: list[Article]
```

## FastAPI Integration

```python
import httpx
from datetime import datetime, timedelta
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    news_api_key: str
    
    class Config:
        env_file = ".env"

class NewsService:
    BASE_URL = "https://newsapi.org/v2"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
    
    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=15.0,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        return self._client
    
    async def search_news(
        self,
        query: str,
        from_date: datetime | None = None,
        page_size: int = 20
    ) -> dict:
        if from_date is None:
            from_date = datetime.now() - timedelta(days=7)
        
        client = await self.get_client()
        response = await client.get(
            "/everything",
            params={
                "q": query,
                "from": from_date.isoformat(),
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "language": "en"
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_headlines(
        self,
        country: str = "us",
        category: str = "business"
    ) -> dict:
        client = await self.get_client()
        response = await client.get(
            "/top-headlines",
            params={"country": country, "category": category}
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
```

## Rate Limits

| Plan       | Requests/day | Requests/15min |
|------------|--------------|----------------|
| Developer  | 100          | 50             |
| Business   | 5,000        | 500            |
| Enterprise | Unlimited    | Configurable   |

## Caching Strategy

```python
from datetime import datetime, timedelta

class NewsCacheService:
    def __init__(self, news_service: NewsService, cache_ttl: int = 300):
        self.news = news_service
        self.cache: dict[str, tuple[dict, datetime]] = {}
        self.ttl = timedelta(seconds=cache_ttl)
    
    async def search_cached(self, query: str) -> dict:
        key = f"search:{query}"
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
        
        data = await self.news.search_news(query)
        self.cache[key] = (data, datetime.now())
        return data
```

## Common Issues

### API Key Security
- Never expose API key in frontend code
- Use environment variables
- Proxy requests through backend

### Historical Data Limits
- Free tier: 1 month history
- Paid tiers: varies by plan
- For older data, consider alternative providers

### Response Truncation
- `content` field is truncated (~200 chars)
- For full content, scrape the article URL

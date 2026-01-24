---
name: backend-expert
description: >
  Backend expert for Python 3.12, FastAPI, and SQLite code review and debugging.
  Use this skill when reviewing, analyzing, or fixing backend code involving
  FastAPI routes, SQLite database operations, or API integrations with Polymarket
  API, News API, or TradingView widgets. Use for code reviews of Python backend
  code, debugging FastAPI endpoints, SQLite query optimization, API integration
  troubleshooting, performance and security audits, and architecture recommendations.
---

# Backend Expert

Expert code reviewer specializing in Python 3.12, FastAPI, SQLite, and API integrations for financial/prediction market applications.

## Core Expertise

### 1. Python 3.12 Best Practices
- Type hints with modern syntax (`type` statement, `Self`, `TypeVarTuple`)
- Pattern matching with `match/case`
- Exception groups and `except*`
- Performance optimization with `__slots__`, generators, async patterns
- Proper use of `dataclasses`, `Pydantic v2` models

### 2. FastAPI Standards
- Route organization with `APIRouter`
- Dependency injection patterns
- Response models with proper status codes
- Error handling with `HTTPException`
- Background tasks and lifecycle events
- OpenAPI documentation best practices

### 3. SQLite Optimization
- Connection pooling patterns for async apps
- Query optimization and indexing strategies
- Transaction management
- WAL mode for concurrent access
- Avoiding common pitfalls (N+1 queries, missing indexes)

## Code Review Checklist

When reviewing backend code, systematically check:

### Security
```python
# ❌ SQL Injection vulnerability
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ Parameterized query
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### Error Handling
```python
# ❌ Generic exception swallowing
try:
    result = await api_call()
except Exception:
    pass

# ✅ Specific handling with logging
try:
    result = await api_call()
except httpx.TimeoutException as e:
    logger.warning("API timeout: %s", e)
    raise HTTPException(status_code=503, detail="Service temporarily unavailable")
```

### Async Patterns
```python
# ❌ Blocking call in async context
def get_data():
    return requests.get(url).json()  # Blocks event loop

# ✅ Proper async HTTP client
async def get_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Resource Management
```python
# ❌ Connection leak
conn = sqlite3.connect("db.sqlite")
cursor = conn.execute(query)

# ✅ Context manager
async with aiosqlite.connect("db.sqlite") as conn:
    async with conn.execute(query) as cursor:
        rows = await cursor.fetchall()
```

## API Integration Guidelines

For detailed API documentation and integration patterns, see:

- **Polymarket API**: See [references/polymarket_api.md](references/polymarket_api.md) for market data, volume, and price endpoints
- **News API**: See [references/news_api.md](references/news_api.md) for real-time news aggregation patterns
- **TradingView Widget**: See [references/tradingview_widget.md](references/tradingview_widget.md) for embedded chart integration

## Common Issue Patterns

### 1. Rate Limiting
```python
# ✅ Implement exponential backoff
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def fetch_with_retry(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### 2. Connection Pooling
```python
# ✅ Reusable client with connection pooling
from contextlib import asynccontextmanager
import httpx

@asynccontextmanager
async def get_http_client():
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        yield client
```

### 3. Caching Strategy
```python
# ✅ Simple TTL cache for API responses
from functools import lru_cache
from datetime import datetime, timedelta
import asyncio

class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> tuple[bool, any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return True, value
        return False, None
    
    def set(self, key: str, value: any) -> None:
        self._cache[key] = (value, datetime.now())
```

## FastAPI Project Structure

Recommended structure for maintainable backends:

```
src/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan events
│   ├── config.py            # Settings with pydantic-settings
│   ├── deps.py              # Dependency injection
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── markets.py       # Polymarket endpoints
│   │   ├── news.py          # News API endpoints
│   │   └── charts.py        # TradingView widget config
│   ├── models/
│   │   ├── __init__.py
│   │   ├── market.py        # Pydantic models
│   │   └── news.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── polymarket.py    # API client
│   │   ├── news.py
│   │   └── cache.py
│   └── db/
│       ├── __init__.py
│       ├── connection.py    # SQLite connection
│       └── queries.py       # SQL queries
└── tests/
    ├── conftest.py
    └── test_*.py
```

## Review Response Format

When providing code review feedback, use this format:

```markdown
## Code Review: [File/Component Name]

### 🔴 Critical Issues
- [Security vulnerabilities, data loss risks, breaking bugs]

### 🟡 Warnings  
- [Performance issues, bad practices, potential bugs]

### 🟢 Suggestions
- [Style improvements, optional optimizations]

### Summary
[Overall assessment and priority fixes]
```

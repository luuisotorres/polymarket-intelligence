# TradingView Widget Reference

## Overview

TradingView widgets embed interactive charts into web applications. The backend provides configuration endpoints that the frontend consumes to render charts.

## Widget Types

| Widget | Use Case |
|--------|----------|
| Advanced Chart | Full trading interface |
| Mini Chart | Compact price display |
| Ticker Tape | Scrolling price ticker |
| Symbol Overview | Symbol info + mini chart |
| Market Overview | Multiple symbols grid |

## Backend Configuration Pattern

The backend serves widget configuration to the frontend:

```python
from pydantic import BaseModel
from enum import Enum

class ChartTheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"

class ChartInterval(str, Enum):
    ONE_MIN = "1"
    FIVE_MIN = "5"
    FIFTEEN_MIN = "15"
    ONE_HOUR = "60"
    ONE_DAY = "D"
    ONE_WEEK = "W"

class ChartConfig(BaseModel):
    symbol: str
    interval: ChartInterval = ChartInterval.ONE_DAY
    theme: ChartTheme = ChartTheme.DARK
    width: int = 800
    height: int = 400
    hide_top_toolbar: bool = False
    hide_side_toolbar: bool = False
    allow_symbol_change: bool = True
    save_image: bool = True
    studies: list[str] = []

class WidgetConfigResponse(BaseModel):
    widget_type: str
    container_id: str
    config: ChartConfig
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Query

router = APIRouter(prefix="/charts", tags=["charts"])

@router.get("/config/{symbol}")
async def get_chart_config(
    symbol: str,
    theme: ChartTheme = Query(default=ChartTheme.DARK),
    interval: ChartInterval = Query(default=ChartInterval.ONE_DAY)
) -> WidgetConfigResponse:
    """Return TradingView widget configuration for a symbol."""
    return WidgetConfigResponse(
        widget_type="advanced_chart",
        container_id=f"tv_chart_{symbol.replace(':', '_')}",
        config=ChartConfig(
            symbol=symbol,
            theme=theme,
            interval=interval,
            studies=["Volume", "MACD"]
        )
    )

@router.get("/symbols")
async def get_available_symbols() -> list[dict]:
    """Return symbols available for charting."""
    return [
        {"symbol": "CRYPTO:BTCUSD", "name": "Bitcoin"},
        {"symbol": "CRYPTO:ETHUSD", "name": "Ethereum"},
        {"symbol": "NASDAQ:AAPL", "name": "Apple Inc"},
    ]
```

## Symbol Mapping for Polymarket

Since Polymarket doesn't have TradingView symbols, map related assets:

```python
POLYMARKET_TO_TRADINGVIEW = {
    # Map market categories to related symbols
    "crypto": ["CRYPTO:BTCUSD", "CRYPTO:ETHUSD"],
    "politics": ["ECONOMICS:USINTERESTRATE", "TVC:DXY"],
    "sports": [],  # No direct mapping
    "finance": ["SP:SPX", "TVC:VIX"],
}

async def get_related_symbols(market_category: str) -> list[str]:
    return POLYMARKET_TO_TRADINGVIEW.get(market_category, [])
```

## Frontend Integration (Reference)

The backend serves config; frontend renders:

```html
<!-- Frontend receives config from /charts/config/{symbol} -->
<div id="tv_chart_CRYPTO_BTCUSD"></div>

<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
<script>
// Config fetched from backend
const config = await fetch('/api/charts/config/CRYPTO:BTCUSD').then(r => r.json());

new TradingView.widget({
    container_id: config.container_id,
    symbol: config.config.symbol,
    interval: config.config.interval,
    theme: config.config.theme,
    width: config.config.width,
    height: config.config.height,
    hide_top_toolbar: config.config.hide_top_toolbar,
    studies: config.config.studies
});
</script>
```

## Common Issues

### CORS Headers
Backend must allow widget domains:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

### Symbol Validation
Validate symbols before returning config:
```python
VALID_EXCHANGES = {"CRYPTO", "NASDAQ", "NYSE", "TVC", "SP", "ECONOMICS"}

def validate_symbol(symbol: str) -> bool:
    if ":" not in symbol:
        return False
    exchange, ticker = symbol.split(":", 1)
    return exchange in VALID_EXCHANGES
```

### Theme Persistence
Store user preference in session/database:
```python
from fastapi import Depends, Cookie

async def get_user_theme(
    theme_pref: str | None = Cookie(default=None)
) -> ChartTheme:
    if theme_pref == "light":
        return ChartTheme.LIGHT
    return ChartTheme.DARK
```

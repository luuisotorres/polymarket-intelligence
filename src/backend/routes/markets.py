"""
API routes for market data.

Provides endpoints for fetching top 50 markets, individual market details, and price history.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import get_db
from src.backend.models import AppState, Market
from src.backend.polymarket.client import polymarket_client
from src.backend.polymarket.schemas import MarketListResponse, MarketOut, MarketStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/markets", tags=["markets"])

CLOB_API_URL = "https://clob.polymarket.com"


class PricePoint(BaseModel):
    """Single price/percentage point in time."""

    timestamp: datetime
    yes_percentage: float
    volume: float = 0.0


class PriceHistoryResponse(BaseModel):
    """Response model for price history."""

    market_id: str
    history: list[PricePoint]
    timeframe: str


@router.get("/top50", response_model=MarketListResponse)
async def get_top_50_markets(db: AsyncSession = Depends(get_db)) -> MarketListResponse:
    """
    Get the top 100 markets by 7-day volume.
    
    (Endpoint name kept as /top50 for compatibility, but returns up to 100)

    Returns:
        List of top 100 active markets sorted by volume.
    """
    result = await db.execute(
        select(Market)
        .where(Market.is_active == True)  # noqa: E712
        .order_by(Market.volume_7d.desc())
        .limit(100)
    )
    markets = result.scalars().all()

    # Get last update time
    state_result = await db.execute(
        select(AppState).where(AppState.key == "markets_last_updated")
    )
    state = state_result.scalar_one_or_none()
    last_updated = None
    if state:
        try:
            last_updated = datetime.fromisoformat(state.value)
        except Exception:
            pass

    return MarketListResponse(
        markets=[MarketOut.model_validate(m) for m in markets],
        total=len(markets),
        last_updated=last_updated,
    )


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status(db: AsyncSession = Depends(get_db)) -> MarketStatusResponse:
    """
    Get the status of market data updates.

    Returns:
        Last update time and market count.
    """
    # Count markets
    result = await db.execute(select(Market).where(Market.is_active == True))  # noqa: E712
    markets = result.scalars().all()

    # Get last update time
    state_result = await db.execute(
        select(AppState).where(AppState.key == "markets_last_updated")
    )
    state = state_result.scalar_one_or_none()
    last_updated = None
    if state:
        try:
            last_updated = datetime.fromisoformat(state.value)
        except Exception:
            pass

    return MarketStatusResponse(
        last_updated=last_updated,
        market_count=len(markets),
        status="ok",
    )


async def fetch_price_history_from_clob(
    token_id: str, interval: str, fidelity: int
) -> list[dict]:
    """
    Fetch price history from Polymarket CLOB API.

    Args:
        token_id: The CLOB token ID (first one is "Yes" token).
        interval: Time interval (1d, 7d, 30d, max).
        fidelity: Data point frequency in minutes.

    Returns:
        List of {t: timestamp, p: price} dicts.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CLOB_API_URL}/prices-history",
                params={
                    "market": token_id,
                    "interval": interval,
                    "fidelity": fidelity,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("history", [])
    except Exception as e:
        logger.error(f"Failed to fetch price history from CLOB: {e}")
        return []


@router.get("/{market_id}/history", response_model=PriceHistoryResponse)
async def get_price_history(
    market_id: str,
    timeframe: str = Query(default="24H", pattern="^(24H|7D|1M|ALL)$"),
    db: AsyncSession = Depends(get_db),
) -> PriceHistoryResponse:
    """
    Get price/percentage history for a market from Polymarket CLOB API.

    Args:
        market_id: The market ID.
        timeframe: Time range - 1H, 6H, 1D, 1W, 1M, or ALL.

    Returns:
        Price history data points.
    """
    # Get market to find CLOB token ID
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Parse CLOB token IDs
    if not market.clob_token_ids:
        # Return current price as single point if no token IDs
        return PriceHistoryResponse(
            market_id=market_id,
            history=[
                PricePoint(
                    timestamp=market.last_updated or datetime.utcnow(),
                    yes_percentage=market.yes_percentage,
                    volume=market.volume_24h,
                )
            ],
            timeframe=timeframe,
        )

    try:
        token_ids = json.loads(market.clob_token_ids)
        if not token_ids or len(token_ids) == 0:
            raise ValueError("Empty token IDs")
        # First token is typically the "Yes" outcome
        yes_token_id = token_ids[0]
    except Exception as e:
        logger.error(f"Failed to parse clob_token_ids: {e}")
        return PriceHistoryResponse(
            market_id=market_id,
            history=[
                PricePoint(
                    timestamp=market.last_updated or datetime.utcnow(),
                    yes_percentage=market.yes_percentage,
                    volume=market.volume_24h,
                )
            ],
            timeframe=timeframe,
        )

    # Map timeframe to CLOB API parameters
    timeframe_config = {
        "24H": ("1d", 15),    # 1 day with 15-minute fidelity
        "7D": ("7d", 60),     # 7 days with 1-hour fidelity
        "1M": ("30d", 240),   # 30 days with 4-hour fidelity
        "ALL": ("max", 1440), # All time with 1-day fidelity
    }
    interval, fidelity = timeframe_config.get(timeframe, ("1d", 15))

    # Fetch from CLOB API
    history_data = await fetch_price_history_from_clob(yes_token_id, interval, fidelity)

    if not history_data:
        # Fallback to current price
        return PriceHistoryResponse(
            market_id=market_id,
            history=[
                PricePoint(
                    timestamp=market.last_updated or datetime.utcnow(),
                    yes_percentage=market.yes_percentage,
                    volume=market.volume_24h,
                )
            ],
            timeframe=timeframe,
        )

    # No additional filtering needed - CLOB API handles timeframes directly

    # Convert to PricePoint format
    history = [
        PricePoint(
            timestamp=datetime.utcfromtimestamp(h["t"]),
            yes_percentage=h["p"] * 100,  # Convert 0-1 to percentage
            volume=0.0,  # CLOB doesn't provide volume per point
        )
        for h in history_data
    ]

    return PriceHistoryResponse(
        market_id=market_id,
        history=history,
        timeframe=timeframe,
    )


class MarketSignal(BaseModel):
    """A trading signal with strength and description."""
    name: str
    signal: str  # "bullish", "bearish", "neutral"
    strength: int  # 1-5
    description: str
    value: float | None = None


class MarketStats(BaseModel):
    """Comprehensive market statistics and signals."""
    market_id: str
    current_price: float
    
    # Price changes
    change_24h: float
    change_24h_percent: float
    change_7d: float
    change_7d_percent: float
    
    # High/Low
    high_24h: float
    low_24h: float
    high_7d: float
    low_7d: float
    
    # Volume
    volume_24h: float
    volume_7d: float
    
    # Overall sentiment
    overall_signal: str  # "bullish", "bearish", "neutral"
    overall_strength: int  # 1-5
    
    # Individual signals
    signals: list[MarketSignal]


@router.get("/{market_id}/stats")
async def get_market_stats(
    market_id: str,
    db: AsyncSession = Depends(get_db)
) -> MarketStats:
    """
    Get comprehensive market statistics and trading signals.
    
    Computes price movement, volatility, and bullish/bearish signals
    based on 24h and 7d price action and volume.
    """
    # Get market
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    
    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    current_price = market.yes_percentage
    volume_24h = market.volume_24h or 0
    volume_7d = market.volume_7d or 0
    
    # Fetch price history for 24h and 7d
    history_24h = []
    history_7d = []
    
    if market.clob_token_ids:
        try:
            token_ids = json.loads(market.clob_token_ids)
            if token_ids:
                yes_token_id = token_ids[0]
                # Fetch both timeframes in parallel
                history_24h, history_7d = await asyncio.gather(
                    fetch_price_history_from_clob(yes_token_id, "1d", 15),
                    fetch_price_history_from_clob(yes_token_id, "7d", 60),
                )
        except Exception as e:
            logger.warning(f"Failed to fetch history for stats: {e}")
    
    # Calculate 24h stats
    if history_24h and len(history_24h) > 1:
        prices_24h = [h["p"] * 100 for h in history_24h]
        first_24h = prices_24h[0]
        high_24h = max(prices_24h)
        low_24h = min(prices_24h)
        change_24h = current_price - first_24h
        change_24h_percent = (change_24h / first_24h * 100) if first_24h > 0 else 0
    else:
        high_24h = current_price
        low_24h = current_price
        first_24h = current_price
        change_24h = 0
        change_24h_percent = 0
    
    # Calculate 7d stats
    if history_7d and len(history_7d) > 1:
        prices_7d = [h["p"] * 100 for h in history_7d]
        first_7d = prices_7d[0]
        high_7d = max(prices_7d)
        low_7d = min(prices_7d)
        change_7d = current_price - first_7d
        change_7d_percent = (change_7d / first_7d * 100) if first_7d > 0 else 0
    else:
        high_7d = current_price
        low_7d = current_price
        first_7d = current_price
        change_7d = 0
        change_7d_percent = 0
    
    # Generate signals
    signals = []
    bullish_score = 0
    bearish_score = 0
    
    # Signal 1: 24h Price Momentum
    if abs(change_24h_percent) > 1:
        if change_24h_percent > 0:
            strength = min(5, int(change_24h_percent / 2) + 1)
            signals.append(MarketSignal(
                name="24h Momentum",
                signal="bullish",
                strength=strength,
                description=f"Price up {change_24h_percent:.1f}% in 24h",
                value=change_24h_percent
            ))
            bullish_score += strength
        else:
            strength = min(5, int(abs(change_24h_percent) / 2) + 1)
            signals.append(MarketSignal(
                name="24h Momentum",
                signal="bearish",
                strength=strength,
                description=f"Price down {abs(change_24h_percent):.1f}% in 24h",
                value=change_24h_percent
            ))
            bearish_score += strength
    else:
        signals.append(MarketSignal(
            name="24h Momentum",
            signal="neutral",
            strength=1,
            description="Price stable in 24h",
            value=change_24h_percent
        ))
    
    # Signal 2: 7d Trend
    if abs(change_7d_percent) > 3:
        if change_7d_percent > 0:
            strength = min(5, int(change_7d_percent / 3) + 1)
            signals.append(MarketSignal(
                name="7d Trend",
                signal="bullish",
                strength=strength,
                description=f"Strong uptrend: +{change_7d_percent:.1f}% over 7 days",
                value=change_7d_percent
            ))
            bullish_score += strength
        else:
            strength = min(5, int(abs(change_7d_percent) / 3) + 1)
            signals.append(MarketSignal(
                name="7d Trend",
                signal="bearish",
                strength=strength,
                description=f"Strong downtrend: {change_7d_percent:.1f}% over 7 days",
                value=change_7d_percent
            ))
            bearish_score += strength
    else:
        signals.append(MarketSignal(
            name="7d Trend",
            signal="neutral",
            strength=1,
            description="No significant weekly trend",
            value=change_7d_percent
        ))
    
    # Signal 3: Price Position (relative to range)
    if history_7d and len(history_7d) > 5:
        range_7d = high_7d - low_7d
        if range_7d > 0:
            position = (current_price - low_7d) / range_7d
            if position > 0.8:
                signals.append(MarketSignal(
                    name="Range Position",
                    signal="bullish",
                    strength=4,
                    description=f"Near 7d high ({position*100:.0f}% of range)",
                    value=position * 100
                ))
                bullish_score += 4
            elif position < 0.2:
                signals.append(MarketSignal(
                    name="Range Position",
                    signal="bearish",
                    strength=4,
                    description=f"Near 7d low ({position*100:.0f}% of range)",
                    value=position * 100
                ))
                bearish_score += 4
            else:
                signals.append(MarketSignal(
                    name="Range Position",
                    signal="neutral",
                    strength=2,
                    description=f"Mid-range ({position*100:.0f}% of range)",
                    value=position * 100
                ))
    
    # Signal 4: Volume Analysis
    if volume_7d > 0:
        daily_avg = volume_7d / 7
        if volume_24h > daily_avg * 1.5:
            signals.append(MarketSignal(
                name="Volume Surge",
                signal="bullish" if change_24h > 0 else "bearish",
                strength=3,
                description=f"Volume {volume_24h/daily_avg:.1f}x above average",
                value=volume_24h / daily_avg
            ))
            if change_24h > 0:
                bullish_score += 3
            else:
                bearish_score += 3
        elif volume_24h < daily_avg * 0.5:
            signals.append(MarketSignal(
                name="Low Volume",
                signal="neutral",
                strength=2,
                description="Below average volume - low conviction",
                value=volume_24h / daily_avg if daily_avg > 0 else 0
            ))
    
    # Signal 5: Volatility
    if history_24h and len(history_24h) > 10:
        prices = [h["p"] * 100 for h in history_24h]
        volatility = max(prices) - min(prices)
        if volatility > 5:
            signals.append(MarketSignal(
                name="High Volatility",
                signal="neutral",
                strength=3,
                description=f"24h range: {volatility:.1f}% - expect swings",
                value=volatility
            ))
        elif volatility < 1:
            signals.append(MarketSignal(
                name="Low Volatility",
                signal="neutral",
                strength=2,
                description=f"24h range: {volatility:.1f}% - consolidating",
                value=volatility
            ))
    
    # Calculate overall signal
    total_score = bullish_score - bearish_score
    if total_score > 3:
        overall_signal = "bullish"
        overall_strength = min(5, total_score // 2)
    elif total_score < -3:
        overall_signal = "bearish"
        overall_strength = min(5, abs(total_score) // 2)
    else:
        overall_signal = "neutral"
        overall_strength = 2
    
    return MarketStats(
        market_id=market_id,
        current_price=round(current_price, 2),
        change_24h=round(change_24h, 2),
        change_24h_percent=round(change_24h_percent, 2),
        change_7d=round(change_7d, 2),
        change_7d_percent=round(change_7d_percent, 2),
        high_24h=round(high_24h, 2),
        low_24h=round(low_24h, 2),
        high_7d=round(high_7d, 2),
        low_7d=round(low_7d, 2),
        volume_24h=round(volume_24h, 0),
        volume_7d=round(volume_7d, 0),
        overall_signal=overall_signal,
        overall_strength=overall_strength,
        signals=signals
    )

@router.get("/{market_id}", response_model=MarketOut)
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)) -> MarketOut:
    """
    Get details for a specific market.

    Args:
        market_id: The market ID or slug.

    Returns:
        Market details.
    """
    # Try by ID first
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()

    # Try by slug if not found
    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    return MarketOut.model_validate(market)


@router.get("/{market_id}/trades")
async def get_market_trades(
    market_id: str, 
    min_volume: float = 100.0,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent large trades (whale orders) for a market.
    
    Returns individual trades above the min_volume threshold.
    Includes both BUY and SELL orders with bullish/bearish sentiment.
    
    Bullish = Buying Yes OR Selling No (betting on positive outcome)
    Bearish = Buying No OR Selling Yes (betting on negative outcome)
    """
    try:
        # Get market to find slug
        result = await db.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one_or_none()

        if not market:
            result = await db.execute(select(Market).where(Market.slug == market_id))
            market = result.scalar_one_or_none()

        if not market:
            raise HTTPException(status_code=404, detail="Market not found")

        market_slug = market.slug
        
        if not market_slug:
            return []

        # Fetch trades from Data API
        trades = await polymarket_client.fetch_trades(market_slug, limit=limit)
        
        if not trades:
            return []

        whale_trades = []
        cutoff = datetime.utcnow() - timedelta(hours=48)
        
        for trade in trades:
            try:
                if not isinstance(trade, dict):
                    continue

                # Filter by market slug to ensure correct market
                trade_slug = trade.get("slug")
                if trade_slug and trade_slug != market_slug:
                    continue

                # Parse timestamp
                ts_val = trade.get("timestamp")
                if not ts_val:
                    continue
                    
                trade_time = None
                if isinstance(ts_val, (int, float)):
                    trade_time = datetime.utcfromtimestamp(int(ts_val))
                else:
                    try:
                        trade_time = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    
                if trade_time < cutoff:
                    continue

                # Get trade details
                side = trade.get("side", "").upper()
                if side not in ("BUY", "SELL"):
                    continue

                outcome = trade.get("outcome", "")
                
                try:
                    size = float(trade.get("size", 0))
                    price = float(trade.get("price", 0))
                except (ValueError, TypeError):
                    continue

                volume = size * price
                
                # Filter by min_volume
                if volume < min_volume:
                    continue

                # Determine bullish/bearish sentiment
                # Bullish = Buying Yes OR Selling No
                # Bearish = Buying No OR Selling Yes
                outcome_lower = outcome.lower() if outcome else ""
                is_yes = outcome_lower in ("yes", "up")
                is_no = outcome_lower in ("no", "down")
                
                if side == "BUY":
                    is_bullish = is_yes
                else:  # SELL
                    is_bullish = is_no

                # Get user info
                address = trade.get("proxyWallet") or "Unknown"
                name = trade.get("name") or trade.get("pseudonym") or ""
                
                whale_trades.append({
                    "trade_id": trade.get("transactionHash", "")[:16] if trade.get("transactionHash") else "",
                    "address": address,
                    "name": name if name else None,
                    "side": side,
                    "outcome": outcome,
                    "is_bullish": is_bullish,
                    "size": round(size, 2),
                    "price": round(price, 4),
                    "volume": round(volume, 2),
                    "timestamp": trade_time.isoformat() + "Z"
                })

            except Exception as e:
                logger.debug(f"Error processing trade: {e}")
                continue

        # Sort by timestamp (newest first)
        whale_trades.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return whale_trades[:50]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_market_trades: {e}")
        return []


@router.get("/{market_id}/holders")
async def get_market_holders(
    market_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get top holders for a market with PnL and ROI data.
    """
    # Get market
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()

    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()
        
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    try:
        condition_id = market.id
        market_slug = market.slug
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Fetch Holders
            response = await client.get(
                "https://data-api.polymarket.com/holders",
                params={"market": condition_id}
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch holders: {response.status_code}")
                return {"yes_holders": [], "no_holders": []}
                
            data = response.json()
            
            # Extract unique addresses to fetch specific stats
            # We focus on the top holders to minimize API calls
            all_holders = []
            for token_data in data:
                token_holders = token_data.get("holders", [])
                for h in token_holders:
                    h["outcomeIndex"] = token_data.get("dummy", h.get("outcomeIndex")) # preserve outcome index
                    all_holders.append(h)

            # Deduplicate by address for fetching stats, but keep references
            unique_addresses = {h["proxyWallet"] for h in all_holders if h.get("proxyWallet")}
            
            # 2. Fetch User Positions Concurrently (Limit concurrency if needed)
            # We'll fetch for ALL unique addresses found in the top lists 
            # (usually data-api returns top ~20-50 per token, so total ~100 max)
            
            async def fetch_user_stats(address):
                try:
                    r = await client.get(
                        "https://data-api.polymarket.com/positions",
                        params={"user": address, "limit": "500"} # fetch enough positions
                    )
                    if r.status_code == 200:
                        return address, r.json()
                except Exception:
                    pass
                return address, []

            # Batch requests to avoid rate limits? 
            # Polymarket is usually lenient, but let's be safe with max 20 parallel at a time if list is huge?
            # For now, asyncio.gather all should be fine for < 50 addrs.
            stats_tasks = [fetch_user_stats(addr) for addr in unique_addresses]
            user_positions_results = await asyncio.gather(*stats_tasks)
            
            # Map address -> positions
            user_positions_map = {addr: pos for addr, pos in user_positions_results if pos is not None}
            
            yes_holders = []
            no_holders = []
            
            for token_data in data:
                token_holders = token_data.get("holders", [])
                
                # Check outcome index from the *token* context if simple holder logic fails
                # Actually data structure is List[TokenHolderInfo], where each item has holders list
                # We need to know which token corresponds to YES/NO.
                # Usually we rely on outcomeIndex inside holder object or order.
                
                for holder in token_holders:
                    address = holder.get("proxyWallet")
                    if not address:
                        continue
                        
                    positions = user_positions_map.get(address, [])
                    
                    # Calculate Stats
                    market_pnl = 0.0
                    market_roi = 0.0
                    global_pnl = 0.0
                    total_cost_basis = 0.0
                    
                    # Market specific PnL/ROI
                    # Find position matching this market by conditionId (market.id = position.conditionId)
                    target_pos = next((p for p in positions if p.get("conditionId") == condition_id), None)
                    if target_pos:
                        market_pnl = float(target_pos.get("cashPnl") or 0)
                        # percentPnl is already a percentage (e.g., -51.109 for -51.109%)
                        market_roi = float(target_pos.get("percentPnl") or 0)
                    
                    # Global Stats
                    for p in positions:
                        # PnL
                        p_pnl = float(p.get("cashPnl") or 0)
                        global_pnl += p_pnl
                        
                        # Use initialValue directly from API for accurate cost basis
                        initial_val = float(p.get("initialValue") or 0)
                        if initial_val > 0:
                            total_cost_basis += initial_val
                            
                    global_roi = (global_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
                    
                    holder_info = {
                        "address": address,
                        "name": holder.get("name") or holder.get("pseudonym") or "Unknown",
                        "amount": float(holder.get("amount", 0)),
                        "img": holder.get("profileImage"),
                        "market_pnl": market_pnl,
                        "market_roi": market_roi,
                        "global_pnl": global_pnl,
                        "global_roi": global_roi
                    }
                    
                    if holder.get("outcomeIndex") == 0:
                        yes_holders.append(holder_info)
                    else:
                        no_holders.append(holder_info)

            # Sort by amount desc
            yes_holders.sort(key=lambda x: x["amount"], reverse=True)
            no_holders.sort(key=lambda x: x["amount"], reverse=True)
            
            return {
                "yes_holders": yes_holders[:20],
                "no_holders": no_holders[:20]
            }

    except Exception as e:
        logger.error(f"Error fetching holders enriched info: {e}")
        return {"yes_holders": [], "no_holders": []}

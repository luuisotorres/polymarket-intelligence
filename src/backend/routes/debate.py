"""Debate Floor API routes for AI-powered market analysis."""

import json
import logging
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import httpx

from src.backend.database import get_db
from src.backend.models import Market
from src.backend.agents.debate import build_debate_graph, DebateState, AgentConfig
from src.backend.routes.markets import fetch_price_history_from_clob
from src.backend.polymarket.client import polymarket_client
from langchain_core.messages import BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debate", tags=["debate"])


class AgentConfigRequest(BaseModel):
    """Request model for agent configuration."""
    statistics_expert: bool = Field(default=True, description="Enable Statistics Expert agent")
    generalist_expert: bool = Field(default=True, description="Enable Generalist Expert (News Analyst) agent")
    devils_advocate: bool = Field(default=True, description="Enable Devil's Advocate agent")
    crypto_macro_analyst: bool = Field(default=True, description="Enable Crypto/Macro Analyst agent")
    time_decay_analyst: bool = Field(default=True, description="Enable Time Decay & Resolution Analyst agent")
    top_traders_analyst: bool = Field(default=True, description="Enable Top Traders Analyst agent")


class DebateRequest(BaseModel):
    """Request model for initiating a debate."""
    agents: Optional[AgentConfigRequest] = Field(
        default=None,
        description="Configuration for which agents to include. If not provided, all agents are enabled."
    )


class DebateResponse(BaseModel):
    """Response model for debate results."""
    market_id: str
    messages: List[Dict[str, str]]
    verdict: str
    enabled_agents: List[str]


def _parse_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_trade_value(trade: dict, size: float, price: float) -> float:
    for key in ("value", "tradeValue", "totalValue", "total_value", "usdValue", "usd_value", "notional"):
        raw = trade.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return size * price


def _extract_position_pnl(position: dict) -> float:
    for key in (
        "totalPnl",
        "total_pnl",
        "profitLoss",
        "profit_loss",
        "pnl",
        "profit",
        "cashPnl",
    ):
        raw = position.get(key)
        if raw is None:
            continue
        return _parse_float(raw)

    realized = _parse_float(position.get("realizedPnl") or position.get("realized_pnl") or 0)
    unrealized = _parse_float(position.get("unrealizedPnl") or position.get("unrealized_pnl") or 0)
    if realized or unrealized:
        return realized + unrealized

    return 0.0


def _extract_position_value(position: dict) -> float:
    for key in (
        "currentValue",
        "current_value",
        "value",
        "positionValue",
        "position_value",
        "markValue",
        "mark_value",
        "notionalValue",
        "notional_value",
        "totalValue",
        "total_value",
    ):
        raw = position.get(key)
        if raw is None:
            continue
        parsed = _parse_float(raw)
        if parsed > 0:
            return parsed
    initial_val = _parse_float(position.get("initialValue") or 0)
    cash_pnl = _parse_float(position.get("cashPnl") or 0)
    fallback = initial_val + cash_pnl
    return fallback if fallback > 0 else 0.0


def _compute_global_stats(positions: list[dict], closed_positions: list[dict] | None = None) -> tuple[float, float, float]:
    global_pnl = 0.0
    total_cost_basis = 0.0
    total_balance = 0.0

    for position in positions:
        if not isinstance(position, dict):
            continue
        global_pnl += _extract_position_pnl(position)

        initial_val = _parse_float(position.get("initialValue") or 0)
        if initial_val > 0:
            total_cost_basis += initial_val

        total_balance += _extract_position_value(position)

    if closed_positions:
        for position in closed_positions:
            if not isinstance(position, dict):
                continue
            global_pnl += _extract_position_pnl(position)

            total_bought = _parse_float(position.get("totalBought") or 0)
            if total_bought > 0:
                total_cost_basis += total_bought

    if total_balance <= 0 and total_cost_basis > 0:
        total_balance = max(0.0, total_cost_basis + global_pnl)

    global_roi = (global_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
    return global_pnl, global_roi, total_balance


async def _fetch_top_traders(market: Market, days: int = 7, limit: int = 500, top_n: int = 5) -> list[dict]:
    """
    Fetch top actors for the Debate Floor.

    Preference order:
    1) Top holders (current positions) for the market (most aligned with "who matters now")
    2) Fallback to top traders by recent traded volume (if holders unavailable)
    """
    # 1) Try top holders first (these are guaranteed to be positioned on this market)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://data-api.polymarket.com/holders",
                params={"market": market.id},
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    holders: list[dict] = []
                    for token_data in data:
                        if not isinstance(token_data, dict):
                            continue
                        token_holders = token_data.get("holders", [])
                        if not isinstance(token_holders, list):
                            continue
                        for holder in token_holders:
                            if not isinstance(holder, dict):
                                continue
                            address = holder.get("proxyWallet")
                            if not address:
                                continue
                            holders.append(
                                {
                                    "address": address,
                                    "name": holder.get("name") or holder.get("pseudonym"),
                                    "profile_image": holder.get("profileImage"),
                                    "position_amount": _parse_float(holder.get("amount") or 0),
                                    "outcome_index": holder.get("outcomeIndex"),
                                    "source": "holders",
                                }
                            )

                    if holders:
                        holders.sort(key=lambda x: x.get("position_amount", 0), reverse=True)
                        top_holders = holders[: max(1, top_n)]

                        # Enrich with global stats + portfolio value
                        async with httpx.AsyncClient(timeout=15.0) as client2:
                            semaphore = asyncio.Semaphore(8)

                            async def enrich(address: str):
                                async with semaphore:
                                    positions = []
                                    closed_positions = []
                                    value_total = 0.0

                                    try:
                                        r = await client2.get(
                                            "https://data-api.polymarket.com/positions",
                                            params={"user": address, "limit": "500"},
                                        )
                                        if r.status_code == 200:
                                            positions = r.json()
                                    except Exception:
                                        positions = []

                                    try:
                                        r = await client2.get(
                                            "https://data-api.polymarket.com/closed-positions",
                                            params={"user": address, "limit": "500"},
                                        )
                                        if r.status_code == 200:
                                            closed_positions = r.json()
                                    except Exception:
                                        closed_positions = []

                                    try:
                                        r = await client2.get(
                                            "https://data-api.polymarket.com/value",
                                            params={"user": address},
                                        )
                                        if r.status_code == 200:
                                            payload = r.json()
                                            if isinstance(payload, list) and payload:
                                                value_total = _parse_float(payload[0].get("value") or 0)
                                    except Exception:
                                        value_total = 0.0

                                positions = positions if isinstance(positions, list) else []
                                closed_positions = closed_positions if isinstance(closed_positions, list) else []
                                global_pnl, global_roi, total_balance = _compute_global_stats(positions, closed_positions)
                                if value_total > 0:
                                    total_balance = value_total
                                return address, global_pnl, global_roi, total_balance

                            stats_results = await asyncio.gather(*[enrich(h["address"]) for h in top_holders])
                            stats_map = {addr: (pnl, roi, bal) for addr, pnl, roi, bal in stats_results}

                        for holder in top_holders:
                            pnl, roi, bal = stats_map.get(holder["address"], (0.0, 0.0, 0.0))
                            holder["global_pnl"] = pnl
                            holder["global_roi"] = roi
                            holder["total_balance"] = bal

                        return top_holders
    except Exception as e:
        logger.debug(f"Top holders fetch failed (falling back to trades): {e}")

    identifiers = []
    if market.slug:
        identifiers.append(market.slug)
    if market.id and market.id not in identifiers:
        identifiers.append(market.id)

    trades: list[dict] = []
    for identifier in identifiers:
        fetched = await polymarket_client.fetch_trades(identifier, limit=limit)
        if fetched:
            trades = fetched
            break

    if not trades:
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    market_keys = {
        str(market.slug).strip().lower() if market.slug else None,
        str(market.id).strip().lower() if market.id else None,
    }
    market_keys.discard(None)

    def trade_matches_market(trade: dict) -> bool:
        trade_fields = [
            trade.get("slug"),
            trade.get("marketSlug"),
            trade.get("market_slug"),
            trade.get("market"),
            trade.get("marketId"),
            trade.get("conditionId"),
            trade.get("condition_id"),
        ]
        normalized = [
            str(value).strip().lower()
            for value in trade_fields
            if value is not None and str(value).strip() != ""
        ]
        if not normalized:
            return False
        return any(value in market_keys for value in normalized)
    aggregates: dict[str, dict[str, Any]] = {}

    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if not trade_matches_market(trade):
            continue

        ts_val = trade.get("timestamp")
        if not ts_val:
            continue
        trade_time = None
        if isinstance(ts_val, (int, float)):
            ts_int = int(ts_val)
            if ts_int > 10**12:
                ts_int = ts_int // 1000
            trade_time = datetime.utcfromtimestamp(ts_int)
        else:
            try:
                trade_time = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
            except ValueError:
                continue

        if trade_time < cutoff:
            continue

        side = str(trade.get("side", "")).upper()
        if side not in ("BUY", "SELL"):
            continue

        outcome = str(trade.get("outcome", ""))
        outcome_lower = outcome.lower() if outcome else ""
        is_yes = outcome_lower in ("yes", "up")
        is_no = outcome_lower in ("no", "down")
        is_bullish = (side == "BUY" and is_yes) or (side == "SELL" and is_no)

        try:
            size = float(trade.get("size", 0))
            price = float(trade.get("price", 0))
        except (TypeError, ValueError):
            continue

        volume = _parse_trade_value(trade, size, price)
        if volume <= 0:
            continue

        address = trade.get("proxyWallet") or trade.get("wallet") or trade.get("address")
        if not address:
            continue

        name = trade.get("name") or trade.get("pseudonym")
        agg = aggregates.setdefault(address, {
            "address": address,
            "name": name,
            "total_volume": 0.0,
            "trade_count": 0,
            "bullish_volume": 0.0,
            "bearish_volume": 0.0,
            "last_trade_at": trade_time.isoformat() + "Z",
        })

        agg["total_volume"] += volume
        agg["trade_count"] += 1
        if is_bullish:
            agg["bullish_volume"] += volume
        else:
            agg["bearish_volume"] += volume

        if trade_time.isoformat() + "Z" > agg["last_trade_at"]:
            agg["last_trade_at"] = trade_time.isoformat() + "Z"

        if not agg.get("name") and name:
            agg["name"] = name

    if not aggregates:
        return []

    traders = list(aggregates.values())
    traders.sort(key=lambda x: x.get("total_volume", 0), reverse=True)
    top_traders = traders[:top_n]

    async with httpx.AsyncClient(timeout=15.0) as client:
        semaphore = asyncio.Semaphore(8)

        async def fetch_user_stats(address: str):
            async with semaphore:
                positions = []
                closed_positions = []
                value_total = 0.0

                try:
                    response = await client.get(
                        "https://data-api.polymarket.com/positions",
                        params={"user": address, "limit": "500"},
                    )
                    if response.status_code == 200:
                        positions = response.json()
                except Exception:
                    positions = []

                try:
                    response = await client.get(
                        "https://data-api.polymarket.com/closed-positions",
                        params={"user": address, "limit": "500"},
                    )
                    if response.status_code == 200:
                        closed_positions = response.json()
                except Exception:
                    closed_positions = []

                try:
                    response = await client.get(
                        "https://data-api.polymarket.com/value",
                        params={"user": address},
                    )
                    if response.status_code == 200:
                        payload = response.json()
                        if isinstance(payload, list) and payload:
                            value_total = _parse_float(payload[0].get("value") or 0)
                except Exception:
                    value_total = 0.0

            positions = positions if isinstance(positions, list) else []
            closed_positions = closed_positions if isinstance(closed_positions, list) else []
            global_pnl, global_roi, total_balance = _compute_global_stats(positions, closed_positions)
            if value_total > 0:
                total_balance = value_total
            return address, global_pnl, global_roi, total_balance

        stats_results = await asyncio.gather(*[fetch_user_stats(t["address"]) for t in top_traders])
        stats_map = {address: (pnl, roi, balance) for address, pnl, roi, balance in stats_results}

    for trader in top_traders:
        bullish = trader.get("bullish_volume", 0.0)
        bearish = trader.get("bearish_volume", 0.0)
        if bullish > bearish * 1.1:
            bias = "bullish"
        elif bearish > bullish * 1.1:
            bias = "bearish"
        else:
            bias = "mixed"
        trader["bias"] = bias

        pnl, roi, balance = stats_map.get(trader["address"], (0.0, 0.0, 0.0))
        trader["global_pnl"] = pnl
        trader["global_roi"] = roi
        trader["total_balance"] = balance

    return top_traders


@router.post("/{market_id}", response_model=DebateResponse)
async def initiate_debate(
    market_id: str,
    request: Optional[DebateRequest] = None,
    db: AsyncSession = Depends(get_db)
) -> DebateResponse:
    """
    Initiates an AI debate for a specific market.
    
    Users can optionally specify which agents to include in the debate
    to reduce token usage and processing time.
    """
    # 1. Fetch Market Data
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    
    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()
        
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # 2. Fetch Price History for Statistics Expert
    price_history_24h: List[float] = []
    price_history_7d: List[float] = []
    
    if market.clob_token_ids:
        try:
            token_ids = json.loads(market.clob_token_ids)
            if token_ids and len(token_ids) > 0:
                yes_token_id = token_ids[0]
                
                # Fetch 24h history (15-min fidelity)
                history_24h = await fetch_price_history_from_clob(yes_token_id, "1d", 15)
                if history_24h:
                    price_history_24h = [h["p"] * 100 for h in history_24h]  # Convert to 0-100 scale
                
                # Fetch 7d history (1-hour fidelity)
                history_7d = await fetch_price_history_from_clob(yes_token_id, "7d", 60)
                if history_7d:
                    price_history_7d = [h["p"] * 100 for h in history_7d]  # Convert to 0-100 scale
                    
                logger.info(f"Fetched price history: 24h={len(price_history_24h)} points, 7d={len(price_history_7d)} points")
        except Exception as e:
            logger.warning(f"Failed to fetch price history for debate: {e}")
    
    # 3. Prepare Data for Agents
    market_data = {
        "title": market.title,
        "price": market.yes_percentage,
        "volume_24h": market.volume_24h,
        "volume_7d": market.volume_7d,
        "liquidity": market.liquidity,
        "end_date": str(market.end_date)
    }

    top_traders = []
    try:
        top_traders = await _fetch_top_traders(market)
    except Exception as e:
        logger.warning(f"Failed to fetch top traders for debate: {e}")
    
    initial_state: DebateState = {
        "messages": [],
        "market_data": market_data,
        "market_question": market.title,
        "verdict": "",
        "price_history_24h": price_history_24h,
        "price_history_7d": price_history_7d,
        "top_traders": top_traders,
    }
    
    # 3. Build Agent Config from Request
    agent_config: AgentConfig = {
        "statistics_expert": True,
        "generalist_expert": True,
        "devils_advocate": True,
        "crypto_macro_analyst": True,
        "time_decay_analyst": True,
        "top_traders_analyst": True,
    }
    
    if request and request.agents:
        agent_config = {
            "statistics_expert": request.agents.statistics_expert,
            "generalist_expert": request.agents.generalist_expert,
            "devils_advocate": request.agents.devils_advocate,
            "crypto_macro_analyst": request.agents.crypto_macro_analyst,
            "time_decay_analyst": request.agents.time_decay_analyst,
            "top_traders_analyst": request.agents.top_traders_analyst,
        }
    
    # Track enabled agents for response
    enabled_agents = [k for k, v in agent_config.items() if v]
    
    # 4. Build Dynamic Graph and Run
    try:
        debate_graph = build_debate_graph(agent_config)
        final_state = await debate_graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debate failed: {str(e)}")
    
    # 5. Format Output
    formatted_messages = []
    for msg in final_state["messages"]:
        if isinstance(msg, HumanMessage) and msg.name:
            formatted_messages.append({
                "agent": msg.name,
                "content": str(msg.content)
            })
            
    return DebateResponse(
        market_id=market_id,
        messages=formatted_messages,
        verdict=final_state.get("verdict", "No verdict reached."),
        enabled_agents=enabled_agents
    )

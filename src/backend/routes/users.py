"""
User analytics routes.

Provides endpoints for fetching Polymarket user activity, PnL, and position analytics.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class UserProfile(BaseModel):
    address: str
    username: str | None = None
    display_name: str | None = None
    profile_image: str | None = None
    resolved: bool = True


class UserPosition(BaseModel):
    market_id: str | None = None
    title: str | None = None
    slug: str | None = None
    outcome: str | None = None
    shares: float = 0.0
    avg_price: float = 0.0
    current_value: float = 0.0
    initial_value: float = 0.0
    total_bought: float = 0.0
    cash_pnl: float = 0.0
    percent_pnl: float = 0.0
    status: str | None = None
    last_updated: str | None = None
    is_open: bool = True


class UserMetrics(BaseModel):
    total_pnl: float = 0.0
    total_roi: float = 0.0
    realized_pnl: float = 0.0
    realized_roi: float = 0.0
    realized_cost_basis: float = 0.0
    volume_traded: float = 0.0
    unrealized_pnl: float = 0.0
    total_initial_value: float = 0.0
    total_current_value: float = 0.0
    open_positions: int = 0
    closed_positions: int = 0
    win_rate: float = 0.0
    avg_roi: float = 0.0
    avg_position_size: float = 0.0
    largest_position_value: float = 0.0
    best_position_pnl: float = 0.0
    worst_position_pnl: float = 0.0
    yes_positions: int = 0
    no_positions: int = 0
    other_positions: int = 0
    last_activity_at: str | None = None


class UserAnalyticsResponse(BaseModel):
    user: UserProfile
    metrics: UserMetrics
    open_positions: list[UserPosition]
    closed_positions: list[UserPosition]
    biggest_wins: list[UserPosition]
    biggest_losses: list[UserPosition]
    positions_total: int


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(value))
        except Exception:
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _is_wallet_address(identifier: str) -> bool:
    return bool(WALLET_RE.match(identifier))


def _extract_user_from_candidate(candidate: dict, requested_username: str | None) -> UserProfile | None:
    if not isinstance(candidate, dict):
        return None
    if isinstance(candidate.get("profile"), dict):
        candidate = candidate.get("profile")
    if isinstance(candidate.get("user"), dict):
        candidate = candidate.get("user")

    username = (
        candidate.get("username")
        or candidate.get("name")
        or candidate.get("pseudonym")
        or candidate.get("profileUsername")
        or candidate.get("handle")
    )
    address = (
        candidate.get("address")
        or candidate.get("walletAddress")
        or candidate.get("wallet_address")
        or candidate.get("proxyWallet")
        or candidate.get("wallet")
        or candidate.get("id")
    )
    if not address:
        return None

    if requested_username and username:
        if str(username).lower() != str(requested_username).lower():
            # Keep it, but mark as not strictly resolved by username match
            pass

    display_name = candidate.get("displayName") or candidate.get("name") or username
    profile_image = (
        candidate.get("profileImage")
        or candidate.get("avatar")
        or candidate.get("image")
        or candidate.get("picture")
    )

    return UserProfile(
        address=str(address),
        username=str(username) if username else None,
        display_name=str(display_name) if display_name else None,
        profile_image=str(profile_image) if profile_image else None,
        resolved=True,
    )


async def _resolve_user(identifier: str) -> UserProfile | None:
    if _is_wallet_address(identifier):
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{GAMMA_API_BASE}/public-profile", params={"address": identifier}
                )
                if response.status_code == 200:
                    data = response.json()
                    profile = _extract_user_from_candidate(data, None)
                    if profile:
                        return profile
            except Exception as e:
                logger.debug(f"Failed to fetch public profile for wallet: {e}")
        return UserProfile(address=identifier, resolved=True)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Some older accounts resolve only via public-profile
        try:
            response = await client.get(
                f"{GAMMA_API_BASE}/public-profile", params={"username": identifier}
            )
            if response.status_code == 200:
                data = response.json()
                profile = _extract_user_from_candidate(data, identifier)
                if profile:
                    return profile
        except Exception as e:
            logger.debug(f"Failed to resolve user via public-profile: {e}")

        for params in (
            {"q": identifier, "search_profiles": "true", "limit_per_type": 10},
            {"q": identifier},
        ):
            try:
                response = await client.get(f"{GAMMA_API_BASE}/public-search", params=params)
                if response.status_code != 200:
                    continue
                data = response.json()

                candidates: list[dict] = []
                if isinstance(data, dict):
                    for key in ("profiles", "users", "results", "data", "items"):
                        if isinstance(data.get(key), list):
                            candidates = data.get(key, [])
                            break

                if not candidates:
                    continue

                # Prefer exact username match if possible
                exact_match = None
                for candidate in candidates:
                    username = (
                        candidate.get("username")
                        or candidate.get("name")
                        or candidate.get("pseudonym")
                        or candidate.get("profileUsername")
                    )
                    if username and str(username).lower() == identifier.lower():
                        exact_match = candidate
                        break

                selected = exact_match or candidates[0]
                profile = _extract_user_from_candidate(selected, identifier)
                if profile:
                    return profile
            except Exception as e:
                logger.debug(f"Failed to resolve user with params {params}: {e}")
                continue

    return None


async def _fetch_positions(user_identifier: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{DATA_API_BASE}/positions",
                params={"user": user_identifier, "limit": str(limit)},
            )
            if response.status_code != 200:
                logger.warning(f"Positions API status {response.status_code}: {response.text}")
                return []
            data = response.json()
            if isinstance(data, dict):
                for key in ("positions", "results", "data", "items"):
                    if isinstance(data.get(key), list):
                        return data.get(key, [])
                return []
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []


async def _fetch_closed_positions(user_identifier: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{DATA_API_BASE}/closed-positions",
                params={"user": user_identifier, "limit": str(limit)},
            )
            if response.status_code != 200:
                logger.warning(f"Closed positions API status {response.status_code}: {response.text}")
                return []
            data = response.json()
            if isinstance(data, dict):
                for key in ("positions", "results", "data", "items"):
                    if isinstance(data.get(key), list):
                        return data.get(key, [])
                return []
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Failed to fetch closed positions: {e}")
            return []


def _extract_list_from_response(data: object) -> list[dict]:
    if isinstance(data, dict):
        for key in ("positions", "results", "data", "items"):
            if isinstance(data.get(key), list):
                return data.get(key, [])
    if isinstance(data, list):
        return data
    return []


def _extract_next_cursor(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("next", "nextCursor", "next_cursor", "cursor", "nextToken"):
        value = data.get(key)
        if value:
            return str(value)
    return None


def _position_key_from_raw(item: dict) -> str | None:
    if not isinstance(item, dict):
        return None
    market_id = item.get("conditionId") or item.get("marketId") or item.get("id") or item.get("slug")
    outcome = item.get("outcome") or item.get("outcomeIndex") or item.get("asset")
    if market_id is None and outcome is None:
        return None
    return f"{market_id}:{outcome}"


async def _fetch_all_positions(
    endpoint: str,
    user_identifier: str,
    limit: int,
    max_pages: int = 200,
) -> list[dict]:
    """
    Best-effort pagination for Data API. Tries cursor if present; otherwise uses offset.
    Stops when an empty page is returned or page limit is reached.
    """
    collected: list[dict] = []
    seen_ids: set[str] = set()
    cursor: str | None = None
    offset = 0
    page = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        while page < max_pages:
            params = {"user": user_identifier, "limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            else:
                params["offset"] = str(offset)

            try:
                response = await client.get(f"{DATA_API_BASE}/{endpoint}", params=params)
                if response.status_code != 200:
                    logger.warning(f"{endpoint} API status {response.status_code}: {response.text}")
                    break
                data = response.json()
                batch = _extract_list_from_response(data)
                if not batch:
                    break

                new_items = 0
                for item in batch:
                    if not isinstance(item, dict):
                        continue
                    key = _position_key_from_raw(item)
                    if key and key in seen_ids:
                        continue
                    if key:
                        seen_ids.add(key)
                    collected.append(item)
                    new_items += 1

                if new_items == 0:
                    break

                next_cursor = _extract_next_cursor(data)
                if next_cursor and next_cursor != cursor:
                    cursor = next_cursor
                else:
                    cursor = None
                    offset += len(batch)

                page += 1
            except Exception as e:
                logger.error(f"Failed to fetch {endpoint} page: {e}")
                break

    return collected


def _normalize_position(position: dict, force_is_open: bool | None = None) -> UserPosition | None:
    if not isinstance(position, dict):
        return None

    market_id = (
        position.get("conditionId")
        or position.get("condition_id")
        or position.get("marketId")
        or position.get("market_id")
        or position.get("id")
    )
    title = (
        position.get("title")
        or position.get("question")
        or position.get("marketTitle")
        or position.get("market")
    )
    slug = position.get("slug") or position.get("marketSlug") or position.get("market_slug")
    outcome = position.get("outcome") or position.get("side") or position.get("positionSide")

    shares = _safe_float(
        position.get("size")
        or position.get("shares")
        or position.get("amount")
    )
    avg_price = _safe_float(
        position.get("avgPrice")
        or position.get("avg_price")
        or position.get("averagePrice")
    )
    current_value = _safe_float(position.get("currentValue") or position.get("current_value"))
    initial_value = _safe_float(
        position.get("initialValue")
        or position.get("initial_value")
        or position.get("costBasis")
    )
    total_bought = _safe_float(position.get("totalBought") or position.get("total_bought"))
    if initial_value == 0:
        initial_value = total_bought
    cash_pnl = _safe_float(
        position.get("cashPnl")
        or position.get("cash_pnl")
        or position.get("realizedPnl")
        or position.get("realized_pnl")
    )
    percent_pnl = _safe_float(position.get("percentPnl") or position.get("percent_pnl"))
    if percent_pnl == 0 and cash_pnl != 0:
        if total_bought > 0:
            percent_pnl = (cash_pnl / total_bought) * 100
        elif initial_value > 0:
            percent_pnl = (cash_pnl / initial_value) * 100

    status = (
        position.get("status")
        or position.get("state")
        or position.get("positionStatus")
        or position.get("marketStatus")
    )

    last_updated = (
        position.get("updatedAt")
        or position.get("lastUpdated")
        or position.get("timestamp")
        or position.get("createdAt")
    )

    status_value = str(status).lower() if status else ""
    is_open = None
    if status_value in {"open", "active", "live"}:
        is_open = True
    elif status_value in {"closed", "settled", "resolved", "expired", "finalized"}:
        is_open = False
    elif position.get("isClosed") is True or position.get("closed") is True:
        is_open = False
    elif position.get("isResolved") is True or position.get("resolved") is True:
        is_open = False

    if is_open is None:
        is_open = shares > 0 or current_value > 0
    if force_is_open is not None:
        is_open = force_is_open

    parsed_dt = _parse_datetime(last_updated)

    return UserPosition(
        market_id=str(market_id) if market_id else None,
        title=str(title) if title else None,
        slug=str(slug) if slug else None,
        outcome=str(outcome) if outcome else None,
        shares=shares,
        avg_price=avg_price,
        current_value=current_value,
        initial_value=initial_value,
        total_bought=total_bought,
        cash_pnl=cash_pnl,
        percent_pnl=percent_pnl,
        status=str(status) if status else None,
        last_updated=parsed_dt.isoformat() if parsed_dt else None,
        is_open=bool(is_open),
    )


def _position_key(position: UserPosition) -> str | None:
    market_id = position.market_id or position.slug
    outcome = position.outcome
    if not market_id and not outcome:
        return None
    return f"{market_id}:{outcome}"


def _compute_metrics(open_positions: list[UserPosition], closed_positions: list[UserPosition]) -> UserMetrics:
    positions = [*open_positions, *closed_positions]
    if not positions:
        return UserMetrics()

    unrealized_pnl = sum(p.cash_pnl for p in open_positions)
    realized_pnl = sum(p.cash_pnl for p in closed_positions)

    def position_cost(p: UserPosition) -> float:
        return p.total_bought if p.total_bought > 0 else p.initial_value

    realized_cost_basis = sum(position_cost(p) for p in closed_positions)
    volume_traded = sum(position_cost(p) for p in positions)
    total_initial_value = volume_traded
    total_current_value = sum(p.current_value for p in open_positions)
    total_pnl = unrealized_pnl + realized_pnl

    win_positions = [p for p in positions if p.cash_pnl > 0]

    total_roi = (total_pnl / volume_traded * 100) if volume_traded > 0 else 0.0
    realized_roi = (realized_pnl / realized_cost_basis * 100) if realized_cost_basis > 0 else 0.0
    avg_roi = sum(p.percent_pnl for p in positions) / len(positions) if positions else 0.0
    avg_position_size = total_initial_value / len(positions) if positions else 0.0
    largest_position_value = max((p.current_value for p in positions), default=0.0)

    best_position = max(positions, key=lambda p: p.cash_pnl, default=None)
    worst_position = min(positions, key=lambda p: p.cash_pnl, default=None)

    yes_positions = 0
    no_positions = 0
    other_positions = 0
    for p in positions:
        if not p.outcome:
            other_positions += 1
            continue
        outcome = p.outcome.lower()
        if outcome in {"yes", "up"}:
            yes_positions += 1
        elif outcome in {"no", "down"}:
            no_positions += 1
        else:
            other_positions += 1

    last_activity = None
    for p in positions:
        dt = _parse_datetime(p.last_updated)
        if dt and (last_activity is None or dt > last_activity):
            last_activity = dt

    win_rate = (len(win_positions) / len(positions) * 100) if positions else 0.0

    return UserMetrics(
        total_pnl=round(total_pnl, 2),
        total_roi=round(total_roi, 2),
        realized_pnl=round(realized_pnl, 2),
        realized_roi=round(realized_roi, 2),
        realized_cost_basis=round(realized_cost_basis, 2),
        volume_traded=round(volume_traded, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        total_initial_value=round(total_initial_value, 2),
        total_current_value=round(total_current_value, 2),
        open_positions=len(open_positions),
        closed_positions=len(closed_positions),
        win_rate=round(win_rate, 2),
        avg_roi=round(avg_roi, 2),
        avg_position_size=round(avg_position_size, 2),
        largest_position_value=round(largest_position_value, 2),
        best_position_pnl=round(best_position.cash_pnl, 2) if best_position else 0.0,
        worst_position_pnl=round(worst_position.cash_pnl, 2) if worst_position else 0.0,
        yes_positions=yes_positions,
        no_positions=no_positions,
        other_positions=other_positions,
        last_activity_at=last_activity.isoformat() if last_activity else None,
    )


@router.get("/analytics", response_model=UserAnalyticsResponse)
async def get_user_analytics(
    query: str = Query(..., min_length=2),
    limit: int = Query(500, ge=1, le=2000),
    list_limit: int = Query(50, ge=1, le=200),
) -> UserAnalyticsResponse:
    """
    Analyze a Polymarket user by username or wallet address.

    Returns user metrics, open/closed positions, and top wins/losses.
    """
    identifier = query.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    profile = await _resolve_user(identifier)

    # If we couldn't resolve a username, try using the identifier directly
    user_identifier = profile.address if profile else identifier

    positions_raw = await _fetch_all_positions("positions", user_identifier, limit)
    closed_positions_raw = await _fetch_all_positions("closed-positions", user_identifier, limit)

    if not positions_raw and not closed_positions_raw and not profile:
        raise HTTPException(status_code=404, detail="User not found")

    open_positions_raw: list[UserPosition] = []
    closed_positions_raw_norm: list[UserPosition] = []

    for pos in positions_raw:
        normalized = _normalize_position(pos, force_is_open=True)
        if normalized:
            open_positions_raw.append(normalized)
    for pos in closed_positions_raw:
        normalized = _normalize_position(pos, force_is_open=False)
        if normalized:
            closed_positions_raw_norm.append(normalized)

    closed_keys = {k for p in closed_positions_raw_norm if (k := _position_key(p))}
    open_positions = [p for p in open_positions_raw if _position_key(p) not in closed_keys]
    closed_positions = closed_positions_raw_norm

    metrics = _compute_metrics(open_positions, closed_positions)

    normalized_positions: list[UserPosition] = [*open_positions, *closed_positions]

    biggest_wins = sorted(
        [p for p in normalized_positions if p.cash_pnl > 0],
        key=lambda p: p.cash_pnl,
        reverse=True,
    )
    biggest_losses = sorted(
        [p for p in normalized_positions if p.cash_pnl < 0],
        key=lambda p: p.cash_pnl,
    )

    if not profile:
        profile = UserProfile(address=user_identifier, resolved=False)

    return UserAnalyticsResponse(
        user=profile,
        metrics=metrics,
        open_positions=open_positions[:list_limit],
        closed_positions=closed_positions[:list_limit],
        biggest_wins=biggest_wins[: min(10, list_limit)],
        biggest_losses=biggest_losses[: min(10, list_limit)],
        positions_total=len(normalized_positions),
    )

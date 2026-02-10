from __future__ import annotations

"""
In-memory TTL cache for Polymarket user stats.

Caches global PnL, ROI, and balance data per wallet address to avoid
repeated external API calls to Polymarket's data-api. Shared across
the /trades and /holders endpoints.
"""

import time
from dataclasses import dataclass


@dataclass
class CachedUserStats:
    """Cached user statistics from Polymarket data-api."""

    global_pnl: float
    global_roi: float
    total_balance: float
    cached_at: float


class UserStatsCache:
    """In-memory TTL cache for user stats from Polymarket data-api.

    Args:
        ttl_seconds: Time-to-live for cache entries in seconds.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: dict[str, CachedUserStats] = {}
        self._ttl = ttl_seconds

    def get(self, address: str) -> CachedUserStats | None:
        """Return cached stats if present and not expired, else None."""
        entry = self._cache.get(address)
        if entry and (time.time() - entry.cached_at) < self._ttl:
            return entry
        if entry:
            del self._cache[address]
        return None

    def set(
        self, address: str, global_pnl: float, global_roi: float, total_balance: float
    ) -> None:
        """Store user stats with the current timestamp."""
        self._cache[address] = CachedUserStats(
            global_pnl=global_pnl,
            global_roi=global_roi,
            total_balance=total_balance,
            cached_at=time.time(),
        )

    def get_many(self, addresses: set[str]) -> tuple[dict[str, CachedUserStats], set[str]]:
        """Bulk lookup. Returns (cached_map, uncached_addresses)."""
        cached: dict[str, CachedUserStats] = {}
        uncached: set[str] = set()
        for addr in addresses:
            entry = self.get(addr)
            if entry:
                cached[addr] = entry
            else:
                uncached.add(addr)
        return cached, uncached

    @property
    def size(self) -> int:
        """Return the number of entries currently in the cache."""
        return len(self._cache)


# Singleton shared across endpoints
user_stats_cache = UserStatsCache(ttl_seconds=300)

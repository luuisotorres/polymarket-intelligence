"""
Background tasks for updating market data.

Uses APScheduler to run periodic updates.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import async_session_factory
from src.backend.models import AppState, Market, PriceHistory
from src.backend.polymarket.client import polymarket_client

logger = logging.getLogger(__name__)


async def update_top_markets() -> None:
    """
    Update the top 100 markets in the database and record price history.

    Fetches fresh data from Polymarket API and updates the database.
    """
    logger.info("Starting market update task...")

    try:
        # Fetch top 100 markets from Polymarket
        markets_data = await polymarket_client.get_top_markets_by_volume(limit=100)

        if not markets_data:
            logger.warning("No markets fetched from Polymarket API")
            return

        async with async_session_factory() as db:
            now = datetime.utcnow()

            # Update or create each market
            for market_data in markets_data:
                # Check if market exists
                result = await db.execute(
                    select(Market).where(Market.id == market_data["id"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing market
                    for key, value in market_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.last_updated = now
                else:
                    # Create new market
                    market = Market(**market_data)
                    db.add(market)

                # Record price history for this market
                price_point = PriceHistory(
                    market_id=market_data["id"],
                    yes_percentage=market_data.get("yes_percentage", 50.0),
                    volume=market_data.get("volume_24h", 0.0),
                    timestamp=now,
                )
                db.add(price_point)

            # Update last update timestamp
            state_result = await db.execute(
                select(AppState).where(AppState.key == "markets_last_updated")
            )
            state = state_result.scalar_one_or_none()

            if state:
                state.value = now.isoformat()
            else:
                state = AppState(
                    key="markets_last_updated",
                    value=now.isoformat(),
                )
                db.add(state)

            await db.commit()
            logger.info(f"Successfully updated {len(markets_data)} markets with price history")

    except Exception as e:
        logger.error(f"Error updating markets: {e}")
        raise


async def cleanup_old_news(days: int = 7) -> None:
    """
    Remove news articles older than the specified number of days.

    Args:
        days: Number of days to keep articles.
    """
    from src.backend.models import NewsArticle

    logger.info(f"Cleaning up news articles older than {days} days...")

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with async_session_factory() as db:
            result = await db.execute(
                delete(NewsArticle).where(NewsArticle.created_at < cutoff)
            )
            await db.commit()
            logger.info(f"Deleted {result.rowcount} old news articles")

    except Exception as e:
        logger.error(f"Error cleaning up old news: {e}")


async def cleanup_old_price_history(days: int = 30) -> None:
    """
    Remove price history older than the specified number of days.

    Args:
        days: Number of days to keep price history.
    """
    logger.info(f"Cleaning up price history older than {days} days...")

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with async_session_factory() as db:
            result = await db.execute(
                delete(PriceHistory).where(PriceHistory.timestamp < cutoff)
            )
            await db.commit()
            logger.info(f"Deleted {result.rowcount} old price history records")

    except Exception as e:
        logger.error(f"Error cleaning up price history: {e}")


def get_scheduler():
    """
    Get configured APScheduler instance.

    Returns:
        Configured AsyncIOScheduler.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = AsyncIOScheduler()

    # Update markets every 15 minutes (and record price history)
    scheduler.add_job(
        update_top_markets,
        trigger=IntervalTrigger(minutes=15),
        id="update_markets",
        name="Update top 100 markets",
        replace_existing=True,
    )

    # Clean up old news daily
    scheduler.add_job(
        cleanup_old_news,
        trigger=IntervalTrigger(hours=24),
        id="cleanup_news",
        name="Clean up old news articles",
        replace_existing=True,
    )

    # Clean up old price history weekly
    scheduler.add_job(
        cleanup_old_price_history,
        trigger=IntervalTrigger(days=7),
        id="cleanup_price_history",
        name="Clean up old price history",
        replace_existing=True,
    )

    return scheduler

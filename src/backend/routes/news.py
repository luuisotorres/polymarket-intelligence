"""
API routes for news articles.

Provides endpoints for fetching news related to markets.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import get_db
from src.backend.models import Market, NewsArticle
from src.backend.news.aggregator import news_aggregator
from src.backend.news.schemas import NewsArticleOut, NewsListResponse

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/{market_id}", response_model=NewsListResponse)
async def get_news_for_market(
    market_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> NewsListResponse:
    """
    Get news articles for a specific market.

    Args:
        market_id: The market ID or slug.
        limit: Maximum number of articles to return.

    Returns:
        List of news articles for the market.
    """
    # Find the market
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()

    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Get cached news articles
    result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.market_id == market.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )
    articles = result.scalars().all()

    # If no cached articles, fetch fresh ones
    if not articles:
        fresh_articles = await news_aggregator.fetch_news_for_market(
            market_title=market.title,
            market_id=market.id,
            limit=limit,
        )

        # Store in database
        for article_data in fresh_articles:
            # Check for duplicate by url_hash
            existing = await db.execute(
                select(NewsArticle).where(NewsArticle.url_hash == article_data["url_hash"])
            )
            if existing.scalar_one_or_none():
                continue

            article = NewsArticle(**article_data)
            db.add(article)

        await db.commit()

        # Refetch from database
        result = await db.execute(
            select(NewsArticle)
            .where(NewsArticle.market_id == market.id)
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )
        articles = result.scalars().all()

    return NewsListResponse(
        articles=[NewsArticleOut.model_validate(a) for a in articles],
        total=len(articles),
        market_id=market.id,
    )


@router.post("/{market_id}/refresh")
async def refresh_news_for_market(
    market_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Force refresh news articles for a specific market.

    Args:
        market_id: The market ID or slug.
        limit: Maximum number of articles to fetch.

    Returns:
        Summary of refreshed articles.
    """
    # Find the market
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()

    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Fetch fresh news
    fresh_articles = await news_aggregator.fetch_news_for_market(
        market_title=market.title,
        market_id=market.id,
        limit=limit,
    )

    new_count = 0
    for article_data in fresh_articles:
        existing = await db.execute(
            select(NewsArticle).where(NewsArticle.url_hash == article_data["url_hash"])
        )
        if existing.scalar_one_or_none():
            continue

        article = NewsArticle(**article_data)
        db.add(article)
        new_count += 1

    await db.commit()

    return {
        "market_id": market.id,
        "fetched": len(fresh_articles),
        "new_articles": new_count,
    }

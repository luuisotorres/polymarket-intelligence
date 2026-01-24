"""
News aggregator for fetching and filtering news articles.

Uses NewsAPI to fetch articles related to market topics.
"""

import hashlib
import logging
import re
from datetime import datetime

import httpx

from src.backend.config import settings
from src.backend.news.schemas import NewsArticleIn

logger = logging.getLogger(__name__)

NEWS_API_BASE = "https://newsapi.org/v2"
EVERYTHING_ENDPOINT = f"{NEWS_API_BASE}/everything"
TOP_HEADLINES_ENDPOINT = f"{NEWS_API_BASE}/top-headlines"


def extract_keywords(title: str) -> str:
    """
    Extract a focused search query from a market title.

    Uses AND logic for better relevance instead of broad OR matching.

    Args:
        title: The market title/question.

    Returns:
        Optimized search query string.
    """
    # Common stopwords to filter out (Expanded list)
    stopwords = {
        "will", "the", "be", "to", "of", "and", "a", "in", "that", "is",
        "for", "on", "with", "as", "at", "by", "this", "from", "or", "an",
        "are", "was", "were", "been", "being", "have", "has", "had", "do",
        "does", "did", "but", "if", "then", "than", "so", "what", "when",
        "where", "who", "which", "why", "how", "yes", "no", "win", "happen",
        "before", "after", "during", "into", "through", "about", "more",
        "any", "some", "most", "over", "under", "again", "further", "once",
        "2024", "2025", "2026", "end", "next", "first", "second", "third",
        "reach", "hit", "price", "market", "polymarket", "bet", "predict",
        "above", "below", "between", "approve", "confirm", "announce", "launch",
    }

    # Clean the title - remove punctuation except hyphens
    title_clean = re.sub(r"[^\w\s\-]", " ", title)
    words = title_clean.split()

    # Extract meaningful keywords (longer words, not stopwords)
    keywords = []
    for word in words:
        word_lower = word.lower()
        # Keep words that are significant
        if (
            word_lower not in stopwords
            and len(word) > 2
            and not word.isdigit()
        ):
            # Preserve capitalization for proper nouns
            keywords.append(word if word[0].isupper() else word_lower)

    # Deduplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique_keywords.append(kw)

    # Take top 5 most significant keywords (increased from 3)
    # This helps specific markets like "Will Trump fire [Person]" by including the person's name
    top_keywords = unique_keywords[:5]

    if not top_keywords:
        return ""
    
    # If fewer than 2 keywords, try to just return what we have
    # If 0 keywords, we updated standard stopwords so maybe it was all stopwords?
    # In that case, fallback to original title limited
    if len(top_keywords) == 0:
        return title[:50]

    # Use AND logic for tighter relevance
    return " AND ".join(top_keywords)


def generate_url_hash(url: str) -> str:
    """Generate a hash for URL deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


class NewsAggregator:
    """Aggregator for fetching news articles from multiple sources."""

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        """
        Initialize the news aggregator.

        Args:
            api_key: NewsAPI API key. Uses settings if not provided.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or settings.NEWS_API_KEY
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_news_for_market(
        self,
        market_title: str,
        market_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Fetch news articles relevant to a market.

        Args:
            market_title: The market title/question.
            market_id: The market ID for association.
            limit: Maximum number of articles to fetch.

        Returns:
            List of article dictionaries ready for database storage.
        """
        if not self.api_key:
            logger.warning("No NEWS_API_KEY configured, skipping news fetch")
            return []

        query = extract_keywords(market_title)
        if not query:
            logger.warning(f"No keywords extracted from: {market_title}")
            return []

        logger.debug(f"News query for '{market_title[:50]}...': {query}")
        client = await self._get_client()

        try:
            response = await client.get(
                EVERYTHING_ENDPOINT,
                params={
                    "q": query,
                    "sortBy": "relevancy",  # Changed from publishedAt for better relevance
                    "pageSize": min(limit, 100),
                    "language": "en",
                    "apiKey": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []

            articles = []
            seen_urls = set()

            for item in data.get("articles", []):
                try:
                    article_in = NewsArticleIn.model_validate(item)

                    # Skip if no URL or duplicate
                    if not article_in.url or article_in.url in seen_urls:
                        continue
                    seen_urls.add(article_in.url)

                    # Skip articles with [Removed] title (deleted content)
                    if article_in.title and "[Removed]" in article_in.title:
                        continue

                    # Parse source name
                    source_name = ""
                    if isinstance(article_in.source, dict):
                        source_name = article_in.source.get("name", "")
                    elif isinstance(article_in.source, str):
                        source_name = article_in.source

                    # Parse published date
                    published_at = None
                    if article_in.publishedAt:
                        try:
                            published_at = datetime.fromisoformat(
                                article_in.publishedAt.replace("Z", "+00:00")
                            )
                        except Exception:
                            pass

                    articles.append(
                        {
                            "market_id": market_id,
                            "url_hash": generate_url_hash(article_in.url),
                            "title": article_in.title,
                            "description": article_in.description,
                            "url": article_in.url,
                            "source": source_name,
                            "author": article_in.author,
                            "image_url": article_in.urlToImage,
                            "published_at": published_at,
                            "sentiment_score": None,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse article: {e}")
                    continue

            return articles[:limit]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid NEWS_API_KEY")
            elif e.response.status_code == 429:
                logger.warning("NewsAPI rate limit reached")
            else:
                logger.error(f"HTTP error fetching news: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []


# Global aggregator instance
news_aggregator = NewsAggregator()

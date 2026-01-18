"""RSS feed collector."""

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from ..utils import get_logger
from .base import Article, Collector

logger = get_logger(__name__)


class RSSCollector(Collector):
    """Collector for RSS feeds."""

    def __init__(self, name: str, url: str):
        self._name = name
        self.url = url
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "DailyBriefing/1.0"},
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return self._name

    async def collect(self) -> list[Article]:
        """Fetch and parse RSS feed."""
        try:
            response = await self.client.get(self.url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)
            articles = []

            for entry in feed.entries:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)

            logger.info(f"[{self.name}] Collected {len(articles)} articles")
            return articles

        except httpx.HTTPError as e:
            logger.error(f"[{self.name}] HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Failed to collect: {e}")
            raise

    def _parse_entry(self, entry: dict) -> Optional[Article]:
        """Parse a feed entry into an Article."""
        url = entry.get("link")
        title = entry.get("title")

        if not url or not title:
            return None

        # Get summary/description
        summary = None
        if "summary" in entry:
            summary = entry.summary
        elif "description" in entry:
            summary = entry.description

        # Strip HTML tags from summary (basic)
        if summary:
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            # Truncate if too long
            if len(summary) > 500:
                summary = summary[:497] + "..."

        # Parse published date
        published_at = None
        if "published_parsed" in entry and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass

        # Get author
        author = entry.get("author")

        # Get tags/categories
        tags = []
        if "tags" in entry:
            tags = [t.get("term", "") for t in entry.tags if t.get("term")]

        return Article(
            url=url,
            title=title,
            source=self.name,
            summary=summary,
            author=author,
            published_at=published_at,
            tags=tags,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

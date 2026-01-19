"""Reddit collector using RSS feeds (more reliable from cloud providers)."""

from datetime import datetime
from typing import Optional
from xml.etree import ElementTree

import httpx

from ..utils import get_logger
from .base import Article, Collector

logger = get_logger(__name__)


class RedditCollector(Collector):
    """Collector for Reddit subreddits using RSS feeds."""

    BASE_URL = "https://www.reddit.com"

    def __init__(self, name: str, subreddit: str):
        self._name = name
        self.subreddit = subreddit
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "DailyBriefing/1.0 (Personal news aggregator)",
            },
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return f"r/{self._name}"

    async def collect(self) -> list[Article]:
        """Fetch hot posts from the subreddit via RSS."""
        url = f"{self.BASE_URL}/r/{self.subreddit}/hot.rss"

        try:
            response = await self.client.get(url, params={"limit": 25})
            response.raise_for_status()

            articles = self._parse_rss(response.text)
            logger.info(f"[{self.name}] Collected {len(articles)} posts")
            return articles

        except httpx.HTTPError as e:
            logger.error(f"[{self.name}] HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Failed to collect: {e}")
            raise

    def _parse_rss(self, xml_content: str) -> list[Article]:
        """Parse RSS feed into Articles."""
        articles = []

        try:
            root = ElementTree.fromstring(xml_content)
        except ElementTree.ParseError as e:
            logger.error(f"[{self.name}] Failed to parse RSS: {e}")
            return []

        # Handle Atom namespace (Reddit uses Atom format)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            article = self._parse_entry(entry, ns)
            if article:
                articles.append(article)

        return articles

    def _parse_entry(self, entry: ElementTree.Element, ns: dict) -> Optional[Article]:
        """Parse an RSS entry into an Article."""
        title_elem = entry.find("atom:title", ns)
        link_elem = entry.find("atom:link", ns)
        updated_elem = entry.find("atom:updated", ns)
        author_elem = entry.find("atom:author/atom:name", ns)
        content_elem = entry.find("atom:content", ns)

        title = title_elem.text if title_elem is not None else None
        url = link_elem.get("href") if link_elem is not None else None

        if not title or not url:
            return None

        # Parse published date
        published_at = None
        if updated_elem is not None and updated_elem.text:
            try:
                # Reddit uses ISO format: 2026-01-18T12:00:00+00:00
                date_str = updated_elem.text
                if date_str.endswith("+00:00"):
                    date_str = date_str[:-6]
                published_at = datetime.fromisoformat(date_str)
            except (TypeError, ValueError):
                pass

        # Get author (strip /u/ prefix)
        author = None
        if author_elem is not None and author_elem.text:
            author = author_elem.text.replace("/u/", "")
            if author == "[deleted]":
                author = None

        # Get content/summary from HTML content
        summary = ""
        if content_elem is not None and content_elem.text:
            # Content is HTML, extract a simple summary
            import re
            text = re.sub(r'<[^>]+>', ' ', content_elem.text)
            text = ' '.join(text.split())[:500]
            if len(text) == 500:
                text = text[:497] + "..."
            summary = text

        return Article(
            url=url,
            title=title,
            source=self.name,
            summary=summary or f"[Post from {self.name}]",
            author=author,
            published_at=published_at,
            topic="sports",  # All our Reddit sources are sports-related
            tags=[],
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

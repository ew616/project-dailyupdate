"""Reddit collector using public JSON endpoint (no auth required)."""

from datetime import datetime
from typing import Optional

import httpx

from ..utils import get_logger
from .base import Article, Collector

logger = get_logger(__name__)


class RedditCollector(Collector):
    """Collector for Reddit subreddits using public JSON API."""

    BASE_URL = "https://www.reddit.com"

    def __init__(self, name: str, subreddit: str):
        self._name = name
        self.subreddit = subreddit
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                # Reddit requires a descriptive User-Agent
                "User-Agent": "DailyBriefing/1.0 (Personal news aggregator)",
            },
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return f"r/{self._name}"

    async def collect(self) -> list[Article]:
        """Fetch hot posts from the subreddit."""
        url = f"{self.BASE_URL}/r/{self.subreddit}/hot.json"

        try:
            response = await self.client.get(url, params={"limit": 25})
            response.raise_for_status()

            data = response.json()
            articles = []

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                article = self._parse_post(post)
                if article:
                    articles.append(article)

            logger.info(f"[{self.name}] Collected {len(articles)} posts")
            return articles

        except httpx.HTTPError as e:
            logger.error(f"[{self.name}] HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Failed to collect: {e}")
            raise

    def _parse_post(self, post: dict) -> Optional[Article]:
        """Parse a Reddit post into an Article."""
        # Skip stickied/pinned posts
        if post.get("stickied"):
            return None

        # Skip posts with very low engagement
        score = post.get("score", 0)
        if score < 10:
            return None

        title = post.get("title")
        permalink = post.get("permalink")

        if not title or not permalink:
            return None

        url = f"{self.BASE_URL}{permalink}"

        # Get post content/selftext
        selftext = post.get("selftext", "")
        if len(selftext) > 500:
            selftext = selftext[:497] + "..."

        # If it's a link post, note the external URL
        external_url = post.get("url", "")
        if external_url and not external_url.startswith(self.BASE_URL):
            if selftext:
                selftext = f"{selftext}\n\nLink: {external_url}"
            else:
                selftext = f"Link: {external_url}"

        # Parse created timestamp
        published_at = None
        created_utc = post.get("created_utc")
        if created_utc:
            try:
                published_at = datetime.fromtimestamp(created_utc)
            except (TypeError, ValueError):
                pass

        # Get author
        author = post.get("author")
        if author == "[deleted]":
            author = None

        # Build summary with engagement stats
        num_comments = post.get("num_comments", 0)
        summary = selftext or f"[{score} upvotes, {num_comments} comments]"

        # Get flair as tags
        tags = []
        flair = post.get("link_flair_text")
        if flair:
            tags.append(flair)

        return Article(
            url=url,
            title=title,
            source=self.name,
            summary=summary,
            author=author,
            published_at=published_at,
            topic="sports",  # All our Reddit sources are sports-related
            tags=tags,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

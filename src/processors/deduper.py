"""Content deduplication using URL normalization and title similarity."""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from ..collectors.base import Article
from ..utils import get_logger

logger = get_logger(__name__)


class Deduper:
    """Deduplicate articles by URL and title similarity."""

    # URL parameters to strip (tracking, session, etc.)
    STRIP_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
    }

    # Title similarity threshold (0.0 - 1.0)
    TITLE_SIMILARITY_THRESHOLD = 0.85

    def __init__(self):
        self._seen_urls: set[str] = set()
        self._seen_titles: list[str] = []

    def normalize_url(self, url: str) -> str:
        """Normalize a URL by removing tracking params and standardizing format."""
        try:
            parsed = urlparse(url)

            # Remove tracking parameters
            query_params = parse_qs(parsed.query, keep_blank_values=False)
            filtered_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in self.STRIP_PARAMS
            }

            # Rebuild URL with sorted params for consistency
            sorted_query = urlencode(sorted(filtered_params.items()), doseq=True)

            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                parsed.params,
                sorted_query,
                "",  # Remove fragment
            ))

            return normalized
        except Exception:
            return url

    def normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        # Lowercase
        title = title.lower()
        # Remove punctuation
        title = re.sub(r"[^\w\s]", "", title)
        # Normalize whitespace
        title = " ".join(title.split())
        return title

    def title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles (0.0 - 1.0)."""
        norm1 = self.normalize_title(title1)
        norm2 = self.normalize_title(title2)
        return SequenceMatcher(None, norm1, norm2).ratio()

    def is_similar_to_seen(self, title: str) -> bool:
        """Check if title is similar to any previously seen title."""
        for seen_title in self._seen_titles:
            if self.title_similarity(title, seen_title) >= self.TITLE_SIMILARITY_THRESHOLD:
                return True
        return False

    def is_duplicate(self, article: Article) -> bool:
        """Check if an article is a duplicate."""
        # Check URL
        normalized_url = self.normalize_url(article.url)
        if normalized_url in self._seen_urls:
            logger.debug(f"Duplicate URL: {article.title[:50]}")
            return True

        # Check title similarity
        if self.is_similar_to_seen(article.title):
            logger.debug(f"Similar title found: {article.title[:50]}")
            return True

        return False

    def mark_seen(self, article: Article) -> None:
        """Mark an article as seen."""
        self._seen_urls.add(self.normalize_url(article.url))
        self._seen_titles.append(article.title)

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        """
        Remove duplicate articles from a list.
        Preserves order, keeping the first occurrence.
        """
        unique = []
        duplicates_removed = 0

        for article in articles:
            if self.is_duplicate(article):
                duplicates_removed += 1
                continue

            self.mark_seen(article)
            unique.append(article)

        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate articles")

        return unique

    def reset(self) -> None:
        """Clear seen URLs and titles."""
        self._seen_urls.clear()
        self._seen_titles.clear()

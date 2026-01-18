"""Base collector interface and Article dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    """Unified article representation from any source."""

    url: str
    title: str
    source: str
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    topic: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        if not isinstance(other, Article):
            return False
        return self.url == other.url


class Collector(ABC):
    """Abstract base class for content collectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the collector/source name."""
        pass

    @abstractmethod
    async def collect(self) -> list[Article]:
        """Collect articles from the source."""
        pass

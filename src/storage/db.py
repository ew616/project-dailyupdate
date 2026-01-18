"""SQLite database operations."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database for tracking articles and briefings."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    source TEXT,
                    topic TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    included_in_briefing_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS briefings (
                    id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topics_json TEXT,
                    html_content TEXT,
                    sent_at TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                );

                CREATE TABLE IF NOT EXISTS source_health (
                    id INTEGER PRIMARY KEY,
                    source_name TEXT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
                CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at);
            """)
        logger.info(f"Database initialized at {self.db_path}")

    def is_article_seen(self, url: str) -> bool:
        """Check if we've already processed this article."""
        with self._get_conn() as conn:
            result = conn.execute(
                "SELECT 1 FROM articles WHERE url = ?", (url,)
            ).fetchone()
            return result is not None

    def save_article(
        self,
        url: str,
        title: str,
        source: str,
        topic: Optional[str] = None,
        briefing_id: Optional[int] = None,
    ) -> int:
        """Save an article to the database."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO articles (url, title, source, topic, included_in_briefing_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (url, title, source, topic, briefing_id),
            )
            return cursor.lastrowid or 0

    def create_briefing(self, topics_json: str, html_content: str) -> int:
        """Create a new briefing record."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO briefings (topics_json, html_content, status)
                VALUES (?, ?, 'created')
                """,
                (topics_json, html_content),
            )
            return cursor.lastrowid or 0

    def mark_briefing_sent(self, briefing_id: int) -> None:
        """Mark a briefing as sent."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE briefings
                SET sent_at = CURRENT_TIMESTAMP, status = 'sent'
                WHERE id = ?
                """,
                (briefing_id,),
            )

    def mark_briefing_failed(self, briefing_id: int, error: str) -> None:
        """Mark a briefing as failed."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE briefings
                SET status = 'failed'
                WHERE id = ?
                """,
                (briefing_id,),
            )

    def log_source_health(
        self, source_name: str, status: str, error_message: Optional[str] = None
    ) -> None:
        """Log source health check result."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO source_health (source_name, status, error_message)
                VALUES (?, ?, ?)
                """,
                (source_name, status, error_message),
            )

    def get_failed_sources_today(self) -> list[str]:
        """Get sources that failed today."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT source_name FROM source_health
                WHERE status != 'ok'
                AND date(checked_at) = date('now')
                """
            ).fetchall()
            return [row["source_name"] for row in rows]

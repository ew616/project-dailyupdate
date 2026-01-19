"""Configuration and constants for the daily briefing system."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "briefing.db"

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# Email
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Daily Briefing <briefing@example.com>")

# Runtime options
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"  # Set to true to use Claude for synthesis

# Topics for classification
TOPICS = ["politics", "crypto", "movies", "business", "sports"]

# Teams for sports section (more specific to avoid false matches)
TEAMS = {
    "Knicks": ["knicks", "new york knicks", "nyk ", "r/nyknicks"],
    "Giants": ["ny giants", "new york giants", "nyg ", "r/nygiants", "giants'"],
    "Liverpool": ["liverpool fc", "lfc", "r/liverpoolfc", "anfield", "klopp", "slot"],
    "Mets": ["mets", "new york mets", "nym ", "r/newyorkmets", "citi field"],
}

# RSS Sources
RSS_SOURCES = [
    {
        "name": "NYT",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "enabled": True,
    },
    {
        "name": "Guardian",
        "url": "https://www.theguardian.com/international/rss",
        "enabled": True,
    },
    {
        "name": "Athletic",
        "url": "https://www.nytimes.com/athletic/feeds/rss/news/",
        "enabled": True,
    },
    {
        "name": "ESPN",
        "url": "https://www.espn.com/espn/rss/news",
        "enabled": True,
    },
    {
        "name": "BBC",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "enabled": True,
    },
    {
        "name": "Atlantic",
        "url": "https://www.theatlantic.com/feed/all/",
        "enabled": True,
    },
    {
        "name": "NewYorker",
        "url": "https://www.newyorker.com/feed/everything",
        "enabled": True,
    },
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "enabled": True,
    },
    {
        "name": "CNBC",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "enabled": True,
    },
]

# Reddit subreddits (disabled - use RSS feeds only)
REDDIT_SOURCES = []

# Claude settings
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096


def get_enabled_rss_sources() -> list[dict]:
    """Return only enabled RSS sources."""
    return [s for s in RSS_SOURCES if s.get("enabled", True)]


def get_enabled_reddit_sources() -> list[dict]:
    """Return only enabled Reddit sources."""
    return [s for s in REDDIT_SOURCES if s.get("enabled", True)]

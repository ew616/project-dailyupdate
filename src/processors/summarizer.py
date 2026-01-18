"""Content summarization - headlines mode (free) or LLM mode (paid)."""

from ..collectors.base import Article
from ..config import ANTHROPIC_API_KEY, TOPICS, TEAMS, USE_LLM
from ..utils import get_logger

logger = get_logger(__name__)


class Summarizer:
    """Summarize articles - uses headlines by default, LLM if enabled."""

    TOPIC_ORDER = ["sports", "politics", "business", "crypto", "movies"]

    def __init__(self):
        self.use_llm = USE_LLM and ANTHROPIC_API_KEY
        if self.use_llm:
            from anthropic import Anthropic
            from ..config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
            self.model = CLAUDE_MODEL
            self.max_tokens = CLAUDE_MAX_TOKENS
            logger.info("Using LLM mode for synthesis")
        else:
            logger.info("Using headlines mode (no LLM)")

    def synthesize_briefing(self, articles: list[Article]) -> dict[str, str]:
        """Create briefing content grouped by topic."""
        if not articles:
            return {}

        # Group articles by topic
        by_topic: dict[str, list[Article]] = {}
        for article in articles:
            topic = article.topic or "general"
            by_topic.setdefault(topic, []).append(article)

        # Build summaries in preferred order
        summaries = {}
        for topic in self.TOPIC_ORDER:
            if topic in by_topic:
                topic_articles = by_topic[topic]
                logger.info(f"Processing {len(topic_articles)} articles for: {topic}")
                if self.use_llm:
                    summaries[topic] = self._synthesize_with_llm(topic, topic_articles)
                else:
                    summaries[topic] = self._format_headlines(topic, topic_articles)

        # Add remaining topics
        for topic, topic_articles in by_topic.items():
            if topic not in summaries and topic in TOPICS:
                logger.info(f"Processing {len(topic_articles)} articles for: {topic}")
                if self.use_llm:
                    summaries[topic] = self._synthesize_with_llm(topic, topic_articles)
                else:
                    summaries[topic] = self._format_headlines(topic, topic_articles)

        return summaries

    def _format_headlines(self, topic: str, articles: list[Article]) -> str:
        """Format articles as a list of hyperlinks."""
        if topic == "sports":
            return self._format_sports_headlines(articles)

        lines = []
        # Show top 8 articles per topic
        for article in articles[:8]:
            # Format as markdown link: [title](url) (source)
            line = f"• [{article.title}]({article.url})"
            if article.source:
                line += f" ({article.source})"
            lines.append(line)

        return "\n".join(lines).strip()

    def _format_sports_headlines(self, articles: list[Article]) -> str:
        """Format sports headlines grouped by team as hyperlinks."""
        team_articles: dict[str, list[Article]] = {team: [] for team in TEAMS}
        other_sports: list[Article] = []

        for article in articles:
            text = f"{article.title} {article.summary or ''}".lower()
            matched = False
            for team, aliases in TEAMS.items():
                if any(alias in text for alias in aliases):
                    team_articles[team].append(article)
                    matched = True
                    break
            if not matched:
                other_sports.append(article)

        lines = []

        # Your teams first
        for team, team_arts in team_articles.items():
            if not team_arts:
                continue
            lines.append(f"**{team}**")
            for article in team_arts[:4]:
                lines.append(f"• [{article.title}]({article.url}) ({article.source})")
            lines.append("")

        # Other sports (limit to 3)
        if other_sports:
            lines.append("**Other Sports**")
            for article in other_sports[:3]:
                lines.append(f"• [{article.title}]({article.url}) ({article.source})")
            lines.append("")

        return "\n".join(lines).strip()

    def _synthesize_with_llm(self, topic: str, articles: list[Article]) -> str:
        """Use Claude to synthesize articles (when USE_LLM=true)."""
        article_texts = []
        for i, article in enumerate(articles[:12], 1):
            text = f"[{i}] {article.title} ({article.source})"
            if article.summary:
                text += f"\n{article.summary}"
            article_texts.append(text)

        articles_context = "\n\n".join(article_texts)

        if topic == "sports":
            team_names = ", ".join(TEAMS.keys())
            prompt = f"""Create a brief sports summary for someone who follows: {team_names}.
Group by team, 2-3 sentences each. Be concise.

Articles:
{articles_context}

Summary:"""
        else:
            prompt = f"""Summarize these {topic} articles in 2-3 paragraphs. Lead with the biggest story. Be concise and cite sources.

Articles:
{articles_context}

Summary:"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def classify_article(self, article: Article) -> str:
        """Classify article into a topic using keywords only (no API)."""
        import re

        title_lower = article.title.lower()
        summary_lower = (article.summary or "").lower()
        text = f"{title_lower} {summary_lower}"

        # Check for team mentions first (strong sports signal)
        for team, aliases in TEAMS.items():
            if any(alias in text for alias in aliases):
                return "sports"

        # Keyword-based classification (more specific to reduce false positives)
        topic_keywords = {
            "politics": ["congress", "senate", "president", "election", "democrat", "republican",
                        "biden", "trump", "legislation", "vote", "political", "governor",
                        "white house", "capitol", "supreme court", "parliament", "minister"],
            "crypto": ["bitcoin", "ethereum", "cryptocurrency", "blockchain", "binance",
                      "coinbase", "solana", "defi", "web3"],
            "movies": ["film", "movie", "cinema", "oscar", "hollywood", "box office", "premiere",
                      "golden globe", "actress", "mattel", "barbie", "paramount", "warner bros"],
            "business": ["stock market", "economy", "ceo", "earnings", "revenue", "startup",
                        "investment", "ipo", "nasdaq", "dow jones", "inflation", "wall street",
                        "profit", "merger", "acquisition"],
            "sports": ["nba", "nfl", "mlb", "premier league", "championship", "playoff",
                      "touchdown", "goalkeeper", "striker", "quarterback", "pitcher"],
        }

        topic_scores = {topic: 0 for topic in TOPICS}
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                # Use word boundary matching for short keywords
                if len(keyword) <= 4:
                    if re.search(rf'\b{re.escape(keyword)}\b', text):
                        topic_scores[topic] += 1
                else:
                    if keyword in text:
                        topic_scores[topic] += 1

        best_topic = max(topic_scores, key=topic_scores.get)
        if topic_scores[best_topic] >= 1:
            return best_topic

        # Default to general (won't be shown in briefing)
        return "general"

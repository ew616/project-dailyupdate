"""Main entry point for the daily briefing system."""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta

from .collectors import RSSCollector, RedditCollector, Article
from .config import (
    DB_PATH,
    DRY_RUN,
    LOG_LEVEL,
    get_enabled_rss_sources,
    get_enabled_reddit_sources,
)
from .delivery import EmailSender
from .processors import Deduper, Summarizer
from .storage import Database
from .utils import setup_logging, get_logger

logger = get_logger(__name__)


async def collect_from_source(
    collector, source_name: str, db: Database
) -> tuple[list[Article], str | None]:
    """Collect from a single source. Returns (articles, error_source_name)."""
    try:
        source_articles = await collector.collect()
        # Filter out already-seen articles
        new_articles = [a for a in source_articles if not db.is_article_seen(a.url)]
        db.log_source_health(source_name, "ok")
        logger.info(f"[{source_name}] {len(new_articles)} new articles (filtered from {len(source_articles)})")
        return new_articles, None
    except Exception as e:
        logger.error(f"[{source_name}] Collection failed: {e}")
        db.log_source_health(source_name, "error", str(e))
        return [], source_name
    finally:
        await collector.close()


async def collect_articles(db: Database) -> tuple[list[Article], list[str]]:
    """Collect articles from all enabled sources in parallel."""
    collectors = []

    # Build RSS collectors
    for source in get_enabled_rss_sources():
        collector = RSSCollector(source["name"], source["url"])
        collectors.append((collector, source["name"]))

    # Build Reddit collectors
    for source in get_enabled_reddit_sources():
        collector = RedditCollector(source["name"], source["subreddit"])
        collectors.append((collector, f"r/{source['name']}"))

    logger.info(f"Fetching from {len(collectors)} sources in parallel...")

    # Collect from all sources in parallel
    tasks = [
        collect_from_source(collector, name, db)
        for collector, name in collectors
    ]
    results = await asyncio.gather(*tasks)

    # Aggregate results
    articles = []
    unavailable_sources = []
    for source_articles, error_source in results:
        articles.extend(source_articles)
        if error_source:
            unavailable_sources.append(error_source)

    return articles, unavailable_sources


def filter_recent_articles(articles: list[Article], max_age_days: int = 7) -> list[Article]:
    """Filter articles to only include those from the last N days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    recent = []
    for article in articles:
        if article.published_at is None:
            # Include articles without a date (can't determine age)
            recent.append(article)
        elif article.published_at >= cutoff:
            recent.append(article)
    return recent


def classify_articles(articles: list[Article], summarizer: Summarizer) -> list[Article]:
    """Classify articles into topics (skips already-classified articles)."""
    for article in articles:
        if not article.topic:
            article.topic = summarizer.classify_article(article)
            logger.debug(f"Classified '{article.title[:50]}...' as {article.topic}")
    return articles


def run_pipeline(dry_run: bool = False) -> None:
    """Run the full briefing pipeline."""
    logger.info("Starting daily briefing pipeline")

    # Initialize components
    db = Database(DB_PATH)
    deduper = Deduper()
    summarizer = Summarizer()
    email_sender = EmailSender()

    # Collect articles
    articles, unavailable_sources = asyncio.run(collect_articles(db))
    logger.info(f"Collected {len(articles)} new articles total")

    if not articles:
        logger.warning("No new articles to process")
        return

    # Deduplicate across sources
    articles = deduper.deduplicate(articles)
    logger.info(f"After deduplication: {len(articles)} articles")

    # Filter to only recent articles (last 7 days)
    articles = filter_recent_articles(articles, max_age_days=7)
    logger.info(f"After date filter (last 7 days): {len(articles)} articles")

    if not articles:
        logger.warning("No recent articles to process")
        return

    # Classify articles
    articles = classify_articles(articles, summarizer)

    # Save articles to database
    for article in articles:
        db.save_article(
            url=article.url,
            title=article.title,
            source=article.source,
            topic=article.topic,
        )

    # Synthesize by topic
    logger.info("Synthesizing briefing...")
    summaries = summarizer.synthesize_briefing(articles)

    if dry_run:
        # Print to console instead of sending
        logger.info("DRY RUN - Not sending email")
        print("\n" + "=" * 60)
        print("DAILY BRIEFING (DRY RUN)")
        print("=" * 60)
        for topic, summary in summaries.items():
            print(f"\n## {topic.upper()}\n")
            print(summary)
        print("\n" + "=" * 60)

        if unavailable_sources:
            print(f"\nUnavailable sources: {', '.join(unavailable_sources)}")

        # Still save the briefing
        html = email_sender.render_briefing(summaries, unavailable_sources, len(articles))
        briefing_id = db.create_briefing(json.dumps(summaries), html)
        logger.info(f"Briefing saved with ID {briefing_id} (not sent)")
        return

    # Create and send email
    html = email_sender.render_briefing(summaries, unavailable_sources, len(articles))
    briefing_id = db.create_briefing(json.dumps(summaries), html)

    try:
        email_id = email_sender.send(summaries, unavailable_sources, len(articles))
        db.mark_briefing_sent(briefing_id)
        logger.info(f"Briefing sent successfully! Email ID: {email_id}")
    except Exception as e:
        db.mark_briefing_failed(briefing_id, str(e))
        logger.error(f"Failed to send briefing: {e}")
        raise


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Daily News Briefing System")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN,
        help="Print briefing to console instead of sending email",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test email to verify configuration",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear seen articles and run fresh",
    )
    parser.add_argument(
        "--log-level",
        default=LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.reset:
        logger.info("Clearing seen articles...")
        db = Database(DB_PATH)
        count = db.clear_seen_articles()
        print(f"Cleared {count} seen articles. Running fresh collection...")

    if args.test_email:
        logger.info("Sending test email...")
        email_sender = EmailSender()
        try:
            email_id = email_sender.send_test()
            print(f"Test email sent successfully! ID: {email_id}")
        except Exception as e:
            print(f"Failed to send test email: {e}")
            sys.exit(1)
        return

    try:
        run_pipeline(dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        # Send error alert (but not in dry-run mode)
        if not args.dry_run:
            try:
                email_sender = EmailSender()
                email_sender.send_error_alert(str(e))
            except Exception as alert_err:
                logger.error(f"Failed to send error alert: {alert_err}")
        sys.exit(1)


if __name__ == "__main__":
    main()

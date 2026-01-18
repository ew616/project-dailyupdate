"""Email delivery via Resend."""

import re
from datetime import datetime
from pathlib import Path

import httpx
import resend
from jinja2 import Environment, FileSystemLoader

from ..config import RESEND_API_KEY, EMAIL_TO, EMAIL_FROM
from ..utils import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_nyc_weather() -> str:
    """Fetch current New York weather from wttr.in."""
    try:
        response = httpx.get(
            "https://wttr.in/New+York?format=%c+%t",
            timeout=5.0,
            headers={"User-Agent": "DailyBriefing/1.0"}
        )
        if response.status_code == 200:
            weather = response.text.strip()
            return f"New York {weather}"
    except Exception as e:
        logger.warning(f"Failed to fetch weather: {e}")
    return ""


def markdown_to_html(text: str) -> str:
    """Convert simple markdown to HTML for email."""
    # Links: [text](url) -> <a href="url">text</a>
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" style="color: #326891; text-decoration: none;">\1</a>',
        text
    )

    # Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Bullet points
    lines = text.split('\n')
    result = []
    for line in lines:
        if line.startswith('• '):
            result.append(f'<div style="margin: 8px 0; padding-left: 8px;">{line}</div>')
        elif line.strip() == '':
            result.append('<div style="height: 8px;"></div>')
        else:
            result.append(f'<div style="margin: 8px 0;">{line}</div>')

    return ''.join(result)


class EmailSender:
    """Send briefing emails via Resend."""

    def __init__(self):
        resend.api_key = RESEND_API_KEY
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    def render_briefing(
        self,
        summaries: dict[str, str],
        unavailable_sources: list[str],
        article_count: int,
        weather: str = "",
    ) -> str:
        """Render the briefing HTML."""
        template = self.env.get_template("briefing.html")

        # Format date nicely
        date_str = datetime.now().strftime("%A, %B %d, %Y")

        # Fetch weather if not provided
        if not weather:
            weather = get_nyc_weather()

        # Convert markdown to HTML
        html_summaries = {topic: markdown_to_html(content) for topic, content in summaries.items()}

        html = template.render(
            date=date_str,
            weather=weather,
            summaries=html_summaries,
            unavailable_sources=unavailable_sources,
            article_count=article_count,
        )
        return html

    def send(
        self,
        summaries: dict[str, str],
        unavailable_sources: list[str],
        article_count: int,
    ) -> str:
        """Send the briefing email."""
        html = self.render_briefing(summaries, unavailable_sources, article_count)
        date_str = datetime.now().strftime("%B %d, %Y")

        try:
            response = resend.Emails.send({
                "from": EMAIL_FROM,
                "to": [EMAIL_TO],
                "subject": f"Elias's Daily Update - {date_str}",
                "html": html,
            })

            email_id = response.get("id", "unknown")
            logger.info(f"Email sent successfully: {email_id}")
            return email_id

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

    def send_test(self) -> str:
        """Send a test email to verify configuration."""
        test_summaries = {
            "sports": (
                "**Knicks**\n"
                "• [Knicks vs Suns Game Notes: January 17, 2026](https://knicks.com/news/knicks-vs-suns-game-notes-january-16-2026) (NBA.com)\n"
                "• [Party Like '99? Three Reasons For and Against New York Winning the East](https://www.espn.com/nba/story/_/id/47586139/new-york-knicks-three-reasons-winning-east) (ESPN)\n"
                "• [Knicks vs Warriors Game Notes: January 15, 2026](https://www.nba.com/knicks/news/knicks-vs-warriors-game-notes-january-15-2026) (NBA.com)\n\n"
                "**Giants**\n"
                "• [Giants Finalize Five-Year Deal with John Harbaugh as Next Coach](https://www.cbssports.com/nfl/news/giants-to-finalize-deal-and-hire-john-harbaugh-next-coach-per-report/) (CBS Sports)\n"
                "• [NY Giants 2026 NFL Draft: 10 Prospects to Watch at the Senior Bowl](https://www.bigblueview.com/senior-bowl/152030/ny-giants-2026-nfl-draft-10-prospects-to-watch-senior-bowl) (Big Blue View)\n"
                "• [Giants 34-17 Cowboys (Jan 4, 2026) Game Recap](https://www.espn.com/nfl/recap?gameId=401772963) (ESPN)\n\n"
                "**Liverpool**\n"
                "• [Liverpool Transfers: Latest News and Analysis on January Signings](https://www.espn.com/soccer/story/_/id/47470578/liverpool-transfers-latest-news-reports-analysis-rumours-signings-exits-deals-contracts) (ESPN)\n"
                "• [Liverpool Cannot Afford January Transfer Misstep](https://www.liverpool.com/liverpool-fc-news/features/january-transfer-plans-bradley-injury-33225271) (Liverpool.com)\n"
                "• [Liverpool Transfer News: $70M Midfielder Wanted](https://www.liverpool.com/liverpool-fc-news/transfer-news/kees-smit-marc-guehi-update-33230156) (Liverpool.com)\n\n"
                "**Mets**\n"
                "• [Mets Sign Bo Bichette to Three-Year, $126 Million Deal](https://www.amazinavenue.com/new-york-mets-morning-news/89289/mets-morning-news-bo-bichette-signs-kyle-tucker-brett-baty-baseball-offseason-new-york-mlb) (Amazin' Avenue)\n"
                "• [Mets Avoid Arbitration with All 6 Eligible Players for 2026](https://www.mlb.com/news/mets-avoid-arbitration-2026) (MLB.com)\n"
                "• [Mets Morning News for January 17, 2026](https://sports.yahoo.com/articles/mets-morning-news-january-17-123000098.html) (Yahoo Sports)\n"
            ),
            "politics": (
                "• [Trump Says U.S. 'In Charge' of Venezuela After Maduro Captured](https://www.cbsnews.com/live-updates/venezuela-us-military-strikes-maduro-trump/) (CBS News)\n"
                "• [No, Trump Can't Cancel the Midterms. He's Doing This Instead](https://www.cnn.com/2026/01/17/politics/midterm-elections-trump-2026-analysis) (CNN)\n"
                "• [GOP Senators Break with Trump on These 2 Points](https://www.pbs.org/newshour/politics/gop-senators-break-with-trump-on-these-2-points) (PBS)\n"
                "• [Trump Administration News: January 16, 2026](https://edition.cnn.com/politics/live-news/trump-administration-news-01-16-26) (CNN)\n"
                "• [A Look at What Happened in the US Government This Week](https://www.wisn.com/article/politics-recap-january-16-2026/70028355) (WISN)\n"
            ),
            "business": (
                "• [What to Expect from Stocks in 2026](https://www.cnn.com/2026/01/01/investing/what-to-expect-stock-market-2026) (CNN)\n"
                "• [Stock Market Today: Dow, S&P Hit All-Time Highs](https://www.bloomberg.com/news/articles/2026-01-14/stock-market-today-dow-s-p-live-updates) (Bloomberg)\n"
                "• [Stock Market Predictions 2026: AI Boom, Dollar's Decline](https://www.bloomberg.com/graphics/2026-investment-outlooks/) (Bloomberg)\n"
                "• [Week Ahead Economic Preview: Week of 19 January 2026](https://www.spglobal.com/marketintelligence/en/mi/research-analysis/week-ahead-economic-preview-week-of-19-january-2026.html) (S&P Global)\n"
                "• [Stock Market News for Jan. 14, 2026](https://www.cnbc.com/2026/01/13/stock-market-today-live-updates.html) (CNBC)\n"
            ),
            "crypto": (
                "• [The Boldest Bitcoin Predictions for 2026: From $75,000 to $225,000](https://www.cnbc.com/2026/01/08/bitcoin-btc-price-predictions-for-2026.html) (CNBC)\n"
                "• [Bitcoin Slips to $95,000 as U.S. Crypto Bill Stalls in Senate](https://www.coindesk.com/markets/2026/01/16/bitcoin-slips-to-nearly-usd95-000-as-senate-delay-and-risk-off-moves-weigh-on-crypto) (CoinDesk)\n"
                "• [BTC, ETH Breakout Liquidates Nearly $700 Million in Shorts](https://www.coindesk.com/markets/2026/01/14/bitcoin-and-ether-s-sharp-mechanical-breakouts-liquidate-nearly-usd700-million-short-positions) (CoinDesk)\n"
                "• [Here's Why Bitcoin and Major Tokens Are Seeing a Strong 2026](https://www.coindesk.com/markets/2026/01/06/here-s-why-bitcoin-and-major-tokens-are-seeing-a-strong-start-to-2026) (CoinDesk)\n"
                "• [Bitcoin's 'Boring' Price Action Likely to Continue, Say Analysts](https://www.coindesk.com/markets/2026/01/08/bitcoin-may-be-in-for-a-more-boring-but-nevertheless-positive-year) (CoinDesk)\n"
            ),
            "movies": (
                "• [Box Office: 'Avatar: Fire And Ash' Burns Trail to $306M U.S.](https://deadline.com/2026/01/box-office-avatar-fire-and-ash-2026-first-weekend-1236660722/) (Deadline)\n"
                "• [Box Office: 'Avatar 3' Leads in First Weekend of 2026](https://variety.com/2026/film/box-office/box-office-avatar-3-leads-2026-1236623079/) (Variety)\n"
                "• ['Primate' Opens; 'Avatar' Still No. 1; 'Housemaid' Holds Strong](https://deadline.com/2026/01/box-office-primate-avatar-fire-and-ash-greenland-migration-1236677406/) (Deadline)\n"
                "• [The Most Anticipated Movies of 2026](https://editorial.rottentomatoes.com/article/the-most-anticipated-movies-of-2026/) (Rotten Tomatoes)\n"
                "• [Indie Film Box Office: Independent Film Shores Up Super Start to 2026](https://deadline.com/2026/01/indie-film-box-office-strong-start-to-2026-1236661162/) (Deadline)\n"
            ),
        }
        return self.send(test_summaries, [], 24)

    def send_error_alert(self, error: str, context: str = "") -> str:
        """Send an error alert email when the pipeline fails."""
        date_str = datetime.now().strftime("%B %d, %Y at %H:%M")

        html = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px;">
                <h2 style="color: #991b1b; margin-top: 0;">Daily Briefing Failed</h2>
                <p style="color: #7f1d1d;">The daily briefing pipeline encountered an error on {date_str}.</p>
                <div style="background: #ffffff; border-radius: 4px; padding: 15px; margin: 15px 0;">
                    <strong style="color: #991b1b;">Error:</strong>
                    <pre style="background: #f3f4f6; padding: 10px; border-radius: 4px; overflow-x: auto; color: #374151;">{error}</pre>
                </div>
                {f'<p style="color: #6b7280;"><strong>Context:</strong> {context}</p>' if context else ''}
                <p style="color: #6b7280; font-size: 12px; margin-bottom: 0;">Check your Railway logs for more details.</p>
            </div>
        </body>
        </html>
        """

        try:
            response = resend.Emails.send({
                "from": EMAIL_FROM,
                "to": [EMAIL_TO],
                "subject": f"[ALERT] Daily Briefing Failed - {date_str}",
                "html": html,
            })

            email_id = response.get("id", "unknown")
            logger.info(f"Error alert sent: {email_id}")
            return email_id

        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")
            raise

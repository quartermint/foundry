import json
import logging

import anthropic

from app.config import settings
from app.database import async_session_factory
from app.models.tip import Tip
from app.services.knowledge_base import ensure_fts_table, sync_fts

logger = logging.getLogger(__name__)

SUBREDDITS = ["3Dprinting", "BambuLab", "functionalprint"]
MIN_UPVOTES = 50


async def scrape_reddit():
    """Scrape Reddit for 3D printing tips and add to knowledge base."""
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.info("Reddit credentials not configured, skipping scrape")
        return

    try:
        import praw

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        tips_added = 0

        async with async_session_factory() as session:
            await ensure_fts_table(session)

            for sub_name in SUBREDDITS:
                try:
                    subreddit = reddit.subreddit(sub_name)
                    for post in subreddit.hot(limit=25):
                        if post.score < MIN_UPVOTES:
                            continue

                        # Check if we already have this URL
                        from sqlalchemy import select, text
                        existing = await session.execute(
                            select(Tip).where(Tip.source_url == post.url)
                        )
                        if existing.scalar_one_or_none():
                            continue

                        # Extract tips using Claude
                        content = f"Title: {post.title}\n\n{post.selftext[:2000]}"
                        message = client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=500,
                            messages=[{
                                "role": "user",
                                "content": f"""Extract any 3D printing tips from this Reddit post.
If there are actionable tips, return a JSON object with:
- "tip": the tip text (concise, actionable)
- "tags": array of relevant tags (e.g. "retraction", "bed adhesion", "PLA")
- "materials": array of materials mentioned
- "printers": array of printer models mentioned

If no useful tips, return {{"tip": null}}.

Post: {content}""",
                            }],
                        )

                        try:
                            resp_text = message.content[0].text.strip()
                            if "{" in resp_text:
                                resp_text = resp_text[resp_text.index("{"):resp_text.rindex("}") + 1]
                            data = json.loads(resp_text)

                            if data.get("tip"):
                                tip = Tip(
                                    source_type="reddit",
                                    source_url=f"https://reddit.com{post.permalink}",
                                    source_title=post.title,
                                    content=data["tip"],
                                    tags=json.dumps(data.get("tags", [])),
                                    materials=json.dumps(data.get("materials", [])),
                                    printer_models=json.dumps(data.get("printers", [])),
                                    upvotes=post.score,
                                )
                                session.add(tip)
                                await session.commit()
                                await session.refresh(tip)
                                await sync_fts(session, tip)
                                tips_added += 1
                        except (json.JSONDecodeError, IndexError):
                            continue

                except Exception:
                    logger.exception("Failed to scrape r/%s", sub_name)

        logger.info("Reddit scrape complete: %d tips added", tips_added)

    except ImportError:
        logger.error("praw not installed — cannot scrape Reddit")
    except Exception:
        logger.exception("Reddit scrape failed")

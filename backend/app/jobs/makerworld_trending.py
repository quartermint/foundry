import logging

import httpx
from bs4 import BeautifulSoup

from app.database import async_session_factory
from app.models.discovery_result import DiscoveryResult

logger = logging.getLogger(__name__)


async def scrape_trending():
    """Scrape MakerWorld trending models and cache for discovery."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                "https://makerworld.com/en/popular",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        models_found = 0

        async with async_session_factory() as session:
            for card in soup.select("a[href*='/models/']")[:30]:
                link = card.get("href", "")
                if not link or "/models/" not in str(link):
                    continue

                if not str(link).startswith("http"):
                    link = f"https://makerworld.com{link}"

                title_el = card.select_one("[class*='title'], h3, h4, span")
                img_el = card.select_one("img")

                title = title_el.get_text(strip=True) if title_el else "Trending Model"
                thumb = img_el.get("src", "") if img_el else None

                # Check for existing
                from sqlalchemy import select
                existing = await session.execute(
                    select(DiscoveryResult).where(DiscoveryResult.source_url == str(link))
                )
                if existing.scalar_one_or_none():
                    continue

                result = DiscoveryResult(
                    title=title[:256],
                    source_url=str(link),
                    source_platform="makerworld",
                    thumbnail_url=thumb,
                    file_type="3mf",
                    has_bambu_profile=True,
                    search_query="trending",
                )
                session.add(result)
                models_found += 1

            await session.commit()

        logger.info("MakerWorld trending scrape: %d new models cached", models_found)

    except Exception:
        logger.exception("MakerWorld trending scrape failed")

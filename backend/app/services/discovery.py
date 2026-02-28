import asyncio
import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def search_makerworld(query: str, limit: int = 10) -> list[dict]:
    """Search MakerWorld for 3D models via scraping."""
    results = []
    url = f"https://makerworld.com/en/search/models?keyword={quote_plus(query)}"

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # MakerWorld model cards — structure varies, extract what we can
        for card in soup.select("[class*='model-card'], [class*='ModelCard'], a[href*='/models/']")[:limit]:
            title_el = card.select_one("[class*='title'], h3, h4, [class*='name']")
            img_el = card.select_one("img")
            link = card.get("href", "")

            if not link or "/models/" not in str(link):
                # Try finding a child link
                a_el = card.select_one("a[href*='/models/']")
                if a_el:
                    link = a_el.get("href", "")

            if not link:
                continue

            if not str(link).startswith("http"):
                link = f"https://makerworld.com{link}"

            results.append({
                "title": title_el.get_text(strip=True) if title_el else "Untitled",
                "source_url": str(link),
                "thumbnail_url": img_el.get("src", "") if img_el else None,
                "platform": "makerworld",
                "has_bambu_profile": True,  # MakerWorld models are Bambu-native
                "file_type": "3mf",
                "downloads": 0,
                "likes": 0,
            })
    except Exception:
        logger.exception("MakerWorld search failed for: %s", query)

    return results


PRINTABLES_GQL = "https://api.printables.com/graphql/"

PRINTABLES_QUERY = """
query SearchModels($query: String!, $limit: Int) {
    result: searchPrintsV2(
        search: $query
        limit: $limit
    ) {
        items {
            id
            name
            slug
            image {
                filePath
            }
            likesCount
            downloadCount
            makesCount
            datePublished
        }
    }
}
"""


async def search_printables(query: str, limit: int = 10) -> list[dict]:
    """Search Printables for 3D models via GraphQL API."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                PRINTABLES_GQL,
                json={
                    "query": PRINTABLES_QUERY,
                    "variables": {"query": query, "limit": limit},
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Foundry/1.0",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("data", {}).get("result", {}).get("items", [])
        for item in items:
            slug = item.get("slug", item.get("id", ""))
            img = item.get("image", {})
            img_url = img.get("filePath", "") if img else ""

            results.append({
                "title": item.get("name", "Untitled"),
                "source_url": f"https://www.printables.com/model/{slug}",
                "thumbnail_url": img_url,
                "platform": "printables",
                "has_bambu_profile": False,
                "file_type": "stl",
                "downloads": item.get("downloadCount", 0),
                "likes": item.get("likesCount", 0),
            })
    except Exception:
        logger.exception("Printables search failed for: %s", query)

    return results


async def search_all(query: str, limit_per_platform: int = 10) -> list[dict]:
    """Search all platforms in parallel and merge results."""
    mw_task = asyncio.create_task(search_makerworld(query, limit_per_platform))
    pr_task = asyncio.create_task(search_printables(query, limit_per_platform))

    mw_results, pr_results = await asyncio.gather(mw_task, pr_task, return_exceptions=True)

    results = []
    if isinstance(mw_results, list):
        results.extend(mw_results)
    else:
        logger.error("MakerWorld search returned error: %s", mw_results)

    if isinstance(pr_results, list):
        results.extend(pr_results)
    else:
        logger.error("Printables search returned error: %s", pr_results)

    return results

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.queue_item import QueueItem
from app.services.ai_pipeline import generate_search_queries, rank_results
from app.services.discovery import search_all
from app.services.slicer import slice_stl
from app.services.thumbnail import generate_thumbnail

import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discover", tags=["discover"], dependencies=[Depends(require_token)])

STORAGE = Path(__file__).resolve().parent.parent.parent / "storage"
MODELS_DIR = STORAGE / "models"
SLICED_DIR = STORAGE / "sliced"
THUMBS_DIR = STORAGE / "thumbnails"


class DiscoverRequest(BaseModel):
    description: str


class AddToQueueRequest(BaseModel):
    title: str
    source_url: str
    source_platform: str
    thumbnail_url: str | None = None
    file_type: str = "stl"
    has_bambu_profile: bool = False


@router.post("/search")
async def search_models(body: DiscoverRequest):
    """Search community platforms for 3D models matching a description."""
    # Generate optimized search queries
    queries = await generate_search_queries(body.description)

    # Search all platforms with all queries, dedup
    all_results = []
    seen_urls = set()

    search_tasks = [search_all(q, limit_per_platform=5) for q in queries]
    batch_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    for batch in batch_results:
        if isinstance(batch, list):
            for r in batch:
                url = r.get("source_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)

    # Rank by relevance
    ranked = await rank_results(body.description, all_results)

    return {
        "description": body.description,
        "queries_used": queries,
        "results": ranked[:15],
        "total_found": len(all_results),
    }


@router.post("/add-to-queue", status_code=201)
async def add_to_queue(
    body: AddToQueueRequest,
    session: AsyncSession = Depends(get_session),
):
    """Download a community model and add it to the print queue."""
    file_id = uuid.uuid4().hex[:12]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    SLICED_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    # Download thumbnail if available
    thumb_path = None
    if body.thumbnail_url:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(body.thumbnail_url)
                if resp.status_code == 200:
                    thumb_path = str(THUMBS_DIR / f"{file_id}.png")
                    with open(thumb_path, "wb") as f:
                        f.write(resp.content)
        except Exception:
            logger.warning("Failed to download thumbnail from %s", body.thumbnail_url)

    # Create queue item — actual model download happens when user approves
    # (community sites may require browser interaction for download)
    item = QueueItem(
        title=body.title,
        description=f"From {body.source_platform}: {body.source_url}",
        source_type="community",
        source_url=body.source_url,
        source_platform=body.source_platform,
        thumbnail_path=thumb_path,
        status="pending_approval",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return item.to_dict()

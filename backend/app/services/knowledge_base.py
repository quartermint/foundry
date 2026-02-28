import json
import logging

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tip import Tip

logger = logging.getLogger(__name__)


async def ensure_fts_table(session: AsyncSession):
    """Create FTS5 virtual table if it doesn't exist."""
    await session.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tips_fts USING fts5(
            content, tags, materials,
            content='tips', content_rowid='id'
        )
    """))
    await session.commit()


async def sync_fts(session: AsyncSession, tip: Tip):
    """Insert a tip's content into the FTS index."""
    await session.execute(text("""
        INSERT OR REPLACE INTO tips_fts(rowid, content, tags, materials)
        VALUES (:id, :content, :tags, :materials)
    """), {"id": tip.id, "content": tip.content, "tags": tip.tags or "", "materials": tip.materials or ""})
    await session.commit()


async def search_tips(session: AsyncSession, query: str, limit: int = 20) -> list[dict]:
    """Search tips using FTS5."""
    try:
        result = await session.execute(text("""
            SELECT t.* FROM tips t
            JOIN tips_fts fts ON t.id = fts.rowid
            WHERE tips_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """), {"query": query, "limit": limit})

        rows = result.mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        # FTS table might not exist yet — fall back to LIKE search
        logger.warning("FTS search failed, falling back to LIKE")
        result = await session.execute(text("""
            SELECT * FROM tips
            WHERE content LIKE :pattern OR tags LIKE :pattern OR materials LIKE :pattern
            ORDER BY upvotes DESC
            LIMIT :limit
        """), {"pattern": f"%{query}%", "limit": limit})
        rows = result.mappings().all()
        return [dict(row) for row in rows]


async def ask_knowledge_base(session: AsyncSession, question: str) -> dict:
    """Answer a question using tips from the knowledge base + Claude synthesis."""
    tips = await search_tips(session, question, limit=20)

    if not tips:
        return {
            "answer": "I don't have enough information in the knowledge base to answer that yet. "
                      "The knowledge base grows over time from Reddit, YouTube, and community sources.",
            "sources": [],
        }

    # Build context from tips
    context_parts = []
    sources = []
    for i, tip in enumerate(tips, 1):
        context_parts.append(f"[{i}] {tip.get('content', '')}")
        url = tip.get("source_url", "")
        title = tip.get("source_title", f"Tip #{tip.get('id', i)}")
        if url:
            sources.append({"title": title, "url": url})

    context = "\n\n".join(context_parts)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You are a helpful 3D printing expert. Answer questions using the provided tips from the knowledge base. "
               "Cite sources using [N] notation. Be concise and practical.",
        messages=[{
            "role": "user",
            "content": f"Knowledge base tips:\n{context}\n\nQuestion: {question}",
        }],
    )

    return {
        "answer": message.content[0].text,
        "sources": sources,
        "tips_used": len(tips),
    }

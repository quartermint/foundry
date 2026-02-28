from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.services.knowledge_base import ask_knowledge_base, search_tips

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(require_token)])


class AskRequest(BaseModel):
    question: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 20


@router.post("/ask")
async def ask(body: AskRequest, session: AsyncSession = Depends(get_session)):
    """Ask a question and get an AI-synthesized answer from the knowledge base."""
    return await ask_knowledge_base(session, body.question)


@router.post("/search")
async def search(body: SearchRequest, session: AsyncSession = Depends(get_session)):
    """Search the knowledge base for tips."""
    results = await search_tips(session, body.query, limit=body.limit)
    return {"results": results, "count": len(results)}

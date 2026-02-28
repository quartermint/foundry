from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.print_job import PrintJob

router = APIRouter(prefix="/api/history", tags=["history"], dependencies=[Depends(require_token)])


@router.get("")
async def list_jobs(
    printer_id: int | None = None,
    outcome: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    query = select(PrintJob).order_by(PrintJob.created_at.desc())
    if printer_id:
        query = query.where(PrintJob.printer_id == printer_id)
    if outcome:
        query = query.where(PrintJob.outcome == outcome)
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return [j.to_dict() for j in result.scalars().all()]


@router.get("/{job_id}")
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(PrintJob, job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Print job not found")
    return job.to_dict()

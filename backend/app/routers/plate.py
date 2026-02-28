from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.printer import Printer
from app.models.queue_item import QueueItem
from app.services.plate_optimizer import optimize_plate

router = APIRouter(prefix="/api/plate", tags=["plate"], dependencies=[Depends(require_token)])


class PlateRequest(BaseModel):
    item_ids: list[int]
    printer_id: int | None = None


@router.post("/optimize")
async def optimize(body: PlateRequest, session: AsyncSession = Depends(get_session)):
    """Pack multiple queue items onto a single build plate."""
    if len(body.item_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 items to plate")

    # Get printer bed dimensions
    bed_x, bed_y = 256, 256
    if body.printer_id:
        printer = await session.get(Printer, body.printer_id)
        if printer:
            bed_x = printer.bed_x_mm
            bed_y = printer.bed_y_mm

    # Get queue items with model paths
    result = await session.execute(
        select(QueueItem).where(QueueItem.id.in_(body.item_ids))
    )
    items = result.scalars().all()

    item_data = []
    for item in items:
        if not item.model_path:
            continue
        item_data.append({"id": item.id, "model_path": item.model_path, "title": item.title})

    if len(item_data) < 2:
        raise HTTPException(status_code=400, detail="Not enough items with model files to plate")

    plate_result = optimize_plate(item_data, bed_x_mm=bed_x, bed_y_mm=bed_y)

    return plate_result

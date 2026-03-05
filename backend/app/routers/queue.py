import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.print_job import PrintJob
from app.models.printer import Printer
from app.models.queue_item import QueueItem
from app.services.bambu_ftp import upload_file
from app.services.bambu_mqtt import mqtt_service
from app.services.notifications import notify
from app.services.slicer import slice_stl
from app.services.thumbnail import generate_thumbnail

router = APIRouter(prefix="/api/queue", tags=["queue"], dependencies=[Depends(require_token)])

STORAGE = Path(__file__).resolve().parent.parent.parent / "storage"
MODELS_DIR = STORAGE / "models"
SLICED_DIR = STORAGE / "sliced"
THUMBS_DIR = STORAGE / "thumbnails"


class QueueItemUpdate(BaseModel):
    status: str | None = None
    printer_id: int | None = None
    material: str | None = None
    title: str | None = None


@router.get("")
async def list_queue(
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(QueueItem).order_by(QueueItem.created_at.desc())
    if status_filter:
        query = query.where(QueueItem.status == status_filter)
    result = await session.execute(query)
    return [item.to_dict() for item in result.scalars().all()]


@router.get("/{item_id}")
async def get_queue_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(QueueItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return item.to_dict()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_model(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
):
    """Upload an STL or .3mf file to the queue."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".stl", ".3mf"):
        raise HTTPException(status_code=400, detail="Only .stl and .3mf files accepted")

    file_id = uuid.uuid4().hex[:12]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    SLICED_DIR.mkdir(parents=True, exist_ok=True)

    model_filename = f"{file_id}{ext}"
    model_path = MODELS_DIR / model_filename
    with open(model_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Generate thumbnail for STL
    thumb_path = THUMBS_DIR / f"{file_id}.png"
    if ext == ".stl":
        generate_thumbnail(str(model_path), str(thumb_path))

    # Auto-slice STL to .3mf
    sliced_path = None
    if ext == ".stl":
        out_3mf = SLICED_DIR / f"{file_id}.3mf"
        success = await slice_stl(str(model_path), str(out_3mf))
        if success:
            sliced_path = str(out_3mf)
    elif ext == ".3mf":
        # Already sliced
        sliced_path = str(model_path)

    item = QueueItem(
        title=Path(file.filename).stem,
        description=f"Uploaded file: {file.filename}",
        source_type="upload",
        model_path=str(model_path),
        sliced_path=sliced_path,
        thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
        status="pending_approval",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    await notify(
        "New item in queue",
        f"{item.title} is ready for review",
        tags="package",
    )

    return item.to_dict()


@router.put("/{item_id}")
async def update_queue_item(
    item_id: int,
    body: QueueItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(QueueItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if body.status:
        valid_transitions = {
            "pending_approval": ["approved", "rejected"],
            "approved": ["slicing", "ready", "printing"],
            "slicing": ["ready", "failed"],
            "ready": ["printing"],
            "printing": ["completed", "failed"],
        }
        allowed = valid_transitions.get(item.status, [])
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{item.status}' to '{body.status}'. Allowed: {allowed}",
            )
        item.status = body.status

    if body.printer_id is not None:
        item.printer_id = body.printer_id
    if body.material is not None:
        item.material = body.material
    if body.title is not None:
        item.title = body.title

    await session.commit()
    await session.refresh(item)
    return item.to_dict()


@router.post("/{item_id}/send")
async def send_to_printer(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Send an approved queue item to the printer for printing."""
    item = await session.get(QueueItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if item.status not in ("approved", "ready"):
        raise HTTPException(status_code=400, detail=f"Item must be approved/ready, currently '{item.status}'")

    if not item.sliced_path or not Path(item.sliced_path).exists():
        raise HTTPException(status_code=400, detail="No sliced .3mf file available")

    if not item.printer_id:
        # Pick first enabled printer
        result = await session.execute(
            select(Printer).where(Printer.enabled == True).limit(1)  # noqa: E712
        )
        printer = result.scalar_one_or_none()
        if not printer:
            raise HTTPException(status_code=400, detail="No enabled printer available")
        item.printer_id = printer.id
    else:
        printer = await session.get(Printer, item.printer_id)
        if not printer:
            raise HTTPException(status_code=404, detail="Assigned printer not found")

    # Upload to printer via FTPS
    remote_name = Path(item.sliced_path).name
    remote_path = await upload_file(printer.ip, printer.access_code, item.sliced_path, remote_name, storage_path=printer.storage_path)
    if not remote_path:
        raise HTTPException(status_code=502, detail="Failed to upload to printer")

    # Start print via MQTT (use full remote path for ftp:// URL)
    success = await mqtt_service.send_print_command(printer.id, remote_path)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send print command")

    item.status = "printing"

    # Create print job record
    job = PrintJob(
        queue_item_id=item.id,
        printer_id=printer.id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(item)
    await session.refresh(job)

    await notify(
        "Print started",
        f"{item.title} is now printing on {printer.name}",
        tags="rocket",
    )

    return {"status": "printing", "job_id": job.id, "queue_item": item.to_dict()}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_queue_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(QueueItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    await session.delete(item)
    await session.commit()

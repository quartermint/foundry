from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.queue_item import QueueItem
from app.services.generation import generate_model

router = APIRouter(prefix="/api/generate", tags=["generate"], dependencies=[Depends(require_token)])


class GenerateRequest(BaseModel):
    description: str
    constraints: dict | None = None
    backend: str | None = None


class IterateRequest(BaseModel):
    queue_item_id: int
    feedback: str


@router.post("")
async def generate_from_description(
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate a 3D model from a natural language description using AI + OpenSCAD/Blender."""
    result = await generate_model(
        body.description,
        constraints=body.constraints,
        backend_override=body.backend,
    )

    if not result["success"]:
        raise HTTPException(status_code=422, detail=result.get("error", "Generation failed"))

    item = QueueItem(
        title=body.description[:200],
        description=body.description,
        source_type="generated",
        model_path=result.get("stl_path"),
        sliced_path=result.get("sliced_path"),
        thumbnail_path=result.get("thumbnail_path"),
        generation_backend=result.get("generation_backend"),
        status="pending_approval",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return {
        "queue_item": item.to_dict(),
        "source_path": result.get("source_path"),
        "generation_backend": result.get("generation_backend"),
    }


@router.post("/iterate")
async def iterate_design(
    body: IterateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Iterate on a previously generated design with feedback."""
    item = await session.get(QueueItem, body.queue_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.source_type != "generated":
        raise HTTPException(status_code=400, detail="Can only iterate on generated models")

    # Detect backend from source file extension
    backend = item.generation_backend
    if not backend and item.model_path:
        source_path = item.model_path.replace(".stl", ".py")
        from pathlib import Path
        if Path(source_path).exists():
            backend = "blender"
        else:
            backend = "openscad"

    # Read previous source code
    previous_code = None
    if item.model_path:
        ext = ".py" if backend == "blender" else ".scad"
        source_path = item.model_path.replace(".stl", ext)
        try:
            with open(source_path, "r") as f:
                previous_code = f.read()
        except Exception:
            pass

    result = await generate_model(
        item.description or item.title,
        previous_code=previous_code,
        feedback=body.feedback,
        backend_override=backend,
    )

    if not result["success"]:
        raise HTTPException(status_code=422, detail=result.get("error", "Iteration failed"))

    # Update the queue item with new files
    item.model_path = result.get("stl_path")
    item.sliced_path = result.get("sliced_path")
    item.thumbnail_path = result.get("thumbnail_path")
    item.generation_backend = result.get("generation_backend")
    item.status = "pending_approval"

    await session.commit()
    await session.refresh(item)

    return {
        "queue_item": item.to_dict(),
        "source_path": result.get("source_path"),
        "generation_backend": result.get("generation_backend"),
    }

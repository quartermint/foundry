import asyncio
import logging
import uuid
from pathlib import Path

from app.config import settings
from app.services.ai_pipeline import generate_openscad
from app.services.slicer import slice_stl
from app.services.thumbnail import generate_thumbnail

logger = logging.getLogger(__name__)

STORAGE = Path(__file__).resolve().parent.parent.parent / "storage"
MODELS_DIR = STORAGE / "models"
SLICED_DIR = STORAGE / "sliced"
THUMBS_DIR = STORAGE / "thumbnails"


async def compile_openscad(scad_path: str, stl_path: str) -> bool:
    """Compile an OpenSCAD file to STL."""
    openscad = settings.openscad_path
    if not Path(openscad).exists():
        logger.error("OpenSCAD not found at %s", openscad)
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            openscad, "-o", stl_path, scad_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error(
                "OpenSCAD compile failed (rc=%d): %s",
                proc.returncode,
                stderr.decode("utf-8", errors="replace"),
            )
            return False

        if not Path(stl_path).exists() or Path(stl_path).stat().st_size == 0:
            logger.error("OpenSCAD produced empty or no output: %s", stl_path)
            return False

        logger.info("OpenSCAD compiled: %s -> %s", scad_path, stl_path)
        return True

    except asyncio.TimeoutError:
        logger.error("OpenSCAD timed out after 120s")
        return False
    except Exception:
        logger.exception("OpenSCAD compilation failed")
        return False


async def generate_model(
    description: str,
    constraints: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
    max_retries: int = 3,
) -> dict:
    """Full generation pipeline: Claude -> OpenSCAD -> STL -> slice -> thumbnail."""
    file_id = uuid.uuid4().hex[:12]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    SLICED_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    scad_path = MODELS_DIR / f"{file_id}.scad"
    stl_path = MODELS_DIR / f"{file_id}.stl"
    threemf_path = SLICED_DIR / f"{file_id}.3mf"
    thumb_path = THUMBS_DIR / f"{file_id}.png"

    last_error = None

    for attempt in range(max_retries):
        # Generate OpenSCAD code
        code = await generate_openscad(
            description,
            constraints=constraints,
            previous_code=previous_code if attempt == 0 else open(scad_path).read(),
            feedback=feedback if attempt == 0 else f"OpenSCAD compilation error: {last_error}",
        )

        with open(scad_path, "w") as f:
            f.write(code)

        # Compile to STL
        success = await compile_openscad(str(scad_path), str(stl_path))
        if success:
            break

        last_error = f"Compilation failed on attempt {attempt + 1}"
        logger.warning("OpenSCAD attempt %d failed, retrying...", attempt + 1)
    else:
        return {
            "success": False,
            "error": f"OpenSCAD compilation failed after {max_retries} attempts: {last_error}",
            "scad_path": str(scad_path),
        }

    # Generate thumbnail
    generate_thumbnail(str(stl_path), str(thumb_path))

    # Slice to .3mf
    sliced = await slice_stl(str(stl_path), str(threemf_path))

    return {
        "success": True,
        "file_id": file_id,
        "scad_path": str(scad_path),
        "stl_path": str(stl_path),
        "sliced_path": str(threemf_path) if sliced else None,
        "thumbnail_path": str(thumb_path) if thumb_path.exists() else None,
    }

import asyncio
import logging
import uuid
from pathlib import Path

from app.config import settings
from app.services.ai_pipeline import (
    generate_blender_script,
    generate_openscad,
    route_generation_backend,
)
from app.services.blender_mcp import BlenderMCPError, blender_mcp
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


async def execute_blender_script(script: str, stl_path: str) -> tuple[bool, str | None]:
    """Execute a bpy script via BlenderMCP and verify STL output.

    Returns (success, error_message).
    """
    try:
        await blender_mcp.execute_code(script)
    except BlenderMCPError as e:
        return False, str(e)

    if not Path(stl_path).exists() or Path(stl_path).stat().st_size == 0:
        return False, "Blender script executed but STL was not produced"

    logger.info("Blender exported: %s", stl_path)
    return True, None


async def _determine_backend(
    description: str,
    backend_override: str | None,
) -> str:
    """Determine which generation backend to use."""
    if backend_override and backend_override in ("openscad", "blender"):
        if backend_override == "blender" and settings.blender_mcp_enabled:
            healthy = await blender_mcp.health_check()
            if not healthy:
                logger.warning("Blender requested but MCP unhealthy, falling back to openscad")
                return "openscad"
        return backend_override

    if not settings.blender_mcp_enabled:
        return "openscad"

    # AI routing
    backend = await route_generation_backend(description)
    if backend == "blender":
        healthy = await blender_mcp.health_check()
        if not healthy:
            logger.warning("AI routed to blender but MCP unhealthy, falling back to openscad")
            return "openscad"

    return backend


async def generate_model(
    description: str,
    constraints: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
    max_retries: int = 3,
    backend_override: str | None = None,
) -> dict:
    """Full generation pipeline: AI -> OpenSCAD/Blender -> STL -> slice -> thumbnail."""
    file_id = uuid.uuid4().hex[:12]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    SLICED_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    backend = await _determine_backend(description, backend_override)
    logger.info("Generation backend: %s (override=%s)", backend, backend_override)

    stl_path = MODELS_DIR / f"{file_id}.stl"
    threemf_path = SLICED_DIR / f"{file_id}.3mf"
    thumb_path = THUMBS_DIR / f"{file_id}.png"

    if backend == "blender":
        source_path = MODELS_DIR / f"{file_id}.py"
        result = await _generate_blender(
            description, str(stl_path), str(source_path),
            constraints, previous_code, feedback, max_retries,
        )
    else:
        source_path = MODELS_DIR / f"{file_id}.scad"
        result = await _generate_openscad(
            description, str(stl_path), str(source_path),
            constraints, previous_code, feedback, max_retries,
        )

    if not result["success"]:
        result["generation_backend"] = backend
        return result

    # Generate thumbnail
    generate_thumbnail(str(stl_path), str(thumb_path))

    # Slice to .3mf
    sliced = await slice_stl(str(stl_path), str(threemf_path))

    return {
        "success": True,
        "file_id": file_id,
        "source_path": str(source_path),
        "stl_path": str(stl_path),
        "sliced_path": str(threemf_path) if sliced else None,
        "thumbnail_path": str(thumb_path) if thumb_path.exists() else None,
        "generation_backend": backend,
    }


async def _generate_openscad(
    description: str,
    stl_path: str,
    scad_path: str,
    constraints: dict | None,
    previous_code: str | None,
    feedback: str | None,
    max_retries: int,
) -> dict:
    """OpenSCAD generation loop with retries."""
    last_error = None

    for attempt in range(max_retries):
        code = await generate_openscad(
            description,
            constraints=constraints,
            previous_code=previous_code if attempt == 0 else open(scad_path).read(),
            feedback=feedback if attempt == 0 else f"OpenSCAD compilation error: {last_error}",
        )

        with open(scad_path, "w") as f:
            f.write(code)

        success = await compile_openscad(scad_path, stl_path)
        if success:
            return {"success": True}

        last_error = f"Compilation failed on attempt {attempt + 1}"
        logger.warning("OpenSCAD attempt %d failed, retrying...", attempt + 1)

    return {
        "success": False,
        "error": f"OpenSCAD compilation failed after {max_retries} attempts: {last_error}",
        "source_path": scad_path,
    }


async def _generate_blender(
    description: str,
    stl_path: str,
    script_path: str,
    constraints: dict | None,
    previous_code: str | None,
    feedback: str | None,
    max_retries: int,
) -> dict:
    """Blender generation loop with retries."""
    # Determine export directory
    export_dir = settings.blender_export_dir
    if not export_dir:
        export_dir = str(MODELS_DIR)
    stl_export_path = str(Path(export_dir) / Path(stl_path).name)

    last_error = None

    for attempt in range(max_retries):
        script = await generate_blender_script(
            description,
            stl_export_path=stl_export_path,
            constraints=constraints,
            previous_code=previous_code if attempt == 0 else open(script_path).read(),
            feedback=feedback if attempt == 0 else f"Blender execution error: {last_error}",
        )

        with open(script_path, "w") as f:
            f.write(script)

        success, error = await execute_blender_script(script, stl_path)
        if success:
            return {"success": True}

        last_error = error or f"Execution failed on attempt {attempt + 1}"
        logger.warning("Blender attempt %d failed: %s", attempt + 1, last_error)

    return {
        "success": False,
        "error": f"Blender generation failed after {max_retries} attempts: {last_error}",
        "source_path": script_path,
    }

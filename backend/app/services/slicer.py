import asyncio
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"


async def slice_stl(
    stl_path: str,
    output_3mf_path: str,
    profile: str = "bambu_p2s_pla_0.4mm",
) -> bool:
    """Slice an STL file to .3mf using OrcaSlicer CLI."""
    orca = settings.orcaslicer_path
    if not Path(orca).exists():
        logger.error("OrcaSlicer not found at %s", orca)
        return False

    profile_path = PROFILES_DIR / f"{profile}.json"
    if not profile_path.exists():
        logger.error("Slicer profile not found: %s", profile_path)
        return False

    Path(output_3mf_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        orca,
        "--slice", "0",
        "--export-3mf", output_3mf_path,
        "--load-settings", str(profile_path),
        stl_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error(
                "OrcaSlicer failed (rc=%d): %s",
                proc.returncode,
                stderr.decode("utf-8", errors="replace"),
            )
            return False

        if not Path(output_3mf_path).exists():
            logger.error("OrcaSlicer produced no output at %s", output_3mf_path)
            return False

        logger.info("Sliced %s -> %s", stl_path, output_3mf_path)
        return True

    except asyncio.TimeoutError:
        logger.error("OrcaSlicer timed out after 120s")
        return False
    except Exception:
        logger.exception("Slicing failed for %s", stl_path)
        return False

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_thumbnail(stl_path: str, output_path: str, size: tuple[int, int] = (400, 400)) -> bool:
    """Generate a PNG thumbnail from an STL file using trimesh."""
    try:
        import trimesh

        mesh = trimesh.load(stl_path)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.dump(concatenate=True)

        scene = trimesh.Scene(mesh)
        png = scene.save_image(resolution=size)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(png)

        logger.info("Thumbnail generated: %s", output_path)
        return True
    except Exception:
        logger.exception("Failed to generate thumbnail for %s", stl_path)
        return False


def get_stl_info(stl_path: str) -> dict | None:
    """Get bounding box and volume info from an STL file."""
    try:
        import numpy as np
        from stl import mesh as stl_mesh

        m = stl_mesh.Mesh.from_file(stl_path)
        bbox = {
            "x": float(np.ptp(m.x)),
            "y": float(np.ptp(m.y)),
            "z": float(np.ptp(m.z)),
        }
        volume_cm3 = float(m.get_mass_properties()[0]) / 1000.0  # mm^3 to cm^3
        return {"bbox_mm": bbox, "volume_cm3": abs(volume_cm3)}
    except Exception:
        logger.exception("Failed to get STL info for %s", stl_path)
        return None

import logging
from pathlib import Path

import rectpack
from stl import mesh as stl_mesh

logger = logging.getLogger(__name__)


def optimize_plate(
    items: list[dict],
    bed_x_mm: int = 256,
    bed_y_mm: int = 256,
    margin_mm: int = 5,
) -> dict:
    """Pack multiple STL files onto a single build plate using 2D bounding boxes.

    Args:
        items: List of dicts with 'id' and 'model_path' keys
        bed_x_mm: Printer bed width
        bed_y_mm: Printer bed depth
        margin_mm: Gap between parts

    Returns:
        Dict with 'placed' (list of positioned items) and 'overflow' (items that didn't fit)
    """
    packer = rectpack.newPacker(rotation=True)
    packer.add_bin(bed_x_mm, bed_y_mm)

    item_sizes = {}
    for item in items:
        model_path = item.get("model_path", "")
        if not model_path or not Path(model_path).exists():
            logger.warning("Skipping item %s: no model file", item.get("id"))
            continue

        try:
            m = stl_mesh.Mesh.from_file(model_path)
            bbox_x = float(m.x.max() - m.x.min()) + margin_mm
            bbox_y = float(m.y.max() - m.y.min()) + margin_mm
            item_sizes[item["id"]] = {"x": bbox_x, "y": bbox_y}
            packer.add_rect(int(bbox_x), int(bbox_y), rid=item["id"])
        except Exception:
            logger.exception("Failed to read STL for item %s", item.get("id"))

    packer.pack()

    placed = []
    placed_ids = set()

    for rect in packer.rect_list():
        bin_idx, x, y, w, h, rid = rect
        placed.append({
            "id": rid,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
        })
        placed_ids.add(rid)

    overflow = [item for item in items if item["id"] not in placed_ids and item["id"] in item_sizes]

    return {
        "placed": placed,
        "overflow": overflow,
        "bed_x_mm": bed_x_mm,
        "bed_y_mm": bed_y_mm,
        "utilization_pct": round(
            sum(p["width"] * p["height"] for p in placed) / (bed_x_mm * bed_y_mm) * 100, 1
        ) if placed else 0,
    }

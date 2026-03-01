import json
import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

MODEL = "gemini-3-flash-preview"


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


async def generate_search_queries(description: str) -> list[str]:
    """Use Gemini to generate optimal search queries from a natural language description."""
    client = _get_client()

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(max_output_tokens=500),
        contents=f"""Generate 3-5 concise search queries to find 3D printable models matching this description.
Return ONLY a JSON array of strings, no explanation.

Description: {description}""",
    )

    text = response.text.strip()
    # Extract JSON array from response
    if "[" in text:
        text = text[text.index("["):text.rindex("]") + 1]
    try:
        queries = json.loads(text)
        if isinstance(queries, list):
            return [str(q) for q in queries[:5]]
    except json.JSONDecodeError:
        logger.warning("Failed to parse search queries from Gemini response")

    # Fallback: use description directly
    return [description]


async def rank_results(description: str, results: list[dict]) -> list[dict]:
    """Use Gemini to rank search results by relevance to the description."""
    if not results:
        return []

    if len(results) <= 3:
        return results

    client = _get_client()

    # Prepare compact result summaries for ranking
    summaries = []
    for i, r in enumerate(results):
        summaries.append({
            "index": i,
            "title": r.get("title", ""),
            "platform": r.get("platform", ""),
            "downloads": r.get("downloads", 0),
            "likes": r.get("likes", 0),
            "has_bambu_profile": r.get("has_bambu_profile", False),
        })

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(max_output_tokens=500),
        contents=f"""Rank these 3D model search results by relevance to: "{description}"

Results: {json.dumps(summaries)}

Return a JSON array of the indices in order of relevance (most relevant first), max 10.
Return ONLY the JSON array, no explanation.""",
    )

    text = response.text.strip()
    if "[" in text:
        text = text[text.index("["):text.rindex("]") + 1]
    try:
        indices = json.loads(text)
        ranked = []
        seen = set()
        for idx in indices:
            idx = int(idx)
            if 0 <= idx < len(results) and idx not in seen:
                ranked.append(results[idx])
                seen.add(idx)
        return ranked
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse ranking from Gemini, returning original order")
        return results


async def generate_openscad(
    description: str,
    constraints: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
) -> str:
    """Use Gemini to generate OpenSCAD code for a described object."""
    client = _get_client()

    system_prompt = """You are an expert CAD designer generating OpenSCAD code for FDM 3D printing.

Constraints:
- Max overhang angle: 45 degrees (design for printability without supports when possible)
- Minimum wall thickness: 0.8mm (for 0.4mm nozzle)
- Build volume: 256 x 256 x 256 mm
- Generate a single self-contained .scad file with no external dependencies
- Use $fn=60 or higher for smooth curves
- Include comments explaining key dimensions
- Design for practical use — functional tolerances, chamfers on contact edges

Return ONLY the OpenSCAD code, no explanation or markdown fences."""

    user_content = f"Design: {description}"

    if constraints:
        user_content += f"\n\nAdditional constraints: {json.dumps(constraints)}"

    if previous_code and feedback:
        user_content += f"\n\nPrevious version:\n```\n{previous_code}\n```\n\nFeedback: {feedback}"

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=4000,
        ),
        contents=user_content,
    )

    code = response.text.strip()
    # Strip markdown fences if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.endswith("```"):
            code = code[:-3].rstrip()

    return code


async def route_generation_backend(description: str) -> str:
    """Use Gemini to classify whether a description should use OpenSCAD or Blender."""
    client = _get_client()

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(max_output_tokens=50),
        contents=f"""Classify this 3D model request into exactly one backend.

Rules:
- "openscad" for parametric, geometric, CSG, functional/mechanical parts, enclosures, brackets, mounts
- "blender" for organic shapes, characters, figurines, sculptures, complex curved surfaces, decorative art, low-poly animals

When in doubt, prefer "openscad".

Return ONLY the single word "openscad" or "blender", nothing else.

Description: {description}""",
    )

    result = response.text.strip().lower()
    if result in ("openscad", "blender"):
        return result
    logger.warning("Unexpected routing response '%s', defaulting to openscad", result)
    return "openscad"


async def generate_blender_script(
    description: str,
    stl_export_path: str,
    constraints: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
) -> str:
    """Use Gemini to generate a Blender bpy Python script for the described object."""
    client = _get_client()

    system_prompt = f"""You are an expert 3D artist generating Blender Python (bpy) scripts for FDM 3D printing.

Your script runs in a HEADLESS Blender instance (--background mode). Important constraints:
- Do NOT use bpy.context.active_object or bpy.context.selected_objects (unavailable in background threads)
- Access objects by name via bpy.data.objects["Name"] instead
- Do NOT use bpy.ops.wm.stl_export (poll fails in background mode)
- Use the bmesh-based STL export helper shown below

You MUST:
1. Clear the scene first: remove all objects and meshes via bpy.data
2. Create the model using bpy.ops mesh primitives and bpy.data APIs
3. Ensure the mesh is manifold (watertight)
4. Join all objects into one, apply transforms, clean geometry
5. Export to binary STL using the helper function below

3D Printing Constraints:
- Max overhang angle: 45 degrees (design for printability without supports)
- Minimum wall thickness: 0.8mm
- Build volume: 256 x 256 x 256 mm
- Ensure solid geometry, no zero-thickness faces

Script Template:
```python
import bpy
import bmesh
import struct

# --- STL export helper (required - bpy.ops export fails in background mode) ---
def export_stl(obj, filepath):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    tris = []
    for f in bm.faces:
        tris.append((f.normal, [v.co for v in f.verts]))
    bm.free()
    with open(filepath, "wb") as fp:
        fp.write(b"\\x00" * 80)
        fp.write(struct.pack("<I", len(tris)))
        for n, vs in tris:
            fp.write(struct.pack("<3f", *n))
            for v in vs:
                fp.write(struct.pack("<3f", *v))
            fp.write(struct.pack("<H", 0))
    print(f"Exported {{len(tris)}} triangles to {{filepath}}")

# Clear scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

# --- Your modeling code here ---
# Use bpy.ops.mesh.primitive_*_add() to create shapes
# Access created objects via bpy.data.objects["ObjectName"]

# Finalize: join all objects, clean geometry, export
objs = list(bpy.data.objects)
if len(objs) > 1:
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()

final_obj = bpy.data.objects[0]
bm = bmesh.new()
bm.from_mesh(final_obj.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(final_obj.data)
bm.free()

export_stl(final_obj, "{stl_export_path}")
```

Return ONLY the Python code, no explanation or markdown fences."""

    user_content = f"Create: {description}"

    if constraints:
        user_content += f"\n\nAdditional constraints: {json.dumps(constraints)}"

    if previous_code and feedback:
        user_content += f"\n\nPrevious script:\n```python\n{previous_code}\n```\n\nFeedback: {feedback}"

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=8000,
        ),
        contents=user_content,
    )

    code = response.text.strip()
    # Strip markdown fences if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.endswith("```"):
            code = code[:-3].rstrip()

    return code

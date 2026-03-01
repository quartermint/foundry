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

Your script will run in a persistent headless Blender instance. You MUST:
1. Clear the scene first: delete all objects, meshes, materials
2. Create the model using bpy ops and data APIs
3. Ensure the mesh is manifold (watertight, no non-manifold edges)
4. Apply all transforms (Ctrl+A equivalent)
5. Recalculate normals to face outward
6. Remove doubles / merge by distance
7. Export to STL at exactly this path: bpy.ops.wm.stl_export(filepath="{stl_export_path}")

3D Printing Constraints:
- Max overhang angle: 45 degrees (design for printability without supports when possible)
- Minimum wall thickness: 0.8mm
- Build volume: 256 x 256 x 256 mm
- Ensure solid geometry, no zero-thickness faces

Script Template:
```python
import bpy
import bmesh

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for mesh in bpy.data.meshes:
    bpy.data.meshes.remove(mesh)

# --- Your modeling code here ---

# Finalize: select all, apply transforms, clean geometry
bpy.ops.object.select_all(action='SELECT')
obj = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.001)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

# Export
bpy.ops.wm.stl_export(filepath="{stl_export_path}")
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

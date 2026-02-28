import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def generate_search_queries(description: str) -> list[str]:
    """Use Claude to generate optimal search queries from a natural language description."""
    client = _get_client()

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Generate 3-5 concise search queries to find 3D printable models matching this description.
Return ONLY a JSON array of strings, no explanation.

Description: {description}""",
        }],
    )

    text = message.content[0].text.strip()
    # Extract JSON array from response
    if "[" in text:
        text = text[text.index("["):text.rindex("]") + 1]
    try:
        queries = json.loads(text)
        if isinstance(queries, list):
            return [str(q) for q in queries[:5]]
    except json.JSONDecodeError:
        logger.warning("Failed to parse search queries from Claude response")

    # Fallback: use description directly
    return [description]


async def rank_results(description: str, results: list[dict]) -> list[dict]:
    """Use Claude to rank search results by relevance to the description."""
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

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Rank these 3D model search results by relevance to: "{description}"

Results: {json.dumps(summaries)}

Return a JSON array of the indices in order of relevance (most relevant first), max 10.
Return ONLY the JSON array, no explanation.""",
        }],
    )

    text = message.content[0].text.strip()
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
        logger.warning("Failed to parse ranking from Claude, returning original order")
        return results


async def generate_openscad(
    description: str,
    constraints: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
) -> str:
    """Use Claude to generate OpenSCAD code for a described object."""
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

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    code = message.content[0].text.strip()
    # Strip markdown fences if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.endswith("```"):
            code = code[:-3].rstrip()

    return code

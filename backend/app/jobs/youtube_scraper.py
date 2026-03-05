import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.config import settings
from app.database import async_session_factory
from app.models.tip import Tip
from app.services.knowledge_base import ensure_fts_table, sync_fts

logger = logging.getLogger(__name__)

# Curated channel URLs — configurable via future settings
YOUTUBE_CHANNELS = [
    "https://www.youtube.com/@CNCKitchen",
    "https://www.youtube.com/@MakersMuse",
    "https://www.youtube.com/@BambuLab",
    "https://www.youtube.com/@TeachingTech",
    "https://www.youtube.com/@3DPrintingNerd",
]

MAX_VIDEOS_PER_CHANNEL = 3


async def scrape_youtube():
    """Extract tips from recent YouTube videos using yt-dlp transcripts."""
    tips_added = 0

    try:
        for channel_url in YOUTUBE_CHANNELS:
            try:
                # Use yt-dlp to get recent video transcripts
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--flat-playlist",
                    "--playlist-end", str(MAX_VIDEOS_PER_CHANNEL),
                    "--print", "%(id)s\t%(title)s",
                    f"{channel_url}/videos",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

                lines = stdout.decode("utf-8", errors="replace").strip().split("\n")

                for line in lines:
                    if "\t" not in line:
                        continue
                    video_id, title = line.split("\t", 1)

                    # Download transcript only
                    sub_proc = await asyncio.create_subprocess_exec(
                        "yt-dlp",
                        "--write-auto-sub",
                        "--sub-lang", "en",
                        "--skip-download",
                        "--write-subs",
                        "-o", f"/tmp/foundry_yt_{video_id}",
                        f"https://www.youtube.com/watch?v={video_id}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(sub_proc.communicate(), timeout=60)

                    # Read transcript
                    import glob
                    sub_files = glob.glob(f"/tmp/foundry_yt_{video_id}*.vtt") + \
                                glob.glob(f"/tmp/foundry_yt_{video_id}*.srt")
                    if not sub_files:
                        continue

                    with open(sub_files[0], "r", errors="replace") as f:
                        transcript = f.read()[:5000]

                    # Clean up temp files
                    for sf in sub_files:
                        import os
                        os.unlink(sf)

                    # Extract tips via Gemini
                    client = genai.Client(api_key=settings.gemini_api_key)
                    response = client.models.generate_content(
                        model="gemini-3-flash-preview",
                        config=types.GenerateContentConfig(max_output_tokens=1000),
                        contents=f"""Extract actionable 3D printing tips from this YouTube video transcript.
Return a JSON array of objects, each with:
- "tip": concise actionable tip
- "tags": relevant tags
- "materials": materials mentioned
- "printers": printer models mentioned

Only include genuinely useful, specific tips. Return empty array if none found.

Title: {title}
Transcript excerpt: {transcript}""",
                    )

                    try:
                        resp_text = response.text.strip()
                        if "[" in resp_text:
                            resp_text = resp_text[resp_text.index("["):resp_text.rindex("]") + 1]
                        tips_data = json.loads(resp_text)

                        async with async_session_factory() as session:
                            await ensure_fts_table(session)
                            for td in tips_data:
                                if not td.get("tip"):
                                    continue
                                tip = Tip(
                                    source_type="youtube",
                                    source_url=f"https://www.youtube.com/watch?v={video_id}",
                                    source_title=title,
                                    content=td["tip"],
                                    tags=json.dumps(td.get("tags", [])),
                                    materials=json.dumps(td.get("materials", [])),
                                    printer_models=json.dumps(td.get("printers", [])),
                                )
                                session.add(tip)
                                await session.commit()
                                await session.refresh(tip)
                                await sync_fts(session, tip)
                                tips_added += 1
                    except (json.JSONDecodeError, ValueError):
                        continue

            except Exception:
                logger.exception("Failed to process channel: %s", channel_url)

    except Exception:
        logger.exception("YouTube scrape failed")

    logger.info("YouTube scrape complete: %d tips added", tips_added)

# External Integrations

## Bambu Lab Printer (MQTT + FTPS)

**Protocol:** MQTT over TLS (port 8883) + Implicit FTPS (port 990)
**Auth:** Username `bblp`, password = LAN Access Code from printer
**TLS:** Self-signed Bambu Lab CA cert, `verify=False` required

### MQTT (Status + Commands)
- **Subscribe:** `device/{SERIAL}/report` - real-time printer status
- **Publish:** `device/{SERIAL}/request` - print commands
- **Client:** `paho-mqtt` 2.1.0 with `MQTTv311` protocol
- **Threading:** Connection runs in daemon thread, callbacks bridge to asyncio event loop
- **Service:** Singleton `BambuMQTTService` at `backend/app/services/bambu_mqtt.py`
- **Features:** Status caching, subscriber pattern for WebSocket forwarding, print command with FTP URL

### FTPS (File Upload)
- **Protocol:** Implicit TLS FTPS (socket wrapped on connect, port 990)
- **Session reuse:** Required by Bambu printers (RFC 4217) - custom `_ImplicitFTP_TLS` class
- **Storage probe:** Tests `/`, `/sdcard/`, `/udisk/`, `/cache/` for writability
- **Diagnostic endpoint:** `POST /api/printers/{id}/diagnose-ftp` probes and auto-configures storage path
- **Service:** `backend/app/services/bambu_ftp.py`

## Google Gemini API

**Auth:** API key via `GEMINI_API_KEY` env var
**Model:** `gemini-3-flash-preview`
**SDK:** `google-genai` Python package

### Usage Points
| Feature | Location | Purpose |
|---------|----------|---------|
| Search query generation | `backend/app/services/ai_pipeline.py:generate_search_queries()` | Convert natural language to search queries |
| Result ranking | `backend/app/services/ai_pipeline.py:rank_results()` | Rank search results by relevance |
| OpenSCAD generation | `backend/app/services/ai_pipeline.py:generate_openscad()` | Generate parametric 3D model code |
| Blender script generation | `backend/app/services/ai_pipeline.py:generate_blender_script()` | Generate bpy Python scripts |
| Backend routing | `backend/app/services/ai_pipeline.py:route_generation_backend()` | Classify description as openscad vs blender |
| Knowledge synthesis | `backend/app/services/knowledge_base.py:ask_knowledge_base()` | Answer questions from tips DB |
| Reddit tip extraction | `backend/app/jobs/reddit_scraper.py` | Extract tips from Reddit posts |
| YouTube tip extraction | `backend/app/jobs/youtube_scraper.py` | Extract tips from video transcripts |

## MakerWorld / Bambu Lab Account

**Auth:** Bambu Lab API at `api.bambulab.com` (email/password login, token cached 60 days)
**Verification:** Email code verification flow supported via `POST /api/discover/makerworld/verify`
**Token storage:** `storage/browser_session/token.json`

### MakerWorld Integration
- **Search:** HTTP scraping with BeautifulSoup (`backend/app/services/discovery.py:search_makerworld()`)
- **Model page:** Playwright headless browser to bypass Cloudflare, extracts `__NEXT_DATA__` JSON
- **Download:** Three-strategy cascade:
  1. f3mf API endpoint (cookie auth via browser context)
  2. Network interception + download button click
  3. `expect_download()` direct file capture
- **Browser state:** Persisted to `storage/browser_session/state.json`
- **Service:** `backend/app/services/makerworld.py`

## Printables (GraphQL API)

**Endpoint:** `https://api.printables.com/graphql/`
**Auth:** None (public API)
**Query:** `SearchModels` / `searchPrintsV2` query
**Service:** `backend/app/services/discovery.py:search_printables()`

## ntfy.sh (Push Notifications)

**Server:** `https://ntfy.sh` (configurable via `NTFY_SERVER`)
**Topic:** `foundry-prints` (configurable via `NTFY_TOPIC`)
**Events:** `print_started`, `new_item_in_queue`
**Service:** `backend/app/services/notifications.py`

## Reddit (Knowledge Base Scraper)

**Endpoint:** `https://www.reddit.com/r/{subreddit}/hot.json`
**Subreddits:** `3Dprinting`, `BambuLab`, `functionalprint`
**Auth:** User-Agent header only (public JSON API)
**Filter:** Posts with 50+ upvotes
**Schedule:** Every 12 hours
**Service:** `backend/app/jobs/reddit_scraper.py`

## YouTube (Knowledge Base Scraper)

**Tool:** `yt-dlp` CLI for video listing + auto-subtitle download
**Channels:** CNCKitchen, MakersMuse, BambuLab, TeachingTech, 3DPrintingNerd
**Max videos:** 3 per channel
**Schedule:** Every 7 days
**Service:** `backend/app/jobs/youtube_scraper.py`

## BlenderMCP (Optional)

**Protocol:** HTTP to `poly-mcp` addon server
**Default URL:** `http://localhost:8000`
**Toggle:** `BLENDER_MCP_ENABLED=true` in `.env`
**Endpoints used:** `/mcp/list_tools` (health), `/mcp/invoke/execute_blender_code` (execution)
**Timeout:** 180s read timeout for code execution
**Service:** `backend/app/services/blender_mcp.py`
**Deploy:** Separate launchd plist `com.blender-mcp.plist`

## OpenSCAD (CLI)

**Path:** `/usr/local/bin/openscad` (configurable via `OPENSCAD_PATH`)
**Usage:** Compile `.scad` files to `.stl`
**Timeout:** 120 seconds
**Service:** `backend/app/services/generation.py:compile_openscad()`

## OrcaSlicer (CLI)

**Path:** `/Applications/OrcaSlicer.app/Contents/MacOS/orca-slicer` (configurable)
**Usage:** Slice `.stl` to `.3mf` with printer-specific profiles
**Profiles:** `backend/profiles/*.json` (currently placeholders)
**Timeout:** 120 seconds
**Service:** `backend/app/services/slicer.py`

# Technology Stack

## Languages & Runtimes

| Layer | Language | Version | Notes |
|-------|----------|---------|-------|
| Backend | Python | 3.12 (target), 3.14 in local venv | Python 3.13+ has TLS issues with Bambu self-signed certs |
| Frontend | TypeScript | 5.7.2 | Strict mode enabled |
| Frontend | React | 18.3.1 | SPA with client-side routing |
| Config | JSON, TOML | - | Slicer profiles, env config |

## Backend Framework & Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.115.6 | HTTP/WebSocket API framework |
| uvicorn | 0.34.0 | ASGI server |
| SQLAlchemy | >=2.0.40 | Async ORM (declarative mapped columns) |
| aiosqlite | 0.20.0 | Async SQLite driver |
| pydantic-settings | 2.7.1 | Environment config via `.env` |
| paho-mqtt | 2.1.0 | MQTT client for Bambu printer protocol |
| google-genai | >=1.0.0 | Gemini AI API (search queries, ranking, code generation, knowledge synthesis) |
| httpx | 0.28.1 | Async HTTP client |
| beautifulsoup4 | 4.12.3 | Web scraping (MakerWorld, Reddit) |
| playwright | 1.49.1 | Headless browser for MakerWorld download (Cloudflare bypass) |
| yt-dlp | 2024.12.23 | YouTube transcript extraction |
| trimesh | 4.5.3 | STL thumbnail generation |
| numpy-stl | 3.1.2 | STL bounding box / volume calculation |
| rectpack | 0.1 | 2D bin packing for plate optimizer |
| apscheduler | 3.10.4 | Background job scheduling |
| python-multipart | 0.0.20 | File upload handling |
| websockets | 14.1 | WebSocket support |
| aiofiles | 24.1.0 | Async file operations |
| cryptography | 44.0.0 | TLS/SSL support |

## Frontend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | 18.3.1 | UI framework |
| react-dom | 18.3.1 | DOM rendering |
| react-router-dom | 7.1.1 | Client-side routing |
| @tanstack/react-query | 5.62.0 | Data fetching, caching, mutations |
| vite | 6.0.5 | Build tool / dev server |
| tailwindcss | 3.4.17 | Utility-first CSS |
| typescript | 5.7.2 | Type checking |
| @vitejs/plugin-react | 4.3.4 | React Fast Refresh |
| autoprefixer | 10.4.20 | CSS vendor prefixes |
| postcss | 8.4.49 | CSS processing |

## External Tools (CLI Dependencies)

| Tool | Path | Purpose | Required |
|------|------|---------|----------|
| OpenSCAD | `/usr/local/bin/openscad` | Compile .scad to .stl | For AI generation |
| OrcaSlicer | `/Applications/OrcaSlicer.app/Contents/MacOS/orca-slicer` | Slice .stl to .3mf | For slicing pipeline |
| Blender (via BlenderMCP) | `http://localhost:8000` | Organic 3D model generation | Optional (disabled by default) |
| yt-dlp | system PATH | YouTube transcript download | For knowledge base |

## Database

- **Engine:** SQLite with WAL mode
- **Location:** `storage/foundry.db` (relative to backend dir)
- **Driver:** aiosqlite (async)
- **ORM:** SQLAlchemy 2.x with `Mapped` typed columns
- **FTS:** SQLite FTS5 virtual table for knowledge base search (`tips_fts`)
- **Migrations:** Manual PRAGMA-based column additions in `backend/app/database.py`

## Configuration

- **Method:** `pydantic-settings` BaseSettings with `.env` file
- **Config file:** `backend/app/config.py` -> `Settings` class
- **Template:** `.env.example` at project root
- **Key variables:** API token, printer IP/serial/access code, Gemini API key, ntfy topic, OrcaSlicer/OpenSCAD paths, Blender MCP toggle

## AI Models Used

| Model | Provider | Purpose | Location |
|-------|----------|---------|----------|
| `gemini-3-flash-preview` | Google | Search queries, ranking, OpenSCAD generation, Blender script generation, knowledge synthesis, tip extraction | `backend/app/services/ai_pipeline.py`, `backend/app/services/knowledge_base.py`, `backend/app/jobs/reddit_scraper.py`, `backend/app/jobs/youtube_scraper.py` |

**Note:** CLAUDE.md references claude-sonnet-4-6 and claude-opus-4-6 for AI models, but actual code uses `gemini-3-flash-preview` throughout. The config has `gemini_api_key` as the credential.

## Build & Deploy

- **Dev:** `make dev` (uvicorn + vite in parallel)
- **Build:** `make build` (Vite builds to `frontend/dist/`, served as static files by FastAPI)
- **Deploy:** `make deploy` (Vite build + launchd plist to `~/Library/LaunchAgents/`)
- **Sync:** `make sync` (rsync to Mac Mini at 100.123.8.125)
- **launchd plist:** `com.foundry.plist` (KeepAlive, RunAtLoad, port 8787)

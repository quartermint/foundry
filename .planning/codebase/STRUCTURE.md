# Directory Structure

## Root Layout

```
foundry/
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
├── CLAUDE.md                 # Project context for Claude Code
├── HANDOFF.md                # Deployment handoff notes
├── Makefile                  # Build/dev/deploy/sync commands
├── com.foundry.plist         # launchd plist for production
├── com.blender-mcp.plist     # launchd plist for BlenderMCP
├── .planning/                # GSD project management
│   └── codebase/             # Codebase mapping documents
├── backend/                  # Python FastAPI backend
├── frontend/                 # React TypeScript frontend
├── storage/                  # Runtime storage (gitignored)
└── logs/                     # Runtime logs (gitignored)
```

## Backend Structure

```
backend/
├── requirements.txt          # Python dependencies
├── profiles/                 # OrcaSlicer print profiles
│   ├── bambu_p2s_pla_0.4mm.json    # PLA profile (placeholder)
│   └── bambu_p2s_petg_0.4mm.json   # PETG profile (placeholder)
├── storage/                  # DB files (gitignored)
│   └── foundry.db            # SQLite database
└── app/
    ├── __init__.py
    ├── main.py               # FastAPI app, lifespan, router mounting
    ├── config.py             # Settings (pydantic-settings from .env)
    ├── database.py           # SQLAlchemy engine, session factory, migrations
    ├── auth.py               # Bearer token auth dependency
    ├── models/               # SQLAlchemy ORM models
    │   ├── __init__.py
    │   ├── printer.py        # Printer (ip, serial, access_code, bed size)
    │   ├── queue_item.py     # QueueItem (status machine, model/sliced paths)
    │   ├── print_job.py      # PrintJob (outcome, timing, filament usage)
    │   ├── tip.py            # Tip (knowledge base entry from scrapers)
    │   └── discovery_result.py # DiscoveryResult (cached trending models)
    ├── routers/              # FastAPI route handlers
    │   ├── __init__.py
    │   ├── printers.py       # CRUD + upload/print/diagnose (9 routes)
    │   ├── ws.py             # WebSocket printer status (1 WS endpoint)
    │   ├── queue.py          # Queue CRUD + upload/send (6 routes)
    │   ├── history.py        # Print history list/get (2 routes)
    │   ├── discovery.py      # Search + add-to-queue + MakerWorld (6 routes)
    │   ├── knowledge.py      # Ask + search knowledge base (2 routes)
    │   ├── generate.py       # AI model generation + iteration (2 routes)
    │   └── plate.py          # Plate optimization (1 route)
    ├── services/             # Business logic services
    │   ├── __init__.py
    │   ├── bambu_mqtt.py     # MQTT client singleton (connect/disconnect/status/print)
    │   ├── bambu_ftp.py      # Implicit FTPS upload + diagnostics
    │   ├── ai_pipeline.py    # Gemini: search queries, ranking, code generation
    │   ├── discovery.py      # MakerWorld + Printables search
    │   ├── makerworld.py     # Playwright browser: login, metadata, .3mf download
    │   ├── generation.py     # Full gen pipeline: AI → compile → slice → thumbnail
    │   ├── knowledge_base.py # FTS5 search + Gemini synthesis
    │   ├── slicer.py         # OrcaSlicer CLI wrapper
    │   ├── thumbnail.py      # STL thumbnail + info (trimesh)
    │   ├── plate_optimizer.py # 2D bin packing (rectpack)
    │   ├── blender_mcp.py    # BlenderMCP HTTP client
    │   └── notifications.py  # ntfy.sh push notifications
    └── jobs/                 # Background scheduled jobs
        ├── __init__.py
        ├── scheduler.py      # APScheduler setup (3 jobs)
        ├── reddit_scraper.py # Reddit tip extraction (every 12h)
        ├── youtube_scraper.py # YouTube transcript tips (every 7d)
        └── makerworld_trending.py # Trending models cache (every 24h)
```

## Frontend Structure

```
frontend/
├── package.json              # Dependencies + scripts
├── package-lock.json
├── tsconfig.json             # TypeScript strict config
├── tsconfig.node.json        # Node TypeScript config
├── vite.config.ts            # Vite + proxy config
├── vite-env.d.ts             # Vite env type declarations
├── postcss.config.js         # PostCSS (Tailwind)
├── tailwind.config.js        # Tailwind configuration
├── index.html                # HTML entry point
├── dist/                     # Vite build output (gitignored)
└── src/
    ├── main.tsx              # App bootstrap (React, Router, QueryClient)
    ├── App.tsx               # Route definitions (6 routes)
    ├── index.css             # Global styles (Tailwind directives)
    ├── api/
    │   └── client.ts         # HTTP fetch wrapper with Bearer auth
    ├── components/
    │   ├── Sidebar.tsx       # Collapsible nav sidebar (6 items)
    │   └── PrinterStatus.tsx # Real-time printer card with temps/progress
    ├── hooks/
    │   └── usePrinterStatus.ts # WebSocket hook for printer status
    └── pages/
        ├── Dashboard.tsx     # Printer grid with live status
        ├── Discover.tsx      # Community search + AI generation
        ├── Queue.tsx         # Upload drop zone + queue management
        ├── History.tsx       # Print history table with pagination
        ├── Knowledge.tsx     # Chat interface for knowledge base
        └── Settings.tsx      # API token + printer CRUD form
```

## Storage Layout (Runtime)

```
storage/
├── foundry.db                # SQLite database
├── models/                   # Uploaded/generated STL/3mf files
├── sliced/                   # OrcaSlicer output .3mf files
├── thumbnails/               # Generated PNG thumbnails
└── browser_session/          # Playwright state + Bambu Lab token
    ├── token.json            # Cached auth token
    └── state.json            # Browser cookies/localStorage
```

## Key File Locations

| What | Path |
|------|------|
| App entry | `backend/app/main.py` |
| Config | `backend/app/config.py` |
| Database setup | `backend/app/database.py` |
| MQTT service | `backend/app/services/bambu_mqtt.py` |
| FTP service | `backend/app/services/bambu_ftp.py` |
| AI pipeline | `backend/app/services/ai_pipeline.py` |
| Generation pipeline | `backend/app/services/generation.py` |
| MakerWorld browser | `backend/app/services/makerworld.py` |
| Slicer profiles | `backend/profiles/*.json` |
| Frontend API client | `frontend/src/api/client.ts` |
| WebSocket hook | `frontend/src/hooks/usePrinterStatus.ts` |
| Env template | `.env.example` |
| Deploy plist | `com.foundry.plist` |
| Makefile | `Makefile` |

## Naming Conventions

- **Backend:** snake_case for everything (files, functions, variables)
- **Frontend:** PascalCase components, camelCase functions/variables, kebab-case file imports where needed
- **Routes:** `/api/{resource}` for REST, `/ws/{resource}` for WebSocket
- **Models:** Singular class names (Printer, QueueItem, PrintJob, Tip, DiscoveryResult)
- **Routers:** Named by resource (printers.py, queue.py, etc.)
- **Services:** Named by integration/domain (bambu_mqtt.py, ai_pipeline.py, etc.)

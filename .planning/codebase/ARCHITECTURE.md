# Architecture

## System Overview

Foundry is a full-stack web application for managing Bambu Lab 3D printers. It combines real-time printer monitoring (MQTT), AI-powered model discovery and generation (Gemini), community search (MakerWorld/Printables), and a print queue management system.

```
┌──────────────────────────────────────┐
│  React SPA (Vite)                    │
│  Dashboard / Discover / Queue /      │
│  History / Knowledge / Settings      │
│         ↕ HTTP + WebSocket           │
├──────────────────────────────────────┤
│  FastAPI Backend (uvicorn :8787)     │
│  ┌─────────┐ ┌──────────────────┐   │
│  │ Routers │ │ Services         │   │
│  │ (8)     │→│ MQTT, FTP, AI,   │   │
│  │         │ │ Discovery, Slicer│   │
│  └─────────┘ └──────────────────┘   │
│  ┌─────────┐ ┌──────────────────┐   │
│  │ Models  │ │ Background Jobs  │   │
│  │ (5)     │ │ Reddit, YouTube, │   │
│  └────┬────┘ │ Trending         │   │
│       │      └──────────────────┘   │
│       ↓                             │
│  SQLite WAL (storage/foundry.db)    │
└──────────────────────────────────────┘
         ↕ MQTT :8883          ↕ FTPS :990
┌──────────────────────────────────────┐
│  Bambu Lab P2S Printer               │
└──────────────────────────────────────┘
```

## Architectural Pattern

**Backend:** Service-oriented with FastAPI dependency injection. Routers handle HTTP, services encapsulate business logic, models define SQLAlchemy ORM entities. No formal layering beyond router -> service -> model.

**Frontend:** React SPA with TanStack Query for server state management. Pages map 1:1 to routes. Components are presentational with hooks for data fetching.

**Communication:**
- HTTP REST for CRUD operations
- WebSocket for real-time printer status (MQTT -> backend -> WS -> frontend)
- Vite dev proxy forwards `/api/*` and `/ws/*` to backend

## Data Flow

### Print Queue Lifecycle
```
Upload/Discover/Generate
        ↓
  pending_approval
        ↓
  approved ─────→ rejected
        ↓
  [slicing] (auto for STL uploads)
        ↓
  ready
        ↓
  printing (FTPS upload → MQTT print command)
        ↓
  completed / failed
```

### AI Generation Pipeline
```
User Description
      ↓
route_generation_backend() → "openscad" or "blender"
      ↓
generate_openscad() / generate_blender_script()  (Gemini AI)
      ↓
compile_openscad() / execute_blender_script()     (CLI/MCP)
      ↓
.stl file
      ↓
generate_thumbnail()    (trimesh)
      ↓
slice_stl()             (OrcaSlicer CLI → .3mf)
      ↓
QueueItem (pending_approval)
```

### AI Discovery Pipeline
```
User Description
      ↓
generate_search_queries()  (Gemini → 3-5 queries)
      ↓
search_all()  (MakerWorld scraping + Printables GraphQL, parallel)
      ↓
rank_results()  (Gemini ranking)
      ↓
Display results → user selects → add_to_queue()
```

### Knowledge Base Pipeline
```
Background Jobs (Reddit/YouTube scrapers)
      ↓ every 12h / 7d
Extract tips via Gemini
      ↓
Tip model → tips table + FTS5 index
      ↓
User asks question
      ↓
FTS5 search → top 20 tips
      ↓
Gemini synthesis → answer with citations
```

## Key Abstractions

### Singleton Services
- `mqtt_service` - Global MQTT client manager (`BambuMQTTService`)
- `blender_mcp` - BlenderMCP HTTP client (`BlenderMCPClient`)
- `settings` - Global config from env (`Settings`)

### Database Session
- Async session factory via `async_session_factory`
- FastAPI dependency `get_session` for per-request sessions
- Direct `async_session_factory()` context manager for background jobs

### Auth
- Bearer token auth (`require_token` dependency)
- WebSocket uses `?token=` query parameter
- Token stored in `localStorage` on frontend, checked against `FOUNDRY_API_TOKEN` env var

## Entry Points

| Entry Point | File | Purpose |
|-------------|------|---------|
| Backend app | `backend/app/main.py` | FastAPI app with lifespan (init DB, connect MQTT, start scheduler) |
| Frontend app | `frontend/src/main.tsx` | React root with BrowserRouter + QueryClient |
| Dev servers | `Makefile:dev` | uvicorn (--reload) + vite dev server |
| Production | `com.foundry.plist` | launchd: uvicorn serves API + static frontend |
| Sync deploy | `Makefile:sync` | rsync to Mac Mini |

## Static File Serving

In production, FastAPI mounts `frontend/dist/` as static files at `/` with `html=True` (SPA fallback). In development, Vite proxies API/WS calls to the backend.

Storage files (thumbnails, models, sliced) are under `storage/` but NOT served by the backend. The frontend references them via `/storage/thumbnails/{filename}` paths which would need a static mount or reverse proxy to work in production.

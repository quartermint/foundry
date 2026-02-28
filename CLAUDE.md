# Foundry - Bambu Lab AI Print Management Suite

## Overview
Always-on service for AI-powered 3D print management with Bambu Lab printers.

## Stack
- **Backend:** Python 3.11+ / FastAPI / SQLAlchemy async / SQLite WAL
- **Frontend:** React 18 / TypeScript / Vite / TailwindCSS
- **Printer Protocol:** MQTT (8883) + FTPS (990) over TLS (self-signed BBL CA)
- **Port:** 8787 (API), 5175 (Vite dev)

## Quick Start
```bash
make setup    # Create venvs, install deps
make dev      # Backend :8787 + Frontend :5175
make build    # Vite build → frontend/dist/
make deploy   # Build + launchd load
```

## Architecture
- `backend/app/` - FastAPI application
- `backend/app/services/bambu_mqtt.py` - MQTT client for printer communication
- `backend/app/services/bambu_ftp.py` - FTPS file upload to printer
- `frontend/src/` - React SPA
- `storage/` - SQLite DB, model files, sliced .3mf files, thumbnails

## Bambu Protocol Notes
- Enable Developer Mode on printer touchscreen first
- Auth: username `bblp`, password = LAN Access Code
- MQTT topics: `device/{SERIAL}/report` (sub), `device/{SERIAL}/request` (pub)
- TLS uses self-signed cert — verify=False required
- Python 3.13+ may have TLS issues — use 3.11 or 3.12

## Database
SQLite with WAL mode at `storage/foundry.db`. Tables: printers, queue_items, print_jobs, tips, discovery_results.

## Auth
Bearer token in .env (FOUNDRY_API_TOKEN). All /api/ routes require it. WebSocket uses ?token= query param.

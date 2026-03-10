# Foundry

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI-powered 3D print management suite for Bambu Lab printers.

## The Problem

Managing a Bambu Lab printer workflow means juggling multiple tools: browsing model sites, slicing files, queueing prints, monitoring progress, and tracking history. There is no unified interface that ties discovery, preparation, and printing together -- let alone one that can generate custom models on demand.

## Features

**Discovery and Generation**
- Search MakerWorld and Printables from a single interface
- AI-powered model generation: describe what you need, get a printable STL (Claude + OpenSCAD/Blender pipeline)
- Thumbnail generation and model preview

**Print Management**
- Drag-and-drop upload queue with approve/reject workflow
- Real-time printer status via WebSocket (temperatures, progress, current layer)
- Print history with pagination and filtering
- Multi-printer support with MQTT communication

**Intelligence**
- Knowledge base with full-text search across tips, notes, and printing guides
- AI-synthesized answers from your knowledge base (Claude API)
- Smart plate optimization for multi-part prints

**Operations**
- Live dashboard with WebSocket printer telemetry
- Printer settings management (add, configure, test connection)
- Background jobs for slicing, discovery, and notifications
- Single-port deployment (API serves frontend static files)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12 / FastAPI / SQLAlchemy async |
| Database | SQLite with WAL mode |
| Frontend | React 18 / TypeScript / Vite / Tailwind CSS |
| Printer Protocol | MQTT (TLS :8883) + FTPS (:990) via Bambu Lab LAN API |
| AI Models | Claude API (search ranking, OpenSCAD generation) |
| Slicer | OrcaSlicer CLI (STL to .3mf) |
| 3D Engine | OpenSCAD / Blender (headless, for AI generation pipeline) |
| Deployment | macOS launchd / single binary on :8787 |

## Quick Start

```bash
git clone https://github.com/quartermint/foundry.git
cd foundry

# Setup
make setup              # Create venvs, install deps

# Configure
cp backend/.env.example backend/.env
# Edit .env with your printer IP, LAN access code, and API keys

# Development
make dev                # Backend :8787 + Frontend :5175

# Production build
make build              # Vite build -> frontend/dist/, served by FastAPI on :8787
make deploy             # Build + launchd service
```

### Prerequisites

- Python 3.12 (3.13+ may have TLS issues with Bambu self-signed certs)
- Node.js 18+
- Bambu Lab printer with **Developer Mode enabled** on the touchscreen
- OrcaSlicer installed (for slicing pipeline)

## Project Structure

```
foundry/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry
│   │   ├── routers/             # 8 API routers (30 routes)
│   │   │   ├── ws.py             # WebSocket printer telemetry
│   │   │   ├── queue.py         # Print queue management
│   │   │   ├── discovery.py     # Model search (MakerWorld, Printables)
│   │   │   ├── generate.py      # AI model generation
│   │   │   ├── history.py       # Print history
│   │   │   ├── knowledge.py     # Knowledge base + AI synthesis
│   │   │   ├── printers.py      # Printer CRUD + connection test
│   │   │   └── plate.py         # Plate optimization
│   │   └── services/            # Business logic
│   │       ├── bambu_mqtt.py    # MQTT client for printer communication
│   │       ├── bambu_ftp.py     # FTPS file upload to printer
│   │       ├── discovery.py     # MakerWorld/Printables scraping
│   │       ├── generation.py    # AI CAD generation pipeline
│   │       ├── slicer.py        # OrcaSlicer CLI integration
│   │       ├── knowledge_base.py # FTS5 knowledge search
│   │       └── ...
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/               # Dashboard, Queue, Discover, History,
│       │                        # Knowledge, Settings
│       └── components/          # Shared UI components
├── storage/                     # SQLite DB, models, thumbnails
├── Makefile                     # Setup, dev, build, deploy, sync
└── com.foundry.plist            # macOS launchd service definition
```

## API Overview

All routes require Bearer token authentication (configured in `.env`).

| Endpoint Group | Description |
|---------------|-------------|
| `GET /api/health` | Health check |
| `/api/dashboard/*` | Live printer status, WebSocket telemetry |
| `/api/queue/*` | Upload, approve, reject, send to printer |
| `/api/discover/*` | Search MakerWorld/Printables, AI generation |
| `/api/generate/*` | AI model generation pipeline status |
| `/api/history/*` | Print job history with pagination |
| `/api/knowledge/*` | Knowledge base CRUD, AI synthesis |
| `/api/printers/*` | Printer management, connection testing |
| `/api/plate/*` | Multi-part plate optimization |

## Roadmap

- [ ] Deploy to always-on Mac Mini server
- [ ] Real OrcaSlicer profile exports (current profiles are placeholders)
- [ ] First end-to-end test print
- [ ] Print time estimation and filament usage tracking
- [ ] Multi-printer job scheduling
- [ ] Notification system (print complete, errors)

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the backend and frontend to verify
5. Open a pull request

## License

[MIT](LICENSE) -- see LICENSE for details.

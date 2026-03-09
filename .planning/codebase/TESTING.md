# Testing

## Current State

**No tests exist.** There are no test files, test directories, test configurations, or testing dependencies in the project.

## What Would Be Needed

### Backend Testing
- **Framework:** pytest + pytest-asyncio (not in requirements.txt)
- **HTTP testing:** httpx.AsyncClient with FastAPI TestClient
- **Database:** In-memory SQLite for isolation
- **Mocking:** unittest.mock or pytest-mock for external services (MQTT, Gemini API, FTPS, Playwright)

### Key Areas to Test

**Unit tests (highest priority):**
- `backend/app/services/ai_pipeline.py` - JSON parsing from Gemini responses
- `backend/app/services/generation.py` - Pipeline orchestration and retry logic
- `backend/app/services/plate_optimizer.py` - 2D bin packing correctness
- `backend/app/services/thumbnail.py` - STL info extraction
- `backend/app/routers/queue.py` - Status transition validation logic

**Integration tests:**
- Router endpoints with mocked services
- Database operations (CRUD, migrations)
- Queue item status machine transitions

**Hard to test (external dependencies):**
- MQTT connection/messaging (requires real printer or mock broker)
- FTPS upload (requires printer or FTP server mock)
- MakerWorld Playwright browser automation
- OrcaSlicer CLI slicing
- OpenSCAD compilation

### Frontend Testing
- **Framework:** Vitest + React Testing Library (not in package.json)
- **Key areas:** API client error handling, status badge rendering, WebSocket reconnection logic

## Test Infrastructure Gaps

- No `pytest.ini`, `pyproject.toml`, or `setup.cfg` with test configuration
- No `conftest.py` fixtures
- No test database fixture
- No CI/CD pipeline
- No test coverage tooling
- No mocking infrastructure for external APIs

## Quality Assurance

Currently quality is assured by:
- TypeScript strict mode catches type errors at build time
- Python type hints provide IDE-level checking
- Manual testing during development
- `noqa: E712` comments indicate awareness of linting

# Concerns & Technical Debt

## Critical (Must Fix Before Production)

### 1. Python Version Mismatch
- **Location:** `backend/.venv/` (local venv)
- **Issue:** Local venv is Python 3.14, but `__pycache__` shows both 3.12 and 3.14 bytecode. Python 3.13+ may have TLS issues with Bambu Lab's self-signed certificates. The Makefile targets Python 3.12 (`python3.12 -m venv .venv`).
- **Fix:** Rebuild venv with Python 3.12 on Mac Mini deployment

### 2. OrcaSlicer Profiles Are Placeholders
- **Location:** `backend/profiles/bambu_p2s_pla_0.4mm.json`, `backend/profiles/bambu_p2s_petg_0.4mm.json`
- **Issue:** Both profiles contain placeholder values with a `_comment` field noting they need real exports from OrcaSlicer GUI. The slicer will run but produce suboptimal results.
- **Fix:** Export real profiles from OrcaSlicer (File > Export > Export Config)

### 3. Storage Files Not Served in Production
- **Location:** `backend/app/main.py` (static mount), `frontend/src/pages/Queue.tsx` (thumbnail references)
- **Issue:** Frontend references thumbnails via `/storage/thumbnails/{filename}` but the backend only mounts `frontend/dist/` as static. The `storage/` directory is NOT served. Thumbnails will 404 in production.
- **Fix:** Add a static file mount for storage, or serve thumbnails through an API endpoint

### 4. CORS Wide Open
- **Location:** `backend/app/main.py`
- **Issue:** `allow_origins=["*"]` with `allow_credentials=True`. This is acceptable for local development but not for any network-exposed deployment.
- **Fix:** Restrict origins to actual frontend URL in production

## High Priority

### 5. No Database Migrations System
- **Location:** `backend/app/database.py:_run_migrations()`
- **Issue:** Schema migrations are manual PRAGMA checks + ALTER TABLE statements. No Alembic or migration framework. Adding new columns requires manual migration code.
- **Impact:** Risky for schema evolution, no rollback capability

### 6. Access Code Exposed in API Response
- **Location:** `backend/app/models/printer.py:to_dict()`
- **Issue:** The `to_dict()` method does NOT include `access_code`, which is correct. However, the printer creation response returns the full dict. The `access_code` column stores the LAN Access Code in plaintext.
- **Impact:** Low risk since auth is required, but access codes should ideally be masked

### 7. MakerWorld Scraping Fragility
- **Location:** `backend/app/services/discovery.py:search_makerworld()`, `backend/app/services/makerworld.py`
- **Issue:** MakerWorld search relies on CSS selectors (`[class*='model-card']`, `a[href*='/models/']`) that will break if MakerWorld changes their HTML. The Playwright-based download uses a 3-strategy cascade because their API is undocumented.
- **Impact:** Community search/download may break without notice

### 8. AI Model Reference Inconsistency
- **Location:** `CLAUDE.md` says claude-sonnet/opus, but `backend/app/services/ai_pipeline.py` uses `gemini-3-flash-preview`
- **Issue:** Documentation references Claude models for search/ranking/generation, but all AI code uses Gemini. The `.env.example` only has `GEMINI_API_KEY`.
- **Impact:** Confusion, but no functional issue

## Medium Priority

### 9. No Test Suite
- **Impact:** No automated quality assurance. Changes to AI pipeline, queue logic, or printer communication could introduce regressions undetected.

### 10. Singleton MQTT Threading Model
- **Location:** `backend/app/services/bambu_mqtt.py`
- **Issue:** MQTT connection runs in daemon threads. Callbacks bridge to asyncio via `loop.call_soon_threadsafe(asyncio.ensure_future, ...)`. The loop reference (`self._loop`) could go stale. The `_get_loop()` fallback to `get_event_loop()` may not work correctly in all scenarios.
- **Impact:** Potential for lost MQTT messages or event loop errors under edge cases

### 11. Background Job Error Isolation
- **Location:** `backend/app/jobs/reddit_scraper.py`, `youtube_scraper.py`
- **Issue:** Reddit scraper creates a new Gemini client per post extraction. YouTube scraper creates a new client per video. Both do `await session.commit()` per tip, so a failure mid-batch leaves partial results.
- **Impact:** Inefficient API usage, possible partial data states

### 12. File Cleanup Not Implemented
- **Location:** `storage/models/`, `storage/sliced/`, `storage/thumbnails/`
- **Issue:** Generated/uploaded files are never cleaned up when queue items are deleted. The `delete_queue_item` handler deletes the DB row but not associated files.
- **Impact:** Storage grows unbounded over time

### 13. Settings Frontend Field Mismatch
- **Location:** `frontend/src/pages/Settings.tsx`
- **Issue:** Frontend uses field names like `nozzle_size`, `bed_width`, `bed_depth`, `materials`, but the backend API uses `nozzle_mm`, `bed_x_mm`, `bed_y_mm`, `capable_materials`. The Settings form may not correctly create/edit printers.
- **Impact:** Printer creation/editing from the UI may fail or send wrong field names

## Low Priority

### 14. Duplicate Storage Path Constants
- Multiple routers and services independently define `STORAGE`, `MODELS_DIR`, `SLICED_DIR`, `THUMBS_DIR` from `Path(__file__).resolve()`. Should be centralized.

### 15. WebSocket Keepalive Sends Raw JSON
- **Location:** `backend/app/routers/ws.py`
- **Issue:** Sends `{"type": "ping"}` which the frontend `usePrinterStatus` hook parses as a `PrinterStatus` object, potentially setting bad state. The hook should filter ping messages.

### 16. FTS5 Content Sync
- **Location:** `backend/app/services/knowledge_base.py`
- **Issue:** FTS5 is configured as a content table (`content='tips', content_rowid='id'`) but inserts use `INSERT OR REPLACE` directly. Deletions from the tips table won't be reflected in FTS. Should use triggers or explicit delete+rebuild.

### 17. `__pycache__` Tracked by Git
- **Location:** Various `__pycache__/` directories visible in file listing
- **Issue:** `.gitignore` has `__pycache__/` and `*.py[cod]` rules, but pycache files appear in the tree. May need `git rm -r --cached` to clean up already-tracked files.

## Security Considerations

- **TLS verification disabled** for Bambu printer connections (expected behavior, self-signed certs)
- **Bearer token auth** is single-token, no user system, no token rotation
- **MakerWorld credentials** stored in `.env` (plaintext)
- **No rate limiting** on API endpoints
- **No input sanitization** on file paths (model_path, sliced_path stored as absolute paths from server filesystem)

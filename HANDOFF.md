# Foundry — Session Handoff

## Current State (2026-03-01)

### What Works
- **MakerWorld .3mf download: FIXED** — Strategy A (f3mf API) confirmed working
  - Endpoint: `GET /api/v1/design-service/instance/{instance_id}/f3mf?type=download`
  - Called via `page.evaluate(fetch(..., {credentials: "include"}))` — cookie auth, NOT Bearer token
  - Returns JSON: `{"name": "...", "url": "https://makerworld.bblmw.com/...presigned...3mf"}`
  - CDN URL downloaded via httpx: 2MB valid .3mf file
- **Queue item creation:** model_path + sliced_path both set for pre-sliced .3mf
- **Playwright browser:** Bypasses Cloudflare, auth token injected as cookie
- **MQTT:** Connected, receiving live status from printer
- **Debug endpoint:** `GET /api/discover/makerworld/debug-download/{design_id}/{instance_id}` — returns API probe results + network log

### What's Broken: File Upload to P2S Printer

**Root cause:** Printer is a **Bambu Lab P2S** (internal model code `N7`), NOT a P1S. The P2S has **no SD card** — it uses **internal eMMC storage**. FTP STOR fails with `553 Could not create file` on ALL paths (root, /cache/, /sdcard/, etc.).

**The P2S does NOT support traditional FTP file uploads.** OrcaSlicer source confirms:
- P1S/P1P/A1 have `ftp_folder: "sdcard/"` — FTP works
- P2S (N7) has **no `ftp_folder`** — uses `FileTransferTunnel` on **port 6000** instead
- Protocol: `bambu:///local/{ip}?port=6000&user=bblp&passwd={access_code}`
- Implemented in OrcaSlicer's `FileTransferTunnel` C++ class

**What was already fixed this session (committed locally, deployed to Mac Mini):**
1. `accept_downloads: True` in Playwright browser context
2. Three-strategy download cascade in `makerworld.py` (f3mf API → network intercept → expect_download)
3. Debug endpoint for remote diagnostics
4. FTP TLS session reuse (`ntransfercmd` override) — fixes `522 SSL session reuse required`
5. FTP `/cache/` path with root fallback
6. `upload_file()` returns remote path string (not bool) for correct MQTT URL
7. MQTT `send_print_command` uses full remote path in `ftp://` URL
8. `sliced_path` auto-set for MakerWorld .3mf downloads
9. DB printer model corrected from "P1S" to "P2S"

## Task for Next Session: Implement Port 6000 File Transfer

### Research Needed
The P2S uses a proprietary binary protocol on port 6000 for file uploads. Key sources to investigate:

1. **OrcaSlicer `FileTransferTunnel` class** — the authoritative implementation
   - Repo: `OrcaSlicer/OrcaSlicer` (new org) or `SoftFever/OrcaSlicer`
   - File: Search for `FileTransferTunnel` in `src/slic3r/`
   - URL scheme: `bambu:///local/{ip}?port=6000&user=bblp&passwd={access_code}`
   - Called from `PrintJob.cpp` when `could_emmc_print` is true

2. **BambuStudio source** — may have an earlier/simpler implementation
   - Repo: `bambulab/BambuStudio`

3. **Community Python implementations** — search for:
   - `bambu_networking` Python bindings
   - `pybambu` library
   - Any Python port 6000 implementations

4. **Protocol details to discover:**
   - Is it a custom binary protocol or HTTP/WebSocket?
   - Authentication mechanism (TLS? access code?)
   - File transfer framing (chunked? streaming?)
   - How does the printer acknowledge receipt?
   - What MQTT command starts the print after tunnel upload?

### Implementation Plan (once protocol is understood)
1. Add `bambu_tunnel.py` service — implements port 6000 file transfer
2. Update `upload_file()` in `bambu_ftp.py` to detect printer type and route:
   - SD card printers → FTP on port 990 (existing code)
   - eMMC printers (P2S, X1C, X1E, H2D) → tunnel on port 6000
3. Update MQTT print command URL format if tunnel uses different scheme
4. Add printer capability field (`storage_type: "sdcard" | "emmc"`) to DB model

### Alternative: Bambu Cloud API
If port 6000 is too complex to reverse-engineer in Python, consider:
- Upload .3mf to Bambu Cloud via their API
- Trigger cloud print to the printer
- Simpler but requires cloud connectivity (no LAN-only mode)

## Printer Details
- **Model:** Bambu Lab P2S (OrcaSlicer code: N7)
- **IP:** 192.168.4.28 (local network from Mac Mini)
- **Serial:** 22E8AJ610301371
- **Access Code:** 28e93e33
- **DB ID:** 1 (model field now correctly "P2S")
- **Storage:** Internal eMMC (no SD card, `sdcard: false` is expected)
- **AMS:** Slot 0 = white PLA, Slot 1 = black PETG HF

## Test Commands
```bash
# API token
FOUNDRY_TOKEN=c305ce7595c66c96ba478720b82d6559309b48ac9ed71f2921c6641c9d63f823

# Sync + restart
make sync && make restart-remote

# Health check
curl -s http://100.123.8.125:8787/api/health

# Test MakerWorld download (WORKS)
curl -s -X POST http://100.123.8.125:8787/api/discover/makerworld/download \
  -H "Authorization: Bearer $FOUNDRY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"design_id": 1107679, "instance_id": 2522009, "profile_id": 585600731}'

# Test send to printer (FAILS — needs port 6000 tunnel)
curl -s -X POST http://100.123.8.125:8787/api/queue/1/send \
  -H "Authorization: Bearer $FOUNDRY_TOKEN"

# View logs
ssh 100.123.8.125 "tail -50 ~/foundry/logs/stderr.log"
```

## Key Files
- `backend/app/services/bambu_ftp.py` — FTP upload (works for SD card printers, needs tunnel for eMMC)
- `backend/app/services/bambu_mqtt.py` — MQTT client + print command
- `backend/app/services/makerworld.py` — MakerWorld download (3 strategies, working)
- `backend/app/routers/queue.py` — Queue management + send-to-printer flow
- `backend/app/routers/discovery.py` — MakerWorld endpoints + debug
- `backend/app/models/printer.py` — Printer DB model (needs storage_type field)

## Critical Lessons
- P2S = N7 in OrcaSlicer config, no `ftp_folder`, uses eMMC
- P2S FTP server accepts connections + auth but rejects ALL writes (553)
- `sdcard: false` is EXPECTED for P2S — not a hardware problem
- Bambu TLS requires session reuse on data channels (ntransfercmd override)
- MakerWorld f3mf API uses cookie auth (credentials: "include"), NOT Bearer token
- MakerWorld old download API (`/download/designId/...`) returns 404 — dead endpoint
- NEVER rsync WAL/SHM files while Foundry is running

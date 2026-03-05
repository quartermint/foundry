"""MakerWorld download service using Playwright headless browser.

MakerWorld is fully behind Cloudflare, returning 403 on all programmatic HTTP
access. This service uses Playwright headless Chromium to:
1. Login via Bambu Lab API (token cached ~2 months on disk)
2. Navigate model pages and extract __NEXT_DATA__ metadata
3. Download .3mf files via authenticated browser requests

The browser context persists session state (cookies, localStorage) across
restarts via storage_state saved to disk.
"""

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, BrowserContext

from app.config import settings

logger = logging.getLogger(__name__)

BAMBU_API = "https://api.bambulab.com"
MAKERWORLD = "https://makerworld.com"

STORAGE = Path(__file__).resolve().parent.parent.parent / "storage"
MODELS_DIR = STORAGE / "models"
THUMBS_DIR = STORAGE / "thumbnails"
SESSION_DIR = STORAGE / "browser_session"
TOKEN_FILE = SESSION_DIR / "token.json"
STATE_FILE = SESSION_DIR / "state.json"

# Singleton Playwright state
_pw = None
_browser = None
_context: BrowserContext | None = None
_init_lock = asyncio.Lock()

# Pending verification code (set via verify_login_code endpoint)
_pending_verify: dict = {}


# ---------------------------------------------------------------------------
# Token management (Bambu Lab API — not behind Cloudflare)
# ---------------------------------------------------------------------------

def _load_token() -> str | None:
    """Load cached Bambu Lab access token from disk."""
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            if data.get("access_token") and time.time() < data.get("expires_at", 0):
                return data["access_token"]
        except Exception:
            pass
    return None


def _save_token(token: str, expires_in: int = 60 * 24 * 3600):
    """Save token to disk (default 60-day cache)."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "access_token": token,
        "expires_at": time.time() + expires_in,
    }))


async def login_bambu() -> str:
    """Login to Bambu Lab API and return access token.

    The API at api.bambulab.com is not behind Cloudflare, so direct HTTP works.
    Token is cached to disk for ~2 months (tokens valid ~3 months).

    If the login requires a verification code, raises ValueError with
    instructions to call verify_login_code().
    """
    cached = _load_token()
    if cached:
        return cached

    if not settings.makerworld_email or not settings.makerworld_password:
        raise ValueError("MAKERWORLD_EMAIL and MAKERWORLD_PASSWORD must be set")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BAMBU_API}/v1/user-service/user/login",
            json={
                "account": settings.makerworld_email,
                "password": settings.makerworld_password,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    logger.info("Bambu Lab login response: %s", json.dumps(data)[:500])

    token = data.get("accessToken")
    if token:
        _save_token(token)
        logger.info("Bambu Lab login successful, token cached")
        return token

    # May need email verification code
    login_type = data.get("loginType")
    if login_type == "verifyCode" or "verify" in str(data).lower():
        _pending_verify["account"] = settings.makerworld_email
        _pending_verify["response"] = data
        raise ValueError(
            "Bambu Lab requires email verification. Check email for code, "
            "then POST /api/discover/makerworld/verify with {\"code\": \"123456\"}. "
            f"API response: {json.dumps(data)[:300]}"
        )

    raise ValueError(f"Bambu Lab login failed: {json.dumps(data)[:500]}")


async def verify_login_code(code: str) -> str:
    """Complete Bambu Lab login with email verification code."""
    account = _pending_verify.get("account", settings.makerworld_email)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BAMBU_API}/v1/user-service/user/login",
            json={
                "account": account,
                "code": code,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    token = data.get("accessToken")
    if not token:
        raise ValueError(f"Verification failed: {json.dumps(data)[:500]}")

    _save_token(token)
    _pending_verify.clear()
    logger.info("Bambu Lab verification successful, token cached")
    return token


# ---------------------------------------------------------------------------
# Playwright browser management
# ---------------------------------------------------------------------------

async def _get_context() -> BrowserContext:
    """Get or create a persistent Playwright browser context."""
    global _pw, _browser, _context

    async with _init_lock:
        if _context:
            try:
                _ = _context.pages  # verify alive
                return _context
            except Exception:
                _context = None
                _browser = None
                _pw = None

        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch(headless=True)

        ctx_kwargs = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 720},
            "accept_downloads": True,
        }
        if STATE_FILE.exists():
            ctx_kwargs["storage_state"] = str(STATE_FILE)

        _context = await _browser.new_context(**ctx_kwargs)
        logger.info("Playwright browser context created")
        return _context


async def _save_state():
    """Persist browser cookies and storage to disk."""
    if _context:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        await _context.storage_state(path=str(STATE_FILE))


async def _inject_token(token: str):
    """Inject Bambu Lab auth token as cookies into browser context."""
    ctx = await _get_context()
    await ctx.add_cookies([
        {
            "name": "token",
            "value": token,
            "domain": ".makerworld.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
        },
    ])
    await _save_state()


async def shutdown_browser():
    """Clean up Playwright resources. Call on app shutdown."""
    global _pw, _browser, _context
    if _context:
        try:
            await _save_state()
            await _context.close()
        except Exception:
            pass
        _context = None
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _pw:
        try:
            await _pw.stop()
        except Exception:
            pass
        _pw = None


# ---------------------------------------------------------------------------
# MakerWorld page access
# ---------------------------------------------------------------------------

async def fetch_model_page(design_id: int) -> dict:
    """Navigate to MakerWorld model page and extract __NEXT_DATA__ JSON.

    Uses Playwright to bypass Cloudflare. Returns the pageProps.design object.
    """
    # Ensure auth token is injected into browser cookies
    token = await login_bambu()
    await _inject_token(token)

    ctx = await _get_context()
    page = await ctx.new_page()

    try:
        url = f"{MAKERWORLD}/en/models/{design_id}"
        logger.info("Navigating to %s", url)

        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Check for Cloudflare challenge — wait if needed
        if resp and resp.status == 403:
            logger.warning("Got 403, waiting for Cloudflare challenge...")
            await page.wait_for_load_state("networkidle", timeout=15000)

        # Wait for __NEXT_DATA__ script tag (script tags are hidden, use "attached" state)
        await page.wait_for_selector("script#__NEXT_DATA__", state="attached", timeout=20000)

        next_data_text = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent : null;
            }
        """)

        if not next_data_text:
            # Debug: capture page content snippet
            title = await page.title()
            raise ValueError(
                f"No __NEXT_DATA__ found for design_id={design_id} (page title: {title})"
            )

        next_data = json.loads(next_data_text)
        design = next_data.get("props", {}).get("pageProps", {}).get("design")
        if not design:
            raise ValueError(f"No design data in __NEXT_DATA__ for design_id={design_id}")

        await _save_state()
        return design

    finally:
        await page.close()


def resolve_instance(design: dict, instance_id: int | None = None) -> dict:
    """Find a specific instance (print profile) in the design data.

    If instance_id is None, returns the default instance.
    """
    instances = design.get("instances", [])
    if not instances:
        raise ValueError("Design has no print profile instances")

    if instance_id:
        for inst in instances:
            if inst.get("id") == instance_id:
                return inst
        raise ValueError(f"Instance {instance_id} not found in design")

    default_id = design.get("defaultInstanceId")
    if default_id:
        for inst in instances:
            if inst.get("id") == default_id:
                return inst

    return instances[0]


def extract_instance_metadata(instance: dict) -> dict:
    """Extract useful print metadata from an instance."""
    ext = instance.get("extention", {}).get("modelInfo", {})
    plates = ext.get("plates", [])
    plate = plates[0] if plates else {}

    filaments = plate.get("filaments", [])
    filament = filaments[0] if filaments else {}

    return {
        "instance_id": instance.get("id"),
        "profile_id": instance.get("profileId"),
        "title": instance.get("title", ""),
        "weight_g": instance.get("weight") or plate.get("weight"),
        "print_time_s": instance.get("prediction") or plate.get("prediction"),
        "material": filament.get("type", "PLA"),
        "color": filament.get("color", ""),
        "plate_count": len(plates),
        "thumbnail_url": plate.get("thumbnail", {}).get("url"),
        "cover_url": instance.get("cover"),
    }


# ---------------------------------------------------------------------------
# .3mf download — three-strategy cascade
# ---------------------------------------------------------------------------

async def _navigate_to_model(page, design_id: int):
    """Navigate to model page and wait for Cloudflare clearance."""
    url = f"{MAKERWORLD}/en/models/{design_id}"
    logger.info("Navigating to %s", url)
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if resp and resp.status == 403:
        logger.warning("Got 403, waiting for Cloudflare challenge...")
        await page.wait_for_load_state("networkidle", timeout=15000)
    # Wait for page to be interactive
    await page.wait_for_selector("script#__NEXT_DATA__", state="attached", timeout=20000)


async def _try_f3mf_api(page, instance_id: int) -> str | None:
    """Strategy A: Call the f3mf API endpoint via browser fetch (cookie auth).

    Returns presigned CDN URL or None.
    """
    logger.info("Strategy A: Trying f3mf API for instance %d", instance_id)
    result = await page.evaluate("""
        async (instanceId) => {
            try {
                const resp = await fetch(
                    `/api/v1/design-service/instance/${instanceId}/f3mf?type=download`,
                    { credentials: "include" }
                );
                const text = await resp.text();
                return {
                    status: resp.status,
                    headers: Object.fromEntries(resp.headers.entries()),
                    body: text,
                    url: resp.url,
                };
            } catch (e) {
                return { error: e.message };
            }
        }
    """, instance_id)

    if isinstance(result, dict) and result.get("error"):
        logger.warning("Strategy A error: %s", result["error"])
        return None

    status = result.get("status", 0)
    body = result.get("body", "")
    logger.info("Strategy A response: status=%d, body=%s", status, body[:500])

    if status != 200:
        logger.warning("Strategy A got HTTP %d", status)
        return None

    # Response may be JSON with a URL, or a redirect URL
    try:
        data = json.loads(body)
        cdn_url = (
            data.get("url")
            or data.get("downloadUrl")
            or data.get("fileUrl")
            or data.get("download_url")
        )
        if cdn_url:
            return cdn_url
        logger.warning("Strategy A: JSON response but no URL field: %s", list(data.keys()))
    except json.JSONDecodeError:
        # Body might be the file itself or a redirect — check content-type
        ct = result.get("headers", {}).get("content-type", "")
        if "application/octet-stream" in ct or "application/zip" in ct:
            logger.info("Strategy A: Got binary response, URL was direct download")
            return result.get("url")  # The fetch URL itself is the download

    return None


async def _try_network_intercept(page, design_id: int) -> str | None:
    """Strategy B: Click download button and intercept network response.

    Captures API responses containing presigned CDN URLs.
    Returns CDN URL or None.
    """
    logger.info("Strategy B: Network intercept + button click for design %d", design_id)

    captured_url = {"value": None}

    async def on_response(response):
        url = response.url
        # Look for API responses that might contain download URLs
        if any(kw in url for kw in ["design-service", "f3mf", "bblmw.com", "download"]):
            try:
                if response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = await response.json()
                        cdn = (
                            data.get("url")
                            or data.get("downloadUrl")
                            or data.get("fileUrl")
                            or data.get("download_url")
                        )
                        if cdn:
                            logger.info("Strategy B: Captured CDN URL from %s", url)
                            captured_url["value"] = cdn
                    elif "octet-stream" in ct or "zip" in ct:
                        logger.info("Strategy B: Captured direct download URL: %s", url)
                        captured_url["value"] = url
            except Exception as e:
                logger.debug("Strategy B: Error processing response from %s: %s", url, e)

    page.on("response", on_response)

    try:
        # Try multiple selectors for the download button
        selectors = [
            'button:has-text("Download 3MF")',
            'button:has-text("Download")',
            '[data-testid*="download"]',
            'a[href*="download"]',
        ]
        clicked = False
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click(timeout=5000)
                    clicked = True
                    logger.info("Strategy B: Clicked '%s'", sel)
                    break
            except Exception:
                continue

        if not clicked:
            logger.warning("Strategy B: No download button found")
            return None

        # Wait for the network response
        await page.wait_for_timeout(5000)
        return captured_url["value"]

    finally:
        page.remove_listener("response", on_response)


async def _try_direct_download(page) -> Path | None:
    """Strategy C: Use expect_download() to capture browser-initiated download.

    Returns saved file path or None.
    """
    logger.info("Strategy C: expect_download + button click")

    try:
        selectors = [
            'button:has-text("Download 3MF")',
            'button:has-text("Download")',
            '[data-testid*="download"]',
        ]
        btn = None
        for sel in selectors:
            try:
                candidate = page.locator(sel).first
                if await candidate.is_visible(timeout=3000):
                    btn = candidate
                    break
            except Exception:
                continue

        if not btn:
            logger.warning("Strategy C: No download button found")
            return None

        async with page.expect_download(timeout=30000) as download_info:
            await btn.click(timeout=5000)

        download = await download_info.value
        tmp_path = MODELS_DIR / f"_tmp_{download.suggested_filename or 'download.3mf'}"
        await download.save_as(str(tmp_path))
        if tmp_path.stat().st_size > 1000:
            logger.info("Strategy C: Downloaded %s (%d bytes)", tmp_path, tmp_path.stat().st_size)
            return tmp_path
        else:
            tmp_path.unlink(missing_ok=True)
            logger.warning("Strategy C: Downloaded file too small")
            return None

    except Exception as e:
        logger.warning("Strategy C failed: %s", e)
        return None


async def download_3mf(
    design_id: int,
    instance_id: int,
    profile_id: int,
) -> tuple[Path, dict]:
    """Download a .3mf file from MakerWorld for the given instance.

    Three-strategy cascade:
    A. f3mf API endpoint (cookie auth via browser context)
    B. Network interception + download button click
    C. expect_download() direct file capture

    Returns (file_path, metadata_dict).
    """
    token = await login_bambu()
    await _inject_token(token)

    # Fetch metadata from model page
    design = await fetch_model_page(design_id)
    instance = resolve_instance(design, instance_id)
    metadata = extract_instance_metadata(instance)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    # Download thumbnail (signed URLs from page data, usually accessible)
    thumb_url = metadata.get("thumbnail_url") or metadata.get("cover_url")
    if thumb_url:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(thumb_url)
                if resp.status_code == 200:
                    thumb_path = THUMBS_DIR / f"mw_{design_id}_{instance_id}.png"
                    thumb_path.write_bytes(resp.content)
                    metadata["thumbnail_path"] = str(thumb_path)
        except Exception:
            logger.warning("Failed to download thumbnail for instance %d", instance_id)

    file_path = MODELS_DIR / f"mw_{design_id}_{instance_id}.3mf"
    ctx = await _get_context()
    page = await ctx.new_page()

    try:
        await _navigate_to_model(page, design_id)

        # --- Strategy A: f3mf API ---
        cdn_url = await _try_f3mf_api(page, instance_id)
        if cdn_url:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(cdn_url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    file_path.write_bytes(resp.content)
                    logger.info("Downloaded .3mf via Strategy A (f3mf API): %s (%d bytes)",
                                file_path, len(resp.content))
                    metadata["file_path"] = str(file_path)
                    metadata["download_strategy"] = "f3mf_api"
                    return file_path, metadata

        # --- Strategy B: Network intercept + button click ---
        cdn_url = await _try_network_intercept(page, design_id)
        if cdn_url:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(cdn_url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    file_path.write_bytes(resp.content)
                    logger.info("Downloaded .3mf via Strategy B (network intercept): %s (%d bytes)",
                                file_path, len(resp.content))
                    metadata["file_path"] = str(file_path)
                    metadata["download_strategy"] = "network_intercept"
                    return file_path, metadata

        # --- Strategy C: Direct download via expect_download ---
        tmp_path = await _try_direct_download(page)
        if tmp_path:
            if tmp_path != file_path:
                shutil.move(str(tmp_path), str(file_path))
            logger.info("Downloaded .3mf via Strategy C (direct download): %s", file_path)
            metadata["file_path"] = str(file_path)
            metadata["download_strategy"] = "direct_download"
            return file_path, metadata

        raise RuntimeError(
            f"Could not download .3mf for design={design_id} instance={instance_id}. "
            "All 3 strategies failed. Use debug-download endpoint for diagnostics."
        )

    finally:
        await page.close()


# ---------------------------------------------------------------------------
# Debug / diagnostics
# ---------------------------------------------------------------------------

async def debug_download(design_id: int, instance_id: int) -> dict:
    """Diagnostic function: probe the f3mf API and capture network activity.

    Returns a dict with API responses and captured network requests for
    remote debugging without SSH access.
    """
    token = await login_bambu()
    await _inject_token(token)

    ctx = await _get_context()
    page = await ctx.new_page()

    results = {
        "design_id": design_id,
        "instance_id": instance_id,
        "strategies": {},
        "network_log": [],
    }

    # Capture all relevant network requests
    async def log_request(request):
        url = request.url
        if any(kw in url for kw in ["design-service", "f3mf", "download", "bblmw"]):
            results["network_log"].append({
                "method": request.method,
                "url": url,
            })

    async def log_response(response):
        url = response.url
        if any(kw in url for kw in ["design-service", "f3mf", "download", "bblmw"]):
            body_preview = ""
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "text" in ct:
                    body_preview = (await response.text())[:1000]
            except Exception:
                body_preview = "<could not read>"
            results["network_log"].append({
                "status": response.status,
                "url": url,
                "content_type": response.headers.get("content-type", ""),
                "body_preview": body_preview,
            })

    page.on("request", log_request)
    page.on("response", log_response)

    try:
        # Navigate to establish Cloudflare clearance
        await _navigate_to_model(page, design_id)
        results["page_loaded"] = True

        # Probe f3mf API endpoint
        f3mf_result = await page.evaluate("""
            async (instanceId) => {
                try {
                    const resp = await fetch(
                        `/api/v1/design-service/instance/${instanceId}/f3mf?type=download`,
                        { credentials: "include" }
                    );
                    const text = await resp.text();
                    return {
                        status: resp.status,
                        headers: Object.fromEntries(resp.headers.entries()),
                        body: text.substring(0, 2000),
                        url: resp.url,
                    };
                } catch (e) {
                    return { error: e.message };
                }
            }
        """, instance_id)
        results["strategies"]["f3mf_api"] = f3mf_result

        # Also try the old download endpoint for comparison
        old_result = await page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch(
                        "/api/v1/design-service/download/designId/{design_id}/instance/{instance_id}",
                        {{ method: "POST", credentials: "include" }}
                    );
                    const text = await resp.text();
                    return {{
                        status: resp.status,
                        body: text.substring(0, 2000),
                    }};
                }} catch (e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)
        results["strategies"]["old_download_api"] = old_result

        # Check what cookies are set
        cookies = await ctx.cookies(MAKERWORLD)
        results["cookies"] = [
            {"name": c["name"], "domain": c["domain"]}
            for c in cookies
        ]

    except Exception as e:
        results["error"] = str(e)

    finally:
        page.remove_listener("request", log_request)
        page.remove_listener("response", log_response)
        await page.close()

    return results

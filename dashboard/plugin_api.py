"""SMF AIGC Studio pane — optional local reachability for Hermes Desktop.

Studio-web lives in ``smfworks/aigc-production-flow`` (``studio-web/``).
This backend does **not** read, write, or invent projects, jobs, packs, or
media. It only reports embed URLs and probes the known loopback ports:

- studio-web Vite ``127.0.0.1:5174`` then preview ``:4174``
- studio API ``127.0.0.1:8000`` ``/readyz`` and ``/healthz``

No hosted studio-web URL was verified. The Vercel app is the pack builder
(``smf-h3-capture``), not this pane.

``GET /status`` — local URLs plus an honest web/API probe.
``GET /health`` — ``{ status: ok, plugin }``.

The desktop iframe gate is the client probe in ``desktop/plugin.js``
(``:5174``, then ``:4174``). This process is the API badge. An unread
``/status`` must not be treated as permission to iframe a closed port.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter()
except ImportError:  # tests / hosts without FastAPI still import the helpers
    APIRouter = None  # type: ignore[misc, assignment]
    JSONResponse = None  # type: ignore[misc, assignment]
    router = None

PLUGIN = "smf-aigc-studio-pane"
USER_AGENT = "SMF-AIGC-Studio-Pane/1.0 (+https://github.com/smfworks/smf-aigc-studio-pane)"
PROBE_TIMEOUT = 2.0

STUDIO_WEB_URL = "http://127.0.0.1:5174/"
STUDIO_PREVIEW_URL = "http://127.0.0.1:4174/"
API_ORIGIN = "http://127.0.0.1:8000"
READYZ_URL = API_ORIGIN + "/readyz"
HEALTHZ_URL = API_ORIGIN + "/healthz"
GITHUB_URL = "https://github.com/smfworks/aigc-production-flow"
DOCS_URL = "https://github.com/smfworks/aigc-production-flow/blob/main/docs/STUDIO.md"
PACK_BUILDER_REPO = "https://github.com/smfworks/smf-h3-capture"
PACK_BUILDER_URL = "http://127.0.0.1:5173/"
DEV_COMMAND = "./scripts/dev-studio.sh all"
LIVE_HOSTED = False
LIVE_NOTE = (
    "No hosted studio-web URL was verified. Studio is local only. "
    "There is no Live tab. The Vercel deploy is the pack builder "
    "(smf-h3-capture), not this pane."
)
HONESTY_NOTE = (
    "This pane embeds studio-web. It does not invent projects, continuity, "
    "jobs, packs, or media. The studio default adapter is stub."
)

WEB_PORTS = {5174, 4174}
API_PORT = 8000
API_PATHS = {"/readyz", "/healthz"}

HttpGetter = Callable[[str, Optional[Dict[str, str]]], Tuple[int, str, Dict[str, str]]]


def local_url_allowed(url: str) -> bool:
    """Known loopback targets only. No scan, no remote hosts."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost"}:
        return False
    if parsed.scheme != "http":
        return False
    if parsed.username or parsed.password:
        return False
    port = parsed.port
    path = parsed.path or "/"
    if port in WEB_PORTS:
        return path in {"", "/"}
    if port == API_PORT:
        return path in API_PATHS
    return False


def default_http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Tuple[int, str, Dict[str, str]]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html, */*"}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs, method="GET")
    wait = PROBE_TIMEOUT if timeout is None else timeout
    try:
        with urlopen(req, timeout=wait) as resp:
            body = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            text = body.decode(charset, errors="replace")
            info = {k.lower(): v for k, v in resp.headers.items()}
            return int(getattr(resp, "status", 200) or 200), text, info
    except HTTPError as exc:
        code = int(exc.code)
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return code, err_body, {}
    except URLError as exc:
        raise OSError(str(exc.reason or exc)) from exc


def probe_code(url: str, getter: HttpGetter) -> Optional[int]:
    if not local_url_allowed(url):
        return None
    try:
        status, _body, _headers = getter(url, {"Accept": "application/json, text/html, */*"})
        return int(status)
    except Exception:
        return None


def probe_web(url: str, getter: HttpGetter) -> bool:
    code = probe_code(url, getter)
    return code is not None and 200 <= code < 500


def _ok(code: Optional[int]) -> bool:
    return code is not None and 200 <= code < 300


def default_status(
    *,
    web_reachable: Optional[bool] = None,
    web_url: Optional[str] = None,
    dev_reachable: Optional[bool] = None,
    preview_reachable: Optional[bool] = None,
    api_reachable: Optional[bool] = None,
    api_ready: Optional[bool] = None,
    api_health: Optional[bool] = None,
) -> Dict[str, Any]:
    return {
        "ok": True,
        "plugin": PLUGIN,
        "source_default": "local",
        "live_hosted": LIVE_HOSTED,
        "live_note": LIVE_NOTE,
        "studio_web_url": STUDIO_WEB_URL,
        "studio_preview_url": STUDIO_PREVIEW_URL,
        "api_origin": API_ORIGIN + "/",
        "readyz_url": READYZ_URL,
        "healthz_url": HEALTHZ_URL,
        "github_url": GITHUB_URL,
        "docs_url": DOCS_URL,
        "pack_builder_repo": PACK_BUILDER_REPO,
        "pack_builder_url": PACK_BUILDER_URL,
        "dev_command": DEV_COMMAND,
        "honesty_note": HONESTY_NOTE,
        "web": {
            "reachable": web_reachable,
            "reachable_url": web_url,
            "dev_reachable": dev_reachable,
            "preview_reachable": preview_reachable,
        },
        "api": {
            "reachable": api_reachable,
            "ready": api_ready,
            "health": api_health,
        },
    }


def collect_status(*, getter: Optional[HttpGetter] = None, probe: bool = True) -> Dict[str, Any]:
    """Report embed URLs. Probe loopback studio-web and API only. Never invent records."""
    if not probe:
        return default_status()
    getter = getter or default_http_get
    dev_up = probe_web(STUDIO_WEB_URL, getter)
    preview_up = probe_web(STUDIO_PREVIEW_URL, getter)
    ready_code = probe_code(READYZ_URL, getter)
    health_code = probe_code(HEALTHZ_URL, getter)
    ready = _ok(ready_code)
    health = _ok(health_code)
    api_reachable = ready_code is not None or health_code is not None
    if dev_up:
        web_url = STUDIO_WEB_URL
    elif preview_up:
        web_url = STUDIO_PREVIEW_URL
    else:
        web_url = None
    return default_status(
        web_reachable=bool(dev_up or preview_up),
        web_url=web_url,
        dev_reachable=dev_up,
        preview_reachable=preview_up,
        api_reachable=api_reachable,
        api_ready=ready,
        api_health=health,
    )


def _json(payload: Dict[str, Any], status: int = 200):
    if JSONResponse is None:
        return payload
    return JSONResponse(payload, status_code=status)


if router is not None:

    @router.get("/status")
    def status():
        try:
            return _json(collect_status(probe=True))
        except Exception as exc:  # pragma: no cover - defensive mount
            payload = default_status(
                web_reachable=False,
                web_url=None,
                api_reachable=False,
                api_ready=False,
                api_health=False,
            )
            payload["ok"] = False
            payload["error"] = str(exc)
            return _json(payload)

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok", "plugin": PLUGIN}

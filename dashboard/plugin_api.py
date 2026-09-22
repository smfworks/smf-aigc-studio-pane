"""SMF AIGC Studio pane — optional local reachability for Hermes Desktop.

Studio-web lives in ``smfworks/aigc-production-flow`` (``studio-web/``).
This backend does **not** invent projects, jobs, packs, or media. It reports
embed URLs, probes the known loopback ports, and reads a Hermes brief that
Studio already wrote:

- studio-web Vite ``127.0.0.1:5174`` then preview ``:4174``
- studio API ``127.0.0.1:8000`` ``/readyz`` and ``/healthz``
- Hermes brief: ``latest.json`` plus ``hermes-handoff.json`` and
  ``agent-brief.json`` (see aigc-production-flow ``AGENTS.md``)
- when ``:8000`` answers, ``GET /api/agent-runs/{id}`` refreshes that brief;
  ``GET /api/handoffs`` is only used when the JSON is itself a brief
  (the pack-zip stage on that path is not a Hermes brief)

No hosted studio-web URL was verified. The Vercel app is the pack builder
(``smf-h3-capture``), not this pane.

``GET /status`` — local URLs plus an honest web/API probe.
``GET /health`` — ``{ status: ok, plugin }``.
``GET /handoff`` — latest brief, or empty. Does not start Hermes or Comfy.
``GET /handoff/{run_id}`` — one ``hermes://aigc/brief?run=`` id.

The desktop iframe gate is the client probe in ``desktop/plugin.js``
(``:5174``, then ``:4174``). This process is the API badge and the brief
reader. An unread ``/status`` must not be treated as permission to iframe a
closed port. A brief on disk is not a finished film and not a Comfy run.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

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
HANDOFFS_PATH = "/api/handoffs"
RUN_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
AGENT_RUN_RE = re.compile(r"^/api/agent-runs/" + RUN_ID_RE.pattern[1:-1] + r"$")
MAX_BRIEF_BYTES = 1_000_000
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
STITCH_NOTE = (
    "The last job is stitch. Concat the playlist in order. "
    "Concat only local video files that exist. "
    "If the inputs are fixture receipts, leave the run awaiting stitch. "
    "Do not invent an MP4."
)

HttpGetter = Callable[[str, Optional[Dict[str, str]]], Tuple[int, str, Dict[str, str]]]


def _agent_run_path(run_id: str) -> str:
    return "/api/agent-runs/" + run_id


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
    if ".." in path or "\\" in path or "\x00" in path:
        return False
    if port in WEB_PORTS:
        return path in {"", "/"}
    if port == API_PORT:
        if path in API_PATHS or path == HANDOFFS_PATH:
            return True
        return AGENT_RUN_RE.match(path) is not None
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


def _as_bool(value: Any) -> bool:
    """True only for a real true. File existence must not coerce this on."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _clip(value: Any, limit: int = 500) -> str:
    text = value if isinstance(value, str) else ""
    text = text.strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _under(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _allowed_path(path: Path, roots: Sequence[Path]) -> bool:
    for root in roots:
        if _under(root, path):
            return True
    return False


def default_handoff_roots() -> List[Path]:
    """Env overrides, the Hermes mirror, and common studio checkout layouts.

    No directory walk. Missing paths are skipped by the reader.
    """
    found: List[Path] = []
    seen = set()

    def add(raw: object) -> None:
        if raw is None:
            return
        text = str(raw).strip()
        if not text:
            return
        path = Path(text).expanduser()
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    for key in ("HANDOFF_ROOT", "STUDIO_HANDOFF_ROOT", "STUDIO_HERMES_DROP"):
        add(os.environ.get(key))
    media = (os.environ.get("STUDIO_MEDIA_ROOT") or "").strip()
    if media:
        add(Path(media).expanduser().parent / "handoff")
    home = Path.home()
    add(home / ".hermes" / "aigc")
    for name in ("", "src", "work", "code", "projects", "dev", "src/smfworks"):
        base = home if not name else home / name
        add(base / "aigc-production-flow" / "data" / "handoff")
    cwd = Path.cwd()
    add(cwd / "data" / "handoff")
    add(cwd / "aigc-production-flow" / "data" / "handoff")
    return found


def _read_json_file(path: Path, roots: Sequence[Path]) -> Optional[Dict[str, Any]]:
    if not _allowed_path(path, roots):
        return None
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > MAX_BRIEF_BYTES:
            return None
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _job_row(row: Dict[str, Any]) -> Dict[str, Any]:
    kind = _clip(row.get("kind"), 80)
    return {
        "order": int(row.get("order") or 0) if str(row.get("order") or "").strip().lstrip("-").isdigit() else 0,
        "kind": kind,
        "subject": _clip(row.get("subject"), 200),
        "take": _clip(row.get("take"), 80),
        "stage": _clip(row.get("stage"), 80),
        "adapter_label": _clip(row.get("adapter_label") or row.get("adapter"), 120),
        "note": _clip(row.get("note"), 500),
        "status": _clip(row.get("status"), 80),
        "called_comfy": _as_bool(row.get("called_comfy")),
        "produced_mp4": _as_bool(row.get("produced_mp4")),
    }


def _jobs_from(rows: Any) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    jobs = [_job_row(row) for row in rows if isinstance(row, dict) and (row.get("kind") or row.get("order"))]
    jobs.sort(key=lambda job: (job["order"], job["kind"]))
    return jobs


def _stitch_note(jobs: Sequence[Dict[str, Any]], honesty: Dict[str, Any]) -> str:
    for job in reversed(list(jobs)):
        if job.get("kind") == "stitch" and job.get("note"):
            return str(job["note"])
    stitch = honesty.get("stitch")
    if isinstance(stitch, str) and stitch.strip():
        return _clip(stitch, 500)
    return STITCH_NOTE


def _looks_like_brief(row: Dict[str, Any]) -> bool:
    """Pack-zip `/api/handoffs` rows are not Hermes briefs."""
    if row.get("deep_link") or row.get("agent_run_id"):
        return True
    if row.get("drop_dir") and row.get("open") == "hermes-handoff.json":
        return True
    return False


def _brief_rows(payload: Any) -> List[Dict[str, Any]]:
    rows: Any = payload if isinstance(payload, list) else None
    if rows is None and isinstance(payload, dict):
        for key in ("handoffs", "items", "runs"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and _looks_like_brief(row)]


def _run_id_of(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return ""
    for key in ("agent_run_id", "id"):
        value = row.get(key)
        if isinstance(value, str) and RUN_ID_RE.match(value):
            return value
    link = row.get("deep_link")
    if isinstance(link, str):
        marker = "run="
        if marker in link:
            token = link.split(marker, 1)[1].split("&", 1)[0].strip()
            if RUN_ID_RE.match(token):
                return token
    return ""


def _empty_handoff(*, studio_api: str, roots_checked: Sequence[str], run: str = "") -> Dict[str, Any]:
    note = "No handoff yet. Studio has not written a brief this pane can see."
    if run:
        note = "No brief for run " + run + "."
    return {
        "ok": True,
        "plugin": PLUGIN,
        "state": "empty",
        "badge": "No handoff yet",
        "source": "",
        "studio_api": studio_api,
        "agent_run_id": "",
        "wizard_id": "",
        "deep_link": "",
        "drop_dir": "",
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "film_on_disk": False,
        "finished_film": False,
        "honesty": {
            "called_comfy": False,
            "hermes_ran": False,
            "produced_mp4": False,
            "still_live": False,
            "clip_live": False,
            "still_label": "",
            "clip_label": "",
            "note": note,
            "stitch": "",
        },
        "jobs": [],
        "stitch_note": STITCH_NOTE,
        "roots_checked": list(roots_checked),
    }


def _load_file_pointer(
    roots: Sequence[Path],
    run: str,
    checked: List[str],
) -> Optional[Dict[str, Any]]:
    """Watch latest.json. Read hermes-handoff.json and agent-brief.json from the drop."""
    matches: List[Dict[str, Any]] = []
    for root in roots:
        checked.append(str(root))
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        latest_path = root / "latest.json"
        latest = _read_json_file(latest_path, [root])
        latest_id = _run_id_of(latest) if latest else ""
        if run and latest_id and latest_id != run:
            latest = None
            latest_id = ""
        if run and not latest_id:
            # A requested run may live beside a newer latest.json.
            folder = root / run
            if _read_json_file(folder / "hermes-handoff.json", [root]) or _read_json_file(
                folder / "agent-brief.json", [root]
            ):
                latest = {
                    "agent_run_id": run,
                    "drop_dir": str(folder),
                    "deep_link": "hermes://aigc/brief?run=" + run,
                    "open": "hermes-handoff.json",
                }
                latest_id = run
        if not latest or not latest_id:
            continue
        drop_raw = latest.get("drop_dir")
        drop_candidates: List[Path] = []
        if isinstance(drop_raw, str) and drop_raw.strip():
            drop_candidates.append(Path(drop_raw).expanduser())
        drop_candidates.append(root / latest_id)
        drop_candidates.append(root / "latest")
        handoff_doc: Optional[Dict[str, Any]] = None
        brief_doc: Optional[Dict[str, Any]] = None
        drop_used = ""
        for drop in drop_candidates:
            if not _allowed_path(drop, roots):
                continue
            handoff_doc = _read_json_file(drop / "hermes-handoff.json", roots)
            brief_doc = _read_json_file(drop / "agent-brief.json", roots)
            if handoff_doc or brief_doc:
                drop_used = str(drop)
                break
        if not drop_used and isinstance(drop_raw, str):
            # Display the path Studio wrote even when this process cannot read it.
            drop_used = drop_raw
        written = latest.get("written_at") if isinstance(latest.get("written_at"), str) else ""
        try:
            stamp = (root / "latest.json").stat().st_mtime
        except OSError:
            stamp = 0.0
        matches.append(
            {
                "pointer": latest,
                "handoff": handoff_doc or {},
                "brief": brief_doc or {},
                "drop_dir": drop_used,
                "agent_run_id": latest_id,
                "written_at": written,
                "stamp": stamp,
            }
        )
    if not matches:
        return None
    if run:
        for item in matches:
            if item["agent_run_id"] == run:
                return item
        return None
    matches.sort(key=lambda item: (item.get("written_at") or "", item.get("stamp") or 0.0), reverse=True)
    return matches[0]


def studio_auth_headers() -> Dict[str, str]:
    token = (
        os.environ.get("STUDIO_API_TOKEN")
        or os.environ.get("AIGC_STUDIO_TOKEN")
        or "local-dev-token"
    ).strip() or "local-dev-token"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    user = (os.environ.get("STUDIO_DEFAULT_USER") or "").strip()
    if user:
        headers["X-User-Name"] = user
    org = (os.environ.get("STUDIO_ORG_ID") or "").strip()
    if org:
        headers["X-Org-Id"] = org
    return headers


def _studio_fetch(url: str, getter: HttpGetter) -> Tuple[str, Any]:
    """Return (state, json). state is ok, unauthorized, miss, or down."""
    if not local_url_allowed(url):
        return "down", None
    try:
        status, text, _headers = getter(url, studio_auth_headers())
    except Exception:
        return "down", None
    code = int(status or 0)
    if code in {401, 403}:
        return "unauthorized", None
    if code == 404 or code == 405:
        return "miss", None
    if code < 200 or code >= 300:
        return "miss", None
    if not text:
        return "ok", None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return "ok", None
    return "ok", parsed


def _studio_up(getter: HttpGetter) -> bool:
    for url in (HEALTHZ_URL, READYZ_URL):
        state, _body = _studio_fetch(url, getter)
        if state == "ok":
            return True
    return False


def _pointer_from_studio_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    run_id = _run_id_of(row)
    if not run_id:
        return None
    link = row.get("deep_link")
    deep_link = link if isinstance(link, str) and link.startswith("hermes://aigc/brief?run=") else (
        "hermes://aigc/brief?run=" + run_id
    )
    drop = row.get("drop_dir") if isinstance(row.get("drop_dir"), str) else ""
    honesty = row.get("honesty") if isinstance(row.get("honesty"), dict) else {}
    steps = row.get("steps") if isinstance(row.get("steps"), list) else []
    jobs_raw = row.get("jobs") if isinstance(row.get("jobs"), list) else steps
    return {
        "pointer": {
            "agent_run_id": run_id,
            "wizard_id": row.get("wizard_id") or "",
            "deep_link": deep_link,
            "drop_dir": drop,
            "called_comfy": _as_bool(row.get("called_comfy")),
            "hermes_ran": _as_bool(row.get("hermes_ran")),
            "produced_mp4": _as_bool(row.get("produced_mp4")),
            "note": row.get("honesty_note") or honesty.get("note") or "",
        },
        "handoff": {"honesty": honesty} if honesty else {},
        "brief": {"jobs": jobs_raw, "honesty": honesty} if jobs_raw or honesty else {},
        "drop_dir": drop,
        "agent_run_id": run_id,
        "from_api": True,
    }


def _read_studio_pointer(
    getter: HttpGetter,
    run: str,
    file_hit: Optional[Dict[str, Any]],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    if not _studio_up(getter):
        return "down", None
    state = "reachable"
    hit: Optional[Dict[str, Any]] = None
    list_state, payload = _studio_fetch(API_ORIGIN + HANDOFFS_PATH, getter)
    if list_state == "unauthorized":
        state = "unauthorized"
    elif list_state == "ok":
        rows = _brief_rows(payload)
        if run:
            rows = [row for row in rows if _run_id_of(row) == run]
        if rows:
            hit = _pointer_from_studio_row(rows[0])
            state = "ok"
    run_id = run or (file_hit or {}).get("agent_run_id") or (hit or {}).get("agent_run_id") or ""
    if isinstance(run_id, str) and RUN_ID_RE.match(run_id):
        run_state, run_payload = _studio_fetch(API_ORIGIN + _agent_run_path(run_id), getter)
        if run_state == "unauthorized":
            state = "unauthorized"
        elif run_state == "ok" and isinstance(run_payload, dict):
            api_hit = _pointer_from_studio_row(run_payload)
            if api_hit:
                hit = api_hit
                state = "ok"
    return state, hit


def _merge_jobs(file_jobs: Sequence[Dict[str, Any]], api_jobs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not file_jobs:
        return list(api_jobs)
    if not api_jobs:
        return list(file_jobs)
    overlay = {(job["order"], job["kind"]): job for job in api_jobs}
    merged: List[Dict[str, Any]] = []
    for job in file_jobs:
        extra = overlay.get((job["order"], job["kind"]))
        if not extra:
            merged.append(job)
            continue
        row = dict(job)
        if extra.get("status"):
            row["status"] = extra["status"]
        if extra.get("adapter_label") and not row.get("adapter_label"):
            row["adapter_label"] = extra["adapter_label"]
        # A true flag on either side is the brief saying so. Never inferred from files.
        row["called_comfy"] = bool(job.get("called_comfy") or extra.get("called_comfy"))
        row["produced_mp4"] = bool(job.get("produced_mp4") or extra.get("produced_mp4"))
        if extra.get("note") and not row.get("note"):
            row["note"] = extra["note"]
        merged.append(row)
    return merged


def _film_on_disk(drop_dir: str, roots: Sequence[Path], docs: Sequence[Dict[str, Any]]) -> bool:
    paths: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"path", "output_path", "mp4_path", "media_path", "output"} and isinstance(value, str):
                    paths.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for doc in docs:
        walk(doc)
    for raw in paths:
        candidate = Path(raw).expanduser()
        try:
            if (
                candidate.is_file()
                and candidate.stat().st_size > 0
                and candidate.suffix.lower() in VIDEO_SUFFIXES
            ):
                return True
        except OSError:
            continue
    if not drop_dir:
        return False
    drop = Path(drop_dir).expanduser()
    if not _allowed_path(drop, roots):
        return False
    try:
        if not drop.is_dir():
            return False
        for child in drop.iterdir():
            if (
                child.is_file()
                and child.suffix.lower() in VIDEO_SUFFIXES
                and child.stat().st_size > 0
            ):
                return True
    except OSError:
        return False
    return False


def _honesty_from(*docs: Dict[str, Any]) -> Dict[str, Any]:
    honesty: Dict[str, Any] = {}
    for doc in docs:
        raw = doc.get("honesty") if isinstance(doc.get("honesty"), dict) else {}
        if not honesty and raw:
            honesty = dict(raw)
        elif raw:
            for key, value in raw.items():
                if key not in honesty or honesty.get(key) in ("", None, False):
                    honesty[key] = value
    return honesty


def _compose(
    *,
    file_hit: Optional[Dict[str, Any]],
    studio_hit: Optional[Dict[str, Any]],
    studio_api: str,
    roots: Sequence[Path],
    roots_checked: Sequence[str],
) -> Dict[str, Any]:
    if not file_hit and not studio_hit:
        return _empty_handoff(studio_api=studio_api, roots_checked=roots_checked)
    had_file = bool(file_hit)
    had_studio = bool(studio_hit)
    file_hit = file_hit or {}
    studio_hit = studio_hit or {}
    pointer = dict(file_hit.get("pointer") or {})
    pointer.update({k: v for k, v in (studio_hit.get("pointer") or {}).items() if v not in ("", None, False)})
    # True only when the file or the agent-run record says true.
    # A row existing, or a video file existing, does not flip these on.
    for flag in ("called_comfy", "hermes_ran", "produced_mp4"):
        file_flag = _as_bool((file_hit.get("pointer") or {}).get(flag))
        api_flag = _as_bool((studio_hit.get("pointer") or {}).get(flag))
        handoff_honesty = (file_hit.get("handoff") or {}).get("honesty") if isinstance(
            (file_hit.get("handoff") or {}).get("honesty"), dict
        ) else {}
        brief_honesty = (file_hit.get("brief") or {}).get("honesty") if isinstance(
            (file_hit.get("brief") or {}).get("honesty"), dict
        ) else {}
        api_honesty = (studio_hit.get("handoff") or {}).get("honesty") if isinstance(
            (studio_hit.get("handoff") or {}).get("honesty"), dict
        ) else {}
        pointer[flag] = bool(
            file_flag
            or api_flag
            or _as_bool(handoff_honesty.get(flag))
            or _as_bool(brief_honesty.get(flag))
            or _as_bool(api_honesty.get(flag))
        )
    file_jobs = _jobs_from((file_hit.get("brief") or {}).get("jobs"))
    api_jobs = _jobs_from((studio_hit.get("brief") or {}).get("jobs"))
    jobs = _merge_jobs(file_jobs, api_jobs)
    for job in jobs:
        if job.get("kind") == "stitch" and job.get("produced_mp4"):
            pointer["produced_mp4"] = True
        if job.get("called_comfy"):
            pointer["called_comfy"] = True
    honesty_docs = [
        file_hit.get("handoff") or {},
        file_hit.get("brief") or {},
        studio_hit.get("handoff") or {},
        studio_hit.get("brief") or {},
    ]
    honesty = _honesty_from(*[doc for doc in honesty_docs if isinstance(doc, dict)])
    called = _as_bool(pointer.get("called_comfy")) or _as_bool(honesty.get("called_comfy"))
    ran = _as_bool(pointer.get("hermes_ran")) or _as_bool(honesty.get("hermes_ran"))
    produced = _as_bool(pointer.get("produced_mp4")) or _as_bool(honesty.get("produced_mp4"))
    drop_dir = str(studio_hit.get("drop_dir") or file_hit.get("drop_dir") or pointer.get("drop_dir") or "")
    run_id = _run_id_of(pointer) or str(file_hit.get("agent_run_id") or studio_hit.get("agent_run_id") or "")
    deep_link = pointer.get("deep_link") if isinstance(pointer.get("deep_link"), str) else ""
    if not deep_link and run_id:
        deep_link = "hermes://aigc/brief?run=" + run_id
    film = False
    if produced:
        film = _film_on_disk(
            drop_dir,
            roots,
            [doc for doc in (file_hit.get("handoff"), file_hit.get("brief"), studio_hit.get("handoff")) if isinstance(doc, dict)],
        )
    if had_file and had_studio:
        source = "studio-api+file"
    elif had_studio:
        source = "studio-api"
    else:
        source = "file"
    note = _clip(honesty.get("note") or pointer.get("note") or "", 500)
    if not note:
        note = (
            "Studio wrote this brief. Hermes has not been invoked. Comfy has not been called. "
            "Stitch is a concat plan until real video files exist."
        )
    still_label = _clip(honesty.get("still_label"), 120)
    clip_label = _clip(honesty.get("clip_label"), 120)
    return {
        "ok": True,
        "plugin": PLUGIN,
        "state": "brief",
        "badge": "Latest brief",
        "source": source,
        "studio_api": studio_api,
        "agent_run_id": run_id,
        "wizard_id": _clip(pointer.get("wizard_id"), 80),
        "deep_link": deep_link,
        "drop_dir": drop_dir,
        "called_comfy": called,
        "hermes_ran": ran,
        "produced_mp4": produced,
        "film_on_disk": film,
        "finished_film": bool(produced and film),
        "honesty": {
            "called_comfy": called,
            "hermes_ran": ran,
            "produced_mp4": produced,
            "still_live": _as_bool(honesty.get("still_live")),
            "clip_live": _as_bool(honesty.get("clip_live")),
            "still_label": still_label,
            "clip_label": clip_label,
            "note": note,
            "stitch": _clip(honesty.get("stitch"), 500) if isinstance(honesty.get("stitch"), str) else "",
        },
        "jobs": jobs,
        "stitch_note": _stitch_note(jobs, honesty),
        "roots_checked": list(roots_checked),
    }


def collect_handoff(
    *,
    run: str = "",
    roots: Optional[Sequence[Path]] = None,
    getter: Optional[HttpGetter] = None,
    probe_studio: bool = True,
) -> Dict[str, Any]:
    """Latest Hermes brief. Does not start Hermes, call Comfy, or invent an MP4."""
    wanted = run.strip()
    if wanted and not RUN_ID_RE.match(wanted):
        return _empty_handoff(studio_api="reachable" if probe_studio else "down", roots_checked=[], run=wanted)
    root_list = list(roots) if roots is not None else default_handoff_roots()
    checked: List[str] = []
    file_hit = _load_file_pointer(root_list, wanted, checked)
    studio_api = "down"
    studio_hit: Optional[Dict[str, Any]] = None
    if probe_studio:
        studio_api, studio_hit = _read_studio_pointer(getter or handoff_http_get, wanted, file_hit)
    if wanted and file_hit and file_hit.get("agent_run_id") != wanted:
        file_hit = None
    if wanted and studio_hit and studio_hit.get("agent_run_id") != wanted:
        studio_hit = None
    payload = _compose(
        file_hit=file_hit,
        studio_hit=studio_hit,
        studio_api=studio_api,
        roots=root_list,
        roots_checked=checked,
    )
    if wanted and payload["state"] == "empty":
        payload["honesty"]["note"] = "No brief for run " + wanted + "."
    return payload


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise URLError("redirect blocked (" + str(code) + ")")


def handoff_http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Tuple[int, str, Dict[str, str]]:
    """Loopback GET that does not follow redirects."""
    if not local_url_allowed(url):
        raise OSError("url not allowed")
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs, method="GET")
    wait = PROBE_TIMEOUT if timeout is None else timeout
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=wait) as resp:
            body = resp.read(MAX_BRIEF_BYTES + 1)
            if len(body) > MAX_BRIEF_BYTES:
                body = body[:MAX_BRIEF_BYTES]
            charset = resp.headers.get_content_charset() or "utf-8"
            text = body.decode(charset, errors="replace")
            info = {k.lower(): v for k, v in resp.headers.items()}
            return int(getattr(resp, "status", 200) or 200), text, info
    except HTTPError as exc:
        code = int(exc.code)
        try:
            err_body = exc.read(MAX_BRIEF_BYTES).decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return code, err_body, {}
    except URLError as exc:
        raise OSError(str(exc.reason or exc)) from exc


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

    @router.get("/handoff")
    def handoff_latest():
        try:
            return _json(collect_handoff())
        except Exception as exc:  # pragma: no cover - defensive mount
            return _json(
                {
                    "ok": False,
                    "plugin": PLUGIN,
                    "state": "unread",
                    "badge": "API unread",
                    "error": str(exc),
                    "called_comfy": False,
                    "hermes_ran": False,
                    "produced_mp4": False,
                    "finished_film": False,
                    "jobs": [],
                }
            )

    @router.get("/handoff/{run_id}")
    def handoff_one(run_id: str):
        if not RUN_ID_RE.match(run_id or ""):
            return _json(
                _empty_handoff(studio_api="reachable", roots_checked=[], run=run_id or ""),
                status=400,
            )
        try:
            return _json(collect_handoff(run=run_id))
        except Exception as exc:  # pragma: no cover - defensive mount
            return _json(
                {
                    "ok": False,
                    "plugin": PLUGIN,
                    "state": "unread",
                    "badge": "API unread",
                    "error": str(exc),
                    "called_comfy": False,
                    "hermes_ran": False,
                    "produced_mp4": False,
                    "finished_film": False,
                    "jobs": [],
                }
            )

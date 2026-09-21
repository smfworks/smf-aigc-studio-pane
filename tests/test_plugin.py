"""Smoke + honesty tests for the SMF AIGC Studio Hermes pane.

Fixture-safe: no network, no invented projects, jobs, packs, or media.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

import plugin_api as api


def test_plugin_yaml_identity():
    yaml = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    assert "name: smf-aigc-studio-pane" in yaml
    assert "author: SMF Works" in yaml
    assert "kind: standalone" in yaml
    assert "studio-web" in yaml


def test_desktop_plugin_embeds_local_studio_and_ids():
    js = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    assert "id: 'smf-aigc-studio-pane-frame'" in js or 'id: "smf-aigc-studio-pane-frame"' in js
    assert "const ID = 'smf-aigc-studio-pane'" in js
    assert "PANES_AREA" in js
    assert "SIDEBAR_NAV_AREA" in js
    assert "PALETTE_AREA" in js
    assert "ROUTES_AREA" in js
    assert "placement: 'right'" in js
    assert "width: '760px'" in js
    assert "Open AIGC Studio" in js
    assert "Open AIGC Studio pane" in js
    assert "label: 'AIGC Studio'" in js
    assert "title: 'AIGC Studio'" in js
    assert "http://127.0.0.1:5174/" in js
    assert "http://127.0.0.1:4174/" in js
    assert "http://127.0.0.1:8000/readyz" in js
    assert "http://127.0.0.1:8000/healthz" in js
    assert "https://github.com/smfworks/aigc-production-flow" in js
    assert "docs/STUDIO.md" in js
    assert "https://github.com/smfworks/smf-h3-capture" in js
    assert "./scripts/dev-studio.sh all" in js
    assert "from 'react/jsx-runtime'" in js
    assert "from '@hermes/plugin-sdk'" in js
    assert "jsx" in js and "jsxs" in js
    assert "iframe" in js
    assert "Live" in js and "Local" in js
    assert "does not invent" in js
    assert "local-first" in js
    assert "No hosted studio-web URL was verified" in js
    assert "return 'local'" in js
    assert "vercel.app" not in js
    assert "http://127.0.0.1:5173/" not in js
    assert ".$iframeNonce.get(" not in js
    assert ".$source.get(" not in js


def test_desktop_plugin_gates_iframe_on_client_probe():
    js = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    assert "async function probeLocalStudio" in js
    assert "function probeOne" in js
    assert "function clientReachableFrom" in js
    assert "function retryLocalProbe" in js
    assert "mode: 'no-cors'" in js
    assert "AbortController" in js
    assert "CLIENT_PROBE_MS = 2000" in js
    assert "probeOne(STUDIO_WEB_URL)" in js
    assert "probeOne(STUDIO_PREVIEW_URL)" in js
    assert "queryFn: () => probeLocalStudio()" in js
    assert "if (!forceEmbed && !clientReachable)" in js
    assert "studio-web is not running on :5174" in js
    assert "aigc-production-flow" in js
    assert "API badge is not a gate" in js
    assert "Embed 5174 anyway" in js
    assert "$forceEmbed.set(true)" in js
    assert "res.type === 'opaque'" in js
    assert "res.ok" not in js
    assert "embedding 5174 anyway" not in js
    assert "Local probe offline" not in js
    assert "if (localMode && !forceEmbed && (backendDown || webDown))" not in js
    assert js.count("embedUrl = STUDIO_WEB_URL") == 1
    assert "Use Local" in js
    assert "Retry" in js
    assert "ctx.rest('/status')" in js
    assert "API ready" in js
    assert "API down" in js
    assert "API unread" in js
    assert "API not ready" in js
    assert "Open Studio" in js
    assert "Copy dev command" in js
    assert "Pack builder" in js
    assert "http://127.0.0.1:5173/" not in js


def test_desktop_plugin_does_not_rewrite_studio_or_pack_builder():
    js = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    for forbidden in (
        "evaluateGates",
        "sigilsSample",
        "MiniMaxH3",
        "/api/jobs",
        "generate-ok",
        "comfy-h3",
        ".mp4",
    ):
        assert forbidden not in js


def test_install_sh_copies_desktop_plugins():
    sh = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "desktop-plugins/$NAME" in sh
    assert "HERMES_HOME" in sh
    assert "profiles/*/plugins" in sh
    assert "smf-aigc-studio-pane" in sh
    assert "copied JS" in sh
    assert "Do not run: hermes desktop" in sh
    assert "Open AIGC Studio pane" in sh
    assert "http://127.0.0.1:5174/" in sh


def test_local_url_allowlist():
    assert api.local_url_allowed("http://127.0.0.1:5174/") is True
    assert api.local_url_allowed("http://127.0.0.1:4174/") is True
    assert api.local_url_allowed("http://localhost:5174/") is True
    assert api.local_url_allowed("http://127.0.0.1:8000/readyz") is True
    assert api.local_url_allowed("http://127.0.0.1:8000/healthz") is True
    assert api.local_url_allowed("http://127.0.0.1:8000/api/meta") is False
    assert api.local_url_allowed("http://127.0.0.1:8000/api/jobs") is False
    assert api.local_url_allowed("http://127.0.0.1:5173/") is False
    assert api.local_url_allowed("http://127.0.0.1:3000/") is False
    assert api.local_url_allowed("https://aigc-production-flow.vercel.app") is False
    assert api.local_url_allowed("https://aigc-production-flow.vercel.app/") is False
    assert api.local_url_allowed("http://evil.example:5174/") is False
    assert api.local_url_allowed("http://user:pass@127.0.0.1:5174/") is False
    assert api.local_url_allowed("file:///etc/passwd") is False


def test_probe_prefers_studio_web_over_preview_and_reads_api():
    calls = []

    def getter(url, headers=None):
        calls.append(url)
        return 200, "ok", {}

    payload = api.collect_status(getter=getter, probe=True)
    assert payload["ok"] is True
    assert payload["plugin"] == "smf-aigc-studio-pane"
    assert payload["source_default"] == "local"
    assert payload["live_hosted"] is False
    assert payload["studio_web_url"] == "http://127.0.0.1:5174/"
    assert payload["github_url"] == "https://github.com/smfworks/aigc-production-flow"
    assert payload["docs_url"].endswith("/docs/STUDIO.md")
    assert payload["pack_builder_repo"] == "https://github.com/smfworks/smf-h3-capture"
    assert payload["dev_command"] == "./scripts/dev-studio.sh all"
    assert payload["web"]["reachable"] is True
    assert payload["web"]["reachable_url"] == "http://127.0.0.1:5174/"
    assert payload["web"]["dev_reachable"] is True
    assert payload["web"]["preview_reachable"] is True
    assert payload["api"]["reachable"] is True
    assert payload["api"]["ready"] is True
    assert payload["api"]["health"] is True
    assert api.STUDIO_WEB_URL in calls
    assert api.STUDIO_PREVIEW_URL in calls
    assert api.READYZ_URL in calls
    assert api.HEALTHZ_URL in calls
    blob = json.dumps(payload)
    assert "projects" not in payload
    assert '"jobs"' not in blob
    assert "mp4" not in blob.lower()
    assert "vercel.app" not in blob


def test_probe_falls_back_to_preview_when_dev_down():
    def getter(url, headers=None):
        if ":5174" in url:
            raise OSError("connection refused")
        return 200, "preview", {}

    payload = api.collect_status(getter=getter, probe=True)
    assert payload["web"]["reachable"] is True
    assert payload["web"]["reachable_url"] == "http://127.0.0.1:4174/"
    assert payload["web"]["dev_reachable"] is False
    assert payload["web"]["preview_reachable"] is True


def test_api_down_does_not_mark_studio_web_down():
    def getter(url, headers=None):
        if ":8000" in url:
            raise OSError("connection refused")
        return 200, "<html>studio</html>", {}

    payload = api.collect_status(getter=getter, probe=True)
    assert payload["web"]["reachable"] is True
    assert payload["web"]["reachable_url"] == "http://127.0.0.1:5174/"
    assert payload["api"]["reachable"] is False
    assert payload["api"]["ready"] is False
    assert payload["api"]["health"] is False


def test_readyz_503_healthz_200_is_not_ready():
    def getter(url, headers=None):
        if url.endswith("/readyz"):
            return 503, "not ready", {}
        if url.endswith("/healthz"):
            return 200, "ok", {}
        return 200, "<html></html>", {}

    payload = api.collect_status(getter=getter, probe=True)
    assert payload["api"]["reachable"] is True
    assert payload["api"]["ready"] is False
    assert payload["api"]["health"] is True
    assert payload["web"]["reachable"] is True


def test_probe_unreachable_is_honest():
    def getter(url, headers=None):
        raise OSError("connection refused")

    payload = api.collect_status(getter=getter, probe=True)
    assert payload["ok"] is True
    assert payload["live_hosted"] is False
    assert payload["web"]["reachable"] is False
    assert payload["web"]["reachable_url"] is None
    assert payload["web"]["dev_reachable"] is False
    assert payload["web"]["preview_reachable"] is False
    assert payload["api"]["reachable"] is False
    assert payload["api"]["ready"] is False
    assert payload["api"]["health"] is False
    blob = json.dumps(payload)
    assert '"title"' not in blob
    assert "logLine" not in blob
    assert '"jobs"' not in blob


def test_probe_skipped_does_not_claim_local_up():
    payload = api.collect_status(probe=False)
    assert payload["web"]["reachable"] is None
    assert payload["web"]["reachable_url"] is None
    assert payload["api"]["reachable"] is None
    assert payload["api"]["ready"] is None
    assert payload["api"]["health"] is None
    assert payload["live_hosted"] is False
    assert "local-first" in payload["live_note"]
    assert "does not invent" in payload["honesty_note"]


def test_disallowed_url_is_not_probed():
    calls = []

    def getter(url, headers=None):
        calls.append(url)
        return 200, "nope", {}

    assert api.probe_web("http://127.0.0.1:5173/", getter) is False
    assert api.probe_code("http://127.0.0.1:8000/api/jobs", getter) is None
    assert calls == []


def test_health_payload():
    if api.router is None:
        assert api.PLUGIN == "smf-aigc-studio-pane"
        return
    body = api.health()
    assert body == {"status": "ok", "plugin": "smf-aigc-studio-pane"}


def test_status_route_uses_injected_getter(monkeypatch):
    def getter(url, headers=None):
        raise OSError("offline fixture")

    monkeypatch.setattr(api, "default_http_get", getter)
    payload = api.collect_status(probe=True)
    assert payload["web"]["reachable"] is False
    assert payload["api"]["reachable"] is False


def test_agents_notes_do_not_iframe_a_dead_port():
    md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "studio-web is not running on :5174" in md
    assert "Embed 5174 anyway" in md
    assert "embed `:5174` anyway" not in md
    assert "blank white" in md
    assert "./scripts/dev-studio.sh all" in md


def test_client_probe_behavior():
    import shutil
    import subprocess

    node = shutil.which("node")
    assert node, "node is required to execute the client probe fixture"
    script = ROOT / "tests" / "client_probe_check.mjs"
    proc = subprocess.run([node, str(script)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "SMF Works" in text


def test_readme_has_install_and_honesty():
    md = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/smfworks/smf-aigc-studio-pane.git ~/.hermes/plugins/smf-aigc-studio-pane" in md
    assert "bash ~/.hermes/plugins/smf-aigc-studio-pane/install.sh" in md
    assert "MIT" in md
    assert "http://127.0.0.1:5174/" in md
    assert "http://127.0.0.1:4174/" in md
    assert "http://127.0.0.1:8000/" in md
    assert "http://127.0.0.1:5173/" in md
    assert "https://github.com/smfworks/aigc-production-flow" in md
    assert "https://github.com/smfworks/smf-h3-capture" in md
    assert "docs/STUDIO.md" in md
    assert "AIGC Studio" in md
    assert "AIGC Flow" in md
    assert "./scripts/dev-studio.sh all" in md
    assert "local-first" in md
    assert "No hosted" in md or "None verified" in md
    assert "does not invent" in md
    assert "studio-web is not running on :5174" in md
    assert "blank" in md
    assert "still embeds `:5174`" not in md
    assert "embeds `:5174` anyway" not in md
    assert "smf-aigc-studio-pane.vercel.app" not in md


def test_manifest_label():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "smf-aigc-studio-pane"
    assert manifest["label"] == "AIGC Studio"
    assert manifest["tab"]["path"] == "/aigc-studio"
    assert manifest["api"] == "plugin_api.py"

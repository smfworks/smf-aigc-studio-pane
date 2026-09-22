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
    assert "badge = 'Local'" in js
    assert "does not invent" in js
    assert "Local only" in js
    assert "No Live tab" in js
    assert "No hosted studio-web URL was verified" in js
    assert "children: 'Live'" not in js
    assert "SOURCE_KEY" not in js
    assert "$source" not in js
    assert "function SourceToggle" not in js
    assert "function LiveLocalFirst" not in js
    assert "persistSource" not in js
    assert "Use Local" not in js
    assert "local-first" not in js
    assert "vercel.app" not in js
    assert "http://127.0.0.1:5173/" not in js
    assert ".$iframeNonce.get(" not in js


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
    assert "local only" in payload["live_note"]
    assert "no Live tab" in payload["live_note"]
    assert "local-first" not in payload["live_note"]
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
    assert "no Live tab" in md
    assert "Live vs Local" not in md


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
    assert "local only" in md.lower() or "Local only" in md
    assert "no Live tab" in md
    assert "Live vs Local" not in md
    assert "No hosted" in md or "None verified" in md or "**None.**" in md
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


RUN = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


def _write_brief(root, run=RUN, *, produced=False, called=False, hermes=False, drop_dir=None, with_film=False, path=None):
    drop = root / run
    drop.mkdir(parents=True)
    jobs = [
        {
            "order": 1,
            "kind": "still-sheet",
            "subject": "lead",
            "adapter_label": "stub",
            "note": "Character sheet before any plate.",
        },
        {
            "order": 2,
            "kind": "clip-hop1",
            "take": "A",
            "adapter_label": "stub (lane not live)",
            "note": "Hop-1 after plates.",
        },
        {
            "order": 3,
            "kind": "stitch",
            "adapter_label": "awaiting stitch",
            "produced_mp4": produced,
            "called_comfy": False,
            "note": "Final job after hop-1 clips. Leave awaiting stitch.",
        },
    ]
    honesty = {
        "called_comfy": called,
        "hermes_ran": hermes,
        "produced_mp4": produced,
        "still_live": False,
        "clip_live": False,
        "still_label": "stub",
        "clip_label": "stub (lane not live)",
        "note": "Studio wrote this brief. Hermes has not been invoked. Comfy has not been called.",
    }
    if path:
        honesty["path"] = path
    (drop / "agent-brief.json").write_text(json.dumps({"jobs": jobs, "honesty": honesty}), encoding="utf-8")
    (drop / "hermes-handoff.json").write_text(
        json.dumps(
            {
                "kind": "aigc-hermes-handoff",
                "agent_run_id": run,
                "deep_link": "hermes://aigc/brief?run=" + run,
                "honesty": honesty,
            }
        ),
        encoding="utf-8",
    )
    latest = {
        "agent_run_id": run,
        "drop_dir": drop_dir if drop_dir is not None else str(drop),
        "deep_link": "hermes://aigc/brief?run=" + run,
        "open": "hermes-handoff.json",
        "called_comfy": called,
        "hermes_ran": hermes,
        "produced_mp4": produced,
        "written_at": "2026-09-22T00:00:00+00:00",
    }
    (root / "latest.json").write_text(json.dumps(latest), encoding="utf-8")
    if with_film:
        (drop / "stitch.mp4").write_bytes(b"bytes-on-disk")
    return drop


def test_latest_brief_lists_jobs_ending_in_stitch(tmp_path):
    _write_brief(tmp_path)
    payload = api.collect_handoff(roots=[tmp_path], probe_studio=False)
    assert payload["ok"] is True
    assert payload["badge"] == "Latest brief"
    assert payload["state"] == "brief"
    assert payload["source"] == "file"
    assert payload["agent_run_id"] == RUN
    assert payload["deep_link"] == "hermes://aigc/brief?run=" + RUN
    assert payload["called_comfy"] is False
    assert payload["hermes_ran"] is False
    assert payload["produced_mp4"] is False
    assert payload["finished_film"] is False
    assert payload["film_on_disk"] is False
    kinds = [job["kind"] for job in payload["jobs"]]
    assert kinds[-1] == "stitch"
    assert "still-sheet" in kinds
    assert payload["honesty"]["still_label"] == "stub"
    assert "awaiting stitch" in payload["stitch_note"] or "stitch" in payload["stitch_note"].lower()
    assert "pwned" not in json.dumps(payload)


def test_video_file_without_produced_flag_is_not_a_finished_film(tmp_path):
    _write_brief(tmp_path, with_film=True, produced=False, called=False, hermes=False)
    payload = api.collect_handoff(roots=[tmp_path], probe_studio=False)
    assert payload["produced_mp4"] is False
    assert payload["called_comfy"] is False
    assert payload["hermes_ran"] is False
    assert payload["film_on_disk"] is False
    assert payload["finished_film"] is False


def test_produced_flag_without_file_is_not_a_finished_film(tmp_path):
    _write_brief(tmp_path, produced=True)
    payload = api.collect_handoff(roots=[tmp_path], probe_studio=False)
    assert payload["produced_mp4"] is True
    assert payload["film_on_disk"] is False
    assert payload["finished_film"] is False
    assert payload["called_comfy"] is False
    assert payload["hermes_ran"] is False


def test_produced_flag_and_file_on_disk_is_a_finished_film(tmp_path):
    _write_brief(tmp_path, produced=True, with_film=True)
    payload = api.collect_handoff(roots=[tmp_path], probe_studio=False)
    assert payload["produced_mp4"] is True
    assert payload["film_on_disk"] is True
    assert payload["finished_film"] is True
    assert payload["called_comfy"] is False
    assert payload["hermes_ran"] is False


def test_drop_dir_outside_roots_is_not_read(tmp_path):
    root = tmp_path / "handoff"
    root.mkdir()
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "agent-brief.json").write_text(
        json.dumps({"jobs": [{"order": 1, "kind": "pwned", "called_comfy": True}], "honesty": {"called_comfy": True}}),
        encoding="utf-8",
    )
    _write_brief(root, drop_dir=str(secret))
    payload = api.collect_handoff(roots=[root], probe_studio=False)
    blob = json.dumps(payload)
    assert "pwned" not in blob
    assert payload["called_comfy"] is False
    assert payload["jobs"][-1]["kind"] == "stitch"
    assert payload["agent_run_id"] == RUN


def test_pack_zip_handoff_list_is_not_a_brief(tmp_path):
    def getter(url, headers=None):
        assert headers and headers.get("Authorization") == "Bearer local-dev-token"
        if url.endswith("/healthz") or url.endswith("/readyz"):
            return 200, '{"ok": true}', {}
        if url.endswith("/api/handoffs"):
            body = [
                {
                    "id": "pack-1",
                    "filename": "pack.zip",
                    "auto_generate": False,
                    "honesty": "Builder Open in Studio stages a pack zip.",
                }
            ]
            return 200, json.dumps(body), {}
        raise OSError("no run")

    payload = api.collect_handoff(roots=[tmp_path], getter=getter, probe_studio=True)
    assert payload["state"] == "empty"
    assert payload["badge"] == "No handoff yet"
    assert payload["agent_run_id"] == ""
    assert payload["jobs"] == []
    assert payload["called_comfy"] is False
    assert payload["finished_film"] is False
    assert "pack.zip" not in json.dumps(payload["jobs"])


def test_studio_agent_run_overlays_flags_without_inventing_a_film(tmp_path):
    drop = _write_brief(tmp_path)

    def getter(url, headers=None):
        assert headers["Authorization"].startswith("Bearer ")
        if url.endswith("/healthz"):
            return 200, '{"ok": true}', {}
        if url.endswith("/readyz"):
            return 200, '{"ok": true}', {}
        if url.endswith("/api/handoffs"):
            return 404, "not a list", {}
        if url.endswith("/api/agent-runs/" + RUN):
            return 200, json.dumps(
                {
                    "id": RUN,
                    "wizard_id": "wiz",
                    "deep_link": "hermes://aigc/brief?run=" + RUN,
                    "drop_dir": str(drop),
                    "called_comfy": True,
                    "hermes_ran": False,
                    "honesty_note": "A job result says Comfy was called.",
                    "stitch_state": "awaiting_stitch",
                    "steps": [
                        {
                            "order": 1,
                            "kind": "still-sheet",
                            "subject": "lead",
                            "status": "succeeded",
                            "called_comfy": True,
                            "adapter_label": "live",
                        },
                        {
                            "order": 3,
                            "kind": "stitch",
                            "status": "awaiting_stitch",
                            "produced_mp4": False,
                            "called_comfy": False,
                            "note": "Stitch plan only.",
                        },
                    ],
                }
            ), {}
        raise OSError(url)

    payload = api.collect_handoff(roots=[tmp_path], getter=getter, probe_studio=True)
    assert payload["source"] == "studio-api+file"
    assert payload["studio_api"] == "ok"
    assert payload["called_comfy"] is True
    assert payload["hermes_ran"] is False
    assert payload["produced_mp4"] is False
    assert payload["finished_film"] is False
    sheet = next(job for job in payload["jobs"] if job["kind"] == "still-sheet")
    assert sheet["status"] == "succeeded"
    assert payload["jobs"][-1]["kind"] == "stitch"


def test_studio_down_still_reads_latest_json(tmp_path):
    _write_brief(tmp_path)

    def getter(url, headers=None):
        raise OSError("connection refused")

    payload = api.collect_handoff(roots=[tmp_path], getter=getter, probe_studio=True)
    assert payload["badge"] == "Latest brief"
    assert payload["source"] == "file"
    assert payload["studio_api"] == "down"
    assert payload["called_comfy"] is False
    assert payload["hermes_ran"] is False


def test_requested_run_does_not_return_a_different_brief(tmp_path):
    _write_brief(tmp_path, run=RUN)
    payload = api.collect_handoff(run=OTHER, roots=[tmp_path], probe_studio=False)
    assert payload["state"] == "empty"
    assert payload["badge"] == "No handoff yet"
    assert payload["agent_run_id"] == ""
    assert OTHER in payload["honesty"]["note"]


def test_invalid_run_id_is_rejected():
    payload = api.collect_handoff(run="../etc/passwd", roots=[], probe_studio=False)
    assert payload["state"] == "empty"
    assert payload["jobs"] == []
    assert payload["finished_film"] is False


def test_agent_run_url_allowlist_stays_narrow():
    run_url = "http://127.0.0.1:8000/api/agent-runs/" + RUN
    assert api.local_url_allowed(run_url) is True
    assert api.local_url_allowed("http://127.0.0.1:8000/api/handoffs") is True
    assert api.local_url_allowed("http://127.0.0.1:8000/api/handoffs/" + RUN) is False
    assert api.local_url_allowed("http://127.0.0.1:8000/api/jobs") is False
    assert api.local_url_allowed("http://127.0.0.1:8000/api/agent-runs/../jobs") is False
    assert api.local_url_allowed("http://127.0.0.1:8000/api/agent-runs/") is False
    assert api.local_url_allowed("http://127.0.0.1:8000/api/meta") is False


def test_handoff_root_env_is_first(monkeypatch, tmp_path):
    monkeypatch.setenv("HANDOFF_ROOT", str(tmp_path / "from-env"))
    monkeypatch.delenv("STUDIO_HANDOFF_ROOT", raising=False)
    monkeypatch.delenv("STUDIO_HERMES_DROP", raising=False)
    monkeypatch.delenv("STUDIO_MEDIA_ROOT", raising=False)
    roots = api.default_handoff_roots()
    assert roots[0] == tmp_path / "from-env"
    assert Path.home() / ".hermes" / "aigc" in roots


def test_desktop_plugin_surfaces_handoff_brief():
    js = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    assert "Open latest brief" in js
    assert "Copy deep link" in js
    assert "Copy drop path" in js
    assert "Focus Studio Create" in js
    assert "Open AIGC handoff brief" in js
    assert "hermes://aigc/brief" in js
    assert "refetchInterval: 8000" in js
    assert "ctx.rest(path)" in js
    assert "'/handoff'" in js or '"/handoff"' in js
    assert "called_comfy" in js
    assert "hermes_ran" in js
    assert "produced_mp4" in js
    assert "No finished film" in js
    assert "No handoff yet" in js
    assert "Latest brief" in js
    assert "API unread" in js
    assert ".mp4" not in js
    assert "/api/jobs" not in js
    assert "generate-ok" not in js


def test_handoff_helpers_behavior():
    import shutil
    import subprocess

    node = shutil.which("node")
    assert node, "node is required to execute the handoff fixture"
    script = ROOT / "tests" / "handoff_check.mjs"
    proc = subprocess.run([node, str(script)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr


def test_readme_and_agents_document_handoff():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for text in (readme, agents):
        assert "hermes://aigc/brief?run=" in text
        assert "Open latest brief" in text
        assert "produced_mp4" in text
        assert "called_comfy" in text
        assert "latest.json" in text
    assert "Open AIGC handoff brief" in readme
    assert "Open AIGC handoff brief" in agents
    assert "GET /handoff" in readme
    assert "Do not start Hermes" in agents
    assert "No handoff yet" in agents

# SMF AIGC Studio — Hermes Desktop Plugin

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) desktop plugin that puts **AIGC Studio** in a wide column to the right of chat. It **embeds** local `studio-web` from [aigc-production-flow](https://github.com/smfworks/aigc-production-flow). It does not rewrite the studio shell into `plugin.js`, and it does not invent projects, jobs, packs, or media.

This is the companion to [smf-h3-capture](https://github.com/smfworks/smf-h3-capture) (**AIGC Flow**), which embeds the pack-builder SPA. Different pane, different port, different job.

| | This pane (`smf-aigc-studio-pane`) | Pack builder (`smf-h3-capture`) |
|---|---|---|
| Sidebar | **AIGC Studio** | **AIGC Flow** |
| Embeds | `studio-web` | Vite pack builder in `app/` |
| Local | `http://127.0.0.1:5174/` | `http://127.0.0.1:5173/` |
| API | `http://127.0.0.1:8000/` (`/healthz`, `/readyz`) | none (packs stay in the SPA) |
| Hosted | **None.** Local only. No Live tab. Vercel is the pack builder | `https://aigc-production-flow.vercel.app` |

Operator path: [docs/STUDIO.md](https://github.com/smfworks/aigc-production-flow/blob/main/docs/STUDIO.md).

## What it does

- **Right pane** — AIGC Studio, docked to the right of the workspace (`760px`)
- **Sidebar + palette** — AIGC Studio, plus ⌘K → **Open AIGC Studio** / **Open AIGC Studio pane**
- **Local studio-web** — the only source. The page probes `http://127.0.0.1:5174/` (`./scripts/dev-studio.sh all` or `./scripts/dev-studio.sh web` in `aigc-production-flow`) and iframes it only when that probe answers. If `:5174` is closed, the same probe tries Vite preview at `http://127.0.0.1:4174/`. If neither answers, the pane shows an empty state instead of a blank iframe. **Embed 5174 anyway** is an escape hatch on that empty state, not the default. There is no Live tab
- **API badge** — `API ready` from `GET /readyz`, `API not ready` when `/healthz` answers but `/readyz` does not, `API down` when nothing answers on `:8000`, `API unread` when this plugin's Python probe is not mounted. The badge never blocks the iframe when the client probe reached studio-web, and an unread Python probe does not mount the iframe by itself
- **Open Studio** — the local studio-web URL in the browser
- **Pack builder** — focuses the AIGC Flow pane (`/h3-capture`) when that plugin is installed; otherwise opens the [smf-h3-capture](https://github.com/smfworks/smf-h3-capture) repo. This pane does not embed port `5173`
- **Studio docs / GitHub** — `docs/STUDIO.md` and the product repo
- **Copy dev command** — `./scripts/dev-studio.sh all`
- **Honesty** — if the client probe cannot reach studio-web, the pane says **studio-web is not running on :5174** and how to start it (`./scripts/dev-studio.sh all` from `aigc-production-flow`). It does not iframe a refused connection. Electron often paints that as a blank white frame and does not fire iframe `onError`. Projects, continuity rows, jobs, and media are whatever studio-web itself loaded. This pane never fabricates them

Not in scope: Spark / Comfy / MiniMax calls, publishing likeness stills or MP4s, a generate button, or a second copy of the pack builder.

## Install

One shot (covers profiles + Desktop JS + enable):

```bash
git clone https://github.com/smfworks/smf-aigc-studio-pane.git ~/.hermes/plugins/smf-aigc-studio-pane
bash ~/.hermes/plugins/smf-aigc-studio-pane/install.sh
```

Or, if Hermes is already on PATH:

```bash
hermes plugins install smfworks/smf-aigc-studio-pane --enable
bash "${HERMES_HOME:-$HOME/.hermes}/plugins/smf-aigc-studio-pane/install.sh"
```

`install.sh` enables the plugin on `$HOME/.hermes` **and** every `profiles/*/plugins` home Desktop may spawn, copies `desktop/plugin.js` into `$HOME/.hermes/desktop-plugins/smf-aigc-studio-pane/` (what packaged Electron actually loads), and tells you to **quit and relaunch Desktop**.

**⌘K → Reload desktop plugins is JS only.** It does not mount `plugin_api.py`. The page still probes `:5174` itself (then `:4174`). A failed `GET /status` is not a reason to iframe a dead port, and it is not required when that client probe succeeds. Quit Desktop and relaunch from the menu if you want the optional `:8000` API badge.

Do **not** run `hermes desktop` to relaunch if you already have the packaged Linux binary. That command rewrites the `.desktop` `Exec=` and can prompt for `chrome-sandbox` sudo. Use the menu entry / `…/linux-unpacked/Hermes --no-sandbox`.

Then:

1. Settings → Plugins → AIGC Studio → on
2. The **AIGC Studio** pane on the right of chat, or Sidebar → **AIGC Studio**, or ⌘K → Open AIGC Studio pane
3. In a checkout of [aigc-production-flow](https://github.com/smfworks/aigc-production-flow): `./scripts/dev-studio.sh all`
   - Studio web `http://127.0.0.1:5174/`
   - API `http://127.0.0.1:8000/` (`/healthz`, `/readyz`, `/api/meta`)
   - Pack builder `http://127.0.0.1:5173/` — open **AIGC Flow**, not this iframe

### Give this to a Hermes agent

```
Install SMF AIGC Studio from https://github.com/smfworks/smf-aigc-studio-pane
Run bash ~/.hermes/plugins/smf-aigc-studio-pane/install.sh (clone first if missing).
Enable on $HOME/.hermes and every profiles/*/ that already has a plugins dir.
Copy desktop/plugin.js to $HOME/.hermes/desktop-plugins/smf-aigc-studio-pane/.
Do not run hermes desktop. Do not kill this chat from inside it.
Tell me to quit Hermes Desktop and relaunch from the menu so plugin_api.py mounts.
This pane is local only. There is no Live tab.
Embed http://127.0.0.1:5174/ from aigc-production-flow studio-web.
Do not invent a hosted studio URL. Do not port studio-web or the pack builder into plugin.js.
The pack builder pane is smf-h3-capture (AIGC Flow, :5173).
```

## Local only

There is no Live tab and no hosted studio-web URL. Vercel deploys the pack builder, which stays in **AIGC Flow**. This pane embeds studio-web on this machine.

| What you see | When |
|---|---|
| iframe `http://127.0.0.1:5174/` after the client probe answers | Studio-web on this machine (`./scripts/dev-studio.sh all` or `web`). A refused port shows an empty state, not a white iframe. |
| iframe `http://127.0.0.1:4174/` | After `npm run preview` in `studio-web/`. Used only if `:5174` is down and the client probe sees preview. |
| Empty state: **studio-web is not running on :5174** | Neither port answered. **Retry** probes again. **Embed 5174 anyway** is the manual override, not the default. |

Local studio-web is not started by this plugin. The iframe mounts only after the in-page probe reaches `:5174` or `:4174`. If both are closed, the pane says studio-web is not running on `:5174` and does not fabricate a project.

`/readyz` green means the studio API process reported ready (DB + worker mode, per `docs/STUDIO.md`). `/healthz` alone means the process answered liveness and is not the same as ready. Neither probe is a generate, and neither is rendered as job history.

## Phase 9, at the altitude of this pane

`studio-web` is the local shell around the FastAPI spine. When you embed it, the product surface includes:

- Projects, ordered episodes, pack revisions, and pack diff
- Identity store (approve, unapprove, keyword edit) and the continuity panel
- Review sign-off, comments, shots, and a job center
- Stub adapters by default — unset Comfy hooks stay stub
- Hop-1 desk and a playlist scrubber (a stub receipt is metadata, not an MP4)
- Writer / art / editor / producer roles, presence, multi-org lite, notifications, backup

`generate-ok` stays inside studio, and only after gates, hop-1 receipts, and sign-off. This pane does not call it and does not draw a fake queue. Likeness stills and engine MP4s are not shipped here. See [docs/STUDIO.md](https://github.com/smfworks/aigc-production-flow/blob/main/docs/STUDIO.md).

## Architecture

```
smf-aigc-studio-pane/
├── install.sh
├── AGENTS.md
├── plugin.yaml
├── __init__.py
├── dashboard/
│   ├── manifest.json        # api: plugin_api.py
│   └── plugin_api.py        # GET /status  GET /health
├── desktop/
│   └── plugin.js            # copy to ~/.hermes/desktop-plugins/smf-aigc-studio-pane/
└── tests/
    └── test_plugin.py
```

| Route | What it does |
|---|---|
| `GET /status` | Report local studio-web / preview / API URLs. Probe `127.0.0.1:5174`, `:4174`, and `:8000/readyz` + `/healthz` only. No project or job JSON. |
| `GET /health` | `{ status: ok, plugin }` |

The iframe uses the same sandbox as SMF H3 Capture (`allow-scripts allow-same-origin allow-forms allow-popups allow-downloads`) so studio-web can keep its own session and local auth header behavior.

## Tests

```bash
python3 -m pytest tests/ -q
```

Network is not required. URL allowlisting, probe honesty, the client reachability gate, and `plugin.js` ID/URL smoke checks run against fixtures.

## License

MIT — SMF Works

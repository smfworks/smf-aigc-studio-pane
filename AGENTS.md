# SMF AIGC Studio pane — agent notes

For Hermes/OpenClaw installing this repo on a user's machine.

Plugin id is `smf-aigc-studio-pane`. Sidebar label is **AIGC Studio**. The product is `studio-web` + the studio API in `smfworks/aigc-production-flow`. The pack builder pane is a different plugin: `smf-h3-capture` (**AIGC Flow**).

## Do

1. Clone to `$HOME/.hermes/plugins/smf-aigc-studio-pane` (or `hermes plugins install smfworks/smf-aigc-studio-pane --enable`).
2. Run `bash install.sh` from that tree. It enables the plugin on `$HOME/.hermes` **and** every `profiles/*/plugins` home, then copies `desktop/plugin.js` to `$HOME/.hermes/desktop-plugins/smf-aigc-studio-pane/`.
3. Tell the user to **quit Hermes Desktop and relaunch from the menu**. The Python API (`plugin_api.py`) mounts only on the next `hermes serve`.
4. Point Local at `http://127.0.0.1:5174/`. The user starts it from `aigc-production-flow` with `./scripts/dev-studio.sh all` (API on `:8000`, pack builder on `:5173` for the other pane).

## Do not

- Do not treat ⌘K → Reload desktop plugins as a backend remount. That is JS only. The JS probes `http://127.0.0.1:5174/` (then `:4174`) in the page and mounts the iframe only when that probe succeeds. Quit/relaunch is for the Python API badge (`plugin_api.py`). Do not invent a project when the probe fails.
- Do not hard-gate the iframe on the Python `/status` probe or on `/readyz`. If the JS probe reaches studio-web and the API does not, show the API badge and keep the iframe. If the JS probe fails, show the empty state (`studio-web is not running on :5174`) and `./scripts/dev-studio.sh all` from `aigc-production-flow`. Do not iframe a connection-refused port — Electron paints that as a blank white frame and often does not fire iframe `onError`. **Embed 5174 anyway** is an escape hatch, not the default.
- Do not run `hermes desktop` to relaunch if a packaged Electron binary already exists (`…/linux-unpacked/Hermes --no-sandbox`). `hermes desktop` rewrites the `.desktop` `Exec=` and can prompt for `chrome-sandbox` sudo.
- Do not `hermes serve --stop` (kills every serve on the box). Do not kill this chat from inside the same Desktop window unless the user asked for a relaunch.
- Do not port studio-web or the nine-gate pack builder into `plugin.js`. Embed local studio-web.
- Do not iframe the pack builder (`:5173` or the Vercel app) as this pane. Send the user to **AIGC Flow** / `smf-h3-capture`.
- Do not claim a hosted studio URL. Live is a local-first empty state with GitHub and `docs/STUDIO.md`. No hosted studio-web was verified.
- Do not invent projects, episodes, continuity, jobs, packs, stills, or MP4s. If Local studio-web is confirmed down, show an error. Empty is empty. Stub adapter receipts are the studio's, and they are not engine MP4s.
- Do not call Spark / Comfy / MiniMax APIs. Do not publish likeness stills or generated MP4s. Do not add a generate button.
- Do not add this as a launcher-only row in `smf-app-launcher`. This is a first-class pane.
- Do not `git reset --hard` an existing plugin checkout.

## After relaunch

Sidebar **AIGC Studio**, the right-of-chat pane, or ⌘K → **Open AIGC Studio** / **Open AIGC Studio pane**. Local embeds `http://127.0.0.1:5174/` only after the client probe reaches it. Preview fallback is `http://127.0.0.1:4174/` only when that probe sees it. API badge reads `http://127.0.0.1:8000/readyz` and `/healthz` and can stay unread or down without mounting a blank iframe.

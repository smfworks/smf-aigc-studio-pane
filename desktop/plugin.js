/**
 * SMF AIGC Studio pane — embed local studio-web from aigc-production-flow.
 * Disk plugin: jsx/jsxs only. Never invent projects, jobs, packs, or media.
 * Plugin id: smf-aigc-studio-pane. Pack builder stays in smf-h3-capture.
 * Local only. No Live tab. No hosted studio-web URL was verified.
 * Mounts an iframe only after a client probe reaches :5174 (or :4174).
 * Python /status is the API badge. It is not the iframe gate.
 * A strip above the iframe watches the Hermes brief (latest.json / Studio API).
 * It does not start Hermes or Comfy, and it does not invent a film.
 */
import {
  Badge,
  Button,
  Codicon,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  Separator,
  atom,
  cn,
  haptic,
  host,
  PALETTE_AREA,
  PANES_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  useQuery,
  useValue,
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'smf-aigc-studio-pane'
const ROUTE = '/aigc-studio'

const STUDIO_WEB_URL = 'http://127.0.0.1:5174/'
const STUDIO_PREVIEW_URL = 'http://127.0.0.1:4174/'
const API_ORIGIN = 'http://127.0.0.1:8000/'
const READYZ_URL = 'http://127.0.0.1:8000/readyz'
const HEALTHZ_URL = 'http://127.0.0.1:8000/healthz'
const GITHUB_URL = 'https://github.com/smfworks/aigc-production-flow'
const DOCS_URL = 'https://github.com/smfworks/aigc-production-flow/blob/main/docs/STUDIO.md'
const PACK_BUILDER_REPO = 'https://github.com/smfworks/smf-h3-capture'
const PACK_BUILDER_ROUTE = '/h3-capture'
const DEV_COMMAND = './scripts/dev-studio.sh all'
const CLIENT_PROBE_MS = 2000

const HONESTY_NOTE =
  'Local only. No hosted studio-web URL was verified. Embeds studio-web on this machine. This pane does not invent projects, continuity, jobs, packs, or media. Default studio adapter is stub.'
const PACK_NOTE =
  'Pack builder is a different pane (smf-h3-capture). This pane does not embed it and does not sync packs.'
const HANDOFF_NOTE =
  'Studio writes the brief. This pane does not start Hermes and does not call Comfy. called_comfy and hermes_ran stay false until the brief says they are true. A file on disk is not a run. No finished film unless produced_mp4 is true and that file is on disk.'
const RUN_ID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/

const IFRAME_SANDBOX = 'allow-scripts allow-same-origin allow-forms allow-popups allow-downloads'

const $iframeError = atom(false)
const $iframeNonce = atom(0)
const $forceEmbed = atom(false)
const $copyHint = atom('')
const $clientProbeTick = atom(0)
const $briefOpen = atom(false)
const $briefRun = atom('')
const $handoffHint = atom('')
const $createFocus = atom(0)
let iframeNonce = 0
let clientProbeTick = 0
let createFocus = 0
let locationBriefRead = false

function remountFrame() {
  iframeNonce += 1
  $iframeError.set(false)
  $iframeNonce.set(iframeNonce)
}

function retryLocalProbe() {
  $forceEmbed.set(false)
  clientProbeTick += 1
  $clientProbeTick.set(clientProbeTick)
  remountFrame()
}

function openExternal(url) {
  if (!url) return
  const tryRequest = (method, params) => {
    try {
      const p = host.request(method, params)
      if (p && typeof p.then === 'function') return p
      return Promise.resolve(p)
    } catch (err) {
      return Promise.reject(err)
    }
  }
  const fallback = () => {
    try {
      if (typeof window !== 'undefined' && typeof window.open === 'function') {
        window.open(url, '_blank', 'noopener,noreferrer')
      }
    } catch {
      /* host blocked popups */
    }
  }
  try {
    if (typeof host.openExternal === 'function') {
      void Promise.resolve(host.openExternal(url)).catch(fallback)
      return
    }
    if (typeof host.open === 'function') {
      void Promise.resolve(host.open(url)).catch(fallback)
      return
    }
  } catch {
    /* continue */
  }
  void tryRequest('os.openExternal', { url })
    .catch(() => tryRequest('os.open', { url }))
    .catch(() => tryRequest('shell.openExternal', { url }))
    .catch(fallback)
}

function openPackBuilderPane() {
  try {
    if (typeof host.navigate === 'function') {
      host.navigate(PACK_BUILDER_ROUTE)
      return
    }
  } catch {
    /* fall through to the pane repo */
  }
  openExternal(PACK_BUILDER_REPO)
}

function copyDevCommand() {
  const done = (ok) => {
    $copyHint.set(ok ? 'copied' : 'copy failed — command is shown below')
  }
  try {
    if (
      typeof navigator !== 'undefined' &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === 'function'
    ) {
      void Promise.resolve(navigator.clipboard.writeText(DEV_COMMAND))
        .then(() => done(true))
        .catch(() => done(false))
      return
    }
  } catch {
    /* fall through */
  }
  done(false)
}

function asStatus(data) {
  if (!data || typeof data !== 'object') return null
  return data
}

function probeOne(url) {
  if (typeof fetch !== 'function') return Promise.resolve(false)
  if (url !== STUDIO_WEB_URL && url !== STUDIO_PREVIEW_URL) return Promise.resolve(false)
  const Controller = typeof AbortController === 'function' ? AbortController : null
  const controller = Controller ? new Controller() : null
  const opts = {
    method: 'GET',
    mode: 'no-cors',
    cache: 'no-store',
    credentials: 'omit',
  }
  if (controller) opts.signal = controller.signal
  const attempt = fetch(url, opts)
    .then((res) => {
      // no-cors yields an opaque response (status 0) when the server answered.
      // That is reachable. Connection refused rejects. Do not treat a false
      // ok flag as down: an opaque response reports ok false anyway.
      if (!res) return false
      if (res.type === 'opaque' || res.status === 0) return true
      return true
    })
    .catch(() => false)
  return new Promise((resolve) => {
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(value)
    }
    const timer = setTimeout(() => {
      if (controller) {
        try {
          controller.abort()
        } catch {
          /* already settled */
        }
      }
      finish(false)
    }, CLIENT_PROBE_MS)
    attempt.then((ok) => finish(ok))
  })
}

async function probeLocalStudio() {
  // Independent of plugin_api.py. Prefer studio-web, then vite preview.
  // Do not probe the pack builder.
  if (typeof fetch !== 'function') return { reachable: false, url: '' }
  const devPromise = probeOne(STUDIO_WEB_URL)
  const previewPromise = probeOne(STUDIO_PREVIEW_URL)
  const devUp = await devPromise
  if (devUp) return { reachable: true, url: STUDIO_WEB_URL }
  const previewUp = await previewPromise
  if (previewUp) return { reachable: true, url: STUDIO_PREVIEW_URL }
  return { reachable: false, url: '' }
}

function clientReachableFrom(client) {
  return Boolean(
    client &&
      client.reachable === true &&
      (client.url === STUDIO_WEB_URL || client.url === STUDIO_PREVIEW_URL),
  )
}

function apiBadgeLabel(status, backendDown) {
  if (backendDown || !status || !status.api) return 'API unread'
  const api = status.api
  if (api.ready === true) return 'API ready'
  if (api.health === true) return 'API not ready'
  if (api.reachable === true) return 'API not ready'
  if (api.reachable === false) return 'API down'
  return 'API unread'
}

// HANDOFF_PURE_START
function parseBriefLink(value) {
  if (!value || typeof value !== 'string') return null
  const trimmed = value.trim()
  const match = trimmed.match(/^hermes:\/\/aigc\/brief\/?\?run=([0-9a-fA-F-]{36})(?:&|$)/)
  if (match && RUN_ID_RE.test(match[1])) return { run: match[1] }
  try {
    const url = new URL(trimmed)
    const hostName = (url.hostname || '').toLowerCase()
    const path = url.pathname || ''
    if (
      url.protocol === 'hermes:' &&
      hostName === 'aigc' &&
      (path === '/brief' || path === '/brief/')
    ) {
      const run = url.searchParams.get('run') || ''
      if (RUN_ID_RE.test(run)) return { run: run }
    }
  } catch {
    return null
  }
  return null
}

function handoffBadge(payload, requestFailed) {
  if (requestFailed || !payload || typeof payload !== 'object') return 'API unread'
  if (payload.badge === 'Latest brief' && payload.agent_run_id) return 'Latest brief'
  if (payload.badge === 'No handoff yet' || payload.state === 'empty') return 'No handoff yet'
  if (payload.badge === 'API unread' || payload.state === 'unread' || payload.ok === false) {
    return 'API unread'
  }
  if (payload.state === 'brief' && payload.agent_run_id) return 'Latest brief'
  return 'No handoff yet'
}

function filmClaim(row) {
  const produced = Boolean(row && row.produced_mp4 === true)
  const onDisk = Boolean(row && row.film_on_disk === true)
  if (produced && onDisk) {
    return 'Finished film: produced_mp4 is true and the file is on disk.'
  }
  if (produced && !onDisk) {
    return 'produced_mp4 is true, but the file is not on disk. This is not a finished film.'
  }
  return 'No finished film. produced_mp4 is false. Stitch stays a plan until a real file exists. This pane does not invent one.'
}

function flagClaim(row) {
  const called = Boolean(row && row.called_comfy === true)
  const ran = Boolean(row && row.hermes_ran === true)
  return {
    called_comfy: called,
    hermes_ran: ran,
    called_line: called
      ? 'called_comfy is true on this brief.'
      : 'called_comfy is false. A file on disk is not a Comfy run.',
    hermes_line: ran
      ? 'hermes_ran is true on this brief.'
      : 'hermes_ran is false. Studio did not start Hermes. This pane does not start it either.',
  }
}

function laneClaim(honesty) {
  const row = honesty && typeof honesty === 'object' ? honesty : {}
  const still = row.still_label || (row.still_live === true ? 'live' : 'stub')
  const clip = row.clip_label || (row.clip_live === true ? 'live' : 'stub')
  return 'Stills ' + still + '. Clips ' + clip + '. Unset lanes are not live.'
}
// HANDOFF_PURE_END

function withCreateHash(url) {
  if (!url) return ''
  const base = url.endsWith('/') ? url : url + '/'
  return base + '#/create'
}

function readLocationBriefOnce() {
  if (locationBriefRead) return
  locationBriefRead = true
  if (typeof window === 'undefined' || !window.location) return
  const href = String(window.location.href || '')
  const fromLink = parseBriefLink(href)
  if (fromLink) {
    $briefRun.set(fromLink.run)
    $briefOpen.set(true)
    return
  }
  try {
    const run = new URL(href).searchParams.get('run') || ''
    if (RUN_ID_RE.test(run)) {
      $briefRun.set(run)
      $briefOpen.set(true)
    }
  } catch {
    /* not a url */
  }
}

function deliverBriefLink(url) {
  const parsed = parseBriefLink(typeof url === 'string' ? url : (url && url.url) || '')
  if (!parsed) return false
  $briefRun.set(parsed.run)
  $briefOpen.set(true)
  try {
    host.navigate(ROUTE)
  } catch {
    /* palette command still opens the pane */
  }
  return true
}

function bindBriefProtocol() {
  const bind = (target, method, args) => {
    try {
      if (target && typeof target[method] === 'function') target[method].apply(target, args)
    } catch {
      /* this host has no protocol hook */
    }
  }
  bind(host, 'registerProtocol', ['hermes', deliverBriefLink])
  bind(host, 'handleProtocol', ['hermes://aigc/brief', deliverBriefLink])
  bind(host, 'on', ['open-url', deliverBriefLink])
  bind(host, 'on', ['deep-link', deliverBriefLink])
  bind(host, 'on', ['protocol', deliverBriefLink])
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    try {
      window.addEventListener('open-url', (event) => {
        const detail = event && event.detail
        const url = (event && event.url) || (detail && detail.url) || ''
        deliverBriefLink(url)
      })
    } catch {
      /* ignore */
    }
  }
}

function openLatestBrief() {
  $briefRun.set('')
  $briefOpen.set(true)
}

function copyField(value, okText, emptyText) {
  const text = value ? String(value) : ''
  if (!text) {
    $handoffHint.set(emptyText)
    return
  }
  const done = (ok) => {
    $handoffHint.set(ok ? okText : 'copy failed')
  }
  try {
    if (
      typeof navigator !== 'undefined' &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === 'function'
    ) {
      void Promise.resolve(navigator.clipboard.writeText(text))
        .then(() => done(true))
        .catch(() => done(false))
      return
    }
  } catch {
    /* fall through */
  }
  done(false)
}

function focusStudioCreate(frameMounted) {
  if (!frameMounted) {
    $handoffHint.set('Open Create in the studio iframe after studio-web is running (#/create).')
    return
  }
  createFocus += 1
  $createFocus.set(createFocus)
  $handoffHint.set('Studio iframe set to #/create.')
}

function jobLine(job) {
  const kind = job && job.kind ? String(job.kind) : 'job'
  const order = job && job.order != null && job.order !== '' ? String(job.order) : ''
  const bits = [order ? order + '. ' + kind : kind]
  if (job && job.subject) bits.push(String(job.subject))
  if (job && job.take) bits.push('take ' + String(job.take))
  if (job && job.adapter_label) bits.push(String(job.adapter_label))
  if (job && job.status) bits.push(String(job.status))
  return bits.join(' · ')
}

function BriefJobs({ jobs }) {
  if (!Array.isArray(jobs) || jobs.length === 0) {
    return jsx('div', {
      className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
      children: 'No ordered jobs in this brief.',
    })
  }
  return jsx('ol', {
    className: 'flex list-decimal flex-col gap-1 pl-4 text-[0.6875rem] text-(--ui-text-secondary)',
    children: jobs.map((job, index) =>
      jsx('li', { children: jobLine(job) }, String((job && job.order) || index) + ':' + String((job && job.kind) || '')),
    ),
  })
}

function BriefDetail({ brief, failed }) {
  if (failed) {
    return jsx(EmptyState, {
      title: 'API unread',
      description:
        'The handoff reader is not mounted. Quit Hermes Desktop and relaunch from the menu so plugin_api.py can watch latest.json. This pane did not invent a brief.',
    })
  }
  const row = brief && brief.state === 'brief' ? brief : null
  if (!row) {
    const watched = brief && Array.isArray(brief.roots_checked) ? brief.roots_checked.filter(Boolean) : []
    const where = watched.length ? ' Watched ' + watched.join(', ') + '.' : ''
    return jsx(EmptyState, {
      title: 'No handoff yet',
      description:
        'No latest.json brief is available from the Studio API or the handoff folders.' +
        where +
        ' Send to Hermes in Studio, then this strip updates. Nothing was invented.',
    })
  }
  const flags = flagClaim(row)
  const honesty = row.honesty || {}
  return jsxs('div', {
    className: 'flex flex-col gap-2 rounded-md px-1 py-1',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx('div', {
            className: 'min-w-0 flex-1 truncate text-xs font-medium',
            children: 'Latest brief',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              $briefOpen.set(false)
            },
            children: 'Close brief',
          }),
        ],
      }),
      jsxs('div', {
        className: 'text-[0.6875rem] text-(--ui-text-secondary)',
        children: [
          'Run ',
          jsx('code', { children: row.agent_run_id || '' }),
        ],
      }),
      row.deep_link
        ? jsx('div', {
            className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
            children: row.deep_link,
          })
        : null,
      row.drop_dir
        ? jsx('div', {
            className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
            children: row.drop_dir,
          })
        : null,
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-secondary)',
        children: flags.called_line,
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-secondary)',
        children: flags.hermes_line,
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-secondary)',
        children: laneClaim(honesty),
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-secondary)',
        children: filmClaim(row),
      }),
      honesty.note
        ? jsx('div', {
            className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
            children: honesty.note,
          })
        : null,
      jsx(BriefJobs, { jobs: row.jobs }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: row.stitch_note || 'Stitch is the last job.',
      }),
    ],
  })
}

function HandoffStrip({ handoff, handoffError, frameMounted }) {
  const open = useValue($briefOpen)
  const hint = useValue($handoffHint)
  const failed = Boolean(handoffError && !handoff)
  const badge = handoffBadge(handoff, failed)
  const row = handoff && typeof handoff === 'object' ? handoff : null
  const deepLink = row && row.deep_link ? String(row.deep_link) : ''
  const dropDir = row && row.drop_dir ? String(row.drop_dir) : ''
  return jsxs('div', {
    className: 'flex flex-col gap-2 px-4 pb-2',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(Badge, { className: 'shrink-0 text-[0.625rem]', children: badge }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              openLatestBrief()
            },
            children: 'Open latest brief',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              copyField(deepLink, 'deep link copied', 'no deep link yet')
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'copy', size: 14 }), 'Copy deep link'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              copyField(dropDir, 'drop path copied', 'no drop path yet')
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'copy', size: 14 }), 'Copy drop path'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              focusStudioCreate(frameMounted)
            },
            children: 'Focus Studio Create',
          }),
        ],
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: HANDOFF_NOTE,
      }),
      hint
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
            children: hint,
          })
        : null,
      open ? jsx(BriefDetail, { brief: row, failed }) : null,
    ],
  })
}

function Chrome({ embedUrl, badge, apiLabel }) {
  const copyHint = useValue($copyHint)
  const browserUrl = embedUrl || STUDIO_WEB_URL
  return jsxs('div', {
    className: 'flex flex-col gap-2 px-4 pt-4 pb-2',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx(Codicon, { name: 'server', size: 16 }),
          jsx('div', {
            className: 'min-w-0 flex-1 truncate text-sm font-medium tracking-wide',
            children: 'AIGC Studio',
          }),
          badge
            ? jsx(Badge, { className: 'shrink-0 text-[0.625rem]', children: badge })
            : null,
          apiLabel
            ? jsx(Badge, { className: 'shrink-0 text-[0.625rem]', children: apiLabel })
            : null,
        ],
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: HONESTY_NOTE,
      }),
      jsx('div', {
        className: 'text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: PACK_NOTE,
      }),
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              openExternal(browserUrl)
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'link-external', size: 14 }), 'Open Studio'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              openPackBuilderPane()
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'layout', size: 14 }), 'Pack builder'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              openExternal(DOCS_URL)
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'book', size: 14 }), 'Studio docs'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              openExternal(GITHUB_URL)
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'github', size: 14 }), 'GitHub'],
            }),
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            className: 'h-7 text-xs',
            onClick: () => {
              haptic('tap')
              copyDevCommand()
            },
            children: jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(Codicon, { name: 'copy', size: 14 }), 'Copy dev command'],
            }),
          }),
        ],
      }),
      jsxs('div', {
        className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
        children: [
          'From aigc-production-flow: ',
          jsx('code', { className: 'text-(--ui-text-secondary)', children: DEV_COMMAND }),
          copyHint ? ' · ' + copyHint : '',
          ' · API ',
          API_ORIGIN,
          ' ',
          READYZ_URL,
          ' ',
          HEALTHZ_URL,
        ],
      }),
    ],
  })
}

function EmbedFrame({ url, title, onRetry, createFocusCount }) {
  const nonce = useValue($iframeNonce)
  const failed = useValue($iframeError)
  const focusCount = createFocusCount || 0
  const src = focusCount ? withCreateHash(url) : url
  if (!url) {
    return jsx(EmptyState, {
      title: 'No embed URL',
      description: 'Nothing to load. This pane does not invent studio records.',
    })
  }
  if (failed) {
    return jsxs('div', {
      className: 'flex h-full flex-col items-center justify-center gap-3 p-8',
      children: [
        jsx(ErrorState, {
          title: 'Could not load AIGC Studio',
          description:
            'The iframe did not load ' +
            url +
            '. Projects, jobs, and packs were not invented. Start studio-web with ./scripts/dev-studio.sh all.',
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(Button, {
              variant: 'ghost',
              size: 'sm',
              onClick: () => {
                haptic('tap')
                if (typeof onRetry === 'function') onRetry()
                else remountFrame()
              },
              children: 'Retry',
            }),
          ],
        }),
      ],
    })
  }
  return jsx('iframe', {
    key: String(nonce) + ':' + String(focusCount) + ':' + src,
    id: 'smf-aigc-studio-pane-frame',
    src: src,
    title: title || 'AIGC Studio',
    className: 'min-h-0 w-full flex-1 border-0 bg-(--ui-bg)',
    sandbox: IFRAME_SANDBOX,
    allow: 'clipboard-read; clipboard-write',
    referrerPolicy: 'no-referrer',
    onError: () => {
      $iframeError.set(true)
    },
  })
}

function LocalMissing({ onRetry, apiLabel }) {
  const label = apiLabel || 'API unread'
  const description =
    'Nothing answered http://127.0.0.1:5174/ or the preview fallback http://127.0.0.1:4174/. From aigc-production-flow run ./scripts/dev-studio.sh all. This pane does not invent projects, jobs, or packs. ' +
    label +
    ' is a badge only — the API badge is not a gate and does not mount a blank iframe.'
  return jsxs('div', {
    className: 'flex h-full flex-col items-center justify-center gap-3 p-8',
    children: [
      jsx(EmptyState, {
        title: 'studio-web is not running on :5174',
        description,
      }),
      jsxs('div', {
        className: 'flex flex-wrap items-center justify-center gap-2',
        children: [
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              onRetry()
            },
            children: 'Retry',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              $forceEmbed.set(true)
              remountFrame()
            },
            children: 'Embed 5174 anyway',
          }),
        ],
      }),
    ],
  })
}

function CheckingStudio() {
  return jsxs('div', {
    className: 'flex flex-1 flex-col items-center justify-center gap-3',
    children: [
      jsx(GlyphSpinner, { size: 24 }),
      jsx('div', {
        className: 'text-sm text-(--ui-text-secondary)',
        children: 'Checking local studio-web…',
      }),
    ],
  })
}

function LocalStudio({
  apiLabel,
  refetchStatus,
  isFetchingStatus,
  handoff,
  handoffError,
  refetchHandoff,
}) {
  const forceEmbed = useValue($forceEmbed)
  const tick = useValue($clientProbeTick)
  const createFocusCount = useValue($createFocus)
  const { data: client, isLoading, isFetching, error } = useQuery({
    queryKey: [ID, 'client-web', tick],
    queryFn: () => probeLocalStudio(),
    staleTime: 4 * 1000,
    retry: 0,
  })
  const clientReachable = clientReachableFrom(client)
  const probePending =
    !forceEmbed &&
    !clientReachable &&
    !error &&
    (isLoading || isFetching || client == null)

  let embedUrl = ''
  let badge = 'Local'
  if (forceEmbed) {
    embedUrl = STUDIO_WEB_URL
    badge = 'Local'
  } else if (clientReachable) {
    embedUrl = client.url
    badge = client.url === STUDIO_PREVIEW_URL ? 'Preview' : 'Local'
  }

  const onRetry = () => {
    retryLocalProbe()
    void refetchStatus()
    if (typeof refetchHandoff === 'function') void refetchHandoff()
  }

  const strip = jsx(HandoffStrip, {
    handoff,
    handoffError,
    frameMounted: Boolean(embedUrl),
  })

  if (!forceEmbed && !clientReachable) {
    return jsxs('div', {
      className: 'flex h-full min-h-0 flex-col bg-(--ui-bg)',
      children: [
        jsx(Chrome, { embedUrl: '', badge, apiLabel }),
        strip,
        jsx(Separator, {}),
        probePending
          ? jsx(CheckingStudio, {})
          : jsx(LocalMissing, { apiLabel, onRetry }),
      ],
    })
  }

  return jsxs('div', {
    className: cn('flex h-full min-h-0 flex-col bg-(--ui-bg)'),
    children: [
      jsx(Chrome, { embedUrl, badge, apiLabel }),
      strip,
      isFetchingStatus
        ? jsx('div', {
            className: 'px-4 text-[0.625rem] text-(--ui-text-quaternary)',
            children: 'updating API badge',
          })
        : null,
      jsx(Separator, {}),
      jsx(EmbedFrame, {
        url: embedUrl,
        title: 'AIGC Studio',
        onRetry,
        createFocusCount,
      }),
    ],
  })
}

function StudioPane({ ctx }) {
  readLocationBriefOnce()
  const briefRun = useValue($briefRun)
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: [ID, 'status'],
    queryFn: async () => ctx.rest('/status'),
    staleTime: 10 * 1000,
    retry: 1,
  })
  const handoffQuery = useQuery({
    queryKey: [ID, 'handoff', briefRun],
    queryFn: async () => {
      const path = briefRun ? '/handoff/' + briefRun : '/handoff'
      return ctx.rest(path)
    },
    staleTime: 5 * 1000,
    refetchInterval: 8000,
    retry: 0,
  })
  const status = asStatus(data)
  const backendDown = Boolean(error && !data)
  const apiLabel = apiBadgeLabel(status, backendDown)

  return jsx(LocalStudio, {
    apiLabel,
    refetchStatus: refetch,
    isFetchingStatus: isFetching,
    handoff: handoffQuery.data,
    handoffError: handoffQuery.error,
    refetchHandoff: handoffQuery.refetch,
  })
}

export default {
  id: ID,
  name: 'AIGC Studio',
  defaultEnabled: true,
  register(ctx) {
    bindBriefProtocol()
    ctx.registerMany([
      {
        id: 'pane',
        area: PANES_AREA,
        title: 'AIGC Studio',
        data: {
          placement: 'right',
          width: '760px',
          dock: { pane: 'workspace', pos: 'right' },
        },
        render: () => jsx(StudioPane, { ctx }),
      },
      {
        id: `${ID}-nav`,
        area: SIDEBAR_NAV_AREA,
        data: { path: ROUTE, label: 'AIGC Studio', codicon: 'server' },
      },
      {
        id: `${ID}-route`,
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(StudioPane, { ctx }),
      },
      {
        id: `${ID}-palette`,
        area: PALETTE_AREA,
        data: {
          id: `${ID}-open`,
          label: 'Open AIGC Studio',
          keywords: ['aigc', 'studio', 'studio-web', 'continuity', 'identity', 'jobs', 'projects', '5174'],
          run: () => host.navigate(ROUTE),
        },
      },
      {
        id: `${ID}-palette-pane`,
        area: PALETTE_AREA,
        data: {
          id: `${ID}-open-pane`,
          label: 'Open AIGC Studio pane',
          keywords: ['aigc', 'studio', 'pane', 'studio-web', 'local', '5174', 'continuity'],
          run: () => host.navigate(ROUTE),
        },
      },
      {
        id: `${ID}-palette-brief`,
        area: PALETTE_AREA,
        data: {
          id: `${ID}-open-brief`,
          label: 'Open AIGC handoff brief',
          keywords: [
            'aigc',
            'handoff',
            'brief',
            'hermes',
            'deep link',
            'hermes://aigc/brief',
            'latest.json',
          ],
          run: () => {
            openLatestBrief()
            host.navigate(ROUTE)
          },
        },
      },
    ])
  },
}

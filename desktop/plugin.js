/**
 * SMF AIGC Studio pane — embed local studio-web from aigc-production-flow.
 * Disk plugin: jsx/jsxs only. Never invent projects, jobs, packs, or media.
 * Plugin id: smf-aigc-studio-pane. Pack builder stays in smf-h3-capture.
 * Local only. No Live tab. No hosted studio-web URL was verified.
 * Mounts an iframe only after a client probe reaches :5174 (or :4174).
 * Python /status is the API badge. It is not the iframe gate.
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

const IFRAME_SANDBOX = 'allow-scripts allow-same-origin allow-forms allow-popups allow-downloads'

const $iframeError = atom(false)
const $iframeNonce = atom(0)
const $forceEmbed = atom(false)
const $copyHint = atom('')
const $clientProbeTick = atom(0)
let iframeNonce = 0
let clientProbeTick = 0

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

function EmbedFrame({ url, title, onRetry }) {
  const nonce = useValue($iframeNonce)
  const failed = useValue($iframeError)
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
    key: String(nonce) + ':' + url,
    id: 'smf-aigc-studio-pane-frame',
    src: url,
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

function LocalStudio({ apiLabel, refetchStatus, isFetchingStatus }) {
  const forceEmbed = useValue($forceEmbed)
  const tick = useValue($clientProbeTick)
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
  }

  if (!forceEmbed && !clientReachable) {
    return jsxs('div', {
      className: 'flex h-full min-h-0 flex-col bg-(--ui-bg)',
      children: [
        jsx(Chrome, { embedUrl: '', badge, apiLabel }),
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
      isFetchingStatus
        ? jsx('div', {
            className: 'px-4 text-[0.625rem] text-(--ui-text-quaternary)',
            children: 'updating API badge',
          })
        : null,
      jsx(Separator, {}),
      jsx(EmbedFrame, { url: embedUrl, title: 'AIGC Studio', onRetry }),
    ],
  })
}

function StudioPane({ ctx }) {
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: [ID, 'status'],
    queryFn: async () => ctx.rest('/status'),
    staleTime: 10 * 1000,
    retry: 1,
  })
  const status = asStatus(data)
  const backendDown = Boolean(error && !data)
  const apiLabel = apiBadgeLabel(status, backendDown)

  return jsx(LocalStudio, {
    apiLabel,
    refetchStatus: refetch,
    isFetchingStatus: isFetching,
  })
}

export default {
  id: ID,
  name: 'AIGC Studio',
  defaultEnabled: true,
  register(ctx) {
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
    ])
  },
}

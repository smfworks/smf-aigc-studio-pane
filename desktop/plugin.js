/**
 * SMF AIGC Studio pane — embed local studio-web from aigc-production-flow.
 * Disk plugin: jsx/jsxs only. Never invent projects, jobs, packs, or media.
 * Plugin id: smf-aigc-studio-pane. Pack builder stays in smf-h3-capture.
 * No hosted studio-web URL was verified — default source is Local.
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

const LIVE_NOTE =
  'No hosted studio-web URL was verified. Studio is local-first. The Vercel deploy is the pack builder (AIGC Flow / smf-h3-capture), not this pane.'
const HONESTY_NOTE =
  'Embeds studio-web only. This pane does not invent projects, continuity, jobs, packs, or media. Default studio adapter is stub.'
const PACK_NOTE =
  'Pack builder is a different pane (smf-h3-capture). This pane does not embed it and does not sync packs.'

const SOURCE_KEY = 'smf-aigc-studio-pane.source'
const IFRAME_SANDBOX = 'allow-scripts allow-same-origin allow-forms allow-popups allow-downloads'

const $source = atom(readStoredSource())
const $iframeError = atom(false)
const $iframeNonce = atom(0)
const $forceEmbed = atom(false)
const $copyHint = atom('')
let iframeNonce = 0

function remountFrame() {
  iframeNonce += 1
  $iframeError.set(false)
  $iframeNonce.set(iframeNonce)
}

function readStoredSource() {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return 'local'
    const raw = window.localStorage.getItem(SOURCE_KEY)
    return raw === 'live' ? 'live' : 'local'
  } catch {
    return 'local'
  }
}

function persistSource(next) {
  $source.set(next)
  $forceEmbed.set(false)
  remountFrame()
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(SOURCE_KEY, next)
    }
  } catch {
    /* private mode */
  }
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

function webTarget(data) {
  const web = data && data.web
  const url = web && web.reachable_url
  if (typeof url === 'string' && (url === STUDIO_WEB_URL || url === STUDIO_PREVIEW_URL)) {
    return url
  }
  if (web && web.dev_reachable) return STUDIO_WEB_URL
  if (web && web.preview_reachable) return STUDIO_PREVIEW_URL
  return null
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

function SourceToggle({ source }) {
  return jsxs('div', {
    className: 'inline-flex items-center gap-1 rounded-md border border-(--ui-stroke-secondary) p-0.5',
    children: [
      jsx(Button, {
        variant: source === 'live' ? 'default' : 'ghost',
        size: 'sm',
        className: 'h-7 text-xs',
        onClick: () => {
          haptic('tap')
          persistSource('live')
        },
        children: 'Live',
      }),
      jsx(Button, {
        variant: source === 'local' ? 'default' : 'ghost',
        size: 'sm',
        className: 'h-7 text-xs',
        onClick: () => {
          haptic('tap')
          persistSource('local')
        },
        children: 'Local',
      }),
    ],
  })
}

function Chrome({ source, embedUrl, badge, apiLabel }) {
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
          jsx(SourceToggle, { source }),
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

function EmbedFrame({ url, title }) {
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
                remountFrame()
              },
              children: 'Retry',
            }),
            jsx(Button, {
              variant: 'ghost',
              size: 'sm',
              onClick: () => {
                haptic('tap')
                persistSource('live')
              },
              children: 'Local-first note',
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
  const title = 'Studio web is not reachable'
  const description =
    'Nothing is listening on http://127.0.0.1:5174/ (studio-web) or http://127.0.0.1:4174/ (vite preview). From aigc-production-flow run ./scripts/dev-studio.sh all. This pane does not invent projects, jobs, or packs. API status (' +
    (apiLabel || 'API unread') +
    ') is a badge only — it does not block the iframe when studio-web is up. Quit Hermes Desktop and relaunch from the menu only if you want the optional probe badge. Reload desktop plugins is JS only.'
  return jsxs('div', {
    className: 'flex h-full flex-col items-center justify-center gap-3 p-8',
    children: [
      jsx(ErrorState, { title, description }),
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
              persistSource('live')
            },
            children: 'Local-first note',
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

function LiveLocalFirst({ status, apiLabel }) {
  const webUp = Boolean(status && status.web && status.web.reachable === true)
  const detail = webUp
    ? 'Local studio-web answered the probe. Switch to Local to embed http://127.0.0.1:5174/. This note is not a hosted studio.'
    : LIVE_NOTE + ' Run ./scripts/dev-studio.sh all, then use Local. Empty here means no hosted URL — not an empty project.'
  return jsxs('div', {
    className: 'flex h-full flex-col items-center justify-center gap-3 p-8',
    children: [
      jsx(EmptyState, {
        title: 'Studio is local-first',
        description: detail,
      }),
      jsx('div', {
        className: 'max-w-md text-center text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children:
          'Phase 9 studio-web (when Local is up) is projects, episodes, pack diff, identity, continuity, jobs, and sign-off. It does not invent those records in this pane. Pack builder stays in AIGC Flow.',
      }),
      jsxs('div', {
        className: 'flex flex-wrap items-center justify-center gap-2',
        children: [
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              persistSource('local')
            },
            children: 'Use Local',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              openExternal(GITHUB_URL)
            },
            children: 'GitHub',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              openExternal(DOCS_URL)
            },
            children: 'Studio docs',
          }),
          jsx(Button, {
            variant: 'ghost',
            size: 'sm',
            onClick: () => {
              haptic('tap')
              openExternal(PACK_BUILDER_REPO)
            },
            children: 'Pack builder repo',
          }),
        ],
      }),
      jsx('div', {
        className: 'text-[0.625rem] text-(--ui-text-quaternary)',
        children: apiLabel + ' · ' + API_ORIGIN + ' · ' + READYZ_URL,
      }),
    ],
  })
}

function StudioPane({ ctx }) {
  const source = useValue($source)
  const forceEmbed = useValue($forceEmbed)
  const localMode = source === 'local'
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: [ID, 'status'],
    queryFn: async () => ctx.rest('/status'),
    staleTime: 10 * 1000,
    retry: 1,
  })
  const status = asStatus(data)
  const webUrl = webTarget(status)
  const backendDown = Boolean(error && !data)
  const apiLabel = apiBadgeLabel(status, backendDown)
  const webDown = Boolean(localMode && status && status.web && status.web.reachable === false)
  const probeUnread = Boolean(
    localMode &&
      !webUrl &&
      !webDown &&
      (backendDown || !status || !status.web || status.web.reachable == null),
  )

  if (!localMode) {
    return jsxs('div', {
      className: 'flex h-full min-h-0 flex-col bg-(--ui-bg)',
      children: [
        jsx(Chrome, { source, embedUrl: '', badge: 'Local-first', apiLabel }),
        jsx(Separator, {}),
        jsx(LiveLocalFirst, { status, apiLabel }),
      ],
    })
  }

  let embedUrl = STUDIO_WEB_URL
  let badge = 'Local'
  if (forceEmbed) {
    embedUrl = STUDIO_WEB_URL
    badge = 'Local'
  } else if (webUrl) {
    embedUrl = webUrl
    badge = webUrl === STUDIO_PREVIEW_URL ? 'Preview' : 'Local'
  } else if (webDown) {
    embedUrl = ''
    badge = 'Local'
  } else {
    // Backend unread or status unknown — /status is optional. Do not hard-gate
    // on the Python probe. Local still iframes 5174 until the iframe fails.
    // API readiness is a badge and does not block studio-web.
    embedUrl = STUDIO_WEB_URL
    badge = 'Local'
  }

  if (localMode && isLoading && !forceEmbed && !backendDown) {
    return jsxs('div', {
      className: 'flex h-full min-h-0 flex-col bg-(--ui-bg)',
      children: [
        jsx(Chrome, { source, embedUrl: STUDIO_WEB_URL, badge: 'Local', apiLabel: 'API unread' }),
        jsx(Separator, {}),
        jsxs('div', {
          className: 'flex flex-1 flex-col items-center justify-center gap-3',
          children: [
            jsx(GlyphSpinner, { size: 24 }),
            jsx('div', {
              className: 'text-sm text-(--ui-text-secondary)',
              children: 'Checking local studio-web…',
            }),
          ],
        }),
      ],
    })
  }

  // Confirmed studio-web-down only. A failed ctx.rest('/status') must not block Local.
  // API down must not block Local either.
  if (localMode && !forceEmbed && webDown) {
    return jsxs('div', {
      className: 'flex h-full min-h-0 flex-col bg-(--ui-bg)',
      children: [
        jsx(Chrome, { source, embedUrl: '', badge: 'Local', apiLabel }),
        jsx(Separator, {}),
        jsx(LocalMissing, {
          apiLabel,
          onRetry: () => {
            $forceEmbed.set(false)
            $iframeError.set(false)
            void refetch()
          },
        }),
      ],
    })
  }

  return jsxs('div', {
    className: cn('flex h-full min-h-0 flex-col bg-(--ui-bg)'),
    children: [
      jsx(Chrome, { source, embedUrl, badge, apiLabel }),
      isFetching
        ? jsx('div', {
            className: 'px-4 text-[0.625rem] text-(--ui-text-quaternary)',
            children: 'updating local probe',
          })
        : probeUnread
          ? jsx('div', {
              className: 'px-4 text-[0.625rem] text-(--ui-text-quaternary)',
              children:
                'Local probe offline — embedding 5174 anyway. API badge is not a gate. Quit and relaunch Desktop if you want the :5174/:8000 badge.',
            })
          : null,
      jsx(Separator, {}),
      jsx(EmbedFrame, { url: embedUrl, title: 'AIGC Studio' }),
    ],
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

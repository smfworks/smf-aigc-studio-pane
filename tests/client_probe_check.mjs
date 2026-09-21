/**
 * Behavioral fixture for the Local reachability gate.
 * Extracts probe helpers from desktop/plugin.js so the test does not load
 * the Hermes plugin SDK. No network.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(import.meta.url)
const root = require('node:path').resolve(new URL('..', import.meta.url).pathname)
const src = readFileSync(root + '/desktop/plugin.js', 'utf8')
const start = src.indexOf('function probeOne')
const end = src.indexOf('function apiBadgeLabel')
assert.ok(start > 0 && end > start, 'probe helpers not found')
const chunk = src.slice(start, end)

const STUDIO_WEB_URL = 'http://127.0.0.1:5174/'
const STUDIO_PREVIEW_URL = 'http://127.0.0.1:4174/'
const PACK_URL = 'http://127.0.0.1:5173/'

function load(fetchImpl, probeMs) {
  const sandbox = {
    STUDIO_WEB_URL,
    STUDIO_PREVIEW_URL,
    CLIENT_PROBE_MS: probeMs,
    fetch: fetchImpl,
    AbortController,
    setTimeout,
    clearTimeout,
    Promise,
  }
  vm.runInNewContext(
    chunk +
      '\nthis.probeOne = probeOne\nthis.probeLocalStudio = probeLocalStudio\nthis.clientReachableFrom = clientReachableFrom\n',
    sandbox,
  )
  return sandbox
}

function opaque() {
  return { type: 'opaque', status: 0, ok: false }
}

function expectResult(result, reachable, url) {
  assert.equal(result.reachable, reachable)
  assert.equal(result.url, url)
}

const calls = []

function scripted(map, hang) {
  return (url, opts) => {
    calls.push({ url, opts })
    assert.equal(opts.method, 'GET')
    assert.equal(opts.mode, 'no-cors')
    assert.equal(opts.cache, 'no-store')
    if (hang && hang.has(url)) return new Promise(() => {})
    if (Object.prototype.hasOwnProperty.call(map, url)) {
      const value = map[url]
      if (value instanceof Error) return Promise.reject(value)
      return Promise.resolve(value)
    }
    return Promise.reject(new Error('connection refused'))
  }
}

async function main() {
  calls.length = 0
  let gate = load(scripted({ [STUDIO_WEB_URL]: opaque(), [STUDIO_PREVIEW_URL]: opaque() }), 2000)
  let result = await gate.probeLocalStudio()
  expectResult(result, true, STUDIO_WEB_URL)
  assert.equal(gate.clientReachableFrom(result), true)
  assert.ok(calls.some((c) => c.url === STUDIO_WEB_URL))

  calls.length = 0
  gate = load(
    scripted({
      [STUDIO_WEB_URL]: new Error('connection refused'),
      [STUDIO_PREVIEW_URL]: opaque(),
    }),
    2000,
  )
  result = await gate.probeLocalStudio()
  expectResult(result, true, STUDIO_PREVIEW_URL)
  assert.equal(gate.clientReachableFrom(result), true)

  calls.length = 0
  gate = load(
    scripted({
      [STUDIO_WEB_URL]: new Error('connection refused'),
      [STUDIO_PREVIEW_URL]: new Error('connection refused'),
    }),
    2000,
  )
  result = await gate.probeLocalStudio()
  expectResult(result, false, '')
  assert.equal(gate.clientReachableFrom(result), false)
  assert.equal(gate.clientReachableFrom(null), false)
  assert.equal(gate.clientReachableFrom({ reachable: true, url: PACK_URL }), false)
  assert.equal(gate.clientReachableFrom({ reachable: false, url: STUDIO_WEB_URL }), false)
  assert.equal(
    gate.clientReachableFrom({ reachable: true, url: 'https://aigc-production-flow.vercel.app/' }),
    false,
  )

  calls.length = 0
  gate = load(scripted({}, new Set([PACK_URL])), 50)
  assert.equal(await gate.probeOne(PACK_URL), false)
  assert.deepEqual(calls, [])

  calls.length = 0
  const started = Date.now()
  gate = load(scripted({}, new Set([STUDIO_WEB_URL, STUDIO_PREVIEW_URL])), 40)
  result = await gate.probeLocalStudio()
  const elapsed = Date.now() - started
  expectResult(result, false, '')
  assert.ok(elapsed < 1000, 'hanging probe should abort within the short timeout, took ' + elapsed)
  assert.ok(calls.every((c) => c.url === STUDIO_WEB_URL || c.url === STUDIO_PREVIEW_URL))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})

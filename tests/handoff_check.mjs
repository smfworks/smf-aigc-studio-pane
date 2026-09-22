/**
 * Honesty fixture for the Hermes brief strip.
 * Extracts pure helpers from desktop/plugin.js. No network. No invented film.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(import.meta.url)
const root = require('node:path').resolve(new URL('..', import.meta.url).pathname)
const src = readFileSync(root + '/desktop/plugin.js', 'utf8')
const start = src.indexOf('// HANDOFF_PURE_START')
const end = src.indexOf('// HANDOFF_PURE_END')
assert.ok(start > 0 && end > start, 'handoff helpers not found')
const chunk = src.slice(start, end)

const RUN_ID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
const RUN = '11111111-1111-4111-8111-111111111111'

const sandbox = { RUN_ID_RE, URL }
vm.runInNewContext(
  chunk +
    '\nthis.parseBriefLink = parseBriefLink\nthis.handoffBadge = handoffBadge\nthis.filmClaim = filmClaim\nthis.flagClaim = flagClaim\nthis.laneClaim = laneClaim\n',
  sandbox,
)

const link = 'hermes://aigc/brief?run=' + RUN
const parsed = sandbox.parseBriefLink(link)
assert.equal(parsed && parsed.run, RUN)
assert.equal(sandbox.parseBriefLink('hermes://aigc/brief?run=not-a-uuid'), null)
assert.equal(sandbox.parseBriefLink('https://example.com/brief?run=' + RUN), null)
assert.equal(sandbox.parseBriefLink(''), null)

assert.equal(sandbox.handoffBadge(null, true), 'API unread')
assert.equal(sandbox.handoffBadge(undefined, false), 'API unread')
assert.equal(
  sandbox.handoffBadge({ ok: true, state: 'empty', badge: 'No handoff yet' }, false),
  'No handoff yet',
)
assert.equal(
  sandbox.handoffBadge(
    { ok: true, state: 'brief', badge: 'Latest brief', agent_run_id: RUN },
    false,
  ),
  'Latest brief',
)
assert.equal(sandbox.handoffBadge({ ok: false, state: 'unread', badge: 'API unread' }, false), 'API unread')

const quiet = { produced_mp4: false, film_on_disk: false, called_comfy: false, hermes_ran: false }
assert.match(sandbox.filmClaim(quiet), /No finished film/)
assert.match(sandbox.filmClaim(quiet), /does not invent/)
assert.equal(sandbox.flagClaim(quiet).called_comfy, false)
assert.equal(sandbox.flagClaim(quiet).hermes_ran, false)
assert.match(sandbox.flagClaim(quiet).called_line, /false/)
assert.match(sandbox.flagClaim(quiet).hermes_line, /did not start Hermes/)

const flagged = { produced_mp4: true, film_on_disk: false, called_comfy: false, hermes_ran: false }
assert.match(sandbox.filmClaim(flagged), /not a finished film/)
assert.doesNotMatch(sandbox.filmClaim(flagged), /Finished film/)

const done = { produced_mp4: true, film_on_disk: true }
assert.match(sandbox.filmClaim(done), /Finished film/)

assert.match(sandbox.laneClaim({ still_label: 'stub', clip_label: 'stub (lane not live)' }), /stub/)
assert.match(sandbox.laneClaim({ still_live: false, clip_live: false }), /not live/)
assert.match(sandbox.laneClaim({ still_live: true, clip_label: 'live' }), /live/)

assert.equal(src.includes('.mp4'), false)
assert.equal(src.includes('/api/jobs'), false)
assert.equal(src.includes('generate-ok'), false)

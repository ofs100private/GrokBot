// Loader check: bundles src/data/classicLive.ts with esbuild (from vite) and
// asserts the flat + legacy layouts parse. Read-only; never writes JSON.
// Usage: node scripts/check-classic-live.mjs [path/to/classic-portfolio.json]
import { build } from 'esbuild'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const jsonPath = process.argv[2] ?? join(root, 'public/classic-portfolio.json')
const dir = mkdtempSync(join(tmpdir(), 'classic-live-'))
const out = join(dir, 'classicLive.mjs')
await build({ entryPoints: [join(root, 'src/data/classicLive.ts')], bundle: true, format: 'esm', platform: 'node', outfile: out, logLevel: 'silent' })
const { parseClassicLivePayload } = await import(pathToFileURL(out).href)
rmSync(dir, { recursive: true, force: true })

// 1) Real flat file
const raw = JSON.parse(readFileSync(jsonPath, 'utf8'))
const snap = parseClassicLivePayload(raw)
const cp = snap.clientPortfolio
assert.equal(snap.layout, 'flat')
assert.equal(snap.account.mirrorId, raw.mirrorId)
assert.equal(snap.account.username, raw.username)
assert.equal(cp.equity, raw.equity)
assert.equal(cp.availableCash, raw.cash)
assert.equal(cp.totalInvested, raw.invested)
assert.equal(cp.profitLoss, raw.openPnl)
assert.deepEqual(cp.positions.map((p) => p.symbol), raw.symbols)
raw.positions.forEach((rp, i) => {
  const p = cp.positions[i]
  assert.equal(p.symbol, rp.symbol)
  assert.equal(p.amount, rp.invested)
  assert.equal(p.unrealizedPnL.pnL, rp.pnl)
  assert.equal(p.units, rp.units)
  assert.equal(p.positionID, rp.positionId)
  assert.equal(p.instrumentID, rp.instrumentId)
})
assert.equal(cp.mirrors.length, 0)
console.log(JSON.stringify({
  file: jsonPath, layout: snap.layout, asOf: snap.asOf, account: snap.account,
  equity: cp.equity, cash: cp.availableCash, invested: cp.totalInvested,
  openPnl: cp.profitLoss, openPnlPctDerived: cp.profitLossPercent, metrics: snap.metrics,
  positions: cp.positions.map((p) => ({ symbol: p.symbol, invested: p.amount, pnl: p.unrealizedPnL.pnL, units: p.units, direction: p.direction })),
}, null, 2))

// 2) Minimal flat payload: optional fields missing → degrade, no throw
const minimal = parseClassicLivePayload({
  mirrorId: 11368142, username: 'X', asOf: '2026-10-12T00:00:00Z', equity: 100, cash: 40,
  positions: [{ symbol: 'AAA', value: 65, pnl: 5 }],
})
assert.equal(minimal.clientPortfolio.totalInvested, 60)
assert.equal(minimal.clientPortfolio.profitLoss, 5)
assert.equal(minimal.clientPortfolio.positions[0].amount, 60)
assert.equal(minimal.clientPortfolio.positions[0].direction, 'Long')
assert.ok(Number.isNaN(minimal.clientPortfolio.positions[0].units))

// 3) Wrong mirror still rejected
assert.throws(() => parseClassicLivePayload({ ...raw, mirrorId: 1 }), /mirrorId must be/)
// 4) Pending placeholder still pending
assert.throws(() => parseClassicLivePayload({ status: 'pending' }), (e) => e.code === 'pending')
// 5) Garbage still rejected with legacy message
assert.throws(() => parseClassicLivePayload({ foo: 1 }), /missing account/)

// 6) Legacy nested layout still accepted
const legacy = parseClassicLivePayload({
  asOf: '2026-09-01T00:00:00Z',
  account: { username: 'OfersClaw5-PRIYN', mirrorId: 11368142, mode: 'real' },
  summary: { equity: 1000, availableCash: 400, totalInvested: 550, profitLoss: 50, profitLossPercent: 9.09, credit: null },
  positions: [{ positionID: 1, instrumentID: 2, symbol: 'SPY', amount: 550, units: 1, openRate: 550, direction: 'Long', unrealizedPnL: { pnL: 50 } }],
  mirrors: [],
})
assert.equal(legacy.layout, 'legacy')
assert.equal(legacy.clientPortfolio.equity, 1000)
assert.equal(legacy.clientPortfolio.positions[0].unrealizedPnL.pnL, 50)

console.log('classicLive checks: ALL PASS')

import type {
  ClientPortfolio,
  Mirror,
  Position,
  PortfolioData,
} from './portfolio'

/** Parent UI / ledger A — Classic reporting truth. */
export const CLASSIC_MIRROR_ID = 11368142

export const CLASSIC_PORTFOLIO_URL = '/classic-portfolio.json'

export interface ClassicAccount {
  username: string
  mirrorId: number
  mode: string
  cid?: number
}

/** Which on-disk layout the snapshot was parsed from. */
export type ClassicSnapshotLayout = 'legacy' | 'flat'

/** Extra top-level metrics only present in the flat layout (all optional). */
export interface ClassicFlatMetrics {
  cashPct?: number
  deploymentPct?: number
  closedPnl?: number | null
  symbols?: string[]
  /** Market value of open positions, when the writer provides it. */
  investedMarketValue?: number
}

export interface ClassicLiveSnapshot {
  asOf: string
  account: ClassicAccount
  clientPortfolio: ClientPortfolio
  source?: unknown
  layout?: ClassicSnapshotLayout
  metrics?: ClassicFlatMetrics
}

export type ClassicLiveLoadState =
  | { status: 'loading' }
  | { status: 'pending'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; snapshot: ClassicLiveSnapshot }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requireNumber(obj: Record<string, unknown>, key: string, ctx: string): number {
  const v = obj[key]
  if (typeof v !== 'number' || Number.isNaN(v)) {
    throw new Error(`${ctx}: missing or invalid number "${key}"`)
  }
  return v
}

function normalizeDirection(raw: unknown): 'Long' | 'Short' {
  if (typeof raw !== 'string') {
    throw new Error('position/mirror: missing direction')
  }
  const lower = raw.toLowerCase()
  if (lower === 'long') return 'Long'
  if (lower === 'short') return 'Short'
  throw new Error(`position/mirror: invalid direction "${raw}"`)
}

function normalizeUnrealizedPnL(raw: unknown): { pnL: number } {
  if (!isRecord(raw) || typeof raw.pnL !== 'number') {
    throw new Error('position/mirror: missing unrealizedPnL.pnL')
  }
  return { pnL: raw.pnL }
}

function normalizePosition(raw: unknown, index: number): Position {
  if (!isRecord(raw)) {
    throw new Error(`positions[${index}]: expected object`)
  }
  return {
    positionID: requireNumber(raw, 'positionID', `positions[${index}]`),
    instrumentID: requireNumber(raw, 'instrumentID', `positions[${index}]`),
    instrumentName: String(raw.instrumentName ?? raw.symbol ?? ''),
    symbol: String(raw.symbol ?? ''),
    amount: requireNumber(raw, 'amount', `positions[${index}]`),
    units: requireNumber(raw, 'units', `positions[${index}]`),
    openRate: requireNumber(raw, 'openRate', `positions[${index}]`),
    direction: normalizeDirection(raw.direction),
    unrealizedPnL: normalizeUnrealizedPnL(raw.unrealizedPnL),
    avatarColor: typeof raw.avatarColor === 'string' ? raw.avatarColor : undefined,
  }
}

function normalizeMirror(raw: unknown, index: number): Mirror {
  if (!isRecord(raw)) {
    throw new Error(`mirrors[${index}]: expected object`)
  }
  return {
    mirrorID: requireNumber(raw, 'mirrorID', `mirrors[${index}]`),
    parentPositionID: requireNumber(raw, 'parentPositionID', `mirrors[${index}]`),
    instrumentName: String(raw.instrumentName ?? raw.symbol ?? ''),
    symbol: String(raw.symbol ?? ''),
    amount: requireNumber(raw, 'amount', `mirrors[${index}]`),
    units: requireNumber(raw, 'units', `mirrors[${index}]`),
    openRate: requireNumber(raw, 'openRate', `mirrors[${index}]`),
    direction: normalizeDirection(raw.direction),
    unrealizedPnL: normalizeUnrealizedPnL(raw.unrealizedPnL),
    copiedFrom: String(raw.copiedFrom ?? ''),
    avatarColor: typeof raw.avatarColor === 'string' ? raw.avatarColor : undefined,
  }
}

/**
 * Map Trader_Classic snapshot (`summary` + top-level positions/mirrors)
 * or already-normalized `{ clientPortfolio }` into UI ClientPortfolio.
 */
function mapToClientPortfolio(raw: Record<string, unknown>): ClientPortfolio {
  const summarySource = isRecord(raw.clientPortfolio)
    ? raw.clientPortfolio
    : isRecord(raw.summary)
      ? raw.summary
      : null

  if (!summarySource) {
    throw new Error('classic snapshot: missing clientPortfolio / summary')
  }

  const positionsRaw =
    isRecord(raw.clientPortfolio) && Array.isArray(raw.clientPortfolio.positions)
      ? (raw.clientPortfolio.positions as unknown[])
      : Array.isArray(raw.positions)
        ? raw.positions
        : null

  const mirrorsRaw =
    isRecord(raw.clientPortfolio) && Array.isArray(raw.clientPortfolio.mirrors)
      ? (raw.clientPortfolio.mirrors as unknown[])
      : Array.isArray(raw.mirrors)
        ? raw.mirrors
        : null

  if (!positionsRaw) {
    throw new Error('classic snapshot: missing positions[]')
  }
  if (!mirrorsRaw) {
    throw new Error('classic snapshot: missing mirrors[]')
  }

  const orders =
    isRecord(raw.clientPortfolio) && Array.isArray(raw.clientPortfolio.orders)
      ? (raw.clientPortfolio.orders as unknown[])
      : Array.isArray(raw.orders)
        ? raw.orders
        : []

  return {
    equity: requireNumber(summarySource, 'equity', 'summary'),
    availableCash: requireNumber(summarySource, 'availableCash', 'summary'),
    totalInvested: requireNumber(summarySource, 'totalInvested', 'summary'),
    profitLoss: requireNumber(summarySource, 'profitLoss', 'summary'),
    profitLossPercent: requireNumber(summarySource, 'profitLossPercent', 'summary'),
    credit:
      summarySource.credit === null || summarySource.credit === undefined
        ? (summarySource.credit ?? null)
        : requireNumber(summarySource, 'credit', 'summary'),
    positions: positionsRaw.map(normalizePosition),
    mirrors: mirrorsRaw.map(normalizeMirror),
    orders,
  }
}

// ---------------------------------------------------------------------------
// Flat layout (daily writers since 2026-09-19):
//   { mirrorId, username, asOf, equity, cash, invested, openPnl, cashPct,
//     deploymentPct, symbols[], positions[{ symbol, instrumentId, invested,
//     units, openRate, positionId, value, pnl, direction, ... }],
//     pendingOrders[], summary{ availableCash, invested, totalValue, ... } }
// No `account` object, no `mirrors[]`, positions use camelCase ids + `pnl`.
// ---------------------------------------------------------------------------

function optNumber(...values: unknown[]): number | undefined {
  for (const v of values) {
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return undefined
}

function optString(...values: unknown[]): string | undefined {
  for (const v of values) {
    if (typeof v === 'string' && v.trim()) return v
  }
  return undefined
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

function sumField(items: Array<Record<string, unknown>>, pick: (r: Record<string, unknown>) => number | undefined): number | undefined {
  let total = 0
  for (const it of items) {
    const v = pick(it)
    if (v === undefined) return undefined
    total += v
  }
  return round2(total)
}

function isFlatLayout(raw: Record<string, unknown>): boolean {
  if (isRecord(raw.account) || isRecord(raw.clientPortfolio)) return false
  if (!Array.isArray(raw.positions)) return false
  const summary = isRecord(raw.summary) ? raw.summary : {}
  return (
    optNumber(raw.equity, raw.totalValue, summary.totalValue, summary.equity) !== undefined
  )
}

function flatPositionInvested(r: Record<string, unknown>): number | undefined {
  const direct = optNumber(r.invested, r.amount)
  if (direct !== undefined) return direct
  const value = optNumber(r.value)
  const pnl = optNumber(r.pnl, isRecord(r.unrealizedPnL) ? r.unrealizedPnL.pnL : undefined)
  return value !== undefined && pnl !== undefined ? round2(value - pnl) : undefined
}

function flatPositionPnl(r: Record<string, unknown>): number | undefined {
  const direct = optNumber(r.pnl, isRecord(r.unrealizedPnL) ? r.unrealizedPnL.pnL : undefined)
  if (direct !== undefined) return direct
  const value = optNumber(r.value)
  const invested = optNumber(r.invested, r.amount)
  return value !== undefined && invested !== undefined ? round2(value - invested) : undefined
}

function normalizeFlatPosition(raw: unknown, index: number): Position {
  const ctx = `positions[${index}]`
  if (!isRecord(raw)) {
    throw new Error(`${ctx}: expected object`)
  }
  const amount = flatPositionInvested(raw)
  if (amount === undefined) {
    throw new Error(`${ctx}: missing invested (or value + pnl)`)
  }
  const pnl = flatPositionPnl(raw)
  if (pnl === undefined) {
    throw new Error(`${ctx}: missing pnl (or value + invested)`)
  }
  const symbol = optString(raw.symbol) ?? ''
  return {
    // Negative id = synthetic React key only (writer omitted positionId).
    positionID: optNumber(raw.positionId, raw.positionID) ?? -(index + 1),
    // 0 = unknown instrument (not displayed by the dashboard).
    instrumentID: optNumber(raw.instrumentId, raw.instrumentID) ?? 0,
    instrumentName: optString(raw.instrumentName, raw.name, raw.symbol) ?? '',
    symbol,
    amount,
    // NaN = unknown; UI renders "—" instead of inventing a value.
    units: optNumber(raw.units) ?? Number.NaN,
    openRate: optNumber(raw.openRate) ?? Number.NaN,
    // Flat writers only hold non-leveraged buys; absent direction ⇒ Long.
    direction: raw.direction === undefined || raw.direction === null ? 'Long' : normalizeDirection(raw.direction),
    unrealizedPnL: { pnL: pnl },
    avatarColor: typeof raw.avatarColor === 'string' ? raw.avatarColor : undefined,
  }
}

function mapFlatToClientPortfolio(raw: Record<string, unknown>): ClientPortfolio {
  const summary = isRecord(raw.summary) ? raw.summary : {}
  const positionsRaw = (Array.isArray(raw.positions) ? raw.positions : []) as unknown[]
  const positions = positionsRaw.map(normalizeFlatPosition)
  const posRecords = positionsRaw.filter(isRecord)

  const equity = optNumber(raw.equity, raw.totalValue, summary.totalValue, summary.equity)
  if (equity === undefined) {
    throw new Error('classic snapshot (flat): missing equity')
  }
  const availableCash = optNumber(raw.cash, raw.availableCash, summary.availableCash, summary.cash)
  if (availableCash === undefined) {
    throw new Error('classic snapshot (flat): missing cash')
  }
  const totalInvested =
    optNumber(raw.invested, raw.totalInvested, summary.invested, summary.totalInvested) ??
    sumField(posRecords, flatPositionInvested) ??
    0
  const profitLoss =
    optNumber(raw.openPnl, raw.unrealizedPnl, raw.profitLoss, summary.unrealizedPnl, summary.profitLoss) ??
    sumField(posRecords, flatPositionPnl) ??
    0
  const profitLossPercent =
    optNumber(raw.openPnlPct, raw.profitLossPercent, summary.profitLossPercent) ??
    (totalInvested > 0 ? round2((profitLoss / totalInvested) * 100) : 0)

  const orders = Array.isArray(raw.orders)
    ? (raw.orders as unknown[])
    : Array.isArray(raw.pendingOrders)
      ? (raw.pendingOrders as unknown[])
      : []

  return {
    equity,
    availableCash,
    totalInvested,
    profitLoss,
    profitLossPercent,
    credit: optNumber(raw.credit, summary.credit) ?? null,
    positions,
    mirrors: Array.isArray(raw.mirrors) ? (raw.mirrors as unknown[]).map(normalizeMirror) : [],
    orders,
  }
}

function parseFlatClassicPayload(raw: Record<string, unknown>): ClassicLiveSnapshot {
  const mirrorId = raw.mirrorId
  if (typeof mirrorId !== 'number' || mirrorId !== CLASSIC_MIRROR_ID) {
    throw new Error(
      `classic snapshot: mirrorId must be ${CLASSIC_MIRROR_ID} (got ${String(mirrorId)})`,
    )
  }
  const username = optString(raw.username, raw.portfolio, raw.agentPortfolio)
  if (!username) {
    throw new Error('classic snapshot (flat): missing username')
  }
  const asOf = raw.asOf
  if (typeof asOf !== 'string' || !asOf.trim()) {
    throw new Error('classic snapshot: missing asOf')
  }

  const clientPortfolio = mapFlatToClientPortfolio(raw)

  const metrics: ClassicFlatMetrics = {}
  const cashPct = optNumber(raw.cashPct)
  if (cashPct !== undefined) metrics.cashPct = cashPct
  const deploymentPct = optNumber(raw.deploymentPct)
  if (deploymentPct !== undefined) metrics.deploymentPct = deploymentPct
  if (raw.closedPnl === null || typeof raw.closedPnl === 'number') {
    metrics.closedPnl = raw.closedPnl as number | null
  }
  const sleeves = isRecord(raw.sleeves) ? raw.sleeves : {}
  const summaryRec = isRecord(raw.summary) ? raw.summary : {}
  const investedMV = optNumber(
    raw.investedMarketValue,
    raw.investedMV,
    summaryRec.investedMarketValue,
    summaryRec.investedMV,
    sleeves.investedMV,
  )
  if (investedMV !== undefined) metrics.investedMarketValue = investedMV
  if (Array.isArray(raw.symbols)) {
    metrics.symbols = (raw.symbols as unknown[]).filter((s): s is string => typeof s === 'string')
  }

  return {
    asOf,
    account: {
      username,
      mirrorId,
      mode: typeof raw.mode === 'string' ? raw.mode : 'real',
      cid: typeof raw.cid === 'number' ? raw.cid : undefined,
    },
    clientPortfolio,
    source: raw.source,
    layout: 'flat',
    metrics,
  }
}

/**
 * Validate and normalize a Classic live JSON payload.
 * Accepts the legacy nested layout (`account` + `summary`/`clientPortfolio` +
 * positions/mirrors) and the flat layout written since 2026-09-19.
 * Rejects pending placeholders and wrong mirrorId. Never invents numbers.
 */
export function parseClassicLivePayload(raw: unknown): ClassicLiveSnapshot {
  if (!isRecord(raw)) {
    throw new Error('classic snapshot: expected JSON object')
  }

  if (raw.status === 'pending') {
    const message =
      typeof raw.message === 'string'
        ? raw.message
        : 'Awaiting Trader_Classic live snapshot'
    const err = new Error(message) as Error & { code: string }
    err.code = 'pending'
    throw err
  }

  if (!isRecord(raw.account)) {
    if (isFlatLayout(raw)) {
      return parseFlatClassicPayload(raw)
    }
    throw new Error('classic snapshot: missing account')
  }

  const mirrorId = raw.account.mirrorId
  if (typeof mirrorId !== 'number' || mirrorId !== CLASSIC_MIRROR_ID) {
    throw new Error(
      `classic snapshot: mirrorId must be ${CLASSIC_MIRROR_ID} (got ${String(mirrorId)})`,
    )
  }

  const username = raw.account.username
  if (typeof username !== 'string' || !username.trim()) {
    throw new Error('classic snapshot: missing account.username')
  }

  const asOf = raw.asOf
  if (typeof asOf !== 'string' || !asOf.trim()) {
    throw new Error('classic snapshot: missing asOf')
  }

  const clientPortfolio = mapToClientPortfolio(raw)

  return {
    asOf,
    account: {
      username,
      mirrorId,
      mode: typeof raw.account.mode === 'string' ? raw.account.mode : 'real',
      cid: typeof raw.account.cid === 'number' ? raw.account.cid : undefined,
    },
    clientPortfolio,
    source: raw.source,
    layout: 'legacy',
  }
}

export function toPortfolioData(snapshot: ClassicLiveSnapshot): PortfolioData {
  return { clientPortfolio: snapshot.clientPortfolio }
}

/**
 * Fetch GET /classic-portfolio.json, validate ledger A (mirror 11368142),
 * map summary → clientPortfolio. On failure returns pending/error — never invents data.
 */
export async function fetchClassicLive(
  url: string = CLASSIC_PORTFOLIO_URL,
): Promise<ClassicLiveLoadState> {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      return {
        status: 'error',
        message: `Failed to load Classic snapshot (${res.status})`,
      }
    }
    const json: unknown = await res.json()
    try {
      const snapshot = parseClassicLivePayload(json)
      return { status: 'ready', snapshot }
    } catch (e) {
      const err = e as Error & { code?: string }
      if (err.code === 'pending') {
        return { status: 'pending', message: err.message }
      }
      return {
        status: 'error',
        message: err.message || 'Invalid Classic snapshot',
      }
    }
  } catch (e) {
    return {
      status: 'error',
      message: e instanceof Error ? e.message : 'Network error loading Classic snapshot',
    }
  }
}

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

export interface ClassicLiveSnapshot {
  asOf: string
  account: ClassicAccount
  clientPortfolio: ClientPortfolio
  source?: unknown
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

/**
 * Validate and normalize a Classic live JSON payload.
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

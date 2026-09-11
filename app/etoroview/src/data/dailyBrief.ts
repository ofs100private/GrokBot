import { CLASSIC_MIRROR_ID } from './classicLive'

export const DAILY_BRIEF_URL = '/daily-brief.json'

export type DailyBriefSlot = 'morning_0530' | 'afternoon_1530' | 'weekend_adhoc'
export type CommodityStance = 'yes' | 'no' | 'wait'
export type SignalSide = 'buy' | 'sell'

export interface FearAndGreed {
  score: number
  rating: string
  previousClose: number
  previous1Week: number
  previous1Month: number
  previous1Year: number
  timestamp: string
}

export interface FearGreedComponent {
  id: string
  label: string
  score: number
  rating: string
}

export interface CommodityQuote {
  symbol: string
  last: number
  dayPct: number
  stance: CommodityStance
  related?: string
}

export interface CommoditiesBlock {
  oil: CommodityQuote
  gold: CommodityQuote
  silver: CommodityQuote
}

export interface SignalCard {
  symbol: string
  side: SignalSide
  open: number | null
  openNote?: string
  prevClose: number
  last: number
  dayPct: number
  rationale: string
}

export interface PortfolioRecommendation {
  buy: string[]
  sell: string[]
  hold: string[]
  diversificationNote: string
}

export interface PortfolioCardPosition {
  symbol: string
  pctOfEquity?: number | null
  value?: number | null
  uPnl?: number | null
}

export interface PortfolioCard {
  positionCount?: number | null
  cashPct?: number | null
  deploymentPct?: number | null
  equity?: number | null
  cash?: number | null
  invested?: number | null
  openPnl?: number | null
  closedPnl?: number | null
  positions?: PortfolioCardPosition[]
}

export interface DailyBriefPortfolio {
  key: string
  name: string
  mirrorId: number | string
  agentPortfolioId?: string | null
  card?: PortfolioCard
  recommendation: PortfolioRecommendation
}

export interface DailyBriefPayload {
  schemaVersion: string
  payloadKind?: string
  slot: DailyBriefSlot
  slotBadge?: string
  asOf: string
  timezone: string
  weekendMode?: boolean
  noNewOpens?: boolean
  fearAndGreed: FearAndGreed
  components: FearGreedComponent[]
  commodities: CommoditiesBlock
  trump?: {
    timestamp?: string | null
    quote?: string | null
    url?: string | null
    marketRelevance?: string | null
    source?: string | null
  }
  analystScore?: {
    bullets?: string[]
    nothingSpecial?: boolean
  }
  dailySignals: {
    buys: SignalCard[]
    sells: SignalCard[]
  }
  cryptoImpact?: {
    btc?: { last?: number; dayPct?: number }
    eth?: { last?: number; dayPct?: number }
    stance?: string
    notes?: string
  }
  expectedDailyImpact?: string[]
  portfolios: DailyBriefPortfolio[]
  source: string
  message?: string
  status?: string
}

export type DailyBriefLoadState =
  | { status: 'loading' }
  | { status: 'pending'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; payload: DailyBriefPayload }

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

function requireString(obj: Record<string, unknown>, key: string, ctx: string): string {
  const v = obj[key]
  if (typeof v !== 'string' || !v.trim()) {
    throw new Error(`${ctx}: missing or invalid string "${key}"`)
  }
  return v
}

function parseFearAndGreed(raw: unknown): FearAndGreed {
  if (!isRecord(raw)) throw new Error('fearAndGreed: expected object')
  return {
    score: requireNumber(raw, 'score', 'fearAndGreed'),
    rating: requireString(raw, 'rating', 'fearAndGreed'),
    previousClose: requireNumber(raw, 'previousClose', 'fearAndGreed'),
    previous1Week: requireNumber(raw, 'previous1Week', 'fearAndGreed'),
    previous1Month: requireNumber(raw, 'previous1Month', 'fearAndGreed'),
    previous1Year: requireNumber(raw, 'previous1Year', 'fearAndGreed'),
    timestamp: requireString(raw, 'timestamp', 'fearAndGreed'),
  }
}

function parseComponent(raw: unknown, index: number): FearGreedComponent {
  if (!isRecord(raw)) throw new Error(`components[${index}]: expected object`)
  return {
    id: requireString(raw, 'id', `components[${index}]`),
    label: requireString(raw, 'label', `components[${index}]`),
    score: requireNumber(raw, 'score', `components[${index}]`),
    rating: requireString(raw, 'rating', `components[${index}]`),
  }
}

function parseCommodity(raw: unknown, key: string): CommodityQuote {
  if (!isRecord(raw)) throw new Error(`commodities.${key}: expected object`)
  const stance = requireString(raw, 'stance', `commodities.${key}`)
  if (stance !== 'yes' && stance !== 'no' && stance !== 'wait') {
    throw new Error(`commodities.${key}: invalid stance "${stance}"`)
  }
  return {
    symbol: requireString(raw, 'symbol', `commodities.${key}`),
    last: requireNumber(raw, 'last', `commodities.${key}`),
    dayPct: requireNumber(raw, 'dayPct', `commodities.${key}`),
    stance,
    related: typeof raw.related === 'string' ? raw.related : undefined,
  }
}

function parseSignal(raw: unknown, index: number, sideHint: string): SignalCard {
  if (!isRecord(raw)) throw new Error(`dailySignals.${sideHint}[${index}]: expected object`)
  const side = requireString(raw, 'side', `dailySignals.${sideHint}[${index}]`)
  if (side !== 'buy' && side !== 'sell') {
    throw new Error(`dailySignals.${sideHint}[${index}]: invalid side`)
  }
  const openRaw = raw.open
  let open: number | null
  if (openRaw === null || openRaw === undefined) {
    open = null
  } else if (typeof openRaw === 'number' && !Number.isNaN(openRaw)) {
    open = openRaw
  } else {
    throw new Error(`dailySignals.${sideHint}[${index}]: missing or invalid number "open"`)
  }
  return {
    symbol: requireString(raw, 'symbol', `dailySignals.${sideHint}[${index}]`),
    side,
    open,
    openNote: typeof raw.openNote === 'string' ? raw.openNote : undefined,
    prevClose: requireNumber(raw, 'prevClose', `dailySignals.${sideHint}[${index}]`),
    last: requireNumber(raw, 'last', `dailySignals.${sideHint}[${index}]`),
    dayPct: requireNumber(raw, 'dayPct', `dailySignals.${sideHint}[${index}]`),
    rationale: requireString(raw, 'rationale', `dailySignals.${sideHint}[${index}]`),
  }
}

function parseRecommendation(raw: unknown, ctx: string): PortfolioRecommendation {
  if (!isRecord(raw)) throw new Error(`${ctx}: recommendation expected object`)
  const buy = Array.isArray(raw.buy) ? raw.buy.map(String) : []
  const sell = Array.isArray(raw.sell) ? raw.sell.map(String) : []
  const hold = Array.isArray(raw.hold) ? raw.hold.map(String) : []
  const diversificationNote =
    typeof raw.diversificationNote === 'string' ? raw.diversificationNote : ''
  return { buy, sell, hold, diversificationNote }
}

function parsePortfolioCard(raw: unknown): PortfolioCard | undefined {
  if (!isRecord(raw)) return undefined
  const numOrNull = (k: string): number | null | undefined => {
    const v = raw[k]
    if (v === null) return null
    if (typeof v === 'number' && !Number.isNaN(v)) return v
    return undefined
  }
  let positions: PortfolioCardPosition[] | undefined
  if (Array.isArray(raw.positions)) {
    positions = raw.positions.filter(isRecord).map((p) => ({
      symbol: String(p.symbol ?? ''),
      pctOfEquity: typeof p.pctOfEquity === 'number' ? p.pctOfEquity : p.pctOfEquity === null ? null : undefined,
      value: typeof p.value === 'number' ? p.value : p.value === null ? null : undefined,
      uPnl: typeof p.uPnl === 'number' ? p.uPnl : p.uPnl === null ? null : undefined,
    }))
  }
  return {
    positionCount: numOrNull('positionCount'),
    cashPct: numOrNull('cashPct'),
    deploymentPct: numOrNull('deploymentPct'),
    equity: numOrNull('equity'),
    cash: numOrNull('cash'),
    invested: numOrNull('invested'),
    openPnl: numOrNull('openPnl'),
    closedPnl: numOrNull('closedPnl'),
    positions,
  }
}

function parsePortfolio(raw: unknown, index: number): DailyBriefPortfolio {
  if (!isRecord(raw)) throw new Error(`portfolios[${index}]: expected object`)
  const mirrorId = raw.mirrorId
  if (typeof mirrorId !== 'number' && typeof mirrorId !== 'string') {
    throw new Error(`portfolios[${index}]: missing mirrorId`)
  }
  return {
    key: requireString(raw, 'key', `portfolios[${index}]`),
    name: requireString(raw, 'name', `portfolios[${index}]`),
    mirrorId,
    agentPortfolioId:
      typeof raw.agentPortfolioId === 'string' || raw.agentPortfolioId === null
        ? (raw.agentPortfolioId as string | null)
        : undefined,
    card: raw.card !== undefined ? parsePortfolioCard(raw.card) : undefined,
    recommendation: parseRecommendation(raw.recommendation, `portfolios[${index}]`),
  }
}

/**
 * Validate live daily_brief v1.0 payload. Never invents Fear & Greed or dollars.
 * Pending / incomplete payloads throw with code pending.
 */
export function parseDailyBriefPayload(raw: unknown): DailyBriefPayload {
  if (!isRecord(raw)) {
    throw new Error('daily brief: expected JSON object')
  }

  if (raw.status === 'pending' || raw.payloadKind === 'pending') {
    const message =
      typeof raw.message === 'string'
        ? raw.message
        : 'Awaiting daily_brief live payload'
    const err = new Error(message) as Error & { code: string }
    err.code = 'pending'
    throw err
  }

  const schemaVersion = raw.schemaVersion
  if (schemaVersion !== '1.0' && schemaVersion !== 1) {
    throw new Error(`daily brief: unsupported schemaVersion ${String(schemaVersion)}`)
  }

  if (!isRecord(raw.fearAndGreed) || typeof raw.fearAndGreed.score !== 'number') {
    const err = new Error('Awaiting fearAndGreed live scores') as Error & { code: string }
    err.code = 'pending'
    throw err
  }

  const slot = requireString(raw, 'slot', 'daily brief') as DailyBriefSlot
  if (slot !== 'morning_0530' && slot !== 'afternoon_1530' && slot !== 'weekend_adhoc') {
    throw new Error(`daily brief: invalid slot "${slot}"`)
  }

  if (!isRecord(raw.commodities)) {
    throw new Error('daily brief: missing commodities')
  }
  if (!isRecord(raw.dailySignals)) {
    throw new Error('daily brief: missing dailySignals')
  }
  if (!Array.isArray(raw.components)) {
    throw new Error('daily brief: missing components[]')
  }
  if (!Array.isArray(raw.portfolios) || raw.portfolios.length < 1) {
    throw new Error('daily brief: missing portfolios[]')
  }

  const buysRaw = Array.isArray(raw.dailySignals.buys) ? raw.dailySignals.buys : []
  const sellsRaw = Array.isArray(raw.dailySignals.sells) ? raw.dailySignals.sells : []

  return {
    schemaVersion: '1.0',
    payloadKind: typeof raw.payloadKind === 'string' ? raw.payloadKind : undefined,
    slot,
    slotBadge: typeof raw.slotBadge === 'string' ? raw.slotBadge : undefined,
    asOf: requireString(raw, 'asOf', 'daily brief'),
    timezone: typeof raw.timezone === 'string' ? raw.timezone : 'Asia/Jerusalem',
    weekendMode: typeof raw.weekendMode === 'boolean' ? raw.weekendMode : undefined,
    noNewOpens: typeof raw.noNewOpens === 'boolean' ? raw.noNewOpens : undefined,
    fearAndGreed: parseFearAndGreed(raw.fearAndGreed),
    components: raw.components.map(parseComponent),
    commodities: {
      oil: parseCommodity(raw.commodities.oil, 'oil'),
      gold: parseCommodity(raw.commodities.gold, 'gold'),
      silver: parseCommodity(raw.commodities.silver, 'silver'),
    },
    trump: isRecord(raw.trump) ? (raw.trump as DailyBriefPayload['trump']) : undefined,
    analystScore: isRecord(raw.analystScore)
      ? {
          bullets: Array.isArray(raw.analystScore.bullets)
            ? raw.analystScore.bullets.map(String)
            : undefined,
          nothingSpecial:
            typeof raw.analystScore.nothingSpecial === 'boolean'
              ? raw.analystScore.nothingSpecial
              : undefined,
        }
      : undefined,
    dailySignals: {
      buys: buysRaw.map((s, i) => parseSignal(s, i, 'buys')),
      sells: sellsRaw.map((s, i) => parseSignal(s, i, 'sells')),
    },
    cryptoImpact: isRecord(raw.cryptoImpact)
      ? (raw.cryptoImpact as DailyBriefPayload['cryptoImpact'])
      : undefined,
    expectedDailyImpact: Array.isArray(raw.expectedDailyImpact)
      ? raw.expectedDailyImpact.map(String)
      : undefined,
    portfolios: raw.portfolios.map(parsePortfolio),
    source: requireString(raw, 'source', 'daily brief'),
    message: typeof raw.message === 'string' ? raw.message : undefined,
  }
}

export function findClassicPortfolio(
  payload: DailyBriefPayload,
): DailyBriefPortfolio | undefined {
  return (
    payload.portfolios.find(
      (p) =>
        p.key === 'Classic' ||
        Number(p.mirrorId) === CLASSIC_MIRROR_ID ||
        String(p.mirrorId) === String(CLASSIC_MIRROR_ID),
    ) ?? payload.portfolios[0]
  )
}

export async function fetchDailyBrief(
  url: string = DAILY_BRIEF_URL,
): Promise<DailyBriefLoadState> {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      return {
        status: 'error',
        message: `Failed to load daily brief (${res.status})`,
      }
    }
    const json: unknown = await res.json()
    try {
      const payload = parseDailyBriefPayload(json)
      return { status: 'ready', payload }
    } catch (e) {
      const err = e as Error & { code?: string }
      if (err.code === 'pending') {
        return { status: 'pending', message: err.message }
      }
      return {
        status: 'error',
        message: err.message || 'Invalid daily brief payload',
      }
    }
  } catch (e) {
    return {
      status: 'error',
      message: e instanceof Error ? e.message : 'Network error loading daily brief',
    }
  }
}

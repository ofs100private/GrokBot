export const TRADING_QA_URL = '/trading-qa.json'

export type QaVerdict = 'PASS' | 'FAIL' | string

export interface TradingQaActionDetails {
  amount_usd?: number | null
  leverage?: number | null
  size?: number | null
  lev?: number | null
  setup?: string | null
  asset_class?: string | null
  rs_rating?: number | null
  rvol?: number | null
  stop_loss?: number | null
  qa_pack_verdict?: string | null
  [key: string]: unknown
}

export interface TradingQaAction {
  action: string
  symbol?: string | null
  portfolio?: string | null
  rationale?: string | null
  qa_verdict?: QaVerdict | null
  qa_reasons?: string[]
  deviation_code?: string | null
  deviation?: boolean
  details?: TradingQaActionDetails | null
  ts_il?: string | null
  ts_utc?: string | null
  run_id?: string | null
  event?: string | null
  script?: string | null
}

export interface TradingQaLesson {
  tag: string
  text: string
  action?: string | null
  symbol?: string | null
  rationale?: string | null
}

export interface TradingQaDayCounts {
  audit_rows?: number
  actions?: number
  qa_pass_actions?: number
  qa_fail_actions?: number
  deviations?: number
  errors?: number
  keep?: number
  avoid?: number
  [key: string]: number | undefined
}

export interface TradingQaDay {
  day?: string
  asOf?: string
  portfolio?: string
  strategy_aligned?: TradingQaLesson[]
  deviations_clear?: TradingQaLesson[]
  top_deviation_codes?: string[]
  lessons?: TradingQaLesson[]
  counts?: TradingQaDayCounts
  qa_bot?: string
  schemaVersion?: string
}

export interface TradingQaClassicPosition {
  symbol?: string | null
  side?: string | null
  sizeUsd?: number | null
  leverage?: number | null
  status?: string | null
  [key: string]: unknown
}

export interface TradingQaClassicCase {
  caseId: string
  asOf?: string
  portfolio?: string
  caseScore?: number | null
  symbol?: string | null
  side?: string | null
  lessons?: TradingQaLesson[]
  position?: TradingQaClassicPosition | null
  status?: string | null
}

export interface TradingQaPortfolio {
  key: string
  name: string
  mirrorId?: number | string | null
  agentPortfolioId?: string | null
  truthNote?: string | null
  actions: TradingQaAction[]
  days: TradingQaDay[]
  classicCases?: TradingQaClassicCase[]
}

export interface TradingQaPayload {
  schemaVersion: string
  asOf?: string
  portfolios: TradingQaPortfolio[]
}

export type TradingQaLoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; payload: TradingQaPayload }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && !Number.isNaN(value) ? value : null
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((v): v is string => typeof v === 'string')
}

function parseLesson(raw: unknown): TradingQaLesson | null {
  if (!isRecord(raw)) return null
  const tag = asString(raw.tag) ?? 'NOTE'
  const text =
    asString(raw.text) ??
    asString(raw.rationale) ??
    asString(raw.message) ??
    ''
  if (!text) return null
  return {
    tag,
    text,
    action: asString(raw.action),
    symbol: asString(raw.symbol),
    rationale: asString(raw.rationale),
  }
}

function parseLessons(raw: unknown): TradingQaLesson[] {
  if (!Array.isArray(raw)) return []
  return raw.map(parseLesson).filter((l): l is TradingQaLesson => l !== null)
}

function parseDetails(raw: unknown): TradingQaActionDetails | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    amount_usd: asNumber(raw.amount_usd),
    leverage: asNumber(raw.leverage),
    size: asNumber(raw.size),
    lev: asNumber(raw.lev),
    setup: asString(raw.setup),
    asset_class: asString(raw.asset_class),
    rs_rating: asNumber(raw.rs_rating),
    rvol: asNumber(raw.rvol),
    stop_loss: asNumber(raw.stop_loss),
    qa_pack_verdict: asString(raw.qa_pack_verdict),
  }
}

function parseAction(raw: unknown, index: number): TradingQaAction | null {
  if (!isRecord(raw)) return null
  const action = asString(raw.action)
  if (!action) {
    // Skip malformed rows rather than failing the whole feed
    console.warn(`trading-qa actions[${index}]: missing action`)
    return null
  }
  return {
    action,
    symbol: asString(raw.symbol),
    portfolio: asString(raw.portfolio),
    rationale: asString(raw.rationale),
    qa_verdict: asString(raw.qa_verdict),
    qa_reasons: asStringArray(raw.qa_reasons),
    deviation_code: asString(raw.deviation_code),
    deviation: typeof raw.deviation === 'boolean' ? raw.deviation : undefined,
    details: parseDetails(raw.details),
    ts_il: asString(raw.ts_il),
    ts_utc: asString(raw.ts_utc),
    run_id: asString(raw.run_id),
    event: asString(raw.event),
    script: asString(raw.script),
  }
}

function parseDayCounts(raw: unknown): TradingQaDayCounts | undefined {
  if (!isRecord(raw)) return undefined
  const counts: TradingQaDayCounts = {}
  for (const [k, v] of Object.entries(raw)) {
    if (typeof v === 'number' && !Number.isNaN(v)) counts[k] = v
  }
  return counts
}

function parseDay(raw: unknown): TradingQaDay | null {
  if (!isRecord(raw)) return null
  return {
    day: asString(raw.day) ?? undefined,
    asOf: asString(raw.asOf) ?? undefined,
    portfolio: asString(raw.portfolio) ?? undefined,
    strategy_aligned: parseLessons(raw.strategy_aligned),
    deviations_clear: parseLessons(raw.deviations_clear),
    top_deviation_codes: asStringArray(raw.top_deviation_codes),
    lessons: parseLessons(raw.lessons),
    counts: parseDayCounts(raw.counts),
    qa_bot: asString(raw.qa_bot) ?? undefined,
    schemaVersion: asString(raw.schemaVersion) ?? undefined,
  }
}

function parseClassicCase(raw: unknown): TradingQaClassicCase | null {
  if (!isRecord(raw)) return null
  const caseId = asString(raw.caseId)
  if (!caseId) return null // rollup / non-case entries

  let position: TradingQaClassicPosition | null = null
  if (isRecord(raw.position)) {
    position = {
      ...raw.position,
      symbol: asString(raw.position.symbol),
      side: asString(raw.position.side),
      sizeUsd: asNumber(raw.position.sizeUsd),
      leverage: asNumber(raw.position.leverage),
      status: asString(raw.position.status),
    }
  }

  return {
    caseId,
    asOf: asString(raw.asOf) ?? undefined,
    portfolio: asString(raw.portfolio) ?? undefined,
    caseScore: asNumber(raw.caseScore),
    symbol: asString(raw.symbol) ?? position?.symbol ?? null,
    side: asString(raw.side) ?? position?.side ?? null,
    lessons: parseLessons(raw.lessons),
    position,
    status: asString(raw.status) ?? undefined,
  }
}

function parsePortfolio(raw: unknown, index: number): TradingQaPortfolio {
  if (!isRecord(raw)) {
    throw new Error(`portfolios[${index}]: expected object`)
  }
  const key = asString(raw.key)
  const name = asString(raw.name)
  if (!key || !name) {
    throw new Error(`portfolios[${index}]: missing key/name`)
  }

  const actions = Array.isArray(raw.actions)
    ? raw.actions
        .map((a, i) => parseAction(a, i))
        .filter((a): a is TradingQaAction => a !== null)
    : []

  const days = Array.isArray(raw.days)
    ? raw.days.map(parseDay).filter((d): d is TradingQaDay => d !== null)
    : []

  let classicCases: TradingQaClassicCase[] | undefined
  if (Array.isArray(raw.classicCases)) {
    classicCases = raw.classicCases
      .map(parseClassicCase)
      .filter((c): c is TradingQaClassicCase => c !== null)
  }

  const mirrorId = raw.mirrorId
  return {
    key,
    name,
    mirrorId:
      typeof mirrorId === 'number' || typeof mirrorId === 'string'
        ? mirrorId
        : null,
    agentPortfolioId: asString(raw.agentPortfolioId),
    truthNote: asString(raw.truthNote),
    actions,
    days,
    classicCases,
  }
}

/**
 * Flexible parser for trading-qa.json. Never invents dollars; skips malformed
 * action/case rows; requires schemaVersion + portfolios[].
 */
export function parseTradingQaPayload(raw: unknown): TradingQaPayload {
  if (!isRecord(raw)) {
    throw new Error('trading-qa: expected JSON object')
  }

  const schemaVersion = asString(raw.schemaVersion)
  if (!schemaVersion) {
    throw new Error('trading-qa: missing schemaVersion')
  }

  if (!Array.isArray(raw.portfolios)) {
    throw new Error('trading-qa: missing portfolios[]')
  }

  return {
    schemaVersion,
    asOf: asString(raw.asOf) ?? undefined,
    portfolios: raw.portfolios.map((p, i) => parsePortfolio(p, i)),
  }
}

export function findPortfolio(
  payload: TradingQaPayload,
  key: string,
): TradingQaPortfolio | undefined {
  return payload.portfolios.find(
    (p) => p.key.toLowerCase() === key.toLowerCase(),
  )
}

export function sortActionsNewestFirst(
  actions: TradingQaAction[],
): TradingQaAction[] {
  return [...actions].sort((a, b) => {
    const ta = Date.parse(a.ts_utc || a.ts_il || '') || 0
    const tb = Date.parse(b.ts_utc || b.ts_il || '') || 0
    return tb - ta
  })
}

/** Prefer amount_usd / size and leverage / lev from details when present. */
export function actionSizeLev(action: TradingQaAction): {
  size: number | null
  lev: number | null
} {
  const d = action.details
  if (!d) return { size: null, lev: null }
  const size = asNumber(d.amount_usd) ?? asNumber(d.size)
  const lev = asNumber(d.leverage) ?? asNumber(d.lev)
  return { size, lev }
}

export async function fetchTradingQa(
  url: string = TRADING_QA_URL,
): Promise<TradingQaLoadState> {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      return {
        status: 'error',
        message: `Failed to load trading QA (${res.status})`,
      }
    }
    const json: unknown = await res.json()
    try {
      const payload = parseTradingQaPayload(json)
      return { status: 'ready', payload }
    } catch (e) {
      return {
        status: 'error',
        message:
          e instanceof Error ? e.message : 'Invalid trading QA payload',
      }
    }
  } catch (e) {
    return {
      status: 'error',
      message:
        e instanceof Error ? e.message : 'Network error loading trading QA',
    }
  }
}

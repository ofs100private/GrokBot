export const CLASSIC_RSI_URL = '/classic-rsi.json'

export interface ClassicRsiPortfolio {
  key: string
  name: string
  mirrorId: number | string | null
  agentPortfolioId?: string | null
  truthNote?: string | null
}

export interface ClassicRsiMandate {
  timeframe?: string | null
  confirmedCloseOnly?: boolean | null
  longOnly?: boolean | null
  sellMeansRiskOffOnly?: boolean | null
  atrSlMult?: number | null
  atrTpMult?: number | null
  qaBeforePlace?: boolean | null
  weekendGate?: boolean | null
  doNotPlaceFromThisUi?: boolean | null
  reminders: string[]
}

export interface ClassicRsiMandateGates {
  weekend?: boolean | null
  us_rth?: boolean | null
  available_cash?: number | null
  cash_floor_usd?: number | null
  blocks?: string[]
  allow_new_buys?: boolean | null
  force?: boolean | null
  note?: string | null
  [key: string]: unknown
}

export interface ClassicRsiBookSummary {
  equity?: number | null
  availableCash?: number | null
  totalInvested?: number | null
  profitLoss?: number | null
  profitLossPercent?: number | null
  closedPnl?: number | null
  credit?: number | null
  stopLossPercentage?: number | null
  currency?: string | null
  cashPct?: number | null
  deploymentPct?: number | null
  /** Market value of open positions, when the file provides it. */
  investedMarketValue?: number | null
  [key: string]: unknown
}

/** Flexible buy pack — never invent fields; render what exists. */
export interface ClassicRsiBuyPack {
  symbol?: string | null
  action?: string | null
  timeframe?: string | null
  bar_time?: string | null
  status?: string | null
  thesis?: string | null
  instrument?: { symbol?: string | null; assetClass?: string | null } | null
  rsi_rule?: {
    rsi?: number | null
    strength_tag?: string | null
    zone?: string | null
    raw_signal?: string | null
  } | null
  sizing?: { suggested_notional_usd?: number | null; note?: string | null } | null
  [key: string]: unknown
}

export interface ClassicRsiRiskOff {
  symbol?: string | null
  action?: string | null
  timeframe?: string | null
  bar_time?: string | null
  note?: string | null
  suggested?: string | null
  rsi?: number | null
  strength_tag?: string | null
  zone?: string | null
  raw_signal?: string | null
  never_short?: boolean | null
  close?: number | null
  [key: string]: unknown
}

export interface ClassicRsiLatestAuto {
  run_id?: string | null
  kind?: string | null
  status?: string | null
  asOfIDT?: string | null
  asOfET?: string | null
  portfolio?: string | null
  mirrorId?: number | string | null
  timeframe?: string | null
  confirmed_close?: boolean | null
  long_only?: boolean | null
  qa_gate?: string | null
  do_not_place?: boolean | null
  place?: boolean | null
  symbols?: string[]
  book_symbols?: string[]
  mandate_gates?: ClassicRsiMandateGates | null
  book_summary?: ClassicRsiBookSummary | null
  buy_packs: ClassicRsiBuyPack[]
  risk_off: ClassicRsiRiskOff[]
  propose_run_id?: string | null
  [key: string]: unknown
}

export interface ClassicRsiPointer {
  run_id?: string | null
  kind?: string | null
  asOfIDT?: string | null
  mirrorId?: number | string | null
  timeframe?: string | null
  buy_packs_count?: number | null
  risk_off_count?: number | null
  params_fingerprint?: string | null
  symbols?: string[]
  qa_gate?: string | null
  do_not_place?: boolean | null
  [key: string]: unknown
}

export interface ClassicRsiBacktestAggregate {
  n_trades?: number | null
  win_rate?: number | null
  expectancy_R?: number | null
  total_R?: number | null
  profit_factor?: number | null
  [key: string]: number | null | undefined
}

export interface ClassicRsiBacktestSummary {
  timeframe?: string | null
  asOfIDT?: string | null
  period?: string | null
  symbols: string[]
  aggregate: ClassicRsiBacktestAggregate | null
  notes: string[]
}

export interface ClassicRsiAuditRow {
  run_id?: string | null
  kind?: string | null
  asOfIDT?: string | null
  path?: string | null
  symbols?: string[]
  buy_packs_count?: number | null
  risk_off_count?: number | null
  params_fingerprint?: string | null
  aggregate?: ClassicRsiBacktestAggregate | null
  [key: string]: unknown
}

export interface ClassicRsiSourcePaths {
  latestAuto?: string | null
  latestPropose?: string | null
  latestBacktest?: string | null
  backtestSummary?: string | null
  auditIndex?: string | null
  [key: string]: string | null | undefined
}

/** Momentum symbols that form the cross-book hard block (read-only provenance). */
export interface ClassicRulesMomentumBlock {
  symbols: string[]
  source?: string | null
  sourceAsOf?: string | null
  sourceSha256?: string | null
  liveCrossCheck?: Record<string, unknown> | null
}

/** Numbers computed from the live data files when classicRules was written (fallback only). */
export interface ClassicRulesSnapshot {
  source?: string | null
  sourceAsOf?: string | null
  sourceSha256?: string | null
  equity?: number | null
  cash?: number | null
  currentFloorAgent?: number | null
  currentFloorMirror?: number | null
  currentDeployable?: number | null
  currentMaxNewTradesPerDay?: number | null
  currentBlocked?: string[]
  pendingFloor?: number | null
  pendingDeployable?: number | null
}

export interface ClassicRulesRow {
  rule: string
  current: string
  pending: string
}

/** Live-rule change set that is NOT live until QA PASS (Trader_Classic fix14). */
export interface ClassicRulesPending {
  id: string
  status: string
  label: string
  live: boolean
  via?: string | null
  effectiveWhen?: string | null
  decidedBy?: string | null
  decidedAtIDT?: string | null
  relayedBy?: string | null
  stagingPackage?: string | null
  /** Where the switch-over is detected: classic-portfolio.json is the single source. */
  switchOverNote?: string | null
  cashFloorPctOfEquity: number | null
  cashFloorRounding?: string | null
  maxNewTradesPerDay: number | null
  hardBlocks: string[]
  /** Text-only rule rows (current vs pending), e.g. XLE adds, QQQ core rebuy. */
  rows: ClassicRulesRow[]
  notes: string[]
  momentumBlocked: ClassicRulesMomentumBlock | null
  snapshot: ClassicRulesSnapshot | null
}

/** Next ruleset, staging only (never live from this feed). */
export interface ClassicRulesetV2 {
  status: string
  label: string
  live: boolean
  summary: string[]
  specNotes: string[]
  paperWeekStart?: string | null
  paperWeekEnd?: string | null
  cutoverTarget?: string | null
  spec?: string | null
  planPage?: string | null
}

export interface ClassicRules {
  updatedAtIDT?: string | null
  pending: ClassicRulesPending | null
  rulesetV2: ClassicRulesetV2 | null
}

export interface ClassicRsiPayload {
  schemaVersion: string
  asOf?: string | null
  portfolio: ClassicRsiPortfolio
  mandate: ClassicRsiMandate
  latestAuto: ClassicRsiLatestAuto | null
  latestPropose: ClassicRsiPointer | null
  latestBacktest: ClassicRsiPointer | null
  backtestSummary: ClassicRsiBacktestSummary | null
  auditIndex: ClassicRsiAuditRow[]
  sourcePaths?: ClassicRsiSourcePaths | null
  /** Classic rule status (pending fix14 + staging v2). Optional; absent = not shown. */
  classicRules: ClassicRules | null
}

export type ClassicRsiLoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; payload: ClassicRsiPayload }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && !Number.isNaN(value) ? value : null
}

function asBool(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((v): v is string => typeof v === 'string')
}

function parsePortfolio(raw: unknown): ClassicRsiPortfolio {
  if (!isRecord(raw)) {
    throw new Error('classic-rsi: missing portfolio')
  }
  const key = asString(raw.key) ?? 'classic'
  const name = asString(raw.name) ?? 'Classic · OfersClaw5-PRIYN'
  const mirrorId =
    asNumber(raw.mirrorId) ??
    (typeof raw.mirrorId === 'string' ? raw.mirrorId : null)
  return {
    key,
    name,
    mirrorId,
    agentPortfolioId: asString(raw.agentPortfolioId),
    truthNote: asString(raw.truthNote),
  }
}

function parseMandate(raw: unknown): ClassicRsiMandate {
  if (!isRecord(raw)) {
    return { reminders: [] }
  }
  return {
    timeframe: asString(raw.timeframe),
    confirmedCloseOnly: asBool(raw.confirmedCloseOnly),
    longOnly: asBool(raw.longOnly),
    sellMeansRiskOffOnly: asBool(raw.sellMeansRiskOffOnly),
    atrSlMult: asNumber(raw.atrSlMult),
    atrTpMult: asNumber(raw.atrTpMult),
    qaBeforePlace: asBool(raw.qaBeforePlace),
    weekendGate: asBool(raw.weekendGate),
    doNotPlaceFromThisUi: asBool(raw.doNotPlaceFromThisUi),
    reminders: asStringArray(raw.reminders),
  }
}

function parseMandateGates(raw: unknown): ClassicRsiMandateGates | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    weekend: asBool(raw.weekend),
    us_rth: asBool(raw.us_rth),
    available_cash: asNumber(raw.available_cash),
    cash_floor_usd: asNumber(raw.cash_floor_usd),
    blocks: asStringArray(raw.blocks),
    allow_new_buys: asBool(raw.allow_new_buys),
    force: asBool(raw.force),
    note: asString(raw.note),
  }
}

function parseBookSummary(raw: unknown): ClassicRsiBookSummary | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    equity: asNumber(raw.equity),
    availableCash: asNumber(raw.availableCash),
    totalInvested: asNumber(raw.totalInvested),
    profitLoss: asNumber(raw.profitLoss),
    profitLossPercent: asNumber(raw.profitLossPercent),
    closedPnl: asNumber(raw.closedPnl),
    credit: asNumber(raw.credit),
    stopLossPercentage: asNumber(raw.stopLossPercentage),
    currency: asString(raw.currency),
    cashPct: asNumber(raw.cashPct),
    deploymentPct: asNumber(raw.deploymentPct),
    investedMarketValue: asNumber(raw.investedMarketValue ?? raw.investedMV),
  }
}

function packSymbol(pack: Record<string, unknown>): string | null {
  const direct = asString(pack.symbol)
  if (direct) return direct
  if (isRecord(pack.instrument)) {
    return asString(pack.instrument.symbol)
  }
  return null
}

function parseBuyPack(raw: unknown): ClassicRsiBuyPack | null {
  if (!isRecord(raw)) return null
  const instrument = isRecord(raw.instrument)
    ? {
        symbol: asString(raw.instrument.symbol),
        assetClass: asString(raw.instrument.assetClass),
      }
    : null
  const rsi_rule = isRecord(raw.rsi_rule)
    ? {
        rsi: asNumber(raw.rsi_rule.rsi),
        strength_tag: asString(raw.rsi_rule.strength_tag),
        zone: asString(raw.rsi_rule.zone),
        raw_signal: asString(raw.rsi_rule.raw_signal),
      }
    : null
  const sizing = isRecord(raw.sizing)
    ? {
        suggested_notional_usd: asNumber(raw.sizing.suggested_notional_usd),
        note: asString(raw.sizing.note),
      }
    : null
  return {
    ...raw,
    symbol: packSymbol(raw),
    action: asString(raw.action),
    timeframe: asString(raw.timeframe),
    bar_time: asString(raw.bar_time),
    status: asString(raw.status),
    thesis: asString(raw.thesis),
    instrument,
    rsi_rule,
    sizing,
  }
}

function parseRiskOff(raw: unknown): ClassicRsiRiskOff | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    symbol: asString(raw.symbol),
    action: asString(raw.action),
    timeframe: asString(raw.timeframe),
    bar_time: asString(raw.bar_time),
    note: asString(raw.note),
    suggested: asString(raw.suggested),
    rsi: asNumber(raw.rsi),
    strength_tag: asString(raw.strength_tag),
    zone: asString(raw.zone),
    raw_signal: asString(raw.raw_signal),
    never_short: asBool(raw.never_short),
    close: asNumber(raw.close),
  }
}

function parseLatestAuto(raw: unknown): ClassicRsiLatestAuto | null {
  if (!isRecord(raw)) return null
  const buy_packs = Array.isArray(raw.buy_packs)
    ? raw.buy_packs
        .map(parseBuyPack)
        .filter((p): p is ClassicRsiBuyPack => p !== null)
    : []
  const risk_off = Array.isArray(raw.risk_off)
    ? raw.risk_off
        .map(parseRiskOff)
        .filter((p): p is ClassicRsiRiskOff => p !== null)
    : []
  return {
    ...raw,
    run_id: asString(raw.run_id),
    kind: asString(raw.kind),
    status: asString(raw.status),
    asOfIDT: asString(raw.asOfIDT),
    asOfET: asString(raw.asOfET),
    portfolio: asString(raw.portfolio),
    mirrorId:
      asNumber(raw.mirrorId) ??
      (typeof raw.mirrorId === 'string' ? raw.mirrorId : null),
    timeframe: asString(raw.timeframe),
    confirmed_close: asBool(raw.confirmed_close),
    long_only: asBool(raw.long_only),
    qa_gate: asString(raw.qa_gate),
    do_not_place: asBool(raw.do_not_place),
    place: asBool(raw.place),
    symbols: asStringArray(raw.symbols),
    book_symbols: asStringArray(raw.book_symbols),
    mandate_gates: parseMandateGates(raw.mandate_gates),
    book_summary: parseBookSummary(raw.book_summary),
    buy_packs,
    risk_off,
    propose_run_id: asString(raw.propose_run_id),
  }
}

function parsePointer(raw: unknown): ClassicRsiPointer | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    run_id: asString(raw.run_id),
    kind: asString(raw.kind),
    asOfIDT: asString(raw.asOfIDT),
    mirrorId:
      asNumber(raw.mirrorId) ??
      (typeof raw.mirrorId === 'string' ? raw.mirrorId : null),
    timeframe: asString(raw.timeframe),
    buy_packs_count: asNumber(raw.buy_packs_count),
    risk_off_count: asNumber(raw.risk_off_count),
    params_fingerprint: asString(raw.params_fingerprint),
    symbols: asStringArray(raw.symbols),
    qa_gate: asString(raw.qa_gate),
    do_not_place: asBool(raw.do_not_place),
  }
}

function parseAggregate(raw: unknown): ClassicRsiBacktestAggregate | null {
  if (!isRecord(raw)) return null
  const out: ClassicRsiBacktestAggregate = {
    n_trades: asNumber(raw.n_trades),
    win_rate: asNumber(raw.win_rate),
    expectancy_R: asNumber(raw.expectancy_R),
    total_R: asNumber(raw.total_R),
    profit_factor: asNumber(raw.profit_factor),
  }
  for (const [k, v] of Object.entries(raw)) {
    if (!(k in out) && typeof v === 'number' && !Number.isNaN(v)) {
      out[k] = v
    } else if (!(k in out) && v === null) {
      out[k] = null
    }
  }
  return out
}

function parseBacktestSummary(raw: unknown): ClassicRsiBacktestSummary | null {
  if (!isRecord(raw)) return null
  return {
    timeframe: asString(raw.timeframe),
    asOfIDT: asString(raw.asOfIDT),
    period: asString(raw.period),
    symbols: asStringArray(raw.symbols),
    aggregate: parseAggregate(raw.aggregate),
    notes: asStringArray(raw.notes),
  }
}

function parseAuditRow(raw: unknown): ClassicRsiAuditRow | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    run_id: asString(raw.run_id),
    kind: asString(raw.kind),
    asOfIDT: asString(raw.asOfIDT),
    path: asString(raw.path),
    symbols: asStringArray(raw.symbols),
    buy_packs_count: asNumber(raw.buy_packs_count),
    risk_off_count: asNumber(raw.risk_off_count),
    params_fingerprint: asString(raw.params_fingerprint),
    aggregate: parseAggregate(raw.aggregate),
  }
}

function asNumberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function parseRulesSnapshot(raw: unknown): ClassicRulesSnapshot | null {
  if (!isRecord(raw)) return null
  return {
    source: asString(raw.source),
    sourceAsOf: asString(raw.sourceAsOf),
    sourceSha256: asString(raw.sourceSha256),
    equity: asNumberOrNull(raw.equity),
    cash: asNumberOrNull(raw.cash),
    currentFloorAgent: asNumberOrNull(raw.currentFloorAgent),
    currentFloorMirror: asNumberOrNull(raw.currentFloorMirror),
    currentDeployable: asNumberOrNull(raw.currentDeployable),
    currentMaxNewTradesPerDay: asNumberOrNull(raw.currentMaxNewTradesPerDay),
    currentBlocked: asStringArray(raw.currentBlocked),
    pendingFloor: asNumberOrNull(raw.pendingFloor),
    pendingDeployable: asNumberOrNull(raw.pendingDeployable),
  }
}

function parseRulesPending(raw: unknown): ClassicRulesPending | null {
  if (!isRecord(raw)) return null
  const mb = isRecord(raw.momentumBlocked) ? raw.momentumBlocked : null
  return {
    id: asString(raw.id) ?? 'fix14',
    status: asString(raw.status) ?? 'PENDING_QA',
    label: asString(raw.label) ?? 'pending QA (fix14)',
    // Fail safe: anything other than an explicit `true` is treated as NOT live.
    live: raw.live === true,
    via: asString(raw.via),
    effectiveWhen: asString(raw.effectiveWhen),
    decidedBy: asString(raw.decidedBy),
    decidedAtIDT: asString(raw.decidedAtIDT),
    relayedBy: asString(raw.relayedBy),
    stagingPackage: asString(raw.stagingPackage),
    switchOverNote: asString(raw.switchOverNote),
    cashFloorPctOfEquity: asNumberOrNull(raw.cashFloorPctOfEquity),
    cashFloorRounding: asString(raw.cashFloorRounding),
    maxNewTradesPerDay: asNumberOrNull(raw.maxNewTradesPerDay),
    hardBlocks: asStringArray(raw.hardBlocks),
    rows: Array.isArray(raw.rows)
      ? raw.rows.flatMap((r): ClassicRulesRow[] => {
          if (!isRecord(r)) return []
          const rule = asString(r.rule)
          if (!rule) return []
          return [{ rule, current: asString(r.current) ?? '—', pending: asString(r.pending) ?? '—' }]
        })
      : [],
    notes: asStringArray(raw.notes),
    momentumBlocked: mb
      ? {
          symbols: asStringArray(mb.symbols),
          source: asString(mb.source),
          sourceAsOf: asString(mb.sourceAsOf),
          sourceSha256: asString(mb.sourceSha256),
          liveCrossCheck: isRecord(mb.liveCrossCheck) ? mb.liveCrossCheck : null,
        }
      : null,
    snapshot: parseRulesSnapshot(raw.snapshot),
  }
}

function parseRulesetV2(raw: unknown): ClassicRulesetV2 | null {
  if (!isRecord(raw)) return null
  return {
    status: asString(raw.status) ?? 'STAGING',
    label: asString(raw.label) ?? 'Ruleset v2: STAGING, not live',
    live: raw.live === true,
    summary: asStringArray(raw.summary),
    specNotes: asStringArray(raw.specNotes),
    paperWeekStart: asString(raw.paperWeekStart),
    paperWeekEnd: asString(raw.paperWeekEnd),
    cutoverTarget: asString(raw.cutoverTarget),
    spec: asString(raw.spec),
    planPage: asString(raw.planPage),
  }
}

function parseClassicRules(raw: unknown): ClassicRules | null {
  if (!isRecord(raw)) return null
  return {
    updatedAtIDT: asString(raw.updatedAtIDT),
    pending: parseRulesPending(raw.pending),
    rulesetV2: parseRulesetV2(raw.rulesetV2),
  }
}

export function parseClassicRsiPayload(json: unknown): ClassicRsiPayload {
  if (!isRecord(json)) {
    throw new Error('classic-rsi: payload is not an object')
  }
  const schemaVersion = asString(json.schemaVersion)
  if (!schemaVersion) {
    throw new Error('classic-rsi: missing schemaVersion')
  }

  const auditIndex = Array.isArray(json.auditIndex)
    ? json.auditIndex
        .map(parseAuditRow)
        .filter((r): r is ClassicRsiAuditRow => r !== null)
    : []

  const sourcePaths = isRecord(json.sourcePaths)
    ? (Object.fromEntries(
        Object.entries(json.sourcePaths).map(([k, v]) => [k, asString(v)]),
      ) as ClassicRsiSourcePaths)
    : null

  return {
    schemaVersion,
    asOf: asString(json.asOf),
    portfolio: parsePortfolio(json.portfolio),
    mandate: parseMandate(json.mandate),
    latestAuto: parseLatestAuto(json.latestAuto),
    latestPropose: parsePointer(json.latestPropose),
    latestBacktest: parsePointer(json.latestBacktest),
    backtestSummary: parseBacktestSummary(json.backtestSummary),
    auditIndex,
    sourcePaths,
    classicRules: parseClassicRules(json.classicRules),
  }
}

/** Display helpers — never invent; return "—" for null/undefined. */
export function dash(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}

export function formatWinRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function formatExpectancyR(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(3)} R`
}

export function sortAuditNewestFirst(
  rows: ClassicRsiAuditRow[],
): ClassicRsiAuditRow[] {
  return [...rows].sort((a, b) => {
    const ta = Date.parse((a.asOfIDT || '').replace(/ IDT$/, '')) || 0
    const tb = Date.parse((b.asOfIDT || '').replace(/ IDT$/, '')) || 0
    if (tb !== ta) return tb - ta
    return String(b.run_id || '').localeCompare(String(a.run_id || ''))
  })
}

export async function fetchClassicRsi(
  url: string = CLASSIC_RSI_URL,
): Promise<ClassicRsiLoadState> {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      return {
        status: 'error',
        message: `Failed to load Classic RSI (${res.status})`,
      }
    }
    const json: unknown = await res.json()
    try {
      const payload = parseClassicRsiPayload(json)
      return { status: 'ready', payload }
    } catch (e) {
      return {
        status: 'error',
        message:
          e instanceof Error ? e.message : 'Invalid classic-rsi payload',
      }
    }
  } catch (e) {
    return {
      status: 'error',
      message:
        e instanceof Error
          ? e.message
          : 'Network error loading classic-rsi.json',
    }
  }
}

export const BREAKOUT_TA_URL = '/breakout-ta.json'

export interface BreakoutTaMandate {
  longOnly?: boolean | null
  confirmedCloseOnly?: boolean | null
  volumeRequired?: boolean | null
  qaBeforeAnyPlace?: boolean | null
  reminders: string[]
}

export interface BreakoutTaSummary {
  confirmedCount: number | null
  watchCount: number | null
  failedCount: number | null
  symbolCount: number | null
}

export interface BreakoutTaStructure {
  type?: string | null
  resistance_R?: number | null
  how_measured?: string | null
  touches_near_R?: number | null
  bars_since_close_above_R?: number | null
  consol_low?: number | null
  range_height?: number | null
  [key: string]: unknown
}

export interface BreakoutTaVolume {
  breakout_vol?: number | null
  avg_vol?: number | null
  ratio?: number | null
  note?: string | null
  [key: string]: unknown
}

export interface BreakoutTaLevels {
  entry?: number | null
  stop?: number | null
  target?: number | null
  atr?: number | null
  risk_R_plan?: number | null
  price_source?: string | null
  [key: string]: unknown
}

/** Flexible row — never invent entry/stop/target; show "—" when missing. */
export interface BreakoutTaRow {
  symbol?: string | null
  timeframe?: string | null
  signal?: string | null
  do_not_place?: boolean | null
  asOfBar?: string | null
  question?: string | null
  structure: BreakoutTaStructure | null
  volume: BreakoutTaVolume | null
  levels: BreakoutTaLevels | null
  /** Flattened for display — from top-level or levels/plan */
  entry: number | null
  stop: number | null
  target: number | null
  invalidation?: string | null
  patience_note?: string | null
  [key: string]: unknown
}

export interface BreakoutTaMethod {
  id?: string | null
  name?: string | null
  timeframe?: string | null
  core?: string | null
  place?: boolean | string | null
  tonight_confirmed?: string[]
  tonight_watch?: string[]
  book_symbols?: string[]
  latest_rsi_buy_packs?: unknown[]
  latest_rsi_risk_off?: unknown[]
  [key: string]: unknown
}

export interface BreakoutTaOverlap {
  [key: string]: string[]
}

export interface BreakoutTaComparison {
  methods: BreakoutTaMethod[]
  overlap: BreakoutTaOverlap
  diff_notes: string[]
}

export interface BreakoutTaPayload {
  schemaVersion: string
  asOf?: string | null
  slot?: string | null
  run_id?: string | null
  timeframe?: string | null
  doNotPlaceFromThisUi: boolean
  mandate: BreakoutTaMandate
  summary: BreakoutTaSummary
  confirmed: BreakoutTaRow[]
  watch: BreakoutTaRow[]
  failed: BreakoutTaRow[]
  comparison: BreakoutTaComparison
  auditPath?: string | null
  skill?: string | null
}

export type BreakoutTaLoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; payload: BreakoutTaPayload }

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

function parseMandate(raw: unknown): BreakoutTaMandate {
  if (!isRecord(raw)) return { reminders: [] }
  return {
    longOnly: asBool(raw.longOnly),
    confirmedCloseOnly: asBool(raw.confirmedCloseOnly),
    volumeRequired: asBool(raw.volumeRequired),
    qaBeforeAnyPlace: asBool(raw.qaBeforeAnyPlace),
    reminders: asStringArray(raw.reminders),
  }
}

function parseSummary(raw: unknown): BreakoutTaSummary {
  if (!isRecord(raw)) {
    return {
      confirmedCount: null,
      watchCount: null,
      failedCount: null,
      symbolCount: null,
    }
  }
  return {
    confirmedCount: asNumber(raw.confirmedCount),
    watchCount: asNumber(raw.watchCount),
    failedCount: asNumber(raw.failedCount),
    symbolCount: asNumber(raw.symbolCount),
  }
}

function parseStructure(raw: unknown): BreakoutTaStructure | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    type: asString(raw.type),
    resistance_R: asNumber(raw.resistance_R),
    how_measured: asString(raw.how_measured),
    touches_near_R: asNumber(raw.touches_near_R),
    bars_since_close_above_R: asNumber(raw.bars_since_close_above_R),
    consol_low: asNumber(raw.consol_low),
    range_height: asNumber(raw.range_height),
  }
}

function parseVolume(raw: unknown): BreakoutTaVolume | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    breakout_vol: asNumber(raw.breakout_vol),
    avg_vol: asNumber(raw.avg_vol),
    ratio: asNumber(raw.ratio),
    note: asString(raw.note),
  }
}

function parseLevels(raw: unknown): BreakoutTaLevels | null {
  if (!isRecord(raw)) return null
  return {
    ...raw,
    entry: asNumber(raw.entry),
    stop: asNumber(raw.stop),
    target: asNumber(raw.target),
    atr: asNumber(raw.atr),
    risk_R_plan: asNumber(raw.risk_R_plan),
    price_source: asString(raw.price_source),
  }
}

/** Pull entry/stop/target from top-level, levels, or plan — never invent. */
function extractLevel(
  raw: Record<string, unknown>,
  key: 'entry' | 'stop' | 'target',
): number | null {
  const top = asNumber(raw[key])
  if (top !== null) return top
  if (isRecord(raw.levels)) {
    const fromLevels = asNumber(raw.levels[key])
    if (fromLevels !== null) return fromLevels
  }
  if (isRecord(raw.plan)) {
    const fromPlan = asNumber(raw.plan[key])
    if (fromPlan !== null) return fromPlan
  }
  return null
}

function parseRow(raw: unknown): BreakoutTaRow | null {
  if (!isRecord(raw)) return null
  const levels = parseLevels(raw.levels)
  return {
    ...raw,
    symbol: asString(raw.symbol),
    timeframe: asString(raw.timeframe),
    signal: asString(raw.signal),
    do_not_place: asBool(raw.do_not_place),
    asOfBar: asString(raw.asOfBar),
    question: asString(raw.question),
    structure: parseStructure(raw.structure),
    volume: parseVolume(raw.volume),
    levels,
    entry: extractLevel(raw, 'entry'),
    stop: extractLevel(raw, 'stop'),
    target: extractLevel(raw, 'target'),
    invalidation: asString(raw.invalidation),
    patience_note: asString(raw.patience_note),
  }
}

function parseMethod(raw: unknown): BreakoutTaMethod | null {
  if (!isRecord(raw)) return null
  const place =
    typeof raw.place === 'boolean' || typeof raw.place === 'string'
      ? raw.place
      : null
  return {
    ...raw,
    id: asString(raw.id),
    name: asString(raw.name),
    timeframe: asString(raw.timeframe),
    core: asString(raw.core),
    place,
    tonight_confirmed: asStringArray(raw.tonight_confirmed),
    tonight_watch: asStringArray(raw.tonight_watch),
    book_symbols: asStringArray(raw.book_symbols),
    latest_rsi_buy_packs: Array.isArray(raw.latest_rsi_buy_packs)
      ? raw.latest_rsi_buy_packs
      : [],
    latest_rsi_risk_off: Array.isArray(raw.latest_rsi_risk_off)
      ? raw.latest_rsi_risk_off
      : [],
  }
}

function parseOverlap(raw: unknown): BreakoutTaOverlap {
  if (!isRecord(raw)) return {}
  const out: BreakoutTaOverlap = {}
  for (const [k, v] of Object.entries(raw)) {
    out[k] = asStringArray(v)
  }
  return out
}

function parseComparison(raw: unknown): BreakoutTaComparison {
  if (!isRecord(raw)) {
    return { methods: [], overlap: {}, diff_notes: [] }
  }
  const methods = Array.isArray(raw.methods)
    ? raw.methods
        .map(parseMethod)
        .filter((m): m is BreakoutTaMethod => m !== null)
    : []
  return {
    methods,
    overlap: parseOverlap(raw.overlap),
    diff_notes: asStringArray(raw.diff_notes),
  }
}

export function parseBreakoutTaPayload(json: unknown): BreakoutTaPayload {
  if (!isRecord(json)) {
    throw new Error('breakout-ta: payload is not an object')
  }
  const schemaVersion = asString(json.schemaVersion)
  if (!schemaVersion) {
    throw new Error('breakout-ta: missing schemaVersion')
  }

  const confirmed = Array.isArray(json.confirmed)
    ? json.confirmed
        .map(parseRow)
        .filter((r): r is BreakoutTaRow => r !== null)
    : []
  const watch = Array.isArray(json.watch)
    ? json.watch.map(parseRow).filter((r): r is BreakoutTaRow => r !== null)
    : []
  const failed = Array.isArray(json.failed)
    ? json.failed.map(parseRow).filter((r): r is BreakoutTaRow => r !== null)
    : []

  // UI must treat doNotPlaceFromThisUi as true regardless of feed value
  const doNotPlaceFromThisUi = true

  return {
    schemaVersion,
    asOf: asString(json.asOf),
    slot: asString(json.slot),
    run_id: asString(json.run_id),
    timeframe: asString(json.timeframe),
    doNotPlaceFromThisUi,
    mandate: parseMandate(json.mandate),
    summary: parseSummary(json.summary),
    confirmed,
    watch,
    failed,
    comparison: parseComparison(json.comparison),
    auditPath: asString(json.auditPath),
    skill: asString(json.skill),
  }
}

/** Display helpers — never invent; return "—" for null/undefined. */
export function dash(
  value: string | number | boolean | null | undefined,
): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(value >= 100 ? 2 : 4)
}

export function formatVolRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value.toFixed(3)}×`
}

export function formatResistance(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(value >= 100 ? 2 : 4)
}

export async function fetchBreakoutTa(
  url: string = BREAKOUT_TA_URL,
): Promise<BreakoutTaLoadState> {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      return {
        status: 'error',
        message: `Failed to load Breakout TA (${res.status})`,
      }
    }
    const json: unknown = await res.json()
    try {
      const payload = parseBreakoutTaPayload(json)
      return { status: 'ready', payload }
    } catch (e) {
      return {
        status: 'error',
        message:
          e instanceof Error ? e.message : 'Invalid breakout-ta payload',
      }
    }
  } catch (e) {
    return {
      status: 'error',
      message:
        e instanceof Error
          ? e.message
          : 'Network error loading breakout-ta.json',
    }
  }
}

import type {
  CommodityQuote,
  DailyBriefLoadState,
  DailyBriefPayload,
  DailyBriefPortfolio,
  FearAndGreed,
  FearGreedComponent,
  SignalCard,
} from '../data/dailyBrief'
import { findClassicPortfolio } from '../data/dailyBrief'
import type { ClassicLiveLoadState, ClassicLiveSnapshot } from '../data/classicLive'
import { CLASSIC_MIRROR_ID } from '../data/classicLive'
import { formatCurrency, formatPercent, formatSigned } from '../utils/format'

interface DailyBriefProps {
  brief: DailyBriefLoadState
  classic: ClassicLiveLoadState
  onRetry: () => void
}

function formatAsOf(asOf: string): string {
  try {
    const d = new Date(asOf)
    if (Number.isNaN(d.getTime())) return asOf
    return d.toLocaleString('en-IL', {
      timeZone: 'Asia/Jerusalem',
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return asOf
  }
}

function ratingColor(rating: string): string {
  const r = rating.toLowerCase()
  if (r.includes('extreme fear')) return 'var(--fg-extreme-fear)'
  if (r.includes('fear')) return 'var(--fg-fear)'
  if (r.includes('extreme greed')) return 'var(--fg-extreme-greed)'
  if (r.includes('greed')) return 'var(--fg-greed)'
  return 'var(--fg-neutral)'
}

function scoreBandColor(score: number): string {
  if (score <= 24) return 'var(--fg-extreme-fear)'
  if (score <= 44) return 'var(--fg-fear)'
  if (score <= 55) return 'var(--fg-neutral)'
  if (score <= 75) return 'var(--fg-greed)'
  return 'var(--fg-extreme-greed)'
}

function slotBadgeLabel(payload: DailyBriefPayload): string {
  if (payload.slotBadge) return payload.slotBadge
  if (payload.weekendMode || payload.slot === 'weekend_adhoc') return 'Next session'
  if (payload.slot === 'morning_0530') return 'Morning 05:30 IL'
  if (payload.slot === 'afternoon_1530') return 'Afternoon 15:30 IL'
  return payload.slot
}

function deltaChip(label: string, current: number, previous: number) {
  const diff = current - previous
  const cls = diff > 0 ? 'positive' : diff < 0 ? 'negative' : 'neutral'
  const sign = diff > 0 ? '+' : ''
  return (
    <span className={`db-chip db-chip-${cls}`} key={label}>
      <span className="db-chip-label">{label}</span>
      <span className="db-chip-value">
        {sign}
        {diff.toFixed(1)}
      </span>
    </span>
  )
}

function FearGreedDial({ fg }: { fg: FearAndGreed }) {
  const score = Math.max(0, Math.min(100, fg.score))
  // Semicircle: angle from 180° (left, 0) to 0° (right, 100)
  const angleDeg = 180 - (score / 100) * 180
  const rad = (angleDeg * Math.PI) / 180
  const cx = 100
  const cy = 100
  const r = 78
  const needleX = cx + r * Math.cos(rad)
  const needleY = cy - r * Math.sin(rad)
  const color = scoreBandColor(score)

  return (
    <div className="db-dial-wrap">
      <svg className="db-dial" viewBox="0 0 200 120" role="img" aria-label={`Fear and Greed ${score}`}>
        <defs>
          <linearGradient id="fgArcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#c62828" />
            <stop offset="25%" stopColor="#ef6c00" />
            <stop offset="50%" stopColor="#f9a825" />
            <stop offset="75%" stopColor="#7cb342" />
            <stop offset="100%" stopColor="#13c636" />
          </linearGradient>
        </defs>
        <path
          d="M 22 100 A 78 78 0 0 1 178 100"
          fill="none"
          stroke="url(#fgArcGrad)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 22 100 A 78 78 0 0 1 178 100"
          fill="none"
          stroke="rgba(0,0,0,0.35)"
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray="2 6"
          opacity="0.4"
        />
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="6" fill={color} />
        <circle cx={cx} cy={cy} r="2.5" fill="#0d1117" />
        <text x="22" y="116" className="db-dial-end" textAnchor="middle" fontSize="9" fill="#9ca3b0">
          Fear
        </text>
        <text x="178" y="116" className="db-dial-end" textAnchor="middle" fontSize="9" fill="#9ca3b0">
          Greed
        </text>
      </svg>
      <div className="db-dial-score" style={{ color }}>
        <span className="db-score-num">{Math.round(score)}</span>
        <span className="db-score-rating">{fg.rating}</span>
      </div>
    </div>
  )
}

function ComponentStrip({ components }: { components: FearGreedComponent[] }) {
  return (
    <div className="db-component-strip" role="list" aria-label="Fear and Greed components">
      {components.map((c) => (
        <div className="db-comp-card" role="listitem" key={c.id}>
          <div
            className="db-comp-score"
            style={{ color: ratingColor(c.rating), borderColor: ratingColor(c.rating) }}
          >
            {Math.round(c.score)}
          </div>
          <div className="db-comp-meta">
            <span className="db-comp-label">{c.label}</span>
            <span className="db-comp-rating" style={{ color: ratingColor(c.rating) }}>
              {c.rating}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function CommodityChip({ name, quote }: { name: string; quote: CommodityQuote }) {
  const pctCls = quote.dayPct >= 0 ? 'positive' : 'negative'
  return (
    <div className={`db-commodity db-stance-${quote.stance}`}>
      <div className="db-commodity-top">
        <span className="db-commodity-name">{name}</span>
        <span className={`db-stance-chip stance-${quote.stance}`}>{quote.stance}</span>
      </div>
      <div className="db-commodity-bottom">
        <span className="db-commodity-price">{quote.last.toLocaleString('en-US')}</span>
        <span className={`db-commodity-pct ${pctCls}`}>{formatPercent(quote.dayPct)}</span>
      </div>
      {quote.related ? <span className="db-commodity-related">{quote.related}</span> : null}
    </div>
  )
}

function SignalTile({ signal }: { signal: SignalCard }) {
  const pctCls = signal.dayPct >= 0 ? 'positive' : 'negative'
  return (
    <div className={`db-signal db-signal-${signal.side}`}>
      <div className="db-signal-head">
        <span className="db-signal-symbol">{signal.symbol}</span>
        <span className={`db-side-badge side-${signal.side}`}>{signal.side}</span>
      </div>
      <div className="db-signal-ohlc">
        <span>
          <em>O</em> {signal.open.toFixed(2)}
        </span>
        <span>
          <em>P</em> {signal.prevClose.toFixed(2)}
        </span>
        <span>
          <em>L</em> {signal.last.toFixed(2)}
        </span>
        <span className={pctCls}>{formatPercent(signal.dayPct)}</span>
      </div>
      <p className="db-signal-rationale">{signal.rationale}</p>
    </div>
  )
}

function ClassicImpactCard({
  portfolio,
  classic,
}: {
  portfolio: DailyBriefPortfolio | undefined
  classic: ClassicLiveLoadState
}) {
  const rec = portfolio?.recommendation
  const cardPct = portfolio?.card

  let dollars: {
    equity: number
    cash: number
    invested: number
    openPnl: number
    source: 'classic-live' | 'brief-card'
  } | null = null

  if (classic.status === 'ready') {
    const cp = classic.snapshot.clientPortfolio
    dollars = {
      equity: cp.equity,
      cash: cp.availableCash,
      invested: cp.totalInvested,
      openPnl: cp.profitLoss,
      source: 'classic-live',
    }
  } else if (
    cardPct &&
    typeof cardPct.equity === 'number' &&
    typeof cardPct.cash === 'number' &&
    typeof cardPct.invested === 'number' &&
    typeof cardPct.openPnl === 'number'
  ) {
    dollars = {
      equity: cardPct.equity,
      cash: cardPct.cash,
      invested: cardPct.invested,
      openPnl: cardPct.openPnl,
      source: 'brief-card',
    }
  }

  const classicMissing =
    classic.status === 'pending' || classic.status === 'error' || classic.status === 'loading'

  return (
    <div className="db-classic-card">
      <div className="db-classic-head">
        <h3>Classic portfolio impact</h3>
        <span className="db-mirror-badge">mirror {CLASSIC_MIRROR_ID}</span>
      </div>

      {dollars ? (
        <div className="db-classic-metrics">
          <div className="db-metric">
            <span className="db-metric-label">Equity</span>
            <span className="db-metric-value">{formatCurrency(dollars.equity)}</span>
          </div>
          <div className="db-metric">
            <span className="db-metric-label">Cash</span>
            <span className="db-metric-value">{formatCurrency(dollars.cash)}</span>
          </div>
          <div className="db-metric">
            <span className="db-metric-label">Invested</span>
            <span className="db-metric-value">{formatCurrency(dollars.invested)}</span>
          </div>
          <div className="db-metric">
            <span className="db-metric-label">Open PnL</span>
            <span
              className={`db-metric-value ${dollars.openPnl >= 0 ? 'positive' : 'negative'}`}
            >
              {formatSigned(dollars.openPnl)}
            </span>
          </div>
        </div>
      ) : (
        <div className="db-classic-error" role="alert">
          Classic dollars unavailable
          {classic.status === 'pending' || classic.status === 'error'
            ? ` — ${classic.message}`
            : classicMissing
              ? ' — loading /classic-portfolio.json'
              : ''}
          . No invented amounts.
        </div>
      )}

      {cardPct && (cardPct.cashPct != null || cardPct.deploymentPct != null) ? (
        <div className="db-classic-pcts">
          {cardPct.cashPct != null ? (
            <span className="db-pct-pill">Cash {cardPct.cashPct.toFixed(1)}%</span>
          ) : null}
          {cardPct.deploymentPct != null ? (
            <span className="db-pct-pill">Deployed {cardPct.deploymentPct.toFixed(1)}%</span>
          ) : null}
          {cardPct.positionCount != null ? (
            <span className="db-pct-pill">{cardPct.positionCount} positions</span>
          ) : null}
        </div>
      ) : null}

      <div className="db-rec-grid">
        <div className="db-rec-col">
          <span className="db-rec-label buy">Buy</span>
          <div className="db-rec-tags">
            {(rec?.buy?.length ? rec.buy : ['—']).map((t) => (
              <span className="db-rec-tag" key={`b-${t}`}>
                {t}
              </span>
            ))}
          </div>
        </div>
        <div className="db-rec-col">
          <span className="db-rec-label sell">Sell</span>
          <div className="db-rec-tags">
            {(rec?.sell?.length ? rec.sell : ['—']).map((t) => (
              <span className="db-rec-tag" key={`s-${t}`}>
                {t}
              </span>
            ))}
          </div>
        </div>
        <div className="db-rec-col db-rec-hold">
          <span className="db-rec-label hold">Hold</span>
          <div className="db-rec-tags">
            {(rec?.hold?.length ? rec.hold : ['—']).map((t) => (
              <span className="db-rec-tag" key={`h-${t}`}>
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
      {rec?.diversificationNote ? (
        <p className="db-rec-note">{rec.diversificationNote}</p>
      ) : null}
      {dollars?.source === 'classic-live' && classic.status === 'ready' ? (
        <p className="db-classic-source">
          Dollars from live Classic · {(classic.snapshot as ClassicLiveSnapshot).account.username}
        </p>
      ) : null}
    </div>
  )
}

function LiveBriefBody({
  payload,
  classic,
}: {
  payload: DailyBriefPayload
  classic: ClassicLiveLoadState
}) {
  const fg = payload.fearAndGreed
  const classicPf = findClassicPortfolio(payload)
  const badge = slotBadgeLabel(payload)
  const nextSession =
    payload.weekendMode || payload.slot === 'weekend_adhoc' || /next/i.test(badge)

  return (
    <div className="db-live">
      <div className="db-hero">
        <FearGreedDial fg={fg} />
        <div className="db-hero-meta">
          <div className="db-hero-badges">
            <span className={`db-slot-badge ${nextSession ? 'db-slot-next' : ''}`}>{badge}</span>
            {payload.noNewOpens ? <span className="db-flag-badge">No new opens</span> : null}
          </div>
          <p className="db-asof">as of {formatAsOf(payload.asOf)}</p>
          <div className="db-compare-chips">
            {deltaChip('vs yesterday', fg.score, fg.previousClose)}
            {deltaChip('vs week', fg.score, fg.previous1Week)}
            {deltaChip('vs month', fg.score, fg.previous1Month)}
            {deltaChip('vs year', fg.score, fg.previous1Year)}
          </div>
        </div>
      </div>

      <ComponentStrip components={payload.components} />

      <div className="db-commodities" aria-label="Commodities">
        <CommodityChip name="Oil" quote={payload.commodities.oil} />
        <CommodityChip name="Gold" quote={payload.commodities.gold} />
        <CommodityChip name="Silver" quote={payload.commodities.silver} />
      </div>

      <div className="db-signals">
        <div className="db-signals-col">
          <h3 className="db-signals-title buy">Buy signals</h3>
          <div className="db-signals-grid">
            {payload.dailySignals.buys.map((s) => (
              <SignalTile key={`buy-${s.symbol}`} signal={s} />
            ))}
            {payload.dailySignals.buys.length === 0 ? (
              <p className="db-empty">No buy signals</p>
            ) : null}
          </div>
        </div>
        <div className="db-signals-col">
          <h3 className="db-signals-title sell">Sell signals</h3>
          <div className="db-signals-grid">
            {payload.dailySignals.sells.map((s) => (
              <SignalTile key={`sell-${s.symbol}`} signal={s} />
            ))}
            {payload.dailySignals.sells.length === 0 ? (
              <p className="db-empty">No sell signals</p>
            ) : null}
          </div>
        </div>
      </div>

      <ClassicImpactCard portfolio={classicPf} classic={classic} />

      {payload.expectedDailyImpact && payload.expectedDailyImpact.length > 0 ? (
        <ul className="db-impact-list">
          {payload.expectedDailyImpact.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      ) : null}

      <p className="db-source">{payload.source}</p>
    </div>
  )
}

export function DailyBrief({ brief, classic, onRetry }: DailyBriefProps) {
  return (
    <section className="daily-brief-section" aria-label="Daily Brief">
      <div className="section-header">
        <h2>Daily Brief</h2>
        {brief.status === 'ready' ? (
          <span className="db-header-slot">{slotBadgeLabel(brief.payload)}</span>
        ) : (
          <span className="count-badge">live JSON</span>
        )}
      </div>

      {brief.status === 'loading' ? (
        <div className="db-waiting" role="status" aria-live="polite">
          <div className="db-waiting-dial" aria-hidden="true" />
          <span className="connect-title">Loading Daily Brief…</span>
          <p>Fetching /daily-brief.json — dial stays blank until live scores arrive.</p>
        </div>
      ) : null}

      {brief.status === 'pending' || brief.status === 'error' ? (
        <div
          className={`db-waiting ${brief.status === 'error' ? 'db-waiting-error' : ''}`}
          role={brief.status === 'error' ? 'alert' : 'status'}
        >
          <div className="db-waiting-dial" aria-hidden="true" />
          <span className="connect-title">
            {brief.status === 'pending' ? 'Waiting for Daily Brief' : 'Daily Brief unavailable'}
          </span>
          <p>{brief.message}</p>
          <p className="live-hint">
            Agents inject a v1.0 live payload into <code>public/daily-brief.json</code>. No fake
            Fear &amp; Greed numbers.
          </p>
          <button type="button" className="live-retry" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}

      {brief.status === 'ready' ? (
        <LiveBriefBody payload={brief.payload} classic={classic} />
      ) : null}
    </section>
  )
}

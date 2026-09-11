import { useEffect, useState } from 'react'
import {
  actionSizeLev,
  fetchTradingQa,
  findPortfolio,
  sortActionsNewestFirst,
  type TradingQaAction,
  type TradingQaClassicCase,
  type TradingQaDay,
  type TradingQaLesson,
  type TradingQaLoadState,
  type TradingQaPortfolio,
} from '../data/tradingQa'

function formatTs(value?: string | null): string {
  if (!value) return '—'
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    return d.toLocaleString('en-IL', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    })
  } catch {
    return value
  }
}

function verdictClass(verdict?: string | null): string {
  const v = (verdict || '').toUpperCase()
  if (v === 'PASS') return 'tqa-verdict-pass'
  if (v === 'FAIL') return 'tqa-verdict-fail'
  return 'tqa-verdict-unknown'
}

function lessonTagClass(tag: string): string {
  const t = tag.toUpperCase()
  if (t === 'KEEP') return 'tqa-tag-keep'
  if (t === 'AVOID') return 'tqa-tag-avoid'
  if (t === 'WATCH') return 'tqa-tag-watch'
  return 'tqa-tag-note'
}

function ActionRow({ action }: { action: TradingQaAction }) {
  const { size, lev } = actionSizeLev(action)
  const sizeLabel =
    size != null ? `$${size.toLocaleString('en-US')}` : null
  const levLabel = lev != null ? `${lev}x` : null

  return (
    <article className="tqa-action-row">
      <div className="tqa-action-top">
        <span className={`tqa-action-badge tqa-action-${action.action.toLowerCase()}`}>
          {action.action}
        </span>
        {action.portfolio ? (
          <span className="tqa-meta-pill">{action.portfolio}</span>
        ) : null}
        {action.symbol ? (
          <span className="tqa-symbol">{action.symbol}</span>
        ) : (
          <span className="tqa-symbol tqa-symbol-muted">—</span>
        )}
        {(sizeLabel || levLabel) && (
          <span className="tqa-size-lev">
            {[sizeLabel, levLabel].filter(Boolean).join(' · ')}
          </span>
        )}
        <span
          className={`tqa-verdict-badge ${verdictClass(action.qa_verdict)}`}
        >
          {action.qa_verdict || 'N/A'}
        </span>
      </div>

      {action.rationale ? (
        <p className="tqa-rationale">{action.rationale}</p>
      ) : null}

      {action.qa_reasons && action.qa_reasons.length > 0 ? (
        <ul className="tqa-reasons">
          {action.qa_reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : null}

      {action.deviation_code ? (
        <p className="tqa-deviation">
          Deviation: <code>{action.deviation_code}</code>
        </p>
      ) : null}

      <div className="tqa-timestamps">
        <span title="Israel time">IL {formatTs(action.ts_il)}</span>
        <span title="UTC">UTC {formatTs(action.ts_utc)}</span>
      </div>
    </article>
  )
}

function LessonsPanel({ day }: { day: TradingQaDay }) {
  const keep = [
    ...(day.strategy_aligned || []).filter(
      (l) => l.tag.toUpperCase() === 'KEEP',
    ),
    ...(day.lessons || []).filter((l) => l.tag.toUpperCase() === 'KEEP'),
  ]
  const avoid = [
    ...(day.deviations_clear || []),
    ...(day.lessons || []).filter((l) => {
      const t = l.tag.toUpperCase()
      return t === 'AVOID' || t === 'WATCH'
    }),
  ]

  const hasContent =
    keep.length > 0 ||
    avoid.length > 0 ||
    (day.top_deviation_codes && day.top_deviation_codes.length > 0) ||
    (day.lessons && day.lessons.length > 0)

  if (!hasContent) {
    return (
      <div className="tqa-empty">
        No daily lessons for {day.day || 'this day'}.
      </div>
    )
  }

  const renderLesson = (l: TradingQaLesson, i: number) => (
    <li key={`${l.tag}-${i}`} className="tqa-lesson-item">
      <span className={`tqa-tag ${lessonTagClass(l.tag)}`}>{l.tag}</span>
      <span className="tqa-lesson-text">{l.text}</span>
    </li>
  )

  return (
    <div className="tqa-lessons-panel">
      <div className="tqa-lessons-meta">
        {day.day ? <span className="tqa-meta-pill">Day {day.day}</span> : null}
        {day.counts ? (
          <span className="tqa-counts">
            {day.counts.qa_pass_actions != null
              ? `${day.counts.qa_pass_actions} PASS`
              : null}
            {day.counts.qa_fail_actions != null
              ? ` · ${day.counts.qa_fail_actions} FAIL`
              : null}
            {day.counts.deviations != null
              ? ` · ${day.counts.deviations} deviations`
              : null}
          </span>
        ) : null}
      </div>

      {day.top_deviation_codes && day.top_deviation_codes.length > 0 ? (
        <div className="tqa-dev-codes">
          <span className="tqa-section-label">Top deviation codes</span>
          <div className="tqa-code-chips">
            {day.top_deviation_codes.map((c) => (
              <code key={c} className="tqa-code-chip">
                {c}
              </code>
            ))}
          </div>
        </div>
      ) : null}

      <div className="tqa-lessons-cols">
        <div className="tqa-lessons-col">
          <h4 className="tqa-col-title tqa-col-keep">KEEP</h4>
          {keep.length === 0 ? (
            <p className="tqa-empty-inline">None</p>
          ) : (
            <ul className="tqa-lesson-list">{keep.map(renderLesson)}</ul>
          )}
        </div>
        <div className="tqa-lessons-col">
          <h4 className="tqa-col-title tqa-col-avoid">AVOID / WATCH</h4>
          {avoid.length === 0 ? (
            <p className="tqa-empty-inline">None</p>
          ) : (
            <ul className="tqa-lesson-list">{avoid.map(renderLesson)}</ul>
          )}
        </div>
      </div>

      {day.lessons &&
      day.lessons.some((l) => {
        const t = l.tag.toUpperCase()
        return t !== 'KEEP' && t !== 'AVOID' && t !== 'WATCH'
      }) ? (
        <ul className="tqa-lesson-list tqa-lesson-extra">
          {day.lessons
            .filter((l) => {
              const t = l.tag.toUpperCase()
              return t !== 'KEEP' && t !== 'AVOID' && t !== 'WATCH'
            })
            .map(renderLesson)}
        </ul>
      ) : null}
    </div>
  )
}

function ClassicCaseCard({ c }: { c: TradingQaClassicCase }) {
  const symbol = c.symbol || c.position?.symbol || '—'
  const side = c.side || c.position?.side || '—'
  return (
    <article className="tqa-case-card">
      <div className="tqa-case-top">
        <code className="tqa-case-id">{c.caseId}</code>
        {c.caseScore != null ? (
          <span className="tqa-case-score">{c.caseScore.toFixed(2)}</span>
        ) : null}
      </div>
      <div className="tqa-case-meta">
        <span className="tqa-symbol">{symbol}</span>
        <span className="tqa-meta-pill">{side}</span>
        {c.position?.sizeUsd != null ? (
          <span className="tqa-size-lev">
            ${c.position.sizeUsd.toLocaleString('en-US')}
            {c.position.leverage != null ? ` · ${c.position.leverage}x` : ''}
          </span>
        ) : null}
      </div>
      {c.lessons && c.lessons.length > 0 ? (
        <ul className="tqa-lesson-list">
          {c.lessons.map((l, i) => (
            <li key={i} className="tqa-lesson-item">
              <span className={`tqa-tag ${lessonTagClass(l.tag)}`}>{l.tag}</span>
              <span className="tqa-lesson-text">{l.text}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}

function PortfolioSection({
  portfolio,
  kind,
}: {
  portfolio: TradingQaPortfolio | undefined
  kind: 'classic' | 'momentum'
}) {
  const title =
    kind === 'classic' ? 'Classic' : 'Momentum'
  const fallbackNote =
    kind === 'classic'
      ? 'mirror 11368142 only'
      : 'A invested $8000 not keys B'

  if (!portfolio) {
    return (
      <section className={`tqa-portfolio tqa-${kind}`}>
        <header className="tqa-portfolio-header">
          <h2>{title}</h2>
          <p className="tqa-truth-note">{fallbackNote}</p>
        </header>
        <div className="tqa-empty">No {title} portfolio in trading-qa.json.</div>
      </section>
    )
  }

  const actions = sortActionsNewestFirst(portfolio.actions)
  const cases = portfolio.classicCases || []

  return (
    <section className={`tqa-portfolio tqa-${kind}`}>
      <header className="tqa-portfolio-header">
        <div>
          <h2>{portfolio.name || title}</h2>
          {portfolio.agentPortfolioId ? (
            <span className="tqa-meta-pill">{portfolio.agentPortfolioId}</span>
          ) : null}
          {portfolio.mirrorId != null ? (
            <span className="tqa-meta-pill">mirror {portfolio.mirrorId}</span>
          ) : null}
        </div>
        <p className="tqa-truth-note">
          {portfolio.truthNote || fallbackNote}
        </p>
      </header>

      <div className="tqa-block">
        <h3 className="tqa-block-title">Action timeline</h3>
        {actions.length === 0 ? (
          <div className="tqa-empty">No actions yet.</div>
        ) : (
          <div className="tqa-action-list">
            {actions.map((a, i) => (
              <ActionRow
                key={`${a.ts_utc || a.ts_il || i}-${a.action}-${a.symbol || ''}`}
                action={a}
              />
            ))}
          </div>
        )}
      </div>

      <div className="tqa-block">
        <h3 className="tqa-block-title">Daily lessons</h3>
        {portfolio.days.length === 0 ? (
          <div className="tqa-empty">No daily lesson packs yet.</div>
        ) : (
          portfolio.days.map((day, i) => (
            <LessonsPanel key={day.day || day.asOf || i} day={day} />
          ))
        )}
      </div>

      {kind === 'classic' ? (
        <div className="tqa-block">
          <h3 className="tqa-block-title">Classic cases</h3>
          {cases.length === 0 ? (
            <div className="tqa-empty">No classic cases yet.</div>
          ) : (
            <div className="tqa-case-list">
              {cases.map((c, i) => (
                <ClassicCaseCard key={`${c.caseId}-${i}`} c={c} />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </section>
  )
}

interface TradingQaProps {
  onRetry?: () => void
}

export function TradingQa({ onRetry }: TradingQaProps) {
  const [state, setState] = useState<TradingQaLoadState>({ status: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetchTradingQa().then((result) => {
      if (!cancelled) setState(result)
    })
    return () => {
      cancelled = true
    }
  }, [reload])

  const handleRetry = () => {
    setReload((n) => n + 1)
    onRetry?.()
  }

  if (state.status === 'loading') {
    return (
      <div className="tqa-root" role="status" aria-live="polite">
        <div className="live-state-card">
          <span className="connect-title">Loading Trading QA…</span>
          <p>Fetching /trading-qa.json</p>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="tqa-root" role="alert">
        <div className="live-state-card live-state-error">
          <span className="connect-title">Trading QA unavailable</span>
          <p>{state.message}</p>
          <button type="button" className="live-retry" onClick={handleRetry}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  const { payload } = state
  const classic = findPortfolio(payload, 'classic')
  const momentum = findPortfolio(payload, 'momentum')

  return (
    <div className="tqa-root">
      <div className="tqa-page-header">
        <h1 className="tqa-page-title">QA &amp; Lessons</h1>
        {payload.asOf ? (
          <span className="tqa-asof">asOf {formatTs(payload.asOf)}</span>
        ) : null}
      </div>
      <p className="tqa-blend-note">
        Classic and Momentum stay separate — never blend books or truth notes.
      </p>
      <div className="tqa-grid">
        <PortfolioSection portfolio={classic} kind="classic" />
        <PortfolioSection portfolio={momentum} kind="momentum" />
      </div>
    </div>
  )
}

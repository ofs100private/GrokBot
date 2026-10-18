import { useEffect, useState } from 'react'
import {
  dash,
  fetchBreakoutTa,
  formatPrice,
  formatResistance,
  formatVolRatio,
  type BreakoutTaLoadState,
  type BreakoutTaMethod,
  type BreakoutTaOverlap,
  type BreakoutTaRow,
} from '../data/breakoutTa'

function overlapLabel(key: string): string {
  return key.replace(/_/g, ' ')
}

function placeLabel(place: boolean | string | null | undefined): string {
  if (place === null || place === undefined) return '—'
  if (typeof place === 'boolean') return place ? 'yes' : 'no (analysis only)'
  return String(place)
}

function SignalBadge({ signal }: { signal?: string | null }) {
  const s = (signal || '').toUpperCase()
  let cls = 'bta-signal-unknown'
  if (s.includes('CONFIRM')) cls = 'bta-signal-confirmed'
  else if (s.includes('WATCH')) cls = 'bta-signal-watch'
  else if (s.includes('FAIL')) cls = 'bta-signal-failed'
  return (
    <span className={`bta-signal-badge ${cls}`}>{dash(signal)}</span>
  )
}

function RowsTable({
  title,
  rows,
  emptyHint,
}: {
  title: string
  rows: BreakoutTaRow[]
  emptyHint: string
}) {
  return (
    <section className="bta-card">
      <div className="bta-card-head">
        <h2 className="bta-card-title">
          {title} ({rows.length})
        </h2>
      </div>
      {rows.length === 0 ? (
        <div className="bta-empty">{emptyHint}</div>
      ) : (
        <div className="bta-table-wrap">
          <table className="bta-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Entry</th>
                <th>Stop</th>
                <th>Target</th>
                <th>Vol ratio</th>
                <th>R</th>
                <th>Signal</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.symbol || i}-${row.asOfBar || i}`}>
                  <td>
                    <span className="bta-symbol">{dash(row.symbol)}</span>
                  </td>
                  <td className="bta-num">{formatPrice(row.entry)}</td>
                  <td className="bta-num">{formatPrice(row.stop)}</td>
                  <td className="bta-num">{formatPrice(row.target)}</td>
                  <td className="bta-num">
                    {formatVolRatio(row.volume?.ratio ?? null)}
                  </td>
                  <td className="bta-num">
                    {formatResistance(row.structure?.resistance_R ?? null)}
                  </td>
                  <td>
                    <SignalBadge signal={row.signal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function MethodCard({ method }: { method: BreakoutTaMethod }) {
  const confirmed = method.tonight_confirmed ?? []
  const watch = method.tonight_watch ?? []
  const book = method.book_symbols ?? []
  return (
    <article className="bta-method-card">
      <h3 className="bta-method-name">{dash(method.name)}</h3>
      <dl className="bta-kv bta-kv-dense">
        <div>
          <dt>id</dt>
          <dd>
            <code>{dash(method.id)}</code>
          </dd>
        </div>
        <div>
          <dt>timeframe</dt>
          <dd>{dash(method.timeframe)}</dd>
        </div>
        <div>
          <dt>place</dt>
          <dd>{placeLabel(method.place)}</dd>
        </div>
      </dl>
      {method.core ? <p className="bta-method-core">{method.core}</p> : null}
      {confirmed.length > 0 ? (
        <div className="bta-symbol-chips">
          <span className="bta-chip-label">tonight confirmed</span>
          {confirmed.map((s) => (
            <span key={s} className="bta-meta-pill bta-pill-confirmed">
              {s}
            </span>
          ))}
        </div>
      ) : null}
      {watch.length > 0 ? (
        <div className="bta-symbol-chips">
          <span className="bta-chip-label">tonight watch</span>
          {watch.map((s) => (
            <span key={s} className="bta-meta-pill bta-pill-watch">
              {s}
            </span>
          ))}
        </div>
      ) : null}
      {book.length > 0 ? (
        <div className="bta-symbol-chips">
          <span className="bta-chip-label">book</span>
          {book.map((s) => (
            <span key={s} className="bta-meta-pill">
              {s}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function OverlapPanel({ overlap }: { overlap: BreakoutTaOverlap }) {
  const entries = Object.entries(overlap)
  if (entries.length === 0) {
    return <div className="bta-empty">No overlap lists in feed.</div>
  }
  return (
    <div className="bta-overlap-grid">
      {entries.map(([key, symbols]) => (
        <div key={key} className="bta-overlap-row">
          <span className="bta-overlap-key">{overlapLabel(key)}</span>
          <div className="bta-symbol-chips">
            {symbols.length === 0 ? (
              <span className="bta-empty-inline">none</span>
            ) : (
              symbols.map((s) => (
                <span key={s} className="bta-meta-pill">
                  {s}
                </span>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export function BreakoutTa() {
  const [state, setState] = useState<BreakoutTaLoadState>({ status: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetchBreakoutTa().then((result) => {
      if (!cancelled) setState(result)
    })
    return () => {
      cancelled = true
    }
  }, [reload])

  if (state.status === 'loading') {
    return (
      <div className="bta-root" role="status" aria-live="polite">
        <div className="live-state-card">
          <span className="connect-title">Loading Breakout TA…</span>
          <p>Fetching /breakout-ta.json</p>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="bta-root" role="alert">
        <div className="live-state-card live-state-error">
          <span className="connect-title">Breakout TA unavailable</span>
          <p>{state.message}</p>
          <button
            type="button"
            className="live-retry"
            onClick={() => setReload((n) => n + 1)}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const { payload } = state
  const { mandate, summary, comparison } = payload

  return (
    <div className="bta-root">
      <header className="bta-page-header">
        <div>
          <h1 className="bta-page-title">Breakout TA</h1>
          <div className="bta-header-meta">
            {payload.run_id ? (
              <span className="bta-meta-pill">
                <code>{payload.run_id}</code>
              </span>
            ) : null}
            {payload.asOf ? (
              <span className="bta-asof">asOf {payload.asOf}</span>
            ) : null}
            {payload.timeframe ? (
              <span className="bta-meta-pill">{payload.timeframe}</span>
            ) : null}
            <span
              className="bta-do-not-place"
              title="This UI never places trades"
            >
              do not place
            </span>
          </div>
        </div>
      </header>

      {mandate.reminders.length > 0 ? (
        <div className="bta-reminders" aria-label="Mandate reminders">
          {mandate.reminders.map((r, i) => (
            <span key={i} className="bta-reminder-chip">
              {r}
            </span>
          ))}
        </div>
      ) : null}

      <div className="bta-summary-chips" aria-label="Summary counts">
        <span className="bta-summary-chip bta-chip-confirmed">
          confirmed{' '}
          <strong>
            {summary.confirmedCount == null ? '—' : summary.confirmedCount}
          </strong>
        </span>
        <span className="bta-summary-chip bta-chip-watch">
          watch{' '}
          <strong>
            {summary.watchCount == null ? '—' : summary.watchCount}
          </strong>
        </span>
        <span className="bta-summary-chip bta-chip-failed">
          failed{' '}
          <strong>
            {summary.failedCount == null ? '—' : summary.failedCount}
          </strong>
        </span>
        {summary.symbolCount != null ? (
          <span className="bta-summary-chip">
            symbols <strong>{summary.symbolCount}</strong>
          </span>
        ) : null}
      </div>

      <RowsTable
        title="Confirmed"
        rows={payload.confirmed}
        emptyHint="No confirmed breakouts in this run."
      />
      <RowsTable
        title="Watch"
        rows={payload.watch}
        emptyHint="No watch list rows."
      />
      <RowsTable
        title="Failed"
        rows={payload.failed}
        emptyHint="No failed breakouts."
      />

      <section className="bta-card">
        <div className="bta-card-head">
          <h2 className="bta-card-title">Comparison</h2>
        </div>
        <p className="bta-compare-note">
          Analysis only — never invents PnL. Overlap mirrors for display:
          Classic 11368142 / Momentum 11630170 when noted in the feed.
        </p>
        {comparison.methods.length === 0 ? (
          <div className="bta-empty">No comparison.methods in feed.</div>
        ) : (
          <div className="bta-methods-grid">
            {comparison.methods.map((m, i) => (
              <MethodCard key={m.id || i} method={m} />
            ))}
          </div>
        )}
        <div className="bta-subblock">
          <h3 className="bta-subheading">Overlap</h3>
          <OverlapPanel overlap={comparison.overlap} />
        </div>
        {comparison.diff_notes.length > 0 ? (
          <div className="bta-subblock">
            <h3 className="bta-subheading">Diff notes</h3>
            <ul className="bta-notes">
              {comparison.diff_notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <p className="bta-footer-note">
        Nightly Breakout TA — analysis only. This tab never places trades
        {payload.skill ? ` · skill ${payload.skill}` : ''}
        {payload.auditPath ? ` · audit ${payload.auditPath}` : ''}.
      </p>
    </div>
  )
}

import { useEffect, useState } from 'react'
import {
  dash,
  fetchClassicRsi,
  formatExpectancyR,
  formatWinRate,
  sortAuditNewestFirst,
  type ClassicRsiBuyPack,
  type ClassicRsiLoadState,
  type ClassicRsiPointer,
  type ClassicRsiRiskOff,
} from '../data/classicRsi'
import { formatCurrency, formatPercent, formatSigned } from '../utils/format'
import { fetchClassicLive, type ClassicLiveLoadState } from '../data/classicLive'

function statusBadgeClass(status?: string | null): string {
  const s = (status || '').toUpperCase()
  if (s === 'PASS' || s === 'OK' || s === 'READY') return 'crsi-badge-pass'
  if (s === 'GATED' || s === 'BLOCKED' || s === 'HOLD') return 'crsi-badge-gated'
  if (s === 'FAIL' || s === 'ERROR') return 'crsi-badge-fail'
  return 'crsi-badge-unknown'
}

function fmtMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return formatCurrency(value)
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return formatPercent(value)
}

function fmtSignedMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return formatSigned(value)
}

function boolLabel(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value ? 'yes' : 'no'
}

function BuyPackRow({ pack }: { pack: ClassicRsiBuyPack }) {
  const symbol =
    pack.symbol ||
    pack.instrument?.symbol ||
    '—'
  const rsi = pack.rsi_rule?.rsi
  const tag = pack.rsi_rule?.strength_tag
  const notional = pack.sizing?.suggested_notional_usd
  return (
    <article className="crsi-pack-row">
      <div className="crsi-pack-top">
        <span className="crsi-action-badge crsi-action-buy">
          {pack.action || 'BUY'}
        </span>
        <span className="crsi-symbol">{symbol}</span>
        {tag ? <span className="crsi-meta-pill">{tag}</span> : null}
        {rsi != null ? (
          <span className="crsi-meta-pill">RSI {rsi.toFixed(1)}</span>
        ) : null}
        {notional != null ? (
          <span className="crsi-size">{fmtMoney(notional)}</span>
        ) : null}
        {pack.status ? (
          <span className="crsi-meta-pill">{pack.status}</span>
        ) : null}
      </div>
      {pack.thesis ? <p className="crsi-thesis">{pack.thesis}</p> : null}
      {pack.bar_time ? (
        <div className="crsi-timestamps">bar {pack.bar_time}</div>
      ) : null}
    </article>
  )
}

function RiskOffRow({ note }: { note: ClassicRsiRiskOff }) {
  return (
    <article className="crsi-pack-row">
      <div className="crsi-pack-top">
        <span className="crsi-action-badge crsi-action-riskoff">
          {note.action || 'RISK_OFF'}
        </span>
        <span className="crsi-symbol">{note.symbol || '—'}</span>
        {note.strength_tag ? (
          <span className="crsi-meta-pill">{note.strength_tag}</span>
        ) : null}
        {note.rsi != null ? (
          <span className="crsi-meta-pill">RSI {note.rsi.toFixed(1)}</span>
        ) : null}
      </div>
      {note.note ? <p className="crsi-thesis">{note.note}</p> : null}
      {note.suggested ? (
        <p className="crsi-suggested">{note.suggested}</p>
      ) : null}
    </article>
  )
}

function PointerCard({
  title,
  pointer,
}: {
  title: string
  pointer: ClassicRsiPointer | null
}) {
  if (!pointer) {
    return (
      <section className="crsi-card">
        <h3 className="crsi-card-title">{title}</h3>
        <div className="crsi-empty">No pointer in classic-rsi.json.</div>
      </section>
    )
  }
  return (
    <section className="crsi-card">
      <h3 className="crsi-card-title">{title}</h3>
      <dl className="crsi-kv">
        <div>
          <dt>run_id</dt>
          <dd>
            <code>{dash(pointer.run_id)}</code>
          </dd>
        </div>
        <div>
          <dt>asOf IDT</dt>
          <dd>{dash(pointer.asOfIDT)}</dd>
        </div>
        <div>
          <dt>timeframe</dt>
          <dd>{dash(pointer.timeframe)}</dd>
        </div>
        <div>
          <dt>buy_packs</dt>
          <dd>
            {pointer.buy_packs_count === null ||
            pointer.buy_packs_count === undefined
              ? '—'
              : pointer.buy_packs_count}
          </dd>
        </div>
        <div>
          <dt>risk_off</dt>
          <dd>
            {pointer.risk_off_count === null ||
            pointer.risk_off_count === undefined
              ? '—'
              : pointer.risk_off_count}
          </dd>
        </div>
        <div>
          <dt>fingerprint</dt>
          <dd>
            <code>{dash(pointer.params_fingerprint)}</code>
          </dd>
        </div>
        {pointer.symbols && pointer.symbols.length > 0 ? (
          <div className="crsi-kv-wide">
            <dt>symbols</dt>
            <dd>{pointer.symbols.join(', ')}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  )
}

export function ClassicBot() {
  const [state, setState] = useState<ClassicRsiLoadState>({ status: 'loading' })
  const [reload, setReload] = useState(0)
  // Live Classic sidecar (/classic-portfolio.json) — source of cost basis + MV.
  const [live, setLive] = useState<ClassicLiveLoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setLive({ status: 'loading' })
    fetchClassicLive().then((result) => {
      if (!cancelled) setLive(result)
    })
    return () => {
      cancelled = true
    }
  }, [reload])

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetchClassicRsi().then((result) => {
      if (!cancelled) setState(result)
    })
    return () => {
      cancelled = true
    }
  }, [reload])

  const liveCp = live.status === 'ready' ? live.snapshot.clientPortfolio : null
  const liveCost = liveCp ? liveCp.totalInvested : null
  const liveMV = live.status === 'ready' ? (live.snapshot.metrics?.investedMarketValue ?? null) : null
  const liveEquity = liveCp ? liveCp.equity : null
  const liveCash = liveCp ? liveCp.availableCash : null
  const liveOpenPnl = liveCp ? liveCp.profitLoss : null
  // Open P/L % of cost basis (file field, or loader-derived openPnl / cost).
  const liveOpenPnlPct = liveCp && liveCp.totalInvested > 0 ? liveCp.profitLossPercent : null
  const liveCashPct = live.status === 'ready' ? (live.snapshot.metrics?.cashPct ?? null) : null
  const liveDeployedMV =
    liveMV != null && liveCp && liveCp.equity > 0
      ? Math.round((liveMV / liveCp.equity) * 10000) / 100
      : null

  if (state.status === 'loading') {
    return (
      <div className="crsi-root" role="status" aria-live="polite">
        <div className="live-state-card">
          <span className="connect-title">Loading Classic Bot…</span>
          <p>Fetching /classic-rsi.json</p>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="crsi-root" role="alert">
        <div className="live-state-card live-state-error">
          <span className="connect-title">Classic RSI unavailable</span>
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
  const { portfolio, mandate, latestAuto, latestPropose, latestBacktest } =
    payload
  const bt = payload.backtestSummary
  const agg = bt?.aggregate ?? null
  const audit = sortAuditNewestFirst(payload.auditIndex)
  const gates = latestAuto?.mandate_gates
  const book = latestAuto?.book_summary

  return (
    <div className="crsi-root">
      <header className="crsi-page-header">
        <div>
          <h1 className="crsi-page-title">
            {portfolio.name || 'Classic · OfersClaw5-PRIYN'}
          </h1>
          <div className="crsi-header-meta">
            {portfolio.agentPortfolioId ? (
              <span className="crsi-meta-pill">{portfolio.agentPortfolioId}</span>
            ) : null}
            {portfolio.mirrorId != null ? (
              <span className="crsi-meta-pill">
                mirror {portfolio.mirrorId}
              </span>
            ) : null}
            {payload.asOf ? (
              <span className="crsi-asof">feed asOf {payload.asOf}</span>
            ) : null}
          </div>
        </div>
        {portfolio.truthNote ? (
          <p className="crsi-truth-note">{portfolio.truthNote}</p>
        ) : null}
      </header>

      {mandate.reminders.length > 0 ? (
        <div className="crsi-reminders" aria-label="Mandate reminders">
          {mandate.reminders.map((r, i) => (
            <span key={i} className="crsi-reminder-chip">
              {r}
            </span>
          ))}
        </div>
      ) : null}

      <section className="crsi-card crsi-auto-card">
        <div className="crsi-card-head">
          <h2 className="crsi-card-title">Latest auto</h2>
          {latestAuto?.status ? (
            <span
              className={`crsi-status-badge ${statusBadgeClass(latestAuto.status)}`}
            >
              {latestAuto.status}
            </span>
          ) : (
            <span className="crsi-status-badge crsi-badge-unknown">—</span>
          )}
        </div>

        {!latestAuto ? (
          <div className="crsi-empty">No latestAuto in classic-rsi.json.</div>
        ) : (
          <>
            <dl className="crsi-kv crsi-kv-dense">
              <div>
                <dt>run_id</dt>
                <dd>
                  <code>{dash(latestAuto.run_id)}</code>
                </dd>
              </div>
              <div>
                <dt>asOf IDT</dt>
                <dd>{dash(latestAuto.asOfIDT)}</dd>
              </div>
              <div>
                <dt>asOf ET</dt>
                <dd>{dash(latestAuto.asOfET)}</dd>
              </div>
              <div>
                <dt>timeframe</dt>
                <dd>{dash(latestAuto.timeframe ?? mandate.timeframe)}</dd>
              </div>
              <div>
                <dt>confirmed_close</dt>
                <dd>{boolLabel(latestAuto.confirmed_close)}</dd>
              </div>
              <div>
                <dt>long_only</dt>
                <dd>{boolLabel(latestAuto.long_only)}</dd>
              </div>
              <div>
                <dt>do_not_place</dt>
                <dd>{boolLabel(latestAuto.do_not_place)}</dd>
              </div>
              <div>
                <dt>qa_gate</dt>
                <dd>
                  <code>{dash(latestAuto.qa_gate)}</code>
                </dd>
              </div>
            </dl>

            {gates ? (
              <div className="crsi-subblock">
                <h3 className="crsi-subheading">Mandate gates</h3>
                <div className="crsi-gate-chips">
                  <span
                    className={`crsi-gate-chip ${gates.weekend ? 'crsi-gate-on' : 'crsi-gate-off'}`}
                  >
                    weekend {gates.weekend == null ? '—' : gates.weekend ? 'ON' : 'off'}
                  </span>
                  <span
                    className={`crsi-gate-chip ${gates.allow_new_buys === false ? 'crsi-gate-on' : 'crsi-gate-off'}`}
                  >
                    allow_new_buys{' '}
                    {gates.allow_new_buys == null
                      ? '—'
                      : gates.allow_new_buys
                        ? 'yes'
                        : 'no'}
                  </span>
                  <span className="crsi-gate-chip crsi-gate-neutral">
                    cash {fmtMoney(gates.available_cash)} / floor{' '}
                    {fmtMoney(gates.cash_floor_usd)}
                  </span>
                  {gates.us_rth != null ? (
                    <span className="crsi-gate-chip crsi-gate-neutral">
                      us_rth {gates.us_rth ? 'yes' : 'no'}
                    </span>
                  ) : null}
                </div>
                {gates.blocks && gates.blocks.length > 0 ? (
                  <div className="crsi-blocks">
                    {gates.blocks.map((b) => (
                      <code key={b} className="crsi-block-chip">
                        {b}
                      </code>
                    ))}
                  </div>
                ) : null}
                {gates.note ? (
                  <p className="crsi-gate-note">{gates.note}</p>
                ) : null}
              </div>
            ) : null}

            {liveCp ? (
              <div className="crsi-subblock">
                <h3 className="crsi-subheading">Book summary (live classic-portfolio.json)</h3>
                <div className="crsi-book-grid">
                  {liveEquity != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Equity</span>
                      <span className="crsi-book-value">{fmtMoney(liveEquity)}</span>
                    </div>
                  ) : null}
                  {liveCash != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Available cash</span>
                      <span className="crsi-book-value">{fmtMoney(liveCash)}</span>
                    </div>
                  ) : null}
                  {liveCost != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Invested (cost)</span>
                      <span className="crsi-book-value">{fmtMoney(liveCost)}</span>
                    </div>
                  ) : null}
                  {liveOpenPnl != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Open P/L (unrealized)</span>
                      <span className="crsi-book-value">
                        {fmtSignedMoney(liveOpenPnl)}
                        {liveOpenPnlPct != null ? ` (${fmtPct(liveOpenPnlPct)} of cost)` : ''}
                      </span>
                    </div>
                  ) : null}
                  {liveCashPct != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Cash %</span>
                      <span className="crsi-book-value">{`${liveCashPct}%`}</span>
                    </div>
                  ) : null}
                  {liveMV != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Invested (MV)</span>
                      <span className="crsi-book-value">{fmtMoney(liveMV)}</span>
                    </div>
                  ) : null}
                  {liveDeployedMV != null ? (
                    <div className="crsi-book-stat">
                      <span className="crsi-book-label">Deployed (MV)</span>
                      <span className="crsi-book-value">{`${liveDeployedMV}%`}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            <div className="crsi-subblock">
              <h3 className="crsi-subheading">
                Buy packs ({latestAuto.buy_packs.length})
              </h3>
              {latestAuto.buy_packs.length === 0 ? (
                <div className="crsi-empty">No buy packs.</div>
              ) : (
                <div className="crsi-pack-list">
                  {latestAuto.buy_packs.map((p, i) => (
                    <BuyPackRow
                      key={`${p.symbol || i}-${p.bar_time || i}`}
                      pack={p}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="crsi-subblock">
              <h3 className="crsi-subheading">
                Risk off ({latestAuto.risk_off.length})
              </h3>
              {latestAuto.risk_off.length === 0 ? (
                <div className="crsi-empty">No risk-off notes.</div>
              ) : (
                <div className="crsi-pack-list">
                  {latestAuto.risk_off.map((n, i) => (
                    <RiskOffRow
                      key={`${n.symbol || i}-${n.bar_time || i}`}
                      note={n}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      <div className="crsi-pointer-grid">
        <PointerCard title="Latest propose" pointer={latestPropose} />
        <PointerCard title="Latest backtest" pointer={latestBacktest} />
      </div>

      <section className="crsi-card">
        <div className="crsi-card-head">
          <h2 className="crsi-card-title">
            Backtest {bt?.timeframe || mandate.timeframe || '1H'} headline
          </h2>
          {bt?.asOfIDT ? (
            <span className="crsi-asof">{bt.asOfIDT}</span>
          ) : null}
        </div>
        {!bt || !agg ? (
          <div className="crsi-empty">
            No backtestSummary.aggregate in classic-rsi.json.
          </div>
        ) : (
          <>
            <div className="crsi-metrics">
              <div className="crsi-metric">
                <span className="crsi-metric-label">n_trades</span>
                <span className="crsi-metric-value">
                  {agg.n_trades == null ? '—' : agg.n_trades}
                </span>
              </div>
              <div className="crsi-metric">
                <span className="crsi-metric-label">win rate</span>
                <span className="crsi-metric-value">
                  {formatWinRate(agg.win_rate)}
                </span>
              </div>
              <div className="crsi-metric">
                <span className="crsi-metric-label">expectancy R</span>
                <span className="crsi-metric-value">
                  {formatExpectancyR(agg.expectancy_R)}
                </span>
              </div>
              {agg.profit_factor != null ? (
                <div className="crsi-metric">
                  <span className="crsi-metric-label">profit factor</span>
                  <span className="crsi-metric-value">
                    {agg.profit_factor.toFixed(2)}
                  </span>
                </div>
              ) : null}
            </div>
            {bt.period || (bt.symbols && bt.symbols.length > 0) ? (
              <p className="crsi-bt-meta">
                {bt.period ? <span>period {bt.period}</span> : null}
                {bt.symbols && bt.symbols.length > 0 ? (
                  <span> · {bt.symbols.join(', ')}</span>
                ) : null}
              </p>
            ) : null}
            {bt.notes && bt.notes.length > 0 ? (
              <ul className="crsi-notes">
                {bt.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </section>

      <section className="crsi-card">
        <h2 className="crsi-card-title">Recent audit index</h2>
        {audit.length === 0 ? (
          <div className="crsi-empty">No auditIndex rows.</div>
        ) : (
          <div className="crsi-table-wrap">
            <table className="crsi-table">
              <thead>
                <tr>
                  <th>asOf IDT</th>
                  <th>kind</th>
                  <th>run_id</th>
                  <th>buys</th>
                  <th>risk_off</th>
                  <th>fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((row, i) => (
                  <tr key={`${row.run_id || i}`}>
                    <td>{dash(row.asOfIDT)}</td>
                    <td>
                      <span className="crsi-meta-pill">{dash(row.kind)}</span>
                    </td>
                    <td>
                      <code className="crsi-run-id">{dash(row.run_id)}</code>
                    </td>
                    <td>
                      {row.buy_packs_count == null ? '—' : row.buy_packs_count}
                    </td>
                    <td>
                      {row.risk_off_count == null ? '—' : row.risk_off_count}
                    </td>
                    <td>
                      <code>{dash(row.params_fingerprint)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="crsi-footer-note">
        Classic OfersClaw5-PRIYN / mirror 11368142 only — never Momentum. This
        tab never places trades.
      </p>
    </div>
  )
}

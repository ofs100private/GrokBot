import { useEffect, useState } from 'react'
import { type AccountMode, getPortfolio } from '../data/portfolio'
import {
  CLASSIC_MIRROR_ID,
  fetchClassicLive,
  type ClassicLiveLoadState,
  type ClassicLiveSnapshot,
} from '../data/classicLive'
import { fetchDailyBrief, type DailyBriefLoadState } from '../data/dailyBrief'
import { Header } from './Header'
import { PortfolioSummary } from './PortfolioSummary'
import { PositionsTable } from './PositionsTable'
import { MorningBriefing } from './MorningBriefing'
import { DailyBrief } from './DailyBrief'

interface DashboardProps {
  mode: AccountMode
  username: string
  onSwitchMode: () => void
  onBack: () => void
  onLiveAccount?: (username: string) => void
}

function formatAsOf(asOf: string): string {
  try {
    const d = new Date(asOf)
    if (Number.isNaN(d.getTime())) return asOf
    return d.toLocaleString('en-IL', {
      timeZone: 'Asia/Jerusalem',
      dateStyle: 'medium',
      timeStyle: 'medium',
    })
  } catch {
    return asOf
  }
}

function RealPortfolioBody({
  live,
  onRetry,
}: {
  live: ClassicLiveLoadState
  onRetry: () => void
}) {
  if (live.status === 'loading') {
    return (
      <div className="live-state-card" role="status" aria-live="polite">
        <span className="connect-title">Loading Classic live data…</span>
        <p>Fetching ledger A snapshot (mirror {CLASSIC_MIRROR_ID}).</p>
      </div>
    )
  }

  if (live.status === 'pending' || live.status === 'error') {
    return (
      <div className="live-state-card live-state-error" role="alert">
        <span className="connect-title">
          {live.status === 'pending' ? 'Waiting for Classic snapshot' : 'Classic data unavailable'}
        </span>
        <p>{live.message}</p>
        <p className="live-hint">
          Agents inject a full Trader_Classic snapshot into{' '}
          <code>public/classic-portfolio.json</code> (served at{' '}
          <code>/classic-portfolio.json</code>). No rebuild required.
        </p>
        <button type="button" className="live-retry" onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }

  const { clientPortfolio } = live.snapshot
  return (
    <>
      <PortfolioSummary portfolio={clientPortfolio} />
      <PositionsTable
        positions={clientPortfolio.positions}
        mirrors={clientPortfolio.mirrors}
      />
    </>
  )
}

export function Dashboard({
  mode,
  username,
  onSwitchMode,
  onBack,
  onLiveAccount,
}: DashboardProps) {
  const [live, setLive] = useState<ClassicLiveLoadState>({ status: 'loading' })
  const [brief, setBrief] = useState<DailyBriefLoadState>({ status: 'loading' })
  const [reloadToken, setReloadToken] = useState(0)
  const [briefReload, setBriefReload] = useState(0)

  useEffect(() => {
    if (mode !== 'real') return

    let cancelled = false
    setLive({ status: 'loading' })

    fetchClassicLive().then((result) => {
      if (cancelled) return
      setLive(result)
      if (result.status === 'ready' && onLiveAccount) {
        onLiveAccount(result.snapshot.account.username)
      }
    })

    return () => {
      cancelled = true
    }
  }, [mode, reloadToken, onLiveAccount])

  useEffect(() => {
    if (mode !== 'real') return

    let cancelled = false
    setBrief({ status: 'loading' })

    fetchDailyBrief().then((result) => {
      if (cancelled) return
      setBrief(result)
    })

    return () => {
      cancelled = true
    }
  }, [mode, briefReload])

  const demoData = mode === 'demo' ? getPortfolio('demo') : null
  const readySnapshot: ClassicLiveSnapshot | null =
    mode === 'real' && live.status === 'ready' ? live.snapshot : null

  return (
    <div className={`dashboard ${mode === 'demo' ? 'dashboard-demo' : 'dashboard-real'}`}>
      <Header
        mode={mode}
        username={username}
        onSwitchMode={onSwitchMode}
        onBack={onBack}
      />

      <main className="dashboard-main">
        {mode === 'real' ? (
          <DailyBrief
            brief={brief}
            classic={live}
            onRetry={() => setBriefReload((n) => n + 1)}
          />
        ) : null}

        <div className="dashboard-content">
          {mode === 'demo' && demoData ? (
            <>
              <PortfolioSummary portfolio={demoData.clientPortfolio} />
              <PositionsTable
                positions={demoData.clientPortfolio.positions}
                mirrors={demoData.clientPortfolio.mirrors}
              />
            </>
          ) : (
            <RealPortfolioBody
              live={live}
              onRetry={() => setReloadToken((n) => n + 1)}
            />
          )}
        </div>

        <aside className="dashboard-sidebar">
          {mode === 'demo' ? <MorningBriefing /> : null}
          <div className="connect-card">
            {mode === 'demo' ? (
              <>
                <span className="connect-title">Demo sample data</span>
                <p>
                  This view uses clearly labeled sample positions from{' '}
                  <code>src/data/portfolio.ts</code>. Switch to Real for live Classic
                  ledger A and Daily Brief.
                </p>
              </>
            ) : (
              <>
                <span className="connect-title">
                  Live Classic · mirror {CLASSIC_MIRROR_ID} ·{' '}
                  {readySnapshot?.account.username ?? username} · asOf
                </span>
                <p>
                  {readySnapshot
                    ? formatAsOf(readySnapshot.asOf)
                    : live.status === 'loading'
                      ? 'Loading snapshot…'
                      : 'Awaiting valid Trader_Classic snapshot at /classic-portfolio.json'}
                </p>
              </>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}

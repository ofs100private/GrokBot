import { useState, useEffect, useCallback } from 'react'
import { AccountChoice } from './components/AccountChoice'
import { Dashboard } from './components/Dashboard'
import { Header } from './components/Header'
import { TradingQa } from './components/TradingQa'
import { type AccountMode } from './data/portfolio'

const STORAGE_KEY = 'etoro-view-mode'
const DEMO_USERNAME = 'Demo'

type AppView = 'portfolio' | 'qa'

function getInitialMode(): AccountMode | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'demo' || stored === 'real') return stored
  } catch {
    // localStorage unavailable
  }
  return null
}

function saveMode(mode: AccountMode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // localStorage unavailable
  }
}

function viewFromHash(): AppView {
  const h = (window.location.hash || '').toLowerCase()
  if (h === '#/qa' || h === '#qa' || h.includes('/qa')) return 'qa'
  return 'portfolio'
}

function setHashForView(view: AppView) {
  const next = view === 'qa' ? '#/qa' : '#/'
  if (window.location.hash !== next) {
    window.location.hash = next
  }
}

export default function App() {
  const [mode, setMode] = useState<AccountMode | null>(getInitialMode)
  const [liveUsername, setLiveUsername] = useState<string | null>(null)
  const [view, setView] = useState<AppView>(() =>
    typeof window !== 'undefined' ? viewFromHash() : 'portfolio',
  )

  const handleSelect = (selected: AccountMode) => {
    setMode(selected)
    saveMode(selected)
    if (selected === 'demo') setLiveUsername(null)
  }

  const handleSwitchMode = () => {
    const next = mode === 'demo' ? 'real' : 'demo'
    setMode(next)
    saveMode(next)
    if (next === 'demo') setLiveUsername(null)
  }

  const handleBack = () => {
    setMode(null)
    setLiveUsername(null)
  }

  const handleLiveAccount = useCallback((username: string) => {
    setLiveUsername(username)
  }, [])

  const handleViewChange = (next: AppView) => {
    setView(next)
    setHashForView(next)
  }

  useEffect(() => {
    document.documentElement.className = mode === 'real' ? 'real-mode' : 'demo-mode'
  }, [mode])

  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (!mode) {
    return (
      <div className="app-shell">
        <AccountChoice onSelect={handleSelect} />
      </div>
    )
  }

  const username =
    mode === 'demo' ? DEMO_USERNAME : liveUsername ?? 'OfersClaw5-PRIYN'

  return (
    <div className="app-shell">
      <nav className="app-view-nav" aria-label="Main views">
        <button
          type="button"
          className={`app-view-tab ${view === 'portfolio' ? 'app-view-tab-active' : ''}`}
          onClick={() => handleViewChange('portfolio')}
          aria-current={view === 'portfolio' ? 'page' : undefined}
        >
          Portfolio
        </button>
        <button
          type="button"
          className={`app-view-tab ${view === 'qa' ? 'app-view-tab-active' : ''}`}
          onClick={() => handleViewChange('qa')}
          aria-current={view === 'qa' ? 'page' : undefined}
        >
          QA &amp; Lessons
        </button>
      </nav>

      {view === 'qa' ? (
        <div className={`dashboard ${mode === 'demo' ? 'dashboard-demo' : 'dashboard-real'}`}>
          <Header
            mode={mode}
            username={username}
            onSwitchMode={handleSwitchMode}
            onBack={handleBack}
          />
          <main className="dashboard-main tqa-main">
            <TradingQa />
          </main>
        </div>
      ) : (
        <Dashboard
          mode={mode}
          username={username}
          onSwitchMode={handleSwitchMode}
          onBack={handleBack}
          onLiveAccount={handleLiveAccount}
        />
      )}
    </div>
  )
}

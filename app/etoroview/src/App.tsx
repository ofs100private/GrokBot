import { useState, useEffect, useCallback } from 'react'
import { AccountChoice } from './components/AccountChoice'
import { Dashboard } from './components/Dashboard'
import { type AccountMode } from './data/portfolio'

const STORAGE_KEY = 'etoro-view-mode'
const DEMO_USERNAME = 'Demo'

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

export default function App() {
  const [mode, setMode] = useState<AccountMode | null>(getInitialMode)
  const [liveUsername, setLiveUsername] = useState<string | null>(null)

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

  useEffect(() => {
    document.documentElement.className = mode === 'real' ? 'real-mode' : 'demo-mode'
  }, [mode])

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
      <Dashboard
        mode={mode}
        username={username}
        onSwitchMode={handleSwitchMode}
        onBack={handleBack}
        onLiveAccount={handleLiveAccount}
      />
    </div>
  )
}

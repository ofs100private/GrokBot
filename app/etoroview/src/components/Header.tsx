import { type AccountMode } from '../data/portfolio'
import { ArrowLeft } from './icons'

interface HeaderProps {
  mode: AccountMode
  username: string
  onSwitchMode: () => void
  onBack: () => void
}

export function Header({ mode, username, onSwitchMode, onBack }: HeaderProps) {
  const isDemo = mode === 'demo'

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="icon-button"
          onClick={onBack}
          aria-label="Back to account choice"
        >
          <ArrowLeft />
        </button>
        <div className="header-brand">
          <span className="wordmark">eToroView</span>
          <span className={`mode-badge ${isDemo ? 'mode-badge-demo' : 'mode-badge-real'}`}>
            {isDemo ? 'DEMO' : 'REAL'}
          </span>
        </div>
      </div>

      <div className="header-right">
        <span className="username">{username}</span>
        <button
          type="button"
          className="switcher-button"
          onClick={onSwitchMode}
          aria-label={`Switch to ${isDemo ? 'real' : 'demo'} mode`}
        >
          Switch to {isDemo ? 'Real' : 'Demo'}
        </button>
      </div>
    </header>
  )
}

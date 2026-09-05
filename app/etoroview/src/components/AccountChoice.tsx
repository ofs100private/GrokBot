import { useState } from 'react'
import { FlaskConical, Wallet } from './icons'
import { type AccountMode } from '../data/portfolio'

interface AccountChoiceProps {
  onSelect: (mode: AccountMode) => void
}

export function AccountChoice({ onSelect }: AccountChoiceProps) {
  const [focused, setFocused] = useState<AccountMode | null>(null)

  return (
    <div className="account-choice">
      <div className="wordmark">eToroView</div>
      <h1 className="title">Choose your portfolio</h1>
      <p className="subtitle">
        Select Demo to practice risk-free, or Real to view your live account.
      </p>

      <div className="tiles" role="group" aria-label="Choose account mode">
        <button
          type="button"
          className={`tile tile-demo ${focused === 'demo' ? 'tile-focused' : ''}`}
          onClick={() => onSelect('demo')}
          onMouseEnter={() => setFocused('demo')}
          onMouseLeave={() => setFocused(null)}
          onFocus={() => setFocused('demo')}
          onBlur={() => setFocused(null)}
          aria-label="Demo virtual portfolio"
        >
          <span className="tile-icon">
            <FlaskConical />
          </span>
          <span className="tile-label">Demo</span>
          <span className="tile-subtitle">Virtual portfolio</span>
          <span className="tile-badge tile-badge-demo">Virtual</span>
        </button>

        <button
          type="button"
          className={`tile tile-real ${focused === 'real' ? 'tile-focused' : ''}`}
          onClick={() => onSelect('real')}
          onMouseEnter={() => setFocused('real')}
          onMouseLeave={() => setFocused(null)}
          onFocus={() => setFocused('real')}
          onBlur={() => setFocused(null)}
          aria-label="Real live portfolio"
        >
          <span className="tile-icon">
            <Wallet />
          </span>
          <span className="tile-label">Real</span>
          <span className="tile-subtitle">Live portfolio</span>
          <span className="tile-badge tile-badge-real">Live</span>
        </button>
      </div>

      <p className="hint">No credentials required. Sample data only.</p>
    </div>
  )
}

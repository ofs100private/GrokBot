import { type ClientPortfolio } from '../data/portfolio'
import { formatCurrency, formatPercent, formatSigned } from '../utils/format'

interface PortfolioSummaryProps {
  portfolio: ClientPortfolio
}

export function PortfolioSummary({ portfolio }: PortfolioSummaryProps) {
  const { equity, availableCash, totalInvested, profitLoss, profitLossPercent } = portfolio
  const isPositive = profitLoss >= 0

  return (
    <section className="portfolio-summary" aria-label="Account summary">
      <div className="summary-card summary-card-main">
        <span className="summary-label">Equity</span>
        <span className="summary-value">{formatCurrency(equity)}</span>
      </div>
      <div className="summary-card">
        <span className="summary-label">Available cash</span>
        <span className="summary-value">{formatCurrency(availableCash)}</span>
      </div>
      <div className="summary-card">
        <span className="summary-label">Total invested</span>
        <span className="summary-value">{formatCurrency(totalInvested)}</span>
      </div>
      <div className="summary-card">
        <span className="summary-label">Profit / Loss</span>
        <span className={`summary-value ${isPositive ? 'positive' : 'negative'}`}>
          {formatSigned(profitLoss)} ({formatPercent(profitLossPercent)})
        </span>
      </div>
    </section>
  )
}

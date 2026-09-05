import { getBriefing } from '../data/briefing'

export function MorningBriefing() {
  const briefing = getBriefing()

  return (
    <section className="briefing-section" aria-label="Morning market briefing">
      <div className="section-header">
        <h2>{briefing.title}</h2>
        <span className="briefing-date">{briefing.dateLabel}</span>
      </div>

      <div className="briefing-card">
        <div className="briefing-tone">
          <span className="tone-label">Market tone</span>
          <span className="tone-value">{briefing.tone}</span>
        </div>
        <p className="briefing-fear-greed">{briefing.fearGreed}</p>

        <div className="briefing-divider" />

        <h3>Overnight headlines</h3>
        <ul className="briefing-list">
          {briefing.headlines.map((headline, index) => (
            <li key={index} className="briefing-item">
              <span className="source">{headline.source}</span>
              <span className="take">{headline.take}</span>
            </li>
          ))}
        </ul>

        <div className="briefing-divider" />

        <h3>What to watch today</h3>
        <ul className="watchlist">
          {briefing.watchlist.map((item, index) => (
            <li key={index} className="watch-item">
              <span className="watch-label">{item.label}</span>
              <span className="watch-detail">{item.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

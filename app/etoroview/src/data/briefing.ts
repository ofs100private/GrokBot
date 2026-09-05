export interface Headline {
  source: string
  take: string
}

export interface WatchItem {
  label: string
  detail: string
}

export interface MorningBriefing {
  title: string
  dateLabel: string
  tone: string
  fearGreed: string
  headlines: Headline[]
  watchlist: WatchItem[]
}

export function getBriefing(): MorningBriefing {
  const now = new Date()
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }

  const asiaTime = now.toLocaleTimeString('en-US', {
    timeZone: 'Asia/Tokyo',
    hour: '2-digit',
    minute: '2-digit',
  })

  const jerusalemTime = now.toLocaleTimeString('en-US', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
  })

  return {
    title: 'Morning Briefing',
    dateLabel: `${now.toLocaleDateString('en-US', options)} · Asia ${asiaTime} · Jerusalem ${jerusalemTime}`,
    tone: 'Cautiously constructive',
    fearGreed: 'Fear & Greed reads 52 — neutral, with a slight risk-on tilt after the overnight session.',
    headlines: [
      {
        source: 'Reuters',
        take: 'S&P 500 futures edge higher as Treasury yields stabilise; tech earnings remain the focus.',
      },
      {
        source: 'Bloomberg',
        take: 'Oil holds near $78/bbl on Middle-East supply watch and a softer dollar.',
      },
      {
        source: 'FT',
        take: 'EUR/USD probes 1.095 after ECB officials hint that rate cuts are approaching a pause.',
      },
      {
        source: 'CNBC',
        take: 'NVIDIA continues to lead momentum names; options activity points to elevated post-earnings moves.',
      },
      {
        source: 'WSJ',
        take: 'Gold consolidates above $2,470 as real yields pull back and safe-haven flows stay steady.',
      },
      {
        source: 'Bloomberg',
        take: 'Nikkei 225 closes +0.7% as exporters gain from a weaker yen; Hang Seng lags property concerns.',
      },
    ],
    watchlist: [
      { label: 'US CPI', detail: 'Pre-release positioning into tomorrow’s print.' },
      { label: 'NVIDIA', detail: 'Earnings due after the close; implied move ~8%.' },
      { label: 'Oil (Brent)', detail: 'Watch $79.50 resistance and OPEC commentary.' },
      { label: 'USD/JPY', detail: 'Intervention chatter near 152 keeps flows choppy.' },
      { label: 'Apple', detail: 'Services growth in focus after China iPhone data.' },
    ],
  }
}

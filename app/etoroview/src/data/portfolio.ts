export type AccountMode = 'demo' | 'real'

export interface UnrealizedPnL {
  pnL: number
}

export interface Position {
  positionID: number
  instrumentID: number
  instrumentName: string
  symbol: string
  amount: number
  units: number
  openRate: number
  direction: 'Long' | 'Short'
  unrealizedPnL: UnrealizedPnL
  /** Optional; UI falls back to a deterministic color from symbol when absent. */
  avatarColor?: string
}

export interface Mirror {
  mirrorID: number
  parentPositionID: number
  instrumentName: string
  symbol: string
  amount: number
  units: number
  openRate: number
  direction: 'Long' | 'Short'
  unrealizedPnL: UnrealizedPnL
  copiedFrom: string
  avatarColor?: string
}

export interface ClientPortfolio {
  credit?: number | null
  equity: number
  availableCash: number
  totalInvested: number
  profitLoss: number
  profitLossPercent: number
  positions: Position[]
  mirrors: Mirror[]
  orders: unknown[]
}

export interface PortfolioData {
  clientPortfolio: ClientPortfolio
}

const demoPositions: Position[] = [
  {
    positionID: 1000001,
    instrumentID: 1001,
    instrumentName: 'NVIDIA',
    symbol: 'NVDA',
    amount: 5000,
    units: 45.25,
    openRate: 110.5,
    direction: 'Long',
    unrealizedPnL: { pnL: 487.5 },
    avatarColor: '#76b900',
  },
  {
    positionID: 1000002,
    instrumentID: 1002,
    instrumentName: 'Tesla',
    symbol: 'TSLA',
    amount: 3200,
    units: 16.8,
    openRate: 190.5,
    direction: 'Long',
    unrealizedPnL: { pnL: -134.4 },
    avatarColor: '#e82127',
  },
  {
    positionID: 1000003,
    instrumentID: 1003,
    instrumentName: 'Microsoft',
    symbol: 'MSFT',
    amount: 2500,
    units: 6.15,
    openRate: 406.5,
    direction: 'Long',
    unrealizedPnL: { pnL: 92.25 },
    avatarColor: '#00a4ef',
  },
  {
    positionID: 1000004,
    instrumentID: 1004,
    instrumentName: 'Bitcoin',
    symbol: 'BTC',
    amount: 1800,
    units: 0.0285,
    openRate: 63158,
    direction: 'Long',
    unrealizedPnL: { pnL: 342.6 },
    avatarColor: '#f7931a',
  },
  {
    positionID: 1000005,
    instrumentID: 1005,
    instrumentName: 'Crude Oil',
    symbol: 'OIL',
    amount: 1200,
    units: 17.1,
    openRate: 70.18,
    direction: 'Long',
    unrealizedPnL: { pnL: 78.3 },
    avatarColor: '#9ca3af',
  },
]

const demoMirrors: Mirror[] = [
  {
    mirrorID: 900001,
    parentPositionID: 800001,
    instrumentName: 'S&P 500',
    symbol: 'SPX',
    amount: 3000,
    units: 6.5,
    openRate: 461.5,
    direction: 'Long',
    unrealizedPnL: { pnL: 156.0 },
    copiedFrom: 'TopTrader_Jane',
    avatarColor: '#13c636',
  },
  {
    mirrorID: 900002,
    parentPositionID: 800002,
    instrumentName: 'Apple',
    symbol: 'AAPL',
    amount: 1500,
    units: 7.8,
    openRate: 192.3,
    direction: 'Long',
    unrealizedPnL: { pnL: -45.6 },
    copiedFrom: 'GrowthHunter',
    avatarColor: '#555555',
  },
]

function buildPortfolio(
  positions: Position[],
  mirrors: Mirror[],
  scale: number,
): ClientPortfolio {
  const totalInvested = [...positions, ...mirrors].reduce(
    (sum, item) => sum + item.amount,
    0,
  )
  const profitLoss = [...positions, ...mirrors].reduce(
    (sum, item) => sum + item.unrealizedPnL.pnL,
    0,
  )
  const credit = totalInvested + 5000 * scale
  const equity = credit + profitLoss
  const availableCash = equity - totalInvested
  const profitLossPercent = (profitLoss / totalInvested) * 100

  return {
    credit,
    equity,
    availableCash,
    totalInvested,
    profitLoss,
    profitLossPercent,
    positions,
    mirrors,
    orders: [],
  }
}

/** Demo-only sample book. Real mode must load live Classic JSON — never use hardcoded Real numbers. */
export const demoPortfolio: PortfolioData = {
  clientPortfolio: buildPortfolio(demoPositions, demoMirrors, 1),
}

/**
 * Returns Demo sample portfolio only.
 * Real / Classic must use `fetchClassicLive` from `./classicLive` — no hardcoded Real book.
 */
export function getPortfolio(mode: AccountMode): PortfolioData {
  if (mode !== 'demo') {
    throw new Error(
      'getPortfolio("real") is disabled — Real mode loads live Classic via fetchClassicLive()',
    )
  }
  return demoPortfolio
}

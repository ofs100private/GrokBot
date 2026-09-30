# Daily Trader tooling

Analysis-only package for **Daily Trader** (agent `8064c9a6-a0f7-4e52-8f7d-4cd4288b7256`).

Mandate: `daily-trader-strategy` skill — stocks + crypto + commodities, **no ETFs**, leverage ×2–×10 (class caps), risk ≤1–2% equity at SL, flatten stocks/commodities before US cash close, crypto overnight OK, daily −3% circuit.

**This package never places trades.** Do not touch Classic / Momentum books.

## Layout

```
/workspace/daily_trader/
  README.md
  qa-gate-notes.md
  daily_trader/
    __init__.py      # book defaults
    universe.py      # ETF reject + classify + liquid universe
    scan.py          # breakout scanner → audit/latest-scan.json
    backtest.py      # same-day leveraged backtest → audit/latest-backtest.*
  audit/             # scan/backtest outputs + OHLC cache
```

Mirrored under `/workspace/GrokBot/daily_trader/` when that tree exists (does not modify classic_rsi / momentum).

## Setup

```bash
cd /workspace/daily_trader
# yfinance + pandas + numpy already expected on the box
python3 -c "import yfinance, pandas, numpy"
```

## Scan (breakout)

Fetches Yahoo daily OHLC for ~80 liquid US stocks + BTC/ETH + CL=F/GC=F/SI=F (polite chunked download, 6h disk cache).

Scores **BREAKOUT**: 20-bar high, upper-third close, RVOL (1.5 stocks / 1.2 crypto / 1.3 commodities). Emits suggested leverage, ATR SL/TP, margin for a $2k book, and `flatten_deadline` for non-crypto.

```bash
cd /workspace/daily_trader
python3 -m daily_trader.scan
python3 -m daily_trader.scan --symbols AAPL NVDA BTC-USD CL=F --no-cache
python3 -m daily_trader.scan --top 15
```

Output: `/workspace/daily_trader/audit/latest-scan.json`

## Backtest (same-day leveraged)

Bar-open/close entry on BREAKOUT days; SL/TP intrabar (SL first if both); **force flat at session end** for stocks/commodities; crypto may hold overnight. Reports win rate, avg R, expectancy, max DD, leveraged P&L on margin.

```bash
cd /workspace/daily_trader
python3 -m daily_trader.backtest
python3 -m daily_trader.backtest --symbols AAPL NVDA TSLA BTC-USD GC=F --period 6mo
python3 -m daily_trader.backtest --entry-mode open --equity 2000 --risk-pct 0.015
```

Outputs:

- `/workspace/daily_trader/audit/latest-backtest.json`
- `/workspace/daily_trader/audit/latest-backtest.md`

## Defaults (from mandate)

| Item | Value |
|------|-------|
| Equity basis | $2,000 |
| Risk at SL | 1.5% equity (band 1–2%) |
| Lev defaults | stock ×3, crypto ×2, commodity ×3 |
| Lev bounds | ×2–×10 (crypto cap ×2, stock soft ×5) |
| Daily circuit | −3% equity (enforced by live bot, not this tooling) |
| Flatten | non-crypto before US cash close (~15:45 ET window in scan cards) |

## QA

See `qa-gate-notes.md` for UpdateState / QA Bot checklist stubs.

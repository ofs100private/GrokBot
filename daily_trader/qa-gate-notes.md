# Daily Trader — QA gate notes (stub for UpdateState skill)

Tooling package checks only. Live place/flatten QA is a separate real-money order gate.
Bot: Daily Trader (`8064c9a6-a0f7-4e52-8f7d-4cd4288b7256`). Skill: `daily-trader-strategy`.

## Pre-place / UpdateState checklist

- [ ] **No ETF** — symbol not in ETF reject list (SPY, QQQ, IWM, XL*, SMH, GLD, SLV, USO, ARK*, leveraged ETPs, etc.); `universe.is_etf` / `reject_reason` clean
- [ ] **Asset class allowed** — stock | crypto | commodity only
- [ ] **Leverage bounds** — suggested lev ∈ [2, 10] and ≤ class cap (crypto ≤2 default, stock soft ≤5, hard ≤10, commodity ≤10); never above eToro instrument max at place time
- [ ] **Risk %** — max loss at SL ≤ 1–2% of equity (card shows `max_loss_pct_equity`); margin/notional consistent with lev
- [ ] **SL present** — fixed SL on every candidate; never naked leverage
- [ ] **TP plan** — TP1 ~1.5R / TP2 ~2.5R (or trail rules) documented on card
- [ ] **Flatten deadline** — stocks & commodities have `flatten_deadline` (US cash close window); overnight flag false
- [ ] **Crypto overnight** — only crypto may set `allows_overnight=true`; still has SL
- [ ] **Daily −3% circuit** — if day realized+unrealized ≤ −3% equity: no new buys; flatten leveraged stock/commodity first
- [ ] **Book isolation** — Daily Trader REAL book only; never Classic / Momentum cash or mirrors
- [ ] **Scan freshness** — `audit/latest-scan.json` asOf is current session; signal is BREAKOUT (or explicit discretionary exception with QA)
- [ ] **QA PASS required** — Full Auto place only after Daily Trader run QA + real-money order QA PASS

## Tooling smoke (no place)

- [ ] `python3 -m daily_trader.scan` exits 0; writes `audit/latest-scan.json`
- [ ] ETF symbols rejected when injected (e.g. SPY/QQQ)
- [ ] `python3 -m daily_trader.backtest --symbols AAPL BTC-USD GC=F` exits 0; JSON + MD under `audit/`
- [ ] Backtest non-crypto exits use `FORCE_FLAT_EOD` / SL / TP only — no silent overnight stock holds in trade log

## AVOID codes (live)

- `OVERNIGHT_STOCK_OR_COMMODITY` — stock/commodity still open after cash close
- `ETF_REJECT` — attempted ETF
- `LEV_OUT_OF_BOUNDS` — outside ×2–×10 or class cap
- `RISK_PCT_EXCEEDED` — SL loss > 2% equity
- `DAILY_CIRCUIT` — day P&L ≤ −3%

## Out of scope for this stub

Place/prepare MCP calls, eToro order payloads, Classic/Momentum interference — handled by live bot + separate QA skills after this tooling is green.

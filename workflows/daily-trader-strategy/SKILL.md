---
name: Daily Trader strategy
description: >-
  use this when planning, scanning, backtesting, or executing Daily Trader
  same-session leveraged super-momentum trades (stocks/crypto/commodities, no
  ETFs)
---
# Daily Trader strategy

Standing playbook for **Daily Trader** — REAL MONEY day-momentum book (~**$2,000** start basis unless Ofer resets). Separate from Classic (×1, no crypto) and Momentum-HHHGDTJ ($8k EOD).

## FULL AUTO (Ofer 2026-09-30)

After **Daily Trader run QA** + **real-money order QA** PASS from QA Bot: **prepare then place** — no chat confirm. Same for flatten / SL moves when QA PASS. Report fills after the fact.

## Mandate

- Universe: **stocks + crypto + commodities** — **no ETFs** (reject SPY/QQQ/XLK/SMH/sector or commodity ETFs; trade underlying CFD/spot symbols eToro lists as stock/crypto/commodity)
- Direction: long-first super-momentum; short only if later skill revision + QA allows
- Leverage: **×2 to ×10**, never above eToro max for that instrument; default stock **×2–×5**, crypto **×2**, commodities per product max ≤×10
- Size: risk-based — max loss at SL ≤ **1–2% of equity** per name; amount so notional = cash_margin × leverage fits book
- **Stocks & commodities:** no overnight — **flatten all** before US cash close (force-close window ~15–30 min pre-close); never hold past session end
- **Crypto:** overnight **allowed**; still manage SL/TP; optional soft flatten if daily loss limit hit
- Daily loss circuit: stop new buys if day realized+unrealized ≤ **−3% equity**; flatten leveraged stock/commodity risk first
- REAL only; never touch Classic / Momentum mirrors; never demo unless Ofer says paper

## Entry — breakout / momentum

Scanner (`daily_trader.scan`) ranks breaking points:

1. **BREAKOUT:** new N-bar high (default 20 on entry TF), close in upper third of bar, RVOL ≥ 1.5 (stocks) / ≥ 1.2 (crypto), RS or relative strength vs peers when available
2. **CONTINUATION:** pullback to VWAP/EMA20 then reclaim with rising volume
3. Reject: ETF symbols, news halt, spread too wide, RVOL dead, already at daily loss limit

Timeframes: stocks/commodities **5m–15m** entries in US RTH only; crypto **15m–1h** anytime except circuit-breaker.

## SL / TP (plan before place)

- **SL:** structure low of breakout bar or 1.0–1.5× ATR(14) below entry (whichever farther but still respects max-loss %)
- **TP1:** +1.5R (optional scale 50%); **TP2:** +2.5–3R or trail after +1R to breakeven then chandelier / prior bar lows
- Always send **fixed SL** on place; never naked leverage
- Pre-trade card must show: symbol, lev, margin$, notional$, entry, SL, TP, R$, max loss %, expected hold to flatten deadline

## P&L discipline

- Mark every open with leveraged P&L% vs margin and vs notional
- Target: win rate × avg R ≥ edge after spread/fees in backtest before raising size
- Prefer few high-RVOL breakouts over spray

## EOD / flatten

- Stocks/commodities: scheduler **force flat** before cash close; AVOID if any left open after close (`OVERNIGHT_STOCK_OR_COMMODITY`)
- Crypto: may hold; still trail / SL

## Do not

Average down. Hold stock/commodity overnight. Buy ETFs. Place without fresh QA PASS. Use Classic/Momentum cash. Exceed instrument leverage max. Ignore daily −3% circuit.

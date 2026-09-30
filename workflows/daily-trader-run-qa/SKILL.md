---
name: Daily Trader run QA
description: >-
  use this when QA must validate a Daily Trader scan, propose pack, or order
  before leveraged same-day place
---
# Daily Trader run QA

Use when validating a Daily Trader scan, propose pack, or pre-place order for the ~$2k leveraged same-day book.

## Hard fails (any → FAIL, no place)

1. **ETF** in pack (SPY/QQQ/IWM/XL*/SMH/GLD/SLV/USO/sector or commodity ETF) — mandate no ETFs
2. Leverage outside **×2–×10** or above eToro instrument max
3. Stock or commodity with **no flatten_deadline** before US cash close, or plan to hold overnight
4. Missing fixed **SL** on place card
5. Risk at SL **> 2% equity** (or missing risk calc)
6. Book is Classic / Momentum mirror — must be Daily Trader book only
7. Place without citing fresh scan/backtest audit paths when required by CoS
8. Daily loss circuit already hit (−3% equity) but new buys still authorized

## Soft (PASS with codes)

- Scan returned 0 breakouts / WATCH-only (OK — do_not_place)
- Crypto overnight hold (allowed)
- Soft MTM drift on cash

## Evidence

- `/workspace/daily_trader/audit/latest-scan.json`
- `/workspace/daily_trader/audit/latest-backtest.json`
- Pre-trade card: symbol, lev, margin$, notional$, entry, SL, TP, R$, max loss %, flatten_deadline

`qa_places=false` always for this gate — Daily Trader places only after separate order QA PASS.

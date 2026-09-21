---
name: RSI four-level entries
description: >-
  use this when applying four-level RSI (Over Buy / Resistance / Support / Over
  Sold) entry or exit filters to Classic or Momentum — long-only remapping,
  daily TF preferred, never pip shorts on eToro books
---
# RSI four-level entries (adapted for Ofer books)

Reusable recipe for the **four-level RSI zone + strong-candle** signal model (levels Over Buy / Resistance / Support / Over Sold). Use when evaluating RSI Signals Entries–style logic for Classic or Momentum, wiring alerts, or coding an equivalent filter in Python — **not** as a standalone short-selling system.

**Strength % is a fixed rule label (80 = extreme touch, 70 = zone + strong candle), not a measured win rate.**

## Default levels (adjustable)

| Level | Default |
|-------|---------|
| Over Buy | 79.90 |
| Resistance | 67.90 |
| Support | 34.90 |
| Over Sold | 19.90 |

RSI length default **14**, source **close**. Wait for **bar close** (no repaint) unless debugging.

## Strong candle

Body = `|close − open|` (ignore wicks). Strong when `body ≥ multiplier × SMA(body, lookback)`. Defaults: lookback **20**, multiplier **1.2**.

## Signal rules (state machine)

Track zone occupancy + “already fired this visit.” Reset fired flag when RSI leaves that zone (so one signal per visit; zone signals can wait for a later strong candle).

**Long-only mapping for eToro books (mandatory):**

| Rule | Raw indicator | Ofer use |
|------|---------------|----------|
| Over Buy touch | Sell 80% | **Risk-off only**: do not open shorts. Prefer **no new adds**; optional tighten trail / skip chase on that name |
| Resistance + strong bearish | Sell 70% | Same as above, weaker — confirmation to pause adds |
| Over Sold touch | Buy 80% | **Candidate long entry / add timing** after other gates |
| Support + strong bullish | Buy 70% | Weaker long timing — needs strong candle in support zone |

Never place FX-style short Sell signals on Classic or Momentum.

## Which strategy should use it

### Prefer **Classic** (primary)

Classic is long-only quality + cash buffer. RSI **Support / Over Sold buys** help time dips into big-US / sector ETFs / commodities without inventing shorts. Use as a **timing overlay** on names already allowed by mandate + research — not as the sole reason to buy.

### **Momentum** (secondary filter only)

Momentum playbook is **EOD breakout / VCP** (often high RS / upper-range). Blind Over Sold buys usually **fight** that sleeve. Allowed uses only:

1. **Exit assist:** Over Buy / Resistance zone on a held name → prefer earlier trail or “no add,” still behind existing CLOSE / BE@2R / TRAIL@1R priority unless QA pack says otherwise  
2. **Soft veto:** if a breakout candidate is also mid Over Buy chase on daily, downgrade priority / skip chase  
3. **Do not** replace breakout sleeve with RSI mean-reversion packs

### Neither book as 1m/5m scalper

Default pip SL/TP (70/80 pips) and 1m/5m tuning are for FX. Our books are **US stocks/ETFs, ×1, QA-gated**. Do not auto-trade the published pip distances on eToro equities.

## Prerequisites before live use

1. **Mandate:** long-only ×1; Classic no crypto; Momentum ≤$1k/name; REAL money; QA PASS before place  
2. **Ledger truth:** Classic mirror `11368142`; Momentum mirror `11630170` ($8k) — never keys-B totals  
3. **Timeframe:** prefer **daily** (or 1H for Classic discretionary timing). Retune strong-candle multiplier on that TF  
4. **Stops/targets:** replace pip engine with **ATR or %** (e.g. SL 1.5–2×ATR, TP ≥1.5R) aligned with Classic/Momentum risk rules  
5. **Confirm on close:** keep ON for any automation  
6. **Regime gates still win:** Momentum EVENT_VOL_FREEZE / HARD_HALT / SOFT; Classic Fear/cash floor / weekend no new opens  
7. **No alert→place bypass:** TradingView alert ≠ order; still prepare → QA → place  
8. **Backtest first:** measure expectancy on the actual symbols/TF before FULL AUTO attachment  
9. **IP:** third-party Pine remains the author’s; we store **logic parameters + adaptation rules** here, not a redistributed copy of their script

## Suggested integration steps

1. Paper or offline: compute RSI(14) + zones + strong candle on daily bars for Classic watchlist / Momentum pack candidates  
2. Log signals with rule tag (`EXTREME_80` / `ZONE_70`) and whether mandate gates would allow a long  
3. Classic: only act on Buy tags when cash floor OK and name fits sleeve; Sell tags = hold/no-add notes  
4. Momentum: wire Sell tags into position_manager notes; keep Buy tags out of screener pack unless a future playbook explicitly adds an RSI mean-reversion sleeve  
5. QA pack must name the RSI rule + TF + ATR stops if any place is proposed

## Do not

- Short stocks/ETFs from Sell triangles  
- Use fixed pip SL/TP on US names without retune  
- Treat 80%/70% as predicted win rate  
- Let 1m/5m RSI noise override EOD Momentum FULL AUTO without a written playbook change and QA gate update

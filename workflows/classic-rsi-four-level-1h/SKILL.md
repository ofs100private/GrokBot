---
name: Classic RSI four-level 1H
description: >-
  use this when running Classic-only 1H RSI four-level entries (Over
  Buy/Resistance/Support/Over Sold) with ATR equity stops, long-only remap,
  confirmed close, and QA before place on OfersClaw5-PRIYN — never Momentum
---
# Classic RSI four-level entries (1H)

**Classic only** (OfersClaw5-PRIYN / Trader_Classic). Do **not** use on Momentum.

Implements the four-level RSI zone model on **1-hour** bars with **ATR equity stops**, **confirmed candle close only**, and **long-only** remapping. Code: `/workspace/classic_rsi/`.

## Mandate locks (do not weaken)

- Long-only ×1; **no shorts** from Sell triangles  
- No crypto opens  
- Cash floor ≥ ~$2.5k after adds; weekend = no new opens unless Ofer overrides  
- Ledger A truth: mirror `11368142` only  
- **QA Bot PASS** required before any prepare/place ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) or standing Classic order gate)  
- Do **not** bypass Fear / cash / weekend gates with RSI signals

## Timeframe

- Signal TF: **1H**  
- Backtest TF: **1H** (must match live)  
- Confirmed bars only (`wait for candle close` = ON)

## Levels (defaults)

| Level | Value |
|-------|------:|
| Over Buy | 79.90 |
| Resistance | 67.90 |
| Support | 34.90 |
| Over Sold | 19.90 |

RSI(14) on close. Strong candle: body ≥ **1.2 × SMA(body, 20)**. One fire per zone visit; reset when RSI leaves the zone.

## Long-only remap

| Rule | Label | Classic action |
|------|------:|----------------|
| Over Sold touch | Buy 80 | Candidate **long** timing (after mandate + research) |
| Support + strong bullish | Buy 70 | Weaker long timing |
| Over Buy touch | Sell 80 | **Risk-off only**: no short; no new add / no chase on that name |
| Resistance + strong bearish | Sell 70 | Same, weaker |

Strength % = which rule fired, **not** a win-rate claim.

## Stops / targets (equities)

- `ATR = ATR(14)` on **1H**  
- Long entry ≈ confirmed bar close  
- **SL = entry − 1.5 × ATR**  
- **TP = entry + 2.0 × ATR**  

## 1H auto (standing)

Script: `python -m classic_rsi.auto_1h` → `/workspace/classic_rsi/audit/latest-auto.json`.

Routine **classic-rsi-1h-auto**: weekdays `CRON_TZ=America/New_York 35 9-15 * * 1-5` (after :30 ET bars during RTH).

- **Universe (no fixed symbol list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ ~$100M, price ≥ $10) → rising confirmed 1H volume (last vol > SMA20 × 1.2) → top ~50 ∪ live Classic book. Screener: `classic_rsi/universe.py`. Envelope carries `universe_meta` (pool/liquid/rising counts, thresholds, fallback flag). Cache fallback: `audit/universe-latest.json` — never silently use the old fixed 6-name list as primary.  
- Auto **proposes** only — **never places**  
- Soft gates: weekend / outside US RTH / cash floor → `GATED` (buys suppressed)  
- **Every run** → QA Bot [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) citing `run_id` (0 packs and GATED still validated)  
- On run-QA **FAIL** → QA messages Trader_Classic to **rerun** `auto_1h` (max 2/hour) → re-validate new `run_id`  
- On run-QA **PASS** with packs → Trader_Classic (Fear/cash/sleeve + prepare) → [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) → place only on PASS  

## Automation flow (manual or auto)

1. `auto_1h` or `propose` on confirmed 1H bars  
2. Mandate filter — RSI cannot override  
3. QA Bot **run QA** with `run_id` (FAIL → Classic rerun → re-QA)  
4. If packs remain after run PASS → order QA → place only after PASS  
5. Post-fill audit  

## Audit trail

`/workspace/classic_rsi/audit/` — `{run_id}.json`, `index.jsonl`, `latest-propose|backtest|auto.json`. Cite `run_id` in thesis.

## Backtest

Always report TF **1H**, period, symbols, metrics, `run_id`.

## Do not

- Use on Momentum · shorts · pip SL/TP · unconfirmed bars · skip QA · treat 70/80 as win rate · place from auto script · rewrite `index.jsonl`

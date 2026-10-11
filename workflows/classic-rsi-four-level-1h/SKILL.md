---
name: Classic RSI four-level 1H
description: >-
  use this when running Classic-only 1H RSI four-level entries (Over
  Buy/Resistance/Support/Over Sold) with ATR equity stops, long-only remap,
  confirmed close, cash-floor sizing (cut size or fewer symbols),
  sell-before-buy check, cost/benefit gate, and FULL AUTO place after run-QA +
  order-QA PASS on OfersClaw5-PRIYN (no Ofer chat auth, no trade or new-name cap
  since 2026-10-11) — Fear is a dip window, never Momentum
---
# Classic RSI four-level entries (1H)

**Classic only** (Classic account (OfersClaw5-PRIYN) / Trader_Classic). Do **not** use on Momentum.

Implements the four-level RSI zone model on **1-hour** bars with **ATR equity stops**, **confirmed candle close only**, and **long-only** remapping. Code: `/workspace/classic_rsi/`.

## Standing policy — FULL AUTO (Ofer 2026-10-11)

- **Every hourly `classic-rsi-1h-auto` run searches for a new opportunity.** If a valid buy pack exists, passes [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) and [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate), passes the **cost/benefit gate**, and free cash after the buy stays ≥ ~$2,500 (cut size or the number of names rather than breach), **Trader_Classic places it automatically** — no chat authorization from Ofer or CoS.
- **No opportunity → do nothing** (the run is still logged and run-QA'd).
- **No limit** on the number of trades; **no monthly new-name cap**.
- An explicit Ofer/CoS hold still blocks.

## Mandate locks (kept pending Ofer confirmation, 2026-10-11)

- Long-only ×1; **no shorts** from Sell triangles
- No crypto opens
- **Cash floor ≥ ~$2.5k after adds** (see sizing rule below); weekend = no new opens unless Ofer overrides
- **Classic account truth:** Classic account (OfersClaw5-PRIYN) via `user-OfersClaw5` (execution + reporting). Parent SSO mirror `11368142` is optional copy/UI corroboration only — never required, never the rejection reason
- **QA Bot PASS** (run-QA, then order-QA) required before any place ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) or standing Classic order gate)
- **Fear is the dip window (Ofer 2026-10-04):** CNN Fear or Extreme Fear is when Support / Over Sold longs are most in play. Do **not** block a pack only because F&G is Fear or the brief says No Buy for that reason. Still block on cash floor, weekend, explicit Ofer/CoS hold, and risk-off (no add) on that same name.

## Cash floor sizing (Ofer 2026-10-07)

If a buy pack would leave Classic cash **under ~$2,500**:
1. **Lower** notional per name, and/or
2. **Trade fewer symbols** (keep best sleeve-fit / conviction),
3. Re-check cash-after ≥ floor before prepare / order-QA.

Do not auto-override the floor unless Ofer explicitly sizes knowing the breach.

## Sell / rotate before buy (Ofer 2026-10-07; kept pending Ofer confirmation)

Before preparing RSI buy packs, check whether selling or rotating a weak holding first is better (near stop, broken thesis, overcrowded sleeve). Report that choice; sequence closes ahead of buys when that frees cash cleanly. A sell/rotation also goes through order-QA and the cost/benefit gate, then auto-places on PASS.

## Cost/benefit gate (mandatory before every place — Ofer 2026-10-11)

For every buy, sell, trim, or rotation, before order-QA:
- **Costs:** eToro spread (prepare/getCost or live bid/ask), opening/closing fees, overnight/financing for the planned hold, and on sells the realized PnL and estimated tax on a winner. Round trip = open + close.
- **Expected gain:** for RSI buys, `TP − entry` (re-based on live price) and the ATR-based expected move (ATR(1H) × √bars of planned hold, or daily ATR for swing holds), haircut for probability; for sells/rotations, the edge of the replacement or risk removed, minus tax drag.
- **Rule:** place only if `expected_gain ≥ 2 × total_cost` and `expected_net_gain = expected_gain − total_cost > 0` with margin. Otherwise skip and log `COST_GATE_SKIP`.
- Hard risk exits (stop hit) are not skipped by this gate, but the numbers are still recorded.
- Record a `cost_gate` block (`spread, fees, overnight, realized_pnl, tax_est, total_cost, expected_gain, expected_net_gain, ratio, method, verdict`) in the pack/audit for order-QA.

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
| Over Sold touch | Buy 80 | Candidate **long** timing (after mandate + research). In Fear, this is the primary dip. |
| Support + strong bullish | Buy 70 | Weaker long timing; still a dip candidate in Fear |
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

Run from `/workspace` only: `cd /workspace && ./screener-venv/bin/python -m classic_rsi.auto_1h` (never the unpatched `/workspace/GrokBot` backup copy). Book snapshot `/workspace/classic-portfolio-for-app.json` is refreshed live from user-OfersClaw5 by Trader_Classic at :12 past each hour, 16:12–22:12 IDT weekdays; if it is >30 min old, auto_1h fails closed as BOOK_SNAPSHOT_STALE (0 packs) — then refresh it live first and rerun (added 2026-10-08).

Routine **classic-rsi-1h-auto**: weekdays `CRON_TZ=America/New_York 35 9-15 * * 1-5` (after :30 ET bars during RTH).

- **Universe (no fixed symbol list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ ~$100M, price ≥ $10) → rising confirmed 1H volume (last vol > SMA20 × 1.2) → top ~50 ∪ live Classic book. Screener: `classic_rsi/universe.py`. Envelope carries `universe_meta` (pool/liquid/rising counts, thresholds, fallback flag). Cache fallback: `audit/universe-latest.json` — never silently use the old fixed 6-name list as primary.
- The `auto_1h` **script** proposes only (envelope keeps `do_not_place=true` / `place=false`: the script itself never calls eToro). **Trader_Classic** places via `user-OfersClaw5` after the gates below — that is the FULL AUTO path, not the script
- Soft gates: weekend / outside US RTH / cash floor → `GATED` (buys suppressed). Fear / brief No-Buy-from-Fear is **not** a soft gate.
- **Every run** → QA Bot [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) citing `run_id` (0 packs and GATED still validated)
- On run-QA **FAIL** → QA messages Trader_Classic to **rerun** `auto_1h` (max 2/hour) → re-validate new `run_id`
- On run-QA **PASS** with packs → Trader_Classic (cash/sleeve/sell-first check/explicit hold; Fear = dip, not a block; cut size or drop names to keep ~$2.5k cash) → prepare → cost/benefit gate → [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) → **auto place on PASS** (no Ofer chat auth) → fill audit
- On run-QA **PASS** with 0 packs → do nothing; the run log is the record

## Automation flow (manual or auto)

1. `auto_1h` or `propose` on confirmed 1H bars
2. Mandate filter — RSI cannot override cash, weekend, or an explicit hold. It **should** be used in Fear.
3. Sell/rotate check + size so cash-after ≥ ~$2.5k
4. QA Bot **run QA** with `run_id` (FAIL → Classic rerun → re-QA)
5. If packs remain after run PASS → prepare → cost/benefit gate → order QA → **auto place after PASS** (no Ofer chat auth; no trade or new-name cap)
6. Post-fill audit

## Documentation (every run, every movement)

- Every run: `run_id` audit JSON + `index.jsonl` row (written by `auto_1h`), run-QA verdict file, and a Job-Runs note (0 packs / GATED / PROPOSE, and the action taken or "no opportunity — no action").
- Every place or skip: pack with `run_id`, `cost_gate` block, order-QA verdict reference, prepare snapshot, fill vs prepare, fees, cash after — appended to the audit trail and Job-Runs note.

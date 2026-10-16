---
name: Classic RSI four-level 1H
description: >-
  use this when running Classic-only 1H RSI four-level entries (Over
  Buy/Resistance/Support/Over Sold) with ATR equity stops, long-only remap,
  confirmed close, cash-floor sizing (cut size or fewer symbols),
  sell-before-buy check, cost/benefit gate, and FULL AUTO place after run-QA +
  order-QA PASS on OfersClaw5-PRIYN (no Ofer chat auth, max 4 new trades/day since 2026-10-16,
  no new-name cap) — 24x5 equities + BTC/ETH/SOL 24/7, TP+SL required; Fear is a dip window, never Momentum
---
# Classic RSI four-level entries (1H)

## Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)
- **FULL AUTO is ON.** Any Classic trade with run-QA PASS (RSI runs) + order-QA PASS + a passing final cost gate (execute_pass GO) is placed automatically by Trader_Classic via `user-OfersClaw5` — no Ofer chat approval. Ofer has accepted QA's earlier residual risks.
- **Hours:** US stocks/ETFs 24x5 via eToro extended hours (Sun 20:05 ET → Fri 20:00 ET, minus US holidays); an instrument that lacks extended hours or reports closed (isOpen=false / prepare rejects) falls back to RTH. Crypto trades 24/7 incl. weekends. The old weekend freeze applies to equities only.
- **Max 4 NEW trades per IDT calendar day** across all Classic runners (counter `classic_rsi/trade_counter.py`, cross-checked with positions opened today). SL edits and protective/risk exits do not count; rotation/add buy legs do.
- **Daily slot protocol (QA fix 2026-10-16):** execute_pass GO (write-lock) atomically reserves a daily slot and returns `trade_reservation_id`. On a confirmed fill run `cd /workspace && ./screener-venv/bin/python -m classic_rsi.trade_counter mark --reservation <ID> --position-id <POS>`; if the place fails or is abandoned run `... trade_counter release --reservation <ID> --reason "<why>"`. Never place without a reservation. Before any buy GO, save a fresh (≤30 min) `user-OfersClaw5` get-my-trading-history read as `{"asOf": <ISO>, "response": <raw>}` to `/workspace/classic_rsi/state/trading-history-today.json` (opened-and-closed-today positions count toward the 4). Missing/stale history → `TRADING_HISTORY_MISSING` (NO-GO). The counter path is pinned; never set `CLASSIC_TRADE_COUNTER` in production.
- **Live open check:** stocks/ETFs need an explicit live per-instrument `isOpen=true` (`--instrument-open true` for RSI buys; `is_open: true` on every rebalance live leg). Unknown → CLOSED (`INSTRUMENT_OPEN_UNKNOWN`). Crypto majors are open 24/7 unless the read says closed.
- **No XLE adds is hard-enforced:** any XLE buy/add → `NO_XLE_ADDS` (execute_pass and propose). Sells/trims of XLE are allowed.
- **Crypto specifics:** crypto packs must carry the explicit instrumentId (100000/100001/100063); a bare BTC/ETH/SOL symbol never resolves to crypto. Crypto SL = max(2.5×ATR(1H), 4%) capped at 20% below entry, TP = entry + 1.5×SL distance; rebalance crypto SL must be 4–20% below ask and ≥ 1× daily ATR. Preliminary crypto cost floor: 1% spread + 1% fee per side.
- **Caps of TOTAL equity:** single stock ≤ 20%, ETF/fund ≤ 35%, any sleeve ≤ 45%, crypto sleeve (BTC+ETH+SOL) ≤ 15%. **Cash floor ~$1,500** after every buy (sequenced across a batch).
- **Crypto:** only BTC (instrumentId 100000), ETH (100001), SOL (100063); ×1 long; SL+TP required. Every other crypto stays blocked. Symbol traps: bare `T` = Threshold crypto (100528), AT&T is `T.US` (1030); `CVX` → `CVX.US`; never resolve by bare ticker alone.
- **Every new buy MUST carry a calculated take-profit AND a stop-loss on the order.** TP from ATR/R-multiple (default SL = entry − 1.5×ATR, TP = entry + 2.0×ATR, re-based on live ask; reward:risk ≥ 1.25) and the TP distance must satisfy the cost gate (expected gain ≥ 2× round-trip cost). A buy without TP (takeProfitRate null) is a hard fail.
- **Unchanged:** ×1 long only, no leverage/shorts, stops required, sell/rotate before buy, cost gate (expected gain ≥ 2× round-trip cost), cross-book block vs Momentum-HHHGDTJ live holdings, no XLE adds.
- **Overlap note:** the Daily Trader book trades leveraged crypto/stocks same-day; Classic crypto is a ×1 swing on a separate account. Flag (do not auto-block) when Classic would buy the same crypto Daily Trader holds/trades that day, and never treat Daily Trader levels as Classic signals.


**Classic only** (Classic account (OfersClaw5-PRIYN) / Trader_Classic). Do **not** use on Momentum.

Implements the four-level RSI zone model on **1-hour** bars with **ATR equity stops**, **confirmed candle close only**, and **long-only** remapping. Code: `/workspace/classic_rsi/`.

## Standing policy — FULL AUTO (Ofer 2026-10-11)

**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place ON — Ofer accepted QA's residual risks 2026-10-16 01:27 IDT (see standing rules update).

- **Every `classic-rsi-1h-auto` run (every 3 hours weekdays) searches for a new opportunity.** If a valid buy pack exists, passes [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) and [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate), passes the **cost/benefit gate**, and free cash after the buy stays ≥ ~$1,500 (cut size or the number of names rather than breach), **Trader_Classic places it automatically** — no chat authorization from Ofer or CoS.
- **No opportunity → do nothing** (the run is still logged and run-QA'd).
- **Max 4 NEW trades per IDT calendar day**; **no monthly new-name cap**.
- An explicit Ofer/CoS hold still blocks.

## Mandate locks (confirmed Ofer 2026-10-16 01:27 IDT; was pending since 2026-10-11)

- Long-only ×1; **no shorts** from Sell triangles
- Crypto opens only BTC/ETH/SOL ×1 (crypto sleeve ≤ 15% of total equity)
- **Cash floor ≥ ~$1.5k after adds** (see sizing rule below); equities 24x5 (extended hours), crypto 24/7; max 4 new trades/day
- **Classic account truth:** Classic account (OfersClaw5-PRIYN) via `user-OfersClaw5` (execution + reporting). Parent SSO mirror `11368142` is optional copy/UI corroboration only — never required, never the rejection reason
- **QA Bot PASS** (run-QA, then order-QA) required before any place ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) or standing Classic order gate)
- **Fear is the dip window (Ofer 2026-10-04):** CNN Fear or Extreme Fear is when Support / Over Sold longs are most in play. Do **not** block a pack only because F&G is Fear or the brief says No Buy for that reason. Still block on cash floor, weekend, explicit Ofer/CoS hold, and risk-off (no add) on that same name.
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either.

## Cash floor sizing (Ofer 2026-10-07)

If a buy pack would leave Classic cash **under ~$1,500**:
1. **Lower** notional per name, and/or
2. **Trade fewer symbols** (keep best sleeve-fit / conviction),
3. Re-check cash-after ≥ floor before prepare / order-QA.

Do not auto-override the floor unless Ofer explicitly sizes knowing the breach.

## Sell / rotate before buy (Ofer 2026-10-07; confirmed 2026-10-16)

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

Routine **classic-rsi-1h-auto**: weekdays every 3 hours `CRON_TZ=Asia/Jerusalem 35 */3 * * 1-5` (Ofer 2026-10-16 01:27 IDT). Equities trade inside the 24x5 extended-hours window; BTC/ETH/SOL 24/7. Soft-gate when the equity window is closed (weekend/holiday); crypto may still scan. Pre-buy refresh (`classic_rsi.pre_buy`) is mandatory before any buy GO. The script self-gates by window.

- **Universe (no fixed symbol list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ ~$100M, price ≥ $10) → rising confirmed 1H volume (last vol > SMA20 × 1.2) → top ~50 ∪ live Classic book. Screener: `classic_rsi/universe.py`. Envelope carries `universe_meta` (pool/liquid/rising counts, thresholds, fallback flag). Cache fallback: `audit/universe-latest.json` — never silently use the old fixed 6-name list as primary.
- The `auto_1h` **script** proposes only (envelope keeps `do_not_place=true` / `place=false`: the script itself never calls eToro). **Trader_Classic** places via `user-OfersClaw5` after the gates below — that is the FULL AUTO path, not the script
- Soft gates: equity window closed (weekend/holiday outside 24x5; crypto still scanned) / daily 4-trade limit / cash floor → `GATED` (buys suppressed). Fear / brief No-Buy-from-Fear is **not** a soft gate.
- **Every run** → QA Bot [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) citing `run_id` (0 packs and GATED still validated)
- On run-QA **FAIL** → QA messages Trader_Classic to **rerun** `auto_1h` (max 2/hour) → re-validate new `run_id`
- On run-QA **PASS** with packs → Trader_Classic (cash/sleeve/sell-first check/explicit hold; Fear = dip, not a block; cut size or drop names to keep ~$1.5k cash) → prepare → cost/benefit gate → [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) → **auto place on PASS** (no Ofer chat auth) → fill audit
- On run-QA **PASS** with 0 packs → do nothing; the run log is the record

## Automation flow (manual or auto)

1. `auto_1h` or `propose` on confirmed 1H bars
2. Mandate filter — RSI cannot override cash, weekend, or an explicit hold. It **should** be used in Fear.
3. Sell/rotate check + size so cash-after ≥ ~$1.5k
4. QA Bot **run QA** with `run_id` (FAIL → Classic rerun → re-QA)
5. If packs remain after run PASS → pre-buy refresh → prepare → cost/benefit gate → order QA → **auto place after PASS** (no Ofer chat auth; max 4 new trades/IDT day; no monthly new-name cap)
6. Post-fill audit

## Documentation (every run, every movement)

- Every run: `run_id` audit JSON + `index.jsonl` row (written by `auto_1h`), run-QA verdict file, and a Job-Runs note (0 packs / GATED / PROPOSE, and the action taken or "no opportunity — no action").
- Every place or skip: pack with `run_id`, `cost_gate` block, order-QA verdict reference, prepare snapshot, fill vs prepare, fees, cash after — appended to the audit trail and Job-Runs note.

## Pre-buy refresh — run before EVERY buy GO (QA fix3 2026-10-16)
1. READ-ONLY on `user-OfersClaw5`, save each raw output verbatim:
   a. `get-my-trading-history` → `/tmp/classic-hist.json`
   b. `execute-read` `GET /api/v1/market-data/instruments/rates` with query `instrumentIds=<comma buy ids>` → `/tmp/classic-rates.json` (note the ISO time it returned)
   c. `get-my-positions-and-orders` → `/tmp/classic-orders.json` (run it LAST, right before step 2: its `timestamp` must be ≤ 60 s old)
2. `cd /workspace && ./screener-venv/bin/python -m classic_rsi.pre_buy --history-response /tmp/classic-hist.json --rates-response /tmp/classic-rates.json --orders-response /tmp/classic-orders.json --instrument-ids <comma buy ids> --rates-read-at <ISO time of read b>`
   - exit 0 required, else no buy this run. Fails closed on any error/empty/unparseable read, a history page that doesn't cover today, or an orders read older than 60 s.
   - writes `state/trading-history-today.json`, `state/instrument-open.json` (isOpen = last quote ≤ 300 s old and bid/ask > 0) and `state/prebuy-state.json`.
   - daily count = unmarked reservations + |placed positionIds ∪ positions opened today (book + history) ∪ today's pending (unfilled) orders|.
   - releases unmarked reservations older than 30 min ONLY if there's no pending order for that instrumentId and no position/trade for it opened after the reservation (otherwise it stays reserved with `release_blocked`).
3. Within 5 minutes: `execute_pass` (it refuses with `PRE_BUY_NOT_FRESH` if prebuy-state is missing, > 5 min old or incomplete, and `BOOK_NOT_FRESH_FOR_COUNT` if the book is > 60 s old). Pass `--instrument-open` from the printed `instrument_open_flags`. Then order-QA → place → `trade_counter mark --reservation <ID> --position-id <POS>` (or `release --reservation <ID> --reason ...` on failure).
- Never run production with `CLASSIC_EXEC_TEST_ROOT` set: test-mode results are labelled `test_mode`, `placeable=false`, the CLI exits 3, and auto_1h envelopes get a `TEST_MODE` hard flag.

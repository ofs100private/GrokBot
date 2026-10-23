---
name: Classic RSI four-level 1H
description: >-
  use this when running Classic-only 1H RSI four-level entries (Over
  Buy/Resistance/Support/Over Sold) with ATR equity stops, long-only remap,
  confirmed close, cash-floor sizing (cut size or fewer symbols),
  sell-before-buy check, cost/benefit gate, and FULL AUTO place after run-QA +
  order-QA PASS on OfersClaw5-PRIYN (no Ofer chat auth, no daily trade cap since
  fix14 2026-10-23, no new-name cap, cash floor 1% of equity, after the SPY+QQQ
  55% core) — 24x5 equities only (crypto removed 2026-10-17), SL 2.5×ATR / TP
  2R, TP+SL required; Fear is a dip window, never Momentum
---
# Classic RSI four-level entries (1H)

## Standing rules update — fix14, Ofer 2026-10-23 13:01 / 13:03 / 13:09 / 13:21 / 13:53 / 13:55 IDT (live engine via QA package `fix14b-live-rule-release-20261023`; supersedes ANY conflicting text below)
- **Cash floor = 1% of total agent equity** (`classic_rsi.floor.CASH_FLOOR_PCT = 0.01`, ≈$72 at equity $7.2k; config sha pin kept; the old $1,500 copy-mirror floor is retired, mirror $ figures are reporting only). Deployable = cash − floor; no extra $110 core buffer.
- **No daily trade cap.** The trade count comes only from the strategy plan (targets, caps, floor, cost gate, QA). `trade_counter` still records every new open (audit/log only) and never blocks; no `DAILY_TRADE_LIMIT` / `DAILY_BUDGET_USED`.
- **XLE no-add block lifted** (no `NO_XLE_ADDS`). The ONLY symbol hard block is the cross-book overlap with Momentum (`CROSS_BOOK_OVERLAP`, unchanged): never hold/buy the same symbol in Classic and Momentum ("don't trade double between the accounts").
- **Core = SPY + QQQ at 55% of total equity COMBINED — a TARGET, not binding** (Ofer 13:53 IDT; each ETF ≤ 35%, that cap is unchanged and binding), **SL and TP on every core lot**: SL −11% / TP +25% from entry (`classic_rsi.levels.CORE_SL_PCT` / `CORE_TP_PCT`; **confirmed by Ofer 2026-10-23 13:55 IDT**). Core buys are sized toward 55% and sized DOWN to it, never blocked; above 55% is only a soft flag (`CORE_WEIGHT_ABOVE_55PCT` in the run / card / pack), never a blocker and never a forced trim. The same combined-core soft flag is computed on EVERY SPY/QQQ buy path (RSI, rebalance, rotation, core). SL/TP on existing core lots (SPY 3609495243 / 3611616761) are never removed or loosened.
- **QQQ core re-buy released:** the daily rebalance re-buys QQQ up to 55% − SPY (minus a 0.25 pp cost buffer) after cost gate + order-QA. Trigger #3 (close < 50DMA with RS3M < 0) only FLAGS a core leg (`TRIGGER3_50DMA_NEG_RS3M`), never blocks it and **never sells a SPY/QQQ core lot**: execute_pass hard-refuses any trigger-3 sell of a core lot (`CORE_TRIGGER3_FLAG_ONLY`); trigger 3 exits apply to non-core holdings only.
- **GO version:** `classic_rsi/execute_pass.py` **v16.12 fix14** (`execute-pass-v16.12-rule-release-20261023-fix14`), sha256 `1fa6ffdd75c3a8699c99d8997bf61bd5d8a00c30bfb832cff6bf105700230bc5`.

- **This skill (fix14):** auto_1h has no daily-limit soft gate; RSI satellites use only cash left above the 1% floor after the 55% core. Satellite levels stay SL 2.5×ATR / TP 2R.

## Standing rules update — Ofer 2026-10-17 18:44 IDT (supersedes the 2026-10-16 crypto text and any conflicting text below)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Standing rules update — Ofer 2026-10-17 18:44 IDT (supersedes the 2026-10-16 crypto text and any conflicting text below)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

- **This skill:** auto_1h scans equities only (no `CRYPTO_UNIVERSE`, no crypto ids). On weekends/holidays there are no buy packs at all (risk-off notes only). Pack levels are SL 2.5×ATR / TP 5×ATR (2R); `rebase_levels` re-bases them on the anchor ask with the same multiples. The old SL 1.5×ATR / TP 2.0×ATR text below is superseded.

## Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

**Classic only** (Classic account (OfersClaw5-PRIYN) / Trader_Classic). Do **not** use on Momentum.

Implements the four-level RSI zone model on **1-hour** bars with **ATR equity stops**, **confirmed candle close only**, and **long-only** remapping. Code: `/workspace/classic_rsi/`.

## Standing policy — FULL AUTO (Ofer 2026-10-11)

**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place ON — Ofer accepted QA's residual risks 2026-10-16 01:27 IDT (see standing rules update).

- **Every `classic-rsi-1h-auto` run (every 3 hours weekdays) searches for a new opportunity.** If a valid buy pack exists, passes [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) and [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate), passes the **cost/benefit gate**, and free cash after the buy stays ≥ the agent floor (1% of equity) (cut size or the number of names rather than breach), **Trader_Classic places it automatically** — no chat authorization from Ofer or CoS.
- **No opportunity → do nothing** (the run is still logged and run-QA'd).
- **No daily trade cap** (fix14: the strategy plan sets the trade count; the counter is audit only); **no monthly new-name cap**.
- An explicit Ofer/CoS hold still blocks.

## Mandate locks (confirmed Ofer 2026-10-16 01:27 IDT; was pending since 2026-10-11)

- Long-only ×1; **no shorts** from Sell triangles
- Crypto opens only BTC/ETH/SOL ×1 (crypto sleeve ≤ 15% of total equity)
- **Cash ≥ agent floor after adds**: cash floor = 1% of total agent equity (config-pinned `python -m classic_rsi.floor`; fail closed if equity is unavailable or the config sha is wrong) (see sizing rule below); equities 24x5 (extended hours); no daily trade cap
- **Classic account truth:** Classic account (OfersClaw5-PRIYN) via `user-OfersClaw5` (execution + reporting). Parent SSO mirror `11368142` is optional copy/UI corroboration only — never required, never the rejection reason
- **QA Bot PASS** (run-QA, then order-QA) required before any place ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) or standing Classic order gate)
- **Fear is the dip window (Ofer 2026-10-04):** CNN Fear or Extreme Fear is when Support / Over Sold longs are most in play. Do **not** block a pack only because F&G is Fear or the brief says No Buy for that reason. Still block on cash floor, weekend, explicit Ofer/CoS hold, and risk-off (no add) on that same name.
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. This is the only symbol hard block (fix14 lifted the XLE no-add rule).

## Cash floor sizing (Ofer 2026-10-07)

If a buy pack would leave Classic cash **under the agent floor (1% of equity)**:
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

## Slot pre-check — first step of every classic-rsi-1h-auto slot (Ofer 2026-10-18, token saving; no trading-rule change)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Slot pre-check — first step of every classic-rsi-1h-auto slot (Ofer 2026-10-18, token saving; no trading-rule change)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

## RSI pre-scan silent exit — lever 3 (Ofer 2026-10-18 16:44 IDT; 2026-10-18g)

Step 0 of classic-rsi-1h-auto is now `precheck … --prescan`. The full rule text is canonical in [Trader Classic strategy](sand-workflow:trader-classic-strategy), section "Slot pre-check", item 5.
- The pre-scan uses this skill's code unchanged: `classic_rsi.signals.compute_signals` (zones 79.90/67.90/34.90/19.90, RSI 14, strong candle 1.2× SMA20 body, confirmed close only) over the auto_1h universe plus holdings.
- Zero entry candidates (BUY_80/BUY_70 → `CANDIDATE_LONG` on the last 3 confirmed 1H bars) and zero holding `RISK_OFF` → silent SKIP (exit 10).
- Anything else, including any data error or staleness, → the normal auto_1h run, unchanged.
- No level, gate, stop or sizing rule changed.

## 1H auto (standing)

Script: `python -m classic_rsi.auto_1h` → `/workspace/classic_rsi/audit/latest-auto.json`.

Run from `/workspace` only: `cd /workspace && ./screener-venv/bin/python -m classic_rsi.auto_1h` (never the unpatched `/workspace/GrokBot` backup copy). Book snapshot `/workspace/classic-portfolio-for-app.json` is refreshed live from user-OfersClaw5 by Trader_Classic at :12 past each hour, 16:12–22:12 IDT weekdays; if it is >30 min old, auto_1h fails closed as BOOK_SNAPSHOT_STALE (0 packs) — then refresh it live first and rerun (added 2026-10-08).

Routine **classic-rsi-1h-auto**: weekdays every 3 hours `CRON_TZ=Asia/Jerusalem 35 */3 * * 1-5` (Ofer 2026-10-16 01:27 IDT). Equities trade inside the 24x5 extended-hours window; BTC/ETH/SOL 24/7. Soft-gate when the equity window is closed (weekend/holiday); crypto may still scan. Pre-buy refresh (`classic_rsi.pre_buy`) is mandatory before any buy GO. The script self-gates by window.

- **Universe (no fixed symbol list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ ~$100M, price ≥ $10) → rising confirmed 1H volume (last vol > SMA20 × 1.2) → top ~50 ∪ live Classic book. Screener: `classic_rsi/universe.py`. Envelope carries `universe_meta` (pool/liquid/rising counts, thresholds, fallback flag). Cache fallback: `audit/universe-latest.json` — never silently use the old fixed 6-name list as primary.
- The `auto_1h` **script** proposes only (envelope keeps `do_not_place=true` / `place=false`: the script itself never calls eToro). **Trader_Classic** places via `user-OfersClaw5` after the gates below — that is the FULL AUTO path, not the script
- Soft gates: equity window closed (weekend/holiday outside 24x5) / cash floor → `GATED` (buys suppressed). No daily trade-limit gate (fix14). Fear / brief No-Buy-from-Fear is **not** a soft gate.
- **Every run** → QA Bot [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa) citing `run_id` (0 packs and GATED still validated). A slot the pre-check SKIPs (exit 10) produces no run, so it has no run-QA; its audit line is the record.
- On run-QA **FAIL** → QA messages Trader_Classic to **rerun** `auto_1h` (max 2/hour) → re-validate new `run_id`
- On run-QA **PASS** with packs → Trader_Classic (cash/sleeve/sell-first check/explicit hold; Fear = dip, not a block; cut size or drop names to keep cash ≥ agent floor = 1% of equity) → prepare → cost/benefit gate → [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) → **auto place on PASS** (no Ofer chat auth) → fill audit
- On run-QA **PASS** with 0 packs → do nothing; the run log is the record

## Automation flow (manual or auto)

1. `auto_1h` or `propose` on confirmed 1H bars
2. Mandate filter — RSI cannot override cash, weekend, or an explicit hold. It **should** be used in Fear.
3. Sell/rotate check + size so cash-after ≥ agent floor (1% of equity)
4. QA Bot **run QA** with `run_id` (FAIL → Classic rerun → re-QA)
5. If packs remain after run PASS → pre-buy refresh → prepare → `prepare_token split` → cost/benefit gate → order QA → **auto place after PASS** → `prepare_token wipe` (no Ofer chat auth; no daily trade cap; no monthly new-name cap)
6. Post-fill audit

## execute_pass GO pin + prepare/place token handling (fix11, deployed 2026-10-21 19:17 IDT; pin updated by fix14)

- **GO version:** `classic_rsi/execute_pass.py` **v16.12 fix14** (`execute-pass-v16.12-rule-release-20261023-fix14`, package 1.1.7), sha256 `1fa6ffdd75c3a8699c99d8997bf61bd5d8a00c30bfb832cff6bf105700230bc5`. Any other sha is not the QA GO version → NO-GO. The daily `build_daily.py` `EP_OK` pins the same sha.
- **Cash floor:** always the config-pinned floor (`python -m classic_rsi.floor`, or `resolve(expected_sha256=<pinned config sha>)`; a bare `resolve()` is not config-pinned) (= execute_pass `cash_floor.agent_floor_usd` = 1% of total equity); never `floor_now()` or a hard-coded number.
- **After every `prepare-trade` / `prepare-close`** (saved with write_to_file): `cd /workspace && ./screener-venv/bin/python -m classic_rsi.prepare_token split --response <raw> --stripped-out <pack-dir>/prepare-tokenstripped.json --token-out /tmp/<unique>-token`. It accepts `token` or `confirmationToken`, writes the token-free copy to disk first, writes the token ONLY to a 0600 file, deletes the raw read and prints metadata only. Exit 2 (`PREPARE_TOKEN_MISSING` / `AMBIGUOUS` / `INVALID` / `NOT_READY` / `VALUE_LEAK`) = do not place; re-prepare. Never read the token field by hand and never print it. Build live.json / execute_pass inputs from the stripped copy only.
- **Place:** one `place-trade` / `place-close` call with `token = "$file:/tmp/<unique>-token"`. Then ALWAYS `./screener-venv/bin/python -m classic_rsi.prepare_token wipe --token-out /tmp/<unique>-token` (after a fill, a failure or an abandon), and save the place result with `prepare_token strip --response <raw> --out <pack-dir>/place-result.json`. Before any re-place, live-read to check whether the first place already went through.
- **Deploy / rollback of classic_rsi packages:** `apply_fixNN.sh` (check only) → `--apply --external`; roll back ALWAYS with `--rollback <backup-dir> --external` (without `--external` the external scripts stay on the new code and fail on import).

## Documentation (every run, every movement)

- Every run: `run_id` audit JSON + `index.jsonl` row (written by `auto_1h`), run-QA verdict file, and a Job-Runs note (0 packs / GATED / PROPOSE, and the action taken or "no opportunity — no action").
- Every place or skip: pack with `run_id`, `cost_gate` block, order-QA verdict reference, prepare snapshot, fill vs prepare, fees, cash after — appended to the audit trail and Job-Runs note.

## Pre-buy refresh — run before EVERY buy GO (QA fix3 2026-10-16)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Pre-buy refresh — run before EVERY buy GO (QA fix3 2026-10-16)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Shared book snapshot + cards (Ofer 2026-10-18c; token saver)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

**Slot usage:** for the step-0 pre-check, run `books.snapshot fresh --book classic --max-age-min 15`. On exit 0 run `python3 -m classic_rsi.precheck --from-books`. On exit 2 do the hinted user-OfersClaw5 read, `ingest` it, then run `--from-books`. `--live-json <raw>` still works, and precheck fails open if the snapshot is unusable. The book-refresh read should also be `ingest`ed (its `classic-portfolio-for-app.json` writer is unchanged). **execute_pass GO gates still take their own ≤60 s / ≤120 s live reads. The snapshot never replaces them.**

## Book refresh = one script (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only; no trading-rule change)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Book refresh = one script (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only; no trading-rule change)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

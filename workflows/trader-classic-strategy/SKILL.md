---
name: Trader Classic strategy
description: >-
  Use this when planning, reviewing, or executing Trader_Classic trades on
  OfersClaw5-PRIYN (keys execution) — any fitting liquid large-cap/ETF, SPX
  heatmap Change 1D URL, cross-regime diversification, beat-SPX after fees/tax,
  hard mandate rules, Fear-as-dip window, cash-floor sizing, sell-before-buy
  check, cost/benefit gate, FULL AUTO place after QA PASS (no Ofer chat auth,
  max 4 new trades/day (2026-10-16), no new-name cap, daily rebalance since 2026-10-11), full run/trade
  audit, and post-trade self-improvement.
---
# Trader Classic strategy

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


Standing playbook for **Trader_Classic** on the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY).

**Objective:** beat **S&P 500** on a **net** basis (after eToro fees/spreads/overnight, realized P&L, and estimated tax drag). Prefer fewer high-quality longs over churn — keep the book **diversified enough to earn across regimes**.

**Naming (Ofer 2026-10-06):** **Classic account** = OfersClaw5-PRIYN agent account (keys MCP `user-OfersClaw5`). Use the phrase **Classic account (OfersClaw5-PRIYN)** going forward. Stop calling it keys-B or ledger B for Classic.

**Source of truth (Ofer 2026-10-06):** Classic **execution, cash gating, prepare/place, order-QA, AND portfolio reporting** (equity/cash/positions on cards, App, briefs, QA data gates) come from the **Classic account (OfersClaw5-PRIYN)** via MCP `user-OfersClaw5`. Do **not** reject OfersClaw5 keys figures as Classic. Parent SSO mirror `11368142` is only the copy/UI view — optional corroboration, never required, never the rejection reason. `prepare-trade` / `place-trade` run on the Classic account.

## Standing policy — FULL AUTO (Ofer 2026-10-11)

**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place ON — Ofer accepted QA's residual risks 2026-10-16 01:27 IDT (see standing rules update).

- **Look for a new opportunity every run** (`classic-rsi-1h-auto` every 3 hours weekdays `CRON_TZ=Asia/Jerusalem 35 */3 * * 1-5`, plus the daily rebalance check). If a valid pack exists, it passes run-QA ([Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa)) and order-QA ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate)), passes the **cost/benefit gate**, and cash after stays ≥ ~$1,500, then **Trader_Classic places automatically — no chat authorization from Ofer or CoS**.
- **No opportunity → do nothing** (log the run).
- **Rebalance is DAILY** (weekdays), not weekly — see [Classic rebalance](sand-workflow:classic-rebalance). Daily trims/rotations/sells/adds are also full auto after QA PASS + cost gate.
- **Max 4 NEW trades per IDT calendar day** across all Classic runners; **no monthly new-name cap**.
- **Every run and every movement is documented** (see Documentation).

## Mandate (confirmed Ofer 2026-10-16 01:27 IDT; was pending since 2026-10-11)

- Long-only, leverage **×1**; crypto only BTC/ETH/SOL ×1 (crypto sleeve ≤ 15%)
- Prefer large liquid US companies / sector ETFs, then commodities
- Prefer leaving cash uninvested; never all-in; cash floor ~$1,500
- Name caps 35% fund/ETF / 20% single stock of **total equity**; growth/sleeve cap 45% of **total equity** (not invested capital; check cost and market-value numerators over total equity — Ofer 2026-10-12 17:56 IDT); stops per [Classic rebalance](sand-workflow:classic-rebalance)
- **Floor-vs-cap exit precedence undecided** (Ofer): any exit pack that depends on choosing cash-floor vs cap-breach first is **held** until Ofer decides
- REAL only; QA PASS + cost gate → auto place → fill audit → CoS
- No place under an explicit Ofer/CoS HOLD; QA PASS is mandatory before every place
- Weekend: no new equity size (crypto majors trade 24/7)
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either.

## Cost/benefit gate (mandatory before every place — Ofer 2026-10-11)

Before every buy, sell, trim, or rotation, estimate the round-trip cost against the expected gain:
- **Costs:** eToro spread/fees (prepare/getCost), any closing fee, overnight/financing for the planned hold, realized PnL and tax impact when selling a winner.
- **Expected gain:** distance to TP and the ATR-based expected move (haircut for probability); for rotations, the replacement's edge minus both legs' costs and tax.
- **Rule:** place only if `expected_gain ≥ 2 × total_cost` and the expected net gain is clearly positive. Else skip and log `COST_GATE_SKIP`. Hard risk exits (stops) still execute; numbers still recorded.
- Put the `cost_gate` numbers in the pack/audit; order-QA must verify them.

## Documentation (every run, every movement)

Follow the existing audit conventions and add the cost-gate numbers: `run_id` audit JSON + `index.jsonl` (`/workspace/classic_rsi/audit/`), run-QA and order-QA verdict files, Job-Runs notes for every run (including "no opportunity — no action" and skips), and for every place: prepare snapshot, `cost_gate` block, QA verdict ref, fill vs prepare, fees, cash after. Daily rebalance runs also write the daily run log per [Classic rebalance](sand-workflow:classic-rebalance).

## Cash floor sizing (Ofer 2026-10-07; confirmed 2026-10-16 — floor ~$1,500)

**Hard preference:** leave **~$1,500+** residual cash on the Classic account after any buy batch.

If a proposed pack would leave cash **below ~$1,500**:
1. **Lower** each trade’s notional, and/or
2. **Buy fewer symbols** (keep the best sleeve-fit / highest-conviction names),
3. Re-check cash-after ≥ floor, then prepare / order-QA.

Do **not** propose a floor override unless Ofer **explicitly** sizes knowing cash will go under ~$1.5k. Never auto-place a pack that breaches the floor without that explicit override.

## Sell / rotate before buy (Ofer 2026-10-07; confirmed 2026-10-16)

**Before every new buy pack**, check whether it is better to **sell or rotate** a weak holding first:
- Names near stop, thesis broken, sleeve overcrowded, or clearly weaker than the candidate
- Freeing cash by closing first can fund the buy without breaching the floor
- Report the sell-first vs buy-only choice in the prepare/handoff notes to CoS

If a clean sell/rotation is better, prepare the close (and order-QA) **before** or sequenced ahead of the new buys.

## Fear is the dip window (Ofer 2026-10-04)

When CNN Fear & Greed is **Fear or Extreme Fear**, that is the **best time to look for the dip** — not a reason to sit out.

- Hunt quality liquid longs on **confirmed weakness** (RSI Support / Over Sold, beaten large-caps and gap sleeves). Do not chase names already extended (RSI Over Buy / risk-off on that name).
- A daily_brief **No Buy Today** that exists only because F&G is Fear does **not** block this search. Do not re-ask Ofer for a Fear override.
- Still required: ×1 long-only, crypto majors only, equity weekend freeze (crypto 24/7), max 4 new trades/day, sleeve caps, QA PASS before place. Size smaller into Extreme Fear; leave a cash buffer when possible.
- Explicit Ofer hold, event-vol freeze, and cash-insufficient fails still block. Fear alone does not.

## Universe

Named tickers are **examples only** — trade **any** fitting liquid large-cap/ETF after research.

## Diversification

Sleeves: growth/tech · industrial · healthcare/pharma · hard assets · cash. Caps (Ofer 2026-10-12 17:56 IDT): name ≤ 35% of **total equity** (fund/ETF) or ≤ 20% (single stock); crypto sleeve ≤ 15%; growth sleeve (and any sleeve) ≤ 45% of **total equity** — not % of invested capital; measure with both cost and market-value numerators over total equity. Prefer gap sleeves. In Fear, prefer the sleeve that is actually on sale, not another add to an extended winner.

## Research loop

1. Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`) snapshot (+ optional mirror `11368142` copy view) + sleeve weights
2. **Sell/rotate check** (see above) before proposing new buys
3. **SPX heatmap (1D):** open  
   `https://www.tradingview.com/heatmap/stock/#%7B%22dataSource%22%3A%22SPX500%22%2C%22blockColor%22%3A%22change%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22grouping%22%3A%22sector%22%7D`  
   Confirm UI label **Change 1D, %** (blockColor `change`). Not 1h (`change|60`). If tiles blank/rate-limited → eToro batch quotes + sector ETFs
4. Rel performance vs SPX/QQQ; beat SPX after costs
5. X Tier-1 (small cost; X MCP guide first)
6. Event calendar (~48h CPI/FOMC/NFP)
7. Timing overlay: [Classic RSI four-level 1H](sand-workflow:classic-rsi-four-level-1h) (`/workspace/classic_rsi/`) — Buy = long timing, Sell = risk-off only; ATR SL/TP; confirmed 1H close. **In Fear, Support/Over Sold buys are the dip.** RSI still does not bypass weekend or an explicit hold.
8. Size so cash-after ≥ ~$1.5k (cut notional or drop symbols first)
9. prepare on **Classic account** (`user-OfersClaw5`) — fees + tax haircut
10. Read latest **KEEP / AVOID** from [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop) before proposing size
11. **Cost/benefit gate** (above) — skip if net expected gain is not clearly positive
12. Order-QA PASS → **auto place** (no Ofer chat auth) → fill audit → CoS

## After every fill / skip / QA FAIL

Run [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop): score Q/A/order/market/X/brief/graph/outcome; write KEEP/AVOID; patch this playbook only when a hard avoid repeats.

## Beat-SPX filter / regimes / daily checklist / pre-trade / events

Hold cash if the dip is not clean; event-vol freeze; in Fear lean into quality dips (healthcare, hard assets, and beaten large-caps) rather than a blanket no-buy; risk-on small liquid adds after QA; NVDA no-add default; any fit symbol when the dip is real.

## Do not

Non-major crypto/shorts/lev>1; buys without TP; exclusive ticker lists; break caps; chase parabolic into event-vol; treat high Fear as an automatic no-buy; ignore fees/tax; duplicate pending closes; place without QA PASS or without a passing, recorded cost/benefit gate; churn trades whose expected gain does not clearly beat round-trip cost + tax; use 1h heatmap when 1D was set; treat RSI Sell tags as shorts; prepare on parent SSO expecting a `mirrorId` (parent cannot target the copy); auto-place packs that leave cash under ~$1.5k without Ofer’s explicit override; skip the sell/rotate check before new buys; buy a symbol held in Momentum (mirror 11630170) — cross-book no-overlap.

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

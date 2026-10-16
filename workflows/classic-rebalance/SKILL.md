---
name: Classic rebalance
description: >-
  use this when running the daily (weekday) rebalance check or monthly full
  rebalance of the Classic account (OfersClaw5-PRIYN via user-OfersClaw5), or
  when a drift trigger fires (name >35% ETF / >20% stock of total equity, sleeve >45%, cash <$1.5k or
  >50% of equity, holding below 50DMA with negative 3M RS, or a trailing stop) —
  sell/rotate before buy, size to target weights, RSI 1H only as entry timing,
  cost/benefit gate, then FULL AUTO place after QA PASS (no Ofer chat auth,
  max 4 new trades/day since 2026-10-16; no new-name cap)
---
# Classic rebalance

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


Applies only to the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY). It composes with [Trader Classic strategy](sand-workflow:trader-classic-strategy) (mandate), [Classic RSI four-level 1H](sand-workflow:classic-rsi-four-level-1h) (timing only), and [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop).

**Why this exists (review 2026-10-08):** the account was −26.75% vs SPY +9.6% from 04-30 to 10-07. 121 closes lost −$2,765 fully loaded. Holds under 7 days caused −$1,951 of that (71%); holds of 30 days or more were about flat; the long-held core (SMH, QQQ, XLV) is all positive. Lesson: **fewer, longer, trend-aligned positions at target weights.** With max 4 new trades/IDT day (2026-10-16) and no monthly new-name cap, the **cost/benefit gate** below is what stops churn.

## Standing policy (Ofer 2026-10-11)
**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place ON — Ofer accepted QA's residual risks 2026-10-16 01:27 IDT (see standing rules update).
- **FULL AUTO**. Daily rebalance actions (trims, rotations, sells, adds) are placed by Trader_Classic automatically once the pack passes the [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) **and** the cost/benefit gate. No chat authorization from Ofer or CoS is needed. If nothing passes, do nothing (still log the run).
- **Cadence moved from weekly to DAILY** (weekdays).
- **Max 4 NEW trades per IDT calendar day**; **no monthly new-name cap** (the old "≤2 new names per month" rule is removed).
- **Every run and every movement is documented** (see Documentation).
- An explicit Ofer/CoS hold still blocks.

## Mandate locks — confirmed Ofer 2026-10-16 01:27 IDT
Confirmed (was pending since 2026-10-11): long ×1 only; crypto only BTC/ETH/SOL (watch for eToro traps: `CVX` = Convex, use `CVX.US` id 1014; `T` and `DIA` are crypto tokens); liquid large caps and sector ETFs, then commodity ETFs; cash ≥ ~$1,500 after any batch (cut size or drop names rather than breach); name caps (35% fund/ETF / 20% single stock of **total equity**) and the 45% sleeve/growth cap (of **total equity**, not invested); crypto sleeve ≤ 15%; stops (drift triggers 3–5); sell/rotate-before-buy check; equities 24x5 (no new equity size outside that window / weekends); crypto 24/7; **QA PASS is mandatory before every place.** **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either.

## Cadence
| When | What | Output |
|---|---|---|
| **Daily**, each US weekday after the close (IDT evening) | Rebalance check: weights, drift flags, sell-rule flags, RS table, account vs SPY (1D/1W/1M/since 04-30). Any trigger or rotation that passes → pack → QA → cost gate → auto place | Daily report + run log. No orders when nothing triggers or nothing passes the cost gate. |
| **Monthly**, first full US trading week | Full rebalance: score, set target weights, packs (sells first) → QA → cost gate → auto place | Rebalance memo plus packs and run log |
| **Ad hoc** | Any drift trigger, or a hard sell rule on a confirmed daily close | Pack for the affected name only → QA → cost gate → auto place |

## Targets and caps (confirmed Ofer 2026-10-16 01:27 IDT)
- Invested sleeves: growth/tech · healthcare · industrials/financials · energy/hard assets · broad core (SPY/RSP). Cash is its own sleeve.
- **Caps are % of TOTAL EQUITY, not invested capital** (Ofer 2026-10-12 17:56 IDT): name ≤ 35% of total equity (fund/ETF) or ≤ 20% (single stock); crypto sleeve ≤ 15%; growth sleeve (and any sleeve) ≤ 45% of total equity. Check **both** cost and market-value numerators over total equity — a breach on either counts.
- Cash: floor $1,500. If cash is above 50% of equity and passing candidates exist, deploy toward target. If nothing passes, park it in SPY rather than sit idle (only if SPY passes the cost gate).
- **Floor-vs-cap exit precedence undecided** (Ofer): when cash-floor and cap-breach exits conflict, do **not** auto-pick an order. Any exit pack that depends on that precedence is **held** until Ofer decides.
- **No new-name cap; max 4 NEW trades per IDT day** (Ofer 2026-10-16). Minimum position $400 (smaller positions are not worth the fees).

## Drift triggers (any one starts an ad-hoc rebalance)
1. A name above 35% of **total equity** (fund/ETF) or 20% (single stock), crypto sleeve above 15%, or a sleeve (incl. growth) above 45% of **total equity** — using either cost or market-value over total equity.
2. Cash below $1,500, or above 50% of equity.
3. A holding has a **confirmed daily close below its 50DMA AND negative 3M RS** vs SPY.
4. A holding has a confirmed daily close below its 200DMA.
5. A trailing stop is hit: ETFs ~8% below the high since entry; single stocks ~10–12%, or 2.5–3× daily ATR(14), whichever is wider.

## Step 0: Build scores (run FIRST)
`cd /workspace && python3 -m classic_rsi.scorer` (writes classic_rsi scores-latest.json + .sha256 sidecar; execute_pass fails closed SCORES_UNVERIFIED if missing/stale/mismatched).

## Step 1: Snapshot (live)
Portfolio summary on the Classic keys connector gives equity, cash, and positions. Compute name % and sleeve % of **total equity** (both cost/equity and market-value/equity), and cash % of equity. Do **not** use invested capital as the cap denominator. Trading history gives closes since the last run (for the report).

## Step 2: Score (daily bars, last confirmed close)
For each holding and each candidate (sector ETFs XLK/XLV/XLF/XLI/XLE/XLP/XLU/XLB/XLY/XLC, SPY/RSP/QQQ/SMH, GLD/IAU/SLV, plus liquid large caps with ADV ≥ $100M):
- Returns over 1M (21d), 3M (63d), 6M (126d). **RS = return minus SPY return** over the same window.
- **Trend OK:** close above the 50DMA, close above the 200DMA, and 50DMA above 200DMA.
- **Score = 0.5×RS3M + 0.5×RS6M.** Also record drawdown from the 52-week high and 63-day vol.
- Data: eToro daily candles via the read route, or Yahoo (yfinance); label the source. Cross-check SPY's last close against eToro.

## Step 3: Sell / rotate first (always before any buy)
- A hard sell rule (trigger 3, 4, or 5) means a close or trim. Stops are risk exits: still record the cost numbers, but a stop exit is not skipped by the cost gate.
- Cap breach: trim back to target.
- **Rotation:** replace a holding only if the candidate passes the trend filter, scores at least **5 pp** higher, fits the caps, **and** the rotation passes the cost/benefit gate (both legs' costs plus tax on the realized gain).
- Do **not** close a position only to reconcile a ledger without a thesis check (example: CVX.US −$78.67 on 10-06).
- Include the realized gain or loss and the tax estimate in the memo and audit.

## Step 4: Buy list and sizing
- Only trend-OK names with positive 3M RS, preferring gap sleeves. **Fear = dip window** means a pullback in a trend-OK name (above its 200DMA). It does **not** mean buying a sector below its 50/200DMA (the September rotations into CAT/XLI/CVX/XOM/NEM/GE lost −$304 with 0 wins).
- Size to target weights. Re-check cash after the batch is ≥ $1.5k; if not, cut notional or drop the weakest name.
- Do not chase: if a candidate is up more than 2% on the day, stage it (half now, half on the next RSI Support or a red day) or wait.

## Step 5: RSI 1H as timing only
- RSI Buy packs are allowed **only** for names on the current target/add list or that pass Step 2.
- **Re-base SL/TP on the fill price.** Skip the pack if live price is more than 0.5×ATR(1H) away from the signal bar close. (On 10-07, ADBE reward:risk fell to 0.31 and GS to 0.17 because of stale levels.)
- No fixed 2.0×ATR(1H) TP on core adds. Use the trailing stop from drift trigger 5 and a planned hold of at least 20 trading days.
- No 1H-ATR initial stops on swing positions (SPCX −1.9%, RBRK −2.3%, CAT −1.56% were all hit within about 1 day).
- RSI Sell tags mean no add on that name. They never trigger a short, and they are never a standalone sell.

## Step 6: Cost/benefit gate (mandatory before every place — Ofer 2026-10-11)
Applies to every buy, sell, trim, and rotation. For each action compute and record:
- **Costs:** eToro spread (from prepare/getCost or live bid/ask), any opening/closing fee, overnight/financing for the planned hold, and for sells the **realized PnL and estimated tax** on a winner (round trip = open + close costs).
- **Expected gain:** for buys/adds, distance to TP (or target weight path) and the ATR-based expected move over the planned hold (daily ATR(14) × √hold days, haircut for probability); for trims/rotations, the score/RS edge of the replacement or the risk reduced, minus tax drag.
- **Rule:** place only if `expected_net_gain = expected_gain − total_cost` is clearly positive, i.e. `expected_gain ≥ 2 × total_cost` **and** `expected_net_gain > 0` by more than the cost itself. Otherwise **skip** and log `COST_GATE_SKIP` with the numbers.
- **Exception:** hard risk exits (stops, trigger 3/4, cap breach above the hard cap, cash below floor) are not skipped by the cost gate, but the numbers are still recorded.
- Record `cost_gate: {spread, fees, overnight, realized_pnl, tax_est, total_cost, expected_gain, expected_net_gain, ratio, method, verdict}` in the audit and hand it to QA.

## Step 7: Execution flow (FULL AUTO, no shortcuts)
1. Analyst memo / daily report (scores, proposed trades, cash after, sleeves after, fees and tax estimate, cost-gate numbers).
2. Trader_Classic prepares closes and trades on `user-OfersClaw5` (sells sequenced first).
3. Cost/benefit gate (Step 6) per action; drop failures.
4. QA Bot runs [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) and must PASS each pack, including the cost-gate numbers.
5. On PASS, Trader_Classic places automatically, one call per PASSed pack (no Ofer/CoS chat authorization needed since 2026-10-11). Re-check cash ≥ ~$1.5k between sequenced places. An explicit Ofer/CoS hold still blocks.
6. Fill audit to QA, then report to CoS (and Ofer on fills).
7. Run the self-improvement loop (KEEP/AVOID).

## Documentation (every run, every movement)
- Every daily/monthly/ad-hoc run writes a run log `/workspace/classic-rebalance/daily/<YYYY-MM-DD>-daily-check.md` (monthly: `.../monthly/<YYYY-MM>-rebalance.md`) with the report, actions taken or "no action", and the reason.
- Every pack and place follows the existing audit conventions: run_id audit JSON, append-only `index.jsonl`, QA verdict files, and a Job-Runs note. Add the `cost_gate` block and the order-QA verdict reference to each.
- Skipped actions (cost gate, cap, cash floor, QA FAIL) are logged too, with numbers.

## Step 8: Reporting templates
**Daily:**
```
Classic daily | <date IDT> | equity $ | cash $ (x% eq) | vs SPY 1D/1W/1M/since 04-30
Weights: SYM x% (sleeve) … | Growth x% | flags: <none | trigger #>
RS top/bottom: … | Actions: none | <side sym $ — QA PASS, cost ratio x.x, placed/skipped>
```
**Monthly memo:** before/after weight table, trades ($, realized P&L, fees, tax est., cost-gate ratio), scores, rejected candidates with the reason, and data sources.

## Do not
- Trade outside the daily/monthly cadence except on a trigger (the hourly RSI auto follows its own skill).
- Add a new name without the sell/rotate check first.
- Buy trend-failing sectors because they are "cheap".
- Use leverage above ×1, crypto other than BTC/ETH/SOL, a buy without TP, or bare `CVX`/`T`/`DIA`.
- Place without QA PASS or without a passing, recorded cost/benefit gate.
- Place a batch that leaves cash under ~$1,500.
- Buy a symbol held in Momentum (mirror 11630170) — cross-book no-overlap (`CROSS_BOOK_OVERLAP`).
- Invent expected returns: the cost-gate expected gain must come from TP distance / ATR math with the method recorded. Report realized vs SPY only.

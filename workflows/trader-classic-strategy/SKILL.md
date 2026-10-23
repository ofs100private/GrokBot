---
name: Trader Classic strategy
description: >-
  Use this when planning, reviewing, or executing Trader_Classic trades on
  OfersClaw5-PRIYN (keys execution) — any fitting liquid large-cap/ETF, SPX
  heatmap Change 1D URL, cross-regime diversification, beat-SPX after fees/tax,
  hard mandate rules, Fear-as-dip window, cash-floor sizing, sell-before-buy
  check, cost/benefit gate, FULL AUTO place after QA PASS (no Ofer chat auth, no
  daily trade cap (fix14: trade count from the strategy plan), no new-name cap,
  daily rebalance since 2026-10-11), full run/trade audit, and post-trade
  self-improvement. Since fix14 (2026-10-23): SPY+QQQ core 55% combined target
  (not binding) with SL/TP, cash floor 1% of equity, cross-book the only symbol
  block; equity-only RSI dip-buys (SL 2.5xATR / TP 2R); crypto removed.
---
# Trader Classic strategy

## Standing rules update — fix14, Ofer 2026-10-23 13:01 / 13:03 / 13:09 / 13:21 / 13:53 / 13:55 IDT (live engine via QA package `fix14b-live-rule-release-20261023`; supersedes ANY conflicting text below)
- **Cash floor = 1% of total agent equity** (`classic_rsi.floor.CASH_FLOOR_PCT = 0.01`, ≈$72 at equity $7.2k; config sha pin kept; the old $1,500 copy-mirror floor is retired, mirror $ figures are reporting only). Deployable = cash − floor; no extra $110 core buffer.
- **No daily trade cap.** The trade count comes only from the strategy plan (targets, caps, floor, cost gate, QA). `trade_counter` still records every new open (audit/log only) and never blocks; no `DAILY_TRADE_LIMIT` / `DAILY_BUDGET_USED`.
- **XLE no-add block lifted** (no `NO_XLE_ADDS`). The ONLY symbol hard block is the cross-book overlap with Momentum (`CROSS_BOOK_OVERLAP`, unchanged): never hold/buy the same symbol in Classic and Momentum ("don't trade double between the accounts").
- **Core = SPY + QQQ at 55% of total equity COMBINED — a TARGET, not binding** (Ofer 13:53 IDT; each ETF ≤ 35%, that cap is unchanged and binding), **SL and TP on every core lot**: SL −11% / TP +25% from entry (`classic_rsi.levels.CORE_SL_PCT` / `CORE_TP_PCT`; **confirmed by Ofer 2026-10-23 13:55 IDT**). Core buys are sized toward 55% and sized DOWN to it, never blocked; above 55% is only a soft flag (`CORE_WEIGHT_ABOVE_55PCT` in the run / card / pack), never a blocker and never a forced trim. The same combined-core soft flag is computed on EVERY SPY/QQQ buy path (RSI, rebalance, rotation, core). SL/TP on existing core lots (SPY 3609495243 / 3611616761) are never removed or loosened.
- **QQQ core re-buy released:** the daily rebalance re-buys QQQ up to 55% − SPY (minus a 0.25 pp cost buffer) after cost gate + order-QA. Trigger #3 (close < 50DMA with RS3M < 0) only FLAGS a core leg (`TRIGGER3_50DMA_NEG_RS3M`), never blocks it and **never sells a SPY/QQQ core lot**: execute_pass hard-refuses any trigger-3 sell of a core lot (`CORE_TRIGGER3_FLAG_ONLY`); trigger 3 exits apply to non-core holdings only.
- **GO version:** `classic_rsi/execute_pass.py` **v16.12 fix14** (`execute-pass-v16.12-rule-release-20261023-fix14`), sha256 `1fa6ffdd75c3a8699c99d8997bf61bd5d8a00c30bfb832cff6bf105700230bc5`.

## Standing rules update — Ofer 2026-10-17 18:44 IDT (supersedes the 2026-10-16 crypto text and any conflicting text below)
Source: Ofer approved the backtest recommendation (`/workspace/classic_rsi/research/backtest-20261016.md`: current rules −13% vs SPY +67% over 2.8 y; crypto lost −$1,951 on 88 trades; a SPY/QQQ core + equity dip-buys scored Sharpe ~1.4).
- **Core (strategic):** SPY + QQQ held at **55% of total equity combined** (fix14; a TARGET, not binding — Ofer 13:53 IDT), each ≤ 35% (ETF cap, binding); the planner water-fills the lighter name first. It is funded from cash above the agent floor (1% of equity) and, if needed, by funding sells (`core_rotation`). The core does not use the RSI p-registry. It **does** pass Ofer's mandatory net-positive cost/benefit rule (QA fix1 2026-10-17) through the **core gain gate** `cost_gate.evaluate_core`:
  - **Expected gain:** EG = Σ buy notional × annual drift × horizon/252 × (1 − 25% tax).
  - **Drift:** SPY 10.05% a year and QQQ 11.6% a year. That is a 50% haircut of the buy-and-hold CAGRs 20.1% / 23.2% in `/workspace/classic_rsi/research/backtest-20261016.md` (2024-01-01→2026-10-16, a bull window).
  - **Horizon:** 252 trading days (strategic hold carried through monthly rebalances). Every block reports a 21-day sensitivity.
  - **PASS iff** EG ≥ 2 × total round-trip cost (spread + fees + overnight + tax), EG − cost > 0, and cost ex-tax ≤ 0.5% of notional.
  - **core_rotation** also needs the rotation benefit = rotated notional × (core drift − sold holding's expected annual return) × horizon/252 × (1 − tax) to be greater than the sell-leg cost + realized-gain tax + the buy-leg cost share.
    - **Held return (QA fix3, 2026-10-17):** held = **max(floor, SPY drift 10.05% + registry excess)**.
      - **Floor:** the pinned conservative default (fix2), never 0: max(the holding's own half-CAGR from the backtest data, SPY-like 10.05%), or 10.05% if the holding is not in the data (`cost_gate.core_held_default`).
      - **Registry excess:** the edge registry calibrates relative strength vs SPY, so its value is an *excess-vs-SPY* return, annualised ×252/h. It only adds on top of SPY drift and never lowers the floor.
      - **Evidence selection:** the registry entry is selected by the **held symbol** (`held_symbols` contains it, exactly one match; `cost_gate.resolve_held_excess`), never by the pack's `edge_ref`/evidence_id. `evaluate_core` resolves it itself, and callers cannot pass a held return.
    - The default table is `classic_rsi/research/data/held_half_cagr-20261016.json` (500 symbols, same bh() method/window/50% haircut, built by `research/held_cagr.py`, sha256 pinned in `CORE_HELD_TABLE`).
    - Effect: rotating out of a broad or sector ETF into SPY almost always SKIPs. Closing a legacy holding to fund the core is then **Ofer's explicit decision only**: never auto-run it on the gate alone, and re-submit it as separate Ofer-authorized steps.
  - **Explicit-approval packs (QA fix3):** `execute_pass` refuses any pack with `requires_explicit_ofer_approval` (any value except literal `false`) unless an approval record kept **outside the pack** verifies, otherwise `OFER_APPROVAL_NOT_VERIFIED`:
    - **Record:** `/workspace/classic_rsi/state/ofer-approvals/<pack_id>.json` with pack_id, approved_by `Ofer`, approved_at (timezone, not in the future, ≤ 120 h old), source, and the exact legs.
    - **Legs match on:** side, symbol, instrumentId, sell positionId, units (6 dp), and buy SL/TP (2 dp).
    - Approval fields inside the pack are ignored.
    - Only the main agent writes a record, and only after Ofer's explicit message approving those exact legs.
  - **Fail-closed sources (QA fix2):** every `evaluate_core` call re-hashes the drift source `backtest-20261016.md` (and, for core_rotation, the held table). A missing file or sha256 mismatch → `CORE_DRIFT_SOURCE_*` / `CORE_HELD_TABLE_*` input error → INVALID, never PASS.
  - **core_trim** has no gain term, so it always SKIPs. A core cap breach exits through the regular trim kind as a verified risk exit.
  - Order-QA is still required. Planner: `classic_rsi/core.py` (targets cash after ≥ the 1% agent floor; no extra buffer; buys sized toward 55% minus a 0.25 pp cost buffer, never above; a core above 55% gets a soft flag, no trim).
- **Core levels (every core lot carries SL AND TP; −11% / +25% confirmed by Ofer 2026-10-23 13:55 IDT):** **SL 11% below entry** (band 10–12%; use 1% under the 200DMA only when that lands inside the band). The SL is trailed up monthly to max(SL, 11% below the highest close since entry) and never lowered. **TP +25%** (band 20–30%): a far TP, required by rule, that rarely binds; if it fills, the next monthly rebalance re-buys. R:R 2.27.
- **Core rebalance:** monthly (first US trading day) **or** when the core is > 5 pp BELOW the 55% combined target, or SPY/QQQ above its 35% cap (above 55% = soft flag only, no forced trim). execute_pass kinds: `core_add` (1 buy), `core_trim` (1 SPY/QQQ sell), `core_rotation` (1 funding sell + 1 SPY/QQQ buy; sale proceeds count toward the floor). The funding sell must be a **non-core satellite/legacy holding** (never SPY/QQQ → `CORE_FUNDING_SELL_NOT_ALLOWED`) held **≥ 20 US trading days** (`FUNDING_SELL_UNDER_MIN_HOLD`), carry a `funding_reason` (`FUNDING_REASON_MISSING`), and pass the rotation benefit test above. Each pack needs `core_reason` ∈ {initial_deploy, monthly_rebalance, drift_gt_5pp}. Blocks: `CORE_SYMBOL_REQUIRED`, `CORE_REASON_MISSING`, `SL_OUT_OF_BOUNDS` (core SL/TP bands), `TAKE_PROFIT_MISSING`, `CORE_TRIGGER3_FLAG_ONLY` (a trigger-3 sell of a core lot). Soft flag (never a blocker): `CORE_WEIGHT_ABOVE_55PCT`. Core buy legs are logged in the trade counter (no cap).
- **RSI dip-buys (satellite):** **equities only** (US stocks/ETFs). Default RSI levels (79.9/67.9/34.9/19.9) on 1H, confirmed close. **SL = entry − 2.5×ATR(1H), TP = entry + 2R (= 5×ATR)** (`LevelsConfig` 2.5/5.0). They use only cash above the agent floor (1% of equity) that is left after the core. No daily trade cap. FULL AUTO after run-QA + order-QA + the RSI cost gate (unchanged; it SKIPs while the p-registry has no qualifying out-of-sample entry).
- **Crypto REMOVED entirely (hard flag):** BTC/ETH/SOL and all crypto are blocked, by name and by id (100000/100001/100063 included): guard `INSTRUMENT_CRYPTO`, execute_pass `CRYPTO_BLOCKED`, trading window `CRYPTO_BLOCKED`. Crypto is removed from the auto_1h universe, from the crypto sleeve/15% cap logic, and from the crypto SL/cost-floor code. Weekends/holidays therefore mean **no buys at all**. A legacy crypto holding may only be sold. The **T vs T.US guard stays** (bare `T` = Threshold crypto 100528 is blocked; AT&T is `T.US` 1030).
- **Cost/benefit rule (Ofer 2026-10-11) still applies to EVERY place:** RSI buys use the p-registry gate (unchanged). Rebalance adds/trims/rotations use the edge-registry gate (unchanged). Core packs use the core gain gate above (documented drift term, same 2× / net-positive rule, plus tax).
- **Unchanged:** ×1 long only; caps 20% stock / 35% ETF / 45% sleeve of total equity; cash ≥ agent floor (1% of equity) after every buy; cross-book block vs Momentum live holdings; pre-buy refresh sequence; trade_counter slot logging (audit only); 24x5 equities with live `isOpen=true`; TP + SL on every new buy.
- **Trader_Classic:** run the core first (classic-rebalance core path), then RSI satellites with whatever cash is left above the floor. Mandate text below that allows crypto majors, a crypto sleeve, or crypto 24/7 is void.

## Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)
- **FULL AUTO is ON.** Any Classic trade with run-QA PASS (RSI runs) + order-QA PASS + a passing final cost gate (execute_pass GO) is placed automatically by Trader_Classic via `user-OfersClaw5` — no Ofer chat approval. Ofer has accepted QA's earlier residual risks.
- **Hours:** US stocks/ETFs 24x5 via eToro extended hours (Sun 20:05 ET → Fri 20:00 ET, minus US holidays); an instrument that lacks extended hours or reports closed (isOpen=false / prepare rejects) falls back to RTH. ~~Crypto trades 24/7 incl. weekends.~~ (crypto removed 2026-10-17) The old weekend freeze applies to equities only.
- **No daily new-trade cap (fix14).** The counter `classic_rsi/trade_counter.py` (cross-checked with positions opened today) logs every new open for audit only; it never blocks.
- **Daily slot protocol (QA fix 2026-10-16; fix14: logging only):** execute_pass GO (write-lock) atomically records a daily slot and returns `trade_reservation_id`. On a confirmed fill run `cd /workspace && ./screener-venv/bin/python -m classic_rsi.trade_counter mark --reservation <ID> --position-id <POS>`; if the place fails or is abandoned run `... trade_counter release --reservation <ID> --reason "<why>"`. Never place without a reservation. Before any buy GO, save a fresh (≤30 min) `user-OfersClaw5` get-my-trading-history read as `{"asOf": <ISO>, "response": <raw>}` to `/workspace/classic_rsi/state/trading-history-today.json` (opened-and-closed-today positions are counted in the log). Missing/stale history → `TRADING_HISTORY_MISSING` (NO-GO). The counter path is pinned; never set `CLASSIC_TRADE_COUNTER` in production.
- **Live open check:** stocks/ETFs need an explicit live per-instrument `isOpen=true` (`--instrument-open true` for RSI buys; `is_open: true` on every rebalance live leg). Unknown → CLOSED (`INSTRUMENT_OPEN_UNKNOWN`). ~~Crypto majors are open 24/7 unless the read says closed.~~ (crypto removed 2026-10-17)
- **XLE no-add rule lifted (fix14, Ofer 2026-10-23):** XLE buys/adds are allowed like any ETF (caps, floor, cost gate, QA, cross-book check).
- ~~**Crypto specifics:** crypto packs must carry the explicit instrumentId (100000/100001/100063); a bare BTC/ETH/SOL symbol never resolves to crypto. Crypto SL = max(2.5×ATR(1H), 4%) capped at 20% below entry, TP = entry + 1.5×SL distance; rebalance crypto SL must be 4–20% below ask and ≥ 1× daily ATR. Preliminary crypto cost floor: 1% spread + 1% fee per side.~~ **[SUPERSEDED 2026-10-17: crypto removed from Classic]**
- **Caps of TOTAL equity:** single stock ≤ 20%, ETF/fund ≤ 35%, any sleeve ≤ 45%. ~~crypto sleeve ≤ 15%~~ (removed 2026-10-17). **Cash floor = 1% of total agent equity (config-pinned `python -m classic_rsi.floor`; fail closed if equity is unavailable or the config sha is wrong)** after every buy (sequenced across a batch).
- ~~**Crypto:** only BTC (instrumentId 100000), ETH (100001), SOL (100063); ×1 long; SL+TP required. Every other crypto stays blocked. Symbol traps: bare `T` = Threshold crypto (100528), AT&T is `T.US` (1030); `CVX` → `CVX.US`; never resolve by bare ticker alone.~~ **[SUPERSEDED 2026-10-17: crypto removed from Classic]**
- **Every new buy MUST carry a calculated take-profit AND a stop-loss on the order.** TP from ATR/R-multiple (RSI default since 2026-10-17: SL = entry − 2.5×ATR, TP = entry + 2R = 5×ATR, re-based on live ask; reward:risk ≥ 1.25; core: SL −11% / TP +25%, confirmed by Ofer 13:55 IDT) and the trade must satisfy the cost gate (expected gain ≥ 2× round-trip cost). For RSI buys that is the TP distance × p; for core buys it is the documented drift gain term, since the far +25% TP is a cap, not the gain estimate. A buy without TP (takeProfitRate null) is a hard fail.
- **Unchanged:** ×1 long only, no leverage/shorts, stops required, sell/rotate before buy, cost gate (expected gain ≥ 2× round-trip cost; for core packs via the 2026-10-17 core gain term), cross-book block vs Momentum-HHHGDTJ live holdings.
- ~~**Overlap note:** the Daily Trader book trades leveraged crypto/stocks same-day; Classic crypto is a ×1 swing on a separate account. Flag (do not auto-block) when Classic would buy the same crypto Daily Trader holds/trades that day, and never treat Daily Trader levels as Classic signals.~~ **[SUPERSEDED 2026-10-17: crypto removed from Classic]**


Standing playbook for **Trader_Classic** on the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY).

**Objective:** beat **S&P 500** on a **net** basis (after eToro fees/spreads/overnight, realized P&L, and estimated tax drag). Prefer fewer high-quality longs over churn — keep the book **diversified enough to earn across regimes**.

**Naming (Ofer 2026-10-06):** **Classic account** = OfersClaw5-PRIYN agent account (keys MCP `user-OfersClaw5`). Use the phrase **Classic account (OfersClaw5-PRIYN)** going forward. Stop calling it keys-B or ledger B for Classic.

**Source of truth (Ofer 2026-10-06):** Classic **execution, cash gating, prepare/place, order-QA, AND portfolio reporting** (equity/cash/positions on cards, App, briefs, QA data gates) come from the **Classic account (OfersClaw5-PRIYN)** via MCP `user-OfersClaw5`. Do **not** reject OfersClaw5 keys figures as Classic. Parent SSO mirror `11368142` is only the copy/UI view — optional corroboration, never required, never the rejection reason. `prepare-trade` / `place-trade` run on the Classic account.

## Standing policy — FULL AUTO (Ofer 2026-10-11)

**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place ON — Ofer accepted QA's residual risks 2026-10-16 01:27 IDT (see standing rules update).

- **Look for a new opportunity every run** (`classic-rsi-1h-auto` every 3 hours weekdays `CRON_TZ=Asia/Jerusalem 35 */3 * * 1-5`, plus the daily rebalance check). If a valid pack exists, it passes run-QA ([Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa)) and order-QA ([Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate)), passes the **cost/benefit gate**, and cash after stays ≥ the agent floor (1% of equity), then **Trader_Classic places automatically — no chat authorization from Ofer or CoS**.
- **No opportunity → do nothing** (log the run).
- **Rebalance is DAILY** (weekdays), not weekly — see [Classic rebalance](sand-workflow:classic-rebalance). Daily trims/rotations/sells/adds are also full auto after QA PASS + cost gate.
- **No daily trade cap** (fix14: the strategy plan sets the trade count); **no monthly new-name cap**.
- **Every run and every movement is documented** (see Documentation).

## Mandate (confirmed Ofer 2026-10-16 01:27 IDT; was pending since 2026-10-11)

- Long-only, leverage **×1**; crypto only BTC/ETH/SOL ×1 (crypto sleeve ≤ 15%)
- Prefer large liquid US companies / sector ETFs, then commodities
- Strategy plan v2 cash band 0–3%; never all-in below the floor; cash ≥ agent floor (1% of total equity)
- Name caps 35% fund/ETF / 20% single stock of **total equity**; growth/sleeve cap 45% of **total equity** (not invested capital; check cost and market-value numerators over total equity — Ofer 2026-10-12 17:56 IDT); stops per [Classic rebalance](sand-workflow:classic-rebalance)
- **Floor-vs-cap exit precedence undecided** (Ofer): any exit pack that depends on choosing cash-floor vs cap-breach first is **held** until Ofer decides
- REAL only; QA PASS + cost gate → auto place → fill audit → CoS
- No place under an explicit Ofer/CoS HOLD; QA PASS is mandatory before every place
- Weekend: no new equity size (crypto majors trade 24/7)
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. This is the ONLY symbol hard block (fix14).

## Cost/benefit gate (mandatory before every place — Ofer 2026-10-11)

Before every buy, sell, trim, or rotation, estimate the round-trip cost against the expected gain:
- **Costs:** eToro spread/fees (prepare/getCost), any closing fee, overnight/financing for the planned hold, realized PnL and tax impact when selling a winner.
- **Expected gain:** distance to TP and the ATR-based expected move (haircut for probability); for rotations, the replacement's edge minus both legs' costs and tax.
- **Rule:** place only if `expected_gain ≥ 2 × total_cost` and the expected net gain is clearly positive. Else skip and log `COST_GATE_SKIP`. Hard risk exits (stops) still execute; numbers still recorded.
- Put the `cost_gate` numbers in the pack/audit; order-QA must verify them.

## Documentation (every run, every movement)

Follow the existing audit conventions and add the cost-gate numbers: `run_id` audit JSON + `index.jsonl` (`/workspace/classic_rsi/audit/`), run-QA and order-QA verdict files, Job-Runs notes for every run (including "no opportunity — no action" and skips), and for every place: prepare snapshot, `cost_gate` block, QA verdict ref, fill vs prepare, fees, cash after. Daily rebalance runs also write the daily run log per [Classic rebalance](sand-workflow:classic-rebalance).

## Cash floor sizing (Ofer 2026-10-07; fix14 2026-10-23: 1% of total equity)

**Hard preference:** cash floor = 1% of total agent equity (config-pinned `python -m classic_rsi.floor`; fail closed if equity is unavailable or the config sha is wrong); leave at least the agent floor as residual cash on the Classic account after any buy batch.

If a proposed pack would leave cash **below the agent floor (1% of equity)**:
1. **Lower** each trade’s notional, and/or
2. **Buy fewer symbols** (keep the best sleeve-fit / highest-conviction names),
3. Re-check cash-after ≥ floor, then prepare / order-QA.

Do **not** propose a floor override unless Ofer **explicitly** sizes knowing cash will go under the agent floor (1% of equity). Never auto-place a pack that breaches the floor without that explicit override.

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
- Still required: ×1 long-only, crypto majors only, equity weekend freeze, sleeve caps, QA PASS before place. Size smaller into Extreme Fear; leave a cash buffer when possible.
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
8. Size so cash-after ≥ agent floor (1% of equity) (cut notional or drop symbols first)
9. prepare on **Classic account** (`user-OfersClaw5`) — fees + tax haircut
10. Read latest **KEEP / AVOID** from [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop) before proposing size
11. **Cost/benefit gate** (above) — skip if net expected gain is not clearly positive
12. Order-QA PASS → **auto place** (no Ofer chat auth) → fill audit → CoS

## After every fill / skip / QA FAIL

Run [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop): score Q/A/order/market/X/brief/graph/outcome; write KEEP/AVOID; patch this playbook only when a hard avoid repeats.

## Beat-SPX filter / regimes / daily checklist / pre-trade / events

Hold cash if the dip is not clean; event-vol freeze; in Fear lean into quality dips (healthcare, hard assets, and beaten large-caps) rather than a blanket no-buy; risk-on small liquid adds after QA; NVDA no-add default; any fit symbol when the dip is real.

## Do not

Non-major crypto/shorts/lev>1; buys without TP; exclusive ticker lists; break caps; chase parabolic into event-vol; treat high Fear as an automatic no-buy; ignore fees/tax; duplicate pending closes; place without QA PASS or without a passing, recorded cost/benefit gate; churn trades whose expected gain does not clearly beat round-trip cost + tax; use 1h heatmap when 1D was set; treat RSI Sell tags as shorts; prepare on parent SSO expecting a `mirrorId` (parent cannot target the copy); auto-place packs that leave cash under the agent floor (1% of equity) without Ofer’s explicit override; skip the sell/rotate check before new buys; buy a symbol held in Momentum (mirror 11630170) — cross-book no-overlap.

## Slot pre-check — first step of every classic-rsi-1h-auto slot (Ofer 2026-10-18, token saving; no trading-rule change)

Before the book refresh, `auto_1h` or any QA handoff:
1. ONE fresh live read of OfersClaw5-PRIYN: MCP `user-OfersClaw5` `get-my-portfolio-summary` with `{"account":"real","includePositions":true,"includeOrders":true,"includeCopiedTraders":false}`. Save the raw output to `/workspace/classic_rsi/state/precheck-live.json`.
2. `cd /workspace && ./screener-venv/bin/python -m classic_rsi.precheck --live-json /workspace/classic_rsi/state/precheck-live.json`
   - It reads the existing `trade_counter` for today's IDT day (plus positions opened today in that live read) and imports every threshold from `execute_pass` / `trade_counter` (agent floor = 1% of the live read's equity via the config-pinned `classic_rsi.floor`, min order $400; the trade count is logged only). It never calls eToro and never places.
   - **Exit 10 = SKIP the whole slot**: no book refresh, no `auto_1h`, no run-QA handoff, no message. Stay quiet. This happens only when no stop/rebalance action is pending AND `0 ≤ availableCash − agent floor (1% of equity) < $400` (`NO_CASH_FOR_MIN_ORDER`). fix14: there is no daily-budget skip.
   - **Exit 0 = PROCEED** with the normal slot, unchanged. The pre-check fails open: a stale (>15 min), unsuccessful or unparseable live read, or a counter error, always means PROCEED.
   - **Pending stop/rebalance means never skip.** That covers pending orders, a position at or through its SL, TP or trailing level (`scores-latest.json`), a missing SL, cash below the floor (`cash_below_floor`), a name or sleeve over its cap of total equity (`hard_cap_breach`), and an open entry in `/workspace/classic_rsi/state/pending-actions.json` (`{"actions":[{"kind":..,"symbol":..,"note":..,"done":false}]}`). Any agent can set that manual flag.
3. Each decision (SKIP or PROCEED) appends one JSON line to `/workspace/classic_rsi/audit/precheck/precheck-YYYYMMDD.jsonl`. A skipped slot has no `run_id` and no run-QA. The audit line is its record, and this replaces "every run → run-QA" for skipped slots only.
4. The classic-rebalance SPY/QQQ core path runs separately and is not gated by this pre-check.
Test: `./screener-venv/bin/python -m classic_rsi.test_precheck_20261018` (offline, 19 checks).
5. **Lever 3 — RSI pre-scan silent exit (Ofer 2026-10-18 16:44 IDT; 2026-10-18g; no trading-rule change).** Add `--prescan` to the precheck command (`--from-books --prescan`, or `--live-json <file> --prescan`).
   - It only acts when precheck would PROCEED with no force reason. Force reasons are: a pending order, an SL/TP/trailing stop hit, a missing SL, cash below the floor, a cap breach, a `pending-actions.json` entry, a stale or failed live read, or a counter error. With a force reason the pre-scan does not run and the slot proceeds.
   - Otherwise it runs `classic_rsi.prescan`: the four-level RSI state machine (`signals.compute_signals`, default levels, confirmed 1H closes only) over the same universe auto_1h builds (S&P liquid + rising 1H volume, top 50) plus the live holdings. Yahoo 1H data via `backtest.fetch_1h`; about 45 s; no LLM, never places.
   - Candidates: a Support/Over Sold long entry (`CANDIDATE_LONG`) on any of the last 3 confirmed bars for any symbol, or a `RISK_OFF` (Over Buy / Resistance) on the last 3 bars for a holding.
   - **Zero candidates → exit 10 SKIP** (reason `NO_RSI_CANDIDATES`): stay silent, no book refresh, no auto_1h, no run-QA. The precheck jsonl line plus `/workspace/classic_rsi/audit/precheck/prescan-*.json` (per-symbol RSI states) are the record.
   - **Any candidate, universe cache fallback, a holding with no data, more than max(2, 5%) symbols without data, stale bars, or a pre-scan error → exit 0 PROCEED** (fails open). The full slot then runs exactly as before: book refresh → auto_1h → run-QA → pre-buy refresh → cost gate → order-QA PASS → fresh live reads at GO.
   - Pass the candidate list to the run: `auto_1h --note "prescan=/workspace/classic_rsi/state/prescan-latest.json"`.
   - Tests: `./screener-venv/bin/python -m classic_rsi.test_prescan_20261018` (25 offline checks).

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
3. Within 5 minutes: `execute_pass` (it refuses with `PRE_BUY_NOT_FRESH` if prebuy-state is missing, > 5 min old or incomplete, and `BOOK_NOT_FRESH_FOR_COUNT` if the book is > 60 s old). Pass `--instrument-open` from the printed `instrument_open_flags`. Then order-QA → `prepare_token split` → place (token via `$file:`) → `prepare_token wipe` → `trade_counter mark --reservation <ID> --position-id <POS>` (or `release --reservation <ID> --reason ...` on failure). See the fix11 section below.
- Never run production with `CLASSIC_EXEC_TEST_ROOT` set: test-mode results are labelled `test_mode`, `placeable=false`, the CLI exits 3, and auto_1h envelopes get a `TEST_MODE` hard flag.

## execute_pass GO pin + prepare/place token handling (fix11, deployed 2026-10-21 19:17 IDT; pin updated by fix14)

- **GO version:** `classic_rsi/execute_pass.py` **v16.12 fix14** (`execute-pass-v16.12-rule-release-20261023-fix14`, package 1.1.7), sha256 `1fa6ffdd75c3a8699c99d8997bf61bd5d8a00c30bfb832cff6bf105700230bc5`. Any other sha is not the QA GO version → NO-GO. The daily `build_daily.py` `EP_OK` pins the same sha.
- **Cash floor:** always the config-pinned floor (`python -m classic_rsi.floor`, or `resolve(expected_sha256=<pinned config sha>)`; a bare `resolve()` is not config-pinned) (= execute_pass `cash_floor.agent_floor_usd` = 1% of total equity); never `floor_now()` or a hard-coded number.
- **After every `prepare-trade` / `prepare-close`** (saved with write_to_file): `cd /workspace && ./screener-venv/bin/python -m classic_rsi.prepare_token split --response <raw> --stripped-out <pack-dir>/prepare-tokenstripped.json --token-out /tmp/<unique>-token`. It accepts `token` or `confirmationToken`, writes the token-free copy to disk first, writes the token ONLY to a 0600 file, deletes the raw read and prints metadata only. Exit 2 (`PREPARE_TOKEN_MISSING` / `AMBIGUOUS` / `INVALID` / `NOT_READY` / `VALUE_LEAK`) = do not place; re-prepare. Never read the token field by hand and never print it. Build live.json / execute_pass inputs from the stripped copy only.
- **Place:** one `place-trade` / `place-close` call with `token = "$file:/tmp/<unique>-token"`. Then ALWAYS `./screener-venv/bin/python -m classic_rsi.prepare_token wipe --token-out /tmp/<unique>-token` (after a fill, a failure or an abandon), and save the place result with `prepare_token strip --response <raw> --out <pack-dir>/place-result.json`. Before any re-place, live-read to check whether the first place already went through.
- **Deploy / rollback of classic_rsi packages:** `apply_fixNN.sh` (check only) → `--apply --external`; roll back ALWAYS with `--rollback <backup-dir> --external` (without `--external` the external scripts stay on the new code and fail on import).

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

Deterministic book work lives in Python: `/workspace/books/snapshot.py` (normalised cache `/workspace/books/latest/<book>.json`, history under `books/history/`) and `/workspace/books/cards.py` (card facts). Books: `classic` (user-OfersClaw5), `momentum_mirror` (mirror 11630170 in user-etoro = Momentum reporting truth), `momentum_keys` (user-Momentum-HHHGDTJ, ledger/cross-check only), `parent` (mirror 11368142, Classic copy, UI only).

1. **Check freshness first:** `cd /workspace && python3 -m books.snapshot fresh --book <book> --max-age-min <N>`. Exit 0 prints the path, so use that JSON and do not re-read. Exit 2 means stale or missing.
2. **If stale, do ONE read per book:** run `python3 -m books.snapshot agent-read-hint --book <book>`, then make exactly the MCP call(s) it prints with `write_to_file=true`. Next run `python3 -m books.snapshot ingest --book <book> --raw <file> [--raw <file2>]`. The same two user-etoro files feed both `momentum_mirror` and `parent`. If ingest refuses with `SOURCE_MISMATCH`, `MIRROR_MISSING` or `OLDER_THAN_CACHE`, that is a real data problem: stop and report it, and never hand-edit the cache.
3. **Cards:** `python3 -m books.cards --max-age-min <N> --json <out.json> --md <out.md>` gives Classic caps/core/deployable/drift/blocked/changes and Momentum stops/blocked/divergence. The LLM writes only the Buy and Sell/Rotation judgement lines (the `<LLM judgement>` placeholders) and never recomputes these facts.
4. `python3 -m books.snapshot overlap` lists cross-book symbols and keys-vs-mirror divergence.

The snapshot never changes trading rules. Caps and floors are imported from `classic_rsi` and are not redefined.

**Usage:** Classic card facts (caps 20/35/45%, cash floor 1% of equity, $400 min order, SPY+QQQ core 55% combined target (not binding) each ≤35% with SL/TP, crypto removed, cross-book blocked list (the only hard block), deployable cash, cash-drift trigger, changes vs previous) come from `books.cards`. Pre-check: `classic_rsi.precheck --from-books` after a fresh `classic` snapshot (≤15 min). Order gates keep their own live reads, unchanged.

## Book refresh = one script (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only; no trading-rule change)
The `classic-portfolio-for-app.json` refresh is fully scripted. Per run:
1. user-OfersClaw5 `get-my-portfolio-summary` and `get-my-positions-and-orders` with `write_to_file`. Do not read or summarise the raw output.
2. `cd /workspace && ./screener-venv/bin/python -m classic_rsi.book_refresh --summary <summary_raw> --positions <positions_raw>`
   - It validates the reads (real account, no copied-trader/mirror data, ≤600 s apart, not older than the book, holdings = lots, reconciliation gap ≤0.5%). Then it builds per-lot rows, cash/equity/floor/core fields and `changesVsPrevRefresh`, recomputes sleeves (`book_sleeves`), backs up and writes atomically, updates `classic_book_refresh_state.json` and ingests the reads into `books/`.
   - Prints one JSON line. Exit 0 = written, 2 = REFUSED (book untouched; consecutiveFailures++), 1 = error.
3. **LLM:** relay nothing when `changes` is empty (equity/cash deltas 0, no symbol/SL changes). Otherwise write one short line from the JSON. No ad-hoc Python, no hand edits of the book, no re-reading the file.

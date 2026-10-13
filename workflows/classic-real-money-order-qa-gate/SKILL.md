---
name: Classic real-money order QA gate
description: >-
  use this when independently validating a Trader_Classic real-money order or
  audit for OfersClaw5-PRIYN before or after execution, including Classic RSI 1H
  packs with run_id audit trail and daily rebalance packs; verifies the
  cost/benefit gate numbers — QA PASS + passing cost gate is sufficient to
  auto-place (no Ofer authorization needed since 2026-10-11)
---
# Classic real-money order QA gate

Independent validator for Trader_Classic on the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY). Activated by Ofer 2026-09-02.

Also covers **Classic RSI 1H** packs (ATR SL/TP, confirmed close, long-only) proposed by Trader_Classic / CoS (2026-09-19).

**Naming (Ofer 2026-10-06):** **Classic account** = OfersClaw5-PRIYN agent account (keys MCP `user-OfersClaw5`). Use **Classic account (OfersClaw5-PRIYN)** going forward. Stop calling it keys-B or ledger B for Classic.

## Authorization (Ofer 2026-10-11 — FULL AUTO)

**Activation status:** APPROVED by Ofer 2026-10-12 06:17 IDT; code gate PASSED QA (fix3, 2026-10-12) — auto-place still OFF until Ofer explicitly accepts QA's residual risks (shared-box verdict forgery, self-reported second-source mark, trader-controlled test mode, editable scores/registry pins) AND out-of-sample edge evidence exists. Until then every Classic place needs QA PASS + explicit Ofer authorization.

**Cost-gate requirement:** order-QA cannot PASS without a verified cost-gate block (from `classic_rsi/cost_gate.py` / `execute_pass.py` output).

**Order-QA field spec (cost-gate contract):** see `order_qa_cost_gate_contract` in `/workspace/classic_rsi/audit/qa-review-classic-full-auto-20261012.json` (`must_be_present`, `recompute`, `also_verify`) — use that as the authoritative field checklist for cost-gate verification until the code gate passes QA.

For Classic, **order-QA PASS (this gate, including a verified cost/benefit gate) is sufficient authorization** for Trader_Classic to place automatically — buys, sells, trims, and rotations, from the hourly RSI auto or the daily rebalance. **No Ofer or CoS chat authorization is required** (only once the code gate passes QA). There is **no trade-count limit and no monthly new-name cap**; do not FAIL on either. An explicit Ofer/CoS hold still blocks. Because PASS now triggers a real-money place, PASS only with complete evidence.

## When to run

Validate EVERY order and audit step before and after execution. Do not self-grade for the trader. No PASS without evidence.

## Cash / book truth (Ofer 2026-10-06)

Classic dollars, cash-after-size, prepare, place, and order-QA use the **Classic account (OfersClaw5-PRIYN)** MCP (`user-OfersClaw5`). **Do not Hard FAIL** a pack solely because it uses Classic account / OfersClaw5 cash/book. Parent SSO mirror `11368142` is the copy/UI view — optional corroboration, never required, never the rejection reason, not the prepare target. Parent `prepare-trade` has no `mirrorId` and must **not** be required.

## Fear / No Buy (Ofer 2026-10-05)

CNN Fear & Greed in **Fear or Extreme Fear** is a **buy-the-dip opportunity**, not an automatic No Buy FAIL for Classic. Do **not** FAIL a Classic long ×1 pack solely because F&G is Fear/Extreme Fear or because daily_brief said No Buy only for Fear. Still require full integrity of this gate and [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa); no place without PASS. Momentum Fear rules are unchanged unless separately mandated.

## Required artifacts before PASS

From Trader_Classic (redact secrets):

1. Portfolio id / name: Classic account (OfersClaw5-PRIYN)
2. Side: buy or sell (sell = close/reduce long only)
3. Instrument (symbol + instrumentId if available)
4. Asset class (must not be crypto)
5. Leverage (must be exactly 1)
6. Size / amount and remaining cash after fill estimate (**Classic account / OfersClaw5 cash**)
7. Fee estimate and overnight/financing estimate
8. **Cost/benefit gate block** (`cost_gate`): spread, fees (open + close), overnight/financing, realized PnL and tax estimate on sells, `total_cost`, `expected_gain` (TP distance and/or ATR-based expected move, method stated), `expected_net_gain`, `ratio`, verdict
9. Thesis (one clear reason tied to Classic mandate; RSI packs: RSI 1H + ATR SL/TP + confirmed close + **cite `run_id`** like `classic-rsi-propose-YYYYMMDD-…`)
10. Prepared order snapshot (immutable after prepare; prepare on **Classic account** `user-OfersClaw5`)
11. Route: must be REAL, never demo
12. Cash after ≥ ~$2,500 (Classic account cash, sequenced across the batch)
13. Post-execution audit: fill vs prepare, fees, cash left, cost_gate echoed, QA verdict ref

For RSI packs, also expect an append-only trail under `/workspace/classic_rsi/audit/` (`index.jsonl`) matching the cited `run_id`.

## Cost/benefit gate verification (mandatory)

Independently recompute from the prepare snapshot / live quote: spread and fees match prepare/getCost; tax estimate is present on sells of winners; `expected_gain` follows the stated method (TP − live entry, ATR-based move) and is not invented. PASS only if `expected_gain ≥ 2 × total_cost` and `expected_net_gain` is clearly positive. Exception: hard risk exits (stop hit, cash below floor) may PASS with a negative ratio, but the numbers must still be present. Write the recomputed numbers into the verdict file.

## Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT)

**Cross-book no-overlap:** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either.

## Hard FAIL (any one fails the gate)

- leverage ≠ 1
- short / sell-to-open
- crypto
- missing `cost_gate` block, numbers that do not reconcile with prepare/getCost, or expected net gain not clearly positive (non-risk-exit) → `COST_GATE_FAIL`
- cash after the place (or sequenced batch) below ~$2,500 without an explicit Ofer sizing override → `CASH_FLOOR`
- name cap (30% fund/ETF / 15% single stock of **total equity**) or sleeve/growth cap (45% of **total equity**) breached after the buy — denominator is total equity, not invested capital; check both cost and market-value numerators over total equity (Ofer 2026-10-12 17:56 IDT; kept pending Ofer confirmation on other mandate items)
- exit pack that depends on **floor-vs-cap exit precedence** (undecided by Ofer) → hold; do not PASS a pack that assumes one precedence over the other
- buy placed without the sell/rotate-before-buy check recorded
- all cash invested with **zero** residual when size was not an explicit Ofer override on a small Classic account book
- demo routes
- missing fee estimate
- missing overnight/financing estimate
- missing thesis
- order changes after prepare
- not long ×1 buy, or not a long-reducing sell matching prepare
- **RSI / signal “sell” tags that imply shorting** — sell tags authorize **risk-off / no-add / long-reducing close only**, NEVER shorts
- RSI pack missing `run_id` in thesis / propose, or no matching audit trail row when required
- prepare on **parent SSO** claiming to hit mirror `11368142` (parent cannot target the copy)
- buy of a symbol already held in the other book (Classic vs Momentum mirror 11630170) → `CROSS_BOOK_OVERLAP` (Ofer 2026-10-13 01:44 IDT); live-read the other book before PASS; existing overlap XLE kept in both books per Ofer 2026-10-13 — never add to it

## Not a Hard FAIL (Classic)

- Fear / Extreme Fear alone, or daily_brief No Buy that exists only because of Fear (2026-10-05 buy-the-dip mandate)
- Using **Classic account (OfersClaw5-PRIYN)** / `user-OfersClaw5` as Classic cash/execution/reporting truth (Ofer 2026-10-06)
- Sub-~$2.5k residual Classic account cash when Ofer explicitly sized the order knowing Classic account cash
- **No Ofer/CoS chat authorization** on the pack (Classic is full auto since 2026-10-11) (only once the code gate passes QA)
- Number of trades today/this month, or number of new names this month (no cap since 2026-10-11)

## PASS

Only long ×1 buys/sells that match the Classic mandate, clear every hard fail, and have a verified cost/benefit gate. A PASS is the place authorization for Classic. Order-QA cannot PASS without a verified cost-gate block (from `classic_rsi/cost_gate.py` / `execute_pass.py` output). RSI 1H entries must be long-only with ATR SL/TP, confirmed-close thesis, and cited `run_id`.

## Verdict schema

- QA writes verdicts to `/workspace/classic_rsi/audit/qa/`.
- Required fields: checker `QA Bot`, skill, checked_at, run_id; for order-QA also pack_sha256, pack_id, symbol, qa_ask, recomputed_cost_gate.
- The cost gate's expected gain is EV including the stop-loss side, and p comes only from out-of-sample registries (no in-sample or assumed p). A missing edge registry or scores file means SKIP.
- A prepare that echoes a takeProfit on a rebalance buy (`takeProfitRate` must be null) is NO-GO.
- Reference `/workspace/classic_rsi/audit/qa-review-classic-full-auto-fix3-20261012.json`.

## Verdict delivery

1. Send PASS or FAIL with reasons + evidence to **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
2. Copy the same verdict to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
3. Tell Ofer in QA Bot chat on FAIL, and on PASS when useful (especially first trade or material size)
4. Save the verdict file (PASS/FAIL, codes, evidence, recomputed cost_gate numbers, `run_id`) next to the audit trail and reference it in the Job-Runs note

Until PASS, Trader_Classic must not place. On PASS, Trader_Classic places automatically without waiting for Ofer/CoS (only once the code gate passes QA). QA never places.

## Related: Classic RSI 1H **run** QA

Every Classic RSI `auto_1h` / `propose` run must first clear [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa). On that gate **FAIL**, QA Bot messages **Trader_Classic** to rerun (max 2/hour) and re-validates the new `run_id`. Do not start this order gate on a FAILed run_id. Empty `buy_packs` can still be a run-level PASS.

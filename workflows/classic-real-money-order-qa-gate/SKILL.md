---
name: Classic real-money order QA gate
description: >-
  use this when independently validating a Trader_Classic real-money order or
  audit for OfersClaw5-PRIYN before or after execution, including Classic RSI 1H
  packs with run_id audit trail
---
# Classic real-money order QA gate

Independent validator for Trader_Classic on the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY). Activated by Ofer 2026-09-02.

Also covers **Classic RSI 1H** packs (ATR SL/TP, confirmed close, long-only) proposed by Trader_Classic / CoS (2026-09-19).

**Naming (Ofer 2026-10-06):** **Classic account** = OfersClaw5-PRIYN agent account (keys MCP `user-OfersClaw5`). Use **Classic account (OfersClaw5-PRIYN)** going forward. Stop calling it keys-B or ledger B for Classic.

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
8. Thesis (one clear reason tied to Classic mandate; RSI packs: RSI 1H + ATR SL/TP + confirmed close + **cite `run_id`** like `classic-rsi-propose-YYYYMMDD-…`)
9. Prepared order snapshot (immutable after prepare; prepare on **Classic account** `user-OfersClaw5`)
10. Route: must be REAL, never demo
11. Post-execution audit: fill vs prepare, fees, cash left

For RSI packs, also expect an append-only trail under `/workspace/classic_rsi/audit/` (`index.jsonl`) matching the cited `run_id`.

## Hard FAIL (any one fails the gate)

- leverage ≠ 1
- short / sell-to-open
- crypto
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

## Not a Hard FAIL (Classic)

- Fear / Extreme Fear alone, or daily_brief No Buy that exists only because of Fear (2026-10-05 buy-the-dip mandate)
- Using **Classic account (OfersClaw5-PRIYN)** / `user-OfersClaw5` as Classic cash/execution/reporting truth (Ofer 2026-10-06)
- Sub-~$2.5k residual Classic account cash when Ofer explicitly sized the order knowing Classic account cash

## PASS

Only long ×1 buys/sells that match the Classic mandate and clear every hard fail. RSI 1H entries must be long-only with ATR SL/TP, confirmed-close thesis, and cited `run_id`.

## Verdict delivery

1. Send PASS or FAIL with reasons + evidence to **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
2. Copy the same verdict to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
3. Tell Ofer in QA Bot chat on FAIL, and on PASS when useful (especially first trade or material size)

Until PASS, Trader_Classic must not place. QA never places.

## Related: Classic RSI 1H **run** QA

Every Classic RSI `auto_1h` / `propose` run must first clear [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa). On that gate **FAIL**, QA Bot messages **Trader_Classic** to rerun (max 2/hour) and re-validates the new `run_id`. Do not start this order gate on a FAILed run_id. Empty `buy_packs` can still be a run-level PASS.

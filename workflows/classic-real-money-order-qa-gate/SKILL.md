---
name: Classic real-money order QA gate
description: >-
  use this when independently validating a Trader_Classic real-money order or
  audit for OfersClaw5-PRIYN before or after execution, including Classic RSI 1H
  packs with run_id audit trail
---
# Classic real-money order QA gate

Independent validator for Trader_Classic on portfolio **OfersClaw5-PRIYN** (REAL MONEY). Activated by Ofer 2026-09-02.

Also covers **Classic RSI 1H** packs (ATR SL/TP, confirmed close, long-only) proposed by Trader_Classic / CoS (2026-09-19).

## When to run

Validate EVERY order and audit step before and after execution. Do not self-grade for the trader. No PASS without evidence.

## Required artifacts before PASS

From Trader_Classic (redact secrets):

1. Portfolio id / name: OfersClaw5-PRIYN (Classic)
2. Side: buy or sell (sell = close/reduce long only)
3. Instrument (symbol + instrumentId if available)
4. Asset class (must not be crypto)
5. Leverage (must be exactly 1)
6. Size / amount and remaining cash after fill estimate
7. Fee estimate and overnight/financing estimate
8. Thesis (one clear reason tied to Classic mandate; RSI packs: RSI 1H + ATR SL/TP + confirmed close + **cite `run_id`** like `classic-rsi-propose-YYYYMMDD-…`)
9. Prepared order snapshot (immutable after prepare)
10. Route: must be REAL, never demo
11. Post-execution audit: fill vs prepare, fees, cash left

For RSI packs, also expect an append-only trail under `/workspace/classic_rsi/audit/` (`index.jsonl`) matching the cited `run_id`.

## Hard FAIL (any one fails the gate)

- leverage ≠ 1
- short / sell-to-open
- crypto
- all cash invested (must leave cash reserve)
- demo routes
- missing fee estimate
- missing overnight/financing estimate
- missing thesis
- order changes after prepare
- not long ×1 buy, or not a long-reducing sell matching prepare
- **RSI / signal “sell” tags that imply shorting** — sell tags authorize **risk-off / no-add / long-reducing close only**, NEVER shorts
- RSI pack missing `run_id` in thesis / propose, or no matching audit trail row when required

## PASS

Only long ×1 buys/sells that match the Classic mandate and clear every hard fail. RSI 1H entries must be long-only with ATR SL/TP, confirmed-close thesis, and cited `run_id`.

## Verdict delivery

1. Send PASS or FAIL with reasons + evidence to **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
2. Copy the same verdict to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
3. Tell Ofer in QA Bot chat on FAIL, and on PASS when useful (especially first trade or material size)

Until PASS, Trader_Classic must not place. QA never places.

## Related: Classic RSI 1H **run** QA

Every Classic RSI `auto_1h` / `propose` run must first clear [Classic RSI 1H run QA](sand-workflow:classic-rsi-1h-run-qa). On that gate **FAIL**, QA Bot messages **Trader_Classic** to rerun (max 2/hour) and re-validates the new `run_id`. Do not start this order gate on a FAILed run_id. Empty `buy_packs` can still be a run-level PASS.

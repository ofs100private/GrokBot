---
name: Classic real-money order QA gate
description: >-
  use this when independently validating a Trader_Classic real-money order or
  audit for OfersClaw5-PRIYN before or after execution
---
# Classic real-money order QA gate

Independent validator for Trader_Classic on portfolio **OfersClaw5-PRIYN** (REAL MONEY). Activated by Ofer 2026-09-02.

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
8. Thesis (one clear reason tied to Classic mandate)
9. Prepared order snapshot (immutable after prepare)
10. Route: must be REAL, never demo
11. Post-execution audit: fill vs prepare, fees, cash left

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

## PASS

Only long ×1 buys/sells that match the Classic mandate and clear every hard fail.

## Verdict delivery

1. Send PASS or FAIL with reasons + evidence to **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
2. Copy the same verdict to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
3. Tell Ofer in QA Bot chat on FAIL, and on PASS when useful (especially first trade or material size)

Until PASS, Trader_Classic must not place.

---
name: Classic portfolio data QA gate
description: >-
  use this when independently validating App or Trader_Classic Classic portfolio
  numbers against live eToro OfersClaw5-PRIYN reads
---
# Classic portfolio data QA gate

Independent validator for **App** and **Trader_Classic** portfolio numbers on Classic.

## Scope

- Portfolio: **Classic account (OfersClaw5-PRIYN)**
- MCP: `user-OfersClaw5`
- Parent SSO mirror id **11368142**: optional copy/UI corroboration only — never required, never the rejection reason
- Source of truth: live Classic account reads via `user-OfersClaw5` (equity/cash/positions). Do **not** reject OfersClaw5 figures as Classic. Never trust App hardcoding.

## When to run

Whenever App or Trader_Classic presents Classic totals or positions for display, sync, or decisions.

## PASS

Every total and every position matches the live **Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`)** read (symbols, units/invested, cash, PnL fields presented). Immaterial rounding only if explicitly within documented tolerance; otherwise exact match on presented fields. Mirror `11368142` may corroborate but must not be required for PASS.

## FAIL

- Hardcoded numbers
- Stale snapshot vs live read
- Any mismatched total or position
- Missing live read (cannot verify = FAIL closed)

## Verdict delivery

1. PASS or FAIL with field-level diffs to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
2. Same verdict to **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
3. Tell Ofer on FAIL, and on PASS when useful

Do not invent live numbers. Pull or require a fresh live Classic account (`user-OfersClaw5`) read before verdict.

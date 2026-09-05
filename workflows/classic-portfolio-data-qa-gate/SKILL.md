---
name: Classic portfolio data QA gate
description: >-
  use this when independently validating App or Trader_Classic Classic portfolio
  numbers against live eToro OfersClaw5-PRIYN reads
---
# Classic portfolio data QA gate

Independent validator for **App** and **Trader_Classic** portfolio numbers on Classic.

## Scope

- Portfolio: **OfersClaw5-PRIYN**
- Mirror id: **11368142**
- Source of truth: live eToro Classic agent portfolio reads (via eToro Account / keys path). Never trust App hardcoding.

## When to run

Whenever App or Trader_Classic presents Classic totals or positions for display, sync, or decisions.

## PASS

Every total and every position matches the live read (symbols, units/invested, cash, PnL fields presented). Immaterial rounding only if explicitly within documented tolerance; otherwise exact match on presented fields.

## FAIL

- Hardcoded numbers
- Stale snapshot vs live read
- Any mismatched total or position
- Missing live read (cannot verify = FAIL closed)

## Verdict delivery

1. PASS or FAIL with field-level diffs to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
2. Same verdict to **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
3. Tell Ofer on FAIL, and on PASS when useful

Do not invent live numbers. Pull or require a fresh live Classic read before verdict.

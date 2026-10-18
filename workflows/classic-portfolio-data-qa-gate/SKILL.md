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

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

Deterministic book work lives in Python: `/workspace/books/snapshot.py` (normalised cache `/workspace/books/latest/<book>.json`, history under `books/history/`) and `/workspace/books/cards.py` (card facts). Books: `classic` (user-OfersClaw5), `momentum_mirror` (mirror 11630170 in user-etoro = Momentum reporting truth), `momentum_keys` (user-Momentum-HHHGDTJ, ledger/cross-check only), `parent` (mirror 11368142, Classic copy, UI only).

1. **Check freshness first:** `cd /workspace && python3 -m books.snapshot fresh --book <book> --max-age-min <N>`. Exit 0 prints the path, so use that JSON and do not re-read. Exit 2 means stale or missing.
2. **If stale, do ONE read per book:** run `python3 -m books.snapshot agent-read-hint --book <book>`, then make exactly the MCP call(s) it prints with `write_to_file=true`. Next run `python3 -m books.snapshot ingest --book <book> --raw <file> [--raw <file2>]`. The same two user-etoro files feed both `momentum_mirror` and `parent`. If ingest refuses with `SOURCE_MISMATCH`, `MIRROR_MISSING` or `OLDER_THAN_CACHE`, that is a real data problem: stop and report it, and never hand-edit the cache.
3. **Cards:** `python3 -m books.cards --max-age-min <N> --json <out.json> --md <out.md>` gives Classic caps/core/deployable/drift/blocked/changes and Momentum stops/blocked/divergence. The LLM writes only the Buy and Sell/Rotation judgement lines (the `<LLM judgement>` placeholders) and never recomputes these facts.
4. `python3 -m books.snapshot overlap` lists cross-book symbols and keys-vs-mirror divergence.

The snapshot never changes trading rules. Caps and floors are imported from `classic_rsi` and are not redefined.

**QA usage:** you may verify against the `classic` snapshot **plus one independent live user-OfersClaw5 read of your own**. Do not `ingest` that read until you have compared it. Compare equity, cash, symbols, lots/positionIds and SL against the snapshot and against the App/Trader figures. Any mismatch, or a snapshot that is missing or older than the presented figures, is a FAIL. The snapshot alone is never sufficient (cannot verify = FAIL closed).

## Scripted gate — run first (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only)
1. Do the live user-OfersClaw5 reads (portfolio summary + positions) with `write_to_file`; do not read the raw output.
2. `cd /workspace && python3 -m qa_gates classic-portfolio --live-raw <summary_raw> <positions_raw>` (add `--presented <file..>` to check other files; default = `classic-portfolio-for-app.json` + `etoroview/public/classic-portfolio.json`). Exit 0 = PASS, 1 = FAIL. No live read → FAIL closed.
3. It compares equity, cash, symbol set, SL and per-position value field by field, checks for hardcode markers, and flags asOf >60 min and books-snapshot drift as soft.
**LLM:** read the verdict JSON only; judge soft flags; write the verdict message. Never override a hard fail.

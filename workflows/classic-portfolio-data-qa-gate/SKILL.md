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
1. Do the live user-OfersClaw5 reads with `write_to_file`, back to back, and do not read the raw output: `get-my-portfolio-summary` (account real, includePositions=true) and `get-my-positions-and-orders` (account real). The gate needs both reads to be <= 30 min old when it runs and within 10 min of each other (fix13d M1), so take them immediately before step 3, not earlier in the routine.
2. **Identity (fix13d M2), same connection, right after the reads:** `get-my-profile-and-scopes` on user-OfersClaw5 with `write_to_file`, then
   `cd /workspace && python3 -m qa_gates.identity --profile <profile_raw> --namespace user-OfersClaw5 --raw <summary_raw> <positions_raw>` (run it as the very next step after the profile `write_to_file`; it chmods the profile raw to 0600 first and always deletes it, also on errors — fix13e).
   This writes `<raw>.identity.json` next to each read (local only, mode 0600) and prints `matched` / `MISMATCH` / `ERROR` only. Never print, copy or post the realCid/username values or the profile; The profile raw has personal data. Do not edit a read after this step (the sidecar is bound to its sha256).
3. `cd /workspace && python3 -m qa_gates classic-portfolio --live-raw <summary_raw> <positions_raw>` (unchanged; add `--presented <file..>` to check other files; default = `classic-portfolio-for-app.json` + `etoroview/public/classic-portfolio.json`). Exit 0 = PASS, 1 = FAIL. No live read, a missing/old/incoherent timestamp, a missing or non-matching identity sidecar, or a read without `account` -> hard FAIL.
4. It compares equity, cash, symbol set, SL/TP per positionId and per-position value field by field, checks lot-row completeness and duplicate/conflicting positionIds, checks for hardcode markers, and flags asOf >60 min and books-snapshot drift as soft. If the verdict save fails it still prints a FAIL verdict (exit 1).
**Identity and verdict rules (fix13d, QA-required — no exceptions):**
- **MISMATCH or ERROR = stop and FAIL.** If `qa_gates.identity` prints anything other than `matched` (or exits non-zero), the gate result is FAIL: report it and stop. Never re-bind, never edit or rewrite a read, never take another profile read or use another connection to get `matched`.
- **Never use `--init-pin` or set `QA_GATES_IDENTITY_PINS` in a routine.** The pin is changed only by a reviewed package deploy.
- **Trust anchor (fix13h M2, fix13h.1).** GO-PINS: go_pins.json=6cab69a54f90158006a3826bdc636e96400f9fd620219f0088efc8b75efdf0e2 verify_live.py=e01fe0f4efdc6a9a62bcf69006ef20bc5f3ce4af2ca7d766f6b04d51a967e2bd
  These are the sha256 of /workspace/qa_gates/go_pins.json and /workspace/qa_gates/verify_live.py approved with this skill. Before trusting a deploy, run `cd /workspace && python3 -B -m qa_gates.verify_live` (package list comes from go_pins.json; always pass `--expect <expected_next>=<sums>` with the value from the QA verdict [QA H-L2]; without it expected_next is not sha-checked). It fails `go_pins_anchor` if either file differs from this line. Never edit this line except by promoting a QA-reviewed skill.
- **Delete the profile read on every exit path.** The identity step deletes it itself (fix13e). If the run stops before that step, or aborts anywhere, first delete the profile raw you saved by its exact path, `rm -f -- "<profile_raw>"` (quoted; only the path under /workspace/agent-tools/ that write_to_file returned for this run's profile read; never a glob, never another path; do not open it), then run `cd /workspace && python3 -m qa_gates.identity --purge-profiles` before you stop (it removes leftover profile raws in /workspace/agent-tools that are older than 2 minutes, so a raw from the current run is only removed by the `rm -f`). Start every gate run with the same purge. Never open or print a profile raw.
- **Trust only the gate's stdout and exit code** (exit 0 + stdout `"verdict": "PASS"`). Never use `qa_gates/verdicts/latest-*.json` or an older verdict file as the result.
**LLM:** read the verdict JSON from the gate's stdout only; judge soft flags; write the verdict message. Never override a hard fail.

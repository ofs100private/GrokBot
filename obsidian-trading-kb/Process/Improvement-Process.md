---
tags: [process, improvement]
ledger: n/a
asOf: "2026-09-30T19:55:00+03:00"
---
# Improvement process

Token-lean loop: **Python writes Job-Runs**; LLM only for weekly rollup when fails / open tickets exist.

## When to open a ticket

Open `Process/Improvements/YYYY-MM-DD-slug.md` when **any** of:

1. Job-run `status: fail`
2. Frontmatter `improvement_needed: true`
3. Actual outcome unexpected vs bot mandate (Fear/No Buy place, wrong ledger, invented PnL, missing QA, etc.)

## Ticket fields

| Field | Notes |
|-------|-------|
| symptom | One sentence |
| evidence | Wikilink to Job-Runs note + audit path |
| root cause | `unknown` OK until investigated |
| proposed fix | Concrete when known |
| owner bot | `Trader_Classic` / `Trader_momentum` / `daily_brief` / `QA_Bot` / `Daily_Trader` / `Breakout_TA` / `Git` / `Chief_of_Staff` |
| priority | P1 (money/QA hard-fail) · P2 · P3 |
| status | `open` / `done` |

## Weekly rollup (`obsidian-kb-weekly-rollup`)

1. Scan `Job-Runs/**` for `status: fail` (and recent `partial` if noisy).
2. Scan `Process/Improvements/` for `status: open`.
3. Emit **top 3 improvements** into the weekly journal / CoS state (see [[Process/Weekly-Rollup-Checklist]]).
4. Do **not** invent run_ids or PnL. Cite Job-Runs notes only.

## Status vocabulary (Job-Runs)

| Status | Meaning |
|--------|---------|
| `success` | Job completed; QA PASS when gated |
| `fail` | QA FAIL or hard error |
| `blocked` | Fear / No Buy / mandate block and no place |
| `partial` | Incomplete artifact / missing QA / truncated |
| `other` | Explicit non-standard outcome |

## Writer

```bash
python3 /workspace/obsidian-trading-kb/Scripts/write_job_run.py --stdin < spec.json
python3 /workspace/obsidian-trading-kb/Scripts/write_job_run.py --backfill --since 20260916
```

Ledger: portfolio claims stay **mirror-A**; Job-Runs may cite **keys-B** audits when labeled.

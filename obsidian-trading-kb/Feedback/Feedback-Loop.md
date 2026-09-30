---
tags: [feedback, qa]
ledger: mirror-A
asOf: "2026-09-30T19:55:00+03:00"
---
# Feedback loop

## Purpose

Close the loop between vault claims → QA Bot → CoS → traders, without inventing PnL. Every bot job also lands a **Job-Runs** note so expected vs actual is auditable.

## Cadence

1. **Refresh `_raw/`** from afternoon/morning sidecars (Classic A + Momentum A only for equity/cash).
2. **Rebuild notes** (`_raw/build_vault.py`) — every note gets `ledger: mirror-A` or `ledger: keys-B` (or explicit `parent-SSO` for personal).
3. **Write Job-Runs** (`Scripts/write_job_run.py`) — one MD per bot job (args or stdin JSON). Backfill: `--backfill --since YYYYMMDD`.
4. **Improvement tickets** when `status=fail` / `improvement_needed` / unexpected vs mandate → `Process/Improvements/` (see [[Process/Improvement-Process]]).
5. **Write QA pack** → `_raw/qa-pack-obsidian-kb.json` (numbers) and/or `_raw/qa-pack-job-runs.json` (job-run schema light gate).
6. **CoS → QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`): request number-gate and/or job-runs light gate; executor cannot `SendToAgent`.
7. On **FAIL**: fix deviation codes; never mark done until PASS. Open/keep improvement tickets.
8. On **PASS**: optional lessons into `Journals/` + Momentum `trading-lessons` path.
9. **Weekly rollup** (`obsidian-kb-weekly-rollup`): scan open tickets + job fails → top 3 improvements ([[Process/Weekly-Rollup-Checklist]]). LLM only when fails/tickets exist.

## Hard rules in every loop

- Classic/Momentum equity = Mirror A sidecars only
- Classic closed moves = parent JSON (`isMirrorTrade` preferred)
- `classic-keys-B-closed-trades.csv` = keys-B only
- `fully_loaded = netProfit - fees`
- Job-Runs may cite keys-B audits if `ledger: keys-B` is labeled; no secrets in notes
- Status vocabulary exact: `success` | `fail` | `blocked` | `partial` | `other`

## Current pack

- QA pack (numbers): `_raw/qa-pack-obsidian-kb.json`
- QA pack (job-runs): `_raw/qa-pack-job-runs.json`
- Last verdict (numbers): `_raw/qa-verdict-obsidian-kb.json`
- Plan baseline capital: **$20,649.39** → see [[01-Plan-70k]]
- Job-Runs index: [[Indexes/MOC-Job-Runs]]

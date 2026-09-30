---
tags: [process, checklist, weekly]
ledger: n/a
asOf: "2026-09-30T19:55:00+03:00"
---
# Weekly rollup checklist · `obsidian-kb-weekly-rollup`

Server-side CoS prompt lives elsewhere — use this vault checklist when updating state.

## Preflight

- [ ] Mirror vault present: `/workspace/obsidian-trading-kb` ↔ `/workspace/GrokBot/obsidian-trading-kb`
- [ ] No secrets in new Job-Runs notes
- [ ] Portfolio equity/cash claims still **mirror-A** only

## Scan (token-lean — prefer Python / ripgrep)

1. [ ] List Job-Runs with `status: fail` in last 7–14 days
2. [ ] List `Process/Improvements/` with `status: open`
3. [ ] Count Job-Runs by folder + status (optional: `_raw/qa-pack-job-runs.json`)

## Produce

1. [ ] **Top 3 improvements** (open tickets + fails) — title, owner bot, evidence wikilink
2. [ ] One Job-Run note for this rollup itself (`job: obsidian-kb-weekly-rollup`, bot `Chief_of_Staff`) via `Scripts/write_job_run.py`
3. [ ] Update [[Feedback/Feedback-Loop]] asOf if cadence changed
4. [ ] CoS `UpdateState` with top 3 + paths (server-side)

## Skip LLM when

- Zero fails **and** zero open improvement tickets → write a short success Job-Run only; no prose rollup.

## QA light gate (after Job-Runs changes)

Ask QA Bot for: file exists, schema fields present, **no invented run_ids**. Pack: `_raw/qa-pack-job-runs.json`.

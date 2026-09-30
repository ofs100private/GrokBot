---
tags: [index, readme]
ledger: mirror-A
asOf: "2026-09-30T15:53:30+03:00"
slot: afternoon_1530
---
# Obsidian Trading KB

Vault for Ofer Sasson trading books. Times in **Asia/Jerusalem (IDT)**.

## Ledger rules

| Tag | Meaning |
|-----|---------|
| `mirror-A` | Classic Mirror A `11368142` or Momentum Mirror A `11630170` reporting truth |
| `keys-B` | Execution keys books — move notes only; **never** equity/cash totals |
| `parent-SSO` | Parent personal closes (`isMirrorTrade:false`) — not Classic/Momentum book |

**REJECT** `user-OfersClaw5` / Momentum keys MCP equity as Classic or Momentum reporting.

**Classic CLOSED moves** = `_raw/parent-etoro-closed-20260501.json` (prefer `isMirrorTrade:true`).  
**NOT** `_raw/classic-keys-B-closed-trades.csv` (OfersClaw5 keys-B; 0 pid overlap with parent).

**fully_loaded** = `netProfit - fees` (do not invent PnL).

## Start here

- [[Home]] — dashboard
- [[01-Plan-70k]] — path from Mirror A capital **$20,649.39** → $70k
- [[Indexes/MOC-Vault]] · [[Indexes/MOC-Trades]] · [[Indexes/MOC-Portfolios]] · [[Indexes/MOC-Job-Runs]]
- [[Ledgers/Ledger-Truth]]
- [[Feedback/Feedback-Loop]]
- [[Process/Improvement-Process]] · [[Process/Weekly-Rollup-Checklist]]
- QA pack (numbers): `_raw/qa-pack-obsidian-kb.json`
- QA pack (job-runs): `_raw/qa-pack-job-runs.json` → CoS asks QA Bot `498c78db-a027-4f2c-8126-3c2be6f0a4bb` light gate

## Job-Runs

Every bot job → one note under `Job-Runs/` with bot, job, Asia/Jerusalem time, status (`success|fail|blocked|partial|other`), and full audit (JSON fence or path + key fields).

```bash
# Single run (CLI)
python3 Scripts/write_job_run.py \
  --bot Trader_Classic --job classic-rsi-1h-auto \
  --run-id classic-rsi-auto-YYYYMMDD-HHMMSS-xxxxxxxx \
  --status success --started-at '2026-09-30T19:44:43+03:00' \
  --ledger keys-B --audit-path /workspace/classic_rsi/audit/...json \
  --qa-verdict PASS --folder Classic-RSI

# Or stdin JSON
echo '{"bot":"daily_brief","job":"daily-brief-1530","run_id":"...","status":"fail",...}' \
  | python3 Scripts/write_job_run.py --stdin

# Backfill from real audits only
python3 Scripts/write_job_run.py --backfill --since 20260916
```

## Snapshot (2026-09-30T15:53:30+03:00)

| Book | Equity | Cash | Ledger |
|------|--------|------|--------|
| Classic A `11368142` | $12,841.61 | $7,285.54 | mirror-A |
| Momentum A `11630170` | $7,807.78 | $549.77 | mirror-A |
| **Combined start (70k plan)** | **$20,649.39** | — | mirror-A |

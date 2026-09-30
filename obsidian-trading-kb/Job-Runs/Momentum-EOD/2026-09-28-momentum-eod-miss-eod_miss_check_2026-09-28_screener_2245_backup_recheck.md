---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-28_screener_2245_backup_recheck
started_at: "2026-09-28T22:45:00+03:00"
finished_at: "2026-09-28T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-28_screener_2245_backup_recheck.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-28_screener_2245_backup_recheck`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-28 22:45 IDT → 2026-09-28 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-28_screener_2245_backup_recheck.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-09-28",
  "now_il": "2026-09-28T22:51:17.359596+03:00",
  "screener_miss": true,
  "pm_miss": true,
  "any_miss": true,
  "next_job": "position_manager",
  "screener": {
    "day": "2026-09-28",
    "now_il": "2026-09-28T22:51:17.359596+03:00",
    "has_eod_screener_action": false,
    "actions": [],
    "run_starts": [],
    "reason": "EOD_SCREENER_MISSED",
    "deviation_code": "EOD_SCREENER_MISSED"
  },
  "position_manager": {
    "day": "2026-09-28",
    "now_il": "2026-09-28T22:51:17.359596+03:00",
    "has_eod_pm_action": false,
    "actions": [],
    "run_starts": [],
    "run_ends": [],
    "reason": "EOD_PM_MISSED",
    "deviation_code": "EOD_PM_MISSED"
  }
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

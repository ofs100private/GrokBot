---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-05_manual_1600
started_at: "2026-10-05T22:45:00+03:00"
finished_at: "2026-10-05T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-05_manual_1600.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-05_manual_1600`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-05 22:45 IDT → 2026-10-05 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-05_manual_1600.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-05",
  "now_il": "2026-10-05T16:05:25.787135+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-10-05",
    "now_il": "2026-10-05T16:05:25.787135+03:00",
    "has_eod_screener_action": false,
    "actions": [],
    "run_starts": [],
    "reason": "before_watch_window"
  },
  "position_manager": {
    "day": "2026-10-05",
    "now_il": "2026-10-05T16:05:25.787135+03:00",
    "has_eod_pm_action": false,
    "actions": [],
    "run_starts": [],
    "run_ends": [],
    "reason": "before_watch_window"
  },
  "manual_early_eod": {
    "source": "manual_1600",
    "pm_run_id": "posmgr-20261005-160439-6c9fb4ac",
    "screener_run_id": "screener-20261005-160452-88488e84",
    "pm_ts_il": "2026-10-05T16:04:39+03:00",
    "screener_action_ts_il": "2026-10-05T16:05:03+03:00",
    "note": "Early manual EOD before 22:40. Miss gate watch window starts 22:46. Screener ACTION BUY at 16:05 will count toward ≤22:50 gate later via screener_actions_by_deadline (all-day ACTION).",
    "screener_miss_expected_false_after_2246": true
  }
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

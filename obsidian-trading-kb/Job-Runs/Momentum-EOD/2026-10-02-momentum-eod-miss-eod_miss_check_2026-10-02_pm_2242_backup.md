---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-02_pm_2242_backup
started_at: "2026-10-02T22:45:00+03:00"
finished_at: "2026-10-02T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-02_pm_2242_backup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-02_pm_2242_backup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-02 22:45 IDT → 2026-10-02 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-02_pm_2242_backup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-02",
  "now_il": "2026-10-02T22:51:38.831445+03:00",
  "source": "22:42 backup (fired ~22:50 IL)",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "decision": "QUIET_IDEMPOTENT",
  "reason": "pm_already_ran",
  "position_manager": {
    "has_eod_pm_action": true,
    "run_ids": [
      "posmgr-20261002-224536-8538561e",
      "posmgr-20261002-224543-cc09a0bc",
      "posmgr-20261002-224607-054f61ae"
    ],
    "first_run_start_il": "2026-10-02T22:45:36.373917+03:00",
    "primary_actions": [
      "XLK TRAIL_SL",
      "CRWD MOVE_SL_BREAKEVEN",
      "VTRS HOLD",
      "P HOLD"
    ],
    "reason": "pm_already_ran"
  },
  "screener": {
    "has_eod_screener_action": true,
    "run_id": "screener-20261002-224453-e769fabd",
    "action_il": "2026-10-02T22:45:04.133898+03:00",
    "action": "HALT EVENT_VOL_FREEZE (NFP)",
    "reason": "screener_already_ran — 22:45 backup / 22:50 watchdog own screener; this backup does not re-run"
  },
  "note": "Primary 22:40 PM already owned tonight. No catch-up. No WakeParent."
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

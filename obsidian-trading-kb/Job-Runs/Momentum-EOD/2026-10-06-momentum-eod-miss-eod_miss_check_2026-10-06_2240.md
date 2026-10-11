---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-06_2240
started_at: "2026-10-06T22:45:00+03:00"
finished_at: "2026-10-06T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-06_2240.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-06_2240`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-06 22:45 IDT → 2026-10-06 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-06_2240.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-06",
  "now_il": "2026-10-06T22:43:34.593313+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-10-06",
    "now_il": "2026-10-06T22:43:34.593313+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-10-06T22:42:42.924828+03:00",
        "action": "BUY",
        "symbol": "MRVL"
      },
      {
        "ts_il": "2026-10-06T22:42:42.924875+03:00",
        "action": "BUY",
        "symbol": "APA"
      },
      {
        "ts_il": "2026-10-06T22:42:42.924927+03:00",
        "action": "BUY",
        "symbol": "ZBRA"
      },
      {
        "ts_il": "2026-10-06T22:42:42.924961+03:00",
        "action": "BUY",
        "symbol": "XLK"
      }
    ],
    "run_starts": [
      "2026-10-06T22:42:26.860436+03:00"
    ],
    "reason": "before_watch_window"
  },
  "position_manager": {
    "day": "2026-10-06",
    "now_il": "2026-10-06T22:43:34.593313+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-10-06T22:42:02.187174+03:00",
        "action": "HOLD",
        "symbol": "AAPL"
      },
      {
        "ts_il": "2026-10-06T22:42:02.361700+03:00",
        "action": "HOLD",
        "symbol": "DE"
      },
      {
        "ts_il": "2026-10-06T22:42:02.487709+03:00",
        "action": "HOLD",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-06T22:42:02.680625+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-06T22:42:03.006210+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-06T22:42:03.167666+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-06T22:42:03.299917+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-06T22:42:03.548552+03:00",
        "action": "HOLD",
        "symbol": "NDSN"
      }
    ],
    "run_starts": [
      "2026-10-06T22:42:01.787894+03:00"
    ],
    "run_ends": [
      "2026-10-06T22:42:03.720550+03:00"
    ],
    "reason": "before_watch_window"
  }
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

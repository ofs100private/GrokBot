---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-08_pm_2242_backup
started_at: "2026-10-08T22:45:00+03:00"
finished_at: "2026-10-08T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-08_pm_2242_backup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-08_pm_2242_backup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-08 22:45 IDT → 2026-10-08 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-08_pm_2242_backup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-08",
  "now_il": "2026-10-08T23:45:16.697822+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-10-08",
    "now_il": "2026-10-08T23:45:16.697822+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-10-08T22:02:07.344417+03:00",
        "action": "BUY",
        "symbol": "HPQ"
      },
      {
        "ts_il": "2026-10-08T22:02:07.344478+03:00",
        "action": "BUY",
        "symbol": "ZBRA"
      },
      {
        "ts_il": "2026-10-08T22:02:07.344519+03:00",
        "action": "BUY",
        "symbol": "ANET"
      },
      {
        "ts_il": "2026-10-08T22:02:07.344551+03:00",
        "action": "BUY",
        "symbol": "XLE"
      },
      {
        "ts_il": "2026-10-08T23:38:02.421468+03:00",
        "action": "BUY",
        "symbol": "HPQ"
      },
      {
        "ts_il": "2026-10-08T23:38:02.421511+03:00",
        "action": "BUY",
        "symbol": "ZBRA"
      },
      {
        "ts_il": "2026-10-08T23:38:02.421545+03:00",
        "action": "BUY",
        "symbol": "ANET"
      },
      {
        "ts_il": "2026-10-08T23:38:02.421577+03:00",
        "action": "BUY",
        "symbol": "XLE"
      }
    ],
    "run_starts": [
      "2026-10-08T22:01:51.525241+03:00",
      "2026-10-08T23:37:46.958702+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-10-08",
    "now_il": "2026-10-08T23:45:16.697822+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-10-08T22:01:32.987614+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-08T22:01:33.196283+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-08T22:01:33.381846+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-08T22:01:33.557097+03:00",
        "action": "HOLD",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-08T23:38:30.882227+03:00",
        "action": "HOLD",
        "symbol": "HPQ"
      },
      {
        "ts_il": "2026-10-08T23:38:31.056880+03:00",
        "action": "HOLD",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-08T23:38:31.250144+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-08T23:38:31.412107+03:00",
        "action": "HOLD",
        "symbol": "ANET"
      },
      {
        "ts_il": "2026-10-08T23:38:31.582777+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-08T23:38:31.746261+03:00",
        "action": "HOLD",
        "symbol": "ZBRA"
      },
      {
        "ts_il": "2026-10-08T23:38:31.963900+03:00",
        "action": "HOLD",
        "symbol": "P"
      }
    ],
    "run_starts": [
      "2026-10-08T22:01:32.643754+03:00",
      "2026-10-08T23:38:30.454875+03:00"
    ],
    "run_ends": [
      "2026-10-08T22:01:33.557285+03:00",
      "2026-10-08T23:38:31.964084+03:00"
    ],
    "reason": "pm_already_ran"
  }
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

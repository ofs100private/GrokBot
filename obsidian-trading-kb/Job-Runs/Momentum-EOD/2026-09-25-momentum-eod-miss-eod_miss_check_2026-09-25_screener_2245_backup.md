---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-25_screener_2245_backup
started_at: "2026-09-25T22:45:00+03:00"
finished_at: "2026-09-25T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-25_screener_2245_backup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-25_screener_2245_backup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-25 22:45 IDT → 2026-09-25 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-25_screener_2245_backup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-09-25",
  "now_il": "2026-09-25T22:52:14.395394+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-09-25",
    "now_il": "2026-09-25T22:52:14.395394+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-09-25T22:50:02.808375+03:00",
        "action": "BUY",
        "symbol": "AAPL"
      },
      {
        "ts_il": "2026-09-25T22:50:02.808415+03:00",
        "action": "BUY",
        "symbol": "MET"
      },
      {
        "ts_il": "2026-09-25T22:50:02.808443+03:00",
        "action": "BUY",
        "symbol": "JNJ"
      }
    ],
    "run_starts": [
      "2026-09-25T22:49:37.269739+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-09-25",
    "now_il": "2026-09-25T22:52:14.395394+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-09-25T22:49:07.895402+03:00",
        "action": "HOLD",
        "symbol": "JNJ"
      },
      {
        "ts_il": "2026-09-25T22:49:08.188374+03:00",
        "action": "HOLD",
        "symbol": "TGT"
      },
      {
        "ts_il": "2026-09-25T22:49:08.497707+03:00",
        "action": "HOLD",
        "symbol": "DE"
      },
      {
        "ts_il": "2026-09-25T22:49:08.915356+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-09-25T22:49:09.157724+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-09-25T22:49:09.384663+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-09-25T22:49:09.605726+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-09-25T22:49:09.848323+03:00",
        "action": "HOLD",
        "symbol": "PLTR"
      }
    ],
    "run_starts": [
      "2026-09-25T22:49:07.352710+03:00"
    ],
    "run_ends": [
      "2026-09-25T22:49:10.085252+03:00"
    ],
    "reason": "pm_already_ran"
  },
  "job": "momentum_eod_screener_2245_backup",
  "decision": "idempotent_skip",
  "decision_reason": "has_eod_screener_action; do not double-buy",
  "screener_run_id": "screener-20260925-224937-f841c72c",
  "note": "Primary/backup PM chain owns place-QA; 2245 backup stays quiet"
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

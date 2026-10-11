---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-07_2245_backup
started_at: "2026-10-07T22:45:00+03:00"
finished_at: "2026-10-07T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-07_2245_backup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-07_2245_backup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-07 22:45 IDT → 2026-10-07 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-07_2245_backup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-07",
  "now_il": "2026-10-07T22:56:41.664847+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-10-07",
    "now_il": "2026-10-07T22:56:41.664847+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-10-07T22:45:08.703275+03:00",
        "action": "BUY",
        "symbol": "ZBRA"
      },
      {
        "ts_il": "2026-10-07T22:45:08.703355+03:00",
        "action": "BUY",
        "symbol": "HPQ"
      },
      {
        "ts_il": "2026-10-07T22:45:08.703393+03:00",
        "action": "BUY",
        "symbol": "XOM"
      },
      {
        "ts_il": "2026-10-07T22:45:08.703426+03:00",
        "action": "BUY",
        "symbol": "XLK"
      }
    ],
    "run_starts": [
      "2026-10-07T22:44:50.825275+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-10-07",
    "now_il": "2026-10-07T22:56:41.664847+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-10-07T22:44:36.975864+03:00",
        "action": "MOVE_SL_BREAKEVEN",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-07T22:44:37.124713+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-07T22:44:37.449267+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-07T22:44:37.793445+03:00",
        "action": "HOLD",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-07T22:44:38.007173+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-07T22:44:38.188413+03:00",
        "action": "HOLD",
        "symbol": "NDSN"
      },
      {
        "ts_il": "2026-10-07T22:44:38.376302+03:00",
        "action": "HOLD",
        "symbol": "DE"
      },
      {
        "ts_il": "2026-10-07T22:44:38.571913+03:00",
        "action": "HOLD",
        "symbol": "AAPL"
      },
      {
        "ts_il": "2026-10-07T22:44:38.749330+03:00",
        "action": "HOLD",
        "symbol": "MRVL"
      },
      {
        "ts_il": "2026-10-07T22:44:38.941499+03:00",
        "action": "HOLD",
        "symbol": "ETH"
      }
    ],
    "run_starts": [
      "2026-10-07T22:44:36.650079+03:00"
    ],
    "run_ends": [
      "2026-10-07T22:44:38.941701+03:00"
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

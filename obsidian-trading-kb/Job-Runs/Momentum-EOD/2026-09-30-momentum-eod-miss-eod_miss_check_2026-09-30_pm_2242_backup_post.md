---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-30_pm_2242_backup_post
started_at: "2026-09-30T22:45:00+03:00"
finished_at: "2026-09-30T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-30_pm_2242_backup_post.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-30_pm_2242_backup_post`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-30 22:45 IDT → 2026-09-30 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-30_pm_2242_backup_post.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-09-30",
  "now_il": "2026-09-30T22:51:17.329380+03:00",
  "source": "22:42 backup catch-up POST",
  "screener": {
    "day": "2026-09-30",
    "now_il": "2026-09-30T22:51:17.329380+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-09-30T22:45:29.703274+03:00",
        "action": "BUY",
        "symbol": "RVTY"
      },
      {
        "ts_il": "2026-09-30T22:45:29.703323+03:00",
        "action": "BUY",
        "symbol": "FTNT"
      },
      {
        "ts_il": "2026-09-30T22:45:29.703361+03:00",
        "action": "BUY",
        "symbol": "NDSN"
      },
      {
        "ts_il": "2026-09-30T22:45:29.703397+03:00",
        "action": "BUY",
        "symbol": "XLK"
      }
    ],
    "run_starts": [
      "2026-09-30T22:45:13.279677+03:00"
    ]
  },
  "position_manager": {
    "day": "2026-09-30",
    "now_il": "2026-09-30T22:51:17.329380+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-09-30T22:44:59.835007+03:00",
        "action": "HOLD",
        "symbol": "AAPL"
      },
      {
        "ts_il": "2026-09-30T22:45:00.013810+03:00",
        "action": "CLOSE",
        "symbol": "JNJ"
      },
      {
        "ts_il": "2026-09-30T22:45:00.234887+03:00",
        "action": "HOLD",
        "symbol": "DE"
      },
      {
        "ts_il": "2026-09-30T22:45:00.460749+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-09-30T22:45:00.588418+03:00",
        "action": "HOLD",
        "symbol": "FTNT"
      },
      {
        "ts_il": "2026-09-30T22:45:00.758544+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-09-30T22:45:00.918661+03:00",
        "action": "MOVE_SL_BREAKEVEN",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-09-30T22:45:01.076658+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-09-30T22:45:01.304066+03:00",
        "action": "HOLD",
        "symbol": "NDSN"
      }
    ],
    "run_starts": [
      "2026-09-30T22:44:59.455815+03:00"
    ],
    "run_ends": [
      "2026-09-30T22:45:01.304252+03:00"
    ]
  },
  "pending": [
    "JNJ CLOSE",
    "CRWD BE",
    "RVTY BUY"
  ],
  "keys_mcp": "BROKEN_MIXED_AUTH user-Momentum-HHHGDTJ",
  "mirror_A_cash": 549.77
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

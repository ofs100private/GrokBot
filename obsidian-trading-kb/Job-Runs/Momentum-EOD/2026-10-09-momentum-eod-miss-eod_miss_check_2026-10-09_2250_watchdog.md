---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-09_2250_watchdog
started_at: "2026-10-09T22:45:00+03:00"
finished_at: "2026-10-09T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-09_2250_watchdog.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-09_2250_watchdog`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-09 22:45 IDT → 2026-10-09 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-09_2250_watchdog.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "slot": "EOD_2250_WATCHDOG",
  "day": "2026-10-09",
  "now_il": "2026-10-09T23:02:58.795346+03:00",
  "nyse_session": true,
  "night_status": {
    "day": "2026-10-09",
    "now_il": "2026-10-09T23:02:58.795371+03:00",
    "screener_miss": false,
    "pm_miss": false,
    "any_miss": false,
    "next_job": null,
    "screener": {
      "day": "2026-10-09",
      "now_il": "2026-10-09T23:02:58.795371+03:00",
      "has_eod_screener_action": true,
      "actions": [
        {
          "ts_il": "2026-10-09T22:47:29.520952+03:00",
          "action": "BUY",
          "symbol": "ZBRA"
        },
        {
          "ts_il": "2026-10-09T22:47:29.521048+03:00",
          "action": "BUY",
          "symbol": "ANET"
        },
        {
          "ts_il": "2026-10-09T22:47:29.521099+03:00",
          "action": "BUY",
          "symbol": "FCX"
        },
        {
          "ts_il": "2026-10-09T22:47:29.521142+03:00",
          "action": "SKIP",
          "symbol": "USO"
        }
      ],
      "run_starts": [
        "2026-10-09T22:47:16.005110+03:00"
      ],
      "reason": "screener_already_ran"
    },
    "position_manager": {
      "day": "2026-10-09",
      "now_il": "2026-10-09T23:02:58.795371+03:00",
      "has_eod_pm_action": true,
      "actions": [
        {
          "ts_il": "2026-10-09T22:47:03.913432+03:00",
          "action": "HOLD",
          "symbol": "NTAP"
        },
        {
          "ts_il": "2026-10-09T22:47:04.063703+03:00",
          "action": "HOLD",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-10-09T22:47:04.198707+03:00",
          "action": "HOLD",
          "symbol": "ANET"
        },
        {
          "ts_il": "2026-10-09T22:47:04.348412+03:00",
          "action": "HOLD",
          "symbol": "CRWD"
        },
        {
          "ts_il": "2026-10-09T22:47:04.473925+03:00",
          "action": "HOLD",
          "symbol": "ZBRA"
        },
        {
          "ts_il": "2026-10-09T22:47:04.607569+03:00",
          "action": "HOLD",
          "symbol": "P"
        },
        {
          "ts_il": "2026-10-09T22:47:59.734197+03:00",
          "action": "HOLD",
          "symbol": "NTAP"
        },
        {
          "ts_il": "2026-10-09T22:47:59.888236+03:00",
          "action": "HOLD",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-10-09T22:48:00.017426+03:00",
          "action": "HOLD",
          "symbol": "ANET"
        },
        {
          "ts_il": "2026-10-09T22:48:00.154167+03:00",
          "action": "HOLD",
          "symbol": "CRWD"
        },
        {
          "ts_il": "2026-10-09T22:48:00.275348+03:00",
          "action": "HOLD",
          "symbol": "ZBRA"
        },
        {
          "ts_il": "2026-10-09T22:48:00.449469+03:00",
          "action": "HOLD",
          "symbol": "P"
        }
      ],
      "run_starts": [
        "2026-10-09T22:47:03.611720+03:00",
        "2026-10-09T22:47:59.466899+03:00"
      ],
      "run_ends": [
        "2026-10-09T22:47:04.607778+03:00",
        "2026-10-09T22:48:00.449728+03:00"
      ],
      "reason": "pm_already_ran"
    }
  },
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "is_miss": false,
  "is_pm_miss": false,
  "screener_status": "CLEAN",
  "pm_status": "CLEAN",
  "screener_run_id": "screener-20261009-224716-e471b45c",
  "screener_action_ts_il": "2026-10-09T22:47:29.520952+03:00",
  "pm_run_ids": [
    "posmgr-20261009-224703-7a519e60",
    "posmgr-20261009-224759-0df52bf0"
  ],
  "authorize_place": true,
  "authorize_place_scope": "FCX only: BUY real mkt x1 $1000 SL 69.3 fixed, no TP. ZBRA/ANET NOT authorized (DUPLICATE_HOLD_BUY if re-bought).",
  "place_ack_present_for_2026_10_09": true,
  "place_ack_files": [
    "/workspace/momentum_audit/place_ack/eod-20261009-2240-fcx-not-placed.json"
  ],
  "place_ack_summary": {
    "symbol": "FCX",
    "status": "NOT_PLACED",
    "reason": "Auto-review blocked place-trade; approval card interrupted/unanswered; prepare token expired 22:52:04 IL; NYSE closed 23:00 IL"
  },
  "watchdog_flag": null,
  "note": "[REDACTED]",
  "action_taken": "none_quiet"
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-29_watchdog_2250
started_at: "2026-09-29T22:53:04+03:00"
finished_at: "2026-09-29T22:53:04+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-29_watchdog_2250.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-29_watchdog_2250`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-29 22:53 IDT → 2026-09-29 22:53 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-29_watchdog_2250.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "job": "watchdog_2250",
  "asOf_il": "2026-09-29T22:53:04.843092+03:00",
  "nyse_session": "open_weekday",
  "night_status": {
    "day": "2026-09-29",
    "now_il": "2026-09-29T22:53:04.843092+03:00",
    "screener_miss": false,
    "pm_miss": false,
    "any_miss": false,
    "next_job": null,
    "screener": {
      "day": "2026-09-29",
      "now_il": "2026-09-29T22:53:04.843092+03:00",
      "has_eod_screener_action": true,
      "actions": [
        {
          "ts_il": "2026-09-29T22:44:39.324660+03:00",
          "action": "BUY",
          "symbol": "FTNT"
        },
        {
          "ts_il": "2026-09-29T22:44:39.324713+03:00",
          "action": "BUY",
          "symbol": "NDSN"
        },
        {
          "ts_il": "2026-09-29T22:44:39.324745+03:00",
          "action": "BUY",
          "symbol": "LLY"
        }
      ],
      "run_starts": [
        "2026-09-29T22:44:25.920017+03:00"
      ],
      "reason": "screener_already_ran"
    },
    "position_manager": {
      "day": "2026-09-29",
      "now_il": "2026-09-29T22:53:04.843092+03:00",
      "has_eod_pm_action": true,
      "actions": [
        {
          "ts_il": "2026-09-29T22:46:23.174549+03:00",
          "action": "HOLD",
          "symbol": "AAPL"
        },
        {
          "ts_il": "2026-09-29T22:46:23.397677+03:00",
          "action": "HOLD",
          "symbol": "JNJ"
        },
        {
          "ts_il": "2026-09-29T22:46:23.607965+03:00",
          "action": "HOLD",
          "symbol": "DE"
        },
        {
          "ts_il": "2026-09-29T22:46:23.912405+03:00",
          "action": "HOLD",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-09-29T22:46:24.063462+03:00",
          "action": "HOLD",
          "symbol": "FTNT"
        },
        {
          "ts_il": "2026-09-29T22:46:24.242582+03:00",
          "action": "MOVE_SL_BREAKEVEN",
          "symbol": "VTRS"
        },
        {
          "ts_il": "2026-09-29T22:46:24.578303+03:00",
          "action": "HOLD",
          "symbol": "P"
        }
      ],
      "run_starts": [
        "2026-09-29T22:46:22.882239+03:00"
      ],
      "run_ends": [
        "2026-09-29T22:46:24.753904+03:00"
      ],
      "reason": "pm_already_ran"
    }
  },
  "verdict": "CLEAN",
  "action": "stay_quiet",
  "note": "Screener ACTION 22:44:39 + PM RUN 22:46 via 22:42 backup; no EOD_SCREENER_MISSED / EOD_PM_MISSED. place-QA authorize VTRS BE + NDSN pending execution."
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a; verdict=CLEAN

## Improvement ticket

_None — run matched mandate / QA expectations._

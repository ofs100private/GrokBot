---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-24_pm
started_at: "2026-09-24T22:45:00+03:00"
finished_at: "2026-09-24T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-24_pm.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-24_pm`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-24 22:45 IDT → 2026-09-24 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-24_pm.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "night_status": {
    "day": "2026-09-24",
    "now_il": "2026-09-24T22:44:58.042590+03:00",
    "screener_miss": false,
    "pm_miss": false,
    "any_miss": false,
    "next_job": null,
    "screener": {
      "day": "2026-09-24",
      "now_il": "2026-09-24T22:44:58.042590+03:00",
      "has_eod_screener_action": true,
      "actions": [
        {
          "ts_il": "2026-09-24T22:43:50.990438+03:00",
          "action": "BUY",
          "symbol": "P"
        },
        {
          "ts_il": "2026-09-24T22:43:50.990489+03:00",
          "action": "BUY",
          "symbol": "AAPL"
        },
        {
          "ts_il": "2026-09-24T22:43:50.990543+03:00",
          "action": "BUY",
          "symbol": "JNJ"
        }
      ],
      "run_starts": [
        "2026-09-24T22:43:22.732217+03:00"
      ],
      "reason": "before_watch_window"
    },
    "position_manager": {
      "day": "2026-09-24",
      "now_il": "2026-09-24T22:44:58.042590+03:00",
      "has_eod_pm_action": true,
      "actions": [
        {
          "ts_il": "2026-09-24T22:42:55.447804+03:00",
          "action": "HOLD",
          "symbol": "JNJ"
        },
        {
          "ts_il": "2026-09-24T22:42:55.700807+03:00",
          "action": "HOLD",
          "symbol": "TGT"
        },
        {
          "ts_il": "2026-09-24T22:42:55.972420+03:00",
          "action": "HOLD",
          "symbol": "DE"
        },
        {
          "ts_il": "2026-09-24T22:42:56.252558+03:00",
          "action": "HOLD",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-09-24T22:42:56.521727+03:00",
          "action": "HOLD",
          "symbol": "VTRS"
        },
        {
          "ts_il": "2026-09-24T22:42:56.729031+03:00",
          "action": "HOLD",
          "symbol": "CRWD"
        },
        {
          "ts_il": "2026-09-24T22:42:56.984694+03:00",
          "action": "HOLD",
          "symbol": "PLTR"
        }
      ],
      "run_starts": [
        "2026-09-24T22:42:54.913456+03:00"
      ],
      "run_ends": [
        "2026-09-24T22:42:57.202405+03:00"
      ],
      "reason": "before_watch_window"
    }
  },
  "actions_by_2250_n": 3,
  "miss": [
    false,
    {
      "day": "2026-09-24",
      "now_il": "2026-09-24T22:44:58.043654+03:00",
      "has_eod_screener_action": true,
      "actions": [
        {
          "ts_il": "2026-09-24T22:43:50.990438+03:00",
          "action": "BUY",
          "symbol": "P"
        },
        {
          "ts_il": "2026-09-24T22:43:50.990489+03:00",
          "action": "BUY",
          "symbol": "AAPL"
        },
        {
          "ts_il": "2026-09-24T22:43:50.990543+03:00",
          "action": "BUY",
          "symbol": "JNJ"
        }
      ],
      "run_starts": [
        "2026-09-24T22:43:22.732217+03:00"
      ],
      "reason": "before_watch_window"
    }
  ],
  "asOf": "2026-09-24T22:44:58.042577+03:00"
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-09_2240
started_at: "2026-10-09T22:48:32+03:00"
finished_at: "2026-10-09T22:48:32+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-09_2240.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-09_2240`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-09 22:48 IDT → 2026-10-09 22:48 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-09_2240.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "slot": "EOD_2240",
  "ts_il": "2026-10-09T22:48:32.007428+03:00",
  "night_status": {
    "day": "2026-10-09",
    "now_il": "2026-10-09T22:48:32.053892+03:00",
    "screener_miss": false,
    "pm_miss": false,
    "any_miss": false,
    "next_job": null,
    "screener": {
      "day": "2026-10-09",
      "now_il": "2026-10-09T22:48:32.053892+03:00",
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
      "now_il": "2026-10-09T22:48:32.053892+03:00",
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
  "is_miss": true,
  "is_pm_miss": true,
  "screener_ran_tonight": true,
  "pm_ran_tonight": true
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-09-28_post_catchup
started_at: "2026-09-28T22:45:00+03:00"
finished_at: "2026-09-28T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-09-28_post_catchup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-09-28_post_catchup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-09-28 22:45 IDT → 2026-09-28 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-09-28_post_catchup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-09-28",
  "now_il": "2026-09-28T22:52:31.072890+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-09-28",
    "now_il": "2026-09-28T22:52:31.072890+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-09-28T22:52:07.341273+03:00",
        "action": "BUY",
        "symbol": "FTNT"
      },
      {
        "ts_il": "2026-09-28T22:52:07.341322+03:00",
        "action": "BUY",
        "symbol": "JNJ"
      },
      {
        "ts_il": "2026-09-28T22:52:07.341353+03:00",
        "action": "BUY",
        "symbol": "LLY"
      }
    ],
    "run_starts": [
      "2026-09-28T22:51:53.365084+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-09-28",
    "now_il": "2026-09-28T22:52:31.072890+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-09-28T22:52:20.882105+03:00",
        "action": "HOLD",
        "symbol": "AAPL"
      },
      {
        "ts_il": "2026-09-28T22:52:21.066416+03:00",
        "action": "HOLD",
        "symbol": "JNJ"
      },
      {
        "ts_il": "2026-09-28T22:52:21.254235+03:00",
        "action": "HOLD",
        "symbol": "TGT"
      },
      {
        "ts_il": "2026-09-28T22:52:21.506954+03:00",
        "action": "HOLD",
        "symbol": "DE"
      },
      {
        "ts_il": "2026-09-28T22:52:21.650507+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-09-28T22:52:22.069076+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-09-28T22:52:22.247901+03:00",
        "action": "HOLD",
        "symbol": "PLTR"
      }
    ],
    "run_starts": [
      "2026-09-28T22:52:20.507023+03:00"
    ],
    "run_ends": [
      "2026-09-28T22:52:22.427107+03:00"
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

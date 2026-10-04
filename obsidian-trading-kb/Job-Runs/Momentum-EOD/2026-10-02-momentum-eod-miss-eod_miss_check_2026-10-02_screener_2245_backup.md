---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-02_screener_2245_backup
started_at: "2026-10-02T22:45:00+03:00"
finished_at: "2026-10-02T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-02_screener_2245_backup.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-02_screener_2245_backup`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-02 22:45 IDT → 2026-10-02 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-02_screener_2245_backup.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-02",
  "now_il": "2026-10-02T22:48:51.476667+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "screener": {
    "day": "2026-10-02",
    "now_il": "2026-10-02T22:48:51.476667+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-10-02T22:44:59.780888+03:00",
        "action": "HALT",
        "symbol": null
      },
      {
        "ts_il": "2026-10-02T22:44:59.780928+03:00",
        "action": "SKIP",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-02T22:44:59.780960+03:00",
        "action": "SKIP",
        "symbol": "ANET"
      },
      {
        "ts_il": "2026-10-02T22:44:59.780986+03:00",
        "action": "SKIP",
        "symbol": "FFIV"
      },
      {
        "ts_il": "2026-10-02T22:44:59.781009+03:00",
        "action": "SKIP",
        "symbol": "NDSN"
      },
      {
        "ts_il": "2026-10-02T22:44:59.781032+03:00",
        "action": "SKIP",
        "symbol": "XOM"
      },
      {
        "ts_il": "2026-10-02T22:45:04.133898+03:00",
        "action": "HALT",
        "symbol": null
      },
      {
        "ts_il": "2026-10-02T22:45:04.133945+03:00",
        "action": "SKIP",
        "symbol": "NTAP"
      },
      {
        "ts_il": "2026-10-02T22:45:04.133979+03:00",
        "action": "SKIP",
        "symbol": "ANET"
      },
      {
        "ts_il": "2026-10-02T22:45:04.134007+03:00",
        "action": "SKIP",
        "symbol": "FFIV"
      },
      {
        "ts_il": "2026-10-02T22:45:04.134031+03:00",
        "action": "SKIP",
        "symbol": "NDSN"
      },
      {
        "ts_il": "2026-10-02T22:45:04.134062+03:00",
        "action": "SKIP",
        "symbol": "XOM"
      }
    ],
    "run_starts": [
      "2026-10-02T22:44:47.967117+03:00",
      "2026-10-02T22:44:53.139986+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-10-02",
    "now_il": "2026-10-02T22:48:51.476667+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-10-02T22:45:36.697447+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-02T22:45:36.830958+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-02T22:45:36.928025+03:00",
        "action": "HOLD",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-02T22:45:37.001170+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-02T22:45:43.999063+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-02T22:45:44.145108+03:00",
        "action": "MOVE_SL_BREAKEVEN",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-02T22:45:44.219718+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-02T22:46:07.681211+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-02T22:46:07.838166+03:00",
        "action": "MOVE_SL_BREAKEVEN",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-02T22:46:07.944207+03:00",
        "action": "HOLD",
        "symbol": "P"
      }
    ],
    "run_starts": [
      "2026-10-02T22:45:36.373917+03:00",
      "2026-10-02T22:45:43.616845+03:00",
      "2026-10-02T22:46:07.365065+03:00"
    ],
    "run_ends": [
      "2026-10-02T22:45:37.001357+03:00",
      "2026-10-02T22:45:44.219894+03:00",
      "2026-10-02T22:46:07.944367+03:00"
    ],
    "reason": "pm_already_ran"
  },
  "source": "22:45 screener backup",
  "note": "Idempotent QUIET: screener-20261002-224453-e769fabd ACTION HALT EVENT_VOL_FREEZE (NFP) at 2026-10-02T22:44:59.780888+03:00 IDT (≤22:50). 0 buys HEALTHY universe_n=520. No double-run. any_miss=False next_job=None."
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

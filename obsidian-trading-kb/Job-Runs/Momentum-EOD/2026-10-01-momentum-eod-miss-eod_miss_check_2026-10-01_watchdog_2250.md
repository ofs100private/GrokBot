---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-01_watchdog_2250
started_at: "2026-10-01T22:45:00+03:00"
finished_at: "2026-10-01T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-01_watchdog_2250.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-01_watchdog_2250`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-01 22:45 IDT → 2026-10-01 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-01_watchdog_2250.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-01",
  "now_il": "2026-10-01T22:58:08.810667+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "soft_nudge": {
    "nudge": false,
    "reason": "within_2m_or_parse",
    "pm_end": "2026-10-01T22:47:19.196149+03:00",
    "scr_start": "2026-10-01T22:47:11.335290+03:00"
  },
  "screener": {
    "day": "2026-10-01",
    "now_il": "2026-10-01T22:58:08.810667+03:00",
    "has_eod_screener_action": true,
    "actions": [
      {
        "ts_il": "2026-10-01T22:47:22.190514+03:00",
        "action": "HALT",
        "symbol": null
      },
      {
        "ts_il": "2026-10-01T22:47:22.190554+03:00",
        "action": "SKIP",
        "symbol": "FTNT"
      },
      {
        "ts_il": "2026-10-01T22:47:22.190584+03:00",
        "action": "SKIP",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-01T22:47:22.190615+03:00",
        "action": "SKIP",
        "symbol": "NDSN"
      },
      {
        "ts_il": "2026-10-01T22:47:22.190640+03:00",
        "action": "SKIP",
        "symbol": "NVDA"
      },
      {
        "ts_il": "2026-10-01T22:47:22.190662+03:00",
        "action": "SKIP",
        "symbol": "JCI"
      }
    ],
    "run_starts": [
      "2026-10-01T22:47:11.335290+03:00"
    ],
    "reason": "screener_already_ran"
  },
  "position_manager": {
    "day": "2026-10-01",
    "now_il": "2026-10-01T22:58:08.810667+03:00",
    "has_eod_pm_action": true,
    "actions": [
      {
        "ts_il": "2026-10-01T22:47:18.652888+03:00",
        "action": "HOLD",
        "symbol": "XLK"
      },
      {
        "ts_il": "2026-10-01T22:47:18.745597+03:00",
        "action": "HOLD",
        "symbol": "FTNT"
      },
      {
        "ts_il": "2026-10-01T22:47:18.857656+03:00",
        "action": "HOLD",
        "symbol": "VTRS"
      },
      {
        "ts_il": "2026-10-01T22:47:18.965587+03:00",
        "action": "MOVE_SL_BREAKEVEN",
        "symbol": "CRWD"
      },
      {
        "ts_il": "2026-10-01T22:47:19.044511+03:00",
        "action": "HOLD",
        "symbol": "P"
      },
      {
        "ts_il": "2026-10-01T22:47:19.195998+03:00",
        "action": "HOLD",
        "symbol": "NDSN"
      }
    ],
    "run_starts": [
      "2026-10-01T22:47:18.418465+03:00"
    ],
    "run_ends": [
      "2026-10-01T22:47:19.196149+03:00"
    ],
    "reason": "pm_already_ran"
  },
  "night_status": {
    "day": "2026-10-01",
    "now_il": "2026-10-01T22:58:08.810667+03:00",
    "screener_miss": false,
    "pm_miss": false,
    "any_miss": false,
    "next_job": null,
    "screener": {
      "day": "2026-10-01",
      "now_il": "2026-10-01T22:58:08.810667+03:00",
      "has_eod_screener_action": true,
      "actions": [
        {
          "ts_il": "2026-10-01T22:47:22.190514+03:00",
          "action": "HALT",
          "symbol": null
        },
        {
          "ts_il": "2026-10-01T22:47:22.190554+03:00",
          "action": "SKIP",
          "symbol": "FTNT"
        },
        {
          "ts_il": "2026-10-01T22:47:22.190584+03:00",
          "action": "SKIP",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-10-01T22:47:22.190615+03:00",
          "action": "SKIP",
          "symbol": "NDSN"
        },
        {
          "ts_il": "2026-10-01T22:47:22.190640+03:00",
          "action": "SKIP",
          "symbol": "NVDA"
        },
        {
          "ts_il": "2026-10-01T22:47:22.190662+03:00",
          "action": "SKIP",
          "symbol": "JCI"
        }
      ],
      "run_starts": [
        "2026-10-01T22:47:11.335290+03:00"
      ],
      "reason": "screener_already_ran"
    },
    "position_manager": {
      "day": "2026-10-01",
      "now_il": "2026-10-01T22:58:08.810667+03:00",
      "has_eod_pm_action": true,
      "actions": [
        {
          "ts_il": "2026-10-01T22:47:18.652888+03:00",
          "action": "HOLD",
          "symbol": "XLK"
        },
        {
          "ts_il": "2026-10-01T22:47:18.745597+03:00",
          "action": "HOLD",
          "symbol": "FTNT"
        },
        {
          "ts_il": "2026-10-01T22:47:18.857656+03:00",
          "action": "HOLD",
          "symbol": "VTRS"
        },
        {
          "ts_il": "2026-10-01T22:47:18.965587+03:00",
          "action": "MOVE_SL_BREAKEVEN",
          "symbol": "CRWD"
        },
        {
          "ts_il": "2026-10-01T22:47:19.044511+03:00",
          "action": "HOLD",
          "symbol": "P"
        },
        {
          "ts_il": "2026-10-01T22:47:19.195998+03:00",
          "action": "HOLD",
          "symbol": "NDSN"
        }
      ],
      "run_starts": [
        "2026-10-01T22:47:18.418465+03:00"
      ],
      "run_ends": [
        "2026-10-01T22:47:19.196149+03:00"
      ],
      "reason": "pm_already_ran"
    }
  },
  "source": "22:50 watchdog",
  "note": "QUIET: screener ACTION HALT EVENT_VOL_FREEZE 22:47:22 IDT (≤22:50); PM posmgr-20261001-224718-5b5735cd ran 22:47. any_miss=false. No catch-up."
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

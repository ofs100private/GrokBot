---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-screener-2026-09-25
started_at: ""
finished_at: ""
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod-2026-09-25-screener-summary.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-screener-2026-09-25`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** n/a → n/a
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod-2026-09-25-screener-summary.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-09-25",
  "job": "eod_pm_2242_backup_catchup",
  "pm_run_id": "posmgr-20260925-224907-7ffd5a55",
  "screener_run_id": "screener-20260925-224937-f841c72c",
  "regime": "HEALTHY",
  "event_vol_freeze": false,
  "universe_n": 520,
  "pm": {
    "holds": [
      "JNJ",
      "TGT",
      "DE",
      "XLK",
      "VTRS",
      "CRWD",
      "P",
      "PLTR"
    ],
    "trail_skip": {
      "symbol": "ETH",
      "reason": "SKIP_NOT_ON_MIRROR_A"
    },
    "closes": [],
    "be": []
  },
  "screener_buys_raw": [
    "AAPL",
    "MET",
    "JNJ"
  ],
  "held_filter_drop": [
    "JNJ"
  ],
  "place_candidates": [
    {
      "symbol": "AAPL",
      "setup": "VCP_SETUP",
      "amount": 900,
      "stopLossRate": 320.79,
      "rs": 86,
      "rvol": 0.44,
      "note": "sized to mirror A cash 904.64 (<1000 pack default)"
    },
    {
      "symbol": "MET",
      "setup": "VCP_SETUP",
      "amount": 1000,
      "stopLossRate": 92.31,
      "rs": 84,
      "rvol": 0.56,
      "note": "blocked pending cash after AAPL; likely GATE_OK_INSUFFICIENT_CASH if AAPL takes ~900"
    }
  ],
  "mirror_A": {
    "id": 11630170,
    "availableCash": 904.64,
    "value": 7840.28
  },
  "miss_cleared": true
}
```

## Expected vs actual

- **Expected:** EOD screener/exec summary written; mandate + cash gates respected.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

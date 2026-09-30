---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-screener-2026-09-24
started_at: ""
finished_at: ""
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod-2026-09-24-screener-summary.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-screener-2026-09-24`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** n/a → n/a
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod-2026-09-24-screener-summary.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "run_id": "screener-20260924-224322-b547bc0e",
  "regime": "HEALTHY",
  "event_freeze": false,
  "universe_n": 520,
  "raw_buys": [
    "P",
    "AAPL",
    "JNJ"
  ],
  "held_drops": [
    {
      "symbol": "JNJ",
      "setup": "VCP_SETUP",
      "rs": 85,
      "rvol": 0.51,
      "stop_loss": 255.59,
      "amount_usd": 1000,
      "day": 1.01,
      "week": 1.73,
      "month": 0.07,
      "drop": "ALREADY_HELD"
    }
  ],
  "executable": [
    {
      "symbol": "P",
      "setup": "VOLUME_BREAKOUT",
      "rs": 95,
      "rvol": 2.17,
      "stop_loss": 108.11,
      "amount_usd": 1000,
      "day": 12.83,
      "week": 26.75,
      "month": 23.18,
      "proposed_amount": 1000
    },
    {
      "symbol": "AAPL",
      "setup": "VCP_SETUP",
      "rs": 85,
      "rvol": 0.35,
      "stop_loss": 316.92,
      "amount_usd": 1000,
      "day": 0.04,
      "week": 0.05,
      "month": 8.79,
      "proposed_amount": 705.72
    }
  ],
  "mirror_A_cash": 1705.72,
  "keys_held": [
    "CRWD",
    "DE",
    "ETH",
    "JNJ",
    "PLTR",
    "TGT",
    "VTRS",
    "XLK"
  ],
  "near_miss": "/workspace/momentum_audit/near-miss-2026-09-24.json",
  "screener_run": "/workspace/momentum_audit/screener-run-screener-20260924-224322-b547bc0e.json",
  "local_screener_qa": "universe_ok TRACE_ok pack_PASS need_QA_Bot_confirm"
}
```

## Expected vs actual

- **Expected:** EOD screener/exec summary written; mandate + cash gates respected.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

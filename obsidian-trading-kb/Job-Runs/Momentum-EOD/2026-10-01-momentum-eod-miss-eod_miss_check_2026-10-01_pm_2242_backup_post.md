---
tags: [job-run]
bot: Trader_momentum
job: momentum-eod
run_id: momentum-eod-miss-eod_miss_check_2026-10-01_pm_2242_backup_post
started_at: "2026-10-01T22:45:00+03:00"
finished_at: "2026-10-01T22:45:00+03:00"
status: success
ledger: keys-B
audit_path: /workspace/momentum_audit/eod_miss_check_2026-10-01_pm_2242_backup_post.json
qa_verdict: n/a
improvement_needed: false
---
# Job run · `momentum-eod-miss-eod_miss_check_2026-10-01_pm_2242_backup_post`

## Summary

- **Bot:** Trader_momentum
- **Job:** momentum-eod
- **Time (Asia/Jerusalem):** 2026-10-01 22:45 IDT → 2026-10-01 22:45 IDT
- **Status:** `success`
- **QA verdict:** n/a
- **Audit path:** `/workspace/momentum_audit/eod_miss_check_2026-10-01_pm_2242_backup_post.json`

## Status

`success` — exact vocabulary: success | fail | blocked | partial | other.

## Full audit

```json
{
  "day": "2026-10-01",
  "now_il": "2026-10-01T22:48:16.714407+03:00",
  "screener_miss": false,
  "pm_miss": false,
  "any_miss": false,
  "next_job": null,
  "source": "22:42 backup catch-up POST",
  "note": "PM posmgr-20261001-224718-5b5735cd + screener screener-20261001-224711-d0b57b81 ACTION 22:47 IDT. CRWD BE pending QA Bot place-QA + eToro Account place_ack.",
  "place_pending": [
    "CRWD MOVE_SL_BREAKEVEN 230.85→242"
  ]
}
```

## Expected vs actual

- **Expected:** EOD miss-check documents whether 22:40/22:45 path ran.
- **Actual:** status=success; qa=n/a

## Improvement ticket

_None — run matched mandate / QA expectations._

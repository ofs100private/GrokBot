---
tags: [improvement, momentum, place-gap]
status: open
owner_bot: Trader_momentum
job: momentum-eod
run_id: place-qa-eod-20260930-jnj-crwd-rvty
priority: P0
created_at: 2026-10-01T00:00:00+03:00
updated_at: 2026-10-04T19:00:12+03:00
ledger: mirror-A
---
# Momentum process improvement — 2026-10-01 (IDT)

**Scope:** process/docs only. CoS does NOT place. No prepare/place in this ticket.

**Book truth:** Mirror A `11630170` ($8k basis). Keys `user-Momentum-HHHGDTJ` = execution ledger B only (currently **BROKEN** mixed Authorization+x-user-key → 422).

## Incident: Wed 2026-09-30 EOD JNJ CLOSE + CRWD BE never filled

### What QA / PM said
- PM `posmgr-20260930-224459` → **CLOSE JNJ** `BELOW_SMA50`; **MOVE_SL_BREAKEVEN CRWD** `HIT_2R` (230.85→242).
- Place-QA `/workspace/momentum_audit/place-qa-eod-20260930-jnj-crwd-rvty.json` @ **22:53 IDT** → `authorize_place_now: [JNJ_CLOSE, CRWD_MOVE_SL_BREAKEVEN]`; RVTY `INSUFFICIENT_CASH` GATE_OK.
- Screener/PM miss checks: **CLEAN** (ACTION ≤22:50).

### Live Mirror A Thu 2026-10-01 ~16:20 IDT (user-etoro SSO)
- Cash still **$549.77** (unchanged) → JNJ **not** closed.
- JNJ still open pos **3584876986**; CRWD SL still **230.85** (not 242).
- No place/fill rows after place-QA in `2026-09-30.jsonl` (file ends at eod_place_gate SKIP @ 22:51).

### Root cause (ranked)
1. **Keys MCP broken (422 mixed auth)** — `eod_place_gate` skipped with `PENDING_QA_BOT_NO_SENDTOAGENT_KEYS_MCP_BROKEN`; Trader cannot place on keys ledger.
2. **Post place-QA handoff gap** — place-QA PASSed @ 22:53 but no Trader_momentum wake / prepare+place ACK; WakeParent text assumed FULL AUTO would fire; it did not.
3. **Watchdog only checks scan/PM ran**, not “authorized risk actions filled” → `CLEAN_STAY_QUIET` hid the miss overnight into Oct 1 morning/afternoon (JNJ still held, cash ~$550).

### Fixes (implement next — no trades here)
| Priority | Fix | Owner |
|---|---|---|
| P0 | Fix `user-Momentum-HHHGDTJ` to **keys-only** (strip OAuth header) OR route ALL Momentum places via a single working Real execution path; document which MCP places. | Ops / MCP config |
| P0 | After place-QA PASS: Trader_momentum **must** prepare+place within same wake; write `place_ack` JSONL (`PLACED` / `WAITING_FOR_MARKET` / `BLOCKED_KEYS_MCP` / `SKIPPED`). | Trader_momentum + skill |
| P0 | Sticky pending: once CLOSE/BE/TRAIL is place-QA PASS, keep on **pending-exec queue** until mirror A confirms (cash↑ / SL changed / position gone) — even if live R later slips <2R. | position_manager EOD chain |
| P1 | Watchdog: fail if `authorize_place_now` exists without matching place_ack within 15m → `EOD_PLACE_NOT_ACKED` (not CLEAN). | eod_miss_check |
| P1 | Cash-block → fresh place-QA loop already in skill; **unblock** by closing soft-gate names first so RVTY (or next pack) can re-QA. | Trader after P0 |
| P2 | Pack sizing / recycle: with cash &lt;~$1000 and ≥8 names, screener BUY pack is advisory until a CLOSE frees ≥$800; log `CASH_RECYCLE_REQUIRED`. | screener / skill |

## Soft-gate reliability (Thu live)
- Yahoo chart SMA50 (ref): **JNJ last 264.74 &lt; SMA50 266.01** → still CLOSE candidate.
- AAPL PnL% ≈ **−3.29%** (mark 331.10 vs 342.39) — near `LOSS_PCT_GE_4`; above SMA50.
- CRWD open PnL still strong (~+$62 / ~+7.8%) but SL not at BE — trail/BE debt.

## Explicit non-actions this ticket
- No prepare-close / place-close / SL patch.
- No RVTY place.
- CoS reports only; Trader places only after CoS/Ofer chain + working execution MCP.

## Update · 2026-10-04 weekly rollup (Mirror A live sidecar)

Evidence: `_raw/momentum-portfolio.json` asOf `2026-10-04T15:51:00+03:00` (mirror `11630170`).

| Field | Live |
|-------|------|
| Equity | $7,847.50 |
| Cash | **$4,361.46** (~55.6%) |
| Open symbols | **CRWD / VTRS / P / XLK** |
| Absent vs prior 9-name book | **DE / FTNT / JNJ / AAPL / NDSN** (also TGT/PLTR/ETH…) |

**Interpretation (evidence only, no invented fill PnL):** closes **did** happen later — cash rose from ~$549.77 (Oct 1 briefs) to $4,361.46 and the five names are absent from live Mirror A. Ticket stays **OPEN** until place_ack / watchdog / keys-MCP fixes land (P0/P1 in ticket body). Do not invent closed-trade PnL for DE/FTNT/JNJ/AAPL/NDSN here.

Related Job-Runs: Momentum-EOD Oct 1–2 miss-checks under `Job-Runs/Momentum-EOD/` (backfill since 20260928).

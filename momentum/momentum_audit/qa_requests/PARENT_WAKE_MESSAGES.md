# Parent: WakeParent / SendToAgent messages (executor has no SendToAgent)

## 1) QA Bot `498c78db-a027-4f2c-8126-3c2be6f0a4bb` — screener-run QA
Please screener-run QA PASS/FAIL for Momentum EOD 2026-09-29 (skill momentum-screener-run-qa):
- run_id: screener-20260929-224425-a44cb333
- summary: /workspace/momentum_audit/screener-run-screener-20260929-224425-a44cb333.json
- near-miss: /workspace/momentum_audit/near-miss-2026-09-29.json
- audit: /workspace/momentum_audit/2026-09-29.jsonl
- pack: /workspace/momentum_audit/screener-2026-09-29-pack.json
- filtered: /workspace/momentum_audit/screener-2026-09-29-pack-filtered.json
- regime HEALTHY (SPX 7670.69 > SMA50 7645.15 / +0.334%, VIX 16.02), universe_n=520 (S&P 503 live), event_vol_freeze=false
- raw buys=[FTNT, NDSN, LLY] all VCP_SETUP (breakout=0 etf=0 commodity=0)
- ACTION ts_il 22:44:39 IDT — **before** 22:50 gate (backup wake; not EOD_SCREENER_MISSED HIGH AVOID)

## 2) place-QA (ONLY after screener-run PASS) — skill momentum-real-money-qa-gate
Mirror A 11630170 availableCash=**$1349.61** (user-etoro portfolio-summary). Keys MCP = fills only.
Mirror A symbols: AAPL JNJ DE XLK FTNT VTRS CRWD P (absent vs keys: ETH).

PM risk (local validate PASS; still needs place-QA before PATCH):
1. VTRS MOVE_SL_BREAKEVEN HIT_2R — keys pos 3580194334, SL 16.38→16.96 (PATCH /api/v2/trading/positions/3580194334)

DO NOT PLACE: FTNT (already held keys pos 3590220047); CRWD TRAIL noop (stop already 230.85); ETH not on mirror A.

Placeable buys after held filter (≤$1000, ×1; cash covers one):
1. NDSN BUY $1000 ×1 mkt SL 310.19 fixed VCP_SETUP RS86
2. LLY BUY $1000 ×1 mkt SL 1113.58 fixed VCP_SETUP RS80 — expect INSUFFICIENT_CASH GATE_OK if NDSN fills first

On place-QA PASS → FULL AUTO prepare+place on user-Momentum-HHHGDTJ immediately (no Ofer confirm). For VTRS BE → execute-write PATCH stopLossRate.
On INSUFFICIENT_CASH FAIL → GATE_OK (audit FAIL OK; not playbook AVOID); do not place.
Never self-PASS. AVOID if violated: PLACE_WITHOUT_QA_BOT_RECHECK.
Bundle: /workspace/momentum_audit/place_qa/eod-20260929-2242-backup-qa-bundle.json
Also: /workspace/momentum_audit/qa_requests/2026-09-29-eod-2242-backup-qa-requests.json

## 3) Risk status this wake — do NOT re-TRAIL CRWD / do NOT trail ETH
- HOLD: AAPL JNJ DE XLK FTNT P (ABOVE_SMA50_UNDER_1R; AAPL ~−3.8% keys not yet −4%)
- MOVE_SL_BREAKEVEN pending QA: VTRS 16.38→16.96
- TRAIL_SL CRWD: NOOP (already 230.85)
- ETH TRAIL_SL decision PASS → execution SKIP_NOT_ON_MIRROR_A
- No CLOSE; no buy fills this wake (pending QA Bot)

## Tell Ofer (English only)
Momentum EOD Tue 2026-09-29 (~22:47 IDT): Primary 22:40 PM missed — 22:42 backup ran PM+screener. Position manager — VTRS to breakeven SL 16.96 pending QA; CRWD trail unchanged; ETH trail skipped (not on mirror A); all other HOLDs (AAPL still above SMA50, loss under −4%). Screener HEALTHY VCP pack FTNT/NDSN/LLY; FTNT held dropped. Mirror A cash $1349.61 — NDSN $1000 then LLY pending QA Bot screener-run + place-QA. No fills this wake.

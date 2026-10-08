# Parent handoff — AAPL Mon-open place resume (2026-09-28 ~16:49 IDT)

## Step 1 DONE (this automation)
Momentum-HHHGDTJ keys book: **AAPL not open, 0 pending orders.**
Open: JNJ TGT DE XLK VTRS CRWD P PLTR + ETH dust.
Keys availableCash **$1120.49** (fills-only; NOT mirror truth).
AAPL live ask **342.22**, allowOpenPosition=true (NYSE open). Proposed: AAPL $900 ×1 mkt SL 320.79 fixed VCP.

## Blockers for this subagent
1. **user-etoro** MCP `needsAuth` — cannot read live mirror A `11630170` availableCash.
2. No **SendToAgent** in this automation run — cannot ask QA Bot.

## Parent must do now (FULL AUTO standing)
1. Pull **live** mirror A 11630170 availableCash via **eToro Account** agent `7b604913-c0fd-49bc-897a-c9ce38589c63` (or reconnect `user-etoro` then get-my-portfolio-summary / copiedTraders). Morning brief still showed **$904.64** @ 05:24 IDT — refresh before QA.
2. **SendToAgent QA Bot** `498c78db-a027-4f2c-8126-3c2be6f0a4bb` — **fresh** place-QA (skill momentum-real-money-qa-gate). **Do NOT reuse Fri 2026-09-25 PASS** (Auto-review interrupt / no fill). Cite live cash + book + exact order below.
3. On place-QA **PASS** → FULL AUTO prepare+place on `user-Momentum-HHHGDTJ` immediately (no Ofer confirm widget). If Auto-review blocks → raise approval card and ping CoS card is pending.
4. On **FAIL / INSUFFICIENT_CASH GATE_OK** → do not place; report; delete routine `aapl-mon-open-place-resume`.
5. On fill → report orderId/pos/SL to user + CoS; request post-fill QA; delete routine.
6. No Classic. MET not in this resume unless cash clearly frees + separate fresh place-QA.

## Exact place-QA request for QA Bot
Please place-QA PASS/FAIL for Momentum-HHHGDTJ (skill momentum-real-money-qa-gate):
- Context: Mon-open resume of unfinished Fri 2026-09-25 AAPL place (Auto-review interrupted; no fill). Fresh QA required.
- Screener run_id (Fri): screener-20260925-224937-f841c72c (prior screener-run QA PASS that session)
- Candidate: **AAPL BUY $900 ×1 mkt SL 320.79 fixed** VCP_SETUP (do not reuse Fri place-QA verdict file)
- Mirror A 11630170 availableCash: **<PARENT FILLS LIVE>** (source user-etoro / eToro Account)
- Keys book held: JNJ TGT DE XLK VTRS CRWD P PLTR (+ ETH keys dust not on mirror A); AAPL not held; 0 pending
- On PASS → trader FULL AUTO prepare+place; QA never places; post-fill QA required
- Artifact: /workspace/momentum_audit/qa_requests/2026-09-28-aapl-mon-open-resume.json

## Tell user + CoS (English)
Mon-open AAPL resume: book clear (no AAPL/pending). Live mirror A cash + fresh place-QA in flight via parent; will FULL AUTO place on PASS or close the watch on FAIL.

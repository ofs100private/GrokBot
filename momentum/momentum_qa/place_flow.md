# Momentum place flow (FULL AUTO)

1. Screener-run QA Bot PASS required before any BUY pack is accepted.
2. Place-QA via QA Bot (mirror A cash truth) before prepare/place.
3. `INSUFFICIENT_CASH` → GATE_OK; log FAIL; do not place; do not score as playbook AVOID.
4. If cash later frees (closes): pull fresh A cash → **re-ask QA Bot place-QA** with new snapshot → place only on new PASS.
5. Never self-PASS / reuse prior FAIL pack. AVOID: `PLACE_WITHOUT_QA_BOT_RECHECK`.

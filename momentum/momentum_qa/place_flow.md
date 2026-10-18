# Momentum place flow (FULL AUTO)

1. Screener-run QA Bot PASS required before any BUY pack is accepted.
2. Place-QA via QA Bot (mirror A cash truth) before prepare/place.
3. `INSUFFICIENT_CASH` → GATE_OK; log FAIL; do not place; do not score as playbook AVOID.
4. If cash later frees (closes): pull fresh A cash → **re-ask QA Bot place-QA** with new snapshot → place only on new PASS.
5. Never self-PASS / reuse prior FAIL pack. AVOID: `PLACE_WITHOUT_QA_BOT_RECHECK`.
6. **Single-use verdict lock (2026-10-15, VTRS/STLD dup incident):** before EVERY place-trade (routine AND parent chat): live `get-my-positions-and-orders` with top-level `timestamp`/`asOf` **<120s** → `python -m momentum_qa.place_lock acquire --verdict <qa-verdict.json> --symbol <SYM> --caller <eod-routine|parent-chat> --positions-json <live.json>` → only on exit 0: prepare-trade → place-trade → `place_lock mark --lock <path> --status PLACED|FAILED --order-id .. --position-id ..`. Exit 2 LOCK_HELD / 3 ALREADY_HELD / 4 POSITIONS_STALE|RETRY_NOT_ALLOWED → do NOT place. Missing timestamp = POSITIONS_STALE. Same verdict sha never re-places; FAILED/EXPIRED retry needs `--retry-after-fail` + fresh QA verdict. PM trail/close use `--allow-held`.
7. Pack shape (playbook 2026-10-05): **unlimited stocks**, etf_buys ≤ 1, ≤$1000/name, cash gate.

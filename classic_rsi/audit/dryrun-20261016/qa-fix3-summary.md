# Classic 2026-10-16 — QA fix3 (last WARN). No trades placed. execute_pass v15-qa3-orders.
Diffs: code-20261016-qafix3-incremental.diff (vs fix2), code-20261016-v4.diff (full vs original).
Tests 549/549: execute_pass 236 · orders_20261016 (NEW) 25 · prebuy 33 · regression 35 · rules 41 · cash_floor 25 · cost_gate 51 · instruments 20 · scorer 45 · universe 38.
- pre_buy --orders-response (required): parse_orders validates raw get-my-positions-and-orders (statusCode 200, direct.positions/orders lists, timestamp <= 60 s, parseable position openTime). Verified on a real read (4 positions, 0 pending).
- Pending (non-terminal) orders placed today or with unknown time count as used slots (key order:<id>), in pre_buy counter and in prebuy-state used by execute_pass.
- release_stale(blocker=...): a stale (>30 min) unmarked reservation is released only if no pending order for its instrumentId (unknown-instrument pending order blocks all), and no position (orders read) or history trade for it opened after the reservation; otherwise stays reserved with release_blocked reason. No orders read => no releases.
- execute_pass buy gates: PRE_BUY_NOT_FRESH unless prebuy-state.json <= 5 min old with history_ok+rates_ok+orders_ok; BOOK_NOT_FRESH_FOR_COUNT if book > 60 s; count unions book + history + prebuy opened ids + pending keys.
- Skills trader-classic-strategy / classic-rsi-four-level-1h pre-buy section rewritten with the 3-read sequence.

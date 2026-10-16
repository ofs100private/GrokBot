# Classic 2026-10-16 rules — QA fix1 summary (response to qa-review-classic-rules-20261016.json FAIL)
No trades placed/closed/modified. execute_pass VERSION = execute-pass-v13-qa1-counter-xle.

Diffs: code-20261016-v2.diff (full vs original), code-20261016-qafix1-incremental.diff (vs first submission).
Dry-run (propose only, live latest-auto untouched): auto_1h-dryrun-v2.json (PROPOSE, no flags; BTC/ETH/SOL scanned with ids 100000/100001/100063).

## Tests (all script runners, test mode)
execute_pass 236/236 · regression_20261016 (NEW, unpinned new floor/caps) 35/35 · rules_20261016 41/41 · cash_floor 25/25 · cost_gate 51/51 · instruments 20/20 · scorer 45/45 · universe 38/38 → 491/491.

## BLOCKING
1. TRADE_COUNTER_NOT_ATOMIC — trade_counter.py rewritten: every read-modify-write under fcntl.flock(LOCK_EX) on <counter>.lock; writes via tempfile.mkstemp (unique) + fsync + os.replace. check+reserve is one locked step `reserve()` (idempotent per key). Test: 8 concurrent processes → exactly 4 reservations; no tmp leftovers.
2. TRADE_COUNTER_NOT_WIRED — execute_pass `_finish`: on GO with write_lock, RSI path (key rsi:<pack_id>) and rebalance path with buy legs (key rebalance:<pack_id>) call TC.reserve; failure → GO locks removed, NO-GO DAILY_TRADE_LIMIT. GO output carries trade_reservation_id + after_place mark/release instructions; `trade_counter mark|release` CLI; reserved slots count until released (no expiry, fail closed). Book fallback now = distinct positionIds opened today (IDT) in open book ∪ saved trading history (paths()["history"], {"asOf","response"} ≤30 min) so opened-and-closed same day count; missing/stale history → TRADING_HISTORY_MISSING NO-GO. Skills document the protocol.
3. TRADE_COUNTER_ENV_OVERRIDE — path pinned to /workspace/classic_rsi/state/daily_new_trades.json; CLASSIC_TRADE_COUNTER honoured only when CLASSIC_EXEC_TEST_ROOT is set; set in production → status/reserve fail closed (COUNTER_ENV_OVERRIDE_IN_PRODUCTION). Tested.
4. NO_XLE_ADDS_NOT_ENFORCED — instruments.NO_ADD_SYMBOLS={"XLE"}; execute_pass hard check `no_xle_adds` on RSI buys and every rebalance buy leg; propose drops XLE buy packs (recorded in no_add_dropped, soft — not an instrument hard flag) and auto_place_eligibility adds NO_XLE_ADDS. Legacy test_execute_pass rebalance-add fixtures moved XLE→DIA (3026); new tests assert XLE RSI buy, XLE rebalance add and XLE propose are blocked.

## WARNINGS
- CRYPTO_COST_GATE — cost_gate preliminary for crypto: spread 1% + open/close fee 1% each of notional ($1,000 assumed if no notional). Tested.
- EXTENDED_HOURS_PER_INSTRUMENT — trading_window: stocks/ETFs need calendar window AND explicit live isOpen=True; None → INSTRUMENT_OPEN_UNKNOWN (closed); supports_extended=False → RTH. Crypto open unless isOpen=False. CLI `--instrument-open true|false`; rebalance live legs `is_open`.
- CRYPTO_SL_HEURISTIC — levels.crypto_long_levels: SL distance = max(2.5×ATR1h, 4%) capped 20%; TP = 1.5R; cost_gate.rebase_levels re-bases crypto with the same rule; rebalance crypto SL must be 4–20% below ask and ≥1× daily ATR (replaces 12–20% trail). Documented in levels.py and skills. Tested.
- CRYPTO_BY_SYMBOL — resolve/guard_symbol take instrument_id; crypto majors resolve only with matching explicit id; bare BTC/ETH/SOL → unresolved. auto_1h passes instrument_ids for the crypto universe; execute_pass uses pack/leg/book ids. Tested.
- LEGACY_TESTS_PINNED — new test_regression_20261016 runs on the real constants (floor 1500, stock 20%, ETF 35%, crypto sleeve 15%) incl. GO+reserve, cash-floor shrink, name cap 20%.

## Remaining limitations
- trading-history file must be written by Trader_Classic from user-OfersClaw5 before buy GOs (no in-script eToro access) — until that's in the routine, buys are NO-GO (fail closed).
- isOpen must come from a live read; the market-data search endpoint did not return isOpen in projection — use rates/prepare response.

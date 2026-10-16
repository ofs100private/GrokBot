---
name: Classic RSI 1H run QA
description: >-
  use this when QA must validate every Classic RSI 1H auto or propose run (audit
  integrity, long-only, ATR stops, confirmed close) and on FAIL message
  Trader_Classic to rerun then re-validate until PASS before any buy pack is
  accepted
---
# Classic RSI 1H run QA (validate → FAIL → Classic rerun → PASS)

## Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)
- **FULL AUTO is ON.** Any Classic trade with run-QA PASS (RSI runs) + order-QA PASS + a passing final cost gate (execute_pass GO) is placed automatically by Trader_Classic via `user-OfersClaw5` — no Ofer chat approval. Ofer has accepted QA's earlier residual risks.
- **Hours:** US stocks/ETFs 24x5 via eToro extended hours (Sun 20:05 ET → Fri 20:00 ET, minus US holidays); an instrument that lacks extended hours or reports closed (isOpen=false / prepare rejects) falls back to RTH. Crypto trades 24/7 incl. weekends. The old weekend freeze applies to equities only.
- **Max 4 NEW trades per IDT calendar day** across all Classic runners (counter `classic_rsi/trade_counter.py`, cross-checked with positions opened today). SL edits and protective/risk exits do not count; rotation/add buy legs do.
- **Daily slot protocol (QA fix 2026-10-16):** execute_pass GO (write-lock) atomically reserves a daily slot and returns `trade_reservation_id`. On a confirmed fill run `cd /workspace && ./screener-venv/bin/python -m classic_rsi.trade_counter mark --reservation <ID> --position-id <POS>`; if the place fails or is abandoned run `... trade_counter release --reservation <ID> --reason "<why>"`. Never place without a reservation. Before any buy GO, save a fresh (≤30 min) `user-OfersClaw5` get-my-trading-history read as `{"asOf": <ISO>, "response": <raw>}` to `/workspace/classic_rsi/state/trading-history-today.json` (opened-and-closed-today positions count toward the 4). Missing/stale history → `TRADING_HISTORY_MISSING` (NO-GO). The counter path is pinned; never set `CLASSIC_TRADE_COUNTER` in production.
- **Live open check:** stocks/ETFs need an explicit live per-instrument `isOpen=true` (`--instrument-open true` for RSI buys; `is_open: true` on every rebalance live leg). Unknown → CLOSED (`INSTRUMENT_OPEN_UNKNOWN`). Crypto majors are open 24/7 unless the read says closed.
- **No XLE adds is hard-enforced:** any XLE buy/add → `NO_XLE_ADDS` (execute_pass and propose). Sells/trims of XLE are allowed.
- **Crypto specifics:** crypto packs must carry the explicit instrumentId (100000/100001/100063); a bare BTC/ETH/SOL symbol never resolves to crypto. Crypto SL = max(2.5×ATR(1H), 4%) capped at 20% below entry, TP = entry + 1.5×SL distance; rebalance crypto SL must be 4–20% below ask and ≥ 1× daily ATR. Preliminary crypto cost floor: 1% spread + 1% fee per side.
- **Caps of TOTAL equity:** single stock ≤ 20%, ETF/fund ≤ 35%, any sleeve ≤ 45%, crypto sleeve (BTC+ETH+SOL) ≤ 15%. **Cash floor ~$1,500** after every buy (sequenced across a batch).
- **Crypto:** only BTC (instrumentId 100000), ETH (100001), SOL (100063); ×1 long; SL+TP required. Every other crypto stays blocked. Symbol traps: bare `T` = Threshold crypto (100528), AT&T is `T.US` (1030); `CVX` → `CVX.US`; never resolve by bare ticker alone.
- **Every new buy MUST carry a calculated take-profit AND a stop-loss on the order.** TP from ATR/R-multiple (default SL = entry − 1.5×ATR, TP = entry + 2.0×ATR, re-based on live ask; reward:risk ≥ 1.25) and the TP distance must satisfy the cost gate (expected gain ≥ 2× round-trip cost). A buy without TP (takeProfitRate null) is a hard fail.
- **Unchanged:** ×1 long only, no leverage/shorts, stops required, sell/rotate before buy, cost gate (expected gain ≥ 2× round-trip cost), cross-book block vs Momentum-HHHGDTJ live holdings, no XLE adds.
- **Overlap note:** the Daily Trader book trades leveraged crypto/stocks same-day; Classic crypto is a ×1 swing on a separate account. Flag (do not auto-block) when Classic would buy the same crypto Daily Trader holds/trades that day, and never treat Daily Trader levels as Classic signals.


Independent **per-run** gate for Classic RSI 1H (`auto_1h` / `propose`). Complements [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) (order packs / fills). This skill owns **run integrity and signal hygiene**, not place sizing.

**Classic only** (Classic account (OfersClaw5-PRIYN) / `user-OfersClaw5`). Never Momentum. **Do not place** from this skill. Parent SSO mirror `11368142` is optional copy/UI corroboration only.

## When to run

- Immediately after every `python -m classic_rsi.auto_1h` (routine **classic-rsi-1h-auto**: weekdays `CRON_TZ=Asia/Jerusalem 35 */3 * * 1-5`, or manual)
- After every `propose` that writes an audit `run_id`
- Before accepting any RSI `buy_pack` for order-QA / place
- On CoS / Trader_Classic handoff citing a Classic RSI `run_id`

## Evidence to collect

1. `/workspace/classic_rsi/audit/<run_id>.json` (required)
2. `/workspace/classic_rsi/audit/latest-auto.json` or `latest-propose.json` matching that `run_id`
3. `/workspace/classic_rsi/audit/index.jsonl` row for the same `run_id`
4. Envelope fields: `kind` (`auto`|`propose`), `status`, `timeframe`, `confirmed_close`, `long_only`, `do_not_place`, `buy_packs`, `risk_off`, `mandate_gates`, `symbols`
5. Independent LIVE check when packs or book summary present: **Classic account (OfersClaw5-PRIYN)** via `user-OfersClaw5`. Do **not** reject OfersClaw5 figures as keys-B. Mirror `11368142` optional corroboration only — never required, never the rejection reason

## Hard FAIL (any one)

| Code | Condition |
| --- | --- |
| `RSI_RUN_MISSING` | No audit JSON for cited `run_id`, or latest-* points at a different run |
| `RSI_AUDIT_INCOMPLETE` | Missing `index.jsonl` row, or envelope lacks timeframe / long_only / confirmed_close / do_not_place |
| `RSI_TF_NOT_1H` | `timeframe` ≠ `1H` |
| `RSI_UNCONFIRMED_BARS` | `confirmed_close` is false or missing when status is PROPOSE with packs |
| `RSI_SHORT_OR_PIP` | Any pack implies short / sell-to-open, or uses FX pip SL/TP instead of ATR/% equity |
| `RSI_CRYPTO` | Any crypto other than BTC (100000) / ETH (100001) / SOL (100063) in buy_packs, or a crypto pack that resolves by bare ticker (e.g. `T`) |
| `RSI_TP_MISSING` | Any buy pack without a calculated take_profit > entry > stop_loss (or reward:risk < 1.25) |
| `RSI_DAILY_LIMIT` | Envelope proposes eligible buys when the daily new-trade budget (max 4/IDT day) is exhausted |
| `RSI_WRONG_BOOK` | Book dollars from Momentum / wrong book, or invented — **not** a fail when from Classic account (`user-OfersClaw5`). Do not require mirror `11368142` |
| `RSI_PLACE_FROM_AUTO` | Auto script or envelope set `place=true` / bypassed QA |
| `RSI_RUN_CRASH` | Exception / empty / corrupt audit with no coherent PROPOSE or GATED status |

`buy_packs=[]` with status `PROPOSE` or `GATED` can still **PASS** if audit integrity and mandate fields are sound (0 packs is a valid outcome).

## FAIL → Classic rerun (mandatory)

On any Hard FAIL:

1. Verdict **FAIL** with `deviation_code`(s) + evidence to **Trader_Classic** and **Chief of Staff**
2. **Message Trader_Classic** to **rerun** `python -m classic_rsi.auto_1h` (or `propose` if that was the failing kind), citing the failed `run_id` and codes
3. Cap **2 reruns** per clock hour for the same slot; if still FAIL after 2, stop looping, tell CoS + Ofer, do not place
4. When a new `run_id` lands, **re-validate** this skill from scratch until **PASS** or the rerun cap is hit

Trader_Classic must treat a QA FAIL on a run as **do not prepare / do not place** until a later `run_id` PASSes.

## PASS (run-level)

All of:

1. Audit JSON + index row exist for `run_id`
2. `timeframe=1H`, `long_only=true`, `confirmed_close=true` (for PROPOSE), `do_not_place=true` on auto
3. No short / pip / non-major crypto / missing TP / wrong-book / place-from-auto (Classic account OfersClaw5 figures are allowed)
4. Packs (if any) carry ATR SL/TP and cite the same `run_id`

Then:

- If `buy_packs` empty → PASS run; no order-QA needed
- If `buy_packs` non-empty → PASS run, then each pack still needs [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) before place


## Soft check — dynamic universe (auto)

When `kind=auto` and `status=PROPOSE` (screener path, not `--symbols` override):

- Prefer `universe_meta.override` absent/false and `len(symbols)` **usually ≫ 6** when the screen worked (`universe_meta.rising_count` / `liquid_count` healthy).
- If symbols look like only the old fixed 6-name list (AAPL/MSFT/QQQ/SMH/XLV/JNJ) **and** book is a subset of those, treat as a **soft warning** in the verdict note — not a Hard FAIL (screen may be empty → book-only is allowed; document `used_fallback` / `fallback_reason` from `universe_meta`).
- Book-only after screener failure is OK; do **not** Hard-FAIL empty rising_count when fallback/book-only is explicit in meta.

## Verdict delivery

1. PASS or FAIL (+ codes/evidence) → **Trader_Classic**
2. Same verdict → **Chief of Staff**
3. On FAIL after rerun cap, also tell Ofer
4. QA never places

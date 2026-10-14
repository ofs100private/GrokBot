# classic_rsi — Classic-only RSI four-level entries (1H)

Long-only timing overlay for **Trader_Classic** on **OfersClaw5-PRIYN** (REAL MONEY).  
The code **never places** trades (no eToro calls; `do_not_place=True` on every pack). Under Classic **FULL AUTO** (Ofer, 2026-10-12) Trader_Classic places via the `user-OfersClaw5` MCP after run-QA PASS + order-QA PASS + final cost gate (`execute_pass` GO) — no chat authorization, no trade-count or monthly new-name cap. Does **not** touch Momentum. Does **not** change Fear / cash / weekend regime gates.

## Specs

| Item | Value |
|------|--------|
| Timeframe | **1H only** (live + backtest) |
| Side | Long-only; Sell triangles → **RISK_OFF** (never short) |
| RSI | length 14, close; Over Buy 79.90 / Resistance 67.90 / Support 34.90 / Over Sold 19.90 |
| Strong candle | body ≥ 1.2 × SMA(body, 20) |
| Labels | EXTREME_80 / ZONE_70 — **rule tags, not win rates** |
| Zone SM | one fire per zone visit; reset when RSI leaves zone |
| Bars | **confirmed close only** (forming bar dropped) |
| SL/TP | ATR(14) on 1H: SL = 1.5×ATR below entry, TP = 2.0×ATR above (**never FX pips**) |

Mandate gates stay with Trader_Classic and are unchanged by FULL AUTO: Fear, cash floor ≥ ~$2.5k (cut size/names, never breach), weekend no new opens, ×1 long only, no crypto, caps 30% ETF / 15% single stock / 45% sleeve, stops, sell-before-buy, run-QA + order-QA PASS and cost gate before every place.

## Package layout

```
/workspace/classic_rsi/
  signals.py   # RSI zones, strong candle, long-only remap
  levels.py    # ATR entry / SL / TP (equities)
  backtest.py  # 1H Yahoo backtest smoke
  propose.py   # candidate BUY packs + RISK_OFF notes + preliminary cost_gate + auto_place_eligible
  cost_gate.py # round-trip cost vs expected gain (expected_gain >= 2 x total_cost)
  execute_pass.py # final pre-place GO/NO-GO (RSI + rebalance) from live prepare values (never calls eToro)
  market_hours.py # NYSE regular-session / holiday check
  paths.py        # fixed production paths (test mode via CLASSIC_EXEC_TEST_ROOT)
  evidence/       # sha-pinned p / edge evidence registries
  testkit.py      # test-mode fixtures
  instruments.py  # fail-closed instrument guard (etoro_instrument_map.json)
  universe.py  # S&P → liquid ADV$ → rising 1H volume screener
  auto_1h.py   # 1H session auto runner (propose → audit; never place)
  audit.py     # append-only run trail
  audit/       # timestamped JSON + index.jsonl + universe-latest.json
  README.md
```

## Trader_Classic invocation (propose → run-QA → prepare → execute_pass → order-QA → agent places)

```python
# From /workspace (or PYTHONPATH including /workspace)
from classic_rsi.propose import propose_from_symbols

out = propose_from_symbols(["AAPL", "MSFT", "QQQ", "SMH", "XLV", "JNJ"])
# out["buy_packs"]  → candidate long packs (ATR SL/TP), status=PROPOSE_ONLY or COST_GATE_SKIP,
#                     each with cost_gate (preliminary) + auto_place_eligible / auto_place_blockers
# out["risk_off"]   → no-add / skip-chase notes (never shorts)
```

CLI:

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.propose --symbols AAPL MSFT QQQ --out /tmp/classic-rsi-propose.json
```

**Then (mandatory):**

1. Only packs with `auto_place_eligible=true` go forward (no hard flags, instrument guard OK, long-only ×1, book not stale, mandate allows new buys, preliminary cost gate not `COST_GATE_SKIP`).
2. Run-QA (**classic-rsi-1h-run-qa**) must PASS for the run.
3. Prepare via the MCP (prepare-trade / getCost) to get live bid/ask, units and fees.
4. Final gate — `execute_pass` v3 (fix2). Never calls eToro. **Paths are fixed** (`paths.py`); there is no `--audit-dir`, `--book`, `--cash` or verdict-path argument in production:

   | What | Fixed path |
   |---|---|
   | auto envelope | `/workspace/classic_rsi/audit/<auto_run_id>.json` |
   | run-QA verdict | `/workspace/classic_rsi/audit/qa/qa-verdict-run-<auto_run_id>.json` |
   | order-QA verdict | `/workspace/classic_rsi/audit/qa/qa-verdict-order-<pack_sha256[:16]>.json` |
   | GO locks | `/workspace/classic_rsi/audit/placed/` |
   | live book (cash, equity, positions; asOf ≤ 60 s) | `/workspace/classic-portfolio-for-app.json` |
   | score file (RS/ATR/50-200DMA, ≤ 5 days) | `/workspace/classic-rebalance/scores-latest.json` |
   | evidence registries (sha pinned) | `classic_rsi/evidence/{p_registry,edge_registry}.json` |

   Verdict schema (both): `verdict:"PASS"`, `checker:"QA Bot"` (exact), `skill` (`classic-rsi-1h-run-qa` / `classic-real-money-order-qa-gate`), `checked_at` (ISO with offset; run ≤ 60 min, order ≤ 15 min), `run_id`. Order-QA adds `pack_sha256`, `pack_id`, `symbol`, `qa_ask` (= anchor ask) and `recomputed_cost_gate {spread, fees, tax_est, total_cost, expected_gain, ratio}` matching execute_pass's **anchor** gate within ±0.01.

   ```bash
   # RSI: 1 plan (live read) -> 2 prepare-trade with the pinned payload -> 3 order-QA -> 4 re-prepare + GO
   ./screener-venv/bin/python -m classic_rsi.execute_pass --pack-id '<auto_run_id>#SYM' \
     --bid B --ask A --quote-ts <ISO+tz> --mark M --units U --open-fee F1 --close-fee F2
   ./screener-venv/bin/python -m classic_rsi.execute_pass --pack-id '<auto_run_id>#SYM' --bid B --mark M \
     --anchor-ask A0 --anchor-bid B0 --prepare-response prepare.json --units U --open-fee F1 --close-fee F2
   # rebalance (rebalance_add / trim / sell / rotation): static pack (hashed) + live quotes/prepares
   ./screener-venv/bin/python -m classic_rsi.execute_pass --rebalance-pack pack.json --live live.json
   ```
   Checks (fail closed): pack_id regex; US regular session; book ≤ 60 s, `0 ≤ cash ≤ equity`; verdicts as above; instrument guard; live quote ≤ 60 s **and a second-source `--mark` within 0.1%**; live ask within 0.1% of the QA anchor; `cash − units×ask − open_fee ≥ 2500` at anchor and live ask; caps on market value **and** cost basis; min $400; anchor gate PASS (QA-recomputed) **and** live gate PASS; MCP payload verified against the prepare response (account, instrumentId, direction `buy`, leverage 1, `mkt`, units ±1e-6, SL/TP, prepare stop bounds); 0 < SL < bid; rebalance buys: `ask − 3.5×ATRd ≤ SL ≤ ask − 1×ATRd` or ETF 8% / stock 10–12% trailing; no position on the instrument opened < 24 h; sell legs: position held, `positionId` int, realized PnL recomputed from openRate (|Δ| ≤ $1, tax on the max); risk exits recomputed from book/scores/live (never self-declared); locks keyed on (run_id, symbol, instrumentId) or (kind, legs, ET date) plus per-leg same-day locks.
5. GO payloads are MCP-native: buy `{account:'real', direction:'buy', instrumentId, units, leverage:1, orderType:'mkt', stopLossRate, takeProfitRate}`; close `{account:'real', positionId:int, unitsToDeduct|null}`. Trader_Classic places with the token of the prepare execute_pass verified (sells first). Test mode (`CLASSIC_EXEC_TEST_ROOT`) re-roots every path and forces `account:'demo'`.

### Cost gate (`cost_gate.py`, v3 fix2)

- `total_cost = spread + open_fee + close_fee + overnight + tax_est` (> 0); spread = `max(spread_usd, (ask − bid)×units)`; fees from prepare/getCost (required at anchor/final); tax 25% of `max(declared, recomputed)` realized on sell legs. Preliminary only: 0.15% spread, $0.75/order (real fills 2026-10-07).
- RSI `EV = units × [p(TP − ask) − (1 − p)(ask − SL)]`, ×0.75 if > 0. **p is never typed**: Wilson 95% lower bound from `evidence/p_registry.json`, usable only if out-of-sample and n ≥ 100. Today's only entry (1H backtest 12/19, in-sample, p_lower 0.410) is unusable → every RSI pack SKIPs.
- Rebalance: `edge_ref {evidence_id}` into `evidence/edge_registry.json` (out-of-sample, n ≥ 30, horizon ≥ 5 d); `er = intercept + slope × score` from the score file, capped at `2 × ATR% × √h`. Registry ships empty → every rebalance add/trim/rotation SKIPs; verified risk exits are RISK_EXIT.
- PASS iff `EV_after_tax ≥ 2 × total_cost` and net > 0.

## Rebalance scorer (fix3, hardened fix4) — run first in the daily rebalance routine
```bash
cd /workspace && python3 -m classic_rsi.scorer
# → /workspace/classic-rebalance/scores-latest.json
# → /workspace/classic-rebalance/scores-latest.sha256   (sidecar: "<sha256hex>  scores-latest.json")
```
- Yahoo daily (yfinance, `auto_adjust=False`): returns/RS on Adj Close; DMA/ATR/highs on raw OHLC. Only bars up to the last completed US session.
- Rows (holdings from the live book + SKILL Step-2 ETFs; large caps via `--extra`): `last_close, dma50, dma200, above_50dma, above_200dma, dma50_above_200dma, trend_ok, ret_/rs_ 1m/3m/6m, score = 0.5·rs_3m + 0.5·rs_6m, atr14 (Wilder, price), atr_pct, dd_52w, vol_63d, adv_usd_20d`. `trailing_stops[sym] = {high_since_entry, threshold (ETF −8%, stock −max(10%, 2.5×ATR%)), level}`.
- **Units (fix4): FRACTION.** `score`, `rs_*`, `ret_*` are fractions (0.05 = +5 pp vs SPY); the file carries `score_units: "fraction"`. Edge registry: `er_pct = intercept_pct + per_score_pct × score_fraction` (`per_score_pct` = % expected return per 1.0 of score) and every entry's `calibration.score_units` must be `"fraction"`; otherwise `EDGE_SCORE_UNITS_NOT_FRACTION` / `SCORE_FILE_UNITS_NOT_FRACTION` → SKIP.
- **Verification (`scorer.verify_scores_file`, called by `execute_pass.load_scores`), fail closed:** `SCORES_MISSING`, `SCORES_SIDECAR_MISSING`, `SCORES_SHA_MISMATCH`, `SCORES_SCHEMA_INVALID`, `SCORES_UNITS_INVALID`, `SCORES_VALUE_INVALID` (every numeric field finite, real-typed — not bool/str/NaN/inf — and in range, e.g. |score|,|rs| ≤ 5, 0 < atr14 ≤ 50% of last_close; booleans strictly bool; symbol regex; **no duplicate symbols**; trailing thresholds in [−50%, −1%]), `SCORES_FROM_FUTURE`, `SCORES_STALE_<n>_TRADING_DAYS`.
- **Freshness (fix4): age 0.** `asOf_bars` must equal the last completed US session. The routine at 18:06 IDT (11:06 ET, session open) scores the prior trading day → age 0, passes. After the 16:00 ET close, or the next morning without a re-run, the file is stale until the scorer runs again.
- **Which packs need verified scores (fix4):** buys (ATR SL bounds + edge), non-risk trims/sells/rotations (edge), and risk exits `trigger_3_50dma_neg_rs` / `trigger_4_200dma`. Protective exits `cash_below_floor`, `stop_hit` (position's own `stopLossRate` vs live bid) and `hard_cap_breach` run from the book + live quote and **do not** require scores; the trailing-stop leg of `stop_hit` only counts when scores are verified.
- The sidecar proves the file is unchanged since it was written — not who wrote it (shared box).

## Risk-exit sizing (fix5)
- `cash_below_floor` and `hard_cap_breach` sells must use the **minimum** units that fix the breach, plus a buffer `B = 1% of equity` (`RISK_EXIT_BUFFER_EQUITY_PCT`):
  - cash: `x·bid − close_fee ≥ 2500 + B − cash`;
  - caps, for the name cap (ETF 30% / stock 15%) **and** the 45% sleeve cap, on **both** market value and cost basis: `x ≥ (X − cap·T + B) / (u·(1 − cap))` with `u` = the position's per-unit value or per-unit cost; the largest requirement wins.
  - `bid = min(anchor bid, live bid)`; units rounded **up** to 1e-6.
- If the residual `(held − x)·bid < $400` (or `x ≥ held`), the whole position is closed (`unitsToDeduct: null`). Otherwise `unitsToDeduct = x`.
- The pack's units must equal the computed size (±1.5e-6) or the pass is NO-GO with `RISK_EXIT_SIZE_MISMATCH`; no silent resizing. Output `risk_exit_sizing` shows the required units per constraint, buffer, residual and `unitsToDeduct`.
- `stop_hit` and `trigger_3/4` may close any size, including the full position.

## Risk-exit GO size band + post-trade caps (fix6)
- Fix5's exact `±1.5e-6` units match is replaced by a one-sided band evaluated at GO with the live book and `min(anchor, live)` bid:
  `required_now ≤ pack_units ≤ 1.02 · max(required_at_qa, required_now)` (`RISK_EXIT_SIZE_BAND`). `required_at_qa` = the leg's `risk_exit_required_units` (hashed with the pack), clamped to `1.05 · required_now`.
- Planners should size the pack at `risk_exit_sizing.suggested_pack_units` = `ceil(1.01 · required)` (`RISK_EXIT_PLAN_HEADROOM`) and set `risk_exit_required_units` = `suggested_required_at_qa`, so small adverse drift (≈±0.02% price, ±$0.10 cash) stays inside the band.
- The `<$400` residual full-close rule is re-evaluated at GO: full close OK if the live rule says full or `held` is inside the band; a partial must leave a live residual ≥ $400. Outside the band ⇒ `RISK_EXIT_SIZE_MISMATCH` (see `risk_exit_band`).
- Post-trade caps: after the sized `cash_below_floor`/`hard_cap_breach` exit the resulting book is simulated and **every** name cap (ETF 30% / stock 15%) and sleeve cap (45%) is checked on value and cost basis. A new breach (bucket ≤ cap before, > cap after) ⇒ `RISK_EXIT_POST_TRADE_CAP_CASCADE`; `risk_exit_post_trade_caps.alternatives` lists other legs that would not cascade (indicative; a new pack + order-QA is needed, nothing is swapped automatically). Pre-existing breaches made worse are reported in `worsened_existing`, not blocked.
- Cap denominator: see fix7 below (now total equity).

## Caps on total equity (fix7, Ofer 2026-10-12 17:56 IDT)
- `CAP_DENOMINATOR = "equity"`: name caps (ETF 30% / stock 15%) and the 45% sleeve cap are measured against **total equity = holdings + cash**. Market-value basis uses the book's `equity`; cost basis uses `sum(cost) + cash`. All cap math goes through `cap_denominator()` (`_caps` buy sizing, `_verify_risk_exit`, `_risk_exit_size`, `post_trade_caps`). `"invested"` remains selectable only for the legacy fix5/fix6 tests.
- Buys: cash moves into the position, so the denominator is unchanged (`max = cap·E − X`).
- Sells / post-trade: proceeds move to cash, so equity after = `E − close_fee + x·(bid − u)` (equity minus fees and the bid-vs-mark gap). Risk-exit size: `x ≥ (X − cap·(E − fee) + B) / (u + cap·(bid − u))`.
- `cost_gate.py`, `scorer.py`, `propose.py`, `auto_1h.py` do no cap arithmetic (text mentions only); the classic-rebalance `SKILL-draft.md` / `body.md` triggers now say "of total equity".
- Today's book (17:44 IDT, equity $7,251.71, cash $3,671.18): SMH+QQQ 21.93%, QQQ 11.38%, TMO 7.0% of equity; no cap or floor breach, so no protective exit is triggered. With cash at $2,499 / $2,300 / $2,000, every single-leg cash-floor exit (TMO, SPY, QQQ, XLV, SMH) is in band with no cap cascade.
- Tests use a frozen copy of that book: `classic_rsi/fixtures/classic-portfolio-20261012-1744.json`.

## Fix7b: equity reconciliation + book sleeves on equity
- Hard check `BOOK_EQUITY_NOT_RECONCILED` (RSI and rebalance): `|equity − (Σ holdings value + cash)| ≤ 0.5%` of equity (`EQUITY_RECONCILE_TOL`). The book's equity is the value-basis cap denominator, so it must agree with its own positions and cash.
- `python3 -m classic_rsi.book_sleeves [--dry-run]` recomputes `sleeves` (growth/healthcare/broad-core, every name, single-stock and SPY core) and the `cashTriggerProposal` SPY 30% cap check in `/workspace/classic-portfolio-for-app.json` as **% of total equity** (cost basis: position cost + cash), from the file's own numbers (no eToro call; atomic write + timestamped backup). Old invested-basis numbers are kept only under `legacyInvestedBasis` (labelled LEGACY).
- The book refresh routine (`classic-book-refresh-before-rsi-1h`) is not on the box; it carries `sleeves` forward from the daily-brief generators. It should run `book_sleeves` after each refresh, or a refresh will bring the invested-basis block back.

## Fix8: Momentum cross-book rule (Ofer 2026-10-13 01:44 IDT)
- Classic must never **buy** a symbol or instrument id held in Momentum-HHHGDTJ (mirror 11630170). Sells and exits are unaffected.
- Snapshot `/workspace/momentum-holdings-for-classic.json` (test mode `<root>/momentum.json`): written by `python3 -m classic_rsi.momentum_holdings --response <file>` from a saved READ-ONLY `user-Momentum-HHHGDTJ get-my-positions-and-orders` response. It holds asOf (IDT), xRequestId, symbols and instrumentIds. Direct positions, copied (mirror) positions and live pending orders all count as held.
- execute_pass, on every buy (RSI and rebalance): `CROSS_BOOK_OVERLAP` if the symbol or id is in the snapshot, and `MOMENTUM_SNAPSHOT_STALE` if the snapshot is missing, invalid or older than 60 s at GO. Refresh the snapshot right before GO.
- propose drops overlapping buy packs into `cross_book_skipped` (reason `CROSS_BOOK_OVERLAP`; a missing snapshot drops all buys); auto_1h carries `cross_book_skipped` and `momentum_snapshot` in the envelope. The rebalance target logic (`SKILL-draft.md`, `filter_symbols`) does the same.

## Fix8b: live Momentum read at GO (QA fix8 R1–R4)
- **GO uses the executor's own live read, not the shared file.** For any buy, pass the raw `user-Momentum-HHHGDTJ get-my-positions-and-orders` response you captured for this GO: `--momentum-response <file> --momentum-captured-at <ISO tz> --momentum-source user-Momentum-HHHGDTJ` (Python: `momentum_read={"source","captured_at","response"}`). It is parsed in-process. Both the capture time and the server `timestamp` must be ≤ 60 s old. The GO audit records `momentum_read.xRequestId` and `response_sha256`. `/workspace/momentum-holdings-for-classic.json` is now only a pre-filter for propose/auto_1h, so a forged fresh file cannot open a buy.
- **Fails closed:** `MOMENTUM_READ_MISSING` (no read), `MOMENTUM_SNAPSHOT_STALE` (capture or server time > 60 s, or missing), `MOMENTUM_READ_EMPTY` (0 positions and 0 live orders), `MOMENTUM_READ_INVALID` (non-200, error, `warnings` set, not real), `MOMENTUM_MIRROR_MISSING`, `MOMENTUM_SOURCE_MISMATCH`.
- **Mirror 11630170 pin:** in the parent `user-etoro` read, Momentum is `mirrors[mirrorId=11630170]` (11368142 = Classic). In its own `user-Momentum-HHHGDTJ` read the same positions are reported under `direct`, with `mirrors: []` and no mirrorId; the profile call returns 403. So the source must be `user-Momentum-HHHGDTJ`, `direct` is the 11630170 section, and any `mirrors[]` content (the parent shape) is rejected; parent positions are never merged. An optional `--momentum-parent-response` cross-checks that the parent's mirror 11630170 ids match exactly.
- Symbols are normalized on both sides (upper-case, trimmed, `.US` dropped); instrument ids also match. Live pending Momentum orders count as held (canceled/rejected/expired do not). The producer and loader pin source and mirror, and an empty file is rejected.

## takeProfitRate on rebalance buys (fix3)
`user-OfersClaw5` `prepare-trade` schema (read-only lookup 2026-10-12): `takeProfitRate` type `["number","null"]`, default `null`, "Optional". Rebalance buys therefore send `takeProfitRate: null` (no fixed TP on core adds — SKILL Step 5; exits via trailing stop). The prepare echo must also be null, otherwise `PREPARE_TP_MISMATCH`.

## Backtest (1H)

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.backtest \
  --symbols AAPL MSFT QQQ SMH XLV JNJ \
  --period 60d \
  --out /workspace/classic_rsi/backtest-summary-1h.json
```

Summary JSON states `timeframe: "1H"`. Yahoo intraday history is ~60d for 1h bars.





## 1H auto runner

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.auto_1h
# optional: --symbols SMH QQQ XLV --force  (weekend override) --dry-run --out /tmp/auto.json
```

Behavior:
- **Universe (no fixed list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ **$100M**, price ≥ **$10**) → rising confirmed 1H volume (last vol > SMA20×**1.2**) → top **~50** ∪ live Classic book (`/workspace/classic-portfolio-for-app.json`). Cache: `audit/universe-latest.json` (fallback if yfinance flakes; never silently use the old 6-name DEFAULT_SYMBOLS as primary). Metadata on envelope as `universe_meta`.
- Soft gates: weekend / outside US RTH / cash &lt; ~$2.5k → status `GATED` (buy packs suppressed; risk_off scan may still run)
- Always `do_not_place=True` (the script never places) — every run → QA Bot (classic-rsi-1h-run-qa) citing `run_id`; on FAIL QA calls Trader_Classic to rerun (max 2/hour). Packs carry `auto_place_eligible`; eligible packs are auto-placed by Trader_Classic only after run-QA PASS + execute_pass + order-QA (classic-real-money-order-qa-gate) PASS
- Writes `audit/latest-auto.json` + append-only audit row (`kind=auto`)

Standing schedule (CoS routine): weekdays `CRON_TZ=America/New_York 35 9-15 * * 1-5` (after each :30 ET hour bar during RTH).

## Audit trail (append-only)

Every **propose** and **backtest** writes under `/workspace/classic_rsi/audit/`:

- `{run_id}.json` — full record (params, fingerprint, packs / aggregate)
- `latest-propose.json` / `latest-backtest.json` / `latest.json`
- `index.jsonl` — one line per run (append-only)

`run_id` is stamped on the propose payload and each `buy_pack`. **QA Bot** and Trader_Classic should cite `run_id=…` in the order thesis.

```bash
ls /workspace/classic_rsi/audit/
tail -n 5 /workspace/classic_rsi/audit/index.jsonl
```

## Do not

- Call eToro or place from this package (placing is done by Trader_Classic through the MCP) / SendToUser
- Place without run-QA PASS, order-QA PASS and an `execute_pass` GO (final cost gate)
- Emit or execute shorts from Sell triangles
- Use pip distances on US equities/ETFs
- Modify Momentum playbooks or Classic Fear/cash/weekend gates here

## Fix9: cash floor fails closed (2026-10-14, QA CASH_FLOOR_NOT_ENFORCED on run classic-rsi-auto-20261014-174135-919e9c8a)
- Root cause: from the 2026-10-14 16:12 IDT refresh on (slots `book_refresh_1612/1642/1712`), the off-box routine `classic-book-refresh-before-rsi-1h` wrote `/workspace/classic-portfolio-for-app.json` with only top-level `cash`/`equity` and no `summary` block. `auto_1h` reads cash only from `summary.availableCash`, got `None`, and `mandate_gate` treated `None` as "no block" (permissive).
- `auto_1h` now fails closed: missing or invalid `summary.availableCash` (absent, None, non-numeric, NaN/inf, negative, bool) gives the hard flag `AVAILABLE_CASH_MISSING`, the gate block `available_cash_missing`, status `GATED`, buy packs suppressed and `auto_place_eligible=False`. `--force` does not bypass it. There is no fallback to top-level `cash`.
- Writer: `book_sleeves.ensure_summary` (runs inside `recompute`, so on every `python3 -m classic_rsi.book_sleeves`) always writes `summary.availableCash` and `summary.equity` (kept if already present, else taken from top-level `cash`/`equity`), and refuses to write a book with no cash/equity. The refresh routine must run `book_sleeves` after every refresh. Its prompt should also write `summary.availableCash` + `summary.equity` itself.
- Tests: `python -m classic_rsi.test_cash_floor`.

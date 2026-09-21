---
name: Classic RSI 1H run QA
description: >-
  use this when QA must validate every Classic RSI 1H auto or propose run (audit
  integrity, long-only, ATR stops, confirmed close) and on FAIL message
  Trader_Classic to rerun then re-validate until PASS before any buy pack is
  accepted
---
# Classic RSI 1H run QA (validate → FAIL → Classic rerun → PASS)

Independent **per-run** gate for Classic RSI 1H (`auto_1h` / `propose`). Complements [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) (order packs / fills). This skill owns **run integrity and signal hygiene**, not place sizing.

**Classic only** (OfersClaw5-PRIYN / mirror `11368142`). Never Momentum. **Do not place** from this skill.

## When to run

- Immediately after every `python -m classic_rsi.auto_1h` (routine or manual)
- After every `propose` that writes an audit `run_id`
- Before accepting any RSI `buy_pack` for order-QA / place
- On CoS / Trader_Classic handoff citing a Classic RSI `run_id`

## Evidence to collect

1. `/workspace/classic_rsi/audit/<run_id>.json` (required)
2. `/workspace/classic_rsi/audit/latest-auto.json` or `latest-propose.json` matching that `run_id`
3. `/workspace/classic_rsi/audit/index.jsonl` row for the same `run_id`
4. Envelope fields: `kind` (`auto`|`propose`), `status`, `timeframe`, `confirmed_close`, `long_only`, `do_not_place`, `buy_packs`, `risk_off`, `mandate_gates`, `symbols`
5. Independent LIVE check when packs or book summary present: parent mirror `11368142` only — **REJECT keys-B**

## Hard FAIL (any one)

| Code | Condition |
| --- | --- |
| `RSI_RUN_MISSING` | No audit JSON for cited `run_id`, or latest-* points at a different run |
| `RSI_AUDIT_INCOMPLETE` | Missing `index.jsonl` row, or envelope lacks timeframe / long_only / confirmed_close / do_not_place |
| `RSI_TF_NOT_1H` | `timeframe` ≠ `1H` |
| `RSI_UNCONFIRMED_BARS` | `confirmed_close` is false or missing when status is PROPOSE with packs |
| `RSI_SHORT_OR_PIP` | Any pack implies short / sell-to-open, or uses FX pip SL/TP instead of ATR/% equity |
| `RSI_CRYPTO` | Any crypto symbol in buy_packs |
| `RSI_KEYS_B` | Book dollars taken from user-OfersClaw5 keys instead of mirror A `11368142` |
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
3. No short / pip / crypto / keys-B / place-from-auto
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

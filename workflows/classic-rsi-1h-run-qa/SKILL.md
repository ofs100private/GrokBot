---
name: Classic RSI 1H run QA
description: >-
  use this when QA must validate every Classic RSI 1H auto or propose run (audit
  integrity, long-only, ATR stops, confirmed close) and on FAIL message
  Trader_Classic to rerun then re-validate until PASS before any buy pack is
  accepted
---
# Classic RSI 1H run QA (validate → FAIL → Classic rerun → PASS)

## Standing rules update — Ofer 2026-10-17 18:44 IDT (supersedes the 2026-10-16 crypto text and any conflicting text below)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Standing rules update — Ofer 2026-10-17 18:44 IDT (supersedes the 2026-10-16 crypto text and any conflicting text below)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

- **Run-QA:**
  - `RSI_CRYPTO` now means ANY crypto in buy_packs or the universe (BTC/ETH/SOL included) → FAIL.
  - Pack levels must be SL = close − 2.5×ATR and TP = close + 5×ATR (r_multiple 2.0).
  - An envelope with `allow_crypto_buys: true` or a crypto symbol in the universe → FAIL.

## Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)

> **Shared text — canonical copy:** [Trader Classic strategy](sand-workflow:trader-classic-strategy) → section "Standing rules update — Ofer 2026-10-16 01:27 IDT (supersedes any conflicting text below)". The identical lines were removed here on 2026-10-18 (dedup); read that section — it applies here unchanged. Lines below are specific to this skill.

Independent **per-run** gate for Classic RSI 1H (`auto_1h` / `propose`). Complements [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) (order packs / fills). This skill owns **run integrity and signal hygiene**, not place sizing.

**Classic only** (Classic account (OfersClaw5-PRIYN) / `user-OfersClaw5`). Never Momentum. **Do not place** from this skill. Parent SSO mirror `11368142` is optional copy/UI corroboration only.

## Skipped slots need no run-QA — lever 3 (Ofer 2026-10-18 16:44 IDT; 2026-10-18g)

A classic-rsi-1h-auto slot that exits at step 0 has no `run_id` and needs no run-QA. That covers the precheck SKIP (`NO_CASH_FOR_MIN_ORDER` / `DAILY_BUDGET_USED`) and, new, the RSI pre-scan SKIP `NO_RSI_CANDIDATES`. It is audited instead:
- the decision line in `/workspace/classic_rsi/audit/precheck/precheck-YYYYMMDD.jsonl`;
- for `NO_RSI_CANDIDATES`, also `prescan-*.json` with the per-symbol RSI states, last bar times and `fail_open` list.
A `NO_RSI_CANDIDATES` SKIP is valid only if `prescan.n_candidates == 0`, `prescan.fail_open` is empty and the line has no pending/force reason. The pre-scan fails open on any data error or staleness, so those cases always produce a normal `run_id` that this gate validates as before. QA may spot-check any skipped slot from those files. Every run that does happen (`auto_1h` `run_id`) still gets the full run-QA; nothing here relaxes a Hard FAIL.

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

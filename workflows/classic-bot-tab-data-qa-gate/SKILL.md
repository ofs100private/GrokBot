---
name: Classic Bot tab data QA gate
description: >-
  use this when validating App Classic Bot tab / Classic RSI surfaces (portfolio
  sidecar, audit trail, backtest summary, auto envelope, tab JSON) against live
  mirror A 11368142 before go-live or refresh
---
# Classic Bot tab data QA gate

Independent QA for **App Classic Bot tab** and **Classic RSI** surfaces. Ledger **A only**: mirror **11368142** / **OfersClaw5-PRIYN**. QA never places.

Companion gates (still required):
- [Classic portfolio data QA gate](sand-workflow:classic-portfolio-data-qa-gate) for portfolio numbers
- [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) before any real-money place

## When to run

Before Classic Bot tab go-live, on every App refresh of Classic Bot / RSI JSON, and whenever CoS / App / Trader_Classic asks for Classic RSI data QA.

## Surfaces to check

| Surface | Path(s) |
|--------|---------|
| RSI audit | `/workspace/classic_rsi/audit/` — `index.jsonl`, `{run_id}.json`, `latest.json`, `latest-auto.json`, `latest-propose.json`, `latest-backtest.json` |
| Backtest summary | `/workspace/classic_rsi/backtest-summary-1h.json` |
| Portfolio sidecar | `/workspace/etoroview/public|dist/classic-portfolio.json` + GrokBot app copies |
| Classic Bot tab JSON | `/workspace/etoroview/public|dist/classic-rsi.json` + GrokBot app copies |

## Gate checklist (all must PASS)

### G1 — Classic portfolio vs live A
- Pull live parent SSO mirror **11368142** (not keys-B, not Momentum 11630170).
- Sidecar equity / cash / closed PnL / open symbols must match live A (immaterial rounding only).
- FAIL: keys-B totals, Momentum book, hardcoded/stale/invented numbers, missing live read.

### G2 — RSI audit trail integrity
- `index.jsonl` is append-only: no duplicate `run_id`, every row’s `{run_id}.json` exists.
- `latest-propose.json` **byte-equal** newest propose `{run_id}.json`.
- `latest-backtest.json` **byte-equal** newest backtest `{run_id}.json`.
- `latest.json` **byte-equal** newest run file (usually auto).
- `latest-auto.json`: same `run_id` as newest auto file; **critical fields** must match that file (`run_id`, `kind`, `do_not_place`, `long_only`, `timeframe`, `mirrorId`, `portfolio`, empty `buy_packs` when GATED). Prefer byte-equal; if App publishes a richer envelope, document the allowlisted extra keys and still require critical-field match.
- Packs / theses that cite a `run_id` must have a matching audit row + file.

### G3 — Backtest summary claims
- `timeframe` / TF = **1H** only (no other TF presented as live Classic RSI).
- `long_only` = true.
- SL/TP = ATR / price units — **not** FX pips (explicit `price_not_pips` or equivalent).
- Portfolio = Classic OfersClaw5-PRIYN / mirror 11368142 lineage only.
- No Momentum bleed (no Momentum mirror ids, books, or pack mix-ins).

### G4 — Auto envelope honesty
- `do_not_place` = true (and `place` false if present).
- Weekend / US RTH gates match calendar reality (e.g. weekend → GATED, `buy_packs` empty).
- When `status` = GATED (or equivalent), **`buy_packs` must be empty**.
- Sell / RISK_OFF tags never become short orders or short packs.

### G5 — Classic Bot tab JSON (App)
- Dual-write: etoroview public==dist and GrokBot public==dist for `classic-rsi.json` (and portfolio sidecars).
- Numbers and `run_id`s PASS only vs audit files + live A.
- FAIL hardcoded / stale / invented fields.
- FAIL Momentum data on Classic tab (negation text like “never Momentum” is OK; Momentum numbers/ids/books are not).
- Tab must not imply place authority (`do_not_place` / `doNotPlaceFromThisUi` true).

## Hard FAIL (any one)

- Shorts from Sell / RISK_OFF tags
- Keys-B presented as Classic
- Momentum data on Classic tab
- Missing live A read
- Pip SL/TP presented as Classic RSI
- Non-1H TF claimed as Classic RSI live/backtest truth
- GATED auto with non-empty `buy_packs`
- `do_not_place` false on auto / tab envelope
- Audit pointer drift: latest-propose/backtest not equal to newest run file; latest-auto `run_id` or critical fields disagree with newest auto file

## Verdict delivery

1. PASS or FAIL with gate id + evidence to **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
2. Same to **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`) when tab/JSON involved; to **Trader_Classic** when packs/orders involved
3. Tell Ofer on FAIL, and on PASS when useful (first go-live, material drift)

QA never places.

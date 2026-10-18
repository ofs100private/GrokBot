---
name: Breakout TA tab data QA gate
description: >-
  use this when validating App Breakout TA nightly tab / breakout-ta.json
  dual-write, audit run_id integrity, and Classic vs Momentum comparison blocks
  before go-live
---
# Breakout TA tab data QA gate

Independent validator for the App **Breakout TA** nightly tab and feed `breakout-ta.json`.

## When to run

After each nightly `breakout_ta.auto_daily` run, and before calling the Breakout tab data go-live / refresh done.

## Scope

- Feed: App-served copies `/workspace/etoroview/public/breakout-ta.json` + `/workspace/etoroview/dist/breakout-ta.json` must be byte-identical (single list: `breakout_ta/feed_paths.py`). latest/ and GrokBot/app copies are not served and are not checked.  
- Audit: `/workspace/breakout_ta/audit/{run_id}.json` and `latest-auto.json`  
- Comparison block vs Classic RSI / Momentum methods  
- Live books only for overlap checks: **Classic** = Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`; mirror `11368142` optional), **Momentum** = mirror `11630170` ($8k reporting truth from a live `user-etoro` read < 60 min old; `user-Momentum-HHHGDTJ` keys book as cross-check). Do **not** reject OfersClaw5 Classic figures as keys-B. A Momentum sidecar older than 60 minutes is a **FAIL**.  

## Gates

**G1 Dual-write** — public == dist for `breakout-ta.json`; `run_id` matches audit latest. **G6** — both copies parse with the real App loader (`parseBreakoutTaPayload`)  

**G2 Audit integrity** — `latest-auto.json` critical fields (run_id, confirmed/watch/failed counts, do_not_place) match `{run_id}.json`; index.jsonl has the run  

**G3 Signal honesty** — every CONFIRMED row has timeframe 1D, entry/stop/target, volume ratio; no short / sell-to-open; `doNotPlaceFromThisUi` true  

**G4 Comparison** — methods list includes breakout_ta, classic_rsi, momentum_breakout; overlap symbols ⊆ scanned universe; no invented Classic/Momentum dollars; Momentum side of Classic/Momentum comparison must come from a LIVE `user-etoro` portfolio read of mirror `11630170` less than 60 minutes old (`user-Momentum-HHHGDTJ` keys book = cross-check only). If the Momentum sidecar is older than 60 minutes → **FAIL** (refresh required; never compare against a stale sidecar)  

**G5 Live book overlap (soft exact)** — if feed claims confirmed-in-classic-book / momentum-book, those symbols must appear on live Classic account (`user-OfersClaw5`) / Momentum mirror `11630170` books (or documented ABSENT); Classic mirror `11368142` optional only  

## Hard FAIL

- Missing dual-write / mismatched copies  
- Place flags true / shorts  
- Using Momentum keys alone as Momentum reporting truth (Momentum reporting = mirror `11630170`); rejecting Classic account / OfersClaw5 figures as Classic truth  
- Momentum sidecar older than 60 minutes used for Classic/Momentum comparison (must refresh with a live read-only `user-etoro` portfolio read of mirror `11630170` first; `user-Momentum-HHHGDTJ` keys book is cross-check only)  
- Comparison claiming places authorized  
- Hardcoded stale run_id vs audit  

## PASS delivery

Send PASS/FAIL + evidence to Chief of Staff and App. QA never places.

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

Deterministic book work lives in Python: `/workspace/books/snapshot.py` (normalised cache `/workspace/books/latest/<book>.json`, history under `books/history/`) and `/workspace/books/cards.py` (card facts). Books: `classic` (user-OfersClaw5), `momentum_mirror` (mirror 11630170 in user-etoro = Momentum reporting truth), `momentum_keys` (user-Momentum-HHHGDTJ, ledger/cross-check only), `parent` (mirror 11368142, Classic copy, UI only).

1. **Check freshness first:** `cd /workspace && python3 -m books.snapshot fresh --book <book> --max-age-min <N>`. Exit 0 prints the path, so use that JSON and do not re-read. Exit 2 means stale or missing.
2. **If stale, do ONE read per book:** run `python3 -m books.snapshot agent-read-hint --book <book>`, then make exactly the MCP call(s) it prints with `write_to_file=true`. Next run `python3 -m books.snapshot ingest --book <book> --raw <file> [--raw <file2>]`. The same two user-etoro files feed both `momentum_mirror` and `parent`. If ingest refuses with `SOURCE_MISMATCH`, `MIRROR_MISSING` or `OLDER_THAN_CACHE`, that is a real data problem: stop and report it, and never hand-edit the cache.
3. **Cards:** `python3 -m books.cards --max-age-min <N> --json <out.json> --md <out.md>` gives Classic caps/core/deployable/drift/blocked/changes and Momentum stops/blocked/divergence. The LLM writes only the Buy and Sell/Rotation judgement lines (the `<LLM judgement>` placeholders) and never recomputes these facts.
4. `python3 -m books.snapshot overlap` lists cross-book symbols and keys-vs-mirror divergence.

The snapshot never changes trading rules. Caps and floors are imported from `classic_rsi` and are not redefined.

**QA usage:** for the overlap/comparison gate you may use the `classic` and `momentum_mirror` snapshots **plus one independent live read** (user-etoro for the mirror, or user-OfersClaw5). Compare symbols with the comparison block and the read. A Momentum snapshot older than 60 min is still a FAIL, as are a missing read and any mismatch.

## Scripted gate — run first (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only)
`cd /workspace && python3 -m qa_gates breakout-tab` → one verdict JSON (also saved to `/workspace/qa_gates/verdicts/latest-breakout-ta-tab.json`). Exit 0 = PASS, 1 = FAIL.
It runs G1–G6 mechanically: copy sha equality across the App-served paths, App-loader parse, feed run_id = latest-auto = run file = index row, row/summary counts, confirmed-row completeness (1D, stop < entry < target, volume ratio, do_not_place, no shorts), method set + signals run id, overlap recomputed per book, Momentum book ≤60 min (books snapshot compare is soft).
**LLM:** do not re-open the feeds or recompute anything. Read `verdict`, `hard_fail_codes` and `soft_flags`; judge only the soft flags and `llm_todo`; write the PASS/FAIL message from them. A hard fail in the script is a FAIL; you may not override it.

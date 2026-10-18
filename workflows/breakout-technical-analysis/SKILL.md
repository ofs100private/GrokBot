---
name: Breakout technical analysis
description: >-
  use this when running or reviewing the nightly Breakout TA scan/App tab —
  daily inflection+volume signals, dual-write breakout-ta.json, compare vs
  Classic RSI and Momentum breakout sleeve (Classic book from a LIVE read),
  never place
---
# Breakout technical analysis (entry / exit)

Nightly automated **inflection / breakout** scan + App tab feed. Does **not** place. Not wired into Classic/Momentum execution.

Reference lesson (logic only): `https://www.youtube.com/watch?v=reUIJ6clllo`.

## Automation

- Runner: `/workspace/screener-venv/bin/python -m breakout_ta.auto_daily`  
- Audit: `/workspace/breakout_ta/audit/`  
- App feed: `breakout-ta.json`, written atomically with identical bytes to exactly the App-served paths `/workspace/etoroview/public/breakout-ta.json` + `/workspace/etoroview/dist/breakout-ta.json` (list in `breakout_ta/feed_paths.py`; plus non-served working copy `/workspace/breakout_ta/breakout-ta.json`). Not written to latest/ or GrokBot/app (no loader reads them; GrokBot is the sanitized git export). Includes **comparison** vs Classic RSI 1H and Momentum EOD breakout sleeve  
- Routine **breakout-ta-daily-auto**: weekdays `CRON_TZ=America/New_York 15 16 * * 1-5` — **always** send Ofer a nightly digest; ping QA (`breakout-ta-tab-data-qa-gate`)  
- Tab (App): `#/breakout-ta`  

## Live Classic book (required before each run, 2026-10-07)

The Python job can't call MCP itself. Before running it: *(2026-10-18c: a fresh `books` classic snapshot (≤30 min) satisfies this. See "Shared book snapshot" below.)*
1. Do a live Classic account read (`user-OfersClaw5` portfolio summary) and save the raw JSON, e.g. `/workspace/breakout_ta/live/classic-live-<YYYYMMDD-HHMMSS>.json`.
2. Run `/workspace/screener-venv/bin/python -m breakout_ta.auto_daily --classic-live-json <that file>`.

`load_classic_book()` refuses any Classic snapshot older than 30 min (`STALE_SNAPSHOT_REFUSED`, which leaves the Classic book empty). If you skip the live read, the comparison will show no Classic names and QA will flag it.

To fix only the comparison for an existing run: `/workspace/screener-venv/bin/python -m breakout_ta.auto_daily --refresh-comparison <run_id> --classic-live-json <file>`, then re-QA (the dual-write is built in). To republish an existing feed without a scan: `./screener-venv/bin/python -m breakout_ta.feed_paths --from <breakout-ta.json> [--backup-suffix ...]`.

## Live Momentum book (required before Classic/Momentum comparison, 2026-10-15)

Classic/Momentum comparison must use a **LIVE Momentum read less than 60 minutes old**, the same freshness bar as the Classic live read. Never compare against a stale Momentum sidecar.

Before comparing:
1. Do a **read-only** `user-etoro` portfolio read of mirror **11630170** and save the raw JSON (Momentum reporting truth), e.g. `/workspace/breakout_ta/live/momentum-live-<YYYYMMDD-HHMMSS>.json`.
2. Cross-check with the **user-Momentum-HHHGDTJ** keys book (keys-side confirmation only — not reporting truth alone).
3. If the Momentum sidecar on disk is **older than 60 minutes**, refresh it with a new live read before comparing. Do **not** proceed with a stale sidecar.

Agreement ≠ place; a failed breakout on a held name is not a close instruction.

## Signals

`NONE` | `WATCH` | `BREAKOUT_CONFIRMED` | `FAILED_BREAKOUT` — daily close vs R + volume (≥ avg, prefer 1.5×).

## Levels

Entry / stop (structure + 1.5×ATR) / target (2R or measured move). Invalidation: close back below R.

## Standing rule — Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT)

**Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either. When comparing/suggesting, flag any buy-side overlap across Classic and Momentum as **blocked** (`CROSS_BOOK_OVERLAP`); never treat overlap as a green light to add.

## Comparison (required in feed)

Methods: Breakout TA (analysis-only) · Classic RSI 1H · Momentum EOD breakout. Overlaps with live books only: Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`, from a live read; mirror 11368142 optional) · Momentum mirror 11630170 ($8k, from a **live** `user-etoro` read < 60 min old; `user-Momentum-HHHGDTJ` keys book as cross-check). Include `breakout_failed_in_classic_book` / `breakout_failed_in_momentum_book`. Agreement ≠ place; a failed breakout on a held name is not a close instruction. **Never compare against a Momentum sidecar older than 60 minutes** — refresh first.

## Do not

Place · FULL AUTO attach · reject the Classic account / OfersClaw5 as Classic truth (or use Momentum keys alone as Momentum reporting truth) · build the Classic comparison from a stale snapshot file · compare Classic vs Momentum against a Momentum sidecar older than 60 minutes (refresh the live `user-etoro` mirror-11630170 read first; keys book is cross-check only) · skip the nightly user digest · skip QA on feed refresh · treat a cross-book held symbol as a buy candidate (cross-book no-overlap)

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

Deterministic book work lives in Python: `/workspace/books/snapshot.py` (normalised cache `/workspace/books/latest/<book>.json`, history under `books/history/`) and `/workspace/books/cards.py` (card facts). Books: `classic` (user-OfersClaw5), `momentum_mirror` (mirror 11630170 in user-etoro = Momentum reporting truth), `momentum_keys` (user-Momentum-HHHGDTJ, ledger/cross-check only), `parent` (mirror 11368142, Classic copy, UI only).

1. **Check freshness first:** `cd /workspace && python3 -m books.snapshot fresh --book <book> --max-age-min <N>`. Exit 0 prints the path, so use that JSON and do not re-read. Exit 2 means stale or missing.
2. **If stale, do ONE read per book:** run `python3 -m books.snapshot agent-read-hint --book <book>`, then make exactly the MCP call(s) it prints with `write_to_file=true`. Next run `python3 -m books.snapshot ingest --book <book> --raw <file> [--raw <file2>]`. The same two user-etoro files feed both `momentum_mirror` and `parent`. If ingest refuses with `SOURCE_MISMATCH`, `MIRROR_MISSING` or `OLDER_THAN_CACHE`, that is a real data problem: stop and report it, and never hand-edit the cache.
3. **Cards:** `python3 -m books.cards --max-age-min <N> --json <out.json> --md <out.md>` gives Classic caps/core/deployable/drift/blocked/changes and Momentum stops/blocked/divergence. The LLM writes only the Buy and Sell/Rotation judgement lines (the `<LLM judgement>` placeholders) and never recomputes these facts.
4. `python3 -m books.snapshot overlap` lists cross-book symbols and keys-vs-mirror divergence.

The snapshot never changes trading rules. Caps and floors are imported from `classic_rsi` and are not redefined.

**Usage:** `breakout_ta.auto_daily` now prefers `books/latest/classic.json` when ≤30 min old (status `FRESH_BOOKS_SNAPSHOT`) and `books/latest/momentum_mirror.json` when ≤60 min old. The existing `--classic-live-json` path still wins when passed, and the legacy sidecars remain the fallback. Preferred pre-run flow: `fresh` for each book, and for stale books one hinted read plus `ingest`, then run the job (no `--classic-live-json` needed). Ingest the keys book too for the divergence cross-check.

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
- App feed: `breakout-ta.json` (etoroview + GrokBot public/dist/latest) including **comparison** vs Classic RSI 1H and Momentum EOD breakout sleeve  
- Routine **breakout-ta-daily-auto**: weekdays `CRON_TZ=America/New_York 15 16 * * 1-5` — **always** send Ofer a nightly digest; ping QA (`breakout-ta-tab-data-qa-gate`)  
- Tab (App): `#/breakout-ta`  

## Live Classic book (required before each run, 2026-10-07)

The Python job can't call MCP itself. Before running it:
1. Do a live Classic account read (`user-OfersClaw5` portfolio summary) and save the raw JSON, e.g. `/workspace/breakout_ta/live/classic-live-<YYYYMMDD-HHMMSS>.json`.
2. Run `/workspace/screener-venv/bin/python -m breakout_ta.auto_daily --classic-live-json <that file>`.

`load_classic_book()` refuses any Classic snapshot older than 30 min (`STALE_SNAPSHOT_REFUSED`, which leaves the Classic book empty). If you skip the live read, the comparison will show no Classic names and QA will flag it.

To fix only the comparison for an existing run: `/workspace/screener-venv/bin/python -m breakout_ta.auto_daily --refresh-comparison <run_id> --classic-live-json <file>`, then re-dual-write and re-QA.

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

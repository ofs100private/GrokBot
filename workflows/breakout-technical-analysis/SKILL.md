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

## Signals

`NONE` | `WATCH` | `BREAKOUT_CONFIRMED` | `FAILED_BREAKOUT` — daily close vs R + volume (≥ avg, prefer 1.5×).

## Levels

Entry / stop (structure + 1.5×ATR) / target (2R or measured move). Invalidation: close back below R.

## Comparison (required in feed)

Methods: Breakout TA (analysis-only) · Classic RSI 1H · Momentum EOD breakout. Overlaps with live books only: Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`, from a live read; mirror 11368142 optional) · Momentum mirror 11630170 ($8k). Include `breakout_failed_in_classic_book` / `breakout_failed_in_momentum_book`. Agreement ≠ place; a failed breakout on a held name is not a close instruction.

## Do not

Place · FULL AUTO attach · reject the Classic account / OfersClaw5 as Classic truth (or use Momentum keys alone as Momentum reporting truth) · build the Classic comparison from a stale snapshot file · skip the nightly user digest · skip QA on feed refresh

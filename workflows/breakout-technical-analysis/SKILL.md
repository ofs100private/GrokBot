---
name: Breakout technical analysis
description: >-
  use this when running or reviewing the nightly Breakout TA scan/App tab —
  daily inflection+volume signals, dual-write breakout-ta.json, compare vs
  Classic RSI and Momentum breakout sleeve, never place
---
# Breakout technical analysis (entry / exit)

Nightly automated **inflection / breakout** scan + App tab feed. Does **not** place. Not wired into Classic/Momentum execution.

Reference lesson (logic only): `https://www.youtube.com/watch?v=reUIJ6clllo`.

## Automation

- Runner: `python -m breakout_ta.auto_daily`  
- Audit: `/workspace/breakout_ta/audit/`  
- App feed: `breakout-ta.json` (etoroview + GrokBot public/dist) including **comparison** vs Classic RSI 1H and Momentum EOD breakout sleeve  
- Routine **breakout-ta-daily-auto**: weekdays `CRON_TZ=America/New_York 15 16 * * 1-5` — **always** send Ofer a nightly digest; ping QA (`breakout-ta-tab-data-qa-gate`)  
- Tab (App): `#/breakout-ta`  

## Signals

`NONE` | `WATCH` | `BREAKOUT_CONFIRMED` | `FAILED_BREAKOUT` — daily close vs R + volume (≥ avg, prefer 1.5×).

## Levels

Entry / stop (structure + 1.5×ATR) / target (2R or measured move). Invalidation: close back below R.

## Comparison (required in feed)

Methods: Breakout TA (analysis-only) · Classic RSI 1H · Momentum EOD breakout. Overlaps with live books only (mirrors 11368142 / 11630170). Agreement ≠ place.

## Do not

Place · FULL AUTO attach · keys-B as truth · skip nightly user digest · skip QA on feed refresh

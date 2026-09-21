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

- Feed: `/workspace/etoroview/public/breakout-ta.json` (+ dist + GrokBot public/dist) must be byte-identical  
- Audit: `/workspace/breakout_ta/audit/{run_id}.json` and `latest-auto.json`  
- Comparison block vs Classic RSI / Momentum methods  
- Live books only for overlap checks: Classic mirror `11368142`, Momentum mirror `11630170` ($8k) — reject keys-B  

## Gates

**G1 Dual-write** — public == dist == GrokBot copies for `breakout-ta.json`; `run_id` matches audit latest  

**G2 Audit integrity** — `latest-auto.json` critical fields (run_id, confirmed/watch/failed counts, do_not_place) match `{run_id}.json`; index.jsonl has the run  

**G3 Signal honesty** — every CONFIRMED row has timeframe 1D, entry/stop/target, volume ratio; no short / sell-to-open; `doNotPlaceFromThisUi` true  

**G4 Comparison** — methods list includes breakout_ta, classic_rsi, momentum_breakout; overlap symbols ⊆ scanned universe; no invented Classic/Momentum dollars  

**G5 Live book overlap (soft exact)** — if feed claims confirmed-in-classic-book / momentum-book, those symbols must appear on live mirror A books (or documented ABSENT)  

## Hard FAIL

- Missing dual-write / mismatched copies  
- Place flags true / shorts  
- Momentum keys-B or Classic keys-B as truth  
- Comparison claiming places authorized  
- Hardcoded stale run_id vs audit  

## PASS delivery

Send PASS/FAIL + evidence to Chief of Staff and App. QA never places.

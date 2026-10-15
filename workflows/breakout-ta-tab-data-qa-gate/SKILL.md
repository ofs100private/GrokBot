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
- Live books only for overlap checks: **Classic** = Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`; mirror `11368142` optional), **Momentum** = mirror `11630170` ($8k reporting truth from a live `user-etoro` read < 60 min old; `user-Momentum-HHHGDTJ` keys book as cross-check). Do **not** reject OfersClaw5 Classic figures as keys-B. A Momentum sidecar older than 60 minutes is a **FAIL**.  

## Gates

**G1 Dual-write** — public == dist == GrokBot copies for `breakout-ta.json`; `run_id` matches audit latest  

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

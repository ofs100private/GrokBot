---
name: Momentum real-money QA gate
description: >-
  use this when validating Momentum-HHHGDTJ screener buys, position_manager risk
  actions, or post-EOD audits before/after execution — unlimited stocks + ≥1 ETF
  capacity (2026-10-05); keys cash must gate authorize_place
---
# Momentum real-money QA gate

Independent validation for Momentum-HHHGDTJ (REAL MONEY). QA Bot co-owns the gate; the trader must not self-grade as PASS without evidence.

**Also run** [Momentum screener run QA](sand-workflow:momentum-screener-run-qa) on every screener execution (full S&P ≥400, TRACE, FAIL→rerun).

Playbook **2026-09-16 full fix** + **sleeve capacity 2026-10-05** (Ofer): unlimited open stocks; at least 1 sector ETF; cash + ≤$1000/name gate size. See [Trader Momentum strategy](sand-workflow:trader-momentum-strategy).

## When to run

- Before every EOD BUY (after screener-run QA PASS)
- Before every CLOSE / MOVE_SL_BREAKEVEN / **TRAIL_SL**
- After every fill
- Daily feedback ~23:05 IL; miss checks ~22:50 IL
- `EOD_SCREENER_MISSED` HIGH AVOID only if no screener ACTION ≤22:50 IL (early/manual counts; catch-up never clears). Soft `SCHEDULED_2245_LATE` if cron late but gate already cleared — see trader-momentum-strategy EOD feedback scoring.

## Cash books (Mirror A vs keys)

- **Mirror A** (11630170 / parent SSO) = copy-basis truth for **reporting** and book allocation.
- **Keys** (`user-Momentum-HHHGDTJ`) = **execution** cash; may diverge from Mirror A.
- **`authorize_place` rule (hardened 2026-10-05 after r2 gap):** set `authorize_place=true` **only** when **keys** `availableCash` covers each intended fill **in sequence** (fees buffer). Mirror A cash alone must **never** authorize place. If Mirror A covers but keys cannot → overall `PASS_WITH_GATE_OK` or per-name `INSUFFICIENT_CASH` **GATE_OK**, `authorize_place=false` on blocked names (trim to keys-coverable prefix only if explicitly re-validated). Do **not** emit a bare place-PASS that FULL AUTO would treat as placeable when keys cannot execute.
- After a keys cash/state change, require a **fresh** place-QA (no self-PASS; flag `PLACE_WITHOUT_QA_BOT_RECHECK`).
- Lesson 2026-10-05: r2 place-QA sized off Mirror A ~$4361 while keys had ~$1612 (then ~$610 after NTAP) → ANET/FFIV failed at place. Breach pattern = Mirror-A-only authorize.

## Pack / sleeve FAIL if

- **Do NOT** FAIL on open stock count / `SLEEVE_CAPACITY_FULL` / `stock_buys > 3` / `buy_count > 4` (obsolete 2026-10-05 — unlimited stocks). Pre-mandate r1 FAIL under the old ≤3-stock cap is **superseded** by the unlimited-sleeve playbook and is **not** scored as a standing AVOID/deviation.
- etf_buys > 1 (still max 1 new ETF per pack)
- Book has **zero** sector ETFs in HEALTHY and pack adds only stocks with no ETF candidate when cash allows (prefer ≥1 ETF)
- more than **2** `MOMENTUM_BREAKOUT` buys **in the same pack night** (quality preference)
- `MOMENTUM_BREAKOUT` with RVOL < 2.0 (soft regime: < 2.5)
- Soft-regime VCP / quiet volume BUY (`REGIME_SOFT_VCP_BLOCK` required instead)
- Any BUY on `EVENT_VOL_FREEZE` or HARD_HALT day
- ETF BUY in SOFT regime
- DWM week/month red on BUY
- leverage ≠ 1, amount > $1000, demo, short, bad mcp/stop shape
- Mirror A cash cannot cover the authorized pack (`INSUFFICIENT_CASH` = GATE_OK)
- Keys execution cash cannot cover the pack as sequenced (`INSUFFICIENT_CASH` = GATE_OK; `authorize_place=false`)

## Regime

- EVENT_VOL_FREEZE (today or next NYSE session FOMC/CPI/NFP): 0 BUY; SKIP/HALT OK; scan+near-miss required
- HARD_HALT (VIX≥25 or SPX<0.98×SMA50): 0 BUY; scan+near-miss required
- SOFT: STOCK only MOMENTUM_BREAKOUT + RVOL≥2.5 + RS≥90 + DWM
- HEALTHY: breakout + VCP under pack rules; unlimited open stocks OK if **keys** cash covers

## Exits

- CLOSE below SMA50 **or** unrealized PnL% ≤ −4 (`LOSS_PCT_GE_4`)
- MOVE_SL_BREAKEVEN at ≥2R
- TRAIL_SL at ≥1R (new stop ≥ prior; cites 1R; 10d-low floor)
- Priority: CLOSE (SMA50 or −4%) > BE > TRAIL > HOLD

## FULL AUTO

After place-QA with **`authorize_place=true`** (keys cash verified), Trader_momentum places without user/CoS chat confirmation. QA never places. Tell user on FAIL and on fills.

**Cash / state / rule change:** `INSUFFICIENT_CASH` = GATE_OK (not process AVOID). After cash frees, book changes, **or sleeve rule changes**, trader must send a **new** place-QA request with the new mirror A **and** keys cash snapshot + rule; prior FAIL/no-fill guidance is not authority to place. Flag `PLACE_WITHOUT_QA_BOT_RECHECK` if they self-PASS.

## Verdict routing

FAIL/PASS → Momentum trader; material FAIL → CoS; fills → user after the fact.

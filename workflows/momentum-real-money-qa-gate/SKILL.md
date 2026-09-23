---
name: Momentum real-money QA gate
description: >-
  use this when validating Momentum-HHHGDTJ screener buys, position_manager risk
  actions, or post-EOD audits before/after execution
---
# Momentum real-money QA gate

Independent validation for Momentum-HHHGDTJ (REAL MONEY). QA Bot co-owns the gate; the trader must not self-grade as PASS without evidence.

**Also run** [Momentum screener run QA](sand-workflow:momentum-screener-run-qa) on every screener execution (full S&P ≥400, TRACE, FAIL→rerun).

Playbook **2026-09-16 full fix**: breakout sleeve primary, VCP secondary, event-vol freeze, soft-regime harden, TRAIL_SL @ 1R. See `/workspace/momentum_audit/playbook-2026-09-16-full-fix.md`.

## When to run

- Before every EOD BUY (after screener-run QA PASS)
- Before every CLOSE / MOVE_SL_BREAKEVEN / **TRAIL_SL**
- After every fill
- Daily feedback ~23:05 IL; miss checks ~22:50 IL

## Pack / sleeve FAIL if

- stock_buys > 3 or etf_buys > 1 or buy_count > 4
- more than **2** `MOMENTUM_BREAKOUT` buys
- `MOMENTUM_BREAKOUT` with RVOL < 2.0 (soft regime: < 2.5)
- Soft-regime VCP / quiet volume BUY (`REGIME_SOFT_VCP_BLOCK` required instead)
- Any BUY on `EVENT_VOL_FREEZE` or HARD_HALT day
- ETF BUY in SOFT regime
- DWM week/month red on BUY
- leverage ≠ 1, amount > $1000, demo, short, bad mcp/stop shape

## Regime

- EVENT_VOL_FREEZE (today or next NYSE session FOMC/CPI/NFP): 0 BUY; SKIP/HALT OK; scan+near-miss required
- HARD_HALT (VIX≥25 or SPX<0.98×SMA50): 0 BUY; scan+near-miss required
- SOFT: STOCK only MOMENTUM_BREAKOUT + RVOL≥2.5 + RS≥90 + DWM
- HEALTHY: breakout + VCP under pack rules

## Exits

- CLOSE below SMA50 **or** unrealized PnL% ≤ −4 (`LOSS_PCT_GE_4`)
- MOVE_SL_BREAKEVEN at ≥2R
- TRAIL_SL at ≥1R (new stop ≥ prior; cites 1R; 10d-low floor)
- Priority: CLOSE (SMA50 or −4%) > BE > TRAIL > HOLD

## FULL AUTO

After PASS, Trader_momentum places without user/CoS chat confirmation. QA never places. Tell user on FAIL and on fills.

**Cash / state change:** `INSUFFICIENT_CASH` = GATE_OK (not process AVOID). After cash frees or book changes, trader must send a **new** place-QA request with the new mirror A cash snapshot; prior FAIL/no-fill guidance is not authority to place. Flag `PLACE_WITHOUT_QA_BOT_RECHECK` if they self-PASS.

## Verdict routing

FAIL/PASS → Momentum trader; material FAIL → CoS; fills → user after the fact.

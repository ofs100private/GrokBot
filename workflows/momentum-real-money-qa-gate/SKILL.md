---
name: Momentum real-money QA gate
description: >-
  use this when validating Momentum-HHHGDTJ screener buys, position_manager risk
  actions, or post-EOD audits before/after execution
---
# Momentum real-money QA gate

Independent validation for **Trader_momentum** on portfolio **Momentum-HHHGDTJ** (REAL MONEY). QA Bot co-owns the gate; the trader must not self-grade as PASS without evidence.

## When to run

- Before every EOD BUY from `momentum_screener.py`
- Before every CLOSE / MOVE_SL_BREAKEVEN from `position_manager.py`
- After every fill (post-audit)
- Daily feedback at ~23:05 Israel (`momentum_qa.feedback_daily`)

## Code gate (must run)

```bash
/workspace/screener-venv/bin/python /workspace/momentum_screener.py
/workspace/screener-venv/bin/python /workspace/position_manager.py --positions-json '...'
/workspace/screener-venv/bin/python -m momentum_qa.feedback_daily
```

Audit JSONL: `/workspace/momentum_audit/YYYY-MM-DD.jsonl`  
Lessons: `/workspace/trading-lessons/momentum/YYYY-MM-DD/`

Every ACTION in the audit must include a non-empty **rationale**. Every strategy breach is a **DEVIATION** with `deviation_code`.

## Hard FAIL (any one)

- Portfolio ≠ Momentum-HHHGDTJ / touching Classic
- leverage ≠ 1; short / sell-to-open; demo account
- Missing rationale on BUY / CLOSE / BE
- mcp_order_params missing account/direction/orderType/stopLossType or using isBuy/isTakeProfitEnabled
- stopLossRate looks like percent (not absolute price)
- STOCK VOLUME_BREAKOUT with RVOL &lt; 1.5
- ETF/commodity outside allowlists
- amount &gt; $1000 allocation cap / more than 3 buys
- Place during Israel 16:30–18:30 intraday ban
- Place on NYSE holiday
- BUY while regime HALT (SPX &lt; SMA50 or VIX ≥ 25)
- CLOSE without BELOW_SMA50 evidence; BE without HIT_2R (R≥2)

## PASS

Only long ×1 real Momentum actions with rationale + evidence that clear every hard fail. FULL AUTO still requires PASS before place.

## Daily feedback loop

1. Read today's audit JSONL
2. Split KEEP (aligned + QA PASS) vs AVOID (deviations / QA FAIL) — each with clear rationale
3. Write `daily_feedback.json` + `.md` under trading-lessons/momentum
4. Message QA Bot with FAIL counts / top deviation codes; tell Ofer only if material deviations or fills

## Verdict routing

1. FAIL / PASS with reasons → Trader_momentum (this agent)
2. Copy material FAIL to QA Bot `498c78db-a027-4f2c-8126-3c2be6f0a4bb`
3. Tell Ofer on FAIL, and on PASS when a fill occurred

Compose with [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop) for scoring after the day.

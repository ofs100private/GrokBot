# Momentum playbook — FULL FIX 2026-09-16 (IL)

Implements Ofer’s four decisions: breakout sleeve primary + VCP secondary, FOMC/event-vol freeze, stronger soft-regime gate, trail winners after 1R. **No trades placed by this change set.** Skills are NOT updated here — CoS owns skill bodies; draft text below for CoS.

## Files changed
- `/workspace/momentum_screener.py` — BREAKOUT/VCP sleeves, soft harden, event freeze, pack 2+1 stocks
- `/workspace/position_manager.py` — `TRAIL_SL` after ≥1R (10-session low floor); priority CLOSE > BE@2R > TRAIL@1R > HOLD
- `/workspace/momentum_qa/event_calendar.py` — **new** `is_event_vol_freeze(now_il)`
- `/workspace/momentum_qa/validate.py` — MOMENTUM_BREAKOUT RVOL≥2.0 / soft VCP block / max 2 breakouts / TRAIL_SL QA
- `/workspace/momentum_qa/test_validate.py` — pack 2BO+1VCP, soft VCP rewrite, EVENT_VOL_FREEZE, TRAIL_SL
- `/workspace/momentum_audit/playbook-2026-09-16-full-fix.md` — this changelog

## Exact new rules

### 1) Sleeves (stocks, after Minervini trend stack + RS≥80)
| Sleeve | Tag | Requirements |
|--------|-----|----------------|
| **BREAKOUT** (preferred) | `reason=MOMENTUM_BREAKOUT`, `setup_type=BREAKOUT` | RS≥90, RVOL≥2.0, close ≥ max(prior 20 closes), close in upper third of day range ≥0.66, day/week/month ≥0 |
| **VCP** (secondary) | `VCP_SETUP` or `VOLUME_BREAKOUT` | VCP contraction **or** volume breakout RVOL≥1.5 + pivot; RS≥80; week/month green |

**Packing:** sort breakouts by RS → take ≤**2**; fill remaining stock slots to **3** with VCP/volume (VOLUME_BREAKOUT before quiet VCP, then RS); then **1** sector ETF if HEALTHY (soft/hard already block ETF buys); commodity only if no sector ETF. Still ×1, $1000, SPX universe ≥400.

Near-miss: high-RS (≥90) stock that fails both sleeves → `blocked_by=NO_BREAKOUT_NO_VCP`.

### 2) Event-vol freeze
`is_event_vol_freeze(now_il) → (bool, reason)`:
- Freeze if **today** (NY date) **or next NYSE session** is on the static event list.
- Prior-session freeze: if next open is event day, tonight’s EOD freezes too.
- On freeze: convert would-be BUYs → `SKIP EVENT_VOL_FREEZE`; emit `HALT` row `reason=EVENT_VOL_FREEZE`; still scan + near-miss.

Hardcoded (editable) Q3–Q4 2026 + known FOMC:
- **FOMC decision days** (Fed calendar): 2026-01-28, 03-18, 04-29, 06-17, 07-29, **09-16**, 10-28, 12-09 (+ 2027-01-27)
- **NFP** (BLS empsit): 07-02, 08-07, 09-04, 10-02, 11-06, 12-04
- **CPI**: 10-14, 11-10, 12-10 confirmed BLS; 07-14 / 08-12 / 09-11 approximate — **Ofer may edit**

### 3) Soft regime (SPX under SMA50 but ≥0.98×SMA50, VIX&lt;25)
- STOCK BUY **only** if `MOMENTUM_BREAKOUT` **and** RVOL≥**2.5** **and** RS≥90 **and** DWM green
- Soft VCP / quiet VOLUME_BREAKOUT → `SKIP REGIME_SOFT_VCP_BLOCK`
- Soft ETF/commodity → `REGIME_SOFT_ETF_BLOCK` (unchanged)
- HARD_HALT unchanged (0 buys, scan+near-miss)
- HEALTHY: both sleeves OK under pack rules

### 4) Position manager trail after 1R
Priority: **CLOSE** (below SMA50) → **MOVE_SL_BREAKEVEN** (≥2R, SL→entry if not already ≥entry) → **TRAIL_SL** (≥1R and stop below entry) → **HOLD**.

`TRAIL_SL` `new_stop_loss = max(prior_stop or 0, min(entry, 10-session Yahoo low))`, then clamp ≤ last−ε; never lower an existing stop; never trail above entry via TRAIL (BE handles ≥entry at 2R).

QA: `validate_position_action` PASS on TRAIL_SL when rationale/reason cites 1R, `new_stop_loss` present, and not below `prior_stop_loss` if provided.

## Kept unchanged
- Full SPX ≥400, StringIO+cache, no mega-cap fallback
- QA PASS→place gate, leverage ×1, $1000, real account
- DWM week/month green hard gate for buys
- Pack shape: ≤3 stocks + ≤1 sector ETF

## Draft skill text (for CoS — do not treat as live skill)
```
Momentum screener (2026-09-16): prefer MOMENTUM_BREAKOUT (RS≥90 RVOL≥2.0 20d close high
upper-third DWM day+week+month green); secondary VCP_SETUP / VOLUME_BREAKOUT.
Pack ≤2 breakouts then fill to 3 stocks; +1 sector ETF only in HEALTHY.
SOFT: only MOMENTUM_BREAKOUT with RVOL≥2.5. EVENT_VOL_FREEZE on FOMC/CPI/NFP
(today or next NYSE session) → no new buys. Position manager: CLOSE <SMA50;
TRAIL_SL at ≥1R (10d low floor); MOVE_SL_BREAKEVEN at ≥2R.
```

## Tests
Run: `cd /workspace && /workspace/screener-venv/bin/python momentum_qa/test_validate.py`

## Do not (this change set)
- Full yfinance EOD screener run
- Git commit
- Place trades / SendToAgent

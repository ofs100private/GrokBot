# Momentum-HHHGDTJ RCA | 2026-09-15 (IL)

Evidence window: audit JSONL 2026-09-11, 2026-09-14, 2026-09-15 only (Fri/Mon/Tue; weekend blank expected).

## Strategy gates (exact)

From /workspace/momentum_screener.py:
1. Session: NYSE open; not INTRADAY_BAN else SKIP
2. Regime FIRST: HALT if SPX < SMA50 OR VIX >= 25 (MARKET_REGIME_RISK)
3. Universe: full S&P500 (>=400 required) + 11 sector ETFs + 6 commodity ETFs; StringIO+cache; no mega-cap fallback
4. Minervini template: price>SMA150>SMA200; SMA200 rising; SMA50>SMA150; price>SMA50; >=30% above 52w low; within 15% of 52w high; RS>=80
5. Setup: STOCK breakout needs RVOL>=1.5 + close>pivot + green day; ETF/COMMODITY breakout no RVOL; OR VCP
6. DWM hard gate: week<0 OR month<0 -> SKIP DWM_STRENGTH_FAIL
7. Cap: max_picks=3, $1000, leverage 1 long only; sort BREAKOUT first then RS desc

PM: CLOSE if below SMA50; MOVE_SL_BREAKEVEN at >=2R; else HOLD. No entries.

## Timing lastRunAt (IL) as of diagnosis ~23:15

- PM 40 22: lastRunAt 2026-09-14 22:43 — Sep15 MISSED
- Screener 45 22: lastRunAt 2026-09-14 22:53 — Sep15 MISSED
- Watchdog 50 22: lastRunAt 2026-09-14 23:12 — Sep15 cron not updated
- Feedback 5 23: lastRunAt 2026-09-14 23:35 — not updated

Sep11 EOD_SCREENER_MISSED (PRIORITY delay). Sep15 EOD_PM_MISSED + both scheduled missed; catch-up HALT.

## Scorecard

| Day | Fills | Outcome |
| 9/11 | XLE+XLK | NVDA DWM skip; late screener catch-up |
| 9/14 | 0 | XLK DWM fail; PM+screener OK chained |
| 9/15 | 0 | cron miss; HALT SPX~7580 < SMA50~7611; HOLD all |

## Ranked causes
1. PROCESS cron reliability (9/11, 9/15)
2. STRATEGY regime HALT (9/15)
3. STRATEGY DWM (NVDA 9/11, XLK 9/14)
4. STRATEGY ETF/VCP + max_picks=3 crowds stocks
5. PROCESS/DATA Wikipedia mega-cap bug (fixed)

Full CoS paste is in the agent final message.

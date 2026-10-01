---
name: Trader Momentum strategy
description: >-
  use this when planning, reviewing, or executing Trader_momentum EOD buys/sells
  on Momentum-HHHGDTJ — full auto after QA PASS, no user confirmation, playbook
  2026-09-16 breakout sleeve + event freeze + 1R trail
---
# Trader Momentum strategy

Standing playbook for **Trader_momentum** on portfolio **Momentum-HHHGDTJ** (REAL MONEY, reporting basis **$8,000** parent mirror `11630170` only — never report keys MCP totals as Momentum dollars).

Changelog: `/workspace/momentum_audit/playbook-2026-09-16-full-fix.md` (supersedes 2026-09-15 sleeve/regime notes where they conflict).

## FULL AUTO (Ofer)

**Buy and sell without waiting for the user in chat.** After [Momentum screener run QA](sand-workflow:momentum-screener-run-qa) PASS and [Momentum real-money QA gate](sand-workflow:momentum-real-money-qa-gate) PASS **from QA Bot**, **prepare then place immediately**. No confirm widget. No waiting for CoS/Ofer “go.” Report fills after the fact.

Same auto rule for position_manager **CLOSE**, **MOVE_SL_BREAKEVEN**, and **TRAIL_SL** when QA PASS. HOLD needs no place. Platform Auto-review cards are the host gate, not chat confirmation. `WaitingForMarket` = leave working order; do not re-place.

### Cash-block → recheck (CoS / QA Bot 2026-09-22)

`INSUFFICIENT_CASH` place-QA FAIL is a **GATE_OK** protective reject (audit FAIL row OK; **not** a playbook AVOID).

If cash later frees (e.g. after `LOSS_PCT_GE_4` / SMA50 closes) and a prior pack name becomes placeable:

1. Pull **fresh** mirror A `11630170` availableCash (eToro Account / mirror truth — never keys alone).
2. **Re-ask QA Bot** for place-QA citing the new cash + book state + exact amount/SL.
3. Place **only** on that **new** PASS. Do **not** self-PASS, reuse the earlier FAIL pack, or treat cash-freed as authority to place.
4. Process AVOID if violated: `PLACE_WITHOUT_QA_BOT_RECHECK`.

## Mandate

- Long-only, leverage **×1**, amount **≤ $1,000** per name
- Full S&P 500 scan every NYSE EOD (≥400). TRACE + retry ≤3
- Pack: up to **3 stocks** + **1 sector ETF**
- DWM: week and month green required for buys (breakout also needs day ≥ 0)
- REAL only; never Classic; never demo
- Intraday ban 16:30–18:30 Israel; skip NYSE holidays

## Sleeves (stocks) — playbook 2026-09-16

1. **MOMENTUM_BREAKOUT** (preferred, max **2** of 3 stock slots): RS ≥ 90, RVOL ≥ 2.0, new 20-day close high, close in upper third of day’s range, DWM day+week+month ≥ 0
2. **VCP_SETUP / VOLUME_BREAKOUT** (secondary): fill remaining stock slots; RS ≥ 80; week+month green
3. Then **1 sector ETF** only in **HEALTHY** regime; commodity only if no sector ETF

Near-miss high-RS names that fail both sleeves: `NO_BREAKOUT_NO_VCP`.

## Regime

- **EVENT_VOL_FREEZE**: today or next NYSE session is FOMC / CPI / NFP (`momentum_qa.event_calendar`) → **0 new buys**; still scan + near-miss
- **HARD_HALT**: VIX ≥ 25 or SPX < 0.98×SMA50 → 0 buys; scan + near-miss
- **SOFT**: SPX under SMA50 but ≥ 0.98×SMA50 → STOCK BUY only if **MOMENTUM_BREAKOUT** with RVOL ≥ 2.5; quiet VCP → `REGIME_SOFT_VCP_BLOCK`; no new ETF
- **HEALTHY**: both sleeves under pack rules

## Exits (EOD position manager)

Priority per name: **CLOSE** (last < SMA50 **or** unrealized PnL% ≤ −4 vs avg open → `LOSS_PCT_GE_4`) → **MOVE_SL_BREAKEVEN** (≥ 2R to entry) → **TRAIL_SL** (≥ 1R: trail to max(prior stop, min(entry, 10-day low)); never lower stop) → **HOLD**

## EOD chain

Weekdays IL: **22:40** PM → same-wake screener → **22:45** backup → **22:50** watchdog. If skipped, `eod_miss_check.next_job` (PM first). QA PASS → place.

### Daily feedback miss scoring (QA / CoS 2026-09-23)

Do **not** tighten the miss rule. Score `EOD_SCREENER_MISSED` as follows:

1. **On-time (not a miss):** any `momentum_screener` **ACTION** (`BUY` / `HALT` / `SKIP` / `ERROR`) with `ts_il` ≤ **22:50 IDT** that NYSE day clears the gate — including early/manual runs (T21+). Implemented in `momentum_qa.eod_miss_check.screener_actions_by_deadline` + `feedback_daily`.
2. **True miss AVOID:** no screener ACTION ≤22:50 IDT. A post-22:50 **catch-up** does **not** clear a true miss (still log process hygiene, but keep AVOID for the miss).
3. **Optional soft flag** `SCHEDULED_2245_LATE`: scheduled 22:40/22:45 cron was late or skipped, but an earlier ACTION ≤22:50 still existed — cron hygiene only; **not** `EOD_SCREENER_MISSED`.

False-positive example (2026-09-23): early ACTION BUY GILD ~21:52 IDT before gate; scorer wrongly flagged miss because it only counted the 23:04 catch-up.

## Post place-QA execution ACK (CoS / Ops 2026-10-01)

Wed 2026-09-30: place-QA **PASS** for JNJ CLOSE + CRWD BE, but Mirror A next day still held JNJ and CRWD SL stayed 230.85 (cash still ~$549.77). Root: keys MCP mixed-auth 422 + no Trader place wake after PASS; watchdog marked CLEAN because screener/PM ran, not because fills landed.

**Mandatory after any place-QA PASS (CLOSE / MOVE_SL_BREAKEVEN / TRAIL_SL / BUY):**

1. Trader_momentum prepares+places in the **same wake** (FULL AUTO). Do not end the wake on PASS alone.
2. Write audit `place_ack` row: `PLACED` | `WAITING_FOR_MARKET` | `BLOCKED_KEYS_MCP` | `SKIPPED_REASON` with mirror A positionId + xRequestId.
3. **Sticky pending queue:** once authorize_place PASS for CLOSE/BE/TRAIL, keep until Mirror A confirms (position gone / SL ≥ new_stop / cash freed). Re-attempt next EOD even if live R later slips below 2R (missed BE is still debt).
4. Watchdog / eod_miss_check: if `authorize_place_now` has no matching place_ack within ~15m → **`EOD_PLACE_NOT_ACKED`** (not CLEAN). Scan/PM ACTION alone is insufficient.
5. Execution path: keys MCP must be keys-only (no mixed OAuth). If keys broken, route place via documented working Real path — never silent skip after PASS.
6. Thin cash (&lt;~$1000) + ≥8 names: log `CASH_RECYCLE_REQUIRED`; BUY pack is advisory until a CLOSE frees room; then **fresh** place-QA (existing cash-block rule).

See `/workspace/momentum_audit/improvement-2026-10-01.md`.

## Do not

Wait for chat confirmation after QA PASS. Average down. Buy VCP into soft regime. Buy into event freeze. Treat keys MCP as the $8k book. Double-buy a name filled this session. Place after a prior place-QA FAIL without a **fresh** QA Bot place-QA PASS on the new cash/book snapshot (`PLACE_WITHOUT_QA_BOT_RECHECK`).

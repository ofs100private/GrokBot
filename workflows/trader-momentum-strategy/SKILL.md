---
name: Trader Momentum strategy
description: >-
  use this when planning, reviewing, or executing Trader_momentum EOD buys/sells
  on Momentum-HHHGDTJ — full auto after QA PASS, place_lock before prepare-trade,
  playbook 2026-09-16 + capacity 2026-10-05 (unlimited stocks, ≤1 new ETF/pack)
---
# Trader Momentum strategy

Standing playbook for **Trader_momentum** on portfolio **Momentum-HHHGDTJ** (REAL MONEY, reporting basis **$8,000** parent mirror `11630170` only — never report keys MCP totals as Momentum dollars).

Changelog: `/workspace/momentum_audit/playbook-2026-09-16-full-fix.md` (supersedes 2026-09-15 sleeve/regime notes where they conflict). Sleeve capacity updated **2026-10-05** (Ofer): unlimited stocks + at least 1 ETF.

## Code-first (2026-10-18)

Ofer rule: Momentum runs code-first like Classic. Trading rules are unchanged; only the mechanics changed.

- **Scripts do all deterministic work** (session/holiday, cash, positions, SL checks, overlap, PM, screener, QA). The agent only does MCP reads/places and relays results.
- **MCP reads go to files:** call with `write_to_file=true`, then pass the file path to a script. Never paste raw JSON into a command or reason over it by hand.
- **Step 0 = precheck** (from `/workspace`):
  `./screener-venv/bin/python -m momentum_qa.precheck --raw <mkeys get-my-positions-and-orders file> [--classic-raw <OfersClaw5 read file>] [--cash-json <user-etoro portfolio-summary file> | --cash N]`
  Exit **10** = silent SKIP (NYSE closed/holiday, or free cash < min order with nothing to manage): end the wake, no message. Exit **0** = PROCEED (open positions, pending orders, missing SL, risk action, or cash for a new order; any unreadable/stale input also proceeds). On a closed day `--raw` can be omitted, so the MCP read can wait until after the session check. Summary: `/workspace/momentum_audit/precheck/precheck-latest.json` (cash, positions, `pm_positions`, pending orders, overlap, Classic `buy_blocklist`). Audit: `/workspace/momentum_audit/precheck-YYYY-MM-DD.jsonl`. Keys balance may 403: take cash from the mirror 11630170 read (`--cash-json`).
- **Then:** `./screener-venv/bin/python position_manager.py --positions-file /workspace/momentum_audit/precheck/precheck-latest.json --out <pm.json>` and `./screener-venv/bin/python momentum_screener.py --classic-json <Classic positions file> --out <screener.json>`.
- **Fixed, tested scripts only** (`momentum_qa/precheck.py`, `momentum_qa/open_gap_check.py`, `position_manager.py`, `momentum_screener.py`, `momentum_qa/*`; tests `tests/test_momentum_precheck.py`). Never write ad-hoc per-run scripts; a gap means a tested fix to the fixed script.
- **Silent when nothing changed:** no message to Ofer on SKIP, HOLD-only, or HALT-without-change days. Report only fills, QA FAILs, deviations, or errors.

## FULL AUTO (Ofer)

**Buy and sell without waiting for the user in chat.** After [Momentum screener run QA](sand-workflow:momentum-screener-run-qa) PASS and [Momentum real-money QA gate](sand-workflow:momentum-real-money-qa-gate) PASS **from QA Bot**, **prepare then place immediately**. No confirm widget. No waiting for CoS/Ofer “go.” Report fills after the fact.

Same auto rule for position_manager **CLOSE**, **MOVE_SL_BREAKEVEN**, and **TRAIL_SL** when QA PASS. HOLD needs no place. Platform Auto-review cards are the host gate, not chat confirmation. `WaitingForMarket` = leave working order; do not re-place.


### Place lock (mandatory, 2026-10-15)

Before **every** `prepare-trade` (EOD routine **and** parent chat):

1. Live `get-my-positions-and-orders` → JSON with top-level `timestamp`/`asOf` **<120s**.
2. `python -m momentum_qa.place_lock acquire --verdict <qa-verdict.json> --symbol SYM --caller <eod-routine|parent-chat> --positions-json <live.json>`
3. Exit **0** only → prepare-trade → place-trade → `place_lock mark --status PLACED|FAILED|EXPIRED`.
4. Refuse place on **LOCK_HELD** (2), **ALREADY_HELD** (3), **POSITIONS_STALE** (4; missing/stale timestamp). Same verdict sha never re-places. PM trail/close: `--allow-held`.

See `/workspace/momentum_qa/place_flow.md`.

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
- **Sleeve capacity (Ofer 2026-10-05):** **unlimited** open stocks; keep **at least 1 sector ETF** in the book (if none held in HEALTHY, prefer adding 1 sector ETF). Do **not** FAIL on stock count / `SLEEVE_CAPACITY_FULL`. Cash + ≤$1000/name still gate size. Max **1** new ETF per pack night (`etf_buys > 1` still FAIL).
- Per-night pack preference (quality, not a hard open-book cap): up to ~3 stock candidates from sleeves + 0–1 sector ETF, as cash allows
- DWM: week and month green required for buys (breakout also needs day ≥ 0)
- REAL only; never Classic; never demo
- Intraday ban 16:30–18:30 Israel; skip NYSE holidays
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either. **Code-enforced (2026-10-13/15):** read Classic via MCP `user-OfersClaw5` get-my-positions-and-orders → `python3 /workspace/classic_book.py save <result>` (snapshot `momentum_audit/classic_book/classic_holdings_latest.json`). Pack scan needs Classic ≤**900s**; stale/missing → fail closed **GATE_OK** (`STALE_CROSSBOOK_FAIL_CLOSED` / `CROSS_BOOK_READ_MISSING_OR_STALE`, no pack). `preplace` needs ≤**120s**. Overlap → `CROSS_BOOK_HELD` / hard-FAIL `CROSS_BOOK_OVERLAP`.

## Fear is the dip window (Ofer 2026-10-04)

When CNN Fear & Greed is **Fear or Extreme Fear**, that is the **best time to look for the dip** — not a reason to skip the scan or zero the pack.

- Prefer names already pulled back that still qualify (breakout retest, VCP, high RS off a dip) over chasing the few names still extended.
- A daily_brief **No Buy Today** that exists only because F&G is Fear does **not** block dip candidates. Do not re-ask Ofer for a Fear override.
- Still required: ×1, ≤$1,000, DWM, sleeve rules, cash, QA PASS, then FULL AUTO place. **EVENT_VOL_FREEZE** and **HARD_HALT** (VIX ≥ 25 or SPX < 0.98×SMA50) still mean 0 new buys — those are not the Fear index.

## Sleeves (stocks) — playbook 2026-09-16 + capacity 2026-10-05

1. **MOMENTUM_BREAKOUT** (preferred; prefer ≤**2** breakouts in a single pack night): RS ≥ 90, RVOL ≥ 2.0, new 20-day close high, close in upper third of day’s range, DWM day+week+month ≥ 0
2. **VCP_SETUP / VOLUME_BREAKOUT** (secondary): fill remaining pack stock slots; RS ≥ 80; week+month green
3. **Sector ETF:** ensure **≥1** sector ETF held; add **1** sector ETF only in **HEALTHY** if missing; commodity only if no sector ETF; never more than 1 new ETF in one pack

Near-miss high-RS names that fail both sleeves: `NO_BREAKOUT_NO_VCP`.

## Regime

- **EVENT_VOL_FREEZE**: today or next NYSE session is FOMC / CPI / NFP (`momentum_qa.event_calendar`) → **0 new buys**; still scan + near-miss
- **HARD_HALT**: VIX ≥ 25 or SPX < 0.98×SMA50 → 0 buys; scan + near-miss
- **SOFT**: SPX under SMA50 but ≥ 0.98×SMA50 → STOCK BUY only if **MOMENTUM_BREAKOUT** with RVOL ≥ 2.5; quiet VCP → `REGIME_SOFT_VCP_BLOCK`; no new ETF
- **HEALTHY**: both sleeves under pack rules
- CNN Fear / Extreme Fear is a **dip bias inside** the regime above. It does not itself set HARD_HALT or cancel a sleeve that already qualifies.

## Exits (EOD position manager)

Priority per name: **CLOSE** (last < SMA50 **or** unrealized PnL% ≤ −4 vs avg open → `LOSS_PCT_GE_4`) → **MOVE_SL_BREAKEVEN** (≥ 2R to entry) → **TRAIL_SL** (≥ 1R: trail to max(prior stop, min(entry, 10-day low)); never lower stop) → **HOLD**

## Open gap check 16:45 IL (2026-10-19)

Ofer 2026-10-19: risk-only check **weekdays 16:45 IL** (shortly after the US open). **SELL ONLY — never buy, never move SL.** Closes any position that gapped **below its SL** (`GAP_BELOW_SL`; broker SL may already have fired) or **below its 50-day SMA** (SMA from daily closes up to yesterday). **Two-read rule (Ofer 2026-10-19 13:01 IDT):** an SL breach closes **immediately**; an SMA50-only break closes only after a **second confirming read 3–30 min later** (`GAP_BELOW_SMA50_CONFIRMED`). Explicit exception to the 16:30–18:30 intraday ban, for these closes only.

1. MCP read `user-Momentum-HHHGDTJ get-my-positions-and-orders {account:"real"}` with `write_to_file=true` (on a closed day the read can be skipped; the script exits 10 with no input).
2. `./screener-venv/bin/python -m momentum_qa.open_gap_check --raw <file> --out /workspace/momentum_audit/open_gap-YYYYMMDD.json` (or `--positions-file <precheck summary>`). Confirm pass: fresh positions read → same command with a new `--out` plus `--confirm-from <first run's --out>`.
3. Exit **10** = NYSE closed/holiday, not in regular session, no positions, or all HOLD → **silent**, end the wake. Exit **3** = bad/stale (>15 min) input or missing market data → report the reason, do **not** act, do not skip silently. Exit **0** = CLOSE rows in `closes[]` (SL breaches, or confirmed SMA50 breaks; any unconfirmed ones are listed in `pending_confirm[]`). Exit **11** = only `PENDING_CONFIRM` (`GAP_BELOW_SMA50_UNCONFIRMED`): do **not** close; wait ~5 min, re-read positions, re-run with `--confirm-from`. On the confirm pass: CLOSE only if the same positionId was below SMA50 in the previous file and that run was 3–30 min earlier; back above SMA50 → HOLD `SMA50_RECOVERED` (silent); previous read too fresh/old/missing → still PENDING (exit 11, re-run again within the window). Also report anything listed in `errors[]`.
4. For **each** CLOSE: QA Bot place-QA **PASS** (cite the row's `qa` block) → fresh positions read (<120s) → `place_lock acquire ... --allow-held` exit 0 → `prepare-close` → `place-close` → `place_lock mark`. If the position is already gone (SL fired), record it and do not re-close.
5. Report only closes, QA FAILs, or errors. Audit: `/workspace/momentum_audit/YYYY-MM-DD.jsonl` (`source=open_gap_check`). Tests: `tests/test_open_gap_check.py`.

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
6. Thin cash (<~$1000): log `CASH_RECYCLE_REQUIRED`; BUY pack is advisory until cash covers; then **fresh** place-QA (existing cash-block rule). Stock-count alone is **not** a capacity block after 2026-10-05.

See `/workspace/momentum_audit/improvement-2026-10-01.md`.

## Do not

Wait for chat confirmation after QA PASS. Average down. Buy VCP into soft regime. Buy into event freeze. Treat CNN Fear as an automatic no-buy. Treat keys MCP as the $8k book. Double-buy a name filled this session. Cap open stocks at 3 (obsolete). Place after a prior place-QA FAIL without a **fresh** QA Bot place-QA PASS on the new cash/book/sleeve-rule snapshot (`PLACE_WITHOUT_QA_BOT_RECHECK`). Buy a symbol held in Classic (OfersClaw5-PRIYN) — cross-book no-overlap. Skip `place_lock acquire`/`mark`. Place on LOCK_HELD / ALREADY_HELD / POSITIONS_STALE.

**Hard FAIL deviations (HIGH):** `DUPLICATE_PLACE`, `AMOUNT_GT_1000_PER_NAME` — day_verdict FAIL; Ofer KEEP does not clear them.

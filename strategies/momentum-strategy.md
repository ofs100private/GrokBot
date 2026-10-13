# Momentum Strategy (eToro)

*Last updated: 2026-10-13*

## Account and purpose

- **Account:** **Momentum-HHHGDTJ** (real money), copied through **mirror 11630170**.
- The mirror is the reporting truth, on an $8,000 basis. The Momentum-HHHGDTJ account is the execution account, and its available cash is what must cover any order.
- **Goal:** an end-of-day breakout and volatility-contraction (VCP) strategy that buys strong, high-relative-strength US stocks plus at least one sector ETF, with tight rule-based exits.

## Universe

- A full S&P 500 scan (at least 400 symbols) plus sector and commodity ETFs, every NYSE trading day after the close. The scan runs even on freeze or halt days, so near-misses get recorded.
- Long-only, ×1, real money only, no demo.

## Entry signals

1. **Momentum breakout (preferred):** RS ≥ 90, relative volume ≥ 2.0, a new 20-day closing high, a close in the upper third of the day's range, and day, week, and month all green. At most 2 breakouts per night.
2. **VCP / volume breakout (secondary):** RS ≥ 80, with week and month green.
3. **Sector ETF:** always keep at least one sector ETF in the book. Add one only in a healthy regime and only if none is held (a commodity ETF only if no sector ETF fits). At most 1 new ETF per night.
- Week and month must be green for any buy (a breakout also needs the day ≥ 0).
- Typical nightly pack: up to ~3 stocks plus 0–1 ETF, as cash allows.
- **RSI (four-level) is a secondary filter only:** Over Buy or Resistance on a held name argues for an earlier trail or no add. A breakout candidate deep in Over Buy on the daily chart gets lower priority or is skipped. RSI mean-reversion buys never replace breakout entries.

## Sizing and caps

- **At most $1,000 per name.**
- **Unlimited number of open stocks** (the old 3-stock cap is obsolete). Cash and the per-name limit are the real constraints.
- Execution-account cash must cover each order in sequence, including a fee buffer. Mirror cash alone never authorizes a buy.
- No averaging down, and no second buy of a name already filled in the same session.

## Stops and exits

The end-of-day position manager checks each name in this priority order:

1. **Close:** last price below the 50-day moving average, **or** unrealized loss of 4% or more.
2. **Move stop to breakeven:** once the position is up 2R or more.
3. **Trail the stop:** once up 1R or more, trail to the higher of the prior stop and the lower of entry and the 10-day low. Never lower a stop.
4. **Hold.**

Once QA passes a close, breakeven, or trail action, it stays queued until the mirror confirms it.

## Rebalance and schedule

- Weekdays, Israel time: position manager at **22:40**, then the screener, then a backup run at **22:45** and a watchdog at **22:50**. Daily feedback runs around 23:05.
- A screener action logged by 22:50 counts as on time. A later catch-up run doesn't clear a miss.
- **No buys between 16:30 and 18:30 Israel time.** Skip NYSE holidays.

## Gates

- **Screener run QA:** each run must cover at least 400 S&P names (no fallback to a mega-cap stub) and have a complete audit trail, run summary, and near-miss file. A failed run gets up to 3 reruns per session; no buys come from a failed run.
- **Real-money QA:** every buy, close, breakeven move, and trail is validated before it's placed. It fails on more than 1 ETF, more than 2 breakouts, weak volume, red week or month, leverage ≠ 1, a name over $1,000, shorts, a demo route, insufficient execution cash, or cross-book overlap. If cash, the book, or a rule changes after a failure, QA has to run again; the trader can never self-pass.
- **Regime gates:**
  - **Event freeze:** FOMC, CPI, or NFP today or on the next NYSE session means 0 new buys (still scan).
  - **Hard halt:** VIX ≥ 25 or SPX below 0.98 × its 50DMA means 0 new buys (still scan).
  - **Soft:** SPX below its 50DMA but above 0.98 × the 50DMA allows only breakouts with relative volume ≥ 2.5. No VCP buys and no new ETF.
  - **Healthy:** all sleeves allowed.
- **Fear rule:** CNN Fear or Extreme Fear is a dip window inside the regime, not a no-buy. Prefer qualifying names that have pulled back. Fear never overrides an event freeze or hard halt.
- Sector concentration is advisory only.

## Automation status

- **Full auto.** After the screener run QA passes and the real-money QA passes with execution cash verified, the trader prepares and places immediately, with no chat confirmation. Fills are reported afterwards.
- After every QA PASS, the order is placed in the same session and acknowledged in the audit. A PASS with no recorded placement within ~15 minutes is flagged.

## Cross-book rules

- No symbol may be bought in both books: Momentum never buys a name held in Classic (OfersClaw5-PRIYN), and Classic never buys a name held in Momentum.
- This is enforced in code. A fresh Classic holdings snapshot (at most 120 seconds old) is required before placing. Matches are dropped from the pack, and a missing or stale snapshot blocks all buys. QA hard-fails any overlap.
- **XLE** is the one existing overlap. It stays held in both books, with **no adds** in either.

## History of rule changes

| Date | Change |
|---|---|
| 2026-09-15 | Earlier sleeve and regime notes (superseded where they conflict with the 09-16 fix). |
| 2026-09-16 | "Full fix" playbook: breakout sleeve rules, event-volatility freeze, 1R trailing stop, mandatory full scan even under halt or freeze. The old "SPX below its 50DMA, so exit without scanning" rule was retired. |
| 2026-09-22 | Rule for cash-blocked buys: once cash frees up, place only after a fresh QA pass. |
| 2026-09-23 | End-of-day miss scoring clarified: any screener action by 22:50 counts as on time. |
| 2026-10-01 | A QA pass must lead to a placement in the same session, with an audit acknowledgment, a sticky queue for exit actions, and an alert if a PASS is never acted on. Added after JNJ and CRWD actions were missed. |
| 2026-10-04 | Fear rule: Fear and Extreme Fear treated as the dip window. |
| 2026-10-05 | Unlimited open stocks plus at least 1 sector ETF, replacing the 3-stock cap. Execution-account cash (not mirror cash) must authorize placement, after mirror-only sizing caused failed orders. |
| 2026-10-13 | Cross-book no-overlap with Classic, enforced in code. XLE kept in both books, no adds. |

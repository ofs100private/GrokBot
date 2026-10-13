# Classic Strategy (eToro)

*Last updated: 2026-10-13*

## Account and purpose

- **Account:** Classic account, **OfersClaw5-PRIYN** (real money).
- The Classic account is the source of truth for execution, cash checks, and portfolio reporting. The parent copy-view mirror is optional corroboration only.
- **Goal:** beat the S&P 500 **net** of eToro spreads and fees, overnight costs, and estimated tax. Hold fewer, higher-quality, longer, trend-aligned positions at target weights, spread across sleeves so the book can earn in different market regimes.

## Universe

- Any liquid US large-cap stock or sector ETF, then commodity ETFs. Named tickers are examples only, not a fixed list.
- Typical candidates: sector ETFs (XLK, XLV, XLF, XLI, XLE, XLP, XLU, XLB, XLY, XLC), SPY, RSP, QQQ, SMH, GLD, IAU, SLV, and large caps that trade at least $100M a day.
- The hourly RSI screen starts from the S&P 500 and keeps names that trade at least ~$100M a day, cost at least $10, and show rising confirmed 1-hour volume (above 1.2× the 20-bar average). It takes the top ~50 plus whatever the book already holds.
- **Not allowed:** crypto, shorts, or leverage above ×1. Watch for eToro ticker traps: bare `CVX`, `T`, and `DIA` are crypto tokens, so use the US-stock listings instead (for example `CVX.US`).

## Entry signals

1. **Trend and relative strength (daily bars):** Score = 0.5 × 3-month RS + 0.5 × 6-month RS, where RS is the return minus SPY's return. Buy only names that are "trend OK" (close above the 50- and 200-day moving averages, and 50DMA above 200DMA) with positive 3-month RS. Prefer sleeves the book is missing.
2. **Research:** daily SPX heatmap (1-day change), performance relative to SPX and QQQ, a scan of top-tier posts on X, and the event calendar for the next ~48 hours.
3. **Timing overlay, four-level RSI on 1-hour bars:** RSI(14) levels are Over Buy 79.9, Resistance 67.9, Support 34.9, and Over Sold 19.9. Signals count only on a confirmed candle close. A strong candle has a body at least 1.2× its 20-bar average.
   - Over Sold touch = "Buy 80": the main long-timing and dip signal.
   - Support zone plus a strong bullish candle = "Buy 70": a weaker long-timing signal.
   - Over Buy or Resistance signals ("Sell 80" and "Sell 70") mean **risk-off only**: don't add to or chase that name. They never open a short and are never a sell on their own.
   - RSI buys are allowed only on names that already pass the trend/RS screen or are on the target list. The 80/70 labels are rule names, not win rates.
4. **No chasing:** if a candidate is up more than 2% on the day, stage it (half now, half on the next Support signal or red day) or wait.
5. **Sell or rotate before buying:** before every new buy, check whether selling or rotating a weak holding first is better.

## Sizing and caps

- Caps are a % of **total equity**, not of invested capital. They are checked with both cost and market value as the numerator, and breaching either counts:
  - **30% per ETF or fund**
  - **15% per single stock**
  - **45% for the growth sleeve** (and for any other sleeve)
- **Cash floor of $2,500** after any buy batch. If a pack would breach it, cut each order's size or buy fewer names. The floor is overridden only if Ofer explicitly sizes an order knowing it will go under.
- **Minimum order of $400.**
- Long-only ×1. No crypto. Never go all-in.
- If cash is above 50% of equity, deploy it toward target weights. If no candidate passes, park it in SPY (only if SPY passes the cost gate).
- Size smaller into Extreme Fear.

## Stops and exits

- **Rebalance and swing positions:** trailing stop about 8% below the high since entry for ETFs. For single stocks, about 10–12% or 2.5–3× daily ATR(14), whichever is wider. Plan to hold at least 20 trading days. No fixed take-profit on core adds, and no tight 1-hour-ATR stops on swing positions.
- **Pure hourly RSI trades:** stop = entry − 1.5 × ATR(14, 1H) and target = entry + 2.0 × ATR, re-based on the fill price. Skip the trade if the live price is more than 0.5 × ATR from the signal bar's close.
- **Hard sell rules (on a confirmed daily close):** close below the 50DMA together with negative 3-month RS; close below the 200DMA; or trailing stop hit.
- **Cap breach:** trim back to target.
- **Rotation:** replace a holding only if the candidate is trend OK, scores at least 5 points higher, fits the caps, and passes the cost gate (counting both legs and tax).
- Don't close a position just to tidy up the ledger without checking the thesis.
- **Still open:** whether the cash floor or a cap breach takes precedence when the two conflict is undecided. Any exit that depends on that choice is held until Ofer decides.

## Rebalance and schedule

- **Hourly RSI run:** weekdays during US market hours, at :35 past each hour from 9:35 to 15:35 New York time (16:35–22:35 Israel time). The script only proposes trades and never places them itself.
- **Daily rebalance check:** each US weekday after the close (Israel evening). It reviews weights, drift flags, sell rules, the RS table, and performance against SPY.
- **Monthly full rebalance:** first full US trading week. It scores the book, sets target weights, and sells first.
- **Ad hoc:** whenever a drift trigger fires: a cap breach, cash under $2,500 or over 50%, a 50DMA plus negative-RS break, a 200DMA break, or a trailing stop.
- No new positions on weekends unless Ofer overrides.

## Gates

- **QA (two stages):** every hourly run must first pass the run QA check (audit integrity, 1-hour bars, long-only, confirmed close, no crypto, no auto-place). A failed run gets up to 2 reruns an hour. Every order then has to pass the independent real-money order QA, which hard-fails on any of the following: leverage ≠ 1, shorts, crypto, cash floor breach, cap breach, a missing or non-reconciling cost gate, no recorded sell-first check, missing fee or overnight estimate, missing thesis, an order changed after prepare, a demo route, or cross-book overlap.
- **Cost/benefit gate:** place only if the expected gain is at least 2× the total round-trip cost (spread, fees, overnight, and tax on a winner) and the net gain is clearly positive. The expected gain must come from target distance or ATR math, using only out-of-sample probability estimates. Otherwise skip and log it. Hard risk exits still execute, with the numbers recorded.
- **Fear rule:** a CNN Fear & Greed reading of Fear or Extreme Fear is the **dip window**, not a reason to stop buying. A "No Buy Today" brief that exists only because of Fear doesn't block. Look for quality names that are pulling back but still trend OK, not sectors trading below their 50/200DMA.
- **Event freezes:** be cautious around CPI, FOMC, and NFP. Don't chase extended names into event volatility. An event-volatility freeze, an explicit hold from Ofer, or insufficient cash still blocks.

## Automation status

- Full auto (QA PASS plus cost gate leads to an automatic place, with no daily rebalance and no cap on trade count or new names) was **approved on 2026-10-11** and confirmed on 2026-10-12. The code gate passed QA on 2026-10-12.
- **Auto-place is currently OFF.** It stays off until Ofer explicitly accepts QA's residual risks and there's out-of-sample evidence of an edge.
- **Right now, every place needs QA PASS plus Ofer's explicit authorization.**
- Every run and every trade is documented: run audit, QA verdicts, cost-gate numbers, fill vs prepare, fees, and cash after. "No opportunity, no action" runs are logged too.

## Cross-book rules

- No symbol may be bought in both books. Classic never buys a name held in Momentum, and Momentum never buys a name held in Classic. Read the other book live before any buy. QA hard-fails any overlap.
- **XLE** is the one existing overlap. It stays held in both books, with **no adds** in either.

## History of rule changes

| Date | Change |
|---|---|
| 2026-09-02 | Real-money order QA gate activated for Classic. |
| 2026-09-19 | Four-level RSI on 1-hour bars added as a timing overlay, with ATR stops, confirmed close, and long-only remapping. Covered by order QA. |
| 2026-10-04 | Fear rule: Fear and Extreme Fear treated as the dip window instead of a no-buy. |
| 2026-10-05 | QA told not to fail Classic packs only because of Fear or a Fear-driven "No Buy". |
| 2026-10-06 | Account renamed "Classic account (OfersClaw5-PRIYN)" and made the source of truth for execution and reporting. The parent mirror became optional. |
| 2026-10-07 | $2,500 cash floor sizing (cut size or names), plus the sell/rotate-before-buy check. |
| 2026-10-08 | Rebalance playbook created after a review: the account was −26.75% vs SPY +9.6% (04-30 to 10-07), and 71% of losses came from holds under 7 days. Moved to fewer, longer, trend-aligned positions, trailing stops instead of 1-hour-ATR stops, and RSI as timing only. A stale-snapshot fail-safe was added to the hourly run. The fixed 6-name list was replaced by a dynamic S&P screen. |
| 2026-10-11 | Full auto approved. Rebalance cadence moved from weekly to daily. Trade-count limit and the "≤2 new names per month" cap removed. Mandatory cost/benefit gate (≥2× cost) added. |
| 2026-10-12 | Approval confirmed and the code gate passed QA, but auto-place kept OFF pending Ofer's acceptance of residual risks and out-of-sample evidence. Caps clarified as % of total equity (30% ETF / 15% stock / 45% sleeve). |
| 2026-10-13 | Cross-book no-overlap rule with Momentum. XLE kept in both books, no adds. |

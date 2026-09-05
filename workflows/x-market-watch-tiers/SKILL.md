---
name: X market watch tiers
description: >-
  Use this when running the user's X market-handle watches or briefs: breaking
  (tier 1), morning fear & greed (tier 2), or pre-open/pre-close (tier 3).
---
# X market watch tiers

Watchlist and recipe for X market-news handles. Read the X MCP guide before any X call. Probe the signed-in user first. Estimate cost; keep `max_results` small (10–25). Combine handles into one `from:a OR from:b` recent search per tier. Skip replies unless they are the story. Report only new posts since the last run. If nothing new, send nothing (no "no updates" filler).

Quote handle, time (user TZ Asia/Jerusalem), and a one-line take. Link each post. Do not paginate or run bulk lookups without a cost estimate and a yes.

## Tier 1 — breaking (every hour, 24/7)

Routine: `x-watch-tier1-hourly`

- @DeItaone
- @FirstSquawk
- @LiveSquawk
- @unusual_whales
- @CheddarFlow

Query: `from:DeItaone OR from:FirstSquawk OR from:LiveSquawk OR from:unusual_whales OR from:CheddarFlow -is:reply`

Surface only market-moving headlines (tape, levels, unexpected prints). Quiet otherwise.

## Tier 2 — morning F&G brief (05:30 Israel, weekdays)

Routine: `daily_fear_greed_brief`

- @CNBCOvertime
- @jimcramer
- @StockCharts
- @alphatrends
- @StockMKTNewz

Query: `from:CNBCOvertime OR from:jimcramer OR from:StockCharts OR from:alphatrends OR from:StockMKTNewz -is:reply`

Write a short fear-and-greed morning brief from overnight/early posts: tone of the tape, notable calls, what to watch into the US open. Skip it if the accounts were quiet.

## Tier 3 — pre-open 09:00 ET + pre-close 15:30 ET (weekdays)

Routines: `x-watch-tier3-preopen`, `x-watch-tier3-preclose`

- @RyanDetrick
- @markminervini
- @thechartdr
- @TrendSpider
- @OptionsPlay
- @Stocktwits
- @MarketRebels
- @BespokeInvest
- @IncredibleTrade
- @SpotGamma

Query: `from:RyanDetrick OR from:markminervini OR from:thechartdr OR from:TrendSpider OR from:OptionsPlay OR from:Stocktwits OR from:MarketRebels OR from:BespokeInvest OR from:IncredibleTrade OR from:SpotGamma -is:reply`

Pre-open: levels, setups, and what they're watching into the bell. Pre-close: positioning, late tape, into-the-close tells. Quiet if nothing useful landed in the last window.

---
name: daily-trading-momentum-brief
description: >-
  use this when running Ofer's daily_brief Fear & Greed / trading momentum brief
  for one or more parameterized agent portfolios
---
# Daily trading momentum brief

## Portfolio parameter (required)
- Input: `portfolios` — list of agent-portfolio keys the user wants (examples: `Classic` / `OfersClaw5-PRIYN`, `Momentum` / `Momentum-HHHGDTJ`).
- Support any subset: one, several, or all of the user's agent portfolios. Never hardcode which book.
- For each selected book, pull LIVE ledger fields via eToro Account / the matching trader agent (invested, equity, cash, open/closed PnL, positions). Do not invent dollar amounts.
- **Standing default (Ofer):** `portfolios=[Classic, Momentum]` — always produce a separate Portfolio Recommendation card for **Classic** (OfersClaw5-PRIYN / mirror 11368142) **and** **Momentum** (Momentum-HHHGDTJ). Override only if Ofer narrows the list for a run.
- Classic truth = parent mirror ledger A (not keys-B totals). Momentum truth = Momentum agent book / its live MCP — never mix Classic dollars into Momentum or vice versa.

## Live data rules
1. Fetch LIVE only via tools. Preferred F&G: `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`. Fallback: web search / CNN Fear & Greed page.
2. CNN 7 COMPONENTS ARE MANDATORY from graphdata: `market_momentum_sp500`, `stock_price_strength`, `stock_price_breadth`, `put_call_options`, `market_volatility_vix`, `junk_bond_demand`, and the remaining component in that payload (include all seven with score + English rating). Never omit the tail of the brief.
3. Commodities: WTI oil, gold, silver — live price + day % change.
4. Trump section: last Trump post with timestamp, short quote, link; 1 line market relevance; enforce freshness.
5. Analyst score (X Tier 2): 3–6 theme bullets from last 24h, or `Nothing Special from the last 24h`.
6. Weekend = recommendations for next US session; no new opens.

## Required brief structure (stop only after Source)
1. Header: `Good Morning | (CNN Fear & Greed)` + today's date (user TZ Asia/Jerusalem)
2. Current score (int) + English rating
3. Compare: previous close, week, month, year
4. All 7 components with score + English rating
5. Section: last trump twit
6. Section: סחורות — Oil / Gold / Silver
7. Section: Analyst score (X Tier 2)
8. Short market read + trading takeaway
9. Section: Daily Signals — What I Would Buy / Sell — 2–4 buys and 2–4 sells/avoids; each ticker: Opening Price / Previous Close / Current Price (% Change), rationale, analyst views
10. Section: Oil / Gold / Silver — explicit yes/no/wait for related asset
11. Section: Impact on Crypto — BTC + daily move; BTC/ETH and crypto-beta (COIN/HOOD); buy vs don’t chase
12. Section: Expected Daily Impact — 3–6 bullets
13. Section: `{PORTFOLIO_NAME} Portfolio Recommendation` for **EACH** selected portfolio — Portfolio card (N names / cash / deployment % — no invented dollars); Buy 0–2 or No Buy Today; Sell/Rotation 1–2 or No Sale; Hold; Diversification note. With the standing default, that means **two** cards: Classic then Momentum.
14. Source line with update timestamp

If length pressure: shorten section-9 reasons; keep sections 10–14. A brief that stops early is FAILED — complete through Source.

## Coordination
- Use X agent / X tools for Tier-2 analyst tape (estimate cost; keep cheap).
- Use trader agents + eToro Account for portfolio cards (Classic via Trader_Classic / mirror A; Momentum via Trader_momentum / Momentum MCP).
- After delivery, refresh App JSON dual-write with **both** portfolio cards when both are selected; never write keys-B Classic totals as Classic A.
- Deliver the full brief to the user (or hand off to Chief of Staff for user delivery when running in an isolated routine).

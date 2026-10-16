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
- **Standing default (Ofer):** `portfolios=[Classic, Momentum]` — always produce a separate Portfolio Recommendation card for **Classic** (Classic account (OfersClaw5-PRIYN)) **and** **Momentum** (Momentum-HHHGDTJ). Override only if Ofer narrows the list for a run.
- **Classic truth** = Classic account (OfersClaw5-PRIYN) live via MCP `user-OfersClaw5` (equity/cash/positions). Parent SSO mirror `11368142` is optional copy/UI corroboration only — never required, never the rejection reason. Do **not** reject OfersClaw5 figures as Classic.
- **Momentum truth** (UNCHANGED): Momentum agent book / mirror `11630170` as $8k reporting truth; keys Momentum-HHHGDTJ for execution only — never mix Classic dollars into Momentum or vice versa.
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal on a recommendation card, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either. **Recommendation cards (section 13):** any buy/add idea that overlaps the other book must appear under **Blocked** (not Buy / Would Buy).

## Live data rules
1. Fetch LIVE only via tools. Preferred F&G: `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`. Fallback: web search / CNN Fear & Greed page.
2. CNN 7 COMPONENTS ARE MANDATORY from graphdata: `market_momentum_sp500`, `stock_price_strength`, `stock_price_breadth`, `put_call_options`, `market_volatility_vix`, `junk_bond_demand`, and the remaining component in that payload (include all seven with score + English rating). Never omit the tail of the brief.
3. Commodities: WTI oil, gold, silver — live price + day % change.
4. Trump section: last Trump post with timestamp, short quote, link; 1 line market relevance; enforce freshness.
5. Analyst score (X Tier 2): 3–6 theme bullets from last 24h, or `Nothing Special from the last 24h`.
6. Weekend: Classic equities are outside the 24x5 window (no new equity size; BTC/ETH/SOL still 24/7). Momentum / RTH-only books → recommendations for next US session; no new equity opens.

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

**Activation status (Ofer 2026-10-16 01:27 IDT):** Classic FULL AUTO is ON. Code gate PASSED QA (fix3, 2026-10-12); Ofer accepted QA's residual risks. After run-QA + order-QA + cost-gate PASS, Trader_Classic auto-places via `user-OfersClaw5` with **no chat authorization**. Caps of **total equity**: stock ≤20%, ETF ≤35%, sleeve ≤45%, crypto (BTC/ETH/SOL) ≤15%. Cash floor ~$1,500. Max **4 new trades per IDT day**. Equities 24x5 (extended hours); BTC/ETH/SOL 24/7. Long ×1; SL+TP mandatory. Unchanged: cross-book no-overlap; no XLE adds.

## Classic recommendation cap filter (mandatory — applies to sections 9 and 13)
Source of truth for caps: `/home/box/agent-data/workflows/classic-rebalance/SKILL.md` — read it each run and cite its caps; if they differ from the values below, its values win.
1. Before listing ANY Classic buy/add idea, compute from the live `user-OfersClaw5` book:
   - Each name's % of **total equity** vs the name cap (currently **≤35% ETF / ≤20% single stock**).
   - Growth sleeve (QQQ+SMH+other growth/tech) and any sleeve % of **total equity** vs the sleeve cap (currently **≤45%**); crypto sleeve (BTC+ETH+SOL) ≤ **15%** of total equity.
   - Cash vs equity: if cash >50% of equity, note the cash drift trigger.
2. Drop any idea that breaches a cap or leaves less than the minimum trade size of headroom (currently **$400** minimum position). A blocked idea may appear only under **Blocked / needs Ofer exception** — never under Would Buy. Market-watch names Classic can't buy must be labeled **market watch only**.
2a. **Cross-book overlap:** before listing any Buy on either portfolio card, live-read the other book. If the symbol is held there, move that buy idea to **Blocked** (`CROSS_BOOK_OVERLAP`); never list it under Buy / Would Buy. Existing overlap XLE stays held in both books per Ofer 2026-10-13; any XLE add is Blocked.
3. Names already held go under **Hold/Watch**, not Would Buy.
4. Authorization wording: briefs must say **Classic FULL AUTO ON (Ofer 2026-10-16 01:27 IDT) — residual risks accepted; auto-place after run-QA + order-QA + cost-gate PASS, no chat auth**. Max **4 new trades per IDT day**; no monthly new-name cap. Cash floor ~$1,500; caps of total equity 20%/35%/45%/15% crypto.
5. Last trump twit: check Truth Social (e.g. trumpstruth.org) as well as X; quote the freshest post.
6. Weekends: if nothing material changed vs the last delivered brief, say so in the META line so the Chief of Staff can skip delivery.

## Dual-write target list
- The canonical App JSON dual-write targets are **only** the live/latest ones:
  - `etoroview` and `GrokBot/app/etoroview`: `public`, `public/latest`, `latest`, `dist`, `dist/latest` (each of `daily-brief.json`, `classic-portfolio.json`, `momentum-portfolio.json`)
  - `daily-brief.json` and `latest.json` in `/workspace/daily-brief` and `/workspace/GrokBot/daily-brief` (plus the portfolio JSON siblings written alongside them)
  - `/workspace/classic-portfolio.json`, `/workspace/classic-portfolio-for-app.json`, `/workspace/momentum-portfolio.json`
  - **plus the CURRENT run's own dated folder and file only** (e.g. `/workspace/daily-brief/morning-0530-YYYY-MM-DD.json` or afternoon equivalent, `/workspace/daily-brief-SLOT-YYYY-MM-DD/*.json`, `/workspace/app-refresh-YYYY-MM-DD-am|pm/*.json`)
- **Never** copy a target list from a previous `written-manifest.json`. Build the list fresh each run from the canonical set above.
- **Never** write to a path whose name carries a **different date** than the current run (no overwriting past-dated archive copies).
- Manifest `targetCount` / summary counts must state the **per-type breakdown**, for example `48 targets (17 daily-brief.json)` (include classic/momentum counts the same way when reporting).

## Coordination
- Use X agent / X tools for Tier-2 analyst tape (estimate cost; keep cheap).
- Use trader agents + MCP for portfolio cards (Classic via Trader_Classic / Classic account `user-OfersClaw5`; Momentum via Trader_momentum / Momentum MCP — Momentum reporting still mirror `11630170`).
- After delivery, refresh App JSON dual-write with **both** portfolio cards when both are selected (see **Dual-write target list**); Classic card numbers must come from live Classic account (`user-OfersClaw5`), not from inventing or requiring mirror `11368142`.
- Deliver the full brief to the user (or hand off to Chief of Staff for user delivery when running in an isolated routine).

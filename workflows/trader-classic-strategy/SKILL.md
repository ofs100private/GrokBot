---
name: Trader Classic strategy
description: >-
  Use this when planning, reviewing, or executing Trader_Classic trades on
  OfersClaw5-PRIYN (ledger A) — any fitting liquid large-cap/ETF, SPX heatmap
  Change 1D URL, cross-regime diversification, beat-SPX after fees/tax, and hard
  mandate rules.
---
# Trader Classic strategy

Standing playbook for **Trader_Classic** on portfolio **OfersClaw5-PRIYN** (REAL MONEY).

**Objective:** beat **S&P 500** on a **net** basis (after eToro fees/spreads/overnight, realized P&L, and estimated tax drag). Prefer fewer high-quality longs over churn — keep the book **diversified enough to earn across regimes**.

**Source of truth = ledger A only:** parent SSO mirror `11368142` (UI/copy). Never treat keys MCP agent-book (ledger B) as Classic for analysis/reporting. Keys MCP only for authorized place/SL that reflects on A.

## Mandate

- Long-only, leverage **×1**; **no crypto** opens
- Prefer large liquid US companies / sector ETFs, then commodities
- Cash floor ≥ **~$2.5k** after adds; never all-in
- REAL only; QA PASS → place → fill audit → CoS
- No place under buy HOLD or without auth after PASS
- Weekend: no new size unless Ofer overrides

## Universe

Named tickers are **examples only** — trade **any** fitting liquid large-cap/ETF after research.

## Diversification

Sleeves: growth/tech · industrial · healthcare/pharma · hard assets · cash. Caps: name ≤~25–30% open invested; sleeve ≤~40–45%; cash ≥~$2.5k. Prefer gap sleeves.

## Research loop

1. Ledger A snapshot + sleeve weights
2. **SPX heatmap (1D):** open  
   `https://www.tradingview.com/heatmap/stock/#%7B%22dataSource%22%3A%22SPX500%22%2C%22blockColor%22%3A%22change%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22grouping%22%3A%22sector%22%7D`  
   Confirm UI label **Change 1D, %** (blockColor `change`). Not 1h (`change|60`). If tiles blank/rate-limited → eToro batch quotes + sector ETFs
3. Rel performance vs SPX/QQQ; beat SPX after costs
4. X Tier-1 (small cost; X MCP guide first)
5. Event calendar (~48h CPI/FOMC/NFP)
6. getCost / prepare — fees + tax haircut

## Beat-SPX filter / regimes / daily checklist / pre-trade / events

Unchanged intent: hold cash if unsure; event-vol freeze; risk-off lean healthcare+hard assets; risk-on small liquid adds after QA; NVDA no-add default; any fit symbol when buys reopen.

## Do not

Report B as Classic; crypto/shorts/lev>1; exclusive ticker lists; break caps; chase parabolic into event-vol; ignore fees/tax; duplicate pending closes; place without QA+auth; use 1h heatmap when 1D was set.

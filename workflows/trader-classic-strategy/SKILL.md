---
name: Trader Classic strategy
description: >-
  Use this when planning, reviewing, or executing Trader_Classic trades on
  OfersClaw5-PRIYN (keys execution) — any fitting liquid large-cap/ETF, SPX
  heatmap Change 1D URL, cross-regime diversification, beat-SPX after fees/tax,
  hard mandate rules, Fear-as-dip window, cash-floor sizing, sell-before-buy
  check, and post-trade self-improvement.
---
# Trader Classic strategy

Standing playbook for **Trader_Classic** on the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY).

**Objective:** beat **S&P 500** on a **net** basis (after eToro fees/spreads/overnight, realized P&L, and estimated tax drag). Prefer fewer high-quality longs over churn — keep the book **diversified enough to earn across regimes**.

**Naming (Ofer 2026-10-06):** **Classic account** = OfersClaw5-PRIYN agent account (keys MCP `user-OfersClaw5`). Use the phrase **Classic account (OfersClaw5-PRIYN)** going forward. Stop calling it keys-B or ledger B for Classic.

**Source of truth (Ofer 2026-10-06):** Classic **execution, cash gating, prepare/place, order-QA, AND portfolio reporting** (equity/cash/positions on cards, App, briefs, QA data gates) come from the **Classic account (OfersClaw5-PRIYN)** via MCP `user-OfersClaw5`. Do **not** reject OfersClaw5 keys figures as Classic. Parent SSO mirror `11368142` is only the copy/UI view — optional corroboration, never required, never the rejection reason. `prepare-trade` / `place-trade` run on the Classic account.

## Mandate

- Long-only, leverage **×1**; **no crypto** opens
- Prefer large liquid US companies / sector ETFs, then commodities
- Prefer leaving cash uninvested; never all-in
- REAL only; QA PASS → place → fill audit → CoS
- No place under an explicit Ofer/CoS buy HOLD or without auth after PASS
- Weekend: no new size unless Ofer overrides

## Cash floor sizing (Ofer 2026-10-07)

**Hard preference:** leave **~$2,500+** residual cash on the Classic account after any buy batch.

If a proposed pack would leave cash **below ~$2,500**:
1. **Lower** each trade’s notional, and/or
2. **Buy fewer symbols** (keep the best sleeve-fit / highest-conviction names),
3. Re-check cash-after ≥ floor, then prepare / order-QA.

Do **not** propose a floor override unless Ofer **explicitly** sizes knowing cash will go under ~$2.5k. Never auto-place a pack that breaches the floor without that explicit override.

## Sell / rotate before buy (Ofer 2026-10-07)

**Before every new buy pack**, check whether it is better to **sell or rotate** a weak holding first:
- Names near stop, thesis broken, sleeve overcrowded, or clearly weaker than the candidate
- Freeing cash by closing first can fund the buy without breaching the floor
- Report the sell-first vs buy-only choice in the prepare/handoff notes to CoS

If a clean sell/rotation is better, prepare the close (and order-QA) **before** or sequenced ahead of the new buys.

## Fear is the dip window (Ofer 2026-10-04)

When CNN Fear & Greed is **Fear or Extreme Fear**, that is the **best time to look for the dip** — not a reason to sit out.

- Hunt quality liquid longs on **confirmed weakness** (RSI Support / Over Sold, beaten large-caps and gap sleeves). Do not chase names already extended (RSI Over Buy / risk-off on that name).
- A daily_brief **No Buy Today** that exists only because F&G is Fear does **not** block this search. Do not re-ask Ofer for a Fear override.
- Still required: ×1 long-only, no crypto, weekend freeze, sleeve caps, QA PASS before place. Size smaller into Extreme Fear; leave a cash buffer when possible.
- Explicit Ofer hold, event-vol freeze, and cash-insufficient fails still block. Fear alone does not.

## Universe

Named tickers are **examples only** — trade **any** fitting liquid large-cap/ETF after research.

## Diversification

Sleeves: growth/tech · industrial · healthcare/pharma · hard assets · cash. Caps: name ≤~25–30% open invested; sleeve ≤~40–45%. Prefer gap sleeves. In Fear, prefer the sleeve that is actually on sale, not another add to an extended winner.

## Research loop

1. Classic account (OfersClaw5-PRIYN / `user-OfersClaw5`) snapshot (+ optional mirror `11368142` copy view) + sleeve weights
2. **Sell/rotate check** (see above) before proposing new buys
3. **SPX heatmap (1D):** open  
   `https://www.tradingview.com/heatmap/stock/#%7B%22dataSource%22%3A%22SPX500%22%2C%22blockColor%22%3A%22change%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22grouping%22%3A%22sector%22%7D`  
   Confirm UI label **Change 1D, %** (blockColor `change`). Not 1h (`change|60`). If tiles blank/rate-limited → eToro batch quotes + sector ETFs
4. Rel performance vs SPX/QQQ; beat SPX after costs
5. X Tier-1 (small cost; X MCP guide first)
6. Event calendar (~48h CPI/FOMC/NFP)
7. Timing overlay: [Classic RSI four-level 1H](sand-workflow:classic-rsi-four-level-1h) (`/workspace/classic_rsi/`) — Buy = long timing, Sell = risk-off only; ATR SL/TP; confirmed 1H close. **In Fear, Support/Over Sold buys are the dip.** RSI still does not bypass weekend or an explicit hold.
8. Size so cash-after ≥ ~$2.5k (cut notional or drop symbols first)
9. prepare on **Classic account** (`user-OfersClaw5`) — fees + tax haircut
10. Read latest **KEEP / AVOID** from [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop) before proposing size

## After every fill / skip / QA FAIL

Run [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop): score Q/A/order/market/X/brief/graph/outcome; write KEEP/AVOID; patch this playbook only when a hard avoid repeats.

## Beat-SPX filter / regimes / daily checklist / pre-trade / events

Hold cash if the dip is not clean; event-vol freeze; in Fear lean into quality dips (healthcare, hard assets, and beaten large-caps) rather than a blanket no-buy; risk-on small liquid adds after QA; NVDA no-add default; any fit symbol when the dip is real.

## Do not

Crypto/shorts/lev>1; exclusive ticker lists; break caps; chase parabolic into event-vol; treat high Fear as an automatic no-buy; ignore fees/tax; duplicate pending closes; place without QA+auth; use 1h heatmap when 1D was set; treat RSI Sell tags as shorts; prepare on parent SSO expecting a `mirrorId` (parent cannot target the copy); auto-place packs that leave cash under ~$2.5k without Ofer’s explicit override; skip the sell/rotate check before new buys.

---
name: Classic rebalance
description: >-
  use this when running the weekly check or monthly rebalance of the Classic
  account (OfersClaw5-PRIYN via user-OfersClaw5), or when a drift trigger fires
  (name >30% of invested, sleeve >45%, cash <$2.5k or >50% of equity, holding
  below 50DMA with negative 3M RS, or a trailing stop) — sell/rotate before buy,
  size to target weights, RSI 1H only as entry timing, QA + Ofer/CoS authorize
  before every place
---
# Classic rebalance

Applies only to the **Classic account (OfersClaw5-PRIYN)** (REAL MONEY). It composes with [Trader Classic strategy](sand-workflow:trader-classic-strategy) (mandate), [Classic RSI four-level 1H](sand-workflow:classic-rsi-four-level-1h) (timing only), and [Trading self-improvement loop](sand-workflow:trading-self-improvement-loop).

**Why this exists (review 2026-10-08):** the account was −26.75% vs SPY +9.6% from 04-30 to 10-07. 121 closes lost −$2,765 fully loaded. Holds under 7 days caused −$1,951 of that (71%); holds of 30 days or more were about flat; the long-held core (SMH, QQQ, XLV) is all positive. Lesson: **fewer, longer, trend-aligned positions at target weights.**

## Mandate locks (unchanged)
Long ×1 only. No crypto (watch for eToro traps: `CVX` = Convex, use `CVX.US` id 1014; `T` and `DIA` are crypto tokens). Liquid large caps and sector ETFs, then commodity ETFs. Cash ≥ ~$2,500 after any batch. No weekend opens. QA PASS and explicit Ofer/CoS authorization before every place.

## Cadence
| When | What | Output |
|---|---|---|
| **Weekly**, Fri after the US close (IDT evening) | Read-only check: weights, drift flags, sell-rule flags, RS table, account vs SPY (1W/1M/since 04-30) | Short report. No orders unless a trigger fires. |
| **Monthly**, first full US trading week | Full rebalance: score, set target weights, propose trades | Rebalance memo plus packs (sells first) |
| **Ad hoc** | Any drift trigger, or a hard sell rule on a confirmed daily close | Pack for the affected name only |

## Targets and caps
- Invested sleeves: growth/tech · healthcare · industrials/financials · energy/hard assets · broad core (SPY/RSP). Cash is its own sleeve.
- Name ≤ 30% of invested (core ETF) or ≤ 15% (single stock). Sleeve ≤ 45% of invested.
- Cash: floor $2,500. If cash is above 50% of equity and passing candidates exist, deploy toward target. If nothing passes, park it in SPY rather than sit idle.
- At most **2 new names per month**. Minimum position $400 (smaller positions are not worth the fees).

## Drift triggers (any one starts an ad-hoc rebalance)
1. A name above 30% of invested, or a sleeve above 45%.
2. Cash below $2,500, or above 50% of equity.
3. A holding has a **confirmed daily close below its 50DMA AND negative 3M RS** vs SPY.
4. A holding has a confirmed daily close below its 200DMA.
5. A trailing stop is hit: ETFs ~8% below the high since entry; single stocks ~10–12%, or 2.5–3× daily ATR(14), whichever is wider.

## Step 1: Snapshot (live)
Portfolio summary on the Classic keys connector gives equity, cash, and positions. Compute % of invested, sleeve %, and cash % of equity. Trading history gives closes since the last run (for the report).

## Step 2: Score (daily bars, last confirmed close)
For each holding and each candidate (sector ETFs XLK/XLV/XLF/XLI/XLE/XLP/XLU/XLB/XLY/XLC, SPY/RSP/QQQ/SMH, GLD/IAU/SLV, plus liquid large caps with ADV ≥ $100M):
- Returns over 1M (21d), 3M (63d), 6M (126d). **RS = return minus SPY return** over the same window.
- **Trend OK:** close above the 50DMA, close above the 200DMA, and 50DMA above 200DMA.
- **Score = 0.5×RS3M + 0.5×RS6M.** Also record drawdown from the 52-week high and 63-day vol.
- Data: eToro daily candles via the read route, or Yahoo (yfinance); label the source. Cross-check SPY's last close against eToro.

## Step 3: Sell / rotate first (always before any buy)
- A hard sell rule (trigger 3, 4, or 5) means a close or trim.
- Cap breach: trim back to target.
- **Rotation:** replace a holding only if the candidate passes the trend filter, scores at least **5 pp** higher, and fits the caps.
- Do **not** close a position only to reconcile a ledger without a thesis check (example: CVX.US −$78.67 on 10-06).
- Include the realized gain or loss and the tax estimate in the memo.

## Step 4: Buy list and sizing
- Only trend-OK names with positive 3M RS, preferring gap sleeves. **Fear = dip window** means a pullback in a trend-OK name (above its 200DMA). It does **not** mean buying a sector below its 50/200DMA (the September rotations into CAT/XLI/CVX/XOM/NEM/GE lost −$304 with 0 wins).
- Size to target weights. Re-check cash after the batch is ≥ $2.5k; if not, cut notional or drop the weakest name.
- Do not chase: if a candidate is up more than 2% on the day, stage it (half now, half on the next RSI Support or a red day) or wait.

## Step 5: RSI 1H as timing only
- RSI Buy packs are allowed **only** for names on the current target/add list or that pass Step 2.
- **Re-base SL/TP on the fill price.** Skip the pack if live price is more than 0.5×ATR(1H) away from the signal bar close. (On 10-07, ADBE reward:risk fell to 0.31 and GS to 0.17 because of stale levels.)
- No fixed 2.0×ATR(1H) TP on core adds. Use the trailing stop from drift trigger 5 and a planned hold of at least 20 trading days.
- No 1H-ATR initial stops on swing positions (SPCX −1.9%, RBRK −2.3%, CAT −1.56% were all hit within about 1 day).
- RSI Sell tags mean no add on that name. They never trigger a short, and they are never a standalone sell.

## Step 6: Approval flow (no shortcuts)
1. Analyst memo (scores, proposed trades, cash after, sleeves after, fees and tax estimate).
2. Trader_Classic prepares closes and trades (sells sequenced first).
3. QA Bot runs [Classic real-money order QA gate](sand-workflow:classic-real-money-order-qa-gate) and must PASS each pack.
4. Ofer or CoS gives explicit authorization (the size and symbol named).
5. Place, one call per approval. Then fill audit to QA, then report.
6. Run the self-improvement loop (KEEP/AVOID).

## Step 7: Reporting templates
**Weekly:**
```
Classic weekly | <date IDT> | equity $ | cash $ (x% eq) | vs SPY 1W/1M/since 04-30
Weights: SYM x% (sleeve) … | Growth x% | flags: <none | trigger #>
RS top/bottom: … | Action: none | ad-hoc pack <sym>
```
**Monthly memo:** before/after weight table, trades ($, realized P&L, fees, tax est.), scores, rejected candidates with the reason, and data sources.

## Do not
- Trade outside the cadence except on a trigger.
- Add a new name without the sell/rotate check first.
- Buy trend-failing sectors because they are "cheap".
- Use leverage above ×1, crypto, or bare `CVX`/`T`/`DIA`.
- Place without QA PASS and explicit authorization.
- Invent expected returns. Report realized vs SPY only.

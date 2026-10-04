---
tags: [plan, 70k]
ledger: mirror-A
starting_capital: 20649.39
classic_equity_start: 12841.61
momentum_equity_start: 7807.78
live_classic: 12930.08
live_momentum: 7847.5
live_combined: 20777.58
target: 70000
gap_live: 49222.42
delta_vs_start: 128.19
asOf: "2026-10-04T15:51:00+03:00"
---
# Plan · $70k from Mirror A capital

## Starting capital (FROZEN — do not overwrite)

| Component | Equity | Source | Ledger |
|-----------|--------|--------|--------|
| Classic Mirror A `11368142` | **$12,841.61** | 2026-09-30 afternoon Mirror A | mirror-A |
| Momentum Mirror A `11630170` | **$7,807.78** | 2026-09-30 afternoon Mirror A | mirror-A |
| **Sum (start)** | **$20,649.39** | 12841.61 + 7807.78 | mirror-A |

```
starting_capital = 12841.61 + 7807.78 = 20649.39
```

**REJECT** keys-B equities (OfersClaw5 / Momentum keys MCP) in this plan.

## Live Mirror A snapshot

| Component | Equity | Cash | Names | Source |
|-----------|--------|------|-------|--------|
| Classic `11368142` | **$12,930.08** | $7,285.54 | SMH, QQQ, XLV | `_raw/classic-portfolio.json` |
| Momentum `11630170` | **$7,847.50** | $4,361.46 | CRWD, VTRS, P, XLK | `_raw/momentum-portfolio.json` |
| **Live combined** | **$20,777.58** | — | — | live classic + momentum |
| Δ vs frozen start | $128.19 | — | — | live_combined − 20649.39 |

## Target

| Item | Value |
|------|-------|
| Target | **$70,000** |
| Gap from **live** | **$49,222.42** (`70000 − 20777.58`) |
| Multiple vs frozen start | 3.39× |

## Path (no invented PnL)

1. Keep Classic cash buffer discipline (mandate cash floor); grow via quality longs after QA PASS.
2. Momentum: breakout/VCP FULL AUTO after QA; cash now ~55.6%.
3. Compound **only** Mirror A marked equity; never count keys-B as progress toward $70k.
4. Review weekly in [[Journals/2026-10-04-weekly-rollup]] + [[Feedback/Feedback-Loop]].

## As-of

Sidecar slot `afternoon_1530` · `2026-10-04T15:51:00+03:00`. Frozen start stays 2026-09-30; live marks refresh from sidecars.

## Reality check (to 2026-12-31)

| Math | Value |
|------|-------|
| Frozen start | $20,649.39 |
| Live combined (asOf sidecar) | see Live Mirror A snapshot above |
| Target | $70,000 |
| Gap from live | see Target table above |
| Multiple vs frozen start | 3.39× |

Under Classic ×1 long-only + Fear/No Buy gates, **Path A alone is not realistic**. Do not force size into Fear to "catch up."

## Three paths

### Path A · Trading-only stretch (low probability)
- Need sustained high-WR breakouts on Momentum + Classic RSI fills when Fear clears.
- Kill-switch: max book DD 15% from peak Mirror A combined; stop increasing risk.

### Path B · Hybrid deposits + bot alpha (**recommended**)
- Treat Mirror A bots as **alpha engines**, not magic 3× machines.
- Example split of the live gap (illustrative schedule — adjust deposits to cash you actually add):
  - Oct: +$10k deposit · bots target +3–6% on deployed risk
  - Nov: +$10k deposit · bots target +3–6%
  - Dec: +$8–15k deposit · bots protect capital into year-end
- Remaining gap covered by realized + unrealized Mirror A P&L only after QA PASS fills.
- Wire **Daily Trader** (~$2k, lev ×2–×10, flat stocks/commodities by US close) only after funding + order-QA — incremental alpha sleeve, not the whole plan.

### Path C · Risk-off honest
- Stay No Buy in Extreme Fear / Fear until F&G recovers; cash is a position.
- Deploy Classic cash only on QA PASS + cleared gates.
- Momentum: trail winners (CRWD/VTRS/P/XLK); free cash before new ~$800–$1k sleeves.

## Monthly milestones (Mirror A combined equity)

| Date | Floor (survive) | Target (on track) |
|------|-----------------|-------------------|
| 2026-10-31 | ≥ $22k (incl. any deposits) | ≥ $30k |
| 2026-11-30 | ≥ $35k | ≥ $50k |
| 2026-12-31 | ≥ $55k | **$70k** |

Milestones count **deposits + Mirror A equity**. Never count keys-B.

## Kill-switches
1. Fear / No Buy → no Classic places (override only by you in chat).
2. QA FAIL → no place / no vault accept.
3. Momentum cash &lt; ~$400 → no new sleeve until free cash + fresh place-QA.
4. Combined Mirror A DD &gt; 15% from post-deposit peak → pause new risk, review lessons.

## What was missing (now fixed)
- No per-move MD store → notes with `ledger:` tags
- keys-B CSV mislabeled as Mirror A → retagged `classic-keys-B-closed-trades.csv`
- Lessons skill unused systematically → weekly Feedback loop
- Dual-write / number drift → QA number gate before accept
- Daily Trader unfunded → still pending live wire

## Token-lean rules
- Deterministic Python rebuild for move MDs (no LLM per fill)
- Weekly rollup only (not hourly self-improve)
- Skip paid X when credits near zero
- One QA gate per vault refresh, not chatter loops

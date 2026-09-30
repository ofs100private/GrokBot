---
tags: [plan, 70k]
ledger: mirror-A
starting_capital: 20649.39
classic_equity: 12841.61
momentum_equity: 7807.78
target: 70000
gap: 49350.61
asOf: "2026-09-30T15:53:30+03:00"
---
# Plan · $70k from Mirror A capital

## Starting capital (reporting truth)

| Component | Equity | Source | Ledger |
|-----------|--------|--------|--------|
| Classic Mirror A `11368142` | **$12,841.61** | `_raw/classic-portfolio.json` | mirror-A |
| Momentum Mirror A `11630170` | **$7,807.78** | `_raw/momentum-portfolio.json` | mirror-A |
| **Sum (start)** | **$20,649.39** | classic.equity + momentum.equity | mirror-A |

```
starting_capital = 12841.61 + 7807.78 = 20649.39
```

**REJECT** keys-B equities (OfersClaw5 ~7246 / Momentum keys ~9843) in this plan.

## Target

| Item | Value |
|------|-------|
| Target | **$70,000** |
| Gap | **$49,350.61** |
| Multiple vs start | 3.39× |

## Path (no invented PnL)

1. Keep Classic cash buffer discipline (mandate cash floor); grow via quality longs after QA PASS.
2. Momentum: breakout/VCP FULL AUTO after QA; protect thin cash (~7.0% now).
3. Compound **only** Mirror A marked equity; never count keys-B as progress toward $70k.
4. Review weekly in [[Journals/2026-09]] + [[Feedback/Feedback-Loop]].

## As-of

Sidecar slot `afternoon_1530` · `2026-09-30T15:53:30+03:00`. Live marks may drift; plan baseline stays afternoon Mirror A sidecars until next vault refresh.

## Reality check (92 days to 2026-12-31)

| Math | Value |
|------|-------|
| Days left | 92 |
| Required multiple | 3.39× |
| Pure trading CAGR to hit $70k | ~+239% in ~3 months |
| Implied ~daily compound | ~1.4%/day |

Under Classic ×1 long-only + Fear/No Buy gates, **Path A alone is not realistic**. Do not force size into Fear to "catch up."

## Three paths

### Path A · Trading-only stretch (low probability)
- Need sustained high-WR breakouts on Momentum + Classic RSI fills when Fear clears.
- Kill-switch: max book DD 15% from peak Mirror A combined; stop increasing risk.

### Path B · Hybrid deposits + bot alpha (**recommended**)
- Treat Mirror A bots as **alpha engines**, not magic 3× machines.
- Example split of the **$49,351 gap** (illustrative schedule — adjust deposits to cash you actually add):
  - Oct: +$10k deposit · bots target +3–6% on deployed risk
  - Nov: +$10k deposit · bots target +3–6%
  - Dec: +$8–15k deposit · bots protect capital into year-end
- Remaining gap covered by realized + unrealized Mirror A P&L only after QA PASS fills.
- Wire **Daily Trader** (~$2k, lev ×2–×10, flat stocks/commodities by US close) only after funding + order-QA — incremental alpha sleeve, not the whole plan.

### Path C · Risk-off honest
- Stay No Buy in Extreme Fear / Fear until F&G recovers; cash is a position.
- Deploy Classic cash (~$7.3k) only on QA PASS + cleared gates.
- Momentum: trail winners (CRWD/VTRS/P…); free cash before new ~$1k sleeves.

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
- No per-move MD store → 467 notes with `ledger:` tags
- keys-B CSV mislabeled as Mirror A → retagged `classic-keys-B-closed-trades.csv`
- Lessons skill unused systematically → weekly Feedback loop
- Dual-write / number drift → QA number gate before accept
- Daily Trader unfunded → still pending live wire

## Token-lean rules
- Deterministic Python rebuild for move MDs (no LLM per fill)
- Weekly rollup only (not hourly self-improve)
- Skip paid X when credits near zero
- One QA gate per vault refresh, not chatter loops


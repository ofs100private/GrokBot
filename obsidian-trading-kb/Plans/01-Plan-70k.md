---
tags: [plan, 70k]
ledger: mirror-A
starting_capital: 20649.39
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

Canonical note: [[01-Plan-70k]]

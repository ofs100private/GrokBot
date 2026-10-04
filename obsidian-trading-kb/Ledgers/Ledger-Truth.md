---
tags: [ledger, policy]
ledger: mirror-A
asOf: "2026-10-04T15:51:00+03:00"
---
# Ledger Truth

## Classic

- **Open / equity / cash:** Mirror A `11368142` ← `_raw/classic-portfolio.json` · tag `mirror-A`
- **Closed moves (Mirror A truth):** `_raw/parent-etoro-closed-20260501.json` where `isMirrorTrade:true` (79 rows) · tag `mirror-A`
- **Execution closes:** `_raw/classic-keys-B-closed-trades.csv` · tag `keys-B` · **never** call Mirror A
- **REJECT:** user-OfersClaw5 keys equity/cash as Classic

## Momentum

- **Open / equity / cash:** Mirror A `11630170` $8k ← `_raw/momentum-portfolio.json` · `mirror-A`
- **Execution closes:** `_raw/momentum-keys-closed-20260501.json` · `keys-B`
- **REJECT:** Momentum keys MCP ~$10k shape as allocation

## PnL

```
fully_loaded = netProfit - fees
```

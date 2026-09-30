---
tags: [portfolio, parent]
ledger: mirror-A
note: Parent SSO is the feed for Classic mirror-A closes; personal rows tagged parent-SSO
mirrorCloses: 79
personalCloses: 118
source: _raw/parent-etoro-closed-20260501.json
---
# Parent eToro SSO

Source file for **Classic Mirror A closed moves** (`isMirrorTrade:true`, n=79).

| Slice | n | Σ netProfit | Σ fully_loaded | Ledger tag |
|-------|---|-------------|----------------|------------|
| Mirror trades | 79 | $35.23 | $37.28 | mirror-A |
| Personal (`isMirrorTrade:false`) | 118 | -$3,661.21 | -$3,922.56 | parent-SSO |

socialTradeId on mirror rows: `11205170` (ambiguous vs numeric mirrorId 11368142 — tagged mirror-A per QA: parent JSON is Classic close truth; filter `isMirrorTrade`).

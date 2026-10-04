---
tags: [feedback, qa]
ledger: mirror-A
asOf: "2026-10-04T15:51:00+03:00"
---
# Feedback loop

## Purpose

Close the loop between vault claims → QA Bot → CoS → traders, without inventing PnL.

## Cadence

1. **Refresh `_raw/`** from afternoon/morning sidecars (Classic A + Momentum A only for equity/cash).
2. **Rebuild notes** (`_raw/build_vault.py`) — every note gets `ledger: mirror-A` or `ledger: keys-B` (or explicit `parent-SSO` for personal).
3. **Write QA pack** → `_raw/qa-pack-obsidian-kb.json` listing every claimed equity/cash/pnl + source path.
4. **CoS → QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`): request number-gate re-check; executor cannot `SendToAgent`.
5. On **FAIL**: fix deviation codes; never mark done until PASS.
6. On **PASS**: optional lessons into `Journals/` + Momentum `trading-lessons` path.

## Hard rules in every loop

- Classic/Momentum equity = Mirror A sidecars only
- Classic closed moves = parent JSON (`isMirrorTrade` preferred)
- `classic-keys-B-closed-trades.csv` = keys-B only
- `fully_loaded = netProfit - fees`

## Current pack

- QA pack: `_raw/qa-pack-obsidian-kb.json`
- Last verdict (prior FAIL): `_raw/qa-verdict-obsidian-kb.json`
- Plan baseline capital: **$20,649.39** → see [[01-Plan-70k]]

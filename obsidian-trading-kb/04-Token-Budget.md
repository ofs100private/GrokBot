---
tags: [tokens, ops]
ledger: mirror-A
---
# Token budget

1. **Rebuild notes with Python** (`_raw/build_vault.py`) after fills — never one LLM call per trade.
2. **Weekly** KEEP/AVOID rollup only (Sunday); skip if no new closes.
3. **QA once** per vault refresh; fix FAIL codes then one re-check.
4. **No** Fear-override re-ask loops; no X Tier-2 when credits ≈ $0.
5. Briefs stay dual-write + QA; do not re-pull full history every slot.

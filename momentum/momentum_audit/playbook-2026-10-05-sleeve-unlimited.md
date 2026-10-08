# Playbook update 2026-10-05 — sleeve capacity

Ofer (chat): Mirror A shows ~$3.2k invested / ~$4.6k cash — room to buy. Old 3-stock+1-ETF **count** cap blocked NTAP/ANET/FFIV despite cash.

**New rule:** unlimited open stocks; keep **at least 1 sector ETF**. Cash + ≤$1000/name still gate. Do **not** FAIL `SLEEVE_CAPACITY_FULL` / `MAX_STOCK_PICKS` / stock_buys>3 / buy_count>4.

Still FAIL: etf_buys>1; >2 MOMENTUM_BREAKOUT in same pack night; freeze/halt/DWM/leverage/amount; INSUFFICIENT_CASH (GATE_OK).

Skills updated: trader-momentum-strategy, momentum-real-money-qa-gate. validate.py pack caps patched.

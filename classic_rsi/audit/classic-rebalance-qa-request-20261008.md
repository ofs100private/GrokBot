To: QA Bot (498c78db-a027-4f2c-8126-3c2be6f0a4bb)
Subject: Classic REAL-money order-QA gate: rebalance batch 2026-10-08 (OfersClaw5-PRIYN)

Please run the Classic real-money order-QA gate on this batch. Ofer approved the rebalance plan (2026-10-08 ~20:26 IDT). BAC is skipped. Nothing gets placed until QA PASS and Ofer/CoS authorize. Prepare tokens expire in ~2 min and were not stored; at place time we re-prepare with identical params.

Batch: /workspace/classic_rsi/audit/classic-rebalance-batch-20261008-keys.json
Live snapshot 20:28 IDT: cash $4,048.63, no pending orders. SMH 2.65783u (pos 3581725275, SL 581.80, live bid 601.27, ~$1,598), QQQ ~$823, XLV ~$758. Live equity ~$7,228.
Sequence (sells first):
1) SMH (6357) SELL partial, 1.25401u (~$754 @ bid 601.27), existing SL 581.80 kept, est fee ~$1.13 (estimated: prepare-close returns no fee) -> /workspace/classic_rsi/audit/classic-rebalance-smh-trim-754-20261008-keys.json
2) SPY (3000) BUY $700 x1, ~0.9083u @ ask 770.65, trailing SL 709.03 (-8%), no TP, fee $1.05 + spread $0.02, overnight $0 -> .../classic-rebalance-spy-700-20261008-keys.json
3) TMO (1592, US stock) BUY $500 x1, ~0.7754u @ ask 644.86, trailing SL 574.26 (-11%), no TP, fee $0.75 + spread $0.29, overnight $0 -> .../classic-rebalance-tmo-500-20261008-keys.json
4) XLE (3008, ETF) BUY $300 x1, ~4.5991u @ ask 65.23, trailing SL 60.01 (-8%), no TP, fee $0.45 + spread $0.05, overnight $0 -> .../classic-rebalance-xle-300-20261008-keys.json. FLAG: XLE is up 2.94% today, so we are chasing; recommend waiting.
Cash after all trades ~$3,298.89 (floor $2,500, PASS). Post-trade weights: SMH 21.5, QQQ 21.0, XLV 19.3, SPY 17.8, TMO 12.7, XLE 7.6. Growth sleeve 42.5% (cap 45). Healthcare 32.0%. All caps pass.
Other flags: SMH SL 581.80 is only 3.2% below the bid (SMH is down 3.8% today). The SMH remainder is ~$844, not $860. SPY and XLE need a W-8BEN on file.

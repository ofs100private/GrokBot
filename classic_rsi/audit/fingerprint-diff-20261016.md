# params_fingerprint diff — 2026-10-16

Runs: classic-rsi-auto-20261016-154325-8f21b04f (fp a04e9a9764275b17) vs classic-rsi-auto-20261016-183755-db0e58a0 (fp 8525cf0f).

## Params that changed (all data-driven)
- `symbols` (scanned universe): 46 names left, 47 names joined (rising-volume top-50 rotates each hour). The book, QQQ/XLE/XLV and BTC/ETH/SOL are in both runs.
  - Left: RTX CVNA KDP RL PEP FRT NDSN TFC GPN FLEX ROL PNR EL DD IR WEC WMB HUBB HAL SNA DTE FE EXPE STE PLD RF ED TRMB AON TROW EOG HIG ALB ITW CPT VEEV MTB SW CBOE MAR PSA ZTS MAA PCG TEL LYB
  - Joined: AAPL TSLA NVDA MSFT UNH TWLO VMRK MRNA NEM F KO CMS RDDT TT PFE AIG BSX MGM UBER DOC AEE CNP STLD BA PM SYK GIS SCHW BRK-B INVH LH NOC DE AMD GM SNDK ESS AES EXR BALL FTNT CI CRWD OMC PLTR Q IBM
- `universe_meta.asOf` / `asOfUTC`: 15:43:03 → 18:37:30 IDT (the scan timestamp is part of the params).
- `universe_meta.liquid_count` 492 → 486, and `liquid_reference.drop_pct` -0.2 → 1.02. That's within the 2% tolerance and above the 481.18 threshold.
- `universe_meta.universe_size` 53 → 54.
- `universe_meta.skipped` / `errors_sample`: VYLR "11 daily bars < 20" → "12 daily bars < 20" (a new listing gained one more daily bar).

## Params that did not change
period, force, notional, status, flags, soft_flags, universe_skipped_count, auto_place_eligible_count, note, instrument_map_sha256 (so the crypto id map and the T/T.US map are the same). Thresholds (min_adv_usd 1e8, min_price 10, rising_mult 1.2, top_n 50, SMA 20, retry policy) are also the same.

## Code/config changes 15:43–18:37
None. A search for files modified in that window under /workspace/classic_rsi (excluding audit/), /workspace/sp500_symbols.json and the venv found nothing.

## Verdict
BENIGN. The fingerprint hashes the whole params dict, and that includes the live universe and the scan timestamp, so it changes on almost every run. RSI levels, ATR multipliers and the instrument map are unchanged. Suggestion: QA could compare a fingerprint that excludes the universe and timestamp fields when checking for config drift.

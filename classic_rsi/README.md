# classic_rsi — Classic-only RSI four-level entries (1H)

Long-only timing overlay for **Trader_Classic** on **OfersClaw5-PRIYN** (REAL MONEY).  
Does **not** place trades. Does **not** touch Momentum. Does **not** change Fear / cash / weekend regime gates.

## Specs

| Item | Value |
|------|--------|
| Timeframe | **1H only** (live + backtest) |
| Side | Long-only; Sell triangles → **RISK_OFF** (never short) |
| RSI | length 14, close; Over Buy 79.90 / Resistance 67.90 / Support 34.90 / Over Sold 19.90 |
| Strong candle | body ≥ 1.2 × SMA(body, 20) |
| Labels | EXTREME_80 / ZONE_70 — **rule tags, not win rates** |
| Zone SM | one fire per zone visit; reset when RSI leaves zone |
| Bars | **confirmed close only** (forming bar dropped) |
| SL/TP | ATR(14) on 1H: SL = 1.5×ATR below entry, TP = 2.0×ATR above (**never FX pips**) |

Mandate gates stay with Trader_Classic: Fear, cash floor ≥ ~$2.5k, weekend no new opens, ×1, no crypto, QA PASS before place.

## Package layout

```
/workspace/classic_rsi/
  signals.py   # RSI zones, strong candle, long-only remap
  levels.py    # ATR entry / SL / TP (equities)
  backtest.py  # 1H Yahoo backtest smoke
  propose.py   # candidate BUY packs + RISK_OFF notes
  universe.py  # S&P → liquid ADV$ → rising 1H volume screener
  auto_1h.py   # 1H session auto runner (propose → audit; never place)
  audit.py     # append-only run trail
  audit/       # timestamped JSON + index.jsonl + universe-latest.json
  README.md
```

## Trader_Classic invocation (propose → QA → place)

```python
# From /workspace (or PYTHONPATH including /workspace)
from classic_rsi.propose import propose_from_symbols

out = propose_from_symbols(["AAPL", "MSFT", "QQQ", "SMH", "XLV", "JNJ"])
# out["buy_packs"]  → candidate long packs (ATR SL/TP), status=PROPOSE_ONLY
# out["risk_off"]   → no-add / skip-chase notes (never shorts)
```

CLI:

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.propose --symbols AAPL MSFT QQQ --out /tmp/classic-rsi-propose.json
```

**Then (mandatory):**

1. Apply Classic mandate gates (Fear, cash ≥ ~$2.5k after size, weekend rule, ×1, no crypto).
2. Fill `fee_estimate` + `overnight_financing_estimate` via prepare / getCost; set size.
3. Submit each BUY pack to **QA Bot** using **classic-real-money-order-qa-gate**.
4. Place **only** after QA **PASS**. RISK_OFF notes never become short orders.

## Backtest (1H)

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.backtest \
  --symbols AAPL MSFT QQQ SMH XLV JNJ \
  --period 60d \
  --out /workspace/classic_rsi/backtest-summary-1h.json
```

Summary JSON states `timeframe: "1H"`. Yahoo intraday history is ~60d for 1h bars.





## 1H auto runner

```bash
cd /workspace
./screener-venv/bin/python -m classic_rsi.auto_1h
# optional: --symbols SMH QQQ XLV --force  (weekend override) --dry-run --out /tmp/auto.json
```

Behavior:
- **Universe (no fixed list):** S&P pool (`/workspace/sp500_symbols.json`) → liquid ADV$ (SMA20 close×volume ≥ **$100M**, price ≥ **$10**) → rising confirmed 1H volume (last vol > SMA20×**1.2**) → top **~50** ∪ live Classic book (`/workspace/classic-portfolio-for-app.json`). Cache: `audit/universe-latest.json` (fallback if yfinance flakes; never silently use the old 6-name DEFAULT_SYMBOLS as primary). Metadata on envelope as `universe_meta`.
- Soft gates: weekend / outside US RTH / cash &lt; ~$2.5k → status `GATED` (buy packs suppressed; risk_off scan may still run)
- Always `do_not_place=True` — every run → QA Bot (classic-rsi-1h-run-qa) citing `run_id`; on FAIL QA calls Trader_Classic to rerun (max 2/hour); packs still need order QA (classic-real-money-order-qa-gate) before place
- Writes `audit/latest-auto.json` + append-only audit row (`kind=auto`)

Standing schedule (CoS routine): weekdays `CRON_TZ=America/New_York 35 9-15 * * 1-5` (after each :30 ET hour bar during RTH).

## Audit trail (append-only)

Every **propose** and **backtest** writes under `/workspace/classic_rsi/audit/`:

- `{run_id}.json` — full record (params, fingerprint, packs / aggregate)
- `latest-propose.json` / `latest-backtest.json` / `latest.json`
- `index.jsonl` — one line per run (append-only)

`run_id` is stamped on the propose payload and each `buy_pack`. **QA Bot** and Trader_Classic should cite `run_id=…` in the order thesis.

```bash
ls /workspace/classic_rsi/audit/
tail -n 5 /workspace/classic_rsi/audit/index.jsonl
```

## Do not

- Place from this package / SendToUser
- Emit or execute shorts from Sell triangles
- Use pip distances on US equities/ETFs
- Modify Momentum playbooks or Classic Fear/cash/weekend gates here

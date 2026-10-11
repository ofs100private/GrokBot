---
tags: [journal, weekly-rollup]
week_ending: 2026-10-11
asOf: "2026-10-11T15:50:00+03:00"
written_at: "2026-10-11T18:50:23+03:00"
qa_fix_at: "2026-10-11T18:52:00+03:00"
---
# Weekly rollup · week ending 2026-10-11 (Sunday IDT)

Evidence-only. No invented PnL. Classic equity/cash from **OfersClaw5-PRIYN agent account** (`user-OfersClaw5`). Momentum from Mirror A id `11630170` (`user-Momentum-HHHGDTJ` / parent mirror). Parent Mirror A id `11368142` (OfersClaw5-PRIYN copy on `user-etoro`) is **reference only** since the 2026-10-06 reporting switch — live ~$12,773.46, not Classic book truth.

## LIVE: Classic agent account (OfersClaw5-PRIYN) + Momentum Mirror A 11630170 (asOf 2026-10-11T15:50:00+03:00)

| Book | Equity | Cash | Symbols |
|------|--------|------|---------|
| Classic, OfersClaw5-PRIYN agent account (`user-OfersClaw5`) | $7,268.37 | $3,671.18 (~50.5%) | QQQ / SMH / XLV / SPY / TMO |
| Momentum Mirror A `11630170` ($8k basis) | $7,925.62 | $2,694.47 (~34.0%) | P / CRWD / XLK / NTAP / ANET / ZBRA |
| **Combined (agent Classic + Momentum Mirror A)** | **$15,193.99** | — | — |

Reference only — parent Mirror A `11368142` (OfersClaw5-PRIYN copy): live ~**$12,773.46** (invested $15,000; cash ~$6,551.41). Not used as Classic truth since 2026-10-06.

Frozen 70k-plan START (2026-09-30): **$20,649.39** (Classic $12,841.61 + Momentum $7,807.78).  
Gap to $70k from LIVE combined: **$54,806.01**. Δ vs start: **−$5,455.40** marked.

**Basis note (not closed PnL):** prior rollup (2026-10-04) used Classic Mirror A SSO equity ~$12,930; from 2026-10-06 Classic reporting sidecars use OfersClaw5-PRIYN (~$7.3k). Do not treat the full Δ vs frozen start as realized trading loss.

> **W1 / SMH pricing basis:** Classic $7,268.37 is from the summary endpoint, which still prices SMH stale at 601.72. Positions-based Classic = **$7,270.38** (SMH @ 603.28), which makes combined **$15,195.99** and gap **$54,804.01**.

Sources: `_raw/classic-portfolio.json`, `_raw/momentum-portfolio.json` (refreshed from `app-refresh-2026-10-11-pm`; Momentum `positionId`/invested enriched from `app-refresh-2026-10-10-am` for open names — marks/pnl from Oct 11 sidecar).

## KEEP (evidence)

1. **Classic Oct 8 rebalance filled with stops** — audit `classic-rebalance-batch-20261008-keys-fill-audit.json` status `ALL 3 EXECUTED (SMH -> SPY -> TMO)`; live sidecar now holds QQQ/SMH/XLV/SPY/TMO with cash $3,671.18 above ~$2,500 floor. Related fills: `classic-rebalance-spy-700-20261008-keys-fill-audit.json`, `classic-rebalance-tmo-500-20261008-keys-fill-audit.json`, SMH trim fill. **Note:** the planned **XLE** leg was never placed (no XLE in Classic trading history since Oct 1, and none in open positions/orders).

## AVOID (evidence)

1. **CAT quick stopout** — Classic trading history pos `3600708904`: opened 2026-10-07 21:51 IDT, $500, 0.616348u @811.23 (SL 798.61, TP 834.14); stopped 2026-10-08 13:25 IDT @798.02 (**−$8.14**, fees 0; fill audit `classic-cat-500-20261007-keys-ofer-fill-audit.json`). Name absent from Oct 11 sidecar. Short hold after entry.

## Top job failures / unexpected (this week · Oct 5–11)

| Status | Run | Note |
|--------|-----|------|
| partial | `daily-brief-1530-2026-10-05-no-qa` | Afternoon folder missing qa-verdict → new P2 ticket |
| partial | `daily-brief-0530-2026-10-10-no-qa` | Morning folder missing qa-verdict → new P2 ticket |
| blocked | `classic-rsi-auto-20261006-111839-dff9a11d` | QA PASS; blocked vs mandate / no place — expected mapping |
| blocked | `classic-rsi-auto-20261008-233619-82d83301` | After hours; qa n/a — expected blocked |

No new `status: fail` Job-Runs in Oct 5–11 (66 success / 2 blocked / 2 partial of **70** notes by filename for Oct 5–11). The backfill `--since 20261004` wrote 73 notes including Oct 4 (3 notes); Oct 5–11 scope is 70. Prior Oct 2 Gate D fail remains historical (superseded PASS).

## Open improvement tickets (5)

1. **P0** [[Process/Improvements/improvement-2026-10-01-momentum-eod-place-gap]] — place_ack / watchdog / keys MCP (still open; book rotated but process fixes not landed)
2. **P2** [[Process/Improvements/2026-10-04-daily-brief-0530-daily-brief-0530-2026-10-02-no-qa]] — morning missing QA
3. **P2** [[Process/Improvements/2026-10-04-daily-brief-0530-daily-brief-0530-2026-10-03-no-qa]] — morning missing QA
4. **P2** [[Process/Improvements/2026-10-11-daily-brief-1530-daily-brief-1530-2026-10-05-no-qa]] — afternoon missing QA (new)
5. **P2** [[Process/Improvements/2026-10-11-daily-brief-0530-daily-brief-0530-2026-10-10-no-qa]] — morning missing QA (new)

Duplicate closed this rollup: [[Process/Improvements/2026-09-30-daily-brief-0530-daily-brief-0530-2026-09-28-no-qa]] marked **done** (same `run_id` as Oct 4 duplicate ticket already done).

## Notable week moves (evidence paths only; no invented PnL)

- Classic fills: SPCX/RBRK (Oct 6), ADBE/GS/CAT (Oct 7), SMH SL set $581.80, Oct 8 rebalance SMH→SPY/TMO; CAT stopped Oct 8 (−$8.14, pos `3600708904`).
- **Classic realized P&L Oct 5–11: −$2.00** (CVX −78.67, IGV +60.88, SPCX −19.10, RBRK −18.65, GS +1.94, ADBE +4.83, CAT −8.14, SMH trim +54.91).
- Momentum: VTRS BE stop (brief 2026-10-08); live names now include ANET/ZBRA; MRVL/VTRS absent vs mid-week briefs.
- **Momentum realized P&L Oct 5–11: −$156.96** (HPQ −61.50, MRVL −36.96, JNJ −59.92; rotation closes NDSN −15.91, DE −39.30, FTNT +72.08, AAPL −15.75, ETH +0.30, VTRS 0.00 BE; −$158.62 after fees).
- **Parent account `ofs56etoro` (outside both bot books):** QNT round-trip; 10x SPX500 opened Oct 9; BAT/ORCA crypto Oct 10; STRK $1,200 opened Oct 11 16:26 IDT. Not part of Classic or Momentum books.
- Job-Runs backfill this rollup: `Scripts/write_job_run.py --backfill --since 20261004 --cap 500` → Classic-RSI 39 · Breakout-TA 6 · Momentum-EOD 16 · Daily-Brief 11 · QA-Gates 1 (73 notes incl. Oct 4; Oct 5–11 = 70).

## Vault rebuild

`_raw/build_vault.py` → live combined **15193.99** (agent Classic + Momentum Mirror A); frozen start stays **20649.39**; Portfolios/Positions regenerated from refreshed sidecars.

## QA number-gate

**YES — needed.** Equity/cash/symbol set changed vs prior vault asOf 2026-10-08 (and vs 2026-10-04 journal). Classic 7302.98→7268.37; Momentum 7909.58→7925.62; symbols Classic +SPY +TMO −ADBE; Momentum +ANET +ZBRA −MRVL. Parent should ask QA Bot `498c78db-a027-4f2c-8126-3c2be6f0a4bb` vs `_raw/qa-pack-obsidian-kb.json`. This automation did not call QA Bot.

QA FAIL fix applied 2026-10-11 (F1_MIRROR_A_MISLABEL + W1–W6): retitled combined basis; dropped frontmatter `ledger: mirror-A`; 11368142 reference-only; XLE note; week realized P&L; Sep-28 ticket duplicate; Oct 5–11 job-run count 70; CAT pos cite; parent-account outside-books note.

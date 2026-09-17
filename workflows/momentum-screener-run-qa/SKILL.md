---
name: Momentum screener run QA
description: >-
  use this when QA must verify each Momentum EOD screener run for full S&P 500
  universe integrity, TRACE/run summary, and on FAIL force a rerun then
  re-validate until PASS before any buy pack is accepted
---
# Momentum screener run QA (verify → FAIL → rerun → PASS)

Independent **per-run** gate for the Momentum EOD screener. Complements the existing Momentum real-money QA gate (order packs / fills). This skill owns **universe integrity and run success**, not position sizing.

**Do not place trades from this skill.** Only PASS / FAIL the run and demand a clean rerun when needed.

Playbook **2026-09-16 full fix**: always scan when session allows; HARD_HALT and **EVENT_VOL_FREEZE** still require scan + near-miss (0 BUY). Sleeve/pack/trade rules live in [Momentum real-money QA gate](sand-workflow:momentum-real-money-qa-gate). Changelog: `/workspace/momentum_audit/playbook-2026-09-16-full-fix.md`.

## When to run

- Immediately after every `momentum_screener` EOD (or catch-up) run lands in the audit
- Before accepting any screener BUY pack for place-QA
- When CoS / trader reports Wikipedia / SPX-list / mega-cap-fallback issues
- On the post-22:50 miss check, if a catch-up screener just finished

## Evidence to collect

1. Screener stderr / run log (S&P list source: live Wikipedia or cache)
2. `/workspace/sp500_symbols.json` when present (`count`, `asOf`, `symbols`)
3. Audit JSONL: `RUN_START` / TRACE / `ACTION` / `RUN_END` for `momentum_screener.py`
4. Run summary: `/workspace/momentum_audit/screener-run-<run_id>.json` (**required**)
5. Near-miss: `/workspace/momentum_audit/near-miss-YYYY-MM-DD.json` when scan ran (HARD_HALT / EVENT_VOL_FREEZE / SOFT / HEALTHY)
6. Screener output pack (BUY / SKIP / HALT rows) if written to disk
7. Patched `momentum_screener.py` markers: `io.StringIO`, no silent 10-name mega-cap fallback

## Hard FAIL (any one) — `deviation_code` as noted

| Code | Condition |
| --- | --- |
| `SPX_UNIVERSE_TOO_SMALL` | Live or cached S&P list `< 400` symbols |
| `SPX_MEGACAP_FALLBACK` | Universe is only a tiny mega-cap stub (e.g. ~10 names) or log shows the old silent fallback |
| `SPX_FETCH_BROKEN` | Log shows `read_html` / `FileNotFoundError` treating HTML as a path, or Wikipedia fail **without** a valid ≥400 cache recovery |
| `SPX_SCAN_NOT_FULL` | Session allowed a scan (not holiday / not intraday ban) but scan did not cover full S&P + sector/commodity ETFs — **includes HARD_HALT and EVENT_VOL_FREEZE**: early exit without download/scan/near-miss is FAIL |
| `SCREENER_RUN_CRASH` | Exception / empty run with no HALT/SKIP/BUY ACTION after retries exhausted |
| `SCREENER_AUDIT_INCOMPLETE` | Missing `RUN_START` or `RUN_END`, ACTION without rationale, missing TRACE (regime / universe_n / retries), or missing `screener-run-<run_id>.json` |

Representative mid/large names (e.g. NOW, PANW, CRM) **must be eligible for scan** whenever the universe is full — they need not be BUY candidates.

## Regime note (playbook 2026-09-16)

- **EVENT_VOL_FREEZE** (FOMC/CPI/NFP today or next NYSE session): 0 BUY OK; still require full scan + near-miss + TRACE + run summary
- **HARD_HALT** (VIX ≥ 25 or SPX < 0.98×SMA50): 0 BUY OK; still require full scan + near-miss + TRACE + run summary
- **SOFT** / **HEALTHY**: full scan required; BUY rows go to Momentum real-money QA gate (breakout sleeve, soft RVOL≥2.5, pack ≤2 BO + fill to 3 stocks)
- Old “any SPX < SMA50 → regime-first exit with no scan” is **retired**

## PASS (run-level)

All of:

1. S&P universe ≥ 400 (live or cache), no mega-cap stub
2. No `SPX_FETCH_BROKEN` / `SPX_MEGACAP_FALLBACK` in this run
3. Audit has coherent screener `RUN_START` → TRACE → ACTION(s) → `RUN_END`
4. `screener-run-<run_id>.json` present with regime + universe_n
5. When session allowed scan: near-miss file present (or empty near-miss explicitly documented in TRACE/run summary)
6. If ACTION is BUY/SKIP pack: pack still goes through the Momentum real-money QA gate
7. HARD_HALT or EVENT_VOL_FREEZE with 0 BUY + full scan + near-miss + TRACE = run PASS for universe

## FAIL → rerun → re-validate (mandatory)

When any hard FAIL above fires:

1. Verdict **FAIL** with codes + evidence paths → trader + CoS
2. **Do not** accept BUY packs from the failed run
3. Instruct the trader to **rerun** the patched screener (StringIO + cache + hard-fail if universe < 400)
4. Cap: **up to 3 attempts** same NYSE session
5. After each rerun: re-collect evidence and re-apply this skill from scratch
6. If still FAIL after max attempts: **day FAIL** for screener integrity; escalate to CoS / user; no places from that pack

## Verdict routing

1. FAIL / PASS (run) → Momentum trader
2. Material FAIL or exhausted retries → Chief of Staff (and user when buys were blocked or day FAIL)
3. Compose with Momentum real-money QA gate for any BUY rows after run PASS

## Standing rule

Every NYSE EOD Momentum screener must scan the **full S&P 500** (+ sector/commodity ETFs), including under HARD_HALT and EVENT_VOL_FREEZE. QA owns verify + demand rerun. Scanning is mandatory; buying remains filtered by strategy + trade QA.

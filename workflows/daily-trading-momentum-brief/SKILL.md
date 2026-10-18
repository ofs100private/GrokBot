---
name: daily-trading-momentum-brief
description: >-
  use this when running Ofer's daily_brief Fear & Greed / trading momentum brief
  for one or more parameterized agent portfolios
---
# Daily trading momentum brief

## Portfolio parameter (required)
- Input: `portfolios` — list of agent-portfolio keys the user wants (examples: `Classic` / `OfersClaw5-PRIYN`, `Momentum` / `Momentum-HHHGDTJ`).
- Support any subset: one, several, or all of the user's agent portfolios. Never hardcode which book.
- For each selected book, pull LIVE ledger fields via eToro Account / the matching trader agent (invested, equity, cash, open/closed PnL, positions). Do not invent dollar amounts.
- **Standing default (Ofer):** `portfolios=[Classic, Momentum]` — always produce a separate Portfolio Recommendation card for **Classic** (Classic account (OfersClaw5-PRIYN)) **and** **Momentum** (Momentum-HHHGDTJ). Override only if Ofer narrows the list for a run.
- **Classic truth** = Classic account (OfersClaw5-PRIYN) live via MCP `user-OfersClaw5` (equity/cash/positions). Parent SSO mirror `11368142` is optional copy/UI corroboration only — never required, never the rejection reason. Do **not** reject OfersClaw5 figures as Classic.
- **Momentum truth** (UNCHANGED): Momentum agent book / mirror `11630170` as $8k reporting truth; keys Momentum-HHHGDTJ for execution only — never mix Classic dollars into Momentum or vice versa.
- **Cross-book no-overlap (Ofer 2026-10-13 01:44 IDT):** never buy a symbol in Classic (OfersClaw5-PRIYN) that is held in Momentum (mirror 11630170), or vice versa. Before any buy or buy proposal on a recommendation card, live-read the other book; overlap = blocked. QA gates hard-FAIL `CROSS_BOOK_OVERLAP`. Existing overlap XLE: Ofer decided 2026-10-13 to keep it held in both books; never add to it in either. **Recommendation cards (section 13):** any buy/add idea that overlaps the other book must appear under **Blocked** (not Buy / Would Buy).

## Live data rules
1. Fetch LIVE only via tools. Preferred F&G: `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`. Fallback: web search / CNN Fear & Greed page.
2. CNN 7 COMPONENTS ARE MANDATORY from graphdata: `market_momentum_sp500`, `stock_price_strength`, `stock_price_breadth`, `put_call_options`, `market_volatility_vix`, `junk_bond_demand`, and the remaining component in that payload (include all seven with score + English rating). Never omit the tail of the brief.
3. Commodities: WTI oil, gold, silver — live price + day % change.
4. Trump section: last Trump post with timestamp, short quote, link; 1 line market relevance; enforce freshness.
5. Analyst score (X Tier 2): 3–6 theme bullets from last 24h, or `Nothing Special from the last 24h`.
6. Weekend (Sat/Sun): only the 05:30 run executes, in **SHORT mode** (see *Weekend SHORT mode*); the 15:30 run is a no-op. Classic equities are outside the 24x5 window (no new equity size; BTC/ETH/SOL still 24/7). Momentum / RTH-only books → recommendations for next US session; no new equity opens.

## Required brief structure (stop only after Source)
1. Header: `Good Morning | (CNN Fear & Greed)` + today's date (user TZ Asia/Jerusalem)
2. Current score (int) + English rating
3. Compare: previous close, week, month, year
4. All 7 components with score + English rating
5. Section: last trump twit
6. Section: סחורות — Oil / Gold / Silver
7. Section: Analyst score (X Tier 2)
8. Short market read + trading takeaway
9. Section: Daily Signals — What I Would Buy / Sell — 2–4 buys and 2–4 sells/avoids; each ticker: Opening Price / Previous Close / Current Price (% Change), rationale, analyst views
10. Section: Oil / Gold / Silver — explicit yes/no/wait for related asset
11. Section: Impact on Crypto — BTC + daily move; BTC/ETH and crypto-beta (COIN/HOOD); buy vs don’t chase
12. Section: Expected Daily Impact — 3–6 bullets
13. Section: `{PORTFOLIO_NAME} Portfolio Recommendation` for **EACH** selected portfolio — Portfolio card (N names / cash / deployment % — no invented dollars); Buy 0–2 or No Buy Today; Sell/Rotation 1–2 or No Sale; Hold; Diversification note. With the standing default, that means **two** cards: Classic then Momentum.
14. Source line with update timestamp

If length pressure: shorten section-9 reasons; keep sections 10–14. A brief that stops early is FAILED — complete through Source.

**Activation status (Ofer 2026-10-16 01:27 IDT):** Classic FULL AUTO is ON. Code gate PASSED QA (fix3, 2026-10-12); Ofer accepted QA's residual risks. After run-QA + order-QA + cost-gate PASS, Trader_Classic auto-places via `user-OfersClaw5` with **no chat authorization**. Caps of **total equity**: stock ≤20%, ETF ≤35%, sleeve ≤45%, crypto (BTC/ETH/SOL) ≤15%. Cash floor ~$1,500. Max **4 new trades per IDT day**. Equities 24x5 (extended hours); BTC/ETH/SOL 24/7. Long ×1; SL+TP mandatory. Unchanged: cross-book no-overlap; no XLE adds.

## Classic recommendation cap filter (mandatory — applies to sections 9 and 13)
Source of truth for caps: `/home/box/agent-data/workflows/classic-rebalance/SKILL.md` — read it each run and cite its caps; if they differ from the values below, its values win.
1. Before listing ANY Classic buy/add idea, compute from the live `user-OfersClaw5` book:
   - Each name's % of **total equity** vs the name cap (currently **≤35% ETF / ≤20% single stock**).
   - Growth sleeve (QQQ+SMH+other growth/tech) and any sleeve % of **total equity** vs the sleeve cap (currently **≤45%**); crypto sleeve (BTC+ETH+SOL) ≤ **15%** of total equity.
   - Cash vs equity: if cash >50% of equity, note the cash drift trigger.
2. Drop any idea that breaches a cap or leaves less than the minimum trade size of headroom (currently **$400** minimum position). A blocked idea may appear only under **Blocked / needs Ofer exception** — never under Would Buy. Market-watch names Classic can't buy must be labeled **market watch only**.
2a. **Cross-book overlap:** before listing any Buy on either portfolio card, live-read the other book. If the symbol is held there, move that buy idea to **Blocked** (`CROSS_BOOK_OVERLAP`); never list it under Buy / Would Buy. Existing overlap XLE stays held in both books per Ofer 2026-10-13; any XLE add is Blocked.
3. Names already held go under **Hold/Watch**, not Would Buy.
4. Authorization wording: briefs must say **Classic FULL AUTO ON (Ofer 2026-10-16 01:27 IDT) — residual risks accepted; auto-place after run-QA + order-QA + cost-gate PASS, no chat auth**. Max **4 new trades per IDT day**; no monthly new-name cap. Cash floor ~$1,500; caps of total equity 20%/35%/45%/15% crypto.
5. Last trump twit: check Truth Social (e.g. trumpstruth.org) as well as X; quote the freshest post.
6. Weekends: if nothing material changed vs the last delivered brief, say so in the META line so the Chief of Staff can skip delivery.

## Weekend SHORT mode (Ofer 2026-10-18, token saving; weekdays unchanged; no trading-rule change)
**Gate first, before any read:** `python3 /workspace/daily-brief/write_targets.py gate --slot <0530|1530>` (Asia/Jerusalem day).
- Exit **3 = noop** (the 15:30 slot on Sat/Sun): exit immediately. No reads, no writes, no QA, no Chief of Staff handoff, no message.
- Exit **4 = short** (the 05:30 slot on Sat/Sun): run SHORT mode as below.
- Exit **0 = full** (any weekday slot): follow the full structure above, unchanged.
- Exit **5 = skip** (weekday 15:30 only; lever 8, Ofer 2026-10-18 16:44 IDT; 2026-10-18g): no material change since the 05:30 inputs. Write nothing, no QA, no handoff, no message; the gate already appended its audit line to `/workspace/daily-brief/audit/gate-1530-YYYYMMDD.jsonl`.

## 1530 brief only on material change (lever 8, Ofer 2026-10-18 16:44 IDT; 2026-10-18g)
- **05:30 (weekdays) must leave the baseline.** Run `market_data.py --slot 0530 --out /workspace/daily-brief/raw/market-0530-<YYYY-MM-DD>.json`, and `books.snapshot ingest` the fresh Classic (`classic`) and Momentum mirror 11630170 (`momentum_mirror`) reads. Ingest keeps a history copy, and the copy nearest 05:30 (04:00–07:30 window) is the baseline.
- **15:30 step 0 (weekdays), before writing anything:**
  1. `cd /workspace && python3 -m books.snapshot fresh --book classic --max-age-min 60` and the same with `--book momentum_mirror`. For each that exits 2, do the hinted live read (`python3 -m books.snapshot agent-read-hint --book <b>`) and `ingest` it. The full brief needs these reads anyway.
  2. `python3 /workspace/daily-brief/write_targets.py gate --slot 1530`. It fetches market data itself (saved as `raw/market-1530-<date>.json`; a FULL run reuses it instead of refetching) and compares against the 05:30 inputs (`material_gate.py`).
- **Material (any → exit 0 FULL):**
  - CNN F&G change ≥5 pts or a rating change;
  - ES=F or NQ=F move ≥1%; VIX move ≥10%; WTI or gold move ≥3%;
  - any Classic or Momentum change in holdings, units, cash (>$1), pending orders or stop-loss;
  - any stop within 2% of price; a Classic-vs-Momentum overlap change.
- **Fails open:** a missing or stale input (no 05:30 market file, no 05:30 book history, a book snapshot older than 60 min, a missing price) → FULL. Exit 5 SKIP only when every check ran and none fired. `--no-material` forces the old behaviour.
- Tests: `python3 /workspace/daily-brief/test_material_gate.py`.

**SHORT mode contents.** This replaces sections 1–14 on weekends only, still ending with a Source line:
1. Header `Good Morning | (CNN Fear & Greed) — Weekend Short` + date (IDT).
2. F&G score (int) + English rating, plus compare (previous close / week / month / year) from CNN graphdata. Still write all 7 `components` into the JSON, because the App reader requires `components[]`. They are in the same graphdata payload, so no extra fetch is needed. The markdown may omit them.
3. X/news delta: 3–5 bullets on what changed since the last delivered brief. Keep the X calls cheap (one `search_news` / `search_posts_all` pass), or write `Nothing material since <last brief>`.
4. Last quotes: WTI oil / gold / silver (last + day %), and BTC / ETH / SOL (last + 24h %). Market data only; crypto stays removed and blocked for Classic.
5. One-line **Classic** card and one-line **Momentum** card: equity, cash, cash %, N names, `No Buy Today (weekend)` / `No Sale` unless a rule-driven action exists. The standing cap, cross-book and no-XLE-add rules still apply to any idea mentioned.
6. Source line with the update timestamp. Put a META line on top: `materialChange` vs the last brief, so the Chief of Staff can skip delivery.
- **Skipped in SHORT:** the Trump section, the full Daily Signals tables (section 9), section 10 long form, Crypto-impact long form, and Expected Daily Impact (section 12).
- **Portfolio reads:** `python3 /workspace/daily-brief/write_targets.py snapshot` lists on-disk live snapshots under 60 minutes old per book. Classic: `/workspace/classic-portfolio-for-app.json` or the public sidecar, from `user-OfersClaw5`. Momentum: the mirror `11630170` sidecar. Reuse a fresh one; otherwise do exactly ONE live read for that book (Classic `user-OfersClaw5` get-my-portfolio-summary; Momentum `user-etoro` mirror `11630170`). Ledger-truth rules are unchanged, and no dollars are invented.
- **App dual-write (SHORT):** call `write_targets.write_all(payload, mode="short", date=..., slot="0530", asof=..., brief_path=..., source=<Source line>)`. It writes ONLY the 34 latest canonical targets: `etoroview` + `GrokBot/app/etoroview` × `public`, `public/latest`, `latest`, `dist`, `dist/latest` × the 3 JSONs, plus `/workspace/daily-brief/{daily-brief,latest,classic-portfolio,momentum-portfolio}.json`. It skips every dated archive copy (`daily-brief-0530-DATE/`, `app-refresh-DATE-am/`, `morning-0530-DATE*.json`), the `GrokBot/daily-brief` mirror, the root `/workspace/*-portfolio*.json` copies (including `classic-portfolio-for-app.json`, which belongs to the Classic book refresh) and per-target `.bak` copies. Its `app_compat()` adds the camelCase fields the App reader (`etoroview/src/data/dailyBrief.ts`) requires and drops the skipped sections, and it refuses to write (`APP_SCHEMA`) a payload the App would reject. Keep the brief markdown at `/workspace/daily-brief/brief-weekend-short-0530-DATE.md` (single copy). The manifest is written to `/workspace/daily-brief/written-manifest-short-0530-DATE.json`.
- **QA (SHORT) is lightweight only:** `python3 /workspace/daily-brief/write_targets.py qa-short <manifest>` checks the target set, identical shas, App contract, today's asOf, Classic + Momentum cards with mirror ids, and the brief sha and Source line. PASS → hand off to the Chief of Staff. FAIL → fix and re-run once. Do not run the full daily_brief QA on weekends.
- Weekday runs keep the full structure, the full canonical dual-write list and full QA. The write itself goes through `write_targets.write_all(..., mode="full")`; see *Dual-write target list*.

## Dual-write target list
- (Weekday / full mode. Weekend SHORT mode writes only the latest subset; see *Weekend SHORT mode*.) The canonical App JSON dual-write targets are **only** the live/latest ones:
  - `etoroview` and `GrokBot/app/etoroview`: `public`, `public/latest`, `latest`, `dist`, `dist/latest` (each of `daily-brief.json`, `classic-portfolio.json`, `momentum-portfolio.json`)
  - `daily-brief.json` and `latest.json` in `/workspace/daily-brief` and `/workspace/GrokBot/daily-brief` (plus the portfolio JSON siblings written alongside them)
  - `/workspace/classic-portfolio.json`, `/workspace/classic-portfolio-for-app.json`, `/workspace/momentum-portfolio.json`
  - **plus the CURRENT run's own dated folder and file only** (e.g. `/workspace/daily-brief/morning-0530-YYYY-MM-DD.json` or afternoon equivalent, `/workspace/daily-brief-SLOT-YYYY-MM-DD/*.json`, `/workspace/app-refresh-YYYY-MM-DD-am|pm/*.json`)
- **Weekday writer (Ofer 2026-10-18b; mandatory):** do every weekday App dual-write with `import sys; sys.path.insert(0, "/workspace/daily-brief"); import write_targets as WT` then `WT.write_all({"daily-brief.json": d, "classic-portfolio.json": c, "momentum-portfolio.json": m, "latest.json": latest}, mode="full", date=DATE, slot="0530"|"1530", asof=ASOF, brief_path=<brief .md>)`. Never hand-roll a target loop. `write_all` builds the canonical list above fresh (it reproduces it exactly, 50 targets including this run's dated copies). It then runs the payload through `app_compat()`, which fills the fields the App reader `etoroview/src/data/dailyBrief.ts` requires, from data already in this run:
  - F&G `previousClose` / `previous1Week` / `previous1Month` / `previous1Year`, and component `label`s
  - commodity `symbol` / `last` / `dayPct` / `stance`
  - `dailySignals` / `expectedDailyImpact` / `analystScore` / `source`, parsed from the brief markdown (sections 7, 9, 12, 14)
  - portfolio `card` and list-form `recommendation`, from the run's sidecars
  
  Next, `app_check()` validates the payload. A payload the App would reject raises `APP_SCHEMA` and nothing is written: fix the brief/payload and re-run.
- Keep the section-9 lines machine-readable: `N. **SYM** — Opening $X / Prev Close $Y / Current $Z (**±p%** …). rationale`. An idea without all three prices is kept only as an `unpriced` note and never shown as an App signal, and no prices are invented. Derived fields are stamped with the brief sha and re-derived each run, so a previous run's signals can never carry over.
- After writing, a quick reader check is optional: `/exec-daemon/node --experimental-strip-types` against a copy of `dailyBrief.ts` (harness `/workspace/daily-brief/appcheck/check_etoroview.ts <file>`; re-copy `dailyBrief.ts` there if the App source changes). `app_check()` mirrors that reader's hard requirements.
- **Never** copy a target list from a previous `written-manifest.json`. Build the list fresh each run from the canonical set above.
- **Never** write to a path whose name carries a **different date** than the current run (no overwriting past-dated archive copies).
- Manifest `targetCount` / summary counts must state the **per-type breakdown**, for example `48 targets (17 daily-brief.json)` (include classic/momentum counts the same way when reporting).

## Coordination
- Use X agent / X tools for Tier-2 analyst tape (estimate cost; keep cheap).
- Use trader agents + MCP for portfolio cards (Classic via Trader_Classic / Classic account `user-OfersClaw5`; Momentum via Trader_momentum / Momentum MCP — Momentum reporting still mirror `11630170`).
- After delivery, refresh App JSON dual-write with **both** portfolio cards when both are selected (see **Dual-write target list**); Classic card numbers must come from live Classic account (`user-OfersClaw5`), not from inventing or requiring mirror `11368142`.
- Deliver the full brief to the user (or hand off to Chief of Staff for user delivery when running in an isolated routine).

## Shared book snapshot + cards (Ofer 2026-10-18c; token saver)

Deterministic book work lives in Python: `/workspace/books/snapshot.py` (normalised cache `/workspace/books/latest/<book>.json`, history under `books/history/`) and `/workspace/books/cards.py` (card facts). Books: `classic` (user-OfersClaw5), `momentum_mirror` (mirror 11630170 in user-etoro = Momentum reporting truth), `momentum_keys` (user-Momentum-HHHGDTJ, ledger/cross-check only), `parent` (mirror 11368142, Classic copy, UI only).

1. **Check freshness first:** `cd /workspace && python3 -m books.snapshot fresh --book <book> --max-age-min <N>`. Exit 0 prints the path, so use that JSON and do not re-read. Exit 2 means stale or missing.
2. **If stale, do ONE read per book:** run `python3 -m books.snapshot agent-read-hint --book <book>`, then make exactly the MCP call(s) it prints with `write_to_file=true`. Next run `python3 -m books.snapshot ingest --book <book> --raw <file> [--raw <file2>]`. The same two user-etoro files feed both `momentum_mirror` and `parent`. If ingest refuses with `SOURCE_MISMATCH`, `MIRROR_MISSING` or `OLDER_THAN_CACHE`, that is a real data problem: stop and report it, and never hand-edit the cache.
3. **Cards:** `python3 -m books.cards --max-age-min <N> --json <out.json> --md <out.md>` gives Classic caps/core/deployable/drift/blocked/changes and Momentum stops/blocked/divergence. The LLM writes only the Buy and Sell/Rotation judgement lines (the `<LLM judgement>` placeholders) and never recomputes these facts.
4. `python3 -m books.snapshot overlap` lists cross-book symbols and keys-vs-mirror divergence.

The snapshot never changes trading rules. Caps and floors are imported from `classic_rsi` and are not redefined.

**Brief usage:** take portfolio numbers from fresh snapshots (`classic`, `momentum_mirror`; ≤60 min, or the weekend SHORT reuse rule). Only stale books get one live read via the hint, then `ingest`. `write_targets.py` does this itself: `snapshot` checks books first and then the legacy sidecars, and `write_all` attaches `books.cards` facts and the App `card` automatically when the snapshot `read_at` falls within [asOf−120 min, asOf+15 min] (manifest `cardSource`). `python3 write_targets.py cards --asof <ISO>` prints the markdown block to paste into the brief's Classic/Momentum Recommendation sections. Fill only the Buy and Sell lines. Outside that window the legacy sidecar card is used (fallback).

## Market data + QA scripted (2026-10-18e; Ofer rule 2026-10-18: anything deterministic runs in code; the LLM does judgement + prose only)
- **Numbers come from code:** `cd /workspace && python3 daily-brief/market_data.py --slot 0530|1530 --out daily-brief/raw/market-<slot>-<date>.json`. It fetches CNN graphdata (score, rating, previous close/week/month/year, all 7 components with English labels), WTI/gold/silver (last, prevClose, day %), SPY/QQQ/^VIX/COIN/HOOD and BTC/ETH/SOL (CoinGecko). Exit 0 = all ok, 3 = partial (entries in `status` that are not "ok" say what is missing: fetch only those by tool/web search), 1 = none (fall back to the old tool flow).
- Copy the numbers verbatim into the brief and payload. **The LLM only writes** the `call` per commodity, the crypto `stance`, the headlines/catalysts judgement and the prose. Do not refetch F&G/commodities/crypto when the script returned them.
- **QA from code:** after `write_targets.write_all`, run `python3 -m qa_gates daily-brief --manifest <manifestPath>`. It checks the exact target set, sha per copy, App reader (node), asOf/slot, portfolio order + mirror ids, F&G range + 7 components, the brief sha and the Source line. Exit 1 = FAIL → fix and rewrite; the LLM judges soft flags only.

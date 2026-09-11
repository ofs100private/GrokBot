---
name: Trading self-improvement loop
description: >-
  use this when reviewing fills, QA packs, daily_brief outcomes, X tape, or
  TradingView graphs to score decisions and upgrade the trading playbook after
  each position
---
# Trading self-improvement loop

Continuous learning playbook for any real-money trading agent. Goal: every question, answer, order, market regime, X post, daily_brief signal, and TradingView graph either **raises edge** or is recorded as **avoid**. Mechanism improves after **every** open, hold, and close — not only on big wins/losses.

**Principles (Claude + Grok best practice)**
- Evidence over vibes. Score only what you can cite (artifact path, orderId, brief slot, chart URL, post id).
- One lesson per decision. Prefer a sharp avoid/keep rule over a long narrative.
- Net edge after fees, spread, overnight, and tax haircut — never celebrate gross P&L.
- Momentum is **pre-identified** (heatmap + sector ETF + tape) before size, not rationalized after.
- Never invent numbers. If a source is missing, mark `unknown` and fail that score dimension.
- Secrets stay redacted. Never store tokens, keys, or cookies in lesson files.

---

## When to run

| Trigger | Cadence |
| --- | --- |
| Post-fill / post-close QA audit | Every execution |
| QA FAIL or suspended PASS | Immediately |
| `daily_brief` delivered (morning / afternoon / weekend) | Each slot |
| Regime change (event-vol, risk-on/off) | When classified |
| Weekly rollup | Once per week (user TZ) |
| User asks “what did we learn?” | On demand |

Do **not** place or resize as part of this skill. Learning is read → score → write lesson → optionally patch strategy skill. Execution stays behind the normal QA → auth → place path.

---

## Inputs (read all that exist)

Collect a **case folder** for the review window (one fill, one day, or one week). Prefer live tools + files over memory alone.

1. **Trade / QA audits**
   - Pre-place packs, prepare snapshots, `getCost` / fee previews
   - QA PASS / FAIL / HOLD / suspended verdicts and reasons
   - Post-fill audits (fill vs prepare, fees, cash left, orderId / positionId)
   - Agent chat / CoS notes that changed auth or HOLD
2. **Platform telemetry (optional context only)**
   - `audit.jsonl` under the trader / QA / account agents — tool calls, MCP status, browser navigations
   - Use to explain *process* failures (wrong ledger, missing getCost, heatmap blank). Do not treat shell noise as alpha.
3. **`daily_brief` artifacts**
   - Latest brief JSON / markdown, Fear & Greed + 7 components, Daily Signals buy/sell, portfolio recommendation card
   - Schema fields: `slot`, `fearAndGreed`, `components`, `dailySignals`, `portfolios`, `source`
4. **Market condition pack**
   - Regime label (event-vol / risk-on / risk-off / sideways)
   - Event calendar (±48h CPI / FOMC / NFP / earnings)
   - Index refs (SPX / QQQ) day% and week% when available
5. **X tape**
   - Tier-1 / Tier-2 posts used in the thesis (handle, timestamp, 1-line claim, link/id)
   - Note cost of the search; discard stale or duplicated noise
6. **TradingView / asset graphs**
   - SPX500 heatmap with **Change 1D** (`blockColor=change`), market-cap blocks, sector grouping
   - Per-asset charts used for entry (timeframe, key levels, relative vs sector ETF)
   - Screenshot path or exact URL; if tiles blank → eToro batch quotes + sector ETFs as fallback (record the fallback)

---

## Case schema (write one JSON or markdown per review)

Save under a durable lessons store (example: `/workspace/trading-lessons/YYYY-MM-DD/<case-id>.json`). One case per decision unit.

```json
{
  "schemaVersion": "1.0",
  "caseId": "YYYYMMDD-symbol-side",
  "asOf": "ISO-8601",
  "portfolio": "<agent-portfolio-key>",
  "position": {
    "symbol": "",
    "instrumentId": null,
    "side": "buy|sell-close|hold|skipped",
    "sizeUsd": null,
    "leverage": 1,
    "orderId": null,
    "positionId": null
  },
  "sources": {
    "qaPack": "",
    "fillAudit": "",
    "dailyBrief": "",
    "heatmapUrlOrShot": "",
    "xPosts": [],
    "auditJsonlWindow": ""
  },
  "scores": {},
  "momentumPreId": {},
  "lessons": [],
  "playbookPatches": []
}
```

---

## Scoring rubric (0–5 each; write 1 sentence evidence)

Score **every** dimension that applies. Use `n/a` only if truly out of scope. Average → `caseScore` (0–5).

| Dimension | 5 = excellent | 0 = fail / avoid |
| --- | --- | --- |
| **Q — Question quality** | Clear decision question (add / trim / hold / skip) tied to mandate + beat-benchmark net | Vague “feels bullish”; no cash/fee constraint |
| **A — Answer / thesis** | One falsifiable reason; cites heatmap **or** tape **or** brief component | Narrative after the fact; ignores fees/tax |
| **O — Order quality** | Matches prepare; lev=1; long-only; cash floor; fees estimated via getCost; QA PASS then place | Wrong ledger, crypto, lev≠1, missing fees, place without PASS, duplicate pending |
| **M — Market condition** | Regime correctly labeled; event window respected; index context noted | Sized into event-vol freeze; ignored risk-off tape |
| **X — X post use** | Fresh Tier-1/2, cost-aware, claim checked vs price | Stale, meme, or single noisy handle as sole trigger |
| **B — daily_brief alignment** | Action maps to brief signals **or** explicit dissent with reason | Blind follow of brief buys; or ignored a hard avoid without note |
| **G — Graph / TV setup** | 1D heatmap + (when sizing) asset chart vs sector; levels recorded | Wrong interval (e.g. 1h when 1D required); blank chart ignored |
| **P — Position outcome (ex-post)** | Net after costs vs thesis horizon; vs SPX/sleeve over same window | Gross-only cheerleading; no vs-benchmark |
| **C — Process / compliance** | QA gate, auth, REAL route, no secret leaks | HOLD breach, demo, secret in logs |

**Grade bands**
- **4.0–5.0** Keep / amplify pattern
- **3.0–3.9** Keep with patch
- **2.0–2.9** Caution — write avoid rule
- **0–1.9** Hard avoid — patch strategy skill before similar size

---

## Pre-identify momentum (before next size)

Run this checklist and store under `momentumPreId` so future cases can judge whether momentum was seen **early enough**.

1. **Sector first:** SPX heatmap Change 1D — list top 2 hot and top 2 cold sectors by block color / breadth.
2. **Sleeve ETF confirm:** Map sector → liquid ETF (examples: XLK, XLF, XLV, XLE, XLI, XLB, XLU, XLP, XLY, XLRE, QQQ, SMH). Prefer confirmation when sector ETF day% agrees with heatmap.
3. **Asset relative strength:** Candidate day%/week% vs its sector ETF and vs SPX. Prefer RS leaders in hot sectors or quality dips in held winners — not laggards in cold sectors unless thesis is mean-reversion with tight risk.
4. **Tape corroboration:** One Tier-1 event **or** Tier-2 flow/theme that matches the sector move. No tape → lower X score; do not invent.
5. **Brief bridge:** Note which `daily_brief` Daily Signal or F&G component supports / contradicts.
6. **Avoid flags (any one → default skip):** parabolic 1D chase into event-vol; heatmap+ETF conflict unresolved; fee/tax edge &lt; round-trip cost; breaks name/sleeve/cash caps; crypto / short / lev≠1.

Output a one-liner:  
`MOMENTUM: <sector> hot|cold | ETF <sym> % | asset RS vs ETF | brief: agree|dissent | action: add|trim|hold|skip`

---

## Link actions ↔ daily_brief ↔ graphs

For each scored action, fill this mapping table in the case write-up:

| Action | daily_brief hook | TV / graph hook | Next mechanism change |
| --- | --- | --- | --- |
| Buy / add | Which Daily Signal or portfolio Buy line? | Heatmap sector + asset TF | Size band / sleeve priority |
| Sell / close | Which Sell/avoid or risk note? | Breakdown vs sector ETF | Exit rule / stop hygiene |
| Hold / skip | “No Buy Today” or event freeze? | Mixed 1D colors / event vol | Cash as position |
| Brief dissent | Explicit override reason | Chart shows different RS | Document override policy |

If the brief said Buy X and we skipped (or vice versa), score **B** honestly and write a lesson either way.

---

## Per-position continuous improvement

After **every** position event (open, add, trim, full close, or deliberate skip):

1. Score the case (rubric above).
2. Write **≤3 lessons**, each tagged:
   - `KEEP` — repeatable edge
   - `AVOID` — do not repeat
   - `WATCH` — needs more samples
3. Update running tallies (in lessons index):
   - Win rate **net** of fees by sleeve
   - Avg edge vs SPX over holding window
   - Top avoid reasons (missing getCost, wrong TV interval, event freeze breach, brief-blind chase, …)
4. If `caseScore &lt; 3.0` **or** hard compliance fail → propose a concrete patch to the active strategy skill (one bullet). Apply only when the user/trader agent owns that skill; otherwise file the patch as a suggestion.
5. Feed forward: next research loop must read the latest `AVOID`/`KEEP` list before proposing size.

---

## Weekly rollup (best practice)

1. Aggregate cases for the week.
2. Rank sleeves by net contribution vs SPX.
3. List top 5 AVOID and top 5 KEEP.
4. Momentum hit-rate: % of adds where heatmap+ETF agreed **before** entry.
5. Brief fidelity: % of actions aligned with daily_brief vs profitable dissent.
6. Process debt: QA FAILs, suspended PASSes, wrong-ledger incidents, blank heatmaps.
7. Deliver a short report to the user / Chief of Staff: what improved, what to avoid next week, one playbook patch.

---

## Output template (user-facing, short)

```
Self-improve | <date> | <caseId>
Scores: Q_ A_ O_ M_ X_ B_ G_ P_ C_ → case _
Momentum pre-id: …
KEEP: …
AVOID: …
Playbook patch: … | none
```

---

## Do not

- Treat `audit.jsonl` tool spam as market signal
- Grade on gross P&L or ignore fees/tax
- Retrofit momentum after a winner (“I knew it”)
- Store secrets or raw tokens in lessons
- Auto-place from a lesson or brief
- Use 1h heatmap coloring when 1D was the standard
- Let one bad/good anecdote overwrite caps or mandate

---

## Related skills (compose, don’t duplicate)

- Run the portfolio’s **strategy** skill for mandate / research loop / place path
- Run **daily-trading-momentum-brief** when producing or judging brief-linked actions
- Run the portfolio’s **order QA gate** for PASS/FAIL evidence before scoring order quality
- Read the **X MCP guide** before any paid X pull used in a case

---

## Success criteria

A run of this skill is done only when: (1) sources listed, (2) all applicable scores filled with evidence, (3) momentum pre-id one-liner written, (4) ≥1 KEEP or AVOID lesson saved, (5) forward hook stated for the next daily research loop.

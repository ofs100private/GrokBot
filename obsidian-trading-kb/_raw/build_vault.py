#!/usr/bin/env python3
"""Rebuild Obsidian trading KB per QA FAIL fixes (CLOSED_MOVE_MISMATCH, MISSING_70K_PLAN, MISSING_LEDGER_TAGS, MISSING_NOTES)."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path("/workspace/obsidian-trading-kb")
RAW = ROOT / "_raw"
IL = timezone(timedelta(hours=3))
CLAIMS: list[dict] = []

# Exact ledger tag vocabulary required by QA
LEDGER_MIRROR_A = "mirror-A"
LEDGER_KEYS_B = "keys-B"


def claim(figure, value, source, note="", ledger=""):
    CLAIMS.append(
        {
            "figure": figure,
            "value": value,
            "source": source,
            "ledger": ledger,
            "note": note,
        }
    )


def fl(net_profit, fees) -> float:
    return round(float(net_profit) - float(fees), 2)


def to_idt(iso: str | None) -> str:
    if not iso:
        return ""
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IL).strftime("%Y-%m-%d %H:%M IDT")


def money(x) -> str:
    v = float(x)
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def pct(x) -> str:
    return f"{float(x):.1f}%"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def fm(**kwargs) -> str:
    """YAML frontmatter. Always includes ledger tag mirror-A | keys-B."""
    lines = ["---"]
    for k, v in kwargs.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{k}: [{', '.join(json.dumps(x) if not isinstance(x, str) else json.dumps(x) for x in v)}]")
            # simpler list of strings:
            if all(isinstance(x, str) for x in v):
                lines[-1] = f"{k}: [{', '.join(x for x in v)}]"
        else:
            # quote strings with special chars
            s = str(v)
            if any(c in s for c in ':#{}[]&*?|>!%@`'):
                lines.append(f'{k}: "{s}"')
            else:
                lines.append(f"{k}: {s}")
    lines.append("---\n")
    return "\n".join(lines)


def load_json(name):
    return json.loads((RAW / name).read_text())


def main():
    # Ensure CSV is correctly named (keys-B, never Mirror A)
    old = RAW / "classic-mirror-closed-trades.csv"
    new = RAW / "classic-keys-B-closed-trades.csv"
    if old.exists() and not new.exists():
        old.rename(new)
    if old.exists() and new.exists():
        old.unlink()
    write(
        RAW / "LEDGER-README.txt",
        "classic-keys-B-closed-trades.csv = OfersClaw5 keys-B execution history. "
        "NOT Mirror A 11368142. Classic Mirror A closed moves = parent-etoro-closed-20260501.json "
        "(prefer isMirrorTrade:true). fully_loaded = netProfit - fees.\n",
    )

    classic = load_json("classic-portfolio.json")
    momentum = load_json("momentum-portfolio.json")
    brief = load_json("daily-brief.json")
    parent = load_json("parent-etoro-closed-20260501.json")
    mom_keys = load_json("momentum-keys-closed-20260501.json")

    classic_keys_rows = list(csv.DictReader(new.open()))
    classic_keys_trades = []
    for r in classic_keys_rows:
        np_, fees = float(r["netProfit"]), float(r["fees"])
        classic_keys_trades.append(
            {
                "symbol": r["symbol"],
                "instrumentId": int(r["instrumentId"]),
                "closeTime": r["closeTime"],
                "netProfit": np_,
                "fees": fees,
                "fullyLoaded": fl(np_, fees),
                "positionId": int(r["positionId"]),
                "investment": float(r["investment"]),
            }
        )

    mom_key_trades = []
    for t in mom_keys["trades"]:
        np_, fees = float(t["netProfit"]), float(t.get("fees") or 0)
        mom_key_trades.append({**t, "symbol": t["market"]["symbol"], "fullyLoaded": fl(np_, fees)})

    # Parent JSON = source of truth for Classic closed moves
    parent_all = []
    classic_mirror_a_closes = []  # isMirrorTrade true
    parent_personal_closes = []  # isMirrorTrade false — tag carefully
    for t in parent["trades"]:
        np_, fees = float(t["netProfit"]), float(t.get("fees") or 0)
        row = {
            **t,
            "symbol": t["market"]["symbol"],
            "fullyLoaded": fl(np_, fees),
        }
        parent_all.append(row)
        if t.get("isMirrorTrade"):
            classic_mirror_a_closes.append(row)
        else:
            parent_personal_closes.append(row)

    as_of = classic.get("asOf") or brief.get("asOf")
    slot = classic.get("slot") or brief.get("slot")
    start_capital = round(float(classic["equity"]) + float(momentum["equity"]), 2)
    assert start_capital == 20649.39, start_capital
    target_70k = 70000.0
    gap_to_70k = round(target_70k - start_capital, 2)

    # ---- claims ----
    for key, src, led in [
        ("classic.equity", classic["equity"], LEDGER_MIRROR_A),
        ("classic.cash", classic["cash"], LEDGER_MIRROR_A),
        ("classic.cashPct", classic["cashPct"], LEDGER_MIRROR_A),
        ("classic.deploymentPct", classic["deploymentPct"], LEDGER_MIRROR_A),
        ("classic.invested", classic["invested"], LEDGER_MIRROR_A),
        ("classic.openPnl", classic["openPnl"], LEDGER_MIRROR_A),
        ("classic.closedPnl", classic["closedPnl"], LEDGER_MIRROR_A),
        ("classic.mirrorId", classic["mirrorId"], LEDGER_MIRROR_A),
    ]:
        claim(key, src if key.endswith("Id") or "Pct" in key else classic[key.split(".", 1)[1]], "_raw/classic-portfolio.json", "", led)

    # fix claims properly
    CLAIMS.clear()
    claim("classic.equity", classic["equity"], "_raw/classic-portfolio.json", "Mirror A 11368142 afternoon sidecar", LEDGER_MIRROR_A)
    claim("classic.cash", classic["cash"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)
    claim("classic.openPnl", classic["openPnl"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)
    claim("classic.closedPnl", classic["closedPnl"], "_raw/classic-portfolio.json", "copiedTraders closedPnl", LEDGER_MIRROR_A)
    claim("classic.invested", classic["invested"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)
    claim("classic.mirrorId", classic["mirrorId"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)
    for p in classic["positions"]:
        claim(f"classic.pos.{p['symbol']}.pnl", p["pnl"], "_raw/classic-portfolio.json", str(p["positionId"]), LEDGER_MIRROR_A)
        claim(f"classic.pos.{p['symbol']}.invested", p["invested"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)

    claim("momentum.equity", momentum["equity"], "_raw/momentum-portfolio.json", "Mirror A 11630170 $8k", LEDGER_MIRROR_A)
    claim("momentum.cash", momentum["cash"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("momentum.openPnl", momentum["openPnl"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("momentum.closedPnl", momentum["closedPnl"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("momentum.invested", momentum["invested"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("momentum.basis", momentum["basis"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("momentum.mirrorId", momentum["mirrorId"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    for p in momentum["positions"]:
        claim(f"momentum.pos.{p['symbol']}.pnl", p["pnl"], "_raw/momentum-portfolio.json", str(p["positionId"]), LEDGER_MIRROR_A)
        claim(f"momentum.pos.{p['symbol']}.invested", p["invested"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)

    claim("plan70k.starting_capital", start_capital, "_raw/classic-portfolio.json + _raw/momentum-portfolio.json", "classic.equity + momentum.equity", LEDGER_MIRROR_A)
    claim("plan70k.classic_component", classic["equity"], "_raw/classic-portfolio.json", "", LEDGER_MIRROR_A)
    claim("plan70k.momentum_component", momentum["equity"], "_raw/momentum-portfolio.json", "", LEDGER_MIRROR_A)
    claim("plan70k.target", target_70k, "01-Plan-70k.md", "plan target not a live book figure", LEDGER_MIRROR_A)
    claim("plan70k.gap", gap_to_70k, "01-Plan-70k.md", "70000 - starting_capital", LEDGER_MIRROR_A)

    c_np = round(sum(t["netProfit"] for t in classic_keys_trades), 2)
    c_fees = round(sum(t["fees"] for t in classic_keys_trades), 2)
    c_fl = round(sum(t["fullyLoaded"] for t in classic_keys_trades), 2)
    claim("classic_keysB.trade_count", len(classic_keys_trades), "_raw/classic-keys-B-closed-trades.csv", "NOT Mirror A", LEDGER_KEYS_B)
    claim("classic_keysB.sum_netProfit", c_np, "_raw/classic-keys-B-closed-trades.csv", "", LEDGER_KEYS_B)
    claim("classic_keysB.sum_fees", c_fees, "_raw/classic-keys-B-closed-trades.csv", "", LEDGER_KEYS_B)
    claim("classic_keysB.sum_fullyLoaded", c_fl, "_raw/classic-keys-B-closed-trades.csv", "sum(netProfit-fees)", LEDGER_KEYS_B)
    for t in classic_keys_trades:
        claim(f"classic_keysB.trade.{t['positionId']}.netProfit", t["netProfit"], "_raw/classic-keys-B-closed-trades.csv", t["symbol"], LEDGER_KEYS_B)
        claim(f"classic_keysB.trade.{t['positionId']}.fees", t["fees"], "_raw/classic-keys-B-closed-trades.csv", t["symbol"], LEDGER_KEYS_B)
        claim(f"classic_keysB.trade.{t['positionId']}.fullyLoaded", t["fullyLoaded"], "_raw/classic-keys-B-closed-trades.csv", "netProfit-fees", LEDGER_KEYS_B)

    m_np = round(sum(t["netProfit"] for t in mom_key_trades), 2)
    m_fees = round(sum(t["fees"] for t in mom_key_trades), 2)
    m_fl = round(sum(t["fullyLoaded"] for t in mom_key_trades), 2)
    claim("momentum_keysB.trade_count", len(mom_key_trades), "_raw/momentum-keys-closed-20260501.json", "", LEDGER_KEYS_B)
    claim("momentum_keysB.sum_netProfit", m_np, "_raw/momentum-keys-closed-20260501.json", "", LEDGER_KEYS_B)
    claim("momentum_keysB.sum_fees", m_fees, "_raw/momentum-keys-closed-20260501.json", "", LEDGER_KEYS_B)
    claim("momentum_keysB.sum_fullyLoaded", m_fl, "_raw/momentum-keys-closed-20260501.json", "sum(netProfit-fees)", LEDGER_KEYS_B)
    for t in mom_key_trades:
        pid = t["positionId"]
        claim(f"momentum_keysB.trade.{pid}.netProfit", t["netProfit"], "_raw/momentum-keys-closed-20260501.json", t["symbol"], LEDGER_KEYS_B)
        claim(f"momentum_keysB.trade.{pid}.fees", t["fees"], "_raw/momentum-keys-closed-20260501.json", t["symbol"], LEDGER_KEYS_B)
        claim(f"momentum_keysB.trade.{pid}.fullyLoaded", t["fullyLoaded"], "_raw/momentum-keys-closed-20260501.json", "netProfit-fees", LEDGER_KEYS_B)

    ma_np = round(sum(t["netProfit"] for t in classic_mirror_a_closes), 2)
    ma_fees = round(sum(t["fees"] for t in classic_mirror_a_closes), 2)
    ma_fl = round(sum(t["fullyLoaded"] for t in classic_mirror_a_closes), 2)
    claim("classic_mirrorA_closes.trade_count", len(classic_mirror_a_closes), "_raw/parent-etoro-closed-20260501.json", "isMirrorTrade=true (socialTradeId shared)", LEDGER_MIRROR_A)
    claim("classic_mirrorA_closes.sum_netProfit", ma_np, "_raw/parent-etoro-closed-20260501.json", "", LEDGER_MIRROR_A)
    claim("classic_mirrorA_closes.sum_fees", ma_fees, "_raw/parent-etoro-closed-20260501.json", "", LEDGER_MIRROR_A)
    claim("classic_mirrorA_closes.sum_fullyLoaded", ma_fl, "_raw/parent-etoro-closed-20260501.json", "sum(netProfit-fees)", LEDGER_MIRROR_A)
    for t in classic_mirror_a_closes:
        pid = t["positionId"]
        claim(f"classic_mirrorA_closes.trade.{pid}.netProfit", t["netProfit"], "_raw/parent-etoro-closed-20260501.json", t["symbol"], LEDGER_MIRROR_A)
        claim(f"classic_mirrorA_closes.trade.{pid}.fees", t["fees"], "_raw/parent-etoro-closed-20260501.json", t["symbol"], LEDGER_MIRROR_A)
        claim(f"classic_mirrorA_closes.trade.{pid}.fullyLoaded", t["fullyLoaded"], "_raw/parent-etoro-closed-20260501.json", "netProfit-fees", LEDGER_MIRROR_A)

    # Parent personal (ambiguous vs Classic) — still from parent JSON; ledger tagged parent-SSO but claims note ambiguity. For QA ledger vocab use keys-B? No — they're not keys-B. Tag as mirror-A source file but ledger_note parent-personal.
    # Steering: tag ledger carefully. Use ledger field parent-SSO in notes; for required tags include a ledger line. QA required_tags are mirror-A | keys-B. Parent personal gets ledger: parent-SSO AND tags include neither exclusively — I'll use ledger: parent-SSO with secondary_tag clarifying, and also put `ledger_family: parent` .
    # Actually for "every note" to have mirror-A | keys-B, parent personal notes should still declare they are NOT classic keys-B reporting. I'll use: ledger: parent-SSO + related_ledger_note. And put in tags: [trade, parent] without forcing wrong mirror-A.
    # Re-read: "Generate ALL .md move notes with ledger tags on every note (mirror-A | keys-B)."
    # So every MOVE note must be one of those two. Parent personal non-mirror → not Classic Mirror A closes. They shouldn't be Classic move notes.
    # Classic CLOSED moves ONLY from parent JSON preferring isMirrorTrade.
    # So Classic closed move notes = 79 isMirrorTrade. Parent personal = separate with careful tag.
    # For parent personal I'll use ledger: parent-SSO and also add `qa_ledger_bucket: parent-SSO` — if QA requires strictly two values, document in README.

    pp_np = round(sum(t["netProfit"] for t in parent_personal_closes), 2)
    pp_fees = round(sum(t["fees"] for t in parent_personal_closes), 2)
    pp_fl = round(sum(t["fullyLoaded"] for t in parent_personal_closes), 2)
    claim("parent_personal.trade_count", len(parent_personal_closes), "_raw/parent-etoro-closed-20260501.json", "isMirrorTrade=false — NOT Classic Mirror A book", "parent-SSO")
    claim("parent_personal.sum_netProfit", pp_np, "_raw/parent-etoro-closed-20260501.json", "", "parent-SSO")
    claim("parent_personal.sum_fees", pp_fees, "_raw/parent-etoro-closed-20260501.json", "", "parent-SSO")
    claim("parent_personal.sum_fullyLoaded", pp_fl, "_raw/parent-etoro-closed-20260501.json", "sum(netProfit-fees)", "parent-SSO")
    for t in parent_personal_closes:
        pid = t["positionId"]
        claim(f"parent_personal.trade.{pid}.netProfit", t["netProfit"], "_raw/parent-etoro-closed-20260501.json", t["symbol"], "parent-SSO")
        claim(f"parent_personal.trade.{pid}.fees", t["fees"], "_raw/parent-etoro-closed-20260501.json", t["symbol"], "parent-SSO")
        claim(f"parent_personal.trade.{pid}.fullyLoaded", t["fullyLoaded"], "_raw/parent-etoro-closed-20260501.json", "netProfit-fees", "parent-SSO")

    fg = brief.get("fearAndGreed") or {}
    claim("brief.fearAndGreed.score", fg.get("score"), "_raw/daily-brief.json", fg.get("rating", ""), "market")

    # ========== STRUCTURE ==========
    dirs = [
        "Indexes",
        "Ledgers",
        "Portfolios",
        "Positions/Classic",
        "Positions/Momentum",
        "Trades/Classic-mirror-A",
        "Trades/Classic-keys-B",
        "Trades/Momentum-keys-B",
        "Trades/Parent-personal",
        "Symbols",
        "Analytics",
        "Daily-Briefs",
        "Journals",
        "Playbooks",
        "Feedback",
        "Plans",
    ]
    for d in dirs:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

    # README
    write(
        ROOT / "README.md",
        fm(
            tags=["index", "readme"],
            ledger=LEDGER_MIRROR_A,
            asOf=as_of,
            slot=slot,
        )
        + f"""# Obsidian Trading KB

Vault for Ofer Sasson trading books. Times in **Asia/Jerusalem (IDT)**.

## Ledger rules

| Tag | Meaning |
|-----|---------|
| `{LEDGER_MIRROR_A}` | Classic Mirror A `11368142` or Momentum Mirror A `11630170` reporting truth |
| `{LEDGER_KEYS_B}` | Execution keys books — move notes only; **never** equity/cash totals |
| `parent-SSO` | Parent personal closes (`isMirrorTrade:false`) — not Classic/Momentum book |

**REJECT** `user-OfersClaw5` / Momentum keys MCP equity as Classic or Momentum reporting.

**Classic CLOSED moves** = `_raw/parent-etoro-closed-20260501.json` (prefer `isMirrorTrade:true`).  
**NOT** `_raw/classic-keys-B-closed-trades.csv` (OfersClaw5 keys-B; 0 pid overlap with parent).

**fully_loaded** = `netProfit - fees` (do not invent PnL).

## Start here

- [[Home]] — dashboard
- [[01-Plan-70k]] — path from Mirror A capital **{money(start_capital)}** → $70k
- [[Indexes/MOC-Vault]] · [[Indexes/MOC-Trades]] · [[Indexes/MOC-Portfolios]]
- [[Ledgers/Ledger-Truth]]
- [[Feedback/Feedback-Loop]]
- QA pack: `_raw/qa-pack-obsidian-kb.json` → CoS asks QA Bot `498c78db-a027-4f2c-8126-3c2be6f0a4bb` to re-check

## Snapshot ({as_of})

| Book | Equity | Cash | Ledger |
|------|--------|------|--------|
| Classic A `{classic['mirrorId']}` | {money(classic['equity'])} | {money(classic['cash'])} | mirror-A |
| Momentum A `{momentum['mirrorId']}` | {money(momentum['equity'])} | {money(momentum['cash'])} | mirror-A |
| **Combined start (70k plan)** | **{money(start_capital)}** | — | mirror-A |
""",
    )

    write(
        ROOT / "Home.md",
        fm(tags=["dashboard"], ledger=LEDGER_MIRROR_A, asOf=as_of, slot=slot)
        + f"""# Trading Home

> [!warning] Ledger gate
> Equity/cash/open = **mirror-A** only. keys-B closes are labeled and never book totals.

## Market

- F&G **{fg.get('score')} — {fg.get('rating')}** · {brief.get('slotBadge','')}

## Classic · mirror-A `{classic['mirrorId']}`

Equity **{money(classic['equity'])}** · Cash **{money(classic['cash'])}** · Open {', '.join(f'[[Positions/Classic/{s}|{s}]]' for s in classic['symbols'])}

## Momentum · mirror-A `{momentum['mirrorId']}` · basis {money(momentum['basis'])}

Equity **{money(momentum['equity'])}** · Cash **{money(momentum['cash'])}** · Open {', '.join(f'[[Positions/Momentum/{s}|{s}]]' for s in momentum['symbols'])}

## Plan

[[01-Plan-70k]] — starting capital **{money(start_capital)}** (Classic A + Momentum A).

## Indexes

[[Indexes/MOC-Vault]] · [[Indexes/MOC-Trades]] · [[Indexes/MOC-Portfolios]] · [[Feedback/Feedback-Loop]]
""",
    )

    # 01-Plan-70k (also copy under Plans/)
    plan_body = f"""# Plan · $70k from Mirror A capital

## Starting capital (reporting truth)

| Component | Equity | Source | Ledger |
|-----------|--------|--------|--------|
| Classic Mirror A `{classic['mirrorId']}` | **{money(classic['equity'])}** | `_raw/classic-portfolio.json` | mirror-A |
| Momentum Mirror A `{momentum['mirrorId']}` | **{money(momentum['equity'])}** | `_raw/momentum-portfolio.json` | mirror-A |
| **Sum (start)** | **{money(start_capital)}** | classic.equity + momentum.equity | mirror-A |

```
starting_capital = 12841.61 + 7807.78 = 20649.39
```

**REJECT** keys-B equities (OfersClaw5 ~7246 / Momentum keys ~9843) in this plan.

## Target

| Item | Value |
|------|-------|
| Target | **$70,000** |
| Gap | **{money(gap_to_70k)}** |
| Multiple vs start | {round(target_70k / start_capital, 2)}× |

## Path (no invented PnL)

1. Keep Classic cash buffer discipline (mandate cash floor); grow via quality longs after QA PASS.
2. Momentum: breakout/VCP FULL AUTO after QA; protect thin cash (~{pct(momentum['cashPct'])} now).
3. Compound **only** Mirror A marked equity; never count keys-B as progress toward $70k.
4. Review weekly in [[Journals/2026-09]] + [[Feedback/Feedback-Loop]].

## As-of

Sidecar slot `{slot}` · `{as_of}`. Live marks may drift; plan baseline stays afternoon Mirror A sidecars until next vault refresh.
"""
    write(
        ROOT / "01-Plan-70k.md",
        fm(
            tags=["plan", "70k"],
            ledger=LEDGER_MIRROR_A,
            starting_capital=start_capital,
            classic_equity=classic["equity"],
            momentum_equity=momentum["equity"],
            target=70000,
            gap=gap_to_70k,
            asOf=as_of,
        )
        + plan_body,
    )
    write(
        ROOT / "Plans/01-Plan-70k.md",
        fm(tags=["plan", "70k"], ledger=LEDGER_MIRROR_A, starting_capital=start_capital, asOf=as_of)
        + plan_body
        + "\nCanonical note: [[01-Plan-70k]]\n",
    )

    # Indexes
    write(
        ROOT / "Indexes/MOC-Vault.md",
        fm(tags=["moc", "index"], ledger=LEDGER_MIRROR_A)
        + """# MOC · Vault

- [[Home]] · [[README]] · [[01-Plan-70k]]
- [[Indexes/MOC-Portfolios]] · [[Indexes/MOC-Trades]] · [[Indexes/MOC-Symbols]]
- [[Ledgers/Ledger-Truth]] · [[Feedback/Feedback-Loop]]
- [[Daily-Briefs/2026-09-30-afternoon-1530]]
- [[Playbooks/Classic-Mandate]] · [[Playbooks/Momentum-Playbook]]
""",
    )
    write(
        ROOT / "Indexes/MOC-Portfolios.md",
        fm(tags=["moc", "portfolios"], ledger=LEDGER_MIRROR_A)
        + """# MOC · Portfolios

- [[Portfolios/Classic]] — ledger `mirror-A` · 11368142
- [[Portfolios/Momentum]] — ledger `mirror-A` · 11630170 · $8k basis
- [[Portfolios/Parent-Account]] — parent SSO context (closes split mirror-A vs personal)
""",
    )
    write(
        ROOT / "Indexes/MOC-Trades.md",
        fm(tags=["moc", "trades"], ledger=LEDGER_MIRROR_A)
        + f"""# MOC · Trades

## Classic Mirror A closes (from parent JSON · `isMirrorTrade:true`)

- Folder: `Trades/Classic-mirror-A/` · **{len(classic_mirror_a_closes)}** notes · ledger `mirror-A`
- Source: `_raw/parent-etoro-closed-20260501.json`
- Summary: [[Analytics/Classic-mirror-A-Closed-Summary]]

## Classic keys-B closes (execution only)

- Folder: `Trades/Classic-keys-B/` · **{len(classic_keys_trades)}** notes · ledger `keys-B`
- Source: `_raw/classic-keys-B-closed-trades.csv` (**not** Mirror A)
- Summary: [[Analytics/Classic-keys-B-Closed-Summary]]

## Momentum keys-B closes

- Folder: `Trades/Momentum-keys-B/` · **{len(mom_key_trades)}** notes · ledger `keys-B`
- [[Analytics/Momentum-keys-B-Closed-Summary]]

## Parent personal (`isMirrorTrade:false`)

- Folder: `Trades/Parent-personal/` · **{len(parent_personal_closes)}** notes · ledger `parent-SSO`
- Not Classic/Momentum reporting books
""",
    )
    write(
        ROOT / "Indexes/MOC-Symbols.md",
        fm(tags=["moc", "symbols"], ledger=LEDGER_MIRROR_A)
        + """# MOC · Symbols

See [[Symbols/_MOC-Symbols]] for the full list.
""",
    )

    # Feedback loop
    write(
        ROOT / "Feedback/Feedback-Loop.md",
        fm(tags=["feedback", "qa"], ledger=LEDGER_MIRROR_A, asOf=as_of)
        + f"""# Feedback loop

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
- Plan baseline capital: **{money(start_capital)}** → see [[01-Plan-70k]]
""",
    )

    write(
        ROOT / "Ledgers/Ledger-Truth.md",
        fm(tags=["ledger", "policy"], ledger=LEDGER_MIRROR_A, asOf=as_of)
        + f"""# Ledger Truth

## Classic

- **Open / equity / cash:** Mirror A `{classic['mirrorId']}` ← `_raw/classic-portfolio.json` · tag `{LEDGER_MIRROR_A}`
- **Closed moves (Mirror A truth):** `_raw/parent-etoro-closed-20260501.json` where `isMirrorTrade:true` ({len(classic_mirror_a_closes)} rows) · tag `{LEDGER_MIRROR_A}`
- **Execution closes:** `_raw/classic-keys-B-closed-trades.csv` · tag `{LEDGER_KEYS_B}` · **never** call Mirror A
- **REJECT:** user-OfersClaw5 keys equity/cash as Classic

## Momentum

- **Open / equity / cash:** Mirror A `{momentum['mirrorId']}` $8k ← `_raw/momentum-portfolio.json` · `{LEDGER_MIRROR_A}`
- **Execution closes:** `_raw/momentum-keys-closed-20260501.json` · `{LEDGER_KEYS_B}`
- **REJECT:** Momentum keys MCP ~$10k shape as allocation

## PnL

```
fully_loaded = netProfit - fees
```
""",
    )

    # Portfolios
    pos_rows = "\n".join(
        f"| [[Positions/Classic/{p['symbol']}\\|{p['symbol']}]] | {p['positionId']} | {money(p['invested'])} | {money(p['pnl'])} | {pct(p['pnlPercent'])} |"
        for p in classic["positions"]
    )
    write(
        ROOT / "Portfolios/Classic.md",
        fm(
            tags=["portfolio", "classic"],
            ledger=LEDGER_MIRROR_A,
            mirrorId=classic["mirrorId"],
            equity=classic["equity"],
            cash=classic["cash"],
            openPnl=classic["openPnl"],
            closedPnl=classic["closedPnl"],
            asOf=as_of,
            source="_raw/classic-portfolio.json",
        )
        + f"""# Classic · Mirror A {classic['mirrorId']}

ledger: **mirror-A** · REJECT keys-B totals.

| Metric | Value |
|--------|-------|
| Equity | {money(classic['equity'])} |
| Cash | {money(classic['cash'])} ({pct(classic['cashPct'])}) |
| Open PnL | {money(classic['openPnl'])} |
| Closed PnL (copiedTraders) | {money(classic['closedPnl'])} |
| Invested | {money(classic['invested'])} |
| Names | {', '.join(classic['symbols'])} |
| Absent | {', '.join(classic.get('absent') or [])} |

## Open (Mirror A)

| Symbol | Pos | Invested | PnL | % |
|--------|-----|----------|-----|---|
{pos_rows}

Closed moves: [[Analytics/Classic-mirror-A-Closed-Summary]] (parent JSON) · keys-B execution: [[Analytics/Classic-keys-B-Closed-Summary]]
""",
    )

    mpos_rows = "\n".join(
        f"| [[Positions/Momentum/{p['symbol']}\\|{p['symbol']}]] | {p['positionId']} | {money(p['invested'])} | {money(p['pnl'])} | {pct(p['pnlPercent'])} | {p.get('stopLossRate','')} |"
        for p in momentum["positions"]
    )
    write(
        ROOT / "Portfolios/Momentum.md",
        fm(
            tags=["portfolio", "momentum"],
            ledger=LEDGER_MIRROR_A,
            mirrorId=momentum["mirrorId"],
            basis=momentum["basis"],
            equity=momentum["equity"],
            cash=momentum["cash"],
            openPnl=momentum["openPnl"],
            closedPnl=momentum["closedPnl"],
            asOf=as_of,
            source="_raw/momentum-portfolio.json",
        )
        + f"""# Momentum · Mirror A {momentum['mirrorId']} · $8k basis

ledger: **mirror-A** · REJECT keys-B ~$10k shape.

| Metric | Value |
|--------|-------|
| Equity | {money(momentum['equity'])} |
| Cash | {money(momentum['cash'])} ({pct(momentum['cashPct'])}) |
| Open / Closed PnL | {money(momentum['openPnl'])} / {money(momentum['closedPnl'])} |
| Basis / Invested | {money(momentum['basis'])} / {money(momentum['invested'])} |
| Names | {', '.join(momentum['symbols'])} |

## Open (Mirror A)

| Symbol | Pos | Invested | PnL | % | SL |
|--------|-----|----------|-----|---|----|
{mpos_rows}

keys-B moves: [[Analytics/Momentum-keys-B-Closed-Summary]]
""",
    )

    write(
        ROOT / "Portfolios/Parent-Account.md",
        fm(
            tags=["portfolio", "parent"],
            ledger=LEDGER_MIRROR_A,
            note="Parent SSO is the feed for Classic mirror-A closes; personal rows tagged parent-SSO",
            mirrorCloses=len(classic_mirror_a_closes),
            personalCloses=len(parent_personal_closes),
            source="_raw/parent-etoro-closed-20260501.json",
        )
        + f"""# Parent eToro SSO

Source file for **Classic Mirror A closed moves** (`isMirrorTrade:true`, n={len(classic_mirror_a_closes)}).

| Slice | n | Σ netProfit | Σ fully_loaded | Ledger tag |
|-------|---|-------------|----------------|------------|
| Mirror trades | {len(classic_mirror_a_closes)} | {money(ma_np)} | {money(ma_fl)} | mirror-A |
| Personal (`isMirrorTrade:false`) | {len(parent_personal_closes)} | {money(pp_np)} | {money(pp_fl)} | parent-SSO |

socialTradeId on mirror rows: `{Counter(t.get('socialTradeId') for t in classic_mirror_a_closes).most_common(1)[0][0] if classic_mirror_a_closes else 'n/a'}` (ambiguous vs numeric mirrorId 11368142 — tagged mirror-A per QA: parent JSON is Classic close truth; filter `isMirrorTrade`).
""",
    )

    # Open positions
    for p in classic["positions"]:
        write(
            ROOT / f"Positions/Classic/{p['symbol']}.md",
            fm(
                tags=["position", "classic", "open"],
                ledger=LEDGER_MIRROR_A,
                symbol=p["symbol"],
                positionId=p["positionId"],
                invested=p["invested"],
                pnl=p["pnl"],
                asOf=as_of,
                source="_raw/classic-portfolio.json",
            )
            + f"""# {p['symbol']} · Classic open · mirror-A

| Field | Value |
|-------|-------|
| Position | `{p['positionId']}` |
| Invested | {money(p['invested'])} |
| Units | {p['units']} |
| Open → Mark | {p['openRate']} → {p['currentRate']} |
| Open PnL | **{money(p['pnl'])}** ({pct(p['pnlPercent'])}) |

[[Portfolios/Classic]] · [[Symbols/{p['symbol']}]]
""",
        )

    for p in momentum["positions"]:
        write(
            ROOT / f"Positions/Momentum/{p['symbol']}.md",
            fm(
                tags=["position", "momentum", "open"],
                ledger=LEDGER_MIRROR_A,
                symbol=p["symbol"],
                positionId=p["positionId"],
                invested=p["invested"],
                pnl=p["pnl"],
                asOf=as_of,
                source="_raw/momentum-portfolio.json",
            )
            + f"""# {p['symbol']} · Momentum open · mirror-A

| Field | Value |
|-------|-------|
| Position | `{p['positionId']}` |
| Invested | {money(p['invested'])} |
| Units | {p['units']} |
| Open → Mark | {p['openRate']} → {p['currentRate']} |
| SL | {p.get('stopLossRate','')} |
| Open PnL | **{money(p['pnl'])}** ({pct(p['pnlPercent'])}) |

[[Portfolios/Momentum]] · [[Symbols/{p['symbol']}]]
""",
        )

    # Classic Mirror A closed move notes (from parent isMirrorTrade)
    for t in classic_mirror_a_closes:
        sym, pid = t["symbol"], t["positionId"]
        write(
            ROOT / f"Trades/Classic-mirror-A/{sym}-{pid}.md",
            fm(
                tags=["trade", "classic", "closed", "move"],
                ledger=LEDGER_MIRROR_A,
                isMirrorTrade=True,
                socialTradeId=t.get("socialTradeId"),
                parentPositionId=t.get("parentPositionId"),
                symbol=sym,
                positionId=pid,
                netProfit=t["netProfit"],
                fees=t["fees"],
                fullyLoaded=t["fullyLoaded"],
                closeTime=t["closeTime"],
                source="_raw/parent-etoro-closed-20260501.json",
            )
            + f"""# {sym} · Classic closed move · mirror-A `{pid}`

> Source: parent SSO JSON · `isMirrorTrade:true` · Classic Mirror A closed-move truth (not keys-B CSV).

| Field | Value |
|-------|-------|
| socialTradeId | {t.get('socialTradeId')} |
| parentPositionId | {t.get('parentPositionId')} |
| Open → Close | {t.get('openRate')} → {t.get('closeRate')} |
| Close IDT | {to_idt(t['closeTime'])} |
| Investment | {money(t.get('investment'))} |
| netProfit | {money(t['netProfit'])} |
| fees | {money(t['fees'])} |
| **fully_loaded** | **{money(t['fullyLoaded'])}** (`netProfit - fees`) |

[[Symbols/{sym}]] · [[Analytics/Classic-mirror-A-Closed-Summary]]
""",
        )

    # Classic keys-B (never Mirror A)
    for t in classic_keys_trades:
        sym, pid = t["symbol"], t["positionId"]
        write(
            ROOT / f"Trades/Classic-keys-B/{sym}-{pid}.md",
            fm(
                tags=["trade", "classic", "closed", "move"],
                ledger=LEDGER_KEYS_B,
                book="OfersClaw5-keys-B",
                symbol=sym,
                positionId=pid,
                netProfit=t["netProfit"],
                fees=t["fees"],
                fullyLoaded=t["fullyLoaded"],
                closeTime=t["closeTime"],
                source="_raw/classic-keys-B-closed-trades.csv",
            )
            + f"""# {sym} · Classic execution close · keys-B `{pid}`

> [!caution] ledger=keys-B
> From `_raw/classic-keys-B-closed-trades.csv` (OfersClaw5). **Not** Mirror A 11368142. 0 pid overlap with parent mirror closes.

| Field | Value |
|-------|-------|
| Close IDT | {to_idt(t['closeTime'])} |
| Investment | {money(t['investment'])} |
| netProfit | {money(t['netProfit'])} |
| fees | {money(t['fees'])} |
| **fully_loaded** | **{money(t['fullyLoaded'])}** |

[[Symbols/{sym}]] · [[Analytics/Classic-keys-B-Closed-Summary]]
""",
        )

    for t in mom_key_trades:
        sym, pid = t["symbol"], t["positionId"]
        write(
            ROOT / f"Trades/Momentum-keys-B/{sym}-{pid}.md",
            fm(
                tags=["trade", "momentum", "closed", "move"],
                ledger=LEDGER_KEYS_B,
                book="Momentum-HHHGDTJ-keys-B",
                symbol=sym,
                positionId=pid,
                netProfit=t["netProfit"],
                fees=t["fees"],
                fullyLoaded=t["fullyLoaded"],
                closeTime=t["closeTime"],
                source="_raw/momentum-keys-closed-20260501.json",
            )
            + f"""# {sym} · Momentum execution close · keys-B `{pid}`

> ledger=keys-B · Mirror A equity truth remains [[Portfolios/Momentum]].

| Field | Value |
|-------|-------|
| Open → Close | {t.get('openRate')} → {t.get('closeRate')} |
| Close IDT | {to_idt(t['closeTime'])} |
| Investment | {money(t.get('investment'))} |
| netProfit | {money(t['netProfit'])} |
| fees | {money(t['fees'])} |
| **fully_loaded** | **{money(t['fullyLoaded'])}** |

[[Symbols/{sym}]] · [[Analytics/Momentum-keys-B-Closed-Summary]]
""",
        )

    for t in parent_personal_closes:
        sym, pid = t["symbol"], t["positionId"]
        # Careful tag: not Classic mirror-A; not keys-B. Use parent-SSO; also set ledger_ambiguous note.
        write(
            ROOT / f"Trades/Parent-personal/{sym}-{pid}.md",
            fm(
                tags=["trade", "parent", "closed", "move"],
                ledger="parent-SSO",
                isMirrorTrade=False,
                symbol=sym,
                positionId=pid,
                netProfit=t["netProfit"],
                fees=t["fees"],
                fullyLoaded=t["fullyLoaded"],
                closeTime=t["closeTime"],
                source="_raw/parent-etoro-closed-20260501.json",
                note="isMirrorTrade=false — not Classic Mirror A closed-move set",
            )
            + f"""# {sym} · Parent personal close `{pid}`

> [!info] ledger=parent-SSO
> From parent JSON with `isMirrorTrade:false`. **Not** counted as Classic Mirror A closed moves (those are `isMirrorTrade:true`).

| Field | Value |
|-------|-------|
| Open → Close | {t.get('openRate')} → {t.get('closeRate')} |
| Close IDT | {to_idt(t['closeTime'])} |
| Investment | {money(t.get('investment'))} |
| netProfit | {money(t['netProfit'])} |
| fees | {money(t['fees'])} |
| **fully_loaded** | **{money(t['fullyLoaded'])}** |

[[Symbols/{sym}]]
""",
        )

    # Analytics
    top_ma = Counter(t["symbol"] for t in classic_mirror_a_closes).most_common(20)
    write(
        ROOT / "Analytics/Classic-mirror-A-Closed-Summary.md",
        fm(
            tags=["analytics", "classic"],
            ledger=LEDGER_MIRROR_A,
            tradeCount=len(classic_mirror_a_closes),
            sumNetProfit=ma_np,
            sumFees=ma_fees,
            sumFullyLoaded=ma_fl,
            source="_raw/parent-etoro-closed-20260501.json",
        )
        + f"""# Classic Mirror A closed summary

Source: parent SSO `_raw/parent-etoro-closed-20260501.json` filtered `isMirrorTrade:true` (n={len(classic_mirror_a_closes)}).

| Aggregate | Value |
|-----------|-------|
| Σ netProfit | {money(ma_np)} |
| Σ fees | {money(ma_fees)} |
| Σ fully_loaded | {money(ma_fl)} |

| Symbol | n | Σ net | Σ fully_loaded |
|--------|---|-------|----------------|
{chr(10).join(f"| [[Symbols/{s}\\|{s}]] | {n} | {money(round(sum(t['netProfit'] for t in classic_mirror_a_closes if t['symbol']==s),2))} | {money(round(sum(t['fullyLoaded'] for t in classic_mirror_a_closes if t['symbol']==s),2))} |" for s,n in top_ma)}

Notes under `Trades/Classic-mirror-A/`.
""",
    )

    top_ck = Counter(t["symbol"] for t in classic_keys_trades).most_common(15)
    write(
        ROOT / "Analytics/Classic-keys-B-Closed-Summary.md",
        fm(
            tags=["analytics", "classic", "keys-B"],
            ledger=LEDGER_KEYS_B,
            tradeCount=len(classic_keys_trades),
            sumNetProfit=c_np,
            sumFees=c_fees,
            sumFullyLoaded=c_fl,
            source="_raw/classic-keys-B-closed-trades.csv",
        )
        + f"""# Classic keys-B closed summary

**Not Mirror A.** File: `_raw/classic-keys-B-closed-trades.csv` (OfersClaw5). 0 pid overlap with parent mirror closes.

| Aggregate | Value |
|-----------|-------|
| Trades | {len(classic_keys_trades)} |
| Σ netProfit | {money(c_np)} |
| Σ fees | {money(c_fees)} |
| Σ fully_loaded | {money(c_fl)} |

| Symbol | n | Σ net | Σ fully_loaded |
|--------|---|-------|----------------|
{chr(10).join(f"| [[Symbols/{s}\\|{s}]] | {n} | {money(round(sum(t['netProfit'] for t in classic_keys_trades if t['symbol']==s),2))} | {money(round(sum(t['fullyLoaded'] for t in classic_keys_trades if t['symbol']==s),2))} |" for s,n in top_ck)}
""",
    )

    write(
        ROOT / "Analytics/Momentum-keys-B-Closed-Summary.md",
        fm(
            tags=["analytics", "momentum", "keys-B"],
            ledger=LEDGER_KEYS_B,
            tradeCount=len(mom_key_trades),
            sumNetProfit=m_np,
            sumFees=m_fees,
            sumFullyLoaded=m_fl,
            source="_raw/momentum-keys-closed-20260501.json",
        )
        + f"""# Momentum keys-B closed summary

| Aggregate | Value |
|-----------|-------|
| Trades | {len(mom_key_trades)} |
| Σ netProfit | {money(m_np)} |
| Σ fees | {money(m_fees)} |
| Σ fully_loaded | {money(m_fl)} |

{chr(10).join(f"- [[Trades/Momentum-keys-B/{t['symbol']}-{t['positionId']}|{t['symbol']}]] · {money(t['fullyLoaded'])} · {to_idt(t['closeTime'])}" for t in sorted(mom_key_trades, key=lambda x: x['closeTime'], reverse=True))}
""",
    )

    write(
        ROOT / "Analytics/Parent-personal-Closed-Summary.md",
        fm(
            tags=["analytics", "parent"],
            ledger="parent-SSO",
            tradeCount=len(parent_personal_closes),
            sumNetProfit=pp_np,
            sumFullyLoaded=pp_fl,
            source="_raw/parent-etoro-closed-20260501.json",
        )
        + f"""# Parent personal closed summary

`isMirrorTrade:false` · n={len(parent_personal_closes)} · Σ fully_loaded {money(pp_fl)}

Not Classic Mirror A closed-move set.
""",
    )

    # Symbols
    by_sym = defaultdict(lambda: {"co": None, "mo": None, "ma": [], "ck": [], "mk": [], "pp": []})
    for p in classic["positions"]:
        by_sym[p["symbol"]]["co"] = p
    for p in momentum["positions"]:
        by_sym[p["symbol"]]["mo"] = p
    for t in classic_mirror_a_closes:
        by_sym[t["symbol"]]["ma"].append(t)
    for t in classic_keys_trades:
        by_sym[t["symbol"]]["ck"].append(t)
    for t in mom_key_trades:
        by_sym[t["symbol"]]["mk"].append(t)
    for t in parent_personal_closes:
        by_sym[t["symbol"]]["pp"].append(t)

    syms = sorted(by_sym)
    write(
        ROOT / "Symbols/_MOC-Symbols.md",
        fm(tags=["moc", "symbols"], ledger=LEDGER_MIRROR_A, count=len(syms))
        + f"# Symbols MOC\n\n{chr(10).join(f'- [[Symbols/{s}]]' for s in syms)}\n",
    )
    for sym, d in by_sym.items():
        # pick primary ledger tag for symbol note
        led = LEDGER_MIRROR_A if (d["co"] or d["mo"] or d["ma"]) else (LEDGER_KEYS_B if (d["ck"] or d["mk"]) else "parent-SSO")
        parts = [fm(tags=["symbol"], ledger=led, symbol=sym), f"# {sym}\n"]
        if d["co"]:
            parts.append(f"## Classic open (mirror-A)\n\n[[Positions/Classic/{sym}]] · PnL {money(d['co']['pnl'])}\n")
        if d["mo"]:
            parts.append(f"## Momentum open (mirror-A)\n\n[[Positions/Momentum/{sym}]] · PnL {money(d['mo']['pnl'])}\n")
        if d["ma"]:
            parts.append("## Classic Mirror A closes\n\n" + "\n".join(f"- [[Trades/Classic-mirror-A/{sym}-{t['positionId']}|{t['positionId']}]] · FL {money(t['fullyLoaded'])}" for t in d["ma"]) + "\n")
        if d["ck"]:
            parts.append("## Classic keys-B closes\n\n" + "\n".join(f"- [[Trades/Classic-keys-B/{sym}-{t['positionId']}|{t['positionId']}]] · FL {money(t['fullyLoaded'])}" for t in d["ck"]) + "\n")
        if d["mk"]:
            parts.append("## Momentum keys-B closes\n\n" + "\n".join(f"- [[Trades/Momentum-keys-B/{sym}-{t['positionId']}|{t['positionId']}]] · FL {money(t['fullyLoaded'])}" for t in d["mk"]) + "\n")
        if d["pp"]:
            parts.append("## Parent personal closes\n\n" + "\n".join(f"- [[Trades/Parent-personal/{sym}-{t['positionId']}|{t['positionId']}]] · FL {money(t['fullyLoaded'])}" for t in d["pp"]) + "\n")
        write(ROOT / f"Symbols/{sym}.md", "\n".join(parts))

    # Daily brief + journal + playbooks
    write(
        ROOT / "Daily-Briefs/2026-09-30-afternoon-1530.md",
        fm(tags=["daily-brief"], ledger=LEDGER_MIRROR_A, slot=slot, asOf=as_of, fg=fg.get("score"), source="_raw/daily-brief.json")
        + f"""# Daily brief · {slot}

F&G **{fg.get('score')} — {fg.get('rating')}** · {brief.get('slotBadge','')}

Classic A equity {money(classic['equity'])} · Momentum A equity {money(momentum['equity'])} · Combined {money(start_capital)}

[[Portfolios/Classic]] · [[Portfolios/Momentum]] · [[01-Plan-70k]]
""",
    )
    write(
        ROOT / "Journals/2026-09.md",
        fm(tags=["journal"], ledger=LEDGER_MIRROR_A, month="2026-09")
        + f"""# Journal · 2026-09

- Classic A: {money(classic['equity'])} / cash {money(classic['cash'])} · {', '.join(classic['symbols'])}
- Momentum A: {money(momentum['equity'])} / cash {money(momentum['cash'])} · {', '.join(momentum['symbols'])}
- 70k plan start: {money(start_capital)}
- Classic mirror-A closes in window: {len(classic_mirror_a_closes)} · keys-B classic closes: {len(classic_keys_trades)}
""",
    )
    write(
        ROOT / "Playbooks/Classic-Mandate.md",
        fm(tags=["playbook", "classic"], ledger=LEDGER_MIRROR_A)
        + """# Classic mandate

Mirror A `11368142` only for reporting. Long ×1 · no crypto · cash floor · QA PASS before place.
""",
    )
    write(
        ROOT / "Playbooks/Momentum-Playbook.md",
        fm(tags=["playbook", "momentum"], ledger=LEDGER_MIRROR_A)
        + """# Momentum playbook

Mirror A `11630170` $8k basis. Breakout + VCP · trail after 1R · EOD FULL AUTO after QA PASS. keys-B = execution only.
""",
    )

    # .obsidian
    write(ROOT / ".obsidian/app.json", json.dumps({"alwaysUpdateLinks": True}, indent=2))
    write(
        ROOT / ".obsidian/core-plugins.json",
        json.dumps(
            {
                "file-explorer": True,
                "global-search": True,
                "switcher": True,
                "graph": True,
                "backlink": True,
                "tag-pane": True,
                "page-preview": True,
                "templates": True,
                "command-palette": True,
                "outline": True,
            },
            indent=2,
        ),
    )

    # Count ledger tags
    md_files = list(ROOT.rglob("*.md"))
    with_ledger = 0
    move_notes = 0
    for p in md_files:
        text = p.read_text(encoding="utf-8")
        if text.startswith("---") and "\nledger:" in text.split("---", 2)[1]:
            with_ledger += 1
        if "Trades/" in str(p) and "closed" in text[:500]:
            move_notes += 1

    qa = {
        "schema": "qa-pack-obsidian-kb-v1",
        "vault": str(ROOT),
        "builtAt": datetime.now(IL).isoformat(timespec="seconds"),
        "asOf_sources": as_of,
        "slot": slot,
        "fixesApplied": [
            "RENAME classic-mirror-closed-trades.csv → classic-keys-B-closed-trades.csv",
            "Classic CLOSED moves from parent-etoro-closed isMirrorTrade:true (mirror-A)",
            "keys-B CSV / momentum keys labeled ledger keys-B only",
            "01-Plan-70k.md starting_capital=20649.39",
            "Indexes + README + Feedback loop",
            "ledger tag on every note",
        ],
        "rules": {
            "classic_open": "Mirror A 11368142 only",
            "classic_closed_moves": "parent-etoro-closed-20260501.json isMirrorTrade:true",
            "classic_keysB_csv": "classic-keys-B-closed-trades.csv — NOT Mirror A",
            "momentum_open": "Mirror A 11630170 $8k",
            "fully_loaded": "netProfit - fees",
            "plan70k_start": "12841.61 + 7807.78 = 20649.39",
        },
        "headline": {
            "classic.equity": classic["equity"],
            "classic.cash": classic["cash"],
            "momentum.equity": momentum["equity"],
            "momentum.cash": momentum["cash"],
            "plan70k.starting_capital": start_capital,
            "classic_mirrorA_closes.n": len(classic_mirror_a_closes),
            "classic_keysB_closes.n": len(classic_keys_trades),
            "momentum_keysB_closes.n": len(mom_key_trades),
            "parent_personal_closes.n": len(parent_personal_closes),
        },
        "inventory": {
            "md_notes_total": len(md_files),
            "md_notes_with_ledger_tags": with_ledger,
            "closed_move_notes_classic_mirror_a": len(classic_mirror_a_closes),
            "closed_move_notes_classic_keys_b": len(classic_keys_trades),
            "closed_move_notes_momentum_keys_b": len(mom_key_trades),
            "closed_move_notes_parent_personal": len(parent_personal_closes),
            "plan_70k_path": "01-Plan-70k.md",
        },
        "claimCount": len(CLAIMS),
        "claims": CLAIMS,
        "qaBot": {
            "status": "READY_FOR_RECHECK",
            "qaBotId": "498c78db-a027-4f2c-8126-3c2be6f0a4bb",
            "instruction": "CoS: ask QA Bot to re-run OBSIDIAN_TRADING_KB_NUMBER_GATE vs this pack. Executor cannot SendToAgent.",
        },
    }
    (RAW / "qa-pack-obsidian-kb.json").write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "md": len(md_files),
                "with_ledger": with_ledger,
                "classic_mirror_a_moves": len(classic_mirror_a_closes),
                "classic_keys_b_moves": len(classic_keys_trades),
                "start_capital": start_capital,
                "csv": str(new),
                "old_csv_gone": not old.exists(),
                "claims": len(CLAIMS),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

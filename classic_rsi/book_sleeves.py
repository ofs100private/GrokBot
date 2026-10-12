"""Recompute the sleeve / name percentages and the SPY cash-parking cap check in the Classic book
(/workspace/classic-portfolio-for-app.json) on TOTAL EQUITY (holdings + cash; Ofer 2026-10-12 17:56 IDT).

Fix7b. Local only: reads the file's own positions/equity/cash, never calls eToro, never places.
Market value basis: % of book equity. Cost basis: % of (sum of position cost + cash).
Old invested-basis numbers are kept only under `legacyInvestedBasis` (labelled, informational).

Run: cd /workspace && python3 -m classic_rsi.book_sleeves [--book PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .execute_pass import DEFAULT_SLEEVES, NAME_CAP, SLEEVE_CAP, CASH_FLOOR_USD
from .instruments import resolve

BOOK = Path("/workspace/classic-portfolio-for-app.json")
BASIS = "% of total equity (holdings + cash); cost basis = % of (position cost + cash) — Ofer 2026-10-12 17:56 IDT"
SPY_CAP = NAME_CAP["etf"]
IDT = ZoneInfo("Asia/Jerusalem")


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def _agg(book: dict) -> tuple[dict, dict]:
    v: dict = {}
    c: dict = {}
    for p in book.get("positions") or []:
        s = str(p["symbol"]).upper()
        v[s] = v.get(s, 0.0) + float(p.get("value") or 0.0)
        c[s] = c.get(s, 0.0) + float(p.get("invested") or 0.0)
    return v, c


def recompute(book: dict) -> dict:
    """Return a copy of `book` with `sleeves` (+ cashTriggerProposal cap fields) on total equity."""
    b = json.loads(json.dumps(book))
    v, c = _agg(b)
    cash = float(b.get("cash", (b.get("summary") or {}).get("availableCash")))
    eq = float(b.get("equity"))
    eq_cost = sum(c.values()) + cash
    hold = sum(v.values())
    sl = {s: DEFAULT_SLEEVES.get(s, "unknown") for s in v}

    def spct(vals, den, name):
        return r2(sum(x for s, x in vals.items() if sl[s] == name) / den * 100)

    growth = sum(x for s, x in v.items() if sl[s] == "growth_tech")
    names = {}
    for s in sorted(v):
        cap = NAME_CAP.get(str((resolve(s) or {}).get("assetClass") or ""))
        names[s] = {"pctEquity": r2(v[s] / eq * 100), "pctEquityCost": r2(c[s] / eq_cost * 100),
                    "capPct": None if cap is None else cap * 100,
                    "headroomUsd": None if cap is None else r2(cap * eq - v[s]),
                    "headroomCostBasisUsd": None if cap is None else r2(cap * eq_cost - c[s])}
    sleeves_all = sorted(set(sl.values()))
    s_out = {
        "basis": BASIS,
        "denominator": "equity",
        "equity": eq, "equityCostBasis": r2(eq_cost), "cash": cash, "holdingsValue": r2(hold),
        "reconciliation": {"equityMinusHoldingsPlusCash": r2(eq - hold - cash),
                           "pctOfEquity": r2(abs(eq - hold - cash) / eq * 100), "tolPct": 0.5,
                           "ok": abs(eq - hold - cash) <= 0.005 * eq},
        "growthPct": spct(v, eq, "growth_tech"),
        "growthLabel": f"{spct(v, eq, 'growth_tech')}% of equity (${growth:,.2f}/${eq:,.2f})",
        "growthLabelBrief": f"{round(growth / eq * 100, 1)}% of equity (${growth:,.2f}/${eq:,.2f})",
        "healthcarePct": spct(v, eq, "healthcare"), "broadCorePct": spct(v, eq, "broad_core"),
        "growthCapPct": SLEEVE_CAP * 100, "growthHeadroomUsd": r2(SLEEVE_CAP * eq - growth),
        "sleevePct": {n: {"pctEquity": spct(v, eq, n), "pctEquityCost": spct(c, eq_cost, n)} for n in sleeves_all},
        "names": names,
        "singleStock": {s: names[s]["pctEquity"] for s in names if names[s]["capPct"] == NAME_CAP["stock"] * 100},
        "spyCore": {"pct": names.get("SPY", {}).get("pctEquity"), "capPct": SPY_CAP * 100,
                    "headroomUsd": names.get("SPY", {}).get("headroomUsd"),
                    "headroomCostBasisUsd": names.get("SPY", {}).get("headroomCostBasisUsd")},
        "legacyInvestedBasis": {
            "label": "LEGACY — % of invested (holdings only, cash excluded); NOT used for caps since 2026-10-12 17:56 IDT",
            "invested": r2(hold), "growthPct": r2(growth / hold * 100) if hold else None,
            "names": {s: r2(v[s] / hold * 100) for s in sorted(v)} if hold else {}},
        "recomputedAt": datetime.now(IDT).isoformat(timespec="seconds"),
        "recomputedBy": "classic_rsi.book_sleeves (local, no eToro call)",
    }
    s_out["singleStock"]["capPct"] = NAME_CAP["stock"] * 100
    b["sleeves"] = s_out
    ct = b.get("cashTriggerProposal")
    if isinstance(ct, dict) and "SPY" in v:
        mx = float(ct.get("maxNotional") or 0.0)
        spy_v, spy_c = v["SPY"], c["SPY"]

        def after(n):
            return {"notional": n, "spyPctEquity": r2((spy_v + n) / eq * 100),
                    "spyPctEquityCost": r2((spy_c + n) / eq_cost * 100),
                    "growthPctEquity": r2(growth / eq * 100), "cash": r2(cash - n),
                    "cashPctEquity": r2((cash - n) / eq * 100), "cashFloorOk": cash - n >= CASH_FLOOR_USD}
        legacy = {k: ct.pop(k) for k in ("after", "rejectedSizing", "capCheck") if k in ct}
        ct["after"] = after(mx)
        hm, hc = r2(SPY_CAP * eq - spy_v), r2(SPY_CAP * eq_cost - spy_c)
        ct["capCheck"] = {"spyCapPct": SPY_CAP * 100, "basis": BASIS, "headroomMarketValueUsd": hm,
                          "headroomCostBasisUsd": hc, "maxNotionalWithinCap": r2(min(hm, hc)),
                          "proposalWithinCap": mx <= min(hm, hc),
                          "binding": (f"30% of equity cap allows up to ${min(hm, hc):,.2f}; the ${mx:,.0f} proposal is "
                                      f"{'within' if mx <= min(hm, hc) else 'ABOVE'} it (cap no longer binding at $440-$500)")}
        ct["sizing500"] = dict(after(500.0), verdict="within 30% of equity cap" if 500 <= min(hm, hc) else "breaches 30% of equity cap")
        if legacy:
            ct["legacyInvestedBasis"] = dict(legacy, label="LEGACY — computed on % of invested (pre 2026-10-12 17:56 IDT); superseded")
    return b


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=str(BOOK))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    p = Path(a.book)
    new = recompute(json.loads(p.read_text()))
    if a.dry_run:
        print(json.dumps({"sleeves": new["sleeves"], "cashTriggerProposal.capCheck": (new.get("cashTriggerProposal") or {}).get("capCheck")}, indent=1))
        return 0
    bak = p.with_name(p.name + ".bak-" + datetime.now(IDT).strftime("%Y%m%d-%H%M%S") + "-pre-equity-sleeves")
    shutil.copy2(p, bak)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".book-", suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(new, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, p)
    print(f"wrote {p} (backup {bak.name}); growth {new['sleeves']['growthPct']}% of equity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

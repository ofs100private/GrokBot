#!/usr/bin/env python3
"""SKIP audit rows for every screener pack BUY name that was not placed (QA Bot 2026-10-21).

Usage:
  ./screener-venv/bin/python -m momentum_qa.pack_skips --screener <screener.json> \\
      --verdict <qa-verdict.json> [--placed SYM,...] [--no-audit] [--backfill] [--day YYYY-MM-DD]

<screener.json>: screener-run-<run_id>.json (run_id + buys) or the screener stdout row list.
Reason per symbol comes from the QA verdict (authorize_place / per_symbol / names entry with
authorize false + code/reason), or ALREADY_HELD / INSUFFICIENT_CASH markers in its text.
Placed = --placed  UNION  names with a FILL/PLACE/POSTFILL(found) row in that day's audit file.
Idempotent: an existing SKIP row for run+base symbol is never duplicated. Prints JSON summary.
RUN_ID CONVENTION: run_id = screener_run_id (same as place_audit rows) + top-level screener_run_id.
Symbols compare as base tickers (eToro A.US / X.RTH == A / X; see instrument_map.base_symbol).
Exit 0 ok, 2 bad input (missing run id / unreadable files).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from momentum_qa import audit as au

SCRIPT = "momentum_qa/pack_skips.py"
KNOWN_CODES = sorted(au.SKIP_GATE_OK_CODES | au.PROTECTIVE_REJECT_CODES | au.INTENTIONAL_SKIP_CODES,
                     key=len, reverse=True)
TEXT_MARKERS = [
    (re.compile(r"already[ _-]?held|held pos|DUPLICATE", re.I), "ALREADY_HELD"),
    (re.compile(r"insufficient[ _-]?cash", re.I), "INSUFFICIENT_CASH"),
    (re.compile(r"cross[ _-]?book", re.I), "CROSS_BOOK_OVERLAP"),
    (re.compile(r"ETF[ _-]?cap", re.I), "ETF_CAP"),
]


def load_screener(obj: Any, run_id: str | None = None) -> tuple[str | None, list[str]]:
    """(run_id, ordered pack BUY symbols) from a run summary dict or a stdout row list."""
    buys: list[str] = []
    if isinstance(obj, dict):
        run_id = run_id or obj.get("run_id")
        src = obj.get("buys") or obj.get("rows") or obj.get("pack_rows") or []
    else:
        src = obj or []
    for b in src:
        if isinstance(b, str):
            sym = b
        elif isinstance(b, dict):
            if str(b.get("action") or "BUY").upper() != "BUY":
                continue
            sym = b.get("symbol") or b.get("etoro_symbol")
            run_id = run_id or b.get("run_id")
        else:
            continue
        if sym and sym not in buys:
            buys.append(str(sym))
    return run_id, buys


def _entries(verdict: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("names", "per_symbol", "authorize_place"):  # later keys win
        v = verdict.get(key)
        if isinstance(v, dict):
            out.update(v)
        elif isinstance(v, list):
            for e in v:
                if isinstance(e, dict) and e.get("symbol"):
                    out[e["symbol"]] = e
    return out


def code_from_text(text: str) -> str | None:
    t = str(text or "")
    for c in KNOWN_CODES:
        if re.search(rf"\b{re.escape(c)}\b", t):
            return "ALREADY_HELD" if c in ("DUPLICATE", "DUPLICATE_PLACE", "DUPLICATE_HOLD_BUY") else c
    for rx, code in TEXT_MARKERS:
        if rx.search(t):
            return code
    return None


def reason_for(symbol: str, verdict: dict) -> tuple[str, str, bool | None]:
    """(reason_code, qa_reason_text, authorize) for one symbol from the QA verdict."""
    e = _entries(verdict).get(symbol)
    if isinstance(e, str):
        return code_from_text(e) or "NO_QA_REASON", e, None
    if isinstance(e, dict):
        auth = e.get("authorize", e.get("authorize_place"))
        reasons = e.get("reasons") if isinstance(e.get("reasons"), list) else []
        text = str(e.get("reason") or "; ".join(map(str, reasons)) or "")
        if auth is True:
            return "AUTHORIZED_NOT_PLACED", text or "QA authorized but no fill recorded", True
        code = e.get("code") or e.get("reason_code") or code_from_text(text) or code_from_text(e.get("verdict"))
        return (str(code).upper() if code else "NO_QA_REASON"), text, auth
    # list markers anywhere top-level, e.g. {"already_held": ["DVN"]}
    for k, v in verdict.items():
        if isinstance(v, list) and symbol in v:
            c = code_from_text(k.replace("_", " ")) or code_from_text(k.upper())
            if c:
                return c, f"verdict.{k}", False
    return "NO_QA_REASON", "symbol not covered by QA verdict", None


def plan(screener: Any, verdict: dict, *, placed: set[str], run_id: str | None = None,
         existing: list[dict] | None = None) -> dict:
    rid, buys = load_screener(screener, run_id)
    rid = rid or ((verdict.get("screener_run") or {}).get("run_id"))
    have = {au.base_symbol_of(r.get("symbol")) for r in (existing or [])
            if r.get("event") == "SKIP" and au.row_screener_run_id(r) == rid}
    placed_base = {au.base_symbol_of(x) for x in placed}
    rows, already = [], []
    for s in buys:
        if au.base_symbol_of(s) in placed_base:
            continue
        if au.base_symbol_of(s) in have:
            already.append(s)
            continue
        code, text, auth = reason_for(s, verdict)
        rows.append({"symbol": s, "reason_code": code, "gate": au.classify_skip_code(code),
                     "qa_reason": text, "authorize": auth})
    return {"run_id": rid, "pack": buys, "placed": sorted(s for s in buys if au.base_symbol_of(s) in placed_base),
            "to_write": rows,
            # QA fixes4: unknown / label-only codes (incl. literal GATE_OK) -> feedback SKIP_UNGATED
            "ungated": sorted(r["symbol"] for r in rows if r["gate"] is None),
            "already_present": already}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--screener", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--placed", default="")
    ap.add_argument("--run-id")
    ap.add_argument("--day", help="target <IL date>.jsonl (default: date in run id, else today IL)")
    ap.add_argument("--no-audit", action="store_true", help="dry run: print rows, write nothing")
    ap.add_argument("--backfill", action="store_true", help="mark rows backfill:true + backfill_ts")
    ap.add_argument("--expect-sha", help="refuse (exit 2) unless the verdict file sha256 matches")
    a = ap.parse_args(argv)
    try:
        screener = json.loads(Path(a.screener).read_text())
        verdict = json.loads(Path(a.verdict).read_text())
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"read failed: {e}"})); return 2
    sha = au.file_sha256(a.verdict)
    if a.expect_sha and a.expect_sha.lower() != sha:
        print(json.dumps({"ok": False, "error": "VERDICT_SHA_MISMATCH", "sha256": sha})); return 2
    rid0, _ = load_screener(screener, a.run_id)
    rid0 = rid0 or (verdict.get("screener_run") or {}).get("run_id")
    if not rid0:
        print(json.dumps({"ok": False, "error": "no screener run_id (pass --run-id)"})); return 2
    day = a.day or au.day_from_run_id(rid0)
    log = au.AuditLogger(rid0, SCRIPT, write_start=False, day=day, backfill=a.backfill)
    existing = log.rows()
    placed = {s.strip() for s in a.placed.split(",") if s.strip()} | au.placed_symbols(existing)
    p = plan(screener, verdict, placed=placed, run_id=rid0, existing=existing)
    written = []
    if not a.no_audit:
        for r in p["to_write"]:
            rec = log.skip(r["symbol"], r["reason_code"], verdict_sha256=sha, run_id=p["run_id"],
                           rationale=f"{r['symbol']} not placed: {r['reason_code']} ({r['gate'] or 'NO_GATE'}) "
                                     f"per QA verdict {Path(a.verdict).name}: {r['qa_reason']}"[:500],
                           details={"qa_reason": r["qa_reason"], "authorize": r["authorize"],
                                    "verdict_path": str(a.verdict), "source": "pack_skips"})
            if rec:
                written.append(r["symbol"])
    print(json.dumps({"ok": True, "audit_path": str(log.path), "verdict_sha256": sha, "dry_run": a.no_audit,
                      "written": written, **p}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

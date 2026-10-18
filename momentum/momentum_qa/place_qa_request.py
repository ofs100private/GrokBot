"""Build the screener place-QA request for QA Bot (QA Bot asks 2026-10-13).

(a) PM gate: requires a CLEAN position_manager RUN_END for the same EOD (IL date). If PM crashed
    and was rerun, BOTH run_ids are cited (crashed + clean rerun). No clean RUN_END → NOT_READY.
(c) Sector-overlap ADVISORY (never a fail): ≥2 same-sector buys in one pack, or a new buy whose
    sector is already ≥25% of the invested book.
Cross-book: buys held in Classic are listed as CROSS_BOOK_HELD (the screener already drops them).

CLI: python -m momentum_qa.place_qa_request --screener-run <json> --eod 2026-10-12
         [--audit momentum_audit/2026-10-12.jsonl] [--book book.json] [--sectors sectors.json]
book.json = [{"symbol": "NTAP", "invested": 1000}, ...] (keys book, live read)
"""
from __future__ import annotations
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/workspace")
AUDIT_DIR = Path("/workspace/momentum_audit")
SECTOR_SHARE_LIMIT = 0.25

ETF_SECTOR = {"XLK": "Technology", "SMH": "Technology", "SOXX": "Technology", "IGV": "Technology", "QQQ": "Broad",
              "SPY": "Broad", "XLE": "Energy", "XOP": "Energy", "USO": "Energy", "XLF": "Financial Services",
              "KRE": "Financial Services", "XLV": "Healthcare", "XBI": "Healthcare", "XLI": "Industrials",
              "ITA": "Industrials", "XLY": "Consumer Cyclical", "XLP": "Consumer Defensive", "XLU": "Utilities",
              "XLB": "Basic Materials", "GLD": "Basic Materials", "SLV": "Basic Materials", "XLRE": "Real Estate",
              "XLC": "Communication Services"}
SECTOR_CACHE = AUDIT_DIR / "sector_cache.json"


def default_sector_of(sym: str) -> str | None:
    s = sym.upper()
    if s in ETF_SECTOR:
        return ETF_SECTOR[s]
    cache = {}
    try:
        cache = json.loads(SECTOR_CACHE.read_text())
    except Exception:
        pass
    if s in cache:
        return cache[s]
    try:
        import yfinance as yf
        sec = (yf.Ticker(s.replace(".", "-")).info or {}).get("sector")
    except Exception:
        sec = None
    if sec:
        cache[s] = sec
        try:
            SECTOR_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))
        except Exception:
            pass
    return sec


def pm_run_status(eod: str, audit_path: str | Path | None = None) -> dict:
    """Scan the EOD audit log for position_manager runs. ok only with a clean RUN_END."""
    p = Path(audit_path) if audit_path else AUDIT_DIR / f"{eod}.jsonl"
    runs: dict[str, dict] = {}
    try:
        lines = p.read_text().splitlines()
    except Exception as e:
        return {"ok": False, "code": "PM_AUDIT_MISSING", "detail": f"{p}: {e}", "clean_run_id": None, "crashed_run_ids": []}
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("script") != "position_manager.py":
            continue
        rid = r.get("run_id")
        st = runs.setdefault(rid, {"run_id": rid, "start": None, "end": False, "error": None})
        ev = r.get("event")
        if ev == "RUN_START":
            st["start"] = r.get("ts_il")
        elif ev == "RUN_END":
            st["end"] = True
        elif ev == "ERROR" and r.get("where") == "main":
            st["error"] = r.get("error")
    clean = [r for r in runs.values() if r["end"] and not r["error"]]
    crashed = [r for r in runs.values() if r["error"] or not r["end"]]
    last_clean = sorted(clean, key=lambda r: r["start"] or "")[-1] if clean else None
    res = {"ok": bool(last_clean), "clean_run_id": last_clean["run_id"] if last_clean else None,
           "crashed_run_ids": [r["run_id"] for r in sorted(crashed, key=lambda r: r["start"] or "")],
           "crash_errors": {r["run_id"]: r["error"] for r in crashed if r["error"]}, "eod": eod}
    res["code"] = ("PM_CLEAN" if not crashed else "PM_CRASHED_THEN_CLEAN_RERUN") if last_clean else "PM_NO_CLEAN_RUN_END"
    if last_clean and crashed:
        res["citation"] = f"PM crashed run(s) {', '.join(res['crashed_run_ids'])}; clean rerun {res['clean_run_id']}"
    elif last_clean:
        res["citation"] = f"PM clean RUN_END {res['clean_run_id']}"
    else:
        res["citation"] = "NO clean PM RUN_END for this EOD — place-QA request NOT_READY"
    return res


def sector_advisories(buys: list[dict], book: list[dict], sector_of=default_sector_of,
                      limit: float = SECTOR_SHARE_LIMIT) -> list[dict]:
    adv = []
    sec_buy = defaultdict(list)
    for b in buys:
        s = sector_of(b["symbol"])
        if s and s != "Broad":
            sec_buy[s].append(b["symbol"])
    for s, syms in sec_buy.items():
        if len(syms) >= 2:
            adv.append({"code": "SECTOR_OVERLAP_PACK", "severity": "ADVISORY", "sector": s, "symbols": syms,
                        "rationale": f"{len(syms)} buys in {s} in one pack"})
    total = sum(float(p.get("invested") or 0) for p in book)
    by_sec = defaultdict(float)
    for p in book:
        s = sector_of(p["symbol"])
        if s:
            by_sec[s] += float(p.get("invested") or 0)
    if total > 0:
        for b in buys:
            s = sector_of(b["symbol"])
            if s and s != "Broad" and by_sec[s] / total >= limit:
                adv.append({"code": "SECTOR_OVERLAP_BOOK", "severity": "ADVISORY", "sector": s, "symbol": b["symbol"],
                            "book_share_pct": round(by_sec[s] / total * 100, 1),
                            "rationale": f"{b['symbol']} adds to {s} already {by_sec[s] / total:.0%} of invested book"})
    return adv


def build_request(screener_run: dict, eod: str, *, audit_path=None, book: list[dict] | None = None,
                  sector_of=default_sector_of, classic_held: set[str] | None = None) -> dict:
    pm = pm_run_status(eod, audit_path)
    buys = [{"symbol": s} if isinstance(s, str) else s for s in (screener_run.get("buys") or [])]
    cross = sorted({b["symbol"] for b in buys} & (classic_held or set()))
    buys = [b for b in buys if b["symbol"] not in cross]
    adv = sector_advisories(buys, book or [], sector_of)
    return {"type": "SCREENER_PLACE_QA_REQUEST", "eod": eod, "screener_run_id": screener_run.get("run_id"),
            "status": "READY" if pm["ok"] else "NOT_READY", "blocking": [] if pm["ok"] else [pm["code"]],
            "pm_gate": pm, "buys": [b["symbol"] for b in buys], "cross_book_held_dropped": cross,
            "advisories": adv, "advisory_note": "sector advisories are informational; they do not fail QA"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screener-run", required=True); ap.add_argument("--eod", required=True)
    ap.add_argument("--audit"); ap.add_argument("--book"); ap.add_argument("--sectors")
    a = ap.parse_args()
    sr = json.loads(Path(a.screener_run).read_text())
    book = json.loads(Path(a.book).read_text()) if a.book else []
    smap = json.loads(Path(a.sectors).read_text()) if a.sectors else None
    sof = (lambda s: smap.get(s) or default_sector_of(s)) if smap else default_sector_of
    import classic_book
    held, _ = classic_book.load_held()
    req = build_request(sr, a.eod, audit_path=a.audit, book=book, sector_of=sof, classic_held=held)
    if held is None:  # fail closed on Classic read
        req["status"] = "NOT_READY"; req["blocking"].append(classic_book.MISSING_CODE)
    print(json.dumps(req, indent=2))
    sys.exit(0 if req["status"] == "READY" else 2)


if __name__ == "__main__":
    main()

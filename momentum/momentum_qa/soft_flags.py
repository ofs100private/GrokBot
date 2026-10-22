"""Soft review flags for the Momentum screener pack (QA Bot ruling 2026-10-19).

Flags are REVIEW NOTES, never gates: computed after the pack is final and never change which
buys are packed or executable.
  LOW_RVOL_PACK         every BUY in the pack has RVOL < 0.6 (needs >= 1 buy with known RVOL;
                        a buy with unknown RVOL does not count as low).
  SECTOR_CONCENTRATION  over unique names = currently held Momentum names + pack buys, one known
                        sector holds >= 50% of the names (unknown-sector names stay in the
                        denominator but never trigger). Only evaluated when the pack has >= 1 buy.
Sector lookup (no network): row["sector"] (screener attaches GICS sector from the S&P universe
table) -> universe sector map (/workspace/sp500_symbols.json "sectors") -> ETF map ->
momentum_audit/sector_cache.json. Names are normalized to GICS sector names.
Held names: books/latest/momentum_keys.json (books.snapshot, written by the step-0 precheck ingest).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

LOW_RVOL_MAX = 0.6
SECTOR_SHARE_MIN = 0.50
SP500_CACHE = Path("/workspace/sp500_symbols.json")
SECTOR_CACHE = Path("/workspace/momentum_audit/sector_cache.json")
HELD_SNAPSHOT = Path("/workspace/books/latest/momentum_keys.json")

# yfinance / Morningstar names -> GICS names (one taxonomy for counting)
_NORM = {"technology": "Information Technology", "information technology": "Information Technology",
         "healthcare": "Health Care", "health care": "Health Care",
         "financial services": "Financials", "financials": "Financials", "financial": "Financials",
         "consumer cyclical": "Consumer Discretionary", "consumer discretionary": "Consumer Discretionary",
         "consumer defensive": "Consumer Staples", "consumer staples": "Consumer Staples",
         "basic materials": "Materials", "materials": "Materials",
         "communication services": "Communication Services", "energy": "Energy",
         "industrials": "Industrials", "utilities": "Utilities", "real estate": "Real Estate"}
ETF_SECTOR = {"XLK": "Information Technology", "XLE": "Energy", "XLF": "Financials", "XLV": "Health Care",
              "XLY": "Consumer Discretionary", "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
              "XLP": "Consumer Staples", "XLRE": "Real Estate", "XLC": "Communication Services",
              "USO": "Energy", "URA": "Energy", "GLD": "Materials", "SLV": "Materials", "CPER": "Materials",
              "DBA": "Consumer Staples"}


def norm_sector(s: Any) -> Optional[str]:
    if not s or not str(s).strip():
        return None
    return _NORM.get(str(s).strip().lower(), str(s).strip())


def _sym(s: Any) -> str:
    from momentum_qa.instrument_map import base_symbol
    return base_symbol(str(s or "").upper().replace("-", "."))


def _read_json(p: Path) -> Any:
    try:
        return json.loads(Path(p).read_text())
    except Exception:  # noqa: BLE001
        return None


def universe_sectors(path: Path = SP500_CACHE) -> dict[str, str]:
    d = _read_json(path) or {}
    return {_sym(k): v for k, v in (d.get("sectors") or {}).items() if v}


def make_sector_of(universe: Optional[dict[str, str]] = None, cache_path: Path = SECTOR_CACHE) -> Callable[[str], Optional[str]]:
    uni = {_sym(k): v for k, v in (universe if universe is not None else universe_sectors()).items()}
    cache = {_sym(k): v for k, v in (_read_json(cache_path) or {}).items()}

    def sector_of(sym: str) -> Optional[str]:
        s = _sym(sym)
        return norm_sector(uni.get(s) or ETF_SECTOR.get(s) or cache.get(s))
    return sector_of


def held_symbols(path: Path = HELD_SNAPSHOT) -> tuple[list[str], Optional[str]]:
    d = _read_json(path)
    if not isinstance(d, dict):
        return [], f"HELD_SNAPSHOT_UNREADABLE: {path}"
    from momentum_qa.instrument_map import base_symbol
    if d.get("symbols"):
        return sorted({_sym(s) for s in d["symbols"] if s}), None
    return sorted({base_symbol(_sym(p.get("symbol")), p.get("instrumentId"))
                   for p in d.get("positions") or [] if p.get("symbol")}), None


def compute_soft_flags(pack_rows: Iterable[dict], held: Iterable[str], sector_of: Callable[[str], Optional[str]],
                       *, held_error: Optional[str] = None) -> list[dict]:
    buys = [r for r in pack_rows if r.get("action") == "BUY"]
    if not buys:
        return []
    flags: list[dict] = []
    rv = [(r.get("symbol"), r.get("rvol")) for r in buys]
    if all(v is not None and float(v) < LOW_RVOL_MAX for _, v in rv):
        flags.append({"code": "LOW_RVOL_PACK", "severity": "SOFT", "gate": False,
                      "detail": f"every pack buy RVOL<{LOW_RVOL_MAX}",
                      "rvol": {s: v for s, v in rv}})
    sec: dict[str, Optional[str]] = {}
    for r in buys:
        s = _sym(r.get("symbol") or r.get("etoro_symbol"))
        sec[s] = norm_sector(r.get("sector")) or sector_of(s)
    for s in held:
        s = _sym(s)
        if s not in sec:
            sec[s] = sector_of(s)
    n = len(sec)
    counts = Counter(v for v in sec.values() if v)
    for name, c in counts.most_common():
        if n and c / n >= SECTOR_SHARE_MIN:
            flags.append({"code": "SECTOR_CONCENTRATION", "severity": "SOFT", "gate": False, "sector": name,
                          "count": c, "n_names": n, "share_pct": round(c / n * 100, 1),
                          "symbols": sorted(k for k, v in sec.items() if v == name),
                          "pack_buys": sorted(_sym(r.get("symbol")) for r in buys),
                          "unknown_sector": sorted(k for k, v in sec.items() if not v),
                          **({"held_error": held_error} if held_error else {})})
    return flags

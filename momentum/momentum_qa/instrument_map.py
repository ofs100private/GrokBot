#!/usr/bin/env python3
"""eToro place-symbol overrides + quote sanity guard (QA Bot 2026-10-21, SYMBOL_MAP_A).

Finding: the screener's eToro symbol for Yahoo 'A' (Agilent) was the bare ticker 'A', and on
eToro the symbol 'A' resolves to VAULTA (crypto, instrumentId 100022, ~$0.10). Agilent
Technologies Inc is instrumentId 1764, eToro symbol 'A.US' (15020 'A.RTH' is the 24h variant,
requires W-8BEN - not used).

  ./screener-venv/bin/python -m momentum_qa.instrument_map resolve --symbol A
  ./screener-venv/bin/python -m momentum_qa.instrument_map guard --symbol A --quote 177.9 \\
        --quote-symbol <live market.symbol> --quote-instrument-id <live market.instrumentId> \\
        --instrument-id <screener row etoro_instrument_id> --screener-rows <screener-run.json> [--max-dev-pct 20]
  ./screener-venv/bin/python -m momentum_qa.instrument_map build-cache --overview <overview outputs...>
  ./screener-venv/bin/python -m momentum_qa.instrument_map cache-missing [--extra XLK,GLD,...]
guard exit: 0 PASS, 3 REFUSE (do NOT prepare/place), 2 bad input.
REFUSE codes: INSTRUMENT_ID_REQUIRED (no --instrument-id), QUOTE_ID_MISMATCH (live quote id/symbol missing
or quote id != screener row id != --instrument-id, or live symbol != place symbol), INSTRUMENT_ID_UNVERIFIED
(id not in instrument_ids.json / the map, or no row id -> fail closed), ID_SYMBOL_MISMATCH (--instrument-id is a known different ticker, e.g. AAPL+100022),
SYMBOL_MAP_MISMATCH, QUOTE_DEVIATION_GT_20PCT, QUOTE_GUARD_INPUT_MISSING (no --ref-close and no
screener row for the symbol -> fail closed).

QA 2026-10-21 re-review: held = id match OR base-symbol match (is_held); a mismatched id never
overrides the symbol. The ticker/crypto collision table below covers all S&P 500 names.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MAX_DEV_PCT = 20.0
# Verified read-only via eToro get-instruments-overview on 2026-10-21 (Momentum-HHHGDTJ):
# all 503 S&P tickers as bare symbols (xRequestIds in
# momentum_audit/instrument_map/sp500-bare-symbol-check-20261021.json) + the .US listings.
# (base, US listing symbol, US instrumentId, US name, crypto id on the BARE symbol, crypto name)
_COLLISIONS = [
    ("A", "A.US", 1764, "Agilent Technologies Inc", 100022, "VAULTA"),
    ("ABT", "ABT.US", 1552, "Abbott Laboratories", 100594, "Arcblock"),
    ("AMP", "AMP.US", 1644, "Ameriprise Financial Inc", 100081, "Amp"),
    ("CVX", "CVX.US", 1014, "Chevron", 100512, "Convex Finance"),
    ("DASH", "DASH.US", 8048, "DoorDash Inc", 100004, "Dash"),
    ("FIS", "FIS.US", 1792, "Fidelity National Information Services Inc", 100673, "Stafi"),
    ("FOX", "FOX.US", 8842, "Fox Corporation", 100666, "Shapeshift"),
    ("IP", "IP.US", 1539, "International Paper Co", 100437, "Story"),
    ("MDT", "MDT.US", 1477, "Medtronic PLC", 100644, "Measurable Data Token"),
    ("MET", "MET.US", 1478, "Metlife Inc", 100520, "Meteora"),
    ("STX", "STX.US", 4356, "Seagate Technology PLC", 100314, "Stacks"),
    ("T", "T.US", 1030, "AT&T Inc", 100528, "Threshold Network"),
    ("WELL", "WELL.US", 4278, "Welltower Inc", 100592, "Moonwell"),
]
# Bare symbol not found on eToro (prepare-trade would reject): place via the .US listing.
_BARE_NOT_FOUND = [
    ("ADI", "ADI.US", 4264, "Analog Devices Inc"), ("BSX", "BSX.US", 6624, "Boston Scientific Corp"),
    ("DG", "DG.US", 5391, "Dollar General Corporation"), ("IVZ", "IVZ.US", 9438, "Invesco Ltd"),
    ("TEL", "TEL.US", 5696, "TE Connectivity Ltd"), ("WRB", "WRB.US", 9436, "W R Berkley Corporation"),
    # Brown-Forman B: eToro spells it 'BF-B' (BF.B / BF.B.US not found; xRequestId 30a7c141-..., 2026-10-21)
    ("BF.B", "BF-B", 9061, "Brown-Forman Corporation"),
]

# Screener symbol -> the eToro identity to place.
ETORO_PLACE_OVERRIDES: dict[str, dict[str, Any]] = {}
# instrumentId -> {etoro_symbol, base, name, kind}. Crypto ids get base "CRYPTO:<sym>" so they
# never equal a stock ticker.
KNOWN_INSTRUMENTS: dict[int, dict[str, Any]] = {
    15020: {"etoro_symbol": "A.RTH", "base": "A", "name": "Agilent Technologies Inc (24h, W-8BEN)", "kind": "stock"},
}
for _b, _us, _id, _nm, _cid, _cnm in _COLLISIONS:
    ETORO_PLACE_OVERRIDES[_b] = {"etoro_symbol": _us, "instrumentId": _id, "name": _nm,
                                 "wrong_bare_symbol": {"symbol": _b, "instrumentId": _cid, "name": f"{_cnm} (crypto)"}}
    KNOWN_INSTRUMENTS[_id] = {"etoro_symbol": _us, "base": _b, "name": _nm, "kind": "stock"}
    KNOWN_INSTRUMENTS[_cid] = {"etoro_symbol": _b, "base": f"CRYPTO:{_b}", "name": _cnm, "kind": "crypto"}
for _b, _us, _id, _nm in _BARE_NOT_FOUND:
    ETORO_PLACE_OVERRIDES[_b] = {"etoro_symbol": _us, "instrumentId": _id, "name": _nm, "bare_not_found": True}
    KNOWN_INSTRUMENTS[_id] = {"etoro_symbol": _us, "base": _b, "name": _nm, "kind": "stock"}
KNOWN_WRONG_IDS = {s: o["wrong_bare_symbol"]["instrumentId"] for s, o in ETORO_PLACE_OVERRIDES.items()
                   if o.get("wrong_bare_symbol")}
# eToro listing suffixes that are the SAME company as the base ticker (US listing / 24h RTH).
LISTING_SUFFIXES = (".US", ".RTH")
ID_TO_BASE: dict[int, str] = {i: k["base"] for i, k in KNOWN_INSTRUMENTS.items()}  # back-compat view


def place_symbol(symbol: str) -> str:
    o = ETORO_PLACE_OVERRIDES.get(symbol)
    return o["etoro_symbol"] if o else symbol


def instrument_id(symbol: str) -> int | None:
    o = ETORO_PLACE_OVERRIDES.get(symbol)
    return o["instrumentId"] if o else None


def _int(x) -> int | None:
    try:
        return int(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def text_base(symbol) -> str:
    """Pure text: upper/strip and drop a .US/.RTH listing suffix. Never consults ids."""
    s = str(symbol or "").strip().upper()
    for suf in LISTING_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


def _consistent(symbol, k: dict) -> bool:
    """Does a POSITION's eToro symbol agree with what that instrumentId is known to be?"""
    raw = str(symbol or "").strip().upper()
    if k["kind"] != "stock":
        return raw == k["etoro_symbol"]  # crypto: only its exact bare eToro symbol
    return raw == k["etoro_symbol"] or text_base(raw) == k["base"]


def held_id_mismatch(symbol, instrument_id) -> bool:
    """Position side: known id whose eToro symbol disagrees with the row's symbol (bad data)."""
    k = KNOWN_INSTRUMENTS.get(_int(instrument_id) or -1)
    return bool(k and symbol and not _consistent(symbol, k))


def base_symbol(symbol, instrument_id=None) -> str:
    """POSITION-side identity: eToro symbol (+ instrumentId) -> screener base ticker.

    'A.US' -> 'A', 'SPY.RTH' -> 'SPY', 'BRK.B' stays. A known id only refines a CONSISTENT
    symbol (('A', 100022) -> 'CRYPTO:A' = VAULTA). A mismatched id never overrides the
    symbol (QA 2026-10-21 HIGH): ('AAPL', 1764) -> 'AAPL'."""
    k = KNOWN_INSTRUMENTS.get(_int(instrument_id) or -1)
    if k and (not symbol or _consistent(symbol, k)):
        return k["base"]
    return text_base(symbol)


def id_symbol_mismatch(symbol, instrument_id) -> str | None:
    """REQUEST side (a buy of screener ticker `symbol` with instrumentId): reason or None.

    Mismatch if the id is known (collision table OR the offline cache id->symbol reverse map) as a
    different ticker (AAPL + 100022/1764, POIS + 1001 = AAPL), or the ticker has known ids and
    this id is not one of them. An id unknown everywhere is not a mismatch here (the guard
    refuses it as INSTRUMENT_ID_UNVERIFIED)."""
    iid = _int(instrument_id)
    if iid is None:
        return None
    b = screener_key(symbol)
    k = KNOWN_INSTRUMENTS.get(iid)
    if k and k["base"] != b:
        return f"ID_SYMBOL_MISMATCH: instrumentId {iid} is {k['etoro_symbol']} ({k['name']}), not {b}"
    cs = cache_symbol_for_id(iid)
    if not k and cs is not None and cs != b:
        return f"ID_SYMBOL_MISMATCH: instrumentId {iid} is {cs} in the instrument cache, not {b}"
    ids = mapped_instrument_ids(b)
    if not k and cs is None and ids and iid not in ids:
        return f"ID_SYMBOL_MISMATCH: {b} is instrumentId {sorted(ids)}, got {iid}"
    return None


def cache_symbol_for_id(instrument_id, cache: dict | None = None) -> str | None:
    """id -> screener symbol from the collision table (stocks) + instrument_ids.json; None if unknown."""
    iid = _int(instrument_id)
    if iid is None:
        return None
    k = KNOWN_INSTRUMENTS.get(iid)
    if k:
        return k["base"]
    for sym, e in (cache if cache is not None else load_cache()).get("symbols", {}).items():
        if _int(e.get("instrumentId")) == iid:
            return screener_key(sym)
    return None


def mapped_instrument_ids(symbol) -> set[int]:
    """All eToro instrumentIds known to be the same company as base ticker `symbol`
    (collision table + the offline cache id)."""
    b = screener_key(symbol)
    out = {i for i, k in KNOWN_INSTRUMENTS.items() if k["base"] == b}
    e = load_cache().get("symbols", {}).get(b)
    if e and _int(e.get("instrumentId")) is not None:
        out.add(_int(e["instrumentId"]))
    return out


def is_held(symbol, held_symbols, held_ids=None, instrument_id=None) -> bool:
    """held = id match OR base-symbol match (both always run).

    Id side uses the ticker's mapped ids plus `instrument_id` only when it is consistent with
    the ticker (a mismatched id is ignored here; callers refuse it via id_symbol_mismatch)."""
    b = text_base(symbol)
    ids = {_int(i) for i in (held_ids or [])} - {None}
    want = set(mapped_instrument_ids(b))
    if _int(instrument_id) is not None and not id_symbol_mismatch(b, instrument_id):
        want.add(_int(instrument_id))
    id_match = bool(ids & want)
    sym_match = b in {text_base(h) for h in (held_symbols or [])}
    return id_match or sym_match


# ---------------------------------------------------------------- instrumentId cache
# Offline symbol -> eToro instrumentId for the whole screener universe (S&P 500 + sector /
# commodity ETFs). Filled ONLY from saved read-only `get-instruments-overview` outputs by
# `instrument_map build-cache` (see place_flow.md step 10). Overrides above always win.
CACHE_PATH = Path(__file__).resolve().parent / "instrument_ids.json"
_CACHE: dict | None = None


def load_cache(path: str | Path | None = None) -> dict:
    global _CACHE
    if path is None and _CACHE is not None:
        return _CACHE
    try:
        d = json.loads(Path(path or CACHE_PATH).read_text())
    except Exception:
        d = {"symbols": {}}
    if path is None:
        _CACHE = d
    return d


def screener_key(symbol) -> str:
    """eToro/Yahoo spelling -> screener symbol ('BF-B' -> 'BF.B', 'A.US' -> 'A')."""
    return text_base(str(symbol or "").replace("-", "."))


def resolve_instrument_id(symbol, cache: dict | None = None) -> int | None:
    """Screener-time id: remap override -> offline cache -> None (caller must fail closed)."""
    k = screener_key(symbol)
    o = ETORO_PLACE_OVERRIDES.get(k)
    if o:
        return o["instrumentId"]
    e = (cache if cache is not None else load_cache()).get("symbols", {}).get(k)
    return _int(e.get("instrumentId")) if e else None


def _overview_rows(path: str | Path) -> tuple[list[dict], str | None, list[str]]:
    t = Path(path).read_text()
    d = json.loads(t[t.index("{"): t.rindex("}") + 1])
    rows = []
    for it in d.get("instruments") or []:
        m = it.get("market") or {}
        if m.get("instrumentId") is not None and m.get("symbol"):
            rows.append({"etoro_symbol": str(m["symbol"]).upper(), "instrumentId": int(m["instrumentId"]),
                         "name": m.get("name")})
    return rows, d.get("xRequestId"), list(d.get("notFoundSymbols") or [])


def build_cache(paths: list[str], *, generated_utc: str | None = None) -> dict:
    """Deterministic: overview outputs -> {symbols: {screener_symbol: {instrumentId, etoro_symbol, name}}}.

    Known crypto collisions are dropped (the override wins for those tickers); a symbol seen
    with two different non-crypto ids is a conflict and is left unresolved (fail closed)."""
    from datetime import datetime, timezone
    seen: dict[str, set] = {}
    best: dict[str, dict] = {}
    xr, nf = [], set()
    for p in paths:
        rows, x, missing = _overview_rows(p)
        xr.append(x); nf |= {screener_key(m) for m in missing}
        for r in rows:
            k = screener_key(r["etoro_symbol"])
            kn = KNOWN_INSTRUMENTS.get(r["instrumentId"])
            if kn and kn["kind"] == "crypto":
                continue
            if k in ETORO_PLACE_OVERRIDES and r["instrumentId"] != ETORO_PLACE_OVERRIDES[k]["instrumentId"]:
                continue
            seen.setdefault(k, set()).add(r["instrumentId"])
            best[k] = r
    conflicts = sorted(k for k, ids in seen.items() if len(ids) > 1)
    syms = {k: best[k] for k in sorted(best) if k not in conflicts}
    for k, o in ETORO_PLACE_OVERRIDES.items():
        syms[k] = {"etoro_symbol": o["etoro_symbol"], "instrumentId": o["instrumentId"], "name": o["name"]}
    return {"generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
            "source": "user-Momentum-HHHGDTJ get-instruments-overview (read-only)", "xRequestIds": xr,
            "conflicts": conflicts, "not_found": sorted(nf - set(syms)), "symbols": dict(sorted(syms.items()))}


def missing_from_cache(symbols: list[str], cache: dict | None = None) -> list[str]:
    return sorted({screener_key(s) for s in symbols if resolve_instrument_id(s, cache) is None})


def quote_guard(symbol: str, quote: float | None, ref_close: float | None, *,
                instrument_id_seen: int | None = None, expected_instrument_id: int | None = None,
                quote_instrument_id: int | None = None, quote_symbol: str | None = None,
                max_dev_pct: float = MAX_DEV_PCT) -> dict:
    """Refuse a place unless ALL hold (QA fixes3 + fixes4, 2026-10-21):
      1. --instrument-id, the live quote's market.instrumentId and market.symbol are given;
      2. none of instrument id / quote id / screener-row id is known (collision table or cache
         reverse map) as a different ticker (ID_SYMBOL_MISMATCH), and the id is in the cache
         (else INSTRUMENT_ID_UNVERIFIED);
      3. live quote id == screener row id (remapped symbol without a row id: the map id) ==
         --instrument-id (else QUOTE_ID_MISMATCH), and the live market.symbol is the place symbol;
      4. remapped symbol: the id is the known stock id (SYMBOL_MAP_MISMATCH);
      5. the live quote is within max_dev_pct of the screener close."""
    key = screener_key(symbol)
    exp_map = instrument_id(symbol) or instrument_id(key)
    exp_row, seen, qid = _int(expected_instrument_id), _int(instrument_id_seen), _int(quote_instrument_id)
    psym = place_symbol(key) if key in ETORO_PLACE_OVERRIDES else place_symbol(symbol)
    res = {"symbol": symbol, "quote": quote, "ref_close": ref_close, "max_dev_pct": max_dev_pct,
           "expected_instrumentId": exp_map if exp_map is not None else exp_row,
           "screener_row_instrumentId": exp_row, "instrumentId_seen": seen,
           "quote_instrumentId": qid, "quote_symbol": quote_symbol, "place_symbol": psym,
           "cache_symbol_for_id": cache_symbol_for_id(seen)}

    def refuse(code, why):
        return {**res, "ok": False, "code": code, "rationale": f"{symbol}: {why} -> refuse"}

    if seen is None:
        return refuse("INSTRUMENT_ID_REQUIRED", "--instrument-id is required for every symbol")
    if qid is None or not quote_symbol:
        return refuse("QUOTE_ID_MISMATCH", "--quote-instrument-id and --quote-symbol (live quote market.instrumentId / "
                                           "market.symbol) are required")
    for label, i in (("--instrument-id", seen), ("live quote id", qid), ("screener row id", exp_row)):
        mm = id_symbol_mismatch(key, i) if i is not None else None
        if mm:
            return {**refuse("ID_SYMBOL_MISMATCH", f"{label}: {mm}"), "rationale": f"{symbol} ({label}): {mm}"}
    if cache_symbol_for_id(seen) is None:
        return refuse("INSTRUMENT_ID_UNVERIFIED", f"instrumentId {seen} is not in the instrument cache / map (fail closed)")
    ref_id = exp_row if exp_row is not None else exp_map
    if ref_id is None:
        return refuse("INSTRUMENT_ID_UNVERIFIED", "no screener-row etoro_instrument_id (fail closed)")
    if not (qid == ref_id == seen):
        return refuse("QUOTE_ID_MISMATCH", f"live quote id {qid} / screener row id {ref_id} / --instrument-id {seen} differ")
    if str(quote_symbol).strip().upper() != str(psym).upper():
        return refuse("QUOTE_ID_MISMATCH", f"live quote symbol {quote_symbol!r} != place symbol {psym!r}")
    if exp_map is not None and seen != exp_map:
        return refuse("SYMBOL_MAP_MISMATCH", f"instrumentId {seen} != mapped {exp_map}")
    try:
        q, r = float(quote), float(ref_close)
    except (TypeError, ValueError):
        return refuse("QUOTE_GUARD_INPUT_MISSING", "quote/ref_close missing (fail closed)")
    if q <= 0 or r <= 0:
        return refuse("QUOTE_GUARD_INPUT_MISSING", "non-positive price")
    dev = abs(q / r - 1.0) * 100.0
    res["deviation_pct"] = round(dev, 2)
    if dev > max_dev_pct:
        return {**res, "ok": False, "code": "QUOTE_DEVIATION_GT_20PCT",
                "rationale": f"{symbol}: quote {q} vs screener close {r} = {dev:.1f}% > {max_dev_pct}% "
                             f"(wrong instrument?) -> refuse place"}
    return {**res, "ok": True, "code": "QUOTE_OK", "rationale": f"{symbol}: quote within {dev:.1f}% of close"}


def screener_rows(obj: Any) -> list[dict]:
    """Rows from a screener stdout ({rows}), a screener-run file ({buys, pack, skips}) or a list."""
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    out = []
    for k in ("rows", "buys", "pack", "skips"):
        v = (obj or {}).get(k)
        if isinstance(v, list):
            out += [r for r in v if isinstance(r, dict)]
    return out


def row_for_symbol(rows: Any, symbol: str) -> dict | None:
    want = {symbol, screener_key(symbol)}
    for r in screener_rows(rows):
        if want & {r.get("symbol"), r.get("etoro_symbol"), r.get("yahoo_symbol"), r.get("etoro_place_symbol")}:
            return r
    return None


def ref_close_from_rows(rows: Any, symbol: str) -> float | None:
    r = row_for_symbol(rows, symbol)
    for k in ("price", "current_price", "last_close"):
        if r and r.get(k) is not None:
            return float(r[k])
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="eToro place-symbol map + quote guard + instrumentId cache")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve"); r.add_argument("--symbol", required=True)
    g = sub.add_parser("guard")
    g.add_argument("--symbol", required=True); g.add_argument("--quote", type=float, required=True)
    g.add_argument("--ref-close", type=float); g.add_argument("--screener-rows")
    g.add_argument("--instrument-id", type=int, help="REQUIRED (missing -> exit 3 INSTRUMENT_ID_REQUIRED)")
    g.add_argument("--quote-instrument-id", type=int,
                   help="REQUIRED: live quote instruments[].market.instrumentId (get-instruments-overview)")
    g.add_argument("--quote-symbol", help="REQUIRED: live quote instruments[].market.symbol")
    g.add_argument("--max-dev-pct", type=float, default=MAX_DEV_PCT)
    b = sub.add_parser("build-cache", help="saved get-instruments-overview outputs -> instrument_ids.json")
    b.add_argument("--overview", nargs="+", required=True); b.add_argument("--out", default=str(CACHE_PATH))
    m = sub.add_parser("cache-missing", help="universe symbols with no resolvable instrumentId")
    m.add_argument("--symbols-json", default="/workspace/sp500_symbols.json")
    m.add_argument("--extra", default="", help="comma list, e.g. the ETF universe")
    a = ap.parse_args(argv)
    if a.cmd == "resolve":
        print(json.dumps({"symbol": a.symbol, "place_symbol": place_symbol(a.symbol),
                          "instrumentId": resolve_instrument_id(a.symbol),
                          "override": ETORO_PLACE_OVERRIDES.get(a.symbol)}, indent=2))
        return 0
    if a.cmd == "build-cache":
        c = build_cache(a.overview)
        Path(a.out).write_text(json.dumps(c, indent=1) + "\n")
        print(json.dumps({"out": a.out, "symbols": len(c["symbols"]), "conflicts": c["conflicts"],
                          "not_found": c["not_found"]}))
        return 0
    if a.cmd == "cache-missing":
        try:
            d = json.loads(Path(a.symbols_json).read_text())
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"symbols unreadable: {e}"})); return 2
        syms = d if isinstance(d, list) else d.get("symbols") or []
        syms = list(syms) + [x for x in a.extra.split(",") if x]
        miss = missing_from_cache(syms)
        print(json.dumps({"checked": len(syms), "missing": miss}))
        return 0 if not miss else 1
    ref, row_id = a.ref_close, None
    if a.screener_rows:
        try:
            rows = json.loads(Path(a.screener_rows).read_text())
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"screener rows unreadable: {e}"})); return 2
        row = row_for_symbol(rows, a.symbol) or {}
        row_id = row.get("etoro_instrument_id")
        if ref is None:
            ref = ref_close_from_rows(rows, a.symbol)
    res = quote_guard(a.symbol, a.quote, ref, instrument_id_seen=a.instrument_id, expected_instrument_id=row_id,
                      quote_instrument_id=a.quote_instrument_id, quote_symbol=a.quote_symbol,
                      max_dev_pct=a.max_dev_pct)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())

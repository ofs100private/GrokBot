"""eToro instrument resolution + fail-closed guard for Classic RSI packs.

Every scanned ticker must map to a US stock/ETF eToro instrument before a pack or
proposal may leave this package. Bare tickers can collide with crypto on eToro
(e.g. 'T' = Threshold Network crypto 100528; AT&T is 'T.US' 1030), so the symbol
alone is never trusted: packs carry ``instrumentId`` + ``etoroSymbol``.

Guard (fail closed) — a pack is dropped when:
  * no resolved instrumentId                       -> INSTRUMENT_UNRESOLVED
  * resolved asset class / exchange is crypto      -> INSTRUMENT_CRYPTO
  * resolved instrument is not a US stock/ETF      -> INSTRUMENT_UNRESOLVED (reason not_us_stock_etf)

Map cache: etoro_instrument_map.json (built from read-only user-OfersClaw5 getSecurities).
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

MAP_PATH = Path(__file__).resolve().parent / "etoro_instrument_map.json"

FLAG_UNRESOLVED = "INSTRUMENT_UNRESOLVED"
FLAG_CRYPTO = "INSTRUMENT_CRYPTO"

US_EXCHANGE_IDS = frozenset({4, 5, 20, 57})  # Nasdaq, NYSE, CBOE, Texas SE
CRYPTO_EXCHANGE_IDS = frozenset({8})  # Digital Currency
ALLOWED_TYPES = frozenset({"Stocks", "ETF"})
ALLOWED_ASSET_CLASSES = frozenset({"stock", "etf"})
CRYPTO_WORDS = frozenset({"crypto", "cryptocurrency", "digital currency"})
# 2026-10-16: ONLY these crypto majors are tradable (x1 long). Verified via user-OfersClaw5
# GET /api/v1/market-data/search (xRequestId 93a0dc63-d79a-4005-9e3b-a8de00c5b87d).
# Bare 'T' stays blocked (Threshold crypto 100528); AT&T is T.US 1030.
CRYPTO_MAJORS = {"BTC": 100000, "ETH": 100001, "SOL": 100063}
CRYPTO_MAJOR_IDS = frozenset(CRYPTO_MAJORS.values())
YAHOO_CRYPTO = {k: f"{k}-USD" for k in CRYPTO_MAJORS}


NO_ADD_SYMBOLS = frozenset({"XLE"})  # standing rule: no XLE adds (buys/adds blocked; sells/trims allowed)


def is_no_add_symbol(symbol: Any) -> bool:
    return str(symbol or "").upper().strip() in NO_ADD_SYMBOLS


def crypto_major(symbol: str) -> Optional[str]:
    s = str(symbol or "").upper().strip()
    if s.endswith("-USD"):
        s = s[:-4]
    return s if s in CRYPTO_MAJORS else None


@lru_cache(maxsize=4)
def _load(path_str: str) -> dict[str, Any]:
    return json.loads(Path(path_str).read_text())


def load_map(path: Optional[Path] = None) -> dict[str, Any]:
    """Load the cached instrument map. Missing/unreadable map -> empty (everything unresolved)."""
    p = Path(path) if path else MAP_PATH
    try:
        return _load(str(p))
    except Exception:  # noqa: BLE001
        return {"instruments": {}, "cryptoInstrumentIds": [], "_error": f"map unreadable: {p}"}


def map_meta(path: Optional[Path] = None) -> dict[str, Any]:
    p = Path(path) if path else MAP_PATH
    m = load_map(p)
    sha = None
    try:
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        pass
    return {
        "path": str(p),
        "sha256": sha,
        "asOf": m.get("asOf"),
        "schema": m.get("schema"),
        "resolved": len(m.get("instruments") or {}),
        "error": m.get("_error"),
    }


def _norm(symbol: str) -> str:
    return str(symbol or "").upper().strip()


def resolve(symbol: str, imap: Optional[dict[str, Any]] = None, instrument_id: Any = None) -> Optional[dict[str, Any]]:
    """Return the map entry for a scanned ticker (Yahoo or eToro form), else None.

    Crypto majors resolve ONLY with an explicit matching instrument_id (BTC 100000 / ETH 100001 /
    SOL 100063); a bare 'BTC'/'ETH'/'SOL' never maps to crypto implicitly (QA 2026-10-16)."""
    imap = imap if imap is not None else load_map()
    inst = imap.get("instruments") or {}
    s = _norm(symbol)
    if not s:
        return None
    cm = crypto_major(s)
    try:
        iid_given = None if instrument_id is None or isinstance(instrument_id, bool) else int(instrument_id)
    except (TypeError, ValueError):
        iid_given = None
    if cm and iid_given is not None and iid_given == CRYPTO_MAJORS[cm]:
        return {"symbol": cm, "etoroSymbol": cm, "instrumentId": CRYPTO_MAJORS[cm], "type": "Crypto",
                "assetClass": "crypto", "exchangeId": 8}
    for key in (s, s.replace(".", "-")):
        if key in inst:
            return dict(inst[key])
    # eToro-form lookup (T.US, BRK.B)
    for v in inst.values():
        if _norm(v.get("etoroSymbol")) == s:
            return dict(v)
    return None


def check_entry(entry: Optional[dict[str, Any]], imap: Optional[dict[str, Any]] = None) -> tuple[bool, Optional[str], str]:
    """Apply the fail-closed guard to a resolved entry. Returns (ok, flag, reason)."""
    imap = imap if imap is not None else load_map()
    if not entry:
        return False, FLAG_UNRESOLVED, "no map entry"
    iid = entry.get("instrumentId")
    try:
        iid = int(iid)
    except (TypeError, ValueError):
        return False, FLAG_UNRESOLVED, "no resolved instrumentId"
    crypto_ids = {int(x) for x in (imap.get("cryptoInstrumentIds") or [])}
    typ = str(entry.get("type") or "")
    ac = str(entry.get("assetClass") or "").lower()
    try:
        exch = int(entry.get("exchangeId"))
    except (TypeError, ValueError):
        exch = None
    if (iid in CRYPTO_MAJOR_IDS and ac == "crypto"
            and CRYPTO_MAJORS.get(str(entry.get("etoroSymbol") or "").upper()) == iid):
        return True, None, "ok (crypto major)"
    if (
        iid in crypto_ids
        or typ.lower() in CRYPTO_WORDS
        or ac in CRYPTO_WORDS
        or exch in CRYPTO_EXCHANGE_IDS
    ):
        return False, FLAG_CRYPTO, f"resolved instrument {iid} is crypto"
    if typ not in ALLOWED_TYPES or ac not in ALLOWED_ASSET_CLASSES or exch not in US_EXCHANGE_IDS:
        return False, FLAG_UNRESOLVED, f"not_us_stock_etf (type={typ or None} assetClass={ac or None} exchangeId={exch})"
    if not entry.get("etoroSymbol"):
        return False, FLAG_UNRESOLVED, "no etoroSymbol"
    return True, None, "ok"


def guard_symbol(symbol: str, imap: Optional[dict[str, Any]] = None, instrument_id: Any = None) -> dict[str, Any]:
    """Resolve + guard one ticker. Always returns a dict with ok/flag/reason/instrument fields.
    Pass instrument_id for crypto majors (required) or to pin a stock id."""
    imap = imap if imap is not None else load_map()
    entry = resolve(symbol, imap, instrument_id=instrument_id)
    ok, flag, reason = check_entry(entry, imap)
    return {
        "symbol": _norm(symbol),
        "ok": ok,
        "flag": flag,
        "reason": reason,
        "instrumentId": (entry or {}).get("instrumentId") if ok else None,
        "etoroSymbol": (entry or {}).get("etoroSymbol") if ok else None,
        "assetClass": (entry or {}).get("assetClass") if ok else None,
        "type": (entry or {}).get("type") if ok else None,
        "exchangeId": (entry or {}).get("exchangeId") if ok else None,
        "resolvedEntry": entry,
    }


def guard_items(items: list[dict[str, Any]], kind: str, imap: Optional[dict[str, Any]] = None,
                symbol_getter=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split packs/notes into (kept, dropped). Kept items get instrumentId/etoroSymbol stamped.

    A pack that already carries an instrumentId is re-checked against that id (it must match
    the map entry for its symbol) so a stale/crypto id can never pass.
    """
    imap = imap if imap is not None else load_map()
    get_sym = symbol_getter or (lambda it: (it.get("instrument") or {}).get("symbol") or it.get("symbol"))
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for it in items:
        sym = get_sym(it)
        carried = (it.get("instrument") or {}).get("instrumentId", it.get("instrumentId"))
        g = guard_symbol(sym, imap, instrument_id=carried if crypto_major(sym) else None)
        if g["ok"] and carried is not None:
            try:
                carried_i = int(carried)
            except (TypeError, ValueError):
                carried_i = None
            if carried_i != int(g["instrumentId"]):
                crypto_ids = {int(x) for x in (imap.get("cryptoInstrumentIds") or [])}
                g = {**g, "ok": False,
                     "flag": FLAG_CRYPTO if carried_i in crypto_ids else FLAG_UNRESOLVED,
                     "reason": f"carried instrumentId {carried} != resolved {g['instrumentId']}"}
        if not g["ok"]:
            dropped.append({"kind": kind, "symbol": g["symbol"], "flag": g["flag"],
                            "reason": g["reason"], "carriedInstrumentId": carried,
                            "item": {**it, "status": f"DROPPED_{g['flag']}", "do_not_place": True}})
            continue
        it = dict(it)
        if isinstance(it.get("instrument"), dict):
            it["instrument"] = {**it["instrument"], "instrumentId": g["instrumentId"],
                                "etoroSymbol": g["etoroSymbol"], "assetClass": g["assetClass"],
                                "exchangeId": g["exchangeId"]}
        it["instrumentId"] = g["instrumentId"]
        it["etoroSymbol"] = g["etoroSymbol"]
        kept.append(it)
    return kept, dropped

"""Offline tests for the eToro instrument map + fail-closed guard (no network, no audit writes).

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_instruments
"""

from __future__ import annotations

from .instruments import (FLAG_CRYPTO, FLAG_UNRESOLVED, check_entry, guard_items,
                          guard_symbol, load_map, resolve)
from .propose import _instrument_block


def _pack(symbol, instrument=None):
    return {"action": "CANDIDATE_LONG", "side": "buy", "leverage": 1,
            "instrument": instrument or _instrument_block(symbol), "do_not_place": True}


def run() -> list[tuple[str, bool, str]]:
    imap = load_map()
    out: list[tuple[str, bool, str]] = []

    def t(name, cond, detail=""):
        out.append((name, bool(cond), detail))

    # 1) T resolves to AT&T T.US / 1030 (not Threshold crypto 100528)
    e = resolve("T", imap)
    t("T resolves to 1030 / T.US", e and e["instrumentId"] == 1030 and e["etoroSymbol"] == "T.US", str(e))
    g = guard_symbol("T", imap)
    t("T passes guard", g["ok"] and g["instrumentId"] == 1030, f"{g['flag']} {g['reason']}")
    t("T.US (eToro form) resolves to 1030", (resolve("T.US", imap) or {}).get("instrumentId") == 1030)
    t("CVX -> CVX.US 1014", (resolve("CVX", imap) or {}).get("instrumentId") == 1014)
    t("DIA -> DIA.US 3026 ETF", (resolve("DIA", imap) or {}).get("instrumentId") == 3026)
    kept, dropped = guard_items([_pack("T")], "buy_pack", imap)
    t("T pack kept with instrumentId+etoroSymbol",
      len(kept) == 1 and kept[0]["instrumentId"] == 1030 and kept[0]["etoroSymbol"] == "T.US"
      and kept[0]["instrument"]["instrumentId"] == 1030, str(kept[:1]))

    # 2) Crypto id rejected
    ok, flag, why = check_entry({"instrumentId": 100528, "etoroSymbol": "T", "type": "Stocks",
                                 "assetClass": "stock", "exchangeId": 5}, imap)
    t("crypto id 100528 rejected even if labelled stock", not ok and flag == FLAG_CRYPTO, why)
    ok, flag, why = check_entry({"instrumentId": 999999, "etoroSymbol": "XYZCOIN", "type": "Crypto",
                                 "assetClass": "crypto", "exchangeId": 8}, imap)
    t("type Crypto / exchange 8 rejected", not ok and flag == FLAG_CRYPTO, why)
    bad = _pack("T", {"symbol": "T", "instrumentId": 100528, "etoroSymbol": "T"})
    kept, dropped = guard_items([bad], "buy_pack", imap)
    t("T pack carrying crypto id 100528 dropped INSTRUMENT_CRYPTO",
      not kept and dropped and dropped[0]["flag"] == FLAG_CRYPTO, str([d["reason"] for d in dropped]))

    # 3) Unmapped ticker dropped
    kept, dropped = guard_items([_pack("ZZZZQ")], "buy_pack", imap)
    t("unmapped ZZZZQ dropped INSTRUMENT_UNRESOLVED",
      not kept and dropped and dropped[0]["flag"] == FLAG_UNRESOLVED, str([d["reason"] for d in dropped]))
    kept, dropped = guard_items([_pack("VYLR")], "buy_pack", imap)
    t("ambiguous VYLR dropped INSTRUMENT_UNRESOLVED", not kept and dropped and dropped[0]["flag"] == FLAG_UNRESOLVED)
    ok, flag, why = check_entry({"instrumentId": 1234, "etoroSymbol": "BARC.L", "type": "Stocks",
                                 "assetClass": "stock", "exchangeId": 7}, imap)
    t("non-US exchange rejected", not ok and flag == FLAG_UNRESOLVED, why)
    ok, flag, why = check_entry({"etoroSymbol": "SPY", "type": "ETF", "assetClass": "etf", "exchangeId": 5}, imap)
    t("missing instrumentId rejected", not ok and flag == FLAG_UNRESOLVED, why)
    kept, dropped = guard_items([{"symbol": "ZZZZQ", "action": "RISK_OFF"}], "risk_off", imap)
    t("unmapped risk_off note dropped", not kept and dropped and dropped[0]["flag"] == FLAG_UNRESOLVED)

    # Book names resolve to the live-book instruments
    for sym, iid in (("QQQ", 3006), ("SMH", 6357), ("XLV", 3017), ("SPY", 3000), ("TMO", 1592)):
        t(f"book {sym} -> {iid}", (resolve(sym, imap) or {}).get("instrumentId") == iid)
    # No mapped instrument is a crypto id / crypto exchange
    crypto_ids = set(imap.get("cryptoInstrumentIds") or [])
    leaks = [k for k, v in (imap.get("instruments") or {}).items()
             if v["instrumentId"] in crypto_ids or v.get("exchangeId") == 8 or v.get("type") not in ("Stocks", "ETF")]
    t("no crypto/non-stock entries in map", not leaks, str(leaks))
    return out


def main() -> int:
    res = run()
    for name, ok, detail in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail else ""))
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

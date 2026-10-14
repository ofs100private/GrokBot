"""Offline tests for fix9: cash floor fails closed when summary.availableCash is missing.

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_cash_floor
No network, no eToro, no audit writes (propose/staleness/market-hours are stubbed).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import auto_1h as A
from . import book_sleeves as B

PACK = {"instrument": {"symbol": "TST", "instrumentId": 1, "assetClass": "stock"}, "side": "buy",
        "leverage": 1, "status": "OK", "cost_gate": {"verdict": "COST_GATE_GO"}}


def _snap(d: dict) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(d, f)
    f.close()
    return Path(f.name)


def run() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def t(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    pos = [{"symbol": "SPY", "value": 700.0, "invested": 700.0}]
    # --- load_book_symbols strictness
    _, c, _ = A.load_book_symbols(_snap({"positions": pos, "cash": 3816.07, "equity": 7243.35}))
    t("top-level cash only -> None (no permissive fallback)", c is None, str(c))
    _, c, _ = A.load_book_symbols(_snap({"positions": pos, "summary": {"availableCash": 3816.07}}))
    t("summary.availableCash read", c == 3816.07, str(c))
    for bad in (None, "x", float("nan"), float("inf"), -5, True, [1]):
        _, c, _ = A.load_book_symbols(_snap({"positions": pos, "summary": {"availableCash": bad}}))
        t(f"invalid availableCash {bad!r} -> None", c is None, str(c))
    _, c, _ = A.load_book_symbols(_snap({"positions": pos, "summary": "oops"}))
    t("non-dict summary -> None", c is None, str(c))

    # --- mandate_gate
    o_we, o_rth = A.is_weekend_idt, A.is_us_rth
    A.is_weekend_idt, A.is_us_rth = (lambda: False), (lambda: True)
    try:
        g = A.mandate_gate(force=False, cash=None)
        t("gate blocks on missing cash", "available_cash_missing" in g["blocks"] and not g["allow_new_buys"], str(g))
        g = A.mandate_gate(force=True, cash=None)
        t("--force does not bypass missing cash", "available_cash_missing" in g["blocks"] and not g["allow_new_buys"], str(g))
        g = A.mandate_gate(force=False, cash=3816.07)
        t("gate clear with cash above floor", g["blocks"] == [] and g["allow_new_buys"] and g["available_cash"] == 3816.07, str(g))
        g = A.mandate_gate(force=False, cash=2400.0)
        t("cash below floor still blocks", "cash_below_floor" in g["blocks"], str(g))

        # --- run_auto_1h end-to-end with stubs
        o_load, o_stale, o_prop, o_guard = A.load_book_symbols, A.book_snapshot_staleness, A.propose_from_symbols, A.guard_symbol
        A.book_snapshot_staleness = lambda *a, **k: None
        A.propose_from_symbols = lambda **k: {"buy_packs": [dict(PACK)], "risk_off": [], "instrument_dropped": []}
        A.guard_symbol = lambda s: {"ok": True, "flag": None, "reason": None, "etoroSymbol": s, "instrumentId": 1,
                                    "assetClass": "stock", "exchangeId": 4}
        o_audit, o_latest = A.append_audit, A.LATEST_AUTO
        A.append_audit = lambda *a, **k: {"skipped": "test"}
        A.LATEST_AUTO = Path(tempfile.mkdtemp()) / "latest-auto.json"
        try:
            for force in (False, True):
                A.load_book_symbols = lambda *a, **k: (["SPY"], None, {})
                env = A.run_auto_1h(symbols=["TST"], dry_run=False, force=force)
                eligible = [p for p in env["buy_packs"] if p.get("auto_place_eligible")]
                t(f"missing cash (force={force}): hard flag AVAILABLE_CASH_MISSING",
                  A.CASH_MISSING_FLAG in env["flags"], str(env["flags"]))
                t(f"missing cash (force={force}): status GATED, no buy packs, none eligible",
                  env["status"] == "GATED" and env["buy_packs"] == [] and not eligible and env["auto_place_eligible_count"] == 0,
                  f"{env['status']} {len(env['buy_packs'])}")
                t(f"missing cash (force={force}): mandate_gates.available_cash None + blocked",
                  env["mandate_gates"]["available_cash"] is None and "available_cash_missing" in env["mandate_gates"]["blocks"])
            A.load_book_symbols = lambda *a, **k: (["SPY"], 3816.07, {"availableCash": 3816.07})
            env = A.run_auto_1h(symbols=["TST"], dry_run=False)
            t("cash present: PROPOSE, no cash flag, available_cash populated",
              env["status"] == "PROPOSE" and A.CASH_MISSING_FLAG not in env["flags"]
              and env["mandate_gates"]["available_cash"] == 3816.07 and len(env["buy_packs"]) == 1,
              f"{env['status']} {env['flags']}")
        finally:
            A.load_book_symbols, A.book_snapshot_staleness, A.propose_from_symbols, A.guard_symbol = o_load, o_stale, o_prop, o_guard
            A.append_audit, A.LATEST_AUTO = o_audit, o_latest
    finally:
        A.is_weekend_idt, A.is_us_rth = o_we, o_rth

    # --- book writer (book_sleeves.ensure_summary)
    b = B.ensure_summary({"cash": 3816.07, "equity": 7243.35, "positions": pos})
    t("writer adds summary.availableCash/equity from top-level",
      b["summary"]["availableCash"] == 3816.07 and b["summary"]["equity"] == 7243.35, str(b.get("summary")))
    b = B.ensure_summary({"cash": 1.0, "equity": 2.0, "summary": {"availableCash": 3816.07, "equity": 7243.35, "note": "k"}})
    t("writer keeps existing summary values + other keys",
      b["summary"]["availableCash"] == 3816.07 and b["summary"]["equity"] == 7243.35 and b["summary"]["note"] == "k")
    try:
        B.ensure_summary({"positions": pos})
        t("writer refuses book with no cash/equity", False)
    except ValueError:
        t("writer refuses book with no cash/equity", True)
    real = json.loads(Path("/workspace/classic-portfolio-for-app.json").read_text())
    real.pop("summary", None)
    try:
        r = B.recompute(real)
        _, c, _ = A.load_book_symbols(_snap(r))
        t("recompute() output passes auto_1h strict cash read", c is not None and r["summary"]["equity"] > 0, str(c))
    except Exception as e:  # noqa: BLE001
        t("recompute() output passes auto_1h strict cash read", False, repr(e))
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

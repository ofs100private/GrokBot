"""Offline tests for Ofer's 2026-10-16 rule update (24x5 + crypto 24/7, 4 trades/day, caps, crypto, TP).

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_rules_20261016  (never calls eToro)
"""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import auto_1h as A
from . import execute_pass as X
from . import trade_counter as TC
from .instruments import guard_symbol, resolve
from .market_hours import extended_session, trading_window
from .propose import auto_place_eligibility

ET = ZoneInfo("America/New_York")
IDT = ZoneInfo("Asia/Jerusalem")


def run():
    out = []
    t = lambda n, ok, d="": out.append((n, bool(ok), d))  # noqa: E731
    # --- windows
    t("24x5 open Tue 03:00 ET (overnight)", extended_session(datetime(2026, 10, 13, 3, 0, tzinfo=ET))["open"])
    t("24x5 open Tue 18:30 ET (after-hours)", extended_session(datetime(2026, 10, 13, 18, 30, tzinfo=ET))["open"])
    t("24x5 closed Sat", not extended_session(datetime(2026, 10, 17, 12, 0, tzinfo=ET))["open"])
    t("24x5 closed Sun 19:00 ET", not extended_session(datetime(2026, 10, 18, 19, 0, tzinfo=ET))["open"])
    t("24x5 open Sun 21:00 ET", extended_session(datetime(2026, 10, 18, 21, 0, tzinfo=ET))["open"])
    t("24x5 closed Fri 20:30 ET", not extended_session(datetime(2026, 10, 16, 20, 30, tzinfo=ET))["open"])
    t("24x5 closed Thanksgiving", not extended_session(datetime(2026, 11, 26, 12, 0, tzinfo=ET))["open"])
    t("24x5 closed eve-of-holiday overnight (Wed 21:00 ET before Thanksgiving)",
      not extended_session(datetime(2026, 11, 25, 21, 0, tzinfo=ET))["open"])
    t("24x5 unknown year fails closed", not extended_session(datetime(2028, 1, 4, 12, 0, tzinfo=ET))["open"])
    sat = datetime(2026, 10, 17, 12, 0, tzinfo=ET)
    t("crypto open Saturday", trading_window("crypto", sat)["open"])
    t("stock closed Saturday", not trading_window("stock", sat)["open"])
    t("RTH fallback when no extended support (Tue 18:30 ET closed)",
      not trading_window("stock", datetime(2026, 10, 13, 18, 30, tzinfo=ET), supports_extended=False,
                         instrument_is_open=True)["open"])
    t("instrument isOpen=False wins", not trading_window("crypto", sat, instrument_is_open=False)["open"])
    tue = datetime(2026, 10, 13, 3, 0, tzinfo=ET)
    t("stock in 24x5 window but isOpen unknown => CLOSED (fail-safe)", not trading_window("stock", tue)["open"])
    t("stock in 24x5 window with live isOpen=True => open", trading_window("stock", tue, instrument_is_open=True)["open"])
    t("unknown asset class closed", not trading_window(None, sat)["open"])
    # --- crypto instruments
    for s, i in (("BTC", 100000), ("ETH", 100001), ("SOL", 100063), ("BTC-USD", 100000)):
        g = guard_symbol(s, instrument_id=i)
        t(f"crypto major {s} -> {i}", g["ok"] and g["instrumentId"] == i, g)
    t("bare T is NOT a crypto major / stays AT&T or blocked", (resolve("T") or {}).get("instrumentId") != 100528
      or not guard_symbol("T")["ok"])
    t("DOGE blocked", not guard_symbol("DOGE")["ok"])
    t("SOLV not treated as SOL", (resolve("SOLV") or {}).get("instrumentId") != 100063)
    # --- caps / floor
    t("stock cap 20%", X.NAME_CAP["stock"] == 0.20)
    t("ETF cap 35%", X.NAME_CAP["etf"] == 0.35)
    t("sleeve cap 45%", X.SLEEVE_CAP == 0.45)
    t("crypto sleeve cap 15%", X.sleeve_cap("crypto") == 0.15 and X.sleeve_cap("growth_tech") == 0.45)
    t("cash floor 1500 (execute_pass + auto_1h)", X.CASH_FLOOR_USD == 1500.0 and A.CASH_FLOOR_USD == 1500.0)
    t("crypto majors mapped to crypto sleeve", all(X.DEFAULT_SLEEVES[s] == "crypto" for s in ("BTC", "ETH", "SOL")))
    # --- daily counter (test mode root; details in test_regression_20261016)
    import os
    from .paths import TEST_ENV
    saved = os.environ.get(TEST_ENV)
    os.environ[TEST_ENV] = tempfile.mkdtemp()
    os.environ.pop(TC.ENV_OVERRIDE, None)
    try:
        now = datetime(2026, 10, 16, 10, 0, tzinfo=IDT)
        t("counter empty -> 4 remaining", TC.status(now)["remaining"] == 4)
        for k_ in range(4):
            st = TC.reserve(f"S{k_}", "S", now=now)
        t("after 4 reserves -> limit reached", not TC.status(now)["ok"])
        t("5th reserve refused", TC.reserve("S9", "S", now=now)["reservation"] is None)
        t("next IDT day resets", TC.status(datetime(2026, 10, 17, 0, 1, tzinfo=IDT))["ok"])
        t("external opens (book+history) 4 -> blocked", not TC.status(datetime(2026, 10, 18, 9, 0, tzinfo=IDT),
                                                                  external_position_ids=["p1", "p2", "p3", "p4"])["ok"])
        bad = TC.counter_path()[0]
        bad.write_text("{not json")
        t("unreadable counter fails closed", not TC.status(now)["ok"])
    finally:
        if saved is None:
            os.environ.pop(TEST_ENV, None)
        else:
            os.environ[TEST_ENV] = saved
    # --- mandatory TP
    c = X._Ctx(now)
    X._tp_check(c, "", None, 90.0, 100.0)
    t("TP missing -> TAKE_PROFIT_MISSING", "TAKE_PROFIT_MISSING" in c.blockers)
    c = X._Ctx(now)
    X._tp_check(c, "", 101.0, 90.0, 100.0)
    t("TP with R:R 0.1 -> REWARD_RISK_TOO_LOW", "REWARD_RISK_TOO_LOW" in c.blockers)
    c = X._Ctx(now)
    X._tp_check(c, "", 115.0, 90.0, 100.0)
    t("TP R:R 1.5 passes", not c.blockers, c.blockers)
    pack = {"instrument": {"symbol": "BTC", "instrumentId": 100000}, "side": "buy", "action": "CANDIDATE_LONG",
            "leverage": 1, "cost_gate": {"verdict": "COST_GATE_PASS"}, "levels": {"entry": 100, "stop_loss": 90}}
    ok, why = auto_place_eligibility(pack)
    t("auto_place: pack without TP not eligible", not ok and "TAKE_PROFIT_OR_STOP_MISSING" in why, why)
    # --- mandate gate daily limit never bypassed by --force
    o = A.daily_budget
    A.daily_budget = lambda: {"ok": False, "remaining": 0}
    try:
        g = A.mandate_gate(force=True, cash=5000.0)
        t("daily limit blocks even with --force", "daily_new_trade_limit" in g["blocks"] and not g["allow_new_buys"], g)
    finally:
        A.daily_budget = o
    g = A.mandate_gate(force=False, cash=5000.0)
    t("crypto window always allowed in mandate gate", g["allow_crypto_buys"] is True)
    return out


def main() -> int:
    res = run()
    for n, ok, d in res:
        print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  [{d}]" if not ok and d != "" else ""))
    nf = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - nf}/{len(res)} passed")
    return 1 if nf else 0


if __name__ == "__main__":
    raise SystemExit(main())

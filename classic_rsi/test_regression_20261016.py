"""Regression suite on the NEW 2026-10-16 limits (floor $1,500, stock 20% / ETF 35% / crypto sleeve 15%)
plus QA fix1 items: atomic counter + reserve/mark/release, pinned counter path, trading-history count,
NO_XLE_ADDS, fail-safe isOpen, explicit crypto ids, crypto SL/cost floors. Test mode only; never calls eToro.

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_regression_20261016
"""
from __future__ import annotations

import multiprocessing as mp
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import cost_gate as CG
from . import execute_pass as X
from . import trade_counter as TC
from .instruments import guard_symbol
from .levels import crypto_long_levels
from .market_hours import trading_window
from .paths import TEST_ENV
from .propose import auto_place_eligibility
from .testkit import (MON, RID, buy_prepare, make_pack, test_root, ts, write_book, write_envelope, write_history,
                      write_order_qa, write_run_qa, write_scores)
from .test_execute_pass import rsi, rsi_ready  # noqa: F401  (decorated run_checks: momentum read + isOpen)

IDT = ZoneInfo("Asia/Jerusalem")


def _reserve_worker(args):
    root, key = args
    os.environ[TEST_ENV] = root
    os.environ.pop(TC.ENV_OVERRIDE, None)
    r = TC.reserve(key, "S", now=MON)
    return r.get("reservation")


def run():
    out = []
    t = lambda n, ok, d="": out.append((n, bool(ok), d))  # noqa: E731
    assert X.CASH_FLOOR_USD == 1500.0 and X.NAME_CAP["stock"] == 0.20 and X.NAME_CAP["etf"] == 0.35
    with test_root() as root:
        os.environ.pop(TC.ENV_OVERRIDE, None)
        T = make_pack("T", entry=27.0, atr=0.5, notional=1000)
        write_envelope(root, [T, make_pack("XLE", entry=95.0, atr=1.9)])
        write_book(root)
        write_scores(root)
        write_run_qa()
        # --- counter: atomic concurrent reserve (8 processes, cap 4)
        with mp.get_context("fork").Pool(8) as pool:
            got = pool.map(_reserve_worker, [(str(root), f"k{i}") for i in range(8)])
        ok = [g for g in got if g]
        t("8 concurrent reserves -> exactly 4 slots (flock)", len(ok) == 4 and len(set(ok)) == 4, got)
        st = TC.status(MON)
        t("status after concurrent reserves: 4 reserved, limit reached", st["reserved"] == 4 and not st["ok"], st)
        TC.release(ok[0], reason="test failure")
        t("release frees a slot", TC.status(MON)["remaining"] == 1)
        TC.mark(ok[1], position_id=555)
        st = TC.status(MON)
        t("mark keeps slot counted (placed)", st["placed"] == 1 and st["count"] == 3, st)
        try:
            TC.mark(ok[0], position_id=1)
            t("released reservation cannot be marked", False)
        except RuntimeError:
            t("released reservation cannot be marked", True)
        r2 = TC.reserve("k1", "S", now=MON)
        t("reserve idempotent per key (placed k1 returns same id, no extra slot)",
          r2.get("idempotent") and TC.status(MON)["count"] == 3, r2)
        tmp_left = [p for p in (root / "state").iterdir() if p.suffix == ".tmp"]
        t("no leftover tmp files (unique mkstemp + atomic rename)", not tmp_left, tmp_left)
        for rid in ok[2:]:
            TC.release(rid)
        TC.release(r2["reservation"]) if False else None
        # --- env override pinned
        saved = os.environ.pop(TEST_ENV)
        os.environ[TC.ENV_OVERRIDE] = str(root / "fresh.json")
        try:
            s_prod = TC.status(MON)
            r_prod = TC.reserve("x", "S", now=MON)
            t("prod: CLASSIC_TRADE_COUNTER set => fail closed (status + reserve)",
              not s_prod["ok"] and s_prod["error"] == "COUNTER_ENV_OVERRIDE_IN_PRODUCTION" and not r_prod["reservation"])
            t("prod path pinned", TC.counter_path()[0] == TC.PROD_COUNTER_PATH)
        finally:
            os.environ.pop(TC.ENV_OVERRIDE, None)
            os.environ[TEST_ENV] = saved
        # fresh counter file for the GO tests
        (root / "state" / "daily_new_trades.json").unlink(missing_ok=True)
        # --- GO path reserves a slot; NO-GO when budget exhausted
        plan, r, anc = rsi_ready()
        write_order_qa(r)
        fresh = buy_prepare(plan["order_payloads"][0], ask=anc["anchor_ask"], quote_ts=ts(MON, 2))
        g = rsi(prepare_response=fresh, write_lock=True, **anc)
        t("RSI GO reserves a daily slot and returns mark/release instructions",
          g["decision"] == "GO" and g.get("trade_reservation_id") and "mark --reservation" in g.get("after_place", ""),
          g["blockers"])
        t("cash_after >= new floor 1500", g["sizing"]["cash_after_usd"]["anchor"] >= 1500 - 1e-6)
        TC.release(g["trade_reservation_id"], reason="test")
        for p_ in g.get("locks") or []:
            os.unlink(p_)
        # 4 positions opened AND closed today in trading history -> limit
        today = MON.astimezone(ZoneInfo("UTC"))
        write_history(root, items=[{"positionId": 9000 + i, "openTime": (today - timedelta(hours=1)).isoformat(),
                                    "closeTime": today.isoformat()} for i in range(4)])
        g = rsi(prepare_response=fresh, write_lock=True, **anc)
        t("4 opened+closed today in trading history => DAILY_TRADE_LIMIT, no reservation",
          "DAILY_TRADE_LIMIT" in g["blockers"] and not g.get("trade_reservation_id"), g["blockers"])
        (root / "history.json").unlink()
        t("trading history missing => TRADING_HISTORY_MISSING", "TRADING_HISTORY_MISSING" in rsi()["blockers"])
        write_history(root, age_s=3600)
        t("trading history stale => TRADING_HISTORY_MISSING", "TRADING_HISTORY_MISSING" in rsi()["blockers"])
        write_history(root)
        # --- isOpen fail-safe
        t("stock isOpen unknown => INSTRUMENT_OPEN_UNKNOWN", "INSTRUMENT_OPEN_UNKNOWN" in rsi(instrument_is_open=None)["blockers"])
        t("stock isOpen False => INSTRUMENT_CLOSED", "INSTRUMENT_CLOSED" in rsi(instrument_is_open=False)["blockers"])
        t("window: stock None closed / crypto None open",
          not trading_window("stock", MON)["open"] and trading_window("crypto", MON)["open"])
        # --- new caps: stock 20%
        rr = rsi(units=400.0)
        t("stock name cap 20% of total equity (value + cost)", rr["caps_after"]["market_value"]["name_pct"] <= 20 + 1e-6
          and rr["caps_after"]["cost_basis"]["name_pct"] <= 20 + 1e-6 and rr["caps_after"]["name_cap_pct"] == 20.0,
          rr.get("caps_after"))
        write_book(root, cash=1500 + 18 * 27.05, equity=9000)
        rr = rsi(units=40.0)
        t("cash floor 1500: shrink keeps cash_after >= 1500", rr["sizing"]["cash_after_usd"]["anchor"] >= 1500 - 1e-6
          and rr["sizing"]["final_units"] <= 18, rr.get("sizing"))
        write_book(root)
        # --- NO_XLE_ADDS
        xp = f"{RID}#XLE"
        t("RSI XLE buy => NO_XLE_ADDS", "NO_XLE_ADDS" in rsi(pack_id=xp)["blockers"])
        add = {"pack_id": "classic-rebalance-20261012-xle-add", "kind": "rebalance_add",
               "edge_ref": {"evidence_id": "test_rs_oos"},
               "legs": [{"side": "buy", "symbol": "XLE", "instrumentId": 3008, "units": 5.0, "anchor_bid": 94.98,
                         "anchor_ask": 95.0, "open_fee_usd": 0.75, "close_fee_usd": 0.75, "stop_loss": 89.3,
                         "take_profit": 103.0}]}
        pay = {"instrumentId": 3008, "units": 5.0, "stopLossRate": 89.3, "takeProfitRate": 103.0}
        live = {"legs": [{"bid": 94.98, "independent_mark": 95.0, "is_open": True,
                          "prepare_response": buy_prepare(pay, 95.0, ts(MON, 3))}]}
        rb = X.run_rebalance_checks(pack=add, live=live, now=MON, write_lock=False)
        t("rebalance XLE add => NO_XLE_ADDS (NO-GO)", "NO_XLE_ADDS" in rb["blockers"] and rb["decision"] == "NO-GO")
        xpk = make_pack("XLE", entry=95.0, atr=1.9)
        t("propose auto_place: XLE pack blocked", "NO_XLE_ADDS" in auto_place_eligibility(xpk)[1])
        from . import propose as PR
        o = PR.propose_from_bars
        PR.propose_from_bars = lambda sym, df, **k: {"symbol": sym, "buy_packs": [make_pack(sym, entry=95.0, atr=1.9)],
                                                      "risk_off": []}
        try:
            pp = PR.propose_from_symbols(["XLE"], bars_by_symbol={"XLE": None})
        finally:
            PR.propose_from_bars = o
        t("propose drops XLE buy pack (no_add_dropped, not an instrument hard flag)",
          not pp["buy_packs"] and [d["symbol"] for d in pp["no_add_dropped"]] == ["XLE"]
          and "NO_XLE_ADDS" not in (pp.get("instrument_flags") or []), {k: pp.get(k) for k in ("no_add_dropped", "instrument_flags")})
    # --- crypto
    t("bare BTC (no id) does NOT resolve to crypto", not guard_symbol("BTC")["ok"])
    t("BTC with explicit id 100000 ok", guard_symbol("BTC", instrument_id=100000)["ok"])
    t("BTC with wrong id rejected", not guard_symbol("BTC", instrument_id=100001)["ok"])
    t("SOL 100063 / ETH 100001 ok", guard_symbol("SOL", instrument_id=100063)["ok"]
      and guard_symbol("ETH", instrument_id=100001)["ok"])
    lv = crypto_long_levels(100000.0, 300.0)
    t("crypto SL floor 4% when 2.5*ATR small", abs((lv["entry"] - lv["stop_loss"]) - 4000.0) < 1e-6)
    lv = crypto_long_levels(100000.0, 2000.0)
    t("crypto SL = 2.5*ATR in range", abs((lv["entry"] - lv["stop_loss"]) - 5000.0) < 1e-6)
    lv = crypto_long_levels(100000.0, 10000.0)
    t("crypto SL capped at 20%", abs((lv["entry"] - lv["stop_loss"]) - 20000.0) < 1e-6)
    t("crypto TP = 1.5R", abs((lv["take_profit"] - lv["entry"]) - 30000.0) < 1e-6)
    cp = {"levels": crypto_long_levels(100000.0, 300.0), "instrument": {"assetClass": "crypto"},
          "sizing": {"suggested_notional_usd": 1000.0}}
    cg = CG.preliminary_for_pack(cp)
    costs = cg.get("costs") or {}
    t("crypto preliminary cost floor: fee >= 1%/side and spread >= 1%",
      (costs.get("open_fee") or 0) >= 10.0 - 1e-6 and (costs.get("close_fee") or 0) >= 10.0 - 1e-6
      and (cg.get("spread") or costs.get("spread") or 0) >= 10.0 - 1e-6, {"costs": costs, "spread": cg.get("spread")})
    b = X._sl_bounds_ok(95000.0, 100000.0, 2000.0, "crypto")
    t("crypto rebalance SL 5% & >= 1x daily ATR ok", b["ok"], b)
    t("crypto rebalance SL 25% rejected", not X._sl_bounds_ok(75000.0, 100000.0, 2000.0, "crypto")["ok"])
    t("crypto rebalance SL 2% rejected", not X._sl_bounds_ok(98000.0, 100000.0, 500.0, "crypto")["ok"])
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

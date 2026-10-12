"""Offline tests for cost_gate v3 (fix2) + auto_place_eligible stamping. No network.

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_cost_gate
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import cost_gate as C
from .paths import TEST_ENV
from .propose import auto_place_eligibility, stamp_auto_place
from .testkit import EDGE_TEST, make_pack, test_root, write_registries, write_scores

IDT = ZoneInfo("Asia/Jerusalem")
NOW = datetime(2026, 10, 12, 18, 0, tzinfo=IDT)
QTS = (NOW - timedelta(seconds=10)).isoformat()
REF = {"evidence_id": "test_rs_oos"}


def final(**kw):
    base = dict(kind="rsi_buy", entry=27.05, units=20, bid=27.03, ask=27.05, quote_ts=QTS, independent_mark=27.05,
                open_fee_usd=1.0, close_fee_usd=1.0, take_profit=28.05, stop_loss=26.30, stage="final", now=NOW)
    base.update(kw)
    return C.evaluate(**base)


def run():
    out = []

    def t(name, cond, detail=""):
        out.append((name, bool(cond), detail))

    # ---------- production registries (env unset) ----------
    os.environ.pop(TEST_ENV, None)
    pkg = Path(__file__).parent
    reg = json.loads((pkg / "evidence" / "p_registry.json").read_text())
    bt = json.loads((pkg / "backtest-summary-1h.json").read_text())["aggregate"]
    ent = reg["entries"][0]
    t("prod p registry entry == backtest file (12/19, in-sample)", (ent["wins"], ent["n"]) == (bt["wins"], bt["n_trades"])
      and ent["out_of_sample"] is False)
    pi = C.p_from_registry(C.DEFAULT_P_EVIDENCE_ID)
    t("prod p = Wilson lower 0.4104; not usable (in-sample, n<100)", abs(pi["p"] - 0.4104) < 1e-4
      and "P_EVIDENCE_NOT_OUT_OF_SAMPLE" in pi["skip"] and f"P_EVIDENCE_N_LT_{C.P_MIN_N}" in pi["skip"], pi["skip"])
    t("prod registries sha-pinned and match", pi["registry"]["sha256"] == C.P_REGISTRY_SHA256
      and C.load_registry("edge")[1]["sha256"] == C.EDGE_REGISTRY_SHA256)
    cg = final()
    t("QA repro T-like pack (prod) => SKIP", cg["verdict"] == "COST_GATE_SKIP", cg["skip_reasons"])
    try:
        C.evaluate(kind="rsi_buy", entry=27.05, units=20, p_hit=0.99, p_source=".")
        typed = True
    except TypeError:
        typed = False
    t("QA repro p=0.99 source '.': typed p rejected (no parameter)", not typed)
    old = C.P_REGISTRY_SHA256
    C.P_REGISTRY_SHA256 = "0" * 64
    try:
        t("tampered p registry (sha mismatch) => INVALID", final()["verdict"] == "COST_GATE_INVALID"
          and "REGISTRY_SHA_MISMATCH" in final()["errors"])
    finally:
        C.P_REGISTRY_SHA256 = old
    cg = C.evaluate(kind="rebalance_add", entry=95.0, units=6.3, edge_ref={"evidence_id": "anything",
                    "expected_return_pct": 40, "horizon_days": 1})
    t("prod edge registry empty => SKIP; typed er ignored", cg["verdict"] == "COST_GATE_SKIP"
      and "EDGE_EVIDENCE_NOT_IN_REGISTRY" in cg["skip_reasons"]
      and cg["inputs"]["edge"]["ignored_typed_fields"] == ["expected_return_pct"])
    t("mark mandatory at final", "SECOND_SOURCE_MARK_MISSING" in final(independent_mark=None)["errors"])
    t("QA repro stale SMH 601.72 w/o mark => rejected", "SECOND_SOURCE_MARK_MISSING" in C.quote_errors(
        bid=601.5, ask=601.72, quote_ts=QTS, now=NOW))
    t("QA repro SMH 601.72 vs mark 603.28 => rejected", "ASK_VS_MARK_GT_0.1PCT" in C.quote_errors(
        bid=601.5, ask=601.72, quote_ts=QTS, now=NOW, independent_mark=603.28))
    for q, bad in (("2026-10-12T18:00:00", True), ("2026-10-12T15:00:00Z", False), ("2026-10-12T11:00:00-04:00", False),
                   ("2026-10-12T18:00:00+00:00", True), ("2026-10-12T18:00:04+03:00", False),
                   ("2026-10-12T18:00:06+03:00", True)):
        e = C.quote_errors(bid=27.03, ask=27.05, quote_ts=q, now=NOW, independent_mark=27.05)
        t(f"quote_ts {q} {'rejected' if bad else 'ok'}", bool(e) == bad, e)

    # ---------- test registries ----------
    with test_root() as root:
        write_scores(root)
        scores = json.loads((root / "scores.json").read_text())
        cg = final(open_fee_usd=0.75, close_fee_usd=0.75)
        p = C.wilson_lower(130, 200)
        ev = 20 * (p * 1.0 - (1 - p) * 0.75)
        t("RSI EV = units[p(TP-ask) - (1-p)(ask-SL)] with registry p", math.isclose(cg["expected_gain_pre_tax"], round(ev, 4)))
        t("positive EV taxed x0.75; ratio = EV_at / cost", math.isclose(cg["expected_gain"], round(ev * 0.75, 4))
          and math.isclose(cg["ratio"], round(ev * 0.75 / (0.4 + 1.5), 3)), cg["ratio"])
        t("verdict PASS iff ratio >= 2", cg["verdict"] == ("PASS" if ev * 0.75 >= 2 * 1.9 else "COST_GATE_SKIP"))
        t("final block: assumptions [], binding, p evidence recorded", cg["assumptions"] == [] and cg["binding"]
          and cg["inputs"]["p_evidence"]["n"] == 200)
        write_registries(root, p_entries=[dict(id=C.DEFAULT_P_EVIDENCE_ID, wins=60, n=99, out_of_sample=True)])
        t("p evidence n=99 => SKIP", f"P_EVIDENCE_N_LT_{C.P_MIN_N}" in final()["skip_reasons"])
        write_registries(root, p_entries=[dict(id=C.DEFAULT_P_EVIDENCE_ID, wins=86, n=200, out_of_sample=True)])
        t("p at/below break-even => SKIP", "P_AT_OR_BELOW_BREAKEVEN" in final()["skip_reasons"])
        write_registries(root)
        # validation
        t("negative fees => INVALID", final(open_fee_usd=-3, close_fee_usd=-3)["verdict"] == "COST_GATE_INVALID")
        t("bid==ask => INVALID", final(bid=27.05)["verdict"] == "COST_GATE_INVALID")
        t("zero total cost => INVALID", C.evaluate(kind="rsi_buy", entry=27.05, units=20, bid=27.05, ask=27.05,
          spread_usd=0, open_fee_usd=0, close_fee_usd=0, take_profit=28.05, stop_loss=26.3)["verdict"] == "COST_GATE_INVALID")
        t("negative units => INVALID", final(units=-5)["verdict"] == "COST_GATE_INVALID")
        t("final without quote => INVALID", final(bid=None, ask=None)["verdict"] == "COST_GATE_INVALID")
        t("quote 61s old => INVALID", final(quote_ts=(NOW - timedelta(seconds=61)).isoformat())["verdict"] == "COST_GATE_INVALID")
        t("final without getCost fee => INVALID", final(open_fee_usd=None)["verdict"] == "COST_GATE_INVALID")
        t("anchor stage: no freshness needed but fees required", C.evaluate(
            kind="rsi_buy", entry=27.05, units=20, bid=27.03, ask=27.05, open_fee_usd=0.75, close_fee_usd=0.75,
            take_profit=28.05, stop_loss=26.3, stage="anchor")["errors"] == [] and "OPEN_FEE_REQUIRED" in C.evaluate(
            kind="rsi_buy", entry=27.05, units=20, bid=27.03, ask=27.05, close_fee_usd=0.75, take_profit=28.05,
            stop_loss=26.3, stage="anchor")["errors"])
        t("spread = max(spread_usd, (ask-bid) x units)", math.isclose(final(spread_usd=0.01, bid=26.55)["spread"], 10.0))
        # edges
        cg = C.evaluate(kind="rebalance_add", entry=95.0, units=10, bid=94.98, ask=95.0, quote_ts=QTS,
                        independent_mark=95.0, open_fee_usd=0.75, close_fee_usd=0.75, edge_ref=REF, scores=scores,
                        symbol="XLE", stage="final", now=NOW)
        t("add er recomputed from score (0.15 x 20 = 3%)", math.isclose(cg["inputs"]["edge"]["expected_return_pct"], 3.0)
          and math.isclose(cg["expected_gain"], round(950 * 0.03 * 0.75, 4)) and cg["verdict"] == "PASS", cg["expected_gain"])
        write_registries(root, edge_entries=[dict(EDGE_TEST, calibration={"intercept_pct": 0, "per_score_pct": 33333, "score_units": "fraction"})])
        cg = C.evaluate(kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores=scores, symbol="XLE")
        cap = 2 * (1.9 / 95.0 * 100) * math.sqrt(20)
        t("QA repro 5000% edge => capped at 2 x ATR% x sqrt(h)", math.isclose(cg["inputs"]["edge"]["expected_return_pct"], cap)
          and cg["inputs"]["edge"]["new_capped"], cg["inputs"]["edge"].get("expected_return_pct"))
        write_registries(root, edge_entries=[dict(EDGE_TEST, calibration={"intercept_pct": 0, "per_score_pct": 20})])
        t("fix4 units: calibration without score_units='fraction' => SKIP", "EDGE_SCORE_UNITS_NOT_FRACTION" in C.evaluate(
            kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores=scores, symbol="XLE")["skip_reasons"])
        write_registries(root, edge_entries=[dict(EDGE_TEST, calibration={"intercept_pct": 0, "per_score_pct": 0.2, "score_units": "percent"})])
        t("fix4 units: calibration score_units='percent' => SKIP", "EDGE_SCORE_UNITS_NOT_FRACTION" in C.evaluate(
            kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores=scores, symbol="XLE")["skip_reasons"])
        write_registries(root)
        t("fix4 units: score file without score_units='fraction' => SKIP", "SCORE_FILE_UNITS_NOT_FRACTION" in C.evaluate(
            kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores={**scores, "score_units": "pct"},
            symbol="XLE")["skip_reasons"])
        t("fix4 units: prod edge registry declares score_units fraction (sha re-pinned)",
          json.loads((C.Path(C.__file__).parent / "evidence" / "edge_registry.json").read_text()).get("score_units") == "fraction")
        for bad, code in ((dict(EDGE_TEST, n=1), f"EDGE_EVIDENCE_N_LT_{C.EDGE_MIN_N}"),
                          (dict(EDGE_TEST, out_of_sample=False), "EDGE_EVIDENCE_NOT_OUT_OF_SAMPLE"),
                          (dict(EDGE_TEST, horizon_days=1), "EDGE_HORIZON_LT_5D"),
                          (dict(EDGE_TEST, method="trust_me"), "EDGE_METHOD_NOT_ALLOWED")):
            write_registries(root, edge_entries=[bad])
            t(f"QA repro fabricated edge => SKIP ({code})", code in C.evaluate(
                kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores=scores, symbol="XLE")["skip_reasons"])
        write_registries(root)
        t("edge without score row => SKIP", "SCORE_DATA_MISSING_new" in C.evaluate(
            kind="rebalance_add", entry=95.0, units=10, edge_ref=REF, scores=scores, symbol="ZZZ")["skip_reasons"])
        cg = C.evaluate(kind="trim", entry=170.0, units=1, bid=170.0, ask=170.05, quote_ts=QTS, independent_mark=170.02,
                        close_fee_usd=0.75, realized_pnl_usd=40, edge_ref=REF, scores=scores, symbol="XLV",
                        stage="final", now=NOW)
        t("trim: EV = -notional x er_held (XLV -1%), tax 25% on realized", math.isclose(cg["expected_gain"], round(170 * 0.01 * 0.75, 4))
          and math.isclose(cg["tax_est"], 10.0) and cg["costs"]["open_fee"] == 0)
        cg = C.evaluate(kind="sell", entry=600, units=1, realized_pnl_usd=100, close_fee_usd=0.75, risk_exit=True,
                        risk_exit_reason="hard_cap_breach")
        t("self-declared risk exit (not verified) => INVALID", cg["verdict"] == "COST_GATE_INVALID"
          and "RISK_EXIT_NOT_VERIFIED" in cg["errors"])
        cg = C.evaluate(kind="sell", entry=600, units=1, realized_pnl_usd=100, close_fee_usd=0.75, risk_exit=True,
                        risk_exit_reason="stop_hit", risk_exit_verified=True)
        t("verified risk exit => RISK_EXIT, tax recorded", cg["verdict"] == "RISK_EXIT" and math.isclose(cg["tax_est"], 25.0))
        sell = {"symbol": "XLV", "units": 5, "bid": 170.0, "ask": 170.05, "quote_ts": QTS, "independent_mark": 170.02,
                "close_fee_usd": 0.75, "realized_pnl_usd": 40.0}
        buy = {"symbol": "XLE", "units": 8, "bid": 94.98, "ask": 95.0, "quote_ts": QTS, "independent_mark": 95.0,
               "open_fee_usd": 0.75, "close_fee_usd": 0.75}
        cg = C.evaluate_rotation(sell=sell, buy=buy, edge_ref=REF, scores=scores, now=NOW)
        tc = 5 * 0.05 + 0.75 + 10.0 + 8 * 0.02 + 1.5
        t("rotation: one gate, both legs + sell tax", math.isclose(cg["total_cost"], round(tc, 4)) and len(cg["legs"]) == 2)
        t("rotation EV = buy_notional x (3% - (-1%)) after tax", math.isclose(cg["expected_gain"], round(760 * 0.04 * 0.75, 4)))
        # propose integration
        P = make_pack("T", entry=27.0, atr=0.5, notional=1000)
        t("pack prelim uses registry p (test) => PASS, eligible", P["cost_gate"]["verdict"] == "PASS"
          and stamp_auto_place(P)["auto_place_eligible"] is True, P["cost_gate"].get("skip_reasons"))
        t("hard flag / stale / gated / x2 / crypto / missing gate block", all(not stamp_auto_place(x, **k)["auto_place_eligible"]
          for x, k in ((P, {"hard_flags": ["INSTRUMENT_CRYPTO"]}), (P, {"book_stale": True}), (P, {"allow_new_buys": False}),
                       (dict(P, leverage=2), {}), (dict(P, instrument={**P["instrument"], "instrumentId": 100528}), {}),
                       ({k: v for k, v in P.items() if k != "cost_gate"}, {}))))
    os.environ.pop(TEST_ENV, None)
    P = make_pack("SPY", entry=700.0, atr=3.0)
    t("production pack (registry p in-sample) => SKIP, not eligible", P["status"] == "COST_GATE_SKIP"
      and not auto_place_eligibility(P)[0] and P["do_not_place"] is True)
    src = (Path(__file__).parent / "auto_1h.py").read_text()
    t("--force never sets auto eligibility", 'allow_new_buys=bool(gates.get("allow_new_buys")) and not force' in src)
    return out


def main() -> int:
    res = run()
    for name, ok, detail in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail != "" else ""))
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

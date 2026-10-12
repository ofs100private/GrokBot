"""Offline tests for execute_pass v3 (fix2): QA fix1 review items A-L + /tmp/adv.py repros.

Test mode only (CLASSIC_EXEC_TEST_ROOT temp dir); never calls eToro.
Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_execute_pass
"""

from __future__ import annotations

import inspect
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import execute_pass as X
from .market_hours import us_session
from .paths import PROD, TEST_ENV, order_verdict_path, paths, run_verdict_path
from .testkit import (MON, PRID, RID, buy_prepare, close_prepare, make_pack, test_root, ts, write_book,
                      write_envelope, write_order_qa, write_registries, write_run_qa, write_scores)

IDT = ZoneInfo("Asia/Jerusalem")
ET = ZoneInfo("America/New_York")
PID = f"{RID}#T"
XLE, XLV, SMH, TMO = 3008, 3017, 6357, 1592


def rsi(now=MON, **kw):
    base = dict(pack_id=PID, bid=27.03, ask=27.05, quote_ts=ts(now, 5), mark=27.05, units=23.0, open_fee_usd=0.75,
                close_fee_usd=0.75, now=now, write_lock=False)
    base.update(kw)
    return X.run_checks(**base)


def rsi_ready(now=MON, **kw):
    """plan -> prepare: returns (plan, ready_result, anchor kwargs)."""
    plan = rsi(now=now, **kw)
    pay = plan["order_payloads"][0]
    anc = {"anchor_ask": plan["anchor"]["ask"], "anchor_bid": plan["anchor"]["bid"]}
    pr = buy_prepare(pay, ask=anc["anchor_ask"], quote_ts=ts(now, 3))
    r = rsi(now=now, prepare_response=pr, **anc, **kw)
    return plan, r, anc


def run():
    out = []

    def t(name, cond, detail=""):
        out.append((name, bool(cond), detail))

    # ---------- fixed production paths ----------
    os.environ.pop(TEST_ENV, None)
    P = paths()
    t("A: production paths fixed (audit/qa, placed, book, scores)", P["qa_dir"] == PROD["qa_dir"]
      and str(P["qa_dir"]) == "/workspace/classic_rsi/audit/qa" and str(P["lock_dir"]) == "/workspace/classic_rsi/audit/placed"
      and str(P["book"]) == "/workspace/classic-portfolio-for-app.json" and P["account"] == "real" and not P["test_mode"])
    t("A: verdict file names fixed", run_verdict_path(RID).name == f"qa-verdict-run-{RID}.json"
      and order_verdict_path("ab" * 32).name == "qa-verdict-order-abababababababab.json")
    sig = inspect.signature(X.run_checks).parameters
    t("A/E: no audit_dir/book/verdict-path/cash overrides in run_checks", not {"audit_dir", "book_path", "run_qa_verdict",
      "order_qa_verdict", "cash_usd", "p_hit", "p_source"} & set(sig))
    try:
        X.main(["--pack-id", PID, "--audit-dir", "/tmp/x", "--mark", "1"])
        cli_override = True
    except SystemExit:
        cli_override = False
    t("A/E: CLI rejects --audit-dir (QA repro different audit dir)", not cli_override)

    with test_root() as root:
        T = make_pack("T", entry=27.0, atr=0.5, notional=1000)
        write_envelope(root, [T, make_pack("SPY", entry=700.0, atr=3.0)])
        write_book(root)
        write_scores(root)
        write_run_qa()

        # ---------- happy path + K (QA binding to anchor, fresh prepare at GO) ----------
        plan = rsi()
        t("plan: NO-GO PREPARE_RESPONSE_MISSING + ORDER_QA_PENDING", set(plan["blockers"]) == {"PREPARE_RESPONSE_MISSING",
          "ORDER_QA_PENDING"}, plan["blockers"])
        pay = plan["order_payloads"][0]
        t("I: MCP-native buy payload (test mode => account demo)", pay == {"account": "demo", "direction": "buy",
          "instrumentId": 1030, "units": plan["sizing"]["final_units"], "leverage": 1, "orderType": "mkt",
          "stopLossRate": 26.3, "takeProfitRate": 28.05}, pay)
        t("test_mode flagged in output", plan["test_mode"] is True)
        _, r, anc = rsi_ready()
        t("prepare verified -> ready_for_order_qa (only ORDER_QA_PENDING)", r["blockers"] == ["ORDER_QA_PENDING"]
          and r["ready_for_order_qa"], r["blockers"])
        t("prepare token never stored", "SECRET" not in json.dumps(r))
        write_order_qa(r, age_s=14 * 60)
        fresh = buy_prepare(pay, ask=27.07, quote_ts=ts(MON, 2))
        g = rsi(prepare_response=fresh, bid=27.05, ask=None, mark=27.07, write_lock=True, **anc)
        t("K: GO 14 min after QA with a fresh prepare within 0.1% of qa_ask", g["decision"] == "GO", g["blockers"])
        t("K: live cost gate recomputed at fresh quote", g["cost_gate"]["inputs"]["ask"] == 27.07
          and g["cost_gate_anchor"]["inputs"]["ask"] == anc["anchor_ask"])
        t("E: GO writes pack + leg-day locks under fixed lock dir", len(g.get("locks", [])) == 2
          and all(l.startswith(str(root / "audit" / "placed")) for l in g["locks"]))
        g2 = rsi(prepare_response=fresh, bid=27.05, ask=None, mark=27.07, **anc)
        t("E: second run => ALREADY_GO_LOCKED", "ALREADY_GO_LOCKED" in g2["blockers"])
        for bad in (f"{RID}#t", f"{RID}# T", f" {RID}#T", f"{RID}#T ", "classic-rsi-auto-x#T"):
            t(f"E: QA repro pack_id {bad!r} => BAD_PACK_ID", rsi(pack_id=bad)["blockers"] == ["BAD_PACK_ID"])
        for f in (root / "audit" / "placed").glob("*.lock"):
            f.unlink()

        far = buy_prepare(pay, ask=27.09, quote_ts=ts(MON, 2))
        t("K: fresh ask > 0.1% from qa_ask => ANCHOR_DRIFT", "ANCHOR_DRIFT" in rsi(prepare_response=far, mark=27.09, **anc)["blockers"])

        # ---------- A: verdict forgery / binding ----------
        _, r, anc = rsi_ready()
        write_order_qa(r, checker="Trader_Classic (self)")
        t("A: QA repro self-written verdict (checker != 'QA Bot') => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        write_order_qa(r, recomputed_cost_gate=None)
        t("A: verdict without recomputed_cost_gate => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        rc = {k: r["cost_gate_anchor"][k] for k in X.RECOMPUTED_FIELDS}
        rc["total_cost"] = rc["total_cost"] + 0.02
        write_order_qa(r, recomputed_cost_gate=rc)
        t("A: recomputed numbers off by 0.02 => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        write_order_qa(r, qa_ask=27.00)
        t("A/K: verdict qa_ask != anchor => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        write_order_qa(r, age_s=16 * 60)
        t("order-QA 16 min old => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        write_order_qa(r, skill="classic-rsi-1h-run-qa")
        t("order-QA wrong skill => NO-GO", "ORDER_QA_NOT_PASS" in rsi(
            prepare_response=buy_prepare(pay, anc["anchor_ask"], ts(MON, 2)), **anc)["blockers"])
        order_verdict_path(r["pack_sha256"]).unlink()
        write_run_qa(checker="Trader_Classic (self)")
        t("A: forged run-QA (checker) => RUN_QA_NOT_PASS", "RUN_QA_NOT_PASS" in rsi()["blockers"])
        write_run_qa(age_s=61 * 60)
        t("run-QA 61 min old => NO-GO", "RUN_QA_NOT_PASS" in rsi()["blockers"])
        run_verdict_path(RID).write_text(json.dumps({"verdict": "PASS", "run_id": PRID, "symbol": "T",
                                                     "created": "2025-01-01", "checker": "QA Bot",
                                                     "checked_at": "2025-01-01T10:00:00+02:00", "skill": X.RUN_QA_SKILL}))
        t("QA repro 2025 PASS file => NO-GO", "RUN_QA_NOT_PASS" in rsi()["blockers"])
        write_run_qa()

        # ---------- I: prepare mismatch ----------
        for k, v, code in (("units", 22.0, "PREPARE_UNITS"), ("direction", "sellShort", "DIRECTION"),
                           ("leverage", 2, "LEVERAGE"), ("stopLossRate", 1.0, "SL"), ("instrumentId", 100528, "INSTRUMENT"),
                           ("verdict", "rejected", "NOT_READY"), ("orderType", "limitIOC", "ORDER_TYPE")):
            pr = buy_prepare(pay, anc["anchor_ask"], ts(MON, 2), **{k: v})
            rr = rsi(prepare_response=pr, **anc)
            det = next(c["detail"] for c in rr["checks"] if c["name"] == "prepare_matches_payload")
            t(f"I: prepare {k}={v!r} => PREPARE_MISMATCH", "PREPARE_MISMATCH" in rr["blockers"] and any(code in d for d in det), det)
        pr = buy_prepare(pay, 27.04, ts(MON, 2))
        t("I: typed --ask must equal prepare ask", "PREPARE_ASK_MISMATCH" in rsi(prepare_response=pr, ask=27.05, **anc)["blockers"])
        pr = buy_prepare(pay, anc["anchor_ask"], ts(MON, 2), maxStopLossRate=26.0)
        t("J: SL outside prepare stop bounds => NO-GO", "PREPARE_MISMATCH" in rsi(prepare_response=pr, **anc)["blockers"])

        # ---------- D / soft: quote + cash sanity ----------
        t("D: no second-source mark => NO-GO", "QUOTE_INVALID_OR_STALE" in rsi(mark=None)["blockers"])
        t("D: mark 0.2% away => NO-GO", "QUOTE_INVALID_OR_STALE" in rsi(mark=27.11)["blockers"])
        t("stale quote 90s => NO-GO", "QUOTE_INVALID_OR_STALE" in rsi(quote_ts=ts(MON, 90))["blockers"])
        write_book(root, cash=99999)
        t("QA repro cash 99999 > equity => CASH_INSANE", "CASH_INSANE" in rsi()["blockers"])
        write_book(root, age_s=61)
        t("F: book 61s old => BOOK_NOT_LIVE", "BOOK_NOT_LIVE" in rsi()["blockers"])
        write_book(root)
        t("open fee omitted => OPEN_FEE_REQUIRED", "OPEN_FEE_REQUIRED" in rsi(open_fee_usd=None)["blockers"])
        write_book(root, cash=2500 + 18 * 27.05, equity=9000)
        rr = rsi(units=18.0)
        t("QA repro 2499.25: shrink keeps cash_after >= 2500 after fee", rr["sizing"]["cash_after_usd"]["anchor"] >= 2500
          and rr["sizing"]["final_units"] < 18, rr["sizing"])
        write_book(root)
        t("QA repro negative fees => NO-GO", rsi(open_fee_usd=-3, close_fee_usd=-3)["decision"] == "NO-GO")
        mon3 = datetime(2026, 10, 12, 3, 0, tzinfo=IDT)
        write_book(root, now=mon3)
        rr = rsi(now=mon3, quote_ts=ts(mon3, 5))
        t("QA repro Mon 03:00 IDT => market closed", {"WEEKEND", "OUTSIDE_RTH"} & set(rr["blockers"]), rr["blockers"])
        write_book(root)
        t("RTH holiday / early close / unknown year", us_session(datetime(2026, 11, 26, 18, 0, tzinfo=IDT))["reason"] == "US_HOLIDAY"
          and not us_session(datetime(2026, 11, 27, 13, 30, tzinfo=ET))["open"]
          and not us_session(datetime(2028, 1, 3, 11, 0, tzinfo=ET))["open"])
        t("drift > 0.5xATR => DRIFT", "DRIFT" in rsi(bid=27.28, ask=27.30, mark=27.30)["blockers"])
        t("default-SKIP pack => NOT_AUTO_PLACE_ELIGIBLE", "NOT_AUTO_PLACE_ELIGIBLE" in rsi(
            pack_id=f"{RID}#SPY", bid=699.9, ask=700.0, mark=700.0, units=1.0)["blockers"])
        write_book(root, extra=[{"symbol": "T", "instrumentId": 1030, "value": 100.0, "invested": 100.0, "units": 3.0,
                                 "openRate": 27.0, "positionId": 77, "openTime": ts(MON, 3600)}])
        t("F: same-instrument position opened < 24h => DUPLICATE_OPEN_POSITION", "DUPLICATE_OPEN_POSITION" in rsi()["blockers"])
        write_book(root)
        rr = rsi(units=40.0)
        t("caps on market value AND cost basis", rr["caps_after"]["cost_basis"]["name_pct"] <= 15 + 1e-6
          and rr["caps_after"]["market_value"]["name_pct"] <= 15 + 1e-6)

        # ---------- rebalance ----------
        def add_pack(pid="classic-rebalance-20261012-xle-add", units=5.0, sl=89.3, **kw):
            p = {"pack_id": pid, "kind": "rebalance_add", "edge_ref": {"evidence_id": "test_rs_oos"},
                 "legs": [{"side": "buy", "symbol": "XLE", "instrumentId": XLE, "units": units, "anchor_bid": 94.98,
                           "anchor_ask": 95.0, "open_fee_usd": 0.75, "close_fee_usd": 0.75, "stop_loss": sl,
                           "take_profit": None}]}
            p.update(kw)
            return p

        def live_for(pack, payloads=None, ask=95.0, **kw):
            legs = []
            for i, l in enumerate(pack["legs"]):
                if l["side"] == "buy":
                    pay_ = {"instrumentId": l["instrumentId"], "units": X._floor_units(l["units"]),
                            "stopLossRate": l["stop_loss"], "takeProfitRate": l.get("take_profit")}
                    legs.append({"bid": round(ask - 0.02, 4), "independent_mark": ask,
                                 "prepare_response": buy_prepare(pay_, ask, ts(MON, 3))})
                else:
                    full = abs(l["units"] - kw.get("held", {}).get(l["positionId"], -1)) < 1e-9
                    legs.append({"bid": l["anchor_bid"], "ask": l["anchor_ask"], "quote_ts": ts(MON, 3),
                                 "independent_mark": l["anchor_bid"],
                                 "prepare_response": close_prepare({"positionId": l["positionId"],
                                                                    "unitsToDeduct": None if full else l["units"]})})
            return {"legs": legs}

        def rb(pack, live=None, **kw):
            return X.run_rebalance_checks(pack=pack, live=live if live is not None else live_for(pack), now=MON,
                                          write_lock=kw.pop("write_lock", False), **kw)

        p = add_pack()
        r = rb(p)
        t("rebalance add (evidenced edge): ready, MCP payload", r["blockers"] == ["ORDER_QA_PENDING"]
          and r["order_payloads"][0]["direction"] == "buy" and r["order_payloads"][0]["account"] == "demo", r["blockers"])
        write_order_qa(r)
        g = rb(p, write_lock=True)
        t("rebalance GO with QA verdict at fixed path", g["decision"] == "GO", g["blockers"])
        t("fix3 TP: rebalance buy sends takeProfitRate null (schema: number|null, Optional) and reaches GO",
          "takeProfitRate" in g["order_payloads"][0] and g["order_payloads"][0]["takeProfitRate"] is None
          and g["decision"] == "GO", g["order_payloads"])
        lv = live_for(p)
        lv["legs"][0]["prepare_response"]["takeProfitRate"] = 142.5
        t("fix3 TP: payload TP null but prepare echoes a TP => NO-GO",
          rb(p, lv)["decision"] != "GO" and any(x.startswith("PREPARE") for x in rb(p, lv)["blockers"]), rb(p, lv)["blockers"])
        p2 = add_pack(pid="classic-rebalance-20261012-xle-add-b")
        t("E/F: QA repro renamed pack_id same XLE add => locked", {"ALREADY_GO_LOCKED", "SAME_DAY_LEG_LOCKED"} & set(rb(p2)["blockers"]))
        for f in (root / "audit" / "placed").glob("*.lock"):
            f.unlink()
        t("E: free-text rebalance pack_id => BAD_PACK_ID", "BAD_PACK_ID" in rb(add_pack(pid="rb-xle-A"))["blockers"])
        t("J: QA repro SL 0.01 => SL_OUT_OF_BOUNDS", "SL_OUT_OF_BOUNDS" in rb(add_pack(sl=0.01))["blockers"])
        t("J: SL inside 1-3.5x daily ATR band ok", "SL_OUT_OF_BOUNDS" not in rb(add_pack(sl=95.0 - 2 * 1.9))["blockers"])
        t("J: ETF 8% trailing rule ok", "SL_OUT_OF_BOUNDS" not in rb(add_pack(sl=round(95 * 0.92, 2)))["blockers"])
        t("J: SL above ask-1xATR (too tight) => NO-GO", "SL_OUT_OF_BOUNDS" in rb(add_pack(sl=94.5))["blockers"])
        write_registries(root, edge_entries=[])
        rr = rb(add_pack())
        t("C: QA repro fabricated edge (not in registry) => COST_GATE_SKIP", "COST_GATE_SKIP" in rr["blockers"])
        rr = rb(add_pack(edge_ref={"evidence_id": "trust me", "expected_return_pct": 40, "horizon_days": 1}))
        t("C: typed 40%/1d n=1 edge => SKIP", "COST_GATE_SKIP" in rr["blockers"])
        write_registries(root)
        t("size beyond caps => SIZE_EXCEEDS_LIMITS (no silent shrink)", "SIZE_EXCEEDS_LIMITS" in rb(add_pack(units=40.0))["blockers"])
        write_book(root, extra=[{"symbol": "XLE", "instrumentId": XLE, "value": 50.0, "invested": 50.0, "units": 0.5,
                                 "openRate": 95.0, "positionId": 88, "openTime": ts(MON, 7200)}])
        t("F: XLE position opened < 24h => RECENT_POSITION_24H", "RECENT_POSITION_24H" in rb(add_pack())["blockers"])
        write_book(root, age_s=61)
        t("F: rebalance book 61s old => BOOK_NOT_LIVE", "BOOK_NOT_LIVE" in rb(add_pack())["blockers"])
        write_book(root)
        lv = live_for(add_pack())
        lv["legs"][0]["prepare_response"]["preparedOrderSnapshot"]["units"] = 4.0
        t("I: rebalance prepare units mismatch => PREPARE_MISMATCH", "PREPARE_MISMATCH" in rb(add_pack(), lv)["blockers"])

        # sells / trims
        held = {1001: 1.29223, 1004: 1.0, 1002: 4.537045}

        def sell_pack(units, kind="trim", pid=1001, iid=SMH, sym="SMH", rp=None, bid=603.0, **kw):
            rp = (bid - 564.35) * units if rp is None else rp
            p = {"pack_id": f"classic-rebalance-20261012-{kind}-{sym.lower()}", "kind": kind,
                 "edge_ref": {"evidence_id": "test_rs_oos"},
                 "legs": [{"side": "sell", "symbol": sym, "instrumentId": iid, "positionId": pid, "units": units,
                           "anchor_bid": bid, "anchor_ask": round(bid + 0.3, 2), "close_fee_usd": 0.75,
                           "realized_pnl_usd": rp}]}
            p.update(kw)
            return p

        r = rb(sell_pack(0.5), live_for(sell_pack(0.5), held=held))
        t("I: partial close payload {account, positionId:int, unitsToDeduct}", r["order_payloads"][0] == {
            "account": "demo", "positionId": 1001, "unitsToDeduct": 0.5}, r["order_payloads"])
        r = rb(sell_pack(1.29223), live_for(sell_pack(1.29223), held=held))
        t("full close => unitsToDeduct null", r["order_payloads"][0]["unitsToDeduct"] is None)
        t("units > held => POSITION_NOT_HELD", "POSITION_NOT_HELD" in rb(sell_pack(1.5), live_for(sell_pack(1.5), held=held))["blockers"])
        t("wrong positionId => POSITION_NOT_HELD", "POSITION_NOT_HELD" in rb(sell_pack(0.5, pid=999), live_for(sell_pack(0.5, pid=999)))["blockers"])
        t("positionId str => POSITION_ID_NOT_INT", "POSITION_ID_NOT_INT" in rb(sell_pack(0.5, pid="1001"), live_for(sell_pack(0.5, pid="1001")))["blockers"])
        t("units 0 / negative => NO-GO", all("POSITION_NOT_HELD" in rb(sell_pack(u), live_for(sell_pack(u)))["blockers"] for u in (0, -1)))
        sp = sell_pack(0.5, rp=-100)
        rr = rb(sp, live_for(sp, held=held))
        t("H: QA repro realized -100 (true +19.3) => REALIZED_PNL_MISMATCH", "REALIZED_PNL_MISMATCH" in rr["blockers"])
        sp = sell_pack(0.5, rp=(603.0 - 564.35) * 0.5 - 0.9)
        rr = rb(sp, live_for(sp, held=held))
        t("H: within $1 => tax uses max(declared, recomputed)", "REALIZED_PNL_MISMATCH" not in rr["blockers"]
          and abs(rr["cost_gate"]["tax_est"] - 0.25 * (603.0 - 564.35) * 0.5) < 1e-3, rr["cost_gate"].get("tax_est"))
        sp = sell_pack(1.29223, kind="sell", risk_exit=True, risk_exit_reason="hard_cap_breach", edge_ref=None)
        rr = rb(sp, live_for(sp, held=held))
        t("G: QA repro self-declared hard_cap_breach (SMH ~21%) => RISK_EXIT_NOT_VERIFIED",
          "RISK_EXIT_NOT_VERIFIED" in rr["blockers"], rr.get("risk_exit_check"))
        write_book(root, value_override={"SMH": 3000.0})
        rr = rb(sp, live_for(sp, held=held))
        t("G: hard_cap_breach verified from book => RISK_EXIT", rr["cost_gate"]["verdict"] == "RISK_EXIT"
          and "RISK_EXIT_NOT_VERIFIED" not in rr["blockers"], rr.get("risk_exit_check"))
        write_book(root)
        sp = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=469.0, risk_exit=True,
                       risk_exit_reason="stop_hit", edge_ref=None)
        rr = rb(sp, live_for(sp, held=held))
        t("G: stop_hit verified (bid <= book stopLossRate)", rr["risk_exit_check"]["verified"], rr.get("risk_exit_check"))
        sp = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=505.0, risk_exit=True,
                       risk_exit_reason="stop_hit", edge_ref=None)
        t("G: stop_hit not hit => NO-GO", "RISK_EXIT_NOT_VERIFIED" in rb(sp, live_for(sp, held=held))["blockers"])
        sp = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=505.0, risk_exit=True,
                       risk_exit_reason="trigger_4_200dma", edge_ref=None)
        t("G: trigger_4 verified from score file (TMO below 200DMA)", rb(sp, live_for(sp, held=held))["risk_exit_check"]["verified"])
        sp = sell_pack(0.5, kind="sell", risk_exit=True, risk_exit_reason="trigger_4_200dma", edge_ref=None)
        t("G: trigger_4 on SMH (above 200DMA) => NO-GO", "RISK_EXIT_NOT_VERIFIED" in rb(sp, live_for(sp, held=held))["blockers"])
        sp = sell_pack(0.5, kind="sell", risk_exit=True, risk_exit_reason="cash_below_floor", edge_ref=None)
        t("G: cash_below_floor with cash 3671 => NO-GO", "RISK_EXIT_NOT_VERIFIED" in rb(sp, live_for(sp, held=held))["blockers"])

        # rotation
        rot = {"pack_id": "classic-rebalance-20261012-rot-xlv-xle", "kind": "rotation",
               "edge_ref": {"evidence_id": "test_rs_oos"},
               "legs": [{"side": "sell", "symbol": "XLV", "instrumentId": XLV, "positionId": 1002, "units": 4.537045,
                         "anchor_bid": 170.0, "anchor_ask": 170.05, "close_fee_usd": 0.75,
                         "realized_pnl_usd": (170.0 - 156.44) * 4.537045},
                        add_pack()["legs"][0]]}
        rr = rb(rot, live_for(rot, held=held))
        t("rotation: one combined gate, payloads sell then buy", rr["cost_gate"]["kind"] == "rotation"
          and "positionId" in rr["order_payloads"][0] and rr["order_payloads"][1]["direction"] == "buy", rr["blockers"])
        t("rotation edge recomputed from scores (XLE 3% vs XLV -1%)",
          abs(rr["cost_gate"]["inputs"]["edge"]["expected_return_pct"] - 3.0) < 1e-9
          and abs(rr["cost_gate"]["inputs"]["edge"]["held_expected_return_pct"] + 1.0) < 1e-9)
        write_scores(root, asof="2026-09-30")
        rr = rb(add_pack())
        t("stale score file => edge SKIP + SCORES_UNVERIFIED", "COST_GATE_SKIP" in rr["blockers"]
          and "SCORES_UNVERIFIED" in rr["blockers"] and rr["scores"]["error"].startswith("SCORES_STALE"), rr["scores"])
        write_scores(root, asof="2026-10-08")
        rr = rb(add_pack())
        t("fix4 scores 1 trading day behind last session (Thu vs Fri) => SCORES_STALE_1",
          rr["scores"]["error"] == "SCORES_STALE_1_TRADING_DAYS" and "SCORES_UNVERIFIED" in rr["blockers"], rr["scores"])
        write_scores(root, asof="2026-10-09")
        r_ = X.run_rebalance_checks(pack=add_pack(), live=live_for(add_pack()), now=MON + timedelta(minutes=6), write_lock=False)
        t("fix4 routine 18:06 IDT Mon (session open) with Fri bars => age 0 accepted",
          r_["scores"]["ok"] and r_["scores"]["age_trading_days"] == 0, r_["scores"])
        write_scores(root, asof="2026-10-07")
        rr = rb(add_pack())
        t("fix3 scores 2 trading days behind => SCORES_STALE_2", rr["scores"]["error"] == "SCORES_STALE_2_TRADING_DAYS"
          and "SCORES_UNVERIFIED" in rr["blockers"], rr["scores"])
        write_scores(root, sidecar=False)
        (root / "scores.sha256").unlink(missing_ok=True)
        rr = rb(add_pack())
        t("fix3 scores sidecar missing => SCORES_UNVERIFIED", rr["scores"]["error"] == "SCORES_SIDECAR_MISSING"
          and "SCORES_UNVERIFIED" in rr["blockers"], rr["scores"])
        write_scores(root)
        sp_ = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=505.0, risk_exit=True,
                        risk_exit_reason="trigger_4_200dma", edge_ref=None)
        d_ = json.loads((root / "scores.json").read_text())
        for r_ in d_["rows"]:
            if r_["symbol"] == "TMO":
                r_["above_200dma"] = True
        (root / "scores.json").write_text(json.dumps(d_))
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix3 hand-edited score file (sha mismatch) => SCORES_SHA_MISMATCH, risk exit not verified",
          rr["scores"]["error"] == "SCORES_SHA_MISMATCH" and "SCORES_UNVERIFIED" in rr["blockers"]
          and rr["decision"] != "GO", rr["scores"])
        (root / "scores.json").unlink()
        rr = rb(add_pack())
        t("fix3 scores file missing => SCORES_UNVERIFIED", rr["scores"]["error"] == "SCORES_MISSING"
          and "SCORES_UNVERIFIED" in rr["blockers"], rr["scores"])
        # fix4: protective exits from book + live quote work without verified scores
        sp_ = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=469.0, risk_exit=True,
                        risk_exit_reason="stop_hit", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 scores missing: stop_hit on position's own SL still verified, no SCORES_UNVERIFIED",
          rr["risk_exit_check"]["verified"] and "SCORES_UNVERIFIED" not in rr["blockers"]
          and rr["cost_gate"]["verdict"] == "RISK_EXIT" and rr["scores"]["required"] is False, rr["blockers"])
        sp_ = sell_pack(1.29223, kind="sell", bid=585.0, risk_exit=True, risk_exit_reason="stop_hit", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 scores missing: trailing-only stop (SMH 585 > SL 581.8, < trail 588.3) NOT verified",
          "RISK_EXIT_NOT_VERIFIED" in rr["blockers"] and rr["risk_exit_check"]["trailing_level"] is None, rr.get("risk_exit_check"))
        write_book(root, value_override={"SMH": 3000.0})
        sp_ = sell_pack(1.29223, kind="sell", risk_exit=True, risk_exit_reason="hard_cap_breach", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 scores missing: hard_cap_breach from book verified, no SCORES_UNVERIFIED",
          rr["cost_gate"]["verdict"] == "RISK_EXIT" and "SCORES_UNVERIFIED" not in rr["blockers"], rr["blockers"])
        write_book(root, cash=2000.0)
        sp_ = sell_pack(0.5, kind="sell", risk_exit=True, risk_exit_reason="cash_below_floor", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 scores missing: cash_below_floor (cash 2000) verified, no SCORES_UNVERIFIED",
          rr["risk_exit_check"]["verified"] and "SCORES_UNVERIFIED" not in rr["blockers"], rr["blockers"])
        write_book(root)
        sp_ = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=505.0, risk_exit=True,
                        risk_exit_reason="trigger_4_200dma", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 scores missing: trigger_4 still needs scores => SCORES_UNVERIFIED + not verified",
          "SCORES_UNVERIFIED" in rr["blockers"] and "RISK_EXIT_NOT_VERIFIED" in rr["blockers"], rr["blockers"])
        sp_ = sell_pack(0.5, kind="sell", risk_exit=True, risk_exit_reason="trigger_3_50dma_neg_rs", edge_ref=None)
        t("fix4 scores missing: trigger_3 => SCORES_UNVERIFIED", "SCORES_UNVERIFIED" in rb(sp_, live_for(sp_, held=held))["blockers"])
        t("fix4 scores missing: non-risk trim still needs scores", "SCORES_UNVERIFIED" in rb(sell_pack(0.5), live_for(sell_pack(0.5), held=held))["blockers"])
        write_scores(root)
        sp_ = sell_pack(1.29223, kind="sell", bid=585.0, risk_exit=True, risk_exit_reason="stop_hit", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix4 verified scores: trailing stop SMH 585 <= 588.3 verified", rr["risk_exit_check"]["verified"], rr.get("risk_exit_check"))
        write_scores(root, overrides={"XLE": ("0.15", 95.0, 1.9, True, True, 0.03)})
        rr = rb(add_pack())
        t("fix4 string score in file => SCORES_VALUE_INVALID", rr["scores"]["error"] == "SCORES_VALUE_INVALID", rr["scores"])
        (root / "scores.json").unlink()
        write_scores(root, asof="2026-10-12")
        rr = rb(add_pack())
        t("fix3 scores dated today before close (unconfirmed bar) => SCORES_FROM_FUTURE",
          rr["scores"]["error"] == "SCORES_FROM_FUTURE", rr["scores"])
        write_scores(root)
        # ---------- fix5/fix6 risk-exit sizing + band + cascade: run on the legacy INVESTED basis ----------
        # (fix7 moved production to CAP_DENOMINATOR="equity"; these keep the invested-basis math covered)
        X.CAP_DENOMINATOR = "invested"
        # ---------- fix5: risk-exit sizing ----------
        import math as _m
        EQ, B = 7270.38, 0.01 * 7270.38

        def xlv_exit(units, reason, bid=170.0):
            p_ = sell_pack(units, kind="sell", pid=1002, iid=XLV, sym="XLV", bid=bid, rp=(bid - 156.44) * units,
                           risk_exit=True, risk_exit_reason=reason, edge_ref=None)
            p_["legs"][0]["anchor_ask"] = round(bid + 0.1, 2)  # keep ask within 0.1% of the mark
            return p_

        def up(x):
            return _m.ceil(round(x / 1e-6, 3)) * 1e-6

        write_book(root, cash=2300.0)
        x_cash = up((2500 + B - 2300.0 + 0.75) / 170.0)
        rr = rb(xlv_exit(4.537045, "cash_below_floor"), live_for(xlv_exit(4.537045, "cash_below_floor"), held=held))
        t("fix5 cash_below_floor full close when partial suffices => RISK_EXIT_SIZE_MISMATCH",
          "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"] and abs(rr["risk_exit_sizing"]["units"] - x_cash) < 2e-6, rr.get("risk_exit_sizing"))
        sp_ = xlv_exit(round(x_cash, 6), "cash_below_floor")
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix5 cash_below_floor min units (cash 2300 -> >= 2500 + 1% equity) => unitsToDeduct partial, no size blocker",
          "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and rr["order_payloads"][0]["unitsToDeduct"] == round(x_cash, 6)
          and rr["cost_gate"]["verdict"] == "RISK_EXIT", (rr["blockers"], rr.get("risk_exit_sizing")))
        t("fix5 cash restored: 2300 + x*bid - fee >= 2500 + buffer",
          2300 + x_cash * 170.0 - 0.75 >= 2500 + B - 1e-6 and 2300 + (x_cash - 2e-6) * 170.0 - 0.75 < 2500 + B)
        sp_ = xlv_exit(round(x_cash + 0.5, 6), "cash_below_floor")
        t("fix5 cash_below_floor oversize (+0.5u) => RISK_EXIT_SIZE_MISMATCH",
          "RISK_EXIT_SIZE_MISMATCH" in rb(sp_, live_for(sp_, held=held))["blockers"])
        write_book(root, cash=2000.0)
        rr = rb(xlv_exit(4.537045, "cash_below_floor"), live_for(xlv_exit(4.537045, "cash_below_floor"), held=held))
        t("fix5 cash 2000: residual < $400 => full close allowed (unitsToDeduct null)",
          rr["risk_exit_sizing"]["full_close"] and rr["risk_exit_sizing"]["full_close_reason"] == "residual < $400"
          and rr["order_payloads"][0]["unitsToDeduct"] is None and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"],
          rr.get("risk_exit_sizing"))
        write_book(root, value_override={"XLV": 2000.0})
        vals = {"QQQ": 830.65, "SMH": 778.16, "XLV": 2000.0, "SPY": 705.82, "TMO": 509.15}
        T, uv = sum(vals.values()), 2000.0 / 4.537045
        x_cap = up(max((2000 - 0.30 * T + B) / (uv * 0.70), (2509.15 - 0.45 * T + B) / (uv * 0.55)))
        rr = rb(xlv_exit(4.537045, "hard_cap_breach"), live_for(xlv_exit(4.537045, "hard_cap_breach"), held=held))
        t("fix5 hard_cap_breach full close when partial suffices => RISK_EXIT_SIZE_MISMATCH",
          rr["risk_exit_check"]["verified"] and "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"]
          and abs(rr["risk_exit_sizing"]["units"] - x_cap) < 2e-6, rr.get("risk_exit_sizing"))
        sp_ = xlv_exit(round(x_cap, 6), "hard_cap_breach")
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix5 hard_cap_breach min units => partial unitsToDeduct, RISK_EXIT",
          "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and rr["order_payloads"][0]["unitsToDeduct"] == round(x_cap, 6)
          and rr["cost_gate"]["verdict"] == "RISK_EXIT", (rr["blockers"], rr.get("risk_exit_sizing")))
        after_v = (2000 - x_cap * uv) / (T - x_cap * uv)
        after_s = (2509.15 - x_cap * uv) / (T - x_cap * uv)
        t("fix5 after sizing: XLV <= 30% and healthcare sleeve <= 45% (value) with buffer",
          after_v <= 0.30 and after_s <= 0.45, (after_v, after_s))
        t("fix5 sizing considers both value and cost basis", set(rr["risk_exit_sizing"]["required_units_by_constraint"]) ==
          {"name_values", "name_cost", "sleeve_values", "sleeve_cost"}, rr["risk_exit_sizing"]["required_units_by_constraint"])
        write_book(root, value_override={"XLV": 2000.0}, cost_override={"XLV": 2500.0})
        rr = rb(xlv_exit(round(x_cap, 6), "hard_cap_breach"), live_for(xlv_exit(round(x_cap, 6), "hard_cap_breach"), held=held))
        t("fix5 cost-basis breach larger than value breach drives the size (=> value-only size rejected)",
          "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"] and rr["risk_exit_sizing"]["units"] > x_cap, rr.get("risk_exit_sizing"))
        write_book(root, value_override={"XLV": 3000.0})
        rr = rb(xlv_exit(4.537045, "hard_cap_breach"), live_for(xlv_exit(4.537045, "hard_cap_breach"), held=held))
        t("fix5 hard cap XLV 3000: residual < $400 => full close allowed",
          rr["risk_exit_sizing"]["full_close"] and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"]
          and rr["order_payloads"][0]["unitsToDeduct"] is None, rr.get("risk_exit_sizing"))
        write_book(root)
        sp_ = sell_pack(0.5, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=469.0, rp=(469.0 - 520.0) * 0.5,
                        risk_exit=True, risk_exit_reason="stop_hit", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix5 stop_hit: any size allowed (partial), no sizing applied", "risk_exit_sizing" not in rr
          and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and rr["risk_exit_check"]["verified"], rr["blockers"])
        sp_ = sell_pack(1.0, kind="sell", pid=1004, iid=TMO, sym="TMO", bid=505.0, rp=(505.0 - 520.0),
                        risk_exit=True, risk_exit_reason="trigger_4_200dma", edge_ref=None)
        rr = rb(sp_, live_for(sp_, held=held))
        t("fix5 trigger_4: full close allowed (unitsToDeduct null), no sizing", "risk_exit_sizing" not in rr
          and rr["order_payloads"][0]["unitsToDeduct"] is None and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"], rr["blockers"])
        # ---------- fix6: GO size band (book/bid/cash drift between plan and GO) ----------
        def exit_pack(sym, pid, iid, units, reason, bid, oprate, req_qa=None):
            p_ = sell_pack(units, kind="trim", pid=pid, iid=iid, sym=sym, bid=bid, rp=(bid - oprate) * units,
                           risk_exit=True, risk_exit_reason=reason, edge_ref=None)
            p_["legs"][0]["anchor_ask"] = round(bid * 1.0003, 2)
            if req_qa is not None:
                p_["legs"][0]["risk_exit_required_units"] = req_qa
            return p_

        def go_live(p_, live_bid=None):
            lv_ = live_for(p_, held=held)
            if live_bid is not None:
                lv_["legs"][0].update(bid=live_bid, ask=round(live_bid * 1.0003, 2), independent_mark=live_bid)
            return lv_

        QB = 746.67
        write_book(root, value_override={"QQQ": 1000.0})
        plan_ = rb(exit_pack("QQQ", 1000, 3006, 0.3, "hard_cap_breach", QB, 677.9), live_for(
            exit_pack("QQQ", 1000, 3006, 0.3, "hard_cap_breach", QB, 677.9), held={1000: 1.106357}))
        rq = plan_["risk_exit_sizing"]["units"]
        t("fix6 plan: QQQ-heavy growth sleeve verified, partial size computed", plan_["risk_exit_check"]["verified"]
          and not plan_["risk_exit_sizing"]["full_close"] and 0 < rq < 1.106357, plan_.get("risk_exit_sizing"))
        held[1000] = 1.106357
        t("fix6 plan suggests pack units = ceil(1.01 x required) (headroom inside the 1.02 band)",
          abs(plan_["risk_exit_sizing"]["suggested_pack_units"] - up(rq * 1.01)) < 2e-6, plan_.get("risk_exit_sizing"))
        rq0, rq = rq, plan_["risk_exit_sizing"]["suggested_pack_units"]
        qp = exit_pack("QQQ", 1000, 3006, rq, "hard_cap_breach", QB, 677.9, req_qa=rq0)
        rr = rb(qp, go_live(qp))
        t("fix6 GO no drift: in band, no SIZE_MISMATCH, no cascade", "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"]
          and "RISK_EXIT_POST_TRADE_CAP_CASCADE" not in rr["blockers"], (rr["blockers"], rr.get("risk_exit_band")))
        for lbl, ov in (("+0.02%", 1000.0 * 1.0002), ("-0.02%", 1000.0 * 0.9998)):
            write_book(root, value_override={"QQQ": ov})
            rr = rb(qp, go_live(qp))
            t(f"fix6 QQQ book value {lbl} between plan and GO => still in band (Fix5 exact match would fail)",
              "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and rr["risk_exit_band"]["ok"], rr.get("risk_exit_band"))
        write_book(root, value_override={"QQQ": 1000.0})
        for lbl, lb in (("+0.02%", round(QB * 1.0002, 2)), ("-0.02%", round(QB * 0.9998, 2))):
            rr = rb(qp, go_live(qp, lb))
            t(f"fix6 QQQ live bid {lbl} at GO => in band", "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"]
              and "ANCHOR_DRIFT" not in rr["blockers"], (rr["blockers"], rr.get("risk_exit_band")))
        write_book(root, value_override={"QQQ": 1030.0})
        rr = rb(qp, go_live(qp))
        t("fix6 QQQ +3% at GO => required_now > pack units => RISK_EXIT_SIZE_MISMATCH (undersized)",
          "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"] and "below required_now" in rr["risk_exit_band"]["why"], rr.get("risk_exit_band"))
        write_book(root, value_override={"QQQ": 970.0})
        rr = rb(qp, go_live(qp))
        t("fix6 QQQ -3% at GO => pack units above 1.02x band => RISK_EXIT_SIZE_MISMATCH (oversized)",
          "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"] and "above band" in rr["risk_exit_band"]["why"], rr.get("risk_exit_band"))
        write_book(root, value_override={"QQQ": 1000.0})
        qp2 = exit_pack("QQQ", 1000, 3006, round(rq0 * 1.019, 6), "hard_cap_breach", QB, 677.9, req_qa=rq0)
        t("fix6 pack 1.9% above required => in band", rb(qp2, go_live(qp2))["risk_exit_band"]["ok"])
        qp3 = exit_pack("QQQ", 1000, 3006, round(rq0 * 1.03, 6), "hard_cap_breach", QB, 677.9, req_qa=rq0)
        t("fix6 pack 3% above required => RISK_EXIT_SIZE_MISMATCH", "RISK_EXIT_SIZE_MISMATCH" in rb(qp3, go_live(qp3))["blockers"])
        qp4 = exit_pack("QQQ", 1000, 3006, round(rq0 * 1.5, 6), "hard_cap_breach", QB, 677.9, req_qa=rq0 * 1.5)
        rr = rb(qp4, go_live(qp4))
        t("fix6 forged required_at_qa (1.5x) clamped to 1.05x required_now => oversize still blocked",
          "RISK_EXIT_SIZE_MISMATCH" in rr["blockers"] and rr["risk_exit_band"]["required_at_qa_used"] < rq0 * 1.06, rr.get("risk_exit_band"))
        # cash drift: SMH cash_below_floor
        SB = 591.48
        write_book(root, cash=2499.0)
        sp0 = exit_pack("SMH", 1001, SMH, 0.1, "cash_below_floor", SB, 564.35)
        sz0 = rb(sp0, go_live(sp0))["risk_exit_sizing"]
        sp1 = exit_pack("SMH", 1001, SMH, sz0["suggested_pack_units"], "cash_below_floor", SB, 564.35,
                        req_qa=sz0["suggested_required_at_qa"])
        rr = rb(sp1, go_live(sp1))
        t("fix6 SMH cash 2499 exit: in band, no cascade (sells the over-weight sleeve)",
          "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and rr["risk_exit_post_trade_caps"]["ok"]
          and "RISK_EXIT_POST_TRADE_CAP_CASCADE" not in rr["blockers"], (rr["blockers"], rr.get("risk_exit_band")))
        for c_ in (2498.90, 2499.10):
            write_book(root, cash=c_)
            rr = rb(sp1, go_live(sp1))
            t(f"fix6 cash 2499 -> {c_} at GO => in band", rr["risk_exit_band"]["ok"]
              and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"], rr.get("risk_exit_band"))
        write_book(root, cash=2480.0)
        t("fix6 cash 2499 -> 2480 at GO => undersized => RISK_EXIT_SIZE_MISMATCH",
          "RISK_EXIT_SIZE_MISMATCH" in rb(sp1, go_live(sp1))["blockers"])
        write_book(root, cash=2490.0)
        sz2 = rb(sp0, go_live(sp0))["risk_exit_sizing"]
        sp2 = exit_pack("SMH", 1001, SMH, sz2["suggested_pack_units"], "cash_below_floor", SB, 564.35,
                        req_qa=sz2["suggested_required_at_qa"])
        write_book(root, cash=2499.9)
        t("fix6 plan at cash 2490, GO at 2499.90 => oversized beyond 1.02x => RISK_EXIT_SIZE_MISMATCH",
          "RISK_EXIT_SIZE_MISMATCH" in rb(sp2, go_live(sp2))["blockers"])
        # full-close / residual rule re-evaluated at GO (direct)
        sz_ = {"min_units": 2.0, "full_close": False}
        t("fix6 band: partial leaving live residual < $400 => blocked",
          not X._risk_exit_band(u=2.0, held=4.0, sz=sz_, bid=170.0, required_at_qa=2.0)["ok"])
        t("fix6 band: partial leaving residual >= $400 => ok",
          X._risk_exit_band(u=2.0, held=4.5, sz=sz_, bid=170.0, required_at_qa=2.0)["ok"])
        t("fix6 band: full close when live rule says full => ok",
          X._risk_exit_band(u=4.0, held=4.0, sz={"min_units": 3.0, "full_close": True}, bid=170.0, required_at_qa=None)["ok"])
        t("fix6 band: full close when live rule says partial and held > band => blocked",
          not X._risk_exit_band(u=4.0, held=4.0, sz={"min_units": 2.0, "full_close": False}, bid=300.0, required_at_qa=None)["ok"])
        t("fix6 band: full close inside band (held <= 1.02x required) => ok",
          X._risk_exit_band(u=4.0, held=4.0, sz={"min_units": 3.95, "full_close": False}, bid=300.0, required_at_qa=None)["ok"])
        write_book(root, cash=2000.0)
        xf = exit_pack("XLV", 1002, XLV, 4.537045, "cash_below_floor", 170.0, 156.44, req_qa=4.537045)
        write_book(root, cash=2000.10)
        rr = rb(xf, go_live(xf))
        t("fix6 XLV full close (residual < $400) re-evaluated at GO with cash +$0.10 => size ok",
          rr["risk_exit_band"]["ok"] and rr["risk_exit_band"]["live_full_close"], rr.get("risk_exit_band"))
        # ---------- fix6: post-trade cap cascade (today's book) ----------
        write_book(root, cash=2000.0)
        rr = rb(xf, go_live(xf))
        pt = rr["risk_exit_post_trade_caps"]
        t("fix6 today's book: SMH+QQQ = 44.71% of invested before", pt["before"]["values"]["sleeve:growth_tech"] == 44.71, pt["before"])
        t("fix6 closing XLV => growth_tech ~57% => RISK_EXIT_POST_TRADE_CAP_CASCADE",
          "RISK_EXIT_POST_TRADE_CAP_CASCADE" in rr["blockers"] and 56.5 < pt["after"]["values"]["sleeve:growth_tech"] < 57.5
          and rr["decision"] == "NO-GO", (rr["blockers"], pt["cascade"]))
        t("fix6 cash 2000: no single leg avoids a new breach (SMH/QQQ full close => healthcare > 45%) => alternatives empty",
          pt.get("alternatives") == [], pt.get("alternatives"))
        write_book(root, cash=2300.0)
        rr = rb(xf, go_live(xf))
        t("fix6 today's book cash 2300: XLV partial cascades and no single-leg alternative exists (SMH/QQQ trims push "
          "TMO > 15% value) => blocked with empty alternatives",
          "RISK_EXIT_POST_TRADE_CAP_CASCADE" in rb(exit_pack("XLV", 1002, XLV, rr["risk_exit_sizing"]["suggested_pack_units"],
                                                             "cash_below_floor", 170.0, 156.44), go_live(exit_pack(
              "XLV", 1002, XLV, rr["risk_exit_sizing"]["suggested_pack_units"], "cash_below_floor", 170.0, 156.44)))["blockers"])
        write_book(root, cash=2300.0, value_override={"TMO": 400.0}, cost_override={"TMO": 400.0})
        rr = rb(xf, go_live(xf))
        sx = rr["risk_exit_sizing"]
        xp = exit_pack("XLV", 1002, XLV, sx["suggested_pack_units"], "cash_below_floor", 170.0, 156.44,
                       req_qa=sx["suggested_required_at_qa"])
        rr = rb(xp, go_live(xp))
        pt = rr["risk_exit_post_trade_caps"]
        alts = {a["symbol"] for a in pt.get("alternatives") or []}
        t("fix6 (TMO 400) cash 2300 partial XLV exit => growth_tech > 45% cascade; lists SMH/QQQ trims as alternatives, never auto-swaps",
          "RISK_EXIT_POST_TRADE_CAP_CASCADE" in rr["blockers"] and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"]
          and {"SMH", "QQQ"} <= alts and "XLV" not in alts and rr["order_payloads"][0]["positionId"] == 1002,
          (rr["blockers"], pt.get("alternatives")))
        write_book(root)
        tmo = list(X.load_book(MON)["positions"])[4]
        pt2 = X.post_trade_caps(X.load_book(MON), symbol="TMO", pos=tmo, units=0.096534, bid=509.15)
        t("fix6 small TMO trim => growth_tech 45.33% (> 45%) => cascade",
          pt2["after"]["values"]["sleeve:growth_tech"] == 45.33 and not pt2["ok"], pt2["cascade"])
        rr = rb(exit_pack("TMO", 1004, TMO, 1.0, "hard_cap_breach", 509.0, 520.0), go_live(
            exit_pack("TMO", 1004, TMO, 1.0, "hard_cap_breach", 509.0, 520.0)))
        rqt = rr["risk_exit_sizing"]["units"]
        tp_ = exit_pack("TMO", 1004, TMO, rqt, "hard_cap_breach", 509.0, 520.0, req_qa=rqt)
        rr = rb(tp_, go_live(tp_))
        t("fix6 TMO cost-basis cap exit (15.25% cost) sized trim => RISK_EXIT_POST_TRADE_CAP_CASCADE",
          rr["risk_exit_check"]["verified"] and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"]
          and "RISK_EXIT_POST_TRADE_CAP_CASCADE" in rr["blockers"], (rr["blockers"], rr.get("risk_exit_post_trade_caps", {}).get("cascade")))
        t("fix6 pre-existing breach (TMO cost 15.25%) made worse by another exit is reported, not a new-breach block",
          X.post_trade_caps(X.load_book(MON), symbol="SMH", pos=X.load_book(MON)["positions"][1], units=0.1, bid=591.48)
          ["worsened_existing"][0]["bucket"] == "name:TMO")
        t("fix6 post-trade check covers value AND cost basis", {"values", "cost"} == set(rr["risk_exit_post_trade_caps"]["after"]))
        t("fix6 [invested basis] cap_denominator = sum of positions", X.cap_denominator({"A": 1.0, "B": 2.0}, 10.0) == 3.0)
        X.CAP_DENOMINATOR = "equity"
        write_book(root)
        fix7_block(root, rb, held, t)
        t("crypto/bare symbol guard on rebalance leg", any(b.startswith("INSTRUMENT") for b in rb(
            {**add_pack(), "legs": [dict(add_pack()["legs"][0], symbol="BTC", instrumentId=100000)]})["blockers"]))
        t("bad shape => BAD_REBALANCE_PACK", "BAD_REBALANCE_PACK" in rb({"pack_id": "classic-rebalance-20261012-x",
                                                                            "kind": "rotation", "legs": []}, {"legs": []})["blockers"])
    os.environ.pop(TEST_ENV, None)
    return out


# ---------------------------------------------------------------- fix7: caps on TOTAL EQUITY
# frozen copy of /workspace/classic-portfolio-for-app.json (asOf 2026-10-12 17:44 IDT) so tests do not drift with live refreshes
REAL_BOOK = os.path.join(os.path.dirname(__file__), "fixtures", "classic-portfolio-20261012-1744.json")
FIX7_MATRIX: list = []


def write_real_book(root, cash=None, value_override=None):
    """Today's live book (positions/equity/cash from REAL_BOOK), re-stamped fresh for test mode.
    cash=c lowers cash and equity by the same amount (holdings unchanged)."""
    d = json.loads(open(REAL_BOOK).read())
    eq0, c0 = float(d["equity"]), float(d["summary"]["availableCash"])
    c = c0 if cash is None else cash
    pos = [dict(p_) for p_ in d["positions"]]
    dv = 0.0
    for p_ in pos:
        if value_override and p_["symbol"] in value_override:
            dv += value_override[p_["symbol"]] - p_["value"]
            p_["value"] = value_override[p_["symbol"]]
    (root / "book.json").write_text(json.dumps({"asOf": ts(MON, 10), "equity": round(eq0 - (c0 - c) + dv, 2),
                                                "summary": {"availableCash": c}, "positions": pos}))
    return pos


def fix7_block(root, rb, held, t):
    from .testkit import write_order_qa as woq

    def leg_pack(p_, units, reason, bid, req=None):
        pk = {"pack_id": f"classic-rebalance-20261012-fix7-{p_['symbol'].lower()}", "kind": "trim",
              "edge_ref": None, "risk_exit": True, "risk_exit_reason": reason,
              "legs": [{"side": "sell", "symbol": p_["symbol"], "instrumentId": p_["instrumentId"],
                        "positionId": p_["positionId"], "units": units, "anchor_bid": bid,
                        "anchor_ask": round(bid * 1.0003, 2), "close_fee_usd": 0.75,
                        "realized_pnl_usd": (bid - p_["openRate"]) * units}]}
        if req is not None:
            pk["legs"][0]["risk_exit_required_units"] = req
        return pk

    def live(pk, held_u):
        l_ = pk["legs"][0]
        full = abs(l_["units"] - held_u) < 1e-9
        return {"legs": [{"bid": l_["anchor_bid"], "ask": l_["anchor_ask"], "quote_ts": ts(MON, 3),
                          "independent_mark": l_["anchor_bid"],
                          "prepare_response": close_prepare({"positionId": l_["positionId"],
                                                             "unitsToDeduct": None if full else l_["units"]})}]}

    def run_exit(p_, reason):
        bid = round(p_["value"] / p_["units"], 2)
        plan_ = rb(leg_pack(p_, p_["units"], reason, bid), live(leg_pack(p_, p_["units"], reason, bid), p_["units"]))
        sz = plan_.get("risk_exit_sizing")
        if not sz:
            return plan_, None
        pk = leg_pack(p_, sz["suggested_pack_units"], reason, bid, sz["suggested_required_at_qa"])
        return rb(pk, live(pk, p_["units"])), pk

    t("fix7 production CAP_DENOMINATOR = 'equity' (Ofer 2026-10-12 17:56 IDT)", X.CAP_DENOMINATOR == "equity")
    pos = write_real_book(root)
    bk = X.load_book(MON)
    t("fix7 today's book loaded: equity 7251.71, cash 3671.18", bk["equity"] == 7251.71 and bk["cash"] == 3671.18,
      (bk["equity"], bk["cash"]))
    t("fix7 cap_denominator(values) = book equity; cost basis = cost + cash",
      X.cap_denominator(bk["values"], bk["cash"], bk["equity"]) == 7251.71
      and abs(X.cap_denominator(bk["cost"], bk["cash"]) - (3389.05 + 3671.18)) < 1e-6)
    p0 = X.post_trade_caps(bk, symbol="XLV", pos=pos[3], units=0.0, bid=171.4)
    t("fix7 today's book on equity: SMH+QQQ 21.93%, QQQ 11.38%, TMO 7.0% (value)",
      p0["before"]["values"]["sleeve:growth_tech"] == 21.93 and p0["before"]["values"]["name:QQQ"] == 11.38
      and p0["before"]["values"]["name:TMO"] == 7.0, p0["before"]["values"])
    for p_ in pos:
        for reason in ("cash_below_floor", "hard_cap_breach"):
            rr, _ = run_exit(p_, reason)
            FIX7_MATRIX.append({"book": "today (cash 3671.18)", "symbol": p_["symbol"], "reason": reason,
                                "decision": rr["decision"], "blockers": rr["blockers"]})
            t(f"fix7 today's book {p_['symbol']} {reason}: not verified (no breach on equity) => NO-GO",
              "RISK_EXIT_NOT_VERIFIED" in rr["blockers"], rr["blockers"])
    pt = X.post_trade_caps(bk, symbol="XLV", pos=pos[3], units=pos[3]["units"], bid=171.4, close_fee=0.75)
    t("fix7 closing XLV on today's book: SMH+QQQ -> ~21.95% of equity, no cascade (was ~57% on invested)",
      pt["ok"] and pt["after"]["values"]["sleeve:growth_tech"] < 22.5, pt["after"]["values"])
    t("fix7 post-trade equity = equity - fee + (proceeds - sold value)",
      abs(pt["denominator_usd"]["values"]["after"] - (7251.71 - 0.75 + pos[3]["units"] * 171.4 - pos[3]["value"])) < 0.01,
      pt["denominator_usd"])
    # cash-floor scenarios on today's holdings (cash and equity lowered together)
    for c_ in (2499.0, 2300.0, 2000.0):
        pos = write_real_book(root, cash=c_)
        for p_ in pos:
            rr, pk = run_exit(p_, "cash_below_floor")
            blk_ = [b for b in rr["blockers"] if b != "ORDER_QA_PENDING"]
            FIX7_MATRIX.append({"book": f"today holdings, cash {c_}", "symbol": p_["symbol"], "reason": "cash_below_floor",
                                "units": (pk or {}).get("legs", [{}])[0].get("units"),
                                "full_close": (rr.get("risk_exit_sizing") or {}).get("full_close"),
                                "growth_after_pct": ((rr.get("risk_exit_post_trade_caps") or {}).get("after", {})
                                                     .get("values", {}).get("sleeve:growth_tech")),
                                "ready_for_order_qa": rr["ready_for_order_qa"], "blockers": rr["blockers"]})
            t(f"fix7 cash {c_}: {p_['symbol']} cash_below_floor exit in band, no cascade => ready (only ORDER_QA_PENDING)",
              not blk_ and rr["ready_for_order_qa"], (rr["blockers"], rr.get("risk_exit_post_trade_caps", {}).get("cascade")))
    pos = write_real_book(root, cash=2000.0)
    rr, pk = run_exit(pos[3], "cash_below_floor")
    woq(rr)
    g = rb(pk, live(pk, pos[3]["units"]))
    t("fix7 cash 2000: XLV full close (residual < $400) reaches GO with order-QA PASS (test mode, no lock)",
      g["decision"] == "GO" and g["order_payloads"][0]["unitsToDeduct"] is None, g["blockers"])
    # hard cap on equity: QQQ inflated to 3500 (> 30% of equity)
    pos = write_real_book(root, value_override={"QQQ": 3500.0})
    rr, pk = run_exit(pos[2], "hard_cap_breach")
    pt = rr.get("risk_exit_post_trade_caps") or {}
    t("fix7 QQQ 3500 (35.6% of equity) => verified; sized on equity, after <= 30% (value), in band, no cascade",
      rr["risk_exit_check"]["verified"] and "RISK_EXIT_SIZE_MISMATCH" not in rr["blockers"] and pt.get("ok")
      and pt["after"]["values"]["name:QQQ"] <= 30.0 and rr["risk_exit_check"]["name_values"] > 30,
      (rr["blockers"], rr.get("risk_exit_check"), pt.get("after", {}).get("values")))
    sz = rr["risk_exit_sizing"]
    bid = round(3500.0 / pos[2]["units"], 2)
    u_ = sz["suggested_required_at_qa"]
    eq_after = (7251.71 + 3500.0 - 825.49) - 0.75 + u_ * (bid - 3500.0 / pos[2]["units"])
    t("fix7 equity sizing formula: (X - x*u) <= 30%*(E - fee + x*(bid-u)) - 1% buffer",
      3500.0 - u_ * 3500.0 / pos[2]["units"] <= 0.30 * eq_after - 0.01 * (7251.71 + 3500.0 - 825.49) + 1e-6,
      (u_, eq_after))
    # fix7b: equity reconciliation (|equity - (holdings + cash)| <= 0.5% of equity)
    pos = write_real_book(root)
    rr, _ = run_exit(pos[3], "cash_below_floor")
    chk = next(c_ for c_ in rr["checks"] if c_["name"] == "book_equity_reconciled")
    t("fix7b today's book reconciles (7251.71 vs 7252.34, gap -0.63)", chk["ok"] and chk["detail"]["gap"] == -0.63, chk)
    d_ = json.loads((root / "book.json").read_text())
    for eqv, ok_ in ((7252.34 * 1.0049, True), (7252.34 * 1.006, False), (7252.34 * 0.994, False), (7252.34 * 0.9951, True)):
        d_["equity"] = round(eqv, 2)
        (root / "book.json").write_text(json.dumps(d_))
        rr2, _ = run_exit(pos[3], "cash_below_floor")
        t(f"fix7b equity {eqv / 7252.34 - 1:+.2%} vs holdings+cash => {'ok' if ok_ else 'BOOK_EQUITY_NOT_RECONCILED'}",
          ("BOOK_EQUITY_NOT_RECONCILED" in rr2["blockers"]) != ok_, rr2["blockers"])
    d_["equity"] = 9000.0
    (root / "book.json").write_text(json.dumps(d_))
    rb_ = X.run_checks(pack_id=PID, bid=27.03, ask=27.05, quote_ts=ts(MON, 5), mark=27.05, units=23.0, open_fee_usd=0.75,
                       close_fee_usd=0.75, now=MON, write_lock=False)
    t("fix7b RSI buy path also blocks on unreconciled equity", "BOOK_EQUITY_NOT_RECONCILED" in rb_["blockers"])
    from . import book_sleeves as BS
    nb = BS.recompute(json.loads(open(REAL_BOOK).read()))
    sv = nb["sleeves"]
    t("fix7b book_sleeves: growth/QQQ/TMO/SPY as % of total equity", sv["denominator"] == "equity" and sv["growthPct"] == 21.93
      and sv["names"]["TMO"]["pctEquity"] == 7.0 and sv["spyCore"]["pct"] == 9.73, (sv["growthPct"], sv["names"]))
    t("fix7b book_sleeves: invested-basis numbers only under labelled legacyInvestedBasis",
      sv["legacyInvestedBasis"]["label"].startswith("LEGACY") and "invested" not in {k for k in sv if k != "legacyInvestedBasis"})
    ct_ = nb["cashTriggerProposal"]
    t("fix7b SPY parking cap on equity: $440 within; cap headroom = min(30%*E - SPY MV, 30%*(cost+cash) - SPY cost)",
      ct_["capCheck"]["proposalWithinCap"] and abs(ct_["capCheck"]["maxNotionalWithinCap"] - round(min(0.3 * 7251.71 - 705.53,
      0.3 * (3389.05 + 3671.18) - 700.0), 2)) < 0.01 and "legacyInvestedBasis" in ct_, ct_["capCheck"])
    write_book(root)


def main() -> int:
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res = run()
    for name, ok, detail in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail != "" else ""))
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

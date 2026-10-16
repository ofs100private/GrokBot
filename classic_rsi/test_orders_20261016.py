"""QA fix3: pending orders / positions guard stale-reservation release; pending orders count as used slots;
pre_buy must have run (history+rates+orders ok) <= 5 min before GO; book <= 60 s for counting. Never calls eToro.

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_orders_20261016
"""
from __future__ import annotations

import json
import os
from datetime import timedelta, timezone

from . import pre_buy as PB
from . import trade_counter as TC
from .testkit import MON, make_pack, test_root, ts, write_book, write_envelope, write_prebuy, write_run_qa, write_scores
from .test_execute_pass import rsi  # noqa: F401  (decorated)

UTC = timezone.utc


def _orders(positions=(), orders=(), age_s=5, sc=200, now=MON):
    return {"account": "real", "statusCode": sc, "timestamp": (now - timedelta(seconds=age_s)).astimezone(UTC).isoformat(),
            "direct": {"positions": list(positions), "orders": list(orders)}, "mirrors": []}


def _pos(pid, iid, open_dt):
    return {"positionId": pid, "market": {"instrumentId": iid}, "openTime": open_dt.astimezone(UTC).replace(tzinfo=None).isoformat()}


def _ord(oid, iid, t=None, status="placed"):
    o = {"orderId": oid, "market": {"instrumentId": iid}, "status": status}
    if t is not None:
        o["openTime"] = t.astimezone(UTC).isoformat()
    return o


def _hist(trades=()):
    return json.dumps({"statusCode": 200, "hasMore": False, "trades": list(trades)})


RATES = json.dumps({"rates": [{"instrumentID": 1001, "bid": 1.0, "ask": 1.01, "date": MON.astimezone(UTC).isoformat()}]})


def run():
    out = []
    t = lambda n, ok, d="": out.append((n, bool(ok), d))  # noqa: E731
    now = MON
    # --- parse_orders
    t("orders: success parsed", PB.parse_orders(_orders([_pos(1, 1592, now - timedelta(days=3))]), now)["ok"])
    for lbl, raw in (("stale timestamp 61s", _orders(age_s=61)), ("non-200", _orders(sc=500)), ("empty", ""),
                     ("no direct", {"statusCode": 200, "timestamp": now.isoformat()}),
                     ("bad position openTime", _orders([{"positionId": 1, "market": {"instrumentId": 1}, "openTime": "x"}])),
                     ("missing timestamp", {**_orders(), "timestamp": None})):
        t(f"orders fail closed: {lbl}", not PB.parse_orders(raw, now)["ok"])
    real = open("/workspace/agent-tools/bf916bda-3d7d-4646-9cce-79c4ed92933e.txt").read() \
        if os.path.exists("/workspace/agent-tools/bf916bda-3d7d-4646-9cce-79c4ed92933e.txt") else None
    if real:
        from datetime import datetime
        r = PB.parse_orders(real, datetime.fromisoformat("2026-10-15T22:42:10+00:00"))
        t("real user-OfersClaw5 positions-and-orders read parses (4 positions, 0 pending)",
          r["ok"] and len(r["positions"]) == 4 and r["pending_orders"] == [], r.get("error"))
    od = PB.parse_orders(_orders(orders=[_ord(11, 1001, now - timedelta(hours=1)), _ord(12, 1001, now - timedelta(days=2)),
                                         _ord(13, 3000), _ord(14, 3000, status="canceled")]), now)
    keys = PB.pending_keys_today(od, now)
    t("pending today + unknown-time count; old pending / terminal don't", keys == ["order:11", "order:13"], keys)
    with test_root() as root:
        os.environ.pop(TC.ENV_OVERRIDE, None)
        old = now - timedelta(minutes=45)

        def fresh_res(iid):
            return TC.reserve(f"k{iid}-{len(os.listdir(root))}", "S", now=old, instrument_id=iid)["reservation"]

        def refresh(orders, hist=_hist()):
            return PB.refresh(history_raw=hist, rates_raw=RATES, instrument_ids=[1001], orders_raw=json.dumps(orders),
                              now=now, read_at=now)
        # pending order for the same instrument blocks release
        r1 = fresh_res(1001)
        res = refresh(_orders(orders=[_ord(21, 1001, now - timedelta(minutes=40))]))
        t("pending order same instrument => release blocked", r1 not in [x["id"] for x in res["released_stale_reservations"]])
        st = json.loads(TC.counter_path()[0].read_text())
        blk = [s_ for v in st.values() for s_ in v.get("slots", []) if s_["id"] == r1][0]
        t("blocked slot stays reserved with reason", blk["state"] == "reserved" and "PENDING_ORDER" in blk["release_blocked"], blk)
        # position opened after reservation blocks
        res = refresh(_orders(positions=[_pos(31, 1001, now - timedelta(minutes=40))]))
        t("position for instrument opened after reservation => blocked", res["released_stale_reservations"] == [])
        # history trade (opened+closed) after reservation blocks
        h = _hist([{"positionId": 41, "market": {"instrumentId": 1001},
                    "openTime": (now - timedelta(minutes=40)).astimezone(UTC).isoformat(),
                    "closeTime": (now - timedelta(minutes=5)).astimezone(UTC).isoformat()}])
        res = refresh(_orders(), hist=h)
        t("history trade for instrument opened after reservation => blocked", res["released_stale_reservations"] == [])
        # pending order with unknown instrument blocks everything
        res = refresh(_orders(orders=[{"orderId": 51, "status": "placed"}]))
        t("pending order unknown instrument => all releases blocked", res["released_stale_reservations"] == [])
        # clean read: other-instrument position before reservation => released
        res = refresh(_orders(positions=[_pos(61, 3000, now - timedelta(minutes=40)), _pos(62, 1001, now - timedelta(hours=2))]))
        t("no pending / no newer position for instrument => stale reservation released",
          r1 in [x["id"] for x in res["released_stale_reservations"]], res["released_stale_reservations"])
        # orders read stale => nothing released, refresh not ok, prebuy state removed
        r2 = fresh_res(1001)
        res = refresh(_orders(age_s=90))
        t("stale orders read => not ok, no release, no prebuy state",
          not res["ok"] and res["released_stale_reservations"] == [] and not PB.state_paths()["prebuy"].exists())
        res = PB.refresh(history_raw=_hist(), rates_raw=RATES, instrument_ids=[1001], now=now, read_at=now)
        t("orders response omitted => not ok (ORDERS_RESPONSE_REQUIRED)", not res["ok"]
          and res["orders"]["error"] == "ORDERS_RESPONSE_REQUIRED")
        TC.release(r2)
        # pending orders count as used slots in refresh counter
        res = refresh(_orders(orders=[_ord(70 + i, 1001, now - timedelta(minutes=10)) for i in range(4)]))
        t("4 pending orders today => counter full", res["counter"]["count"] >= 4 and not res["counter"]["ok"], res["counter"])
        t("prebuy state written with pending keys", PB.state_paths()["prebuy"].exists()
          and len(json.loads(PB.state_paths()["prebuy"].read_text())["pending_order_keys"]) == 4)
        # --- execute_pass gates
        (root / "state" / "daily_new_trades.json").unlink(missing_ok=True)
        write_envelope(root, [make_pack("T", entry=27.0, atr=0.5, notional=1000)])
        write_book(root)
        write_scores(root)
        write_run_qa()
        base = rsi()["blockers"]
        t("baseline: fresh prebuy => no PRE_BUY/count blockers",
          not {"PRE_BUY_NOT_FRESH", "DAILY_TRADE_LIMIT", "BOOK_NOT_FRESH_FOR_COUNT"} & set(base), base)
        (root / "prebuy-state.json").unlink()
        t("no prebuy state => PRE_BUY_NOT_FRESH", "PRE_BUY_NOT_FRESH" in rsi()["blockers"])
        write_prebuy(root, age_s=301)
        t("prebuy 5m01s old => PRE_BUY_NOT_FRESH", "PRE_BUY_NOT_FRESH" in rsi()["blockers"])
        write_prebuy(root, orders_ok=False)
        t("prebuy without orders_ok => PRE_BUY_NOT_FRESH", "PRE_BUY_NOT_FRESH" in rsi()["blockers"])
        write_prebuy(root, pending=["order:1", "order:2", "order:3", "order:4"])
        t("4 pending orders in prebuy state => DAILY_TRADE_LIMIT", "DAILY_TRADE_LIMIT" in rsi()["blockers"])
        write_prebuy(root)
        write_book(root, age_s=61)
        b = rsi()["blockers"]
        t("book 61 s old => BOOK_NOT_FRESH_FOR_COUNT", "BOOK_NOT_FRESH_FOR_COUNT" in b, b)
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

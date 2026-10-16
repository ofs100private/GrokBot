"""QA WARN fixes (2026-10-16 fix2): pre_buy refresh (history validation, live isOpen from rates quote
freshness, stale reservation release), union daily count, test-mode GO never placeable. Never calls eToro.

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_prebuy_20261016
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import execute_pass as X
from . import pre_buy as PB
from . import trade_counter as TC
from .testkit import MON, buy_prepare, make_pack, test_root, ts, write_book, write_envelope, write_order_qa, \
    write_run_qa, write_scores
from .test_execute_pass import rsi, rsi_ready  # noqa: F401

UTC = timezone.utc
IDT = ZoneInfo("Asia/Jerusalem")


def _hist(trades, sc=200, more=False):
    return {"account": "real", "statusCode": sc, "hasMore": more, "trades": trades}


def _tr(pid, open_dt, close_dt):
    return {"positionId": pid, "openTime": open_dt.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "closeTime": close_dt.astimezone(UTC).isoformat().replace("+00:00", "Z"), "market": {"instrumentId": 1}}


def run():
    out = []
    t = lambda n, ok, d="": out.append((n, bool(ok), d))  # noqa: E731
    now = MON
    y = now - timedelta(days=1)
    # --- history validation
    h = PB.parse_history(_hist([_tr(1, now - timedelta(hours=2), now - timedelta(hours=1)),
                                _tr(2, y, now - timedelta(hours=1)), _tr(3, y - timedelta(days=2), y)]), now)
    t("history success: only same-IDT-day opens counted", h["ok"] and h["opened_today_position_ids"] == ["1"], h)
    t("history: execute-read envelope unwrapped",
      PB.parse_history({"statusCode": 200, "isSuccess": True, "body": json.dumps(_hist([]))}, now)["ok"])
    t("history: wrapper text around JSON tolerated", PB.parse_history("<x>\n" + json.dumps(_hist([])) + "\n</x>", now)["ok"])
    for lbl, raw in (("empty string", ""), ("not json", "{oops"), ("error status", _hist([], sc=401)),
                     ("error key", {**_hist([]), "error": "unauthorized"}), ("no trades list", {"statusCode": 200}),
                     ("list body", [1, 2]),
                     ("unparseable openTime", _hist([{"positionId": 1, "openTime": "yesterday-ish",
                                                      "closeTime": "2026-10-12T10:00:00Z"}])),
                     ("missing positionId", _hist([{"openTime": "2026-10-12T10:00:00Z", "closeTime": "2026-10-12T11:00:00Z"}])),
                     ("hasMore and page all today", _hist([_tr(5, now - timedelta(hours=3), now - timedelta(hours=1))], more=True)),
                     ("execute-read 500", {"statusCode": 500, "isSuccess": False, "body": "{}"})):
        t(f"history fails closed: {lbl}", not PB.parse_history(raw, now)["ok"])
    t("history hasMore but page reaches before today => ok",
      PB.parse_history(_hist([_tr(6, y - timedelta(days=1), y)], more=True), now)["ok"])
    # --- rates -> isOpen
    rd = now.astimezone(UTC)
    rates = {"rates": [
        {"instrumentID": 1001, "bid": 341.49, "ask": 341.58, "date": (rd - timedelta(seconds=40)).isoformat().replace("+00:00", "Z")},
        {"instrumentID": 3000, "bid": 772.29, "ask": 772.3, "date": (rd - timedelta(hours=3)).isoformat().replace("+00:00", "Z")},
        {"instrumentID": 8754, "bid": 0, "ask": 343.2, "date": (rd - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")}]}
    r = PB.parse_rates({"statusCode": 200, "body": json.dumps(rates)}, rd, [1001, 3000, 8754, 4242])
    ins = r["instruments"]
    t("rates: fresh quote => open", ins["1001"]["is_open"] is True)
    t("rates: 3h-old quote => closed (QUOTE_STALE)", ins["3000"]["is_open"] is False and ins["3000"]["reason"] == "QUOTE_STALE")
    t("rates: bid 0 => closed", ins["8754"]["is_open"] is False)
    t("rates: instrument missing => closed", ins["4242"]["is_open"] is False and ins["4242"]["reason"] == "NO_RATE")
    t("rates: garbage => not ok", not PB.parse_rates("nope", rd, [1])["ok"])
    with test_root() as root:
        os.environ.pop(TC.ENV_OVERRIDE, None)
        # --- union count
        TC.reserve("a", "S", now=now)
        rb = TC.reserve("b", "S", now=now)["reservation"]
        TC.mark(rb, position_id=777)
        st = TC.status(now, external_position_ids=["777", "888"])
        t("union: 1 reserved + {777 placed ∪ 777,888 history} = 3 (not max)", st["count"] == 3 and st["history_only_opens"] == 1, st)
        st = TC.status(now, external_position_ids=["888", "999"])
        t("union: history-only opens add to reservations", st["count"] == 4 and not st["ok"], st)
        # --- refresh end-to-end + stale release
        stale_at = now - timedelta(minutes=45)
        rs = TC.reserve("old", "S", now=stale_at)["reservation"]
        res = PB.refresh(history_raw=json.dumps(_hist([_tr(777, now - timedelta(hours=1), now - timedelta(minutes=10))])),
                         rates_raw=json.dumps({"statusCode": 200, "body": json.dumps(rates)}), instrument_ids=[1001, 3000],
                         orders_raw=json.dumps({"statusCode": 200, "timestamp": rd.isoformat(),
                                                "direct": {"positions": [], "orders": []}}),
                         now=now, read_at=rd)
        rel = [x["id"] for x in res["released_stale_reservations"]]
        t("refresh ok; writes history + open state", res["ok"] and PB.state_paths()["history"].exists()
          and PB.state_paths()["open"].exists(), res.get("history"))
        t("refresh releases only the >30 min unmarked reservation", rel == [rs], rel)
        t("refresh flags: 1001 true / 3000 false", res["instrument_open_flags"] == {"1001": "true", "3000": "false"})
        t("load_open_state reads fresh state", PB.load_open_state(1001, now) is True and PB.load_open_state(3000, now) is False)
        t("load_open_state stale (>5 min) => None", PB.load_open_state(1001, now + timedelta(minutes=10)) is None)
        bad = PB.refresh(history_raw="", rates_raw="{}", instrument_ids=[1001], now=now, read_at=rd)
        t("refresh with empty history: not ok, history file removed, nothing released",
          not bad["ok"] and not PB.state_paths()["history"].exists() and bad["released_stale_reservations"] == [])
        # --- execute_pass end-to-end with refresh state and test-mode labelling
        T = make_pack("T", entry=27.0, atr=0.5, notional=1000)
        write_envelope(root, [T])
        write_book(root)
        write_scores(root)
        write_run_qa()
        (root / "state" / "daily_new_trades.json").unlink(missing_ok=True)
        (root / "history.json").write_text(json.dumps({"asOf": ts(now, 10), "response": _hist([], sc=500)}))
        t("history file with error response => TRADING_HISTORY_MISSING", "TRADING_HISTORY_MISSING" in rsi()["blockers"])
        write_book(root)
        plan, r, anc = rsi_ready()
        write_order_qa(r)
        fresh = buy_prepare(plan["order_payloads"][0], ask=anc["anchor_ask"], quote_ts=ts(now, 2))
        g = rsi(prepare_response=fresh, write_lock=True, **anc)
        t("test-mode GO is labelled and NOT placeable / not auto-place eligible",
          g["decision"] == "GO" and g["test_mode"] is True and g["placeable"] is False
          and g["auto_place_eligible"] is False and "NEVER place" in g.get("test_mode_warning", ""), g["blockers"])
        TC.release(g["trade_reservation_id"])
        for p_ in g.get("locks") or []:
            os.unlink(p_)
        # isOpen from pre_buy state when caller omits it (T resolves to AT&T id from the map)
        iid = plan["instrumentId"]
        (root / "instrument-open.json").write_text(json.dumps({"asOf": now.isoformat(), "instruments": {str(iid): {"is_open": False}}}))
        r2 = X.run_checks.__wrapped__(pack_id=plan["pack_id"], bid=27.03, ask=27.05, quote_ts=ts(now, 5), mark=27.05, units=23.0,
                          open_fee_usd=0.75, close_fee_usd=0.75, now=now, write_lock=False,
                          momentum_read=__import__("classic_rsi.testkit", fromlist=["momentum_read"]).momentum_read(now=now))
        t("isOpen omitted -> taken from pre_buy state (closed) => INSTRUMENT_CLOSED",
          "INSTRUMENT_CLOSED" in r2["blockers"] and r2.get("instrument_open_source", "").startswith("pre_buy"), r2["blockers"])
        (root / "instrument-open.json").unlink()
        r3 = X.run_checks.__wrapped__(pack_id=plan["pack_id"], bid=27.03, ask=27.05, quote_ts=ts(now, 5), mark=27.05, units=23.0,
                          open_fee_usd=0.75, close_fee_usd=0.75, now=now, write_lock=False,
                          momentum_read=__import__("classic_rsi.testkit", fromlist=["momentum_read"]).momentum_read(now=now))
        t("no state + no caller isOpen => INSTRUMENT_OPEN_UNKNOWN", "INSTRUMENT_OPEN_UNKNOWN" in r3["blockers"])
    # CLI refuses test mode (exit 3) - source check (CLI needs live inputs)
    import inspect
    t("CLI returns 3 for any test-mode result", "return 3" in inspect.getsource(X.main))
    from . import auto_1h as A
    t("auto_1h adds TEST_MODE hard flag when CLASSIC_EXEC_TEST_ROOT set", '"TEST_MODE"' in inspect.getsource(A.run_auto_1h))
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

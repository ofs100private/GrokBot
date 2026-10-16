"""Pre-buy refresh for Classic FULL AUTO (QA WARN fix 2026-10-16). Run before EVERY buy GO.

The script has no eToro access of its own: Trader_Classic makes two READ-ONLY MCP calls on
user-OfersClaw5, saves the raw outputs, and passes them here:

  1. get-my-trading-history                      -> --history-response FILE
  2. execute-read GET /api/v1/market-data/instruments/rates?instrumentIds=<ids>
                                                 -> --rates-response FILE
  3. get-my-positions-and-orders (<= 60 s old)   -> --orders-response FILE

It then (fail closed on anything unexpected):
  * validates the history is a recognisable SUCCESS response (statusCode 200, a `trades` list, every
    trade has a parseable openTime/closeTime, and the page reaches back before today's IDT midnight
    or hasMore=false) and writes /workspace/classic_rsi/state/trading-history-today.json;
  * derives a live per-instrument isOpen from the rates read: open iff the instrument's last quote
    `date` is within OPEN_QUOTE_MAX_AGE_S of the read time and bid/ask > 0 (eToro stops quoting an
    instrument outside its tradable session — e.g. 2026-10-16 01:39 IDT: AAPL 1001 quoting live
    (extended hours) while SPY 3000 and AAPL.RTH 8754 were last quoted at 19:28Z). Writes
    /workspace/classic_rsi/state/instrument-open.json;
  * releases unmarked daily-slot reservations older than 30 minutes.
Prints a JSON summary incl. the `--instrument-open true|false` value to pass to execute_pass.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from . import trade_counter as TC
from .paths import TEST_ENV, paths

IDT = ZoneInfo("Asia/Jerusalem")
OPEN_QUOTE_MAX_AGE_S = 300.0
OPEN_STATE_MAX_AGE_S = 300.0
ORDERS_MAX_AGE_S = 60.0       # positions-and-orders read used for counting must be <= 60 s old
PREBUY_MAX_AGE_S = 300.0      # execute_pass: pre_buy must have run (all reads ok) <= 5 min before GO
TERMINAL_ORDER = ("canceled", "cancelled", "rejected", "expired", "executed", "filled")
RATES_ENDPOINT = "GET /api/v1/market-data/instruments/rates?instrumentIds=<ids> (user-OfersClaw5 execute-read)"


def _unwrap(raw: Any) -> Any:
    """Accept a dict, a JSON string, or an execute-read envelope {statusCode, body:"<json>"}."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            raise ValueError("empty response")
        if not s.startswith(("{", "[")) and "{" in s:  # tolerate a tool-output wrapper line around the JSON
            s = s[s.index("{"): s.rindex("}") + 1]
        raw = json.loads(s)
    if isinstance(raw, dict) and isinstance(raw.get("body"), str) and "trades" not in raw and "rates" not in raw:
        sc = raw.get("statusCode")
        if sc not in (200, None) or raw.get("isSuccess") is False:
            raise ValueError(f"execute-read not successful: statusCode={sc}")
        inner = json.loads(raw["body"])
        if isinstance(inner, dict):
            inner.setdefault("statusCode", sc)
        raw = inner
    return raw


def _ts(v: Any) -> Optional[datetime]:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        t = datetime.fromisoformat(v.strip().replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse_history(raw: Any, now: datetime) -> dict[str, Any]:
    """Validate a get-my-trading-history response. Returns {ok, error, opened_today_position_ids, ...}."""
    try:
        d = _unwrap(raw)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"HISTORY_UNPARSEABLE: {e}"}
    if not isinstance(d, dict):
        return {"ok": False, "error": "HISTORY_NOT_OBJECT"}
    if d.get("statusCode") != 200 or d.get("error") or d.get("errors"):
        return {"ok": False, "error": f"HISTORY_NOT_SUCCESS: statusCode={d.get('statusCode')} error={d.get('error')}"}
    trades = d.get("trades")
    if not isinstance(trades, list):
        return {"ok": False, "error": "HISTORY_NO_TRADES_LIST"}
    day0 = now.astimezone(IDT).replace(hour=0, minute=0, second=0, microsecond=0)
    ids: set[str] = set()
    meta: list[dict[str, Any]] = []
    oldest_close: Optional[datetime] = None
    for i, tr in enumerate(trades):
        if not isinstance(tr, dict):
            return {"ok": False, "error": f"HISTORY_TRADE_{i}_NOT_OBJECT"}
        ot, ct = _ts(tr.get("openTime")), _ts(tr.get("closeTime"))
        pid = tr.get("positionId")
        if ot is None or ct is None or pid in (None, ""):
            return {"ok": False, "error": f"HISTORY_TRADE_{i}_BAD_FIELDS (openTime/closeTime/positionId)"}
        if ot >= day0:
            ids.add(str(pid))
        meta.append({"positionId": str(pid), "instrumentId": (tr.get("market") or {}).get("instrumentId",
                     tr.get("instrumentId")), "openTime": ot.isoformat()})
        oldest_close = ct if oldest_close is None or ct < oldest_close else oldest_close
    if d.get("hasMore") and (oldest_close is None or oldest_close >= day0):
        return {"ok": False, "error": "HISTORY_PAGE_DOES_NOT_COVER_TODAY (hasMore and oldest close is today)"}
    return {"ok": True, "error": None, "opened_today_position_ids": sorted(ids), "trades_seen": len(trades), "trades_meta": meta,
            "has_more": bool(d.get("hasMore")), "xRequestId": d.get("xRequestId")}


def parse_rates(raw: Any, read_at: datetime, instrument_ids: list[int]) -> dict[str, Any]:
    try:
        d = _unwrap(raw)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"RATES_UNPARSEABLE: {e}", "instruments": {}}
    rates = d.get("rates") if isinstance(d, dict) else None
    if not isinstance(rates, list):
        return {"ok": False, "error": "RATES_NO_LIST", "instruments": {}}
    by = {}
    for r in rates:
        if isinstance(r, dict) and r.get("instrumentID") is not None:
            by[int(r["instrumentID"])] = r
    out: dict[str, Any] = {}
    for iid in instrument_ids:
        r = by.get(int(iid))
        if r is None:
            out[str(iid)] = {"is_open": False, "reason": "NO_RATE"}
            continue
        qt = _ts(r.get("date"))
        bid, ask = r.get("bid"), r.get("ask")
        age = None if qt is None else (read_at - qt).total_seconds()
        ok = (age is not None and -30 <= age <= OPEN_QUOTE_MAX_AGE_S and isinstance(bid, (int, float))
              and isinstance(ask, (int, float)) and 0 < bid <= ask)
        out[str(iid)] = {"is_open": bool(ok), "quote_date": r.get("date"), "quote_age_s": None if age is None else round(age, 1),
                         "bid": bid, "ask": ask,
                         "reason": None if ok else ("QUOTE_STALE" if age is not None else "QUOTE_TIME_MISSING")}
    return {"ok": True, "error": None, "instruments": out, "rule": f"open iff last quote <= {OPEN_QUOTE_MAX_AGE_S:g}s old"}


def parse_orders(raw: Any, read_at: datetime) -> dict[str, Any]:
    """Validate a user-OfersClaw5 get-my-positions-and-orders response (Classic `direct` block).
    Returns open positions (instrumentId, positionId, openTime) and pending (non-terminal) orders.
    Fail closed: non-200/error, missing direct.positions/orders lists, stale `timestamp` (> 60 s),
    unparseable position openTime. A pending order without a parseable time or instrumentId is kept
    with time=None (counts as today and blocks every stale release)."""
    try:
        d = _unwrap(raw)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"ORDERS_UNPARSEABLE: {e}"}
    if not isinstance(d, dict) or d.get("statusCode") != 200 or d.get("error"):
        return {"ok": False, "error": f"ORDERS_NOT_SUCCESS: statusCode={(d or {}).get('statusCode') if isinstance(d, dict) else None}"}
    blk = d.get("direct")
    if not isinstance(blk, dict) or not isinstance(blk.get("positions"), list) or not isinstance(blk.get("orders"), list):
        return {"ok": False, "error": "ORDERS_NO_DIRECT_LISTS"}
    ts_ = _ts(d.get("timestamp"))
    age = None if ts_ is None else (read_at - ts_).total_seconds()
    if age is None or not (-30 <= age <= ORDERS_MAX_AGE_S):
        return {"ok": False, "error": f"ORDERS_STALE: timestamp={d.get('timestamp')} age_s={age}"}
    positions, pending = [], []
    for i, p in enumerate(blk["positions"]):
        m = p.get("market") or {}
        ot = _ts(p.get("openTime"))
        if ot is None or p.get("positionId") in (None, ""):
            return {"ok": False, "error": f"ORDERS_POSITION_{i}_BAD_FIELDS"}
        positions.append({"positionId": str(p["positionId"]), "instrumentId": m.get("instrumentId", p.get("instrumentId")),
                          "openTime": ot.isoformat()})
    for o in blk["orders"]:
        if str(o.get("status") or "").lower() in TERMINAL_ORDER:
            continue
        m = o.get("market") or {}
        t = None
        for k in ("openTime", "orderTime", "createdAt", "openDateTime", "requestTime", "date"):
            t = _ts(o.get(k))
            if t:
                break
        oid = o.get("orderId") or o.get("orderID") or o.get("id")
        pending.append({"orderId": None if oid is None else str(oid),
                        "instrumentId": m.get("instrumentId", o.get("instrumentId")),
                        "time": None if t is None else t.isoformat(), "status": o.get("status")})
    return {"ok": True, "error": None, "timestamp": d.get("timestamp"), "age_s": round(age, 1),
            "positions": positions, "pending_orders": pending, "xRequestId": d.get("xRequestId")}


def pending_keys_today(orders: dict[str, Any], now: datetime) -> list[str]:
    """Pending (unfilled) orders placed today (IDT) — or with unknown time — count as used slots."""
    day0 = now.astimezone(IDT).replace(hour=0, minute=0, second=0, microsecond=0)
    keys = []
    for i, o in enumerate(orders.get("pending_orders") or []):
        t = _ts(o.get("time"))
        if t is None or t >= day0:
            keys.append(f"order:{o.get('orderId') or f'unknown{i}'}")
    return keys


def release_blocker(orders: dict[str, Any], history: dict[str, Any]):
    """Return fn(slot, reserved_at) -> reason|None for TC.release_stale."""
    def fn(slot: dict, reserved_at: datetime) -> Optional[str]:
        iid = slot.get("instrumentId")
        for o in orders.get("pending_orders") or []:
            if o.get("instrumentId") is None or iid is None:
                return "PENDING_ORDER_UNKNOWN_INSTRUMENT"
            if str(o["instrumentId"]) == str(iid):
                return f"PENDING_ORDER_FOR_INSTRUMENT {iid}"
        for p in (orders.get("positions") or []) + (history.get("trades_meta") or []):
            t = _ts(p.get("openTime"))
            if (iid is None or str(p.get("instrumentId")) == str(iid)) and (t is None or t >= reserved_at):
                return f"POSITION_OPENED_AFTER_RESERVATION {iid} positionId={p.get('positionId')}"
        return None
    return fn


def state_paths() -> dict[str, Path]:
    P = paths()
    base = Path(P["history"])
    return {"history": base, "open": base.with_name("instrument-open.json"),
            "prebuy": base.with_name("prebuy-state.json")}


def load_prebuy_state(now: datetime) -> dict[str, Any]:
    """execute_pass: the last successful pre_buy refresh, required <= 5 min old with history+rates+orders ok."""
    p = state_paths()["prebuy"]
    try:
        d = json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "path": str(p), "error": f"PREBUY_MISSING: {e}"}
    t = _ts(d.get("asOf"))
    age = None if t is None else (now - t).total_seconds()
    fresh = age is not None and -5 <= age <= PREBUY_MAX_AGE_S
    allok = all(d.get(k) is True for k in ("history_ok", "rates_ok", "orders_ok"))
    return {**d, "ok": bool(fresh and allok), "age_s": age, "path": str(p),
            "error": None if (fresh and allok) else ("PREBUY_STALE" if not fresh else "PREBUY_INCOMPLETE")}


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, indent=2, default=str)
    os.replace(tmp, path)


def load_open_state(iid: Any, now: datetime) -> Optional[bool]:
    """Live isOpen for iid from the last refresh (<= 5 min old), else None (=> CLOSED for stocks/ETFs)."""
    p = state_paths()["open"]
    try:
        d = json.loads(p.read_text())
        t = _ts(d.get("asOf"))
        if t is None or not (-5 <= (now - t).total_seconds() <= OPEN_STATE_MAX_AGE_S):
            return None
        v = (d.get("instruments") or {}).get(str(int(iid)))
        return None if not isinstance(v, dict) else (v.get("is_open") is True)
    except Exception:  # noqa: BLE001
        return None


def refresh(*, history_raw: Any, rates_raw: Any, instrument_ids: list[int], orders_raw: Any = None,
            now: Optional[datetime] = None, read_at: Optional[datetime] = None,
            orders_read_at: Optional[datetime] = None, release_after_min: float = 30.0) -> dict[str, Any]:
    now = now or datetime.now(IDT)
    read_at = read_at or now
    sp = state_paths()
    out: dict[str, Any] = {"kind": "pre_buy_refresh", "asOf": now.isoformat(), "test_mode": paths()["test_mode"],
                           "rates_endpoint": RATES_ENDPOINT}
    h = parse_history(history_raw, now)
    out["history"] = {k: v for k, v in h.items() if k != "trades_meta"}
    od = parse_orders(orders_raw, orders_read_at or now) if orders_raw is not None else {"ok": False, "error": "ORDERS_RESPONSE_REQUIRED"}
    out["orders"] = {k: v for k, v in od.items()}
    if h["ok"]:
        resp = _unwrap(history_raw)
        _atomic_write(sp["history"], {"asOf": now.isoformat(), "source": "user-OfersClaw5 get-my-trading-history",
                                      "validated_by": "pre_buy.parse_history", "response": resp})
        out["history"]["path"] = str(sp["history"])
        # release stale reservations only after successful history AND positions/orders reads; a pending
        # order or a position for that instrument opened after the reservation blocks the release
        out["released_stale_reservations"] = (TC.release_stale(release_after_min, now, blocker=release_blocker(od, h))
                                              if od["ok"] else [])
    else:
        sp["history"].unlink(missing_ok=True)  # never leave an old success file behind a failed read
        out["released_stale_reservations"] = []
    r = parse_rates(rates_raw, read_at, instrument_ids)
    out["open"] = r
    if r["ok"]:
        _atomic_write(sp["open"], {"asOf": read_at.isoformat(), "rule": r["rule"], "endpoint": RATES_ENDPOINT,
                                   "instruments": r["instruments"]})
    else:
        sp["open"].unlink(missing_ok=True)
    out["instrument_open_flags"] = {k: ("true" if v.get("is_open") else "false") for k, v in r["instruments"].items()}
    day0 = now.astimezone(IDT).replace(hour=0, minute=0, second=0, microsecond=0)
    book_ids = [p["positionId"] for p in od.get("positions") or [] if (_ts(p["openTime"]) or day0) >= day0]
    pend = pending_keys_today(od, now) if od["ok"] else []
    ext = sorted(set(h.get("opened_today_position_ids") or []) | set(book_ids) | set(pend))
    out["counter"] = TC.status(now, external_position_ids=ext)
    out["ok"] = bool(h["ok"] and r["ok"] and od["ok"])
    st = {"asOf": now.isoformat(), "history_ok": bool(h["ok"]), "rates_ok": bool(r["ok"]), "orders_ok": bool(od["ok"]),
          "opened_today_position_ids": sorted(set(h.get("opened_today_position_ids") or []) | set(book_ids)),
          "pending_order_keys": pend, "orders_timestamp": od.get("timestamp"), "rates_read_at": read_at.isoformat()}
    if out["ok"]:
        _atomic_write(sp["prebuy"], st)
    else:
        sp["prebuy"].unlink(missing_ok=True)
    out["prebuy_state"] = st
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history-response", required=True, help="file: raw get-my-trading-history output")
    ap.add_argument("--rates-response", required=True, help="file: raw execute-read rates output")
    ap.add_argument("--instrument-ids", required=True, help="comma list of instrumentIds in the rates read")
    ap.add_argument("--orders-response", required=True, help="file: raw get-my-positions-and-orders output (<= 60 s old)")
    ap.add_argument("--rates-read-at", help="ISO time the rates read returned (default: now)")
    a = ap.parse_args(argv)
    if os.environ.get(TEST_ENV):
        print(json.dumps({"warning": "TEST MODE (CLASSIC_EXEC_TEST_ROOT set): writes test state only"}))
    ids = [int(x) for x in a.instrument_ids.split(",") if x.strip()]
    ra = datetime.fromisoformat(a.rates_read_at) if a.rates_read_at else None
    res = refresh(history_raw=Path(a.history_response).read_text(), rates_raw=Path(a.rates_response).read_text(),
                  orders_raw=Path(a.orders_response).read_text(), instrument_ids=ids, read_at=ra)
    print(json.dumps(res, indent=2, default=str))
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

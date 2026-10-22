"""Momentum EOD step-0 pre-check (Ofer 2026-10-18: Momentum moves to code-first like Classic).

Fixed, checked-in script. Read-only: never calls eToro / MCP, never places, no trading-rule changes.
Scripts cannot call MCP, so the routine does ONE MCP read with write_to_file=true and passes the file:
  * Momentum keys  user-Momentum-HHHGDTJ get-my-positions-and-orders {account:"real"}   (required on NYSE days)
    (a keys get-my-portfolio-summary file is also accepted; it carries totals.availableCash)
  * optional Classic user-OfersClaw5 read (summary or positions)       -> cross-book overlap / buy blocklist
  * optional cash source: --cash N, or --cash-json <user-etoro get-my-portfolio-summary file> (mirror 11630170
    availableCash = Momentum reporting truth). The keys balance endpoint may 403, so cash precedence is:
    --cash > --cash-json (mirror 11630170) > keys raw totals.availableCash (summary shape) > unknown.

Decision (exit code):
  10 SKIP (silent)  NYSE closed / holiday today (NY date, nyse_session.nyse_today_is_open), OR
                    free cash < MIN_ORDER_USD AND nothing to manage (no open positions, no pending orders,
                    no missing SL, no position-manager risk action).
   0 PROCEED        anything else. Fail-OPEN: unreadable / unsuccessful / stale (>15 min) raw, unknown cash,
                    or an ingest error never skips. Open positions always PROCEED (the EOD position manager
                    must evaluate SMA50 / -4% / 1R / 2R on every held name; that needs Yahoo, not this script).
  Forcing PROCEED reasons (listed in "manage"): open_positions, pending_orders, stop_missing, stop_hit,
  loss_pct_ge_4 (raw pnl% <= -4), pm_risk_action (CLOSE / MOVE_SL_BREAKEVEN / TRAIL_SL in --pm-json).

Side effects on a NYSE day (when --raw is given):
  python3 -m books.snapshot ingest --book momentum_keys --raw <raw>   (in-process, same code path)
  python3 -m books.snapshot ingest --book classic --raw <classic>     (if --classic-raw)
  python3 -m books.snapshot overlap
  Summary JSON -> --out (default /workspace/momentum_audit/precheck/precheck-latest.json, plus a timestamped
  copy) with cash, normalized positions (pm_positions = position_manager input), pending orders, overlap and
  the Classic buy blocklist. One audit line per run -> /workspace/momentum_audit/precheck-YYYY-MM-DD.jsonl.
  stdout: one JSON line {decision, reasons, summary_path, audit_file}.

CLI (run from /workspace):
  ./screener-venv/bin/python -m momentum_qa.precheck --raw <mkeys-positions.json> \
      [--classic-raw <classic.json>] [--cash-json <etoro-summary.json> | --cash N] [--pm-json <pm-out.json>] \
      [--out <summary.json>] [--min-order 50] [--no-audit] [--no-ingest]
  Holiday short-circuit: --raw may be omitted; a closed NYSE day exits 10 before any file is needed.

classic-fresh (QA 2026-10-21; run right before EACH place-trade, after a fresh user-OfersClaw5 read):
  ./screener-venv/bin/python -m momentum_qa.precheck classic-fresh --classic-raw <classic.json> \
      [--max-age 900] [--save]
  exit 0 FRESH; 2 STALE / MISSING / UNREADABLE / unsuccessful read / --max-age > 900 (MAX_AGE_TOO_HIGH)
  (fail closed: do NOT place);
  --save (only when fresh) writes the cross-book snapshot via classic_book.save_snapshot
  (symbols + instrumentIds, also classic_holdings_latest.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import nyse_session  # noqa: E402
from momentum_qa.instrument_map import base_symbol, held_id_mismatch

IDT = ZoneInfo("Asia/Jerusalem")
EXIT_PROCEED, EXIT_SKIP = 0, 10
MIN_ORDER_USD = 50.0          # smallest order worth a screener pass (no Momentum min existed; not a sizing rule)
RAW_MAX_AGE_S = 900.0         # a raw older than 15 min cannot justify a skip
MIRROR_ID = 11630170          # Momentum reporting truth inside the parent account
RISK_ACTIONS = ("CLOSE", "MOVE_SL_BREAKEVEN", "TRAIL_SL")
TERMINAL_ORDER = ("canceled", "cancelled", "rejected", "expired", "filled", "executed")


def audit_dir() -> Path:
    return Path(os.environ.get("MOMENTUM_AUDIT_DIR", "/workspace/momentum_audit"))


def _num(x: Any) -> Optional[float]:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def load_json_file(path: str | Path) -> Any:
    """Saved MCP output: tolerates wrapper text around the JSON object (write_to_file output)."""
    txt = Path(path).read_text()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        s = txt.strip()
        i = min([k for k in (s.find("{"), s.find("[")) if k >= 0], default=-1)
        if i < 0:
            raise
        close = "}" if s[i] == "{" else "]"
        return json.loads(s[i: s.rindex(close) + 1])


def _unwrap(d: Any) -> Any:
    if isinstance(d, dict) and isinstance(d.get("response"), dict) and not ({"direct", "totals", "holdings"} & set(d)):
        return _unwrap(d["response"])
    return d


def _ts(d: dict) -> Optional[datetime]:
    v = d.get("timestamp") or d.get("asOf")
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    if "." in s:  # eToro 7-digit fractions
        head, rest = s.split(".", 1)
        frac = "".join(ch for ch in rest if ch.isdigit())
        tz = rest[len(frac):]
        s = f"{head}.{frac[:6]}{tz}"
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse_keys_raw(raw: Any, now: datetime) -> dict[str, Any]:
    """Momentum keys get-my-positions-and-orders (or get-my-portfolio-summary) -> normalized lots/orders/cash."""
    d = _unwrap(raw)
    if not isinstance(d, dict):
        return {"ok": False, "error": "RAW_NOT_OBJECT"}
    if d.get("error") or int(d.get("statusCode") or 0) != 200:
        return {"ok": False, "error": f"RAW_NOT_SUCCESS: statusCode={d.get('statusCode')} error={d.get('error')!r}"}
    if str(d.get("account", "real")) != "real":
        return {"ok": False, "error": f"RAW_NOT_REAL_ACCOUNT: {d.get('account')}"}
    if d.get("mirrors") or d.get("copiedTraders"):
        return {"ok": False, "error": "RAW_SOURCE_MISMATCH: parent user-etoro shape (mirrors/copiedTraders), not keys"}
    t = _ts(d)
    if t is None:
        return {"ok": False, "error": "RAW_NO_TIMESTAMP"}
    age = (now - t).total_seconds()
    lots: list[dict] = []
    orders_raw: list = []
    cash = None
    if isinstance(d.get("direct"), dict):
        shape = "positions"
        for p in d["direct"].get("positions") or []:
            m = p.get("market") or {}
            lots.append(_lot(p, m.get("symbol"), m.get("instrumentId")))
        orders_raw = d["direct"].get("orders") or []
    elif "totals" in d or "holdings" in d:
        shape = "summary"
        cash = _num((d.get("totals") or {}).get("availableCash"))
        for h in d.get("holdings") or []:
            m = h.get("market") or {}
            pl = h.get("positions") or []
            if not pl:  # summary without includePositions: keep a holding-level row (SL unknown)
                lots.append({**_lot(h, m.get("symbol"), m.get("instrumentId")), "lot_rows_missing": True})
            for p in pl:
                lots.append(_lot(p, m.get("symbol"), m.get("instrumentId")))
        orders_raw = d.get("pendingOrders") or []
    else:
        return {"ok": False, "error": "RAW_UNKNOWN_SHAPE"}
    orders = []
    for o in orders_raw:
        if str(o.get("status", "")).lower() in TERMINAL_ORDER:
            continue
        m = o.get("market") or {}
        orders.append({"orderId": o.get("orderId"),
                       "symbol": base_symbol(m.get("symbol") or o.get("symbol"), m.get("instrumentId") or o.get("instrumentId")),
                       "instrumentId": m.get("instrumentId") or o.get("instrumentId"),
                       "action": o.get("action"), "type": o.get("type"), "status": o.get("status"),
                       "amount": _num(o.get("amount") or o.get("requestedAmount"))})
    return {"ok": True, "error": None, "shape": shape, "timestamp": d.get("timestamp"), "age_s": round(age, 1),
            "xRequestId": d.get("xRequestId"), "cash": cash, "lots": lots, "orders": orders}


def _lot(p: dict, sym: Any, iid: Any) -> dict:
    inv, pnl = _num(p.get("invested")), _num(p.get("pnl"))
    pct = _num(p.get("pnlPercent"))
    if pct is None and inv and pnl is not None:
        pct = round(pnl / inv * 100, 2)
    return {"positionId": p.get("positionId"), "symbol": base_symbol(sym, iid), "etoro_symbol": str(sym or "").upper(),
            "instrumentId": iid, "id_symbol_mismatch": held_id_mismatch(sym, iid),
            "openTime": p.get("openTime"), "avg_price": _num(p.get("openRate") or p.get("avgOpenRate")),
            "current_rate": _num(p.get("currentRate")), "units": _num(p.get("units")), "invested": inv, "pnl": pnl,
            "pnl_pct": pct, "leverage": p.get("leverage"), "direction": p.get("direction", "long"),
            "stop_loss": _num(p.get("stopLossRate")), "take_profit": _num(p.get("takeProfitRate"))}


def cash_from_mirror_file(path: str | Path) -> tuple[Optional[float], Optional[str]]:
    """user-etoro get-my-portfolio-summary (copiedTraders) or a books.snapshot momentum_mirror json."""
    d = _unwrap(load_json_file(path))
    if not isinstance(d, dict):
        return None, "CASH_JSON_NOT_OBJECT"
    if d.get("schema") == "books.snapshot.v1":
        if d.get("book") != "momentum_mirror":
            return None, f"CASH_JSON_WRONG_BOOK: {d.get('book')}"
        v = _num(d.get("available_cash"))
        return (v, None) if v is not None else (None, "CASH_JSON_NO_CASH")
    if d.get("error") or int(d.get("statusCode") or 0) != 200:
        return None, f"CASH_JSON_NOT_SUCCESS: {d.get('statusCode')}"
    ct = next((c for c in d.get("copiedTraders") or [] if int(c.get("mirrorId") or 0) == MIRROR_ID), None)
    if ct is None:
        return None, f"CASH_JSON_NO_MIRROR_{MIRROR_ID}"
    v = _num(ct.get("availableCash"))
    return (v, None) if v is not None else (None, "CASH_JSON_NO_CASH")


def pm_risk_actions(pm_out: Any) -> list[dict]:
    rows = pm_out if isinstance(pm_out, list) else (pm_out or {}).get("rows") or (pm_out or {}).get("actions") or []
    return [{"kind": "pm_risk_action", "symbol": r.get("symbol"), "action": r.get("action"), "reason": r.get("reason")}
            for r in rows if isinstance(r, dict) and r.get("action") in RISK_ACTIONS]


def manage_reasons(live: dict, pm_rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    lots = live["lots"]
    if lots:
        out.append({"kind": "open_positions", "n": len(lots), "symbols": sorted({x["symbol"] for x in lots})})
    if live["orders"]:
        out.append({"kind": "pending_orders", "n": len(live["orders"]), "symbols": sorted({o["symbol"] for o in live["orders"]})})
    for x in lots:
        if not x.get("stop_loss") and not x.get("lot_rows_missing"):
            out.append({"kind": "stop_missing", "symbol": x["symbol"], "positionId": x["positionId"]})
        px, sl = x.get("current_rate"), x.get("stop_loss")
        if px is not None and sl and px <= sl:
            out.append({"kind": "stop_hit", "symbol": x["symbol"], "px": px, "sl": sl})
        if x.get("pnl_pct") is not None and x["pnl_pct"] <= -4.0:
            out.append({"kind": "loss_pct_ge_4", "symbol": x["symbol"], "pnl_pct": x["pnl_pct"]})
    out += pm_rows
    return out


def run_books(raw: Optional[str], classic_raw: Optional[str]) -> dict[str, Any]:
    """books.snapshot ingest (momentum_keys [+ classic]) + overlap, in-process (same code as the CLI)."""
    from books import snapshot as S
    res: dict[str, Any] = {"ingest": {}, "overlap": None, "errors": []}
    for book, f in (("momentum_keys", raw), ("classic", classic_raw)):
        if not f:
            continue
        try:
            snap, paths = S.ingest(book, [f])
            res["ingest"][book] = {"ok": True, **paths, "read_at_idt": snap["read_at_idt"], "warnings": snap["warnings"]}
        except Exception as e:  # noqa: BLE001  (fail-open: decision never depends on the cache)
            res["ingest"][book] = {"ok": False, "error": str(e)}
            res["errors"].append(f"ingest {book}: {e}")
    try:
        res["overlap"] = S.overlap()
        c = S.fresh("classic", 60)
        res["classic_symbols"] = sorted({base_symbol(p["norm_symbol"], p.get("instrumentId")) for p in c["positions"]} |
                                        {base_symbol(o["symbol"], o.get("instrumentId")) for o in c.get("pending_orders") or []
                                         if o.get("action") != "close"}) if c else None
    except Exception as e:  # noqa: BLE001
        res["errors"].append(f"overlap: {e}")
    return res


def decide(raw: Any, now: datetime, *, cash_override: Optional[float] = None, cash_json: Optional[str] = None,
           pm_out: Any = None, min_order: float = MIN_ORDER_USD) -> dict[str, Any]:
    rec: dict[str, Any] = {"at": now.astimezone(IDT).isoformat(timespec="seconds"), "slot": "momentum-eod",
                           "portfolio": "Momentum-HHHGDTJ", "decision": "PROCEED", "reasons": [], "min_order": min_order}
    if not nyse_session.nyse_today_is_open(now):
        rec.update(decision="SKIP", reasons=["NYSE_CLOSED_OR_HOLIDAY"])
        return rec
    if raw is None:
        rec["reasons"] = ["RAW_MISSING"]
        return rec
    live = parse_keys_raw(raw, now)
    if not live["ok"]:
        rec.update(reasons=["RAW_NOT_USABLE"], error=live["error"])
        return rec
    cash, src, cash_err = None, None, None
    if cash_override is not None:
        cash, src = float(cash_override), "--cash"
    elif cash_json:
        try:
            cash, cash_err = cash_from_mirror_file(cash_json)
        except Exception as e:  # noqa: BLE001
            cash_err = f"CASH_JSON_UNREADABLE: {e}"
        src = f"mirror {MIRROR_ID}" if cash is not None else None
    if cash is None and live["cash"] is not None:
        cash, src = live["cash"], "keys totals.availableCash"
    rec.update(cash=cash, cash_source=src, raw_shape=live["shape"], raw_xRequestId=live["xRequestId"],
               raw_age_s=live["age_s"], live=live)
    if cash_err:
        rec["cash_error"] = cash_err
    pm_rows = pm_risk_actions(pm_out) if pm_out is not None else []
    manage = manage_reasons(live, pm_rows)
    rec["manage"] = manage
    if not (-60 <= live["age_s"] <= RAW_MAX_AGE_S):
        rec["reasons"] = [f"RAW_STALE_NO_SKIP: age_s={live['age_s']:.0f}"]
        return rec
    if cash is None:
        rec["reasons"] = ["CASH_UNKNOWN_NO_SKIP"] + (["MANAGE"] if manage else [])
        return rec
    if cash < min_order and not manage:
        rec.update(decision="SKIP", reasons=["NO_CASH_FOR_MIN_ORDER_AND_NOTHING_TO_MANAGE"])
    elif cash < min_order:
        rec["reasons"] = ["NO_CASH_FOR_MIN_ORDER", "NOT_SKIPPED_MANAGE"]
    else:
        rec["reasons"] = ["CASH_FOR_NEW_ORDER"] + (["MANAGE"] if manage else [])
    return rec


def build_summary(rec: dict, books: Optional[dict]) -> dict:
    live = rec.get("live") or {}
    by: dict[str, dict] = {}
    for x in live.get("lots") or []:
        b = by.setdefault(x["symbol"], {"symbol": x["symbol"], "instrumentId": x["instrumentId"], "positionIds": [],
                                        "units": 0.0, "invested": 0.0, "pnl": 0.0, "stop_losses": []})
        b["positionIds"].append(x["positionId"])
        b["units"] = round(b["units"] + (x["units"] or 0), 6)
        b["invested"] = round(b["invested"] + (x["invested"] or 0), 2)
        b["pnl"] = round(b["pnl"] + (x["pnl"] or 0), 2)
        if x.get("stop_loss"):
            b["stop_losses"].append(x["stop_loss"])
        b["current_rate"] = x.get("current_rate")
    for b in by.values():
        b["stop_loss"] = max(b["stop_losses"]) if b["stop_losses"] else None
        b["missing_stop"] = not b["stop_losses"]
        b["pnl_pct"] = round(b["pnl"] / b["invested"] * 100, 2) if b["invested"] else None
    ov = (books or {}).get("overlap") or {}
    classic = (books or {}).get("classic_symbols")
    return {
        "schema": "momentum.precheck.v1", "at": rec["at"], "decision": rec["decision"], "reasons": rec["reasons"],
        "cash": rec.get("cash"), "cash_source": rec.get("cash_source"), "min_order": rec.get("min_order"),
        "raw": {"shape": rec.get("raw_shape"), "xRequestId": rec.get("raw_xRequestId"), "age_s": rec.get("raw_age_s"),
                "timestamp": live.get("timestamp")},
        "positions": sorted(by.values(), key=lambda b: -(b["invested"] or 0)),
        "pm_positions": [{k: x[k] for k in ("symbol", "positionId", "avg_price", "stop_loss", "units", "current_rate")}
                         for x in live.get("lots") or []],
        "pending_orders": live.get("orders") or [],
        "manage": rec.get("manage") or [],
        "overlap": ov.get("overlap_any"), "overlap_detail": ov or None,
        "classic_symbols": classic,
        "buy_blocklist": (sorted(set(classic) | set(ov.get("overlap_any") or [])) if classic is not None else None),
        "buy_blocklist_note": ("Classic-held symbols (fresh books/latest/classic.json <= 60 min). None = Classic snapshot "
                               "stale/missing: screener crossbook gate still fails closed."),
        "books": {k: v for k, v in (books or {}).items() if k != "overlap"} or None,
    }


def write_audit(rec: dict, now: datetime) -> Path:
    d = audit_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"precheck-{now.astimezone(IDT).strftime('%Y-%m-%d')}.jsonl"
    slim = {k: v for k, v in rec.items() if k != "live"}
    with open(f, "a") as fh:
        fh.write(json.dumps(slim, default=str, separators=(",", ":")) + "\n")
    return f


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str) + "\n")
    os.replace(tmp, path)


CLASSIC_MAX_AGE_S = 900.0
EXIT_CLASSIC_FRESH, EXIT_CLASSIC_STALE = 0, 2


def classic_freshness(raw: Any, now: datetime, max_age_s: float = CLASSIC_MAX_AGE_S) -> dict:
    """FRESH only if the Classic read is successful and its timestamp is <= max_age_s old."""
    if not isinstance(raw, dict):
        return {"fresh": False, "code": "CLASSIC_READ_UNREADABLE", "age_s": None}
    if raw.get("error") or raw.get("statusCode") not in (200, None):
        return {"fresh": False, "code": "CLASSIC_READ_FAILED", "age_s": None,
                "error": raw.get("error") or raw.get("statusCode")}
    ts = _ts(raw)
    if ts is None:
        return {"fresh": False, "code": "CLASSIC_READ_NO_TIMESTAMP", "age_s": None}
    age = (now - ts).total_seconds()
    if age < -5 or age > max_age_s:
        return {"fresh": False, "code": "CLASSIC_READ_STALE", "age_s": round(age, 1), "max_age_s": max_age_s}
    return {"fresh": True, "code": "CLASSIC_READ_FRESH", "age_s": round(age, 1), "max_age_s": max_age_s}


def classic_fresh_main(argv: list[str], now: Optional[datetime] = None) -> int:
    ap = argparse.ArgumentParser(prog="momentum_qa.precheck classic-fresh",
                                 description="Fail closed unless the Classic read is fresh (run right before each place)")
    ap.add_argument("--classic-raw", required=True, help="saved user-OfersClaw5 get-my-positions-and-orders output")
    ap.add_argument("--max-age", type=float, default=CLASSIC_MAX_AGE_S,
                    help="max age in seconds (default and hard limit 900; >900 -> exit 2 MAX_AGE_TOO_HIGH)")
    ap.add_argument("--save", action="store_true", help="when fresh, save the cross-book snapshot (+instrumentIds)")
    a = ap.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    if not (0 < a.max_age <= CLASSIC_MAX_AGE_S):  # QA fixes4: callers cannot widen the window
        print(json.dumps({"fresh": False, "code": "MAX_AGE_TOO_HIGH" if a.max_age > CLASSIC_MAX_AGE_S else "MAX_AGE_INVALID",
                          "max_age_s": min(a.max_age, CLASSIC_MAX_AGE_S), "requested_max_age_s": a.max_age,
                          "limit_s": CLASSIC_MAX_AGE_S}))
        return EXIT_CLASSIC_STALE
    try:
        raw = load_json_file(a.classic_raw)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"fresh": False, "code": "CLASSIC_READ_UNREADABLE", "error": str(e)}))
        return EXIT_CLASSIC_STALE
    res = classic_freshness(raw, now, a.max_age)
    if res["fresh"] and a.save:
        import classic_book
        try:
            res["snapshot"] = str(classic_book.save_snapshot(raw))
        except Exception as e:  # noqa: BLE001
            res.update(fresh=False, code="CLASSIC_SNAPSHOT_SAVE_FAILED", error=str(e))
    print(json.dumps(res, default=str))
    return EXIT_CLASSIC_FRESH if res["fresh"] else EXIT_CLASSIC_STALE


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "classic-fresh":
        return classic_fresh_main(argv[1:], now)
    ap = argparse.ArgumentParser(prog="momentum_qa.precheck", description="Momentum EOD step 0 (exit 10 = silent SKIP)")
    ap.add_argument("--raw", help="saved Momentum keys get-my-positions-and-orders (or portfolio-summary) MCP output")
    ap.add_argument("--classic-raw", help="optional saved Classic user-OfersClaw5 read (summary or positions)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cash", type=float, help="cash override (USD), e.g. from a mirror 11630170 read")
    g.add_argument("--cash-json", help="user-etoro get-my-portfolio-summary file (mirror 11630170 availableCash)")
    ap.add_argument("--pm-json", help="optional position_manager output; CLOSE/MOVE_SL_BREAKEVEN/TRAIL_SL forces PROCEED")
    ap.add_argument("--min-order", type=float, default=MIN_ORDER_USD)
    ap.add_argument("--out", help="summary JSON path (default <audit>/precheck/precheck-latest.json)")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--no-ingest", action="store_true", help="skip books.snapshot ingest/overlap")
    a = ap.parse_args(argv)
    now = now or datetime.now(IDT)
    raw, err = None, None
    if a.raw:
        try:
            raw = load_json_file(a.raw)
        except Exception as e:  # noqa: BLE001
            err = f"RAW_UNREADABLE: {e}"
    pm_out = None
    if a.pm_json:
        try:
            pm_out = load_json_file(a.pm_json)
        except Exception as e:  # noqa: BLE001
            pm_out = [{"action": "CLOSE", "reason": f"PM_JSON_UNREADABLE: {e}"}]  # fail open => PROCEED
    rec = decide(raw, now, cash_override=a.cash, cash_json=a.cash_json, pm_out=pm_out, min_order=a.min_order)
    if err and rec["decision"] != "SKIP":
        rec.update(reasons=["RAW_UNREADABLE"], error=err)
    books = None
    if rec["reasons"] != ["NYSE_CLOSED_OR_HOLIDAY"] and not a.no_ingest and (a.raw or a.classic_raw):
        books = run_books(a.raw if raw is not None else None, a.classic_raw)
        rec["books_errors"] = books.get("errors") or []
    out = Path(a.out) if a.out else audit_dir() / "precheck" / "precheck-latest.json"
    if rec["reasons"] != ["NYSE_CLOSED_OR_HOLIDAY"]:
        summ = build_summary(rec, books)
        _atomic_write(out, summ)
        if not a.out:
            _atomic_write(out.parent / f"precheck-{now.astimezone(IDT).strftime('%Y%m%d-%H%M%S')}.json", summ)
        rec["summary_path"] = str(out)
    if not a.no_audit:
        rec["audit_file"] = str(write_audit(rec, now))
    print(json.dumps({k: rec.get(k) for k in ("decision", "reasons", "cash", "cash_source", "summary_path",
                                               "audit_file", "error") if rec.get(k) is not None}, default=str))
    return EXIT_SKIP if rec["decision"] == "SKIP" else EXIT_PROCEED


if __name__ == "__main__":
    sys.exit(main())

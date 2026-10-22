"""Momentum open-gap risk check — 16:45 IL weekdays, shortly after the US open (Ofer 2026-10-19).

SELL ONLY. Fixed, checked-in script; read-only: never calls eToro / MCP, never places or closes anything.
It only emits CLOSE / HOLD rows for the routine, which then runs QA Bot place-QA (PASS) + place_lock before
every prepare-close. No BUY / OPEN / SL-move action can ever be emitted (asserted before output).

Rule per open position (long lots of Momentum-HHHGDTJ, real account):
  price  = live quote: raw currentRate if present, else market data (Yahoo last price)
  sma50  = mean of the last 50 daily closes strictly BEFORE today's NY session date (i.e. up to yesterday)
  CLOSE  if price <= stopLossRate      reason GAP_BELOW_SL     (note: broker SL may already have fired)
  price <  sma50 (SL not hit)          TWO-READ RULE (Ofer 2026-10-19 13:01 IDT):
     without --confirm-from              -> PENDING_CONFIRM  reason GAP_BELOW_SMA50_UNCONFIRMED
     with --confirm-from PREV.json: same positionId in PREV had price < sma50 AND PREV run_ts is
       3..30 min before now              -> CLOSE            reason GAP_BELOW_SMA50_CONFIRMED
       PREV missing / too fresh / too old / unreadable / row absent / PREV row not below SMA50
                                         -> PENDING_CONFIRM  reason GAP_BELOW_SMA50_UNCONFIRMED (+confirm_why)
  price >= sma50 now but PREV row was below SMA50 -> HOLD reason SMA50_RECOVERED
  (SL hit always closes immediately, confirm or not; if SMA50 also broken, reasons lists both)   else HOLD
  ERROR  if price / SMA50 unavailable, history stale, or the lot is not long (never acted on)

Input (scripts cannot call MCP -> routine does ONE read with write_to_file=true and passes the file):
  --raw <file>             raw user-Momentum-HHHGDTJ get-my-positions-and-orders {account:"real"} (wrapper text ok)
  --positions-file <file>  momentum_qa.precheck summary (momentum.precheck.v1; uses pm_positions + raw.timestamp)

Exit codes:
  10  silent skip: NYSE closed/holiday today, NYSE not in regular session right now, no open positions,
      or every position HOLD
   0  one or more CLOSE rows in the output (PENDING_CONFIRM rows listed in pending_confirm[], ERROR rows in errors[])
  11  no CLOSE, >= 1 PENDING_CONFIRM: re-run in ~5 min (3..30 min window) with --confirm-from <this run's --out>
      (ERROR rows, if any, are still listed in errors[] and must be reported)
   3  bad / stale (> --max-age-s, default 900) / non-real / unparseable input, or market data missing for a
      position with no CLOSE anywhere -> report the reason, do not skip silently, do not act
   2  CLI usage error (argparse)

CLI (run from /workspace):
  ./screener-venv/bin/python -m momentum_qa.open_gap_check --raw <mkeys-positions.txt> [--out out.json] [--no-audit] \
      [--confirm-from <previous run's --out json>]
  ./screener-venv/bin/python -m momentum_qa.open_gap_check --positions-file momentum_audit/precheck/precheck-latest.json
  Optional: --max-age-s 900, --allow-outside-rth (testing only: evaluate outside 09:30-16:00 NY).
stdout: the full JSON result (same as --out). Audit: /workspace/momentum_audit/YYYY-MM-DD.jsonl
(source=open_gap_check, run_id=opengap-...), unless --no-audit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import nyse_session  # noqa: E402
from momentum_qa import precheck as PC  # noqa: E402  (raw loader / keys parser / timestamp parser reused)
from momentum_qa.audit import AuditLogger, new_run_id  # noqa: E402
from momentum_qa.instrument_map import base_symbol  # noqa: E402

IDT = ZoneInfo("Asia/Jerusalem")
NY = ZoneInfo("America/New_York")
EXIT_CLOSE, EXIT_USAGE, EXIT_BAD_INPUT, EXIT_SKIP, EXIT_PENDING = 0, 2, 3, 10, 11
CONFIRM_MIN_S, CONFIRM_MAX_S = 180.0, 1800.0
MAX_AGE_S = 900.0
SMA_N = 50
ALLOWED_ACTIONS = ("CLOSE", "HOLD", "PENDING_CONFIRM", "ERROR")
SOURCE = "open_gap_check"
PORTFOLIO = "Momentum-HHHGDTJ"


class BadInput(Exception):
    pass


# ---------------------------------------------------------------- market data (mockable)
def _to_yahoo(symbol: str) -> str:
    from position_manager import to_yahoo  # reuse the PM symbol map (crypto + BRK.B -> BRK-B)
    return to_yahoo(symbol)


def fetch_daily_closes(symbol: str) -> list[tuple[date, float]]:
    """Yahoo daily closes (auto_adjust=True, same convention as position_manager.price_context)."""
    import yfinance as yf
    start = (datetime.now(tz=None) - timedelta(days=140)).strftime("%Y-%m-%d")
    df = yf.download(_to_yahoo(symbol), start=start, progress=False, auto_adjust=True, threads=False)
    if df is None or df.empty:
        return []
    c = df["Close"]
    if hasattr(c, "columns"):
        c = c.squeeze(axis=1)
    c = c.dropna()
    return [(ts.date(), float(v)) for ts, v in c.items()]


def fetch_live_price(symbol: str) -> Optional[float]:
    import yfinance as yf
    try:
        v = yf.Ticker(_to_yahoo(symbol)).fast_info["last_price"]
        return float(v) if v else None
    except Exception:  # noqa: BLE001
        return None


class MarketData:
    def __init__(self, closes: Callable = fetch_daily_closes, live: Callable = fetch_live_price):
        self.closes, self.live = closes, live


# ---------------------------------------------------------------- session helpers
def ny_date(now: datetime) -> date:
    return now.astimezone(NY).date()


def prev_session(d: date) -> date:
    import pandas as pd
    cal = nyse_session._XNYS
    if cal is not None:
        return cal.previous_session(pd.Timestamp(d)).date()
    x = d - timedelta(days=1)
    while x.weekday() >= 5:
        x -= timedelta(days=1)
    return x


def in_rth(now: datetime) -> bool:
    """True while NYSE regular session is open now (exchange_calendars open/close; fallback 09:30-16:00 NY)."""
    import pandas as pd
    cal = nyse_session._XNYS
    d = pd.Timestamp(ny_date(now))
    if cal is not None:
        try:
            return cal.session_open(d) <= pd.Timestamp(now.astimezone(timezone.utc)) < cal.session_close(d)
        except Exception:  # noqa: BLE001
            return False
    t = now.astimezone(NY)
    m = t.hour * 60 + t.minute
    return 9 * 60 + 30 <= m < 16 * 60


# ---------------------------------------------------------------- input
def load_lots(raw_path: Optional[str], summary_path: Optional[str], now: datetime, max_age_s: float) -> dict:
    """-> {lots:[{symbol, positionId, current_rate, stop_loss, direction}], timestamp, age_s, source, xRequestId}."""
    path = raw_path or summary_path
    try:
        d = PC.load_json_file(path)
    except Exception as e:  # noqa: BLE001
        raise BadInput(f"INPUT_UNREADABLE: {e}")
    if raw_path:
        live = PC.parse_keys_raw(d, now)
        if not live["ok"]:
            raise BadInput(live["error"])
        if live["shape"] != "positions":
            raise BadInput("RAW_WRONG_SHAPE: need get-my-positions-and-orders (direct.positions), got summary")
        lots, ts, age, xr, src = live["lots"], live["timestamp"], live["age_s"], live["xRequestId"], "raw"
    else:
        if not isinstance(d, dict) or d.get("schema") != "momentum.precheck.v1" or not isinstance(d.get("pm_positions"), list):
            raise BadInput("SUMMARY_BAD_SHAPE: need momentum.precheck.v1 with pm_positions")
        raw_meta = d.get("raw") or {}
        t = PC._ts({"timestamp": raw_meta.get("timestamp")})
        if t is None:
            raise BadInput("SUMMARY_NO_RAW_TIMESTAMP")
        age = round((now - t).total_seconds(), 1)
        lots = [{**x, "direction": x.get("direction", "long")} for x in d["pm_positions"]]
        ts, xr, src = raw_meta.get("timestamp"), raw_meta.get("xRequestId"), "precheck_summary"
    if not (-60 <= age <= max_age_s):
        raise BadInput(f"INPUT_STALE: age_s={age:.0f} > {max_age_s:.0f}")
    for x in lots:
        if not x.get("symbol") or x.get("positionId") is None:
            raise BadInput(f"BAD_POSITION_ROW: {str(x)[:120]}")
    return {"lots": lots, "timestamp": ts, "age_s": age, "source": src, "xRequestId": xr, "path": str(path)}


# ---------------------------------------------------------------- rule
def sma50_before(closes: list[tuple[date, float]], today: date) -> tuple[Optional[float], dict]:
    prior = sorted((d, v) for d, v in closes if d < today and v == v)
    meta = {"n_closes": len(prior), "last_close_date": prior[-1][0].isoformat() if prior else None,
            "first_sma_date": prior[-SMA_N][0].isoformat() if len(prior) >= SMA_N else None}
    if len(prior) < SMA_N:
        return None, meta
    return sum(v for _, v in prior[-SMA_N:]) / SMA_N, meta


def evaluate_lot(lot: dict, today: date, md: MarketData, closes_cache: dict) -> dict:
    sym = base_symbol(lot["symbol"], lot.get("instrumentId"))  # A.US / X.RTH -> base ticker for Yahoo + audit
    row: dict[str, Any] = {"symbol": sym, "positionId": lot["positionId"], "side": "SELL"}
    sl = PC._num(lot.get("stop_loss"))
    price, psrc = PC._num(lot.get("current_rate")), "raw.currentRate"
    if price is None or price <= 0:
        price, psrc = PC._num(md.live(sym)), "market_data.last_price"
    if sym not in closes_cache:
        try:
            closes_cache[sym] = md.closes(sym)
        except Exception as e:  # noqa: BLE001
            closes_cache[sym] = e
    cl = closes_cache[sym]
    if isinstance(cl, Exception):
        sma, meta = None, {"n_closes": 0, "last_close_date": None, "fetch_error": str(cl)}
    else:
        sma, meta = sma50_before(cl or [], today)
    exp_prev = prev_session(today).isoformat()
    row.update(price=None if price is None else round(price, 4), sl=sl,
               sma50=None if sma is None else round(sma, 4))
    qa = {"price": price, "price_source": psrc if price is not None else None, "sl": sl, "sma50": sma,
          "sma_window": SMA_N, "sma_closes_before": today.isoformat(), "expected_last_close": exp_prev, **meta,
          "price_le_sl": (price is not None and sl is not None and price <= sl),
          "price_lt_sma50": (price is not None and sma is not None and price < sma),
          "sl_missing": sl is None, "rule": "CLOSE iff price <= sl OR price < sma50; else HOLD; SELL only"}
    reasons: list[str] = []
    if str(lot.get("direction", "long")).lower() != "long":
        row.update(action="ERROR", reason="NOT_LONG")
    elif price is None:
        row.update(action="ERROR", reason="NO_PRICE")
    elif qa["price_le_sl"]:
        reasons.append("GAP_BELOW_SL")
    if row.get("action") is None and price is not None and sma is not None and price < sma:
        reasons.append("GAP_BELOW_SMA50")
    if row.get("action") is None:
        if reasons:
            row.update(action="CLOSE", reason=reasons[0], reasons=reasons)
        elif sma is None:
            row.update(action="ERROR", reason="NO_SMA50")
        elif meta["last_close_date"] != exp_prev:
            row.update(action="ERROR", reason="SMA_HISTORY_STALE")
        else:
            row.update(action="HOLD", reason="ABOVE_SL_AND_SMA50")
    if row["action"] == "CLOSE" and meta.get("last_close_date") not in (None, exp_prev):
        qa["sma_history_stale_warning"] = True  # SL breach / still-valid SMA close stands; flag for QA Bot
    qa["expected_action"] = row["action"]
    row["note"] = _note(row, sl, sma, price)
    row["qa"] = qa
    return row


def _note(row: dict, sl, sma, price) -> str:
    a, s = row["action"], row["symbol"]
    if a == "CLOSE":
        bits = []
        if "GAP_BELOW_SL" in row.get("reasons", []):
            bits.append(f"price {price:.4f} <= SL {sl:.4f} (broker SL may already have fired — re-read positions "
                        "before prepare-close)")
        if "GAP_BELOW_SMA50" in row.get("reasons", []):
            bits.append(f"price {price:.4f} < SMA50 {sma:.4f}")
        return f"Close {s}: " + "; ".join(bits)
    if a == "HOLD":
        return f"Hold {s}: price {price:.4f} > SL {sl} and >= SMA50 {sma:.4f}"
    return f"{s}: {row['reason']} — not evaluated, do not act"


# ---------------------------------------------------------------- two-read SMA50 confirmation
def load_confirm(path: Optional[str], now: datetime) -> dict:
    """Previous open_gap_check --out json -> {ok, why, run_ts, gap_min, rows_by_pid}."""
    info: dict[str, Any] = {"path": path, "ok": False, "why": None, "run_ts": None, "gap_min": None, "rows": {}}
    if not path:
        info["why"] = "NO_CONFIRM_FROM"
        return info
    try:
        prev = PC.load_json_file(path)
    except Exception as e:  # noqa: BLE001
        info["why"] = f"PREV_UNREADABLE: {e}"
        return info
    if not isinstance(prev, dict) or prev.get("schema") != "momentum.open_gap_check.v1":
        info["why"] = "PREV_BAD_SHAPE"
        return info
    ts = prev.get("run_ts") or prev.get("at")
    t = PC._ts({"timestamp": ts}) if ts else None
    if t is None:
        info["why"] = "PREV_NO_RUN_TS"
        return info
    gap = (now - t).total_seconds()
    info.update(run_ts=t.astimezone(IDT).isoformat(timespec="seconds"), gap_min=round(gap / 60, 2),
                rows={str(r.get("positionId")): r for r in prev.get("rows") or [] if isinstance(r, dict)})
    if gap < CONFIRM_MIN_S:
        info["why"] = f"PREV_TOO_FRESH: {gap / 60:.2f} min < {CONFIRM_MIN_S / 60:.0f}"
    elif gap > CONFIRM_MAX_S:
        info["why"] = f"PREV_TOO_OLD: {gap / 60:.2f} min > {CONFIRM_MAX_S / 60:.0f}"
    else:
        info["ok"] = True
    return info


def _prev_below(r: Optional[dict]) -> bool:
    if not r:
        return False
    p, s = PC._num(r.get("price")), PC._num(r.get("sma50"))
    return p is not None and s is not None and p < s


def apply_confirm(row: dict, conf: dict, now: datetime) -> dict:
    """Two-read rule for SMA50-only breaks. SL breach (GAP_BELOW_SL) is never touched."""
    if row["action"] not in ("CLOSE", "HOLD") or "GAP_BELOW_SL" in row.get("reasons", []):
        return row
    prev = conf["rows"].get(str(row["positionId"]))
    q = row["qa"]
    q["confirm"] = {"confirm_from": conf["path"], "price_now": row["price"], "sma50_now": row["sma50"],
                    "ts_now": now.astimezone(IDT).isoformat(timespec="seconds"),
                    "price_prev": (prev or {}).get("price"), "sma50_prev": (prev or {}).get("sma50"),
                    "ts_prev": conf["run_ts"], "gap_min": conf["gap_min"],
                    "window_min": [CONFIRM_MIN_S / 60, CONFIRM_MAX_S / 60], "prev_below_sma50": _prev_below(prev)}
    if row["action"] == "HOLD":
        if _prev_below(prev):
            row.update(reason="SMA50_RECOVERED")
            row["note"] = (f"Hold {row['symbol']}: back above SMA50 ({row['price']:.4f} >= {row['sma50']:.4f}); "
                           f"previous read {prev.get('price')} < {prev.get('sma50')} ({conf['gap_min']} min earlier)")
        q["expected_action"] = row["action"]
        return row
    why = conf["why"] if not conf["ok"] else (None if prev else "PREV_ROW_MISSING")
    if why is None and not _prev_below(prev):
        why = "PREV_NOT_BELOW_SMA50"
    q["confirm"]["confirmed"] = why is None
    q["confirm"]["why"] = why
    if why is None:
        row.update(action="CLOSE", reason="GAP_BELOW_SMA50_CONFIRMED", reasons=["GAP_BELOW_SMA50_CONFIRMED"])
        row["note"] = (f"Close {row['symbol']}: price {row['price']:.4f} < SMA50 {row['sma50']:.4f}, confirmed by read "
                       f"{conf['gap_min']} min earlier ({prev.get('price')} < {prev.get('sma50')})")
    else:
        row.update(action="PENDING_CONFIRM", reason="GAP_BELOW_SMA50_UNCONFIRMED",
                   reasons=["GAP_BELOW_SMA50_UNCONFIRMED"])
        row["note"] = (f"Pending {row['symbol']}: price {row['price']:.4f} < SMA50 {row['sma50']:.4f}, needs a second read "
                       f"3-30 min later ({why}) — do not close yet")
    q["expected_action"] = row["action"]
    return row


# ---------------------------------------------------------------- audit
class GapAudit(AuditLogger):
    def __init__(self, run_id: str, now: datetime):  # noqa: D401  (path chosen at call time, env-overridable)
        self.run_id, self.script, self.portfolio = run_id, "momentum_qa/open_gap_check.py", PORTFOLIO
        d = Path(os.environ.get("MOMENTUM_AUDIT_DIR", "/workspace/momentum_audit"))
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{now.astimezone(IDT).strftime('%Y-%m-%d')}.jsonl"
        self._write({"event": "RUN_START", "rationale": f"Starting open_gap_check for {PORTFOLIO}"})

    def _write(self, payload: dict[str, Any]) -> None:
        super()._write({"source": SOURCE, **payload})


# ---------------------------------------------------------------- main
def run(raw: Optional[str], positions_file: Optional[str], now: datetime, md: MarketData,
        max_age_s: float = MAX_AGE_S, allow_outside_rth: bool = False,
        confirm_from: Optional[str] = None) -> tuple[int, dict]:
    today = ny_date(now)
    res: dict[str, Any] = {"schema": "momentum.open_gap_check.v1", "source": SOURCE, "portfolio": PORTFOLIO,
                           "at": now.astimezone(IDT).isoformat(timespec="seconds"),
                           "run_ts": now.astimezone(IDT).isoformat(timespec="seconds"), "ny_date": today.isoformat(),
                           "status": None, "reason": None, "rows": [], "closes": [], "pending_confirm": []}
    if not nyse_session.nyse_today_is_open(now):
        res.update(status="SKIP", reason="NYSE_CLOSED_OR_HOLIDAY")
        return EXIT_SKIP, res
    if not allow_outside_rth and not in_rth(now):
        res.update(status="SKIP", reason="NYSE_NOT_IN_REGULAR_SESSION")
        return EXIT_SKIP, res
    try:
        inp = load_lots(raw, positions_file, now, max_age_s)
    except BadInput as e:
        res.update(status="BAD_INPUT", reason=str(e))
        return EXIT_BAD_INPUT, res
    res["input"] = {k: inp[k] for k in ("source", "path", "timestamp", "age_s", "xRequestId")}
    if not inp["lots"]:
        res.update(status="SKIP", reason="NO_OPEN_POSITIONS")
        return EXIT_SKIP, res
    cache: dict = {}
    conf = load_confirm(confirm_from, now)
    rows = [apply_confirm(evaluate_lot(x, today, md, cache), conf, now) for x in inp["lots"]]
    res["confirm"] = {k: conf[k] for k in ("path", "ok", "why", "run_ts", "gap_min")}
    bad = [r for r in rows if r["action"] not in ALLOWED_ACTIONS]
    if bad:  # hard guarantee: sell-only
        raise AssertionError(f"forbidden action emitted: {bad}")
    res["rows"] = rows
    res["closes"] = [{k: r[k] for k in ("symbol", "positionId", "price", "sl", "sma50", "reason")}
                     for r in rows if r["action"] == "CLOSE"]
    res["pending_confirm"] = [{k: r[k] for k in ("symbol", "positionId", "price", "sl", "sma50", "reason")}
                              | {"why": r["qa"]["confirm"]["why"]} for r in rows if r["action"] == "PENDING_CONFIRM"]
    errs = [r for r in rows if r["action"] == "ERROR"]
    res["errors"] = [{"symbol": r["symbol"], "positionId": r["positionId"], "reason": r["reason"]} for r in errs]
    res["qa"] = {"sell_only": True, "allowed_actions": list(ALLOWED_ACTIONS), "n_positions": len(rows),
                 "n_close": len(res["closes"]),
                 "n_pending_confirm": len(res["pending_confirm"]), "n_hold": sum(r["action"] == "HOLD" for r in rows),
                 "n_error": len(errs), "max_age_s": max_age_s,
                 "next_step": ("per CLOSE: QA Bot place-QA PASS + place_lock acquire, re-read positions, prepare-close; "
                               "PENDING_CONFIRM: fresh read + re-run in 3-30 min with --confirm-from <this --out>")}
    if res["closes"]:
        res.update(status="CLOSE", reason=f"{len(res['closes'])} CLOSE" +
                   (f", {len(res['pending_confirm'])} PENDING_CONFIRM" if res["pending_confirm"] else ""))
        return EXIT_CLOSE, res
    if res["pending_confirm"]:
        res.update(status="PENDING_CONFIRM", reason=f"{len(res['pending_confirm'])} PENDING_CONFIRM" +
                   (f"; errors: " + ", ".join(f"{e['symbol']}:{e['reason']}" for e in res["errors"]) if errs else ""))
        return EXIT_PENDING, res
    if errs:
        res.update(status="BAD_INPUT", reason="MARKET_DATA_OR_ROW_ERROR: " +
                   ", ".join(f"{e['symbol']}:{e['reason']}" for e in res["errors"]))
        return EXIT_BAD_INPUT, res
    res.update(status="SKIP", reason="ALL_HOLD")
    return EXIT_SKIP, res


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None, md: Optional[MarketData] = None) -> int:
    ap = argparse.ArgumentParser(prog="momentum_qa.open_gap_check",
                                 description="Momentum 16:45 IL open-gap check (SELL only). Exit 10 = silent skip.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--raw", help="saved keys get-my-positions-and-orders MCP output (wrapper text ok)")
    g.add_argument("--positions-file", help="momentum_qa.precheck summary JSON (momentum.precheck.v1)")
    ap.add_argument("--out", help="also write the JSON result here")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--max-age-s", type=float, default=MAX_AGE_S)
    ap.add_argument("--allow-outside-rth", action="store_true", help="testing only")
    ap.add_argument("--confirm-from", help="previous run's --out json (3-30 min old) to confirm SMA50-only closes")
    a = ap.parse_args(argv)
    now = now or datetime.now(IDT)
    md = md or MarketData()
    run_id = new_run_id("opengap")
    log = None if a.no_audit else GapAudit(run_id, now)
    if not (a.raw or a.positions_file) and nyse_session.nyse_today_is_open(now):
        code, res = EXIT_BAD_INPUT, {"schema": "momentum.open_gap_check.v1", "source": SOURCE, "status": "BAD_INPUT",
                                     "reason": "INPUT_MISSING: pass --raw or --positions-file", "rows": [], "closes": []}
    else:
        try:
            code, res = run(a.raw, a.positions_file, now, md, a.max_age_s, a.allow_outside_rth, a.confirm_from)
        except Exception as e:  # noqa: BLE001  (crash = bad state: report, never act)
            code, res = EXIT_BAD_INPUT, {"schema": "momentum.open_gap_check.v1", "source": SOURCE,
                                         "status": "BAD_INPUT", "reason": f"CRASH: {e}", "rows": [], "closes": []}
    res["run_id"], res["exit_code"] = run_id, code
    if log:
        for r in res.get("rows") or []:
            log.action(r["action"], r["note"], symbol=r["symbol"],
                       details={k: r[k] for k in r if k != "note"},
                       qa_verdict=None, qa_reasons=[r["reason"]])
        if code == EXIT_BAD_INPUT:
            log.error("open_gap_check", res["reason"], rationale="bad/stale input — no action, reported")
        log.end(f"open_gap_check {res['status']}: {res['reason']}",
                details={"exit_code": code, "closes": res.get("closes"), "pending_confirm": res.get("pending_confirm"),
                         "confirm": res.get("confirm"), "errors": res.get("errors"),
                         "input": res.get("input")})
        res["audit_file"] = str(log.path)
    txt = json.dumps(res, indent=1, default=str, ensure_ascii=False)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt + "\n")
    print(txt)
    return code


if __name__ == "__main__":
    sys.exit(main())

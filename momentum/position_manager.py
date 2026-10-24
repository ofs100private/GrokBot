#!/usr/bin/env python3
"""Momentum EOD position manager — Momentum-HHHGDTJ with QA + audit.

Rules (run at NYSE close-20m = 15:40 New York on NYSE sessions; 22:40 IL normally, 21:40 IL on 2026-10-26..30):
- If price last below SMA50 → CLOSE (rationale required)
- If unrealized PnL% <= -4.0 vs avg open → CLOSE LOSS_PCT_GE_4 (hard stop)
- If unrealized >= 2R vs initial risk → MOVE SL to breakeven (entry)
- If unrealized >= 1R and stop still below entry → TRAIL_SL to
  max(prior_stop, min(entry, 10-session low)), never above last-ε, never lower stop
Priority per name: CLOSE (SMA50 or -4%) > MOVE_SL_BREAKEVEN (>=2R) > TRAIL_SL (>=1R) > HOLD
Does NOT place orders itself; prints JSON for the bot. QA annotates PASS/FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

import yfinance as yf

from nyse_session import in_intraday_ban, nyse_today_is_open
from momentum_qa.audit import AuditLogger, new_run_id
from momentum_qa.validate import validate_position_action


# eToro crypto/common symbols → Yahoo Finance tickers
ETORO_TO_YAHOO = {
    "ETH": "ETH-USD",
    "BTC": "BTC-USD",
    "XRP": "XRP-USD",
    "SOL": "SOL-USD",
    "ADA": "ADA-USD",
    "DOGE": "DOGE-USD",
}


def to_yahoo(symbol: str) -> str:
    if symbol in ETORO_TO_YAHOO:
        return ETORO_TO_YAHOO[symbol]
    from momentum_qa.instrument_map import base_symbol  # eToro 'A.US' / 'X.RTH' -> base ticker
    return base_symbol(symbol).replace(".", "-")


def price_context(symbol: str) -> dict | None:
    """SMA50, last close, yesterday low, 10-session low (Yahoo daily)."""
    start = (datetime.now(tz=None) - timedelta(days=120)).strftime("%Y-%m-%d")
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True, threads=False)
    if df is None or df.empty:
        return None
    close = df["Close"]
    low = df["Low"]
    if hasattr(close, "columns"):
        close = close.squeeze(axis=1)
    if hasattr(low, "columns"):
        low = low.squeeze(axis=1)
    c = close.dropna()
    lo = low.dropna()
    if len(c) < 50 or len(lo) < 10:
        return None
    last = float(c.iloc[-1])
    sma50 = float(c.rolling(50).mean().iloc[-1])
    # 10-session low including today; yesterday_low = prior bar
    low_10 = float(lo.iloc[-10:].min())
    yesterday_low = float(lo.iloc[-2]) if len(lo) >= 2 else low_10
    return {
        "sma50": sma50,
        "last": last,
        "low_10": low_10,
        "yesterday_low": yesterday_low,
    }


def sma50_and_last(symbol: str) -> tuple[float, float] | None:
    """Back-compat helper."""
    ctx = price_context(symbol)
    if ctx is None:
        return None
    return ctx["sma50"], ctx["last"]


def normalize_positions(raw) -> list:
    """Coerce PM input to a list of {symbol, avg_price, stop_loss, ...} dicts.

    Fix for posmgr-20261012-225006-410ace7d ("string indices must be integers, not 'str'"):
    the old loop did p["symbol"] on whatever it iterated — a dict wrapper ({"positions": [...]})
    or the raw MCP shape ({"direct": {"positions": [...]}}) iterates as str keys and crashed the
    whole run. Non-dict rows are passed through (manage() logs them as row-level ERROR)."""
    if isinstance(raw, (bytes, str)):
        raw = json.loads(raw) if str(raw).strip() else []
    if isinstance(raw, dict):
        if isinstance(raw.get("direct"), dict):
            raw = raw["direct"].get("positions") or []
        elif "positions" in raw:
            raw = raw.get("positions") or []
        elif "symbol" in raw or "market" in raw:
            raw = [raw]
        else:
            raw = []
    out = []
    for p in raw or []:
        if isinstance(p, str) and p.strip():
            out.append({"symbol": p.strip().upper()})
        elif isinstance(p, dict):
            q = dict(p)
            if not q.get("symbol") and isinstance(q.get("market"), dict):
                q["symbol"] = q["market"].get("symbol")
            if q.get("avg_price") is None and q.get("openRate") is not None:
                q["avg_price"] = q["openRate"]
            if "stop_loss" not in q and "stopLossRate" in q:
                q["stop_loss"] = q["stopLossRate"]
            out.append(q)
        else:
            out.append(p)
    return out


def manage(positions, log: AuditLogger | None = None) -> list[dict]:
    positions = normalize_positions(positions)
    if not nyse_today_is_open():
        row = {"action": "SKIP", "reason": "NYSE_HOLIDAY_OR_CLOSED", "rationale": "NYSE closed/holiday — no EOD risk pass"}
        if log:
            log.action("SKIP", row["rationale"], qa_verdict="PASS", qa_reasons=["holiday skip"])
        return [row]
    if in_intraday_ban():
        row = {
            "action": "SKIP",
            "reason": "INTRADAY_BAN",
            "rationale": "Intraday ban window — risk pass only runs near NYSE close",
        }
        if log:
            log.deviation("INTRADAY_BAN", row["rationale"], severity="HIGH")
            log.action("SKIP", row["rationale"], deviation=True, deviation_code="INTRADAY_BAN", qa_verdict="PASS")
        return [row]

    out: list[dict] = []
    for p in positions:
        if not isinstance(p, dict) or not p.get("symbol"):
            row = {"symbol": None, "action": "ERROR", "reason": "BAD_POSITION_ROW",
                   "rationale": f"Unparseable position row skipped: {str(p)[:80]}"}
            if log:
                log.error("bad_row", ValueError(row["rationale"]), rationale=row["rationale"])
            out.append(row)
            continue
        sym = p["symbol"]
        yahoo = to_yahoo(sym)
        try:
            ctx = price_context(yahoo)
        except Exception as e:
            row = {"symbol": sym, "action": "ERROR", "details": str(e), "rationale": f"Failed SMA50 fetch: {e}"}
            if log:
                log.error("sma50", e, rationale=row["rationale"], details={"symbol": sym})
            out.append(row)
            continue
        if ctx is None:
            row = {"symbol": sym, "action": "SKIP", "reason": "NO_SMA50", "rationale": "Insufficient history for SMA50"}
            out.append(row)
            continue

        s50 = ctx["sma50"]
        last = ctx["last"]
        low_10 = ctx["low_10"]
        avg = float(p.get("avg_price") or 0)
        sl = p.get("stop_loss")
        if sl and avg:
            r_per_share = abs(avg - float(sl))
        else:
            r_per_share = avg * 0.06 if avg else 0
        pnl_per_share = (last - avg) if avg else 0
        r_multiple = (pnl_per_share / r_per_share) if r_per_share > 0 else 0
        pnl_pct = (pnl_per_share / avg * 100.0) if avg else 0.0
        eps = max(last * 0.0001, 0.01)

        if last < s50:
            row = {
                "symbol": sym,
                "action": "CLOSE",
                "reason": "BELOW_SMA50",
                "rationale": (
                    f"Close {sym}: last {last:.4f} < SMA50 {s50:.4f} — "
                    f"EOD playbook exits broken trend (R={r_multiple:.2f}, pnl={pnl_pct:.2f}%)"
                ),
                "last": round(last, 4),
                "sma50": round(s50, 4),
                "avg_price": round(avg, 4) if avg else None,
                "pnl_pct": round(pnl_pct, 2),
                "r_multiple": round(r_multiple, 2),
            }
        elif avg and pnl_pct <= -4.0:
            row = {
                "symbol": sym,
                "action": "CLOSE",
                "reason": "LOSS_PCT_GE_4",
                "rationale": (
                    f"Close {sym}: unrealized {pnl_pct:.2f}% <= -4.0% "
                    f"(last {last:.4f}, entry {avg:.4f}) — hard loss cut"
                ),
                "last": round(last, 4),
                "sma50": round(s50, 4),
                "avg_price": round(avg, 4),
                "pnl_pct": round(pnl_pct, 2),
                "r_multiple": round(r_multiple, 2),
            }
        elif r_multiple >= 2.0 and avg:
            # MOVE_SL_BREAKEVEN if trail not already >= entry
            if sl is None or float(sl) < avg:
                row = {
                    "symbol": sym,
                    "action": "MOVE_SL_BREAKEVEN",
                    "reason": "HIT_2R",
                    "rationale": (
                        f"Move SL to breakeven on {sym}: R={r_multiple:.2f} ≥ 2 "
                        f"(last {last:.4f}, entry {avg:.4f})"
                    ),
                    "last": round(last, 4),
                    "sma50": round(s50, 4),
                    "new_stop_loss": round(avg, 4),
                    "prior_stop_loss": float(sl) if sl is not None else None,
                    "r_multiple": round(r_multiple, 2),
                }
            else:
                row = {
                    "symbol": sym,
                    "action": "HOLD",
                    "reason": "SL_ALREADY_GE_BE",
                    "rationale": f"Hold {sym}: already ≥2R and SL at/above entry",
                    "last": round(last, 4),
                    "sma50": round(s50, 4),
                    "r_multiple": round(r_multiple, 2),
                }
        elif r_multiple >= 1.0 and avg and (sl is None or float(sl) < avg):
            # TRAIL_SL: floor = 10-session low; never above entry; never lower stop; never above last-ε
            trail_floor = float(low_10)
            prior = float(sl) if sl is not None else 0.0
            proposed = max(prior, min(avg, trail_floor))
            proposed = min(proposed, last - eps)
            # Never lower an existing stop
            if sl is not None and proposed < float(sl):
                proposed = float(sl)
            if sl is None or proposed > float(sl) + 1e-9:
                row = {
                    "symbol": sym,
                    "action": "TRAIL_SL",
                    "reason": "HIT_1R",
                    "rationale": (
                        f"Trail SL on {sym}: R={r_multiple:.2f} ≥ 1R — "
                        f"new_stop={proposed:.4f} (10d_low={low_10:.4f}, entry={avg:.4f}, "
                        f"prior={sl})"
                    ),
                    "last": round(last, 4),
                    "sma50": round(s50, 4),
                    "new_stop_loss": round(proposed, 4),
                    "prior_stop_loss": float(sl) if sl is not None else None,
                    "trail_floor": round(trail_floor, 4),
                    "r_multiple": round(r_multiple, 2),
                }
            else:
                row = {
                    "symbol": sym,
                    "action": "HOLD",
                    "reason": "TRAIL_NO_RAISE",
                    "rationale": (
                        f"Hold {sym}: ≥1R but trail would not raise stop "
                        f"(prior={sl}, floor={low_10:.4f})"
                    ),
                    "last": round(last, 4),
                    "sma50": round(s50, 4),
                    "r_multiple": round(r_multiple, 2),
                }
        else:
            row = {
                "symbol": sym,
                "action": "HOLD",
                "reason": "ABOVE_SMA50_UNDER_1R" if r_multiple < 1.0 else "ABOVE_SMA50_UNDER_2R",
                "rationale": (
                    f"Hold {sym}: last {last:.4f} > SMA50 {s50:.4f}, "
                    f"R={r_multiple:.2f} — no risk action"
                ),
                "last": round(last, 4),
                "sma50": round(s50, 4),
                "r_multiple": round(r_multiple, 2),
            }

        verdict = validate_position_action(row)
        row["qa"] = verdict.to_dict()
        if log:
            if not verdict.ok:
                for d in verdict.deviations or [{"code": "QA_FAIL"}]:
                    log.deviation(
                        d.get("code", "QA_FAIL"),
                        rationale="; ".join(verdict.reasons),
                        symbol=sym,
                        details=row,
                    )
            log.action(
                row["action"],
                rationale=row["rationale"],
                symbol=sym,
                details={k: row[k] for k in row if k not in ("qa",)},
                deviation=not verdict.ok,
                deviation_code=(verdict.deviations or [{}])[0].get("code") if not verdict.ok else None,
                qa_verdict=verdict.verdict,
                qa_reasons=verdict.reasons,
            )
        # Only executable risk actions that PASS QA
        if row["action"] in ("CLOSE", "MOVE_SL_BREAKEVEN", "TRAIL_SL") and not verdict.ok:
            row["blocked"] = True
        out.append(row)
    return out


def load_positions_file(path: str) -> list:
    """File input for the routine (2026-10-18 code-first; no raw JSON pasted on the command line).

    Accepts: raw MCP keys get-my-positions-and-orders output (wrapper text tolerated), a keys
    get-my-portfolio-summary (holdings[].positions flattened), a momentum_qa.precheck summary
    (uses its "pm_positions"), or a plain list. Parsing only; trading rules live in manage()."""
    from pathlib import Path
    txt = Path(path).read_text()
    try:
        raw = json.loads(txt)
    except json.JSONDecodeError:
        s = txt.strip()
        i = min([k for k in (s.find("{"), s.find("[")) if k >= 0], default=-1)
        if i < 0:
            raise
        raw = json.loads(s[i: s.rindex("}" if s[i] == "{" else "]") + 1])
    if isinstance(raw, dict) and isinstance(raw.get("pm_positions"), list):
        return raw["pm_positions"]
    if isinstance(raw, dict) and isinstance(raw.get("holdings"), list) and "direct" not in raw:
        rows = []
        for h in raw["holdings"]:
            m = h.get("market") or {}
            for p in h.get("positions") or []:
                rows.append({**p, "symbol": m.get("symbol")})
        return rows
    return raw


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--positions-json", default=None, help="inline JSON (legacy) or @FILE")
    src.add_argument("--positions-file", default=None,
                     help="raw keys MCP positions/summary file, or momentum_qa.precheck summary JSON")
    ap.add_argument("--out", default=None, help="also write the JSON result to this file")
    args = ap.parse_args()
    if args.positions_file:
        positions = load_positions_file(args.positions_file)
    elif args.positions_json and args.positions_json.startswith("@"):
        positions = load_positions_file(args.positions_json[1:])
    else:
        positions = json.loads(args.positions_json or "[]")
    run_id = new_run_id("posmgr")
    log = AuditLogger(run_id, "position_manager.py")
    try:
        result = manage(positions, log=log)
        log.end(f"position_manager done: {len(result)} rows", details={"n": len(result)})
        txt = json.dumps(result, indent=2, ensure_ascii=False)
        if args.out:
            from pathlib import Path
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(txt + "\n")
        print(txt)
    except Exception as e:
        log.error("main", e, rationale="position_manager crashed")
        print(json.dumps([{"action": "ERROR", "reason": str(e)}], indent=2))
        sys.exit(1)

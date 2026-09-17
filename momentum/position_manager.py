#!/usr/bin/env python3
"""Momentum EOD position manager — Momentum-HHHGDTJ with QA + audit.

Rules (run ~22:40 Israel / 15:40 NY on NYSE sessions):
- If price last below SMA50 → CLOSE (rationale required)
- If unrealized >= 2R vs initial risk → MOVE SL to breakeven (entry)
- If unrealized >= 1R and stop still below entry → TRAIL_SL to
  max(prior_stop, min(entry, 10-session low)), never above last-ε, never lower stop
Priority per name: CLOSE > MOVE_SL_BREAKEVEN (>=2R) > TRAIL_SL (>=1R) > HOLD
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
    return symbol.replace(".", "-")


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


def manage(positions: list[dict], log: AuditLogger | None = None) -> list[dict]:
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
        eps = max(last * 0.0001, 0.01)

        if last < s50:
            row = {
                "symbol": sym,
                "action": "CLOSE",
                "reason": "BELOW_SMA50",
                "rationale": (
                    f"Close {sym}: last {last:.4f} < SMA50 {s50:.4f} — "
                    f"EOD playbook exits broken trend (R={r_multiple:.2f})"
                ),
                "last": round(last, 4),
                "sma50": round(s50, 4),
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions-json", default="[]")
    args = ap.parse_args()
    positions = json.loads(args.positions_json)
    run_id = new_run_id("posmgr")
    log = AuditLogger(run_id, "position_manager.py")
    try:
        result = manage(positions, log=log)
        log.end(f"position_manager done: {len(result)} rows", details={"n": len(result)})
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        log.error("main", e, rationale="position_manager crashed")
        print(json.dumps([{"action": "ERROR", "reason": str(e)}], indent=2))
        sys.exit(1)

"""Daily Trader breakout scanner (analysis only — never places).

BREAKOUT score: new 20-bar high, close in upper third of bar, RVOL.
Writes /workspace/daily_trader/audit/latest-scan.json
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import (
    DEFAULT_EQUITY,
    DEFAULT_RISK_PCT,
    LEV_MAX,
    LEV_MIN,
    __agent_id__,
    __version__,
)
from .universe import (
    allows_overnight,
    build_scan_universe,
    classify,
    clamp_leverage,
    default_leverage,
    is_etf,
    reject_reason,
)

IDT = ZoneInfo("Asia/Jerusalem")
ET = ZoneInfo("America/New_York")

PKG_ROOT = Path(__file__).resolve().parent.parent  # /workspace/daily_trader
AUDIT_DIR = PKG_ROOT / "audit"
LATEST_SCAN = AUDIT_DIR / "latest-scan.json"
CACHE_DIR = AUDIT_DIR / "ohlc_cache"

LOOKBACK_BARS = 20
ATR_LEN = 14
VOL_SMA = 20
RVOL_STOCK = 1.5
RVOL_CRYPTO = 1.2
RVOL_COMMODITY = 1.3
SL_ATR_MULT = 1.25
TP1_R = 1.5
TP2_R = 2.5
FETCH_SLEEP_S = 0.15  # polite Yahoo pacing
CHUNK = 8


def _now_idt_str() -> str:
    return datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten_deadline_et(as_of: Optional[datetime] = None) -> str:
    """US cash session force-flat window start (~15:45 ET)."""
    now_et = (as_of or datetime.now(timezone.utc)).astimezone(ET)
    # next/same weekday cash close window
    d = now_et.date()
    # if weekend, roll to Monday
    while d.weekday() >= 5:
        d = d + timedelta(days=1)
    deadline = datetime.combine(d, dtime(15, 45), tzinfo=ET)
    if now_et > deadline and now_et.weekday() < 5:
        # after window today → next session
        d = d + timedelta(days=1)
        while d.weekday() >= 5:
            d = d + timedelta(days=1)
        deadline = datetime.combine(d, dtime(15, 45), tzinfo=ET)
    return deadline.strftime("%Y-%m-%dT%H:%M:%S%z")


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [str(c[0]).lower() for c in out.columns]
    else:
        out.columns = [str(c).lower() for c in out.columns]
    # dedupe columns if Yahoo duplicates
    out = out.loc[:, ~out.columns.duplicated()]
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in out.columns]
    out = out[keep].dropna(subset=["open", "high", "low", "close"])
    if "volume" not in out.columns:
        out["volume"] = 0.0
    out.index = pd.to_datetime(out.index, utc=True)
    return out.sort_index()


def atr_series(df: pd.DataFrame, length: int = ATR_LEN) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev).abs(), (low - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def fetch_daily(
    symbols: list[str],
    period: str = "3mo",
    use_cache: bool = True,
    sleep_s: float = FETCH_SLEEP_S,
) -> dict[str, pd.DataFrame]:
    """Polite Yahoo daily OHLC fetch with optional disk cache."""
    import yfinance as yf

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}
    pending: list[str] = []

    for sym in symbols:
        cache_path = CACHE_DIR / f"{sym.replace('=', '_').replace('/', '_')}_1d.json"
        if use_cache and cache_path.exists():
            age_h = (time.time() - cache_path.stat().st_mtime) / 3600.0
            if age_h < 6.0:
                try:
                    payload = json.loads(cache_path.read_text())
                    df = pd.DataFrame(payload["rows"])
                    if not df.empty and "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"], utc=True)
                        df = df.set_index("date")
                    df = _normalize_ohlc(df)
                    if len(df) >= LOOKBACK_BARS + ATR_LEN:
                        out[sym] = df
                        continue
                except Exception:  # noqa: BLE001
                    pass
        pending.append(sym)

    for i in range(0, len(pending), CHUNK):
        batch = pending[i : i + CHUNK]
        try:
            raw = yf.download(
                batch,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            # fall back one-by-one
            for sym in batch:
                try:
                    t = yf.Ticker(sym)
                    one = _normalize_ohlc(t.history(period=period, interval="1d", auto_adjust=True))
                    if not one.empty:
                        out[sym] = one
                        _write_cache(sym, one)
                except Exception:  # noqa: BLE001
                    continue
                time.sleep(sleep_s)
            time.sleep(sleep_s)
            continue

        if len(batch) == 1:
            sym = batch[0]
            df = _normalize_ohlc(raw)
            if not df.empty:
                out[sym] = df
                _write_cache(sym, df)
        else:
            for sym in batch:
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        level0 = raw.columns.get_level_values(0)
                        if sym in level0:
                            df = _normalize_ohlc(raw[sym])
                        else:
                            continue
                    else:
                        df = _normalize_ohlc(raw)
                    if not df.empty:
                        out[sym] = df
                        _write_cache(sym, df)
                except Exception:  # noqa: BLE001
                    continue
        time.sleep(sleep_s)

    return out


def _write_cache(sym: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{sym.replace('=', '_').replace('/', '_')}_1d.json"
    rows = df.reset_index()
    date_col = "date" if "date" in rows.columns else rows.columns[0]
    rows = rows.rename(columns={date_col: "date"})
    rows["date"] = pd.to_datetime(rows["date"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps({"symbol": sym, "rows": rows.to_dict(orient="records")}, default=str))


def score_breakout(symbol: str, df: pd.DataFrame) -> dict[str, Any]:
    """Score BREAKOUT on daily bars (proxy for session momentum scan)."""
    cls = classify(symbol)
    base: dict[str, Any] = {
        "symbol": symbol,
        "asset_class": cls,
        "signal": "NONE",
        "score": 0.0,
        "do_not_place": True,
    }
    if is_etf(symbol) or cls == "etf":
        base["error"] = "ETF_REJECT"
        return base
    if df is None or len(df) < LOOKBACK_BARS + ATR_LEN + 2:
        base["error"] = "insufficient_bars"
        base["bars"] = 0 if df is None else len(df)
        return base

    d = df.copy()
    need = LOOKBACK_BARS + ATR_LEN + 2
    if len(d) < need:
        base["error"] = "insufficient_bars"
        base["bars"] = len(d)
        return base

    atr = atr_series(d, ATR_LEN)
    vol_sma = d["volume"].rolling(VOL_SMA, min_periods=max(5, VOL_SMA // 2)).mean()
    last = d.iloc[-1]
    prior = d.iloc[-(LOOKBACK_BARS + 1) : -1]  # exclude today for N-bar high
    prior_high = float(prior["high"].max())
    o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
    vol = float(last["volume"]) if not pd.isna(last["volume"]) else 0.0
    vsma = float(vol_sma.iloc[-1]) if not pd.isna(vol_sma.iloc[-1]) else 0.0
    atr_v = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0

    bar_range = h - l
    upper_third = bar_range > 0 and c >= (l + (2.0 / 3.0) * bar_range)
    new_n_high = h >= prior_high * 0.999  # touch/break 20-bar high
    close_above_prior = c >= prior_high

    if cls == "crypto":
        rvol_min = RVOL_CRYPTO
    elif cls == "commodity":
        rvol_min = RVOL_COMMODITY
    else:
        rvol_min = RVOL_STOCK
    rvol = (vol / vsma) if vsma > 0 else 0.0
    rvol_ok = rvol >= rvol_min or (cls == "commodity" and vsma == 0)  # some futures vol sparse

    # Score components
    score = 0.0
    if new_n_high:
        score += 40.0
    if close_above_prior:
        score += 20.0
    if upper_third:
        score += 20.0
    if rvol_ok:
        score += 20.0
    # bonus: strength of break
    if prior_high > 0 and c > prior_high:
        score += min(10.0, (c / prior_high - 1.0) * 500.0)

    is_breakout = bool(new_n_high and upper_third and rvol_ok)
    signal = "BREAKOUT" if is_breakout and score >= 60 else ("WATCH" if score >= 40 else "NONE")

    lev = clamp_leverage(symbol, default_leverage(symbol))
    # SL: farther of structure low of breakout bar vs 1.25×ATR below close
    struct_sl = l
    atr_sl = c - SL_ATR_MULT * atr_v if atr_v > 0 else struct_sl
    sl = float(min(struct_sl, atr_sl))
    if sl >= c:
        sl = c * 0.98
    risk_per_unit = c - sl
    tp1 = c + TP1_R * risk_per_unit
    tp2 = c + TP2_R * risk_per_unit

    # Margin suggestion for $2k book: risk ≤ risk_pct equity at SL
    equity = DEFAULT_EQUITY
    risk_budget = equity * DEFAULT_RISK_PCT
    if risk_per_unit <= 0 or c <= 0:
        margin_usd = 0.0
        notional = 0.0
        units = 0.0
        max_loss_pct = 0.0
    else:
        # notional sized so loss at SL ≈ risk_budget; margin = notional / lev
        units = risk_budget / risk_per_unit
        notional = units * c
        margin_usd = notional / lev
        # cap margin to 40% of book so we can diversify
        if margin_usd > equity * 0.4:
            margin_usd = equity * 0.4
            notional = margin_usd * lev
            units = notional / c
        max_loss_pct = (units * risk_per_unit) / equity * 100.0

    overnight = allows_overnight(symbol)
    result = {
        **base,
        "signal": signal,
        "score": round(float(score), 2),
        "bars": len(d),
        "last_close": round(c, 6),
        "last_high": round(h, 6),
        "last_low": round(l, 6),
        "prior_20_high": round(prior_high, 6),
        "new_20bar_high": bool(new_n_high),
        "upper_third_close": bool(upper_third),
        "rvol": round(float(rvol), 3),
        "rvol_min": rvol_min,
        "rvol_ok": bool(rvol_ok),
        "atr14": round(atr_v, 6),
        "suggested_leverage": lev,
        "leverage_bounds": [LEV_MIN, min(LEV_MAX, lev if cls == "crypto" else LEV_MAX)],
        "entry": round(c, 6),
        "stop_loss": round(sl, 6),
        "take_profit_1": round(tp1, 6),
        "take_profit_2": round(tp2, 6),
        "tp1_r": TP1_R,
        "tp2_r": TP2_R,
        "risk_per_unit": round(risk_per_unit, 6),
        "margin_suggestion_usd": round(margin_usd, 2),
        "notional_suggestion_usd": round(notional, 2),
        "units_suggestion": round(units, 6),
        "max_loss_pct_equity": round(max_loss_pct, 3),
        "risk_pct_target": DEFAULT_RISK_PCT,
        "equity_basis": equity,
        "allows_overnight": overnight,
        "flatten_deadline": None if overnight else _flatten_deadline_et(),
        "flatten_note": "crypto overnight OK" if overnight else "force flat before US cash close",
    }
    return result


def run_scan(
    symbols: Optional[list[str]] = None,
    period: str = "3mo",
    use_cache: bool = True,
    top_n: int = 25,
) -> dict[str, Any]:
    universe = symbols or build_scan_universe()
    rejected = []
    clean: list[str] = []
    for s in universe:
        reason = reject_reason(s)
        if reason:
            rejected.append({"symbol": s, "reason": reason})
        else:
            clean.append(s)

    frames = fetch_daily(clean, period=period, use_cache=use_cache)
    results: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for sym in clean:
        df = frames.get(sym)
        if df is None or df.empty:
            failed.append({"symbol": sym, "error": "fetch_empty"})
            continue
        try:
            results.append(score_breakout(sym, df))
        except Exception as exc:  # noqa: BLE001
            failed.append({"symbol": sym, "error": str(exc)})

    candidates = [r for r in results if r.get("signal") in ("BREAKOUT", "WATCH")]
    candidates.sort(key=lambda r: (-float(r.get("score") or 0), r.get("symbol") or ""))
    breakouts = [r for r in candidates if r.get("signal") == "BREAKOUT"]

    run_id = f"daily-trader-scan-{datetime.now(IDT).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "run_id": run_id,
        "bot": "Daily Trader",
        "agent_id": __agent_id__,
        "tooling_version": __version__,
        "asOfIDT": _now_idt_str(),
        "asOfUTC": _now_utc_iso(),
        "do_not_place": True,
        "mandate": {
            "universe": "stocks+crypto+commodities",
            "no_etfs": True,
            "equity_basis": DEFAULT_EQUITY,
            "risk_pct": DEFAULT_RISK_PCT,
            "leverage": "x2-x10 capped per class",
            "flatten_stocks_commodities": True,
            "crypto_overnight_ok": True,
        },
        "universe_size": len(clean),
        "fetched": len(frames),
        "n_candidates": len(candidates),
        "n_breakouts": len(breakouts),
        "candidates": candidates[:top_n],
        "breakouts": breakouts[:top_n],
        "all_scored": results,
        "rejected_etf_or_invalid": rejected,
        "failed": failed,
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, default=str) + "\n"
    LATEST_SCAN.write_text(text)
    (AUDIT_DIR / f"{run_id}.json").write_text(text)
    with (AUDIT_DIR / "scan-index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "run_id": run_id,
                    "asOfIDT": payload["asOfIDT"],
                    "n_candidates": len(candidates),
                    "n_breakouts": len(breakouts),
                    "path": str(LATEST_SCAN),
                }
            )
            + "\n"
        )
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Daily Trader breakout scan (no place)")
    p.add_argument("--symbols", nargs="*", help="Override universe symbols")
    p.add_argument("--period", default="3mo")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--json-out", type=str, default=str(LATEST_SCAN))
    args = p.parse_args(argv)

    payload = run_scan(
        symbols=args.symbols,
        period=args.period,
        use_cache=not args.no_cache,
        top_n=args.top,
    )
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.resolve() != LATEST_SCAN.resolve():
        out_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")

    print(
        f"[Daily Trader scan] {payload['asOfIDT']} | universe={payload['universe_size']} "
        f"fetched={payload['fetched']} breakouts={payload['n_breakouts']} "
        f"candidates={payload['n_candidates']} → {LATEST_SCAN}"
    )
    for c in (payload.get("breakouts") or [])[:10]:
        print(
            f"  BREAKOUT {c['symbol']:10s} score={c['score']:5.1f} "
            f"lev=x{c['suggested_leverage']} rvol={c['rvol']:.2f} "
            f"margin=${c['margin_suggestion_usd']:.0f} "
            f"SL={c['stop_loss']} TP1={c['take_profit_1']}"
        )
    if not payload.get("breakouts"):
        print("  (no BREAKOUT signals — markets may be quiet; WATCH/NONE still scored)")
        for c in (payload.get("candidates") or [])[:5]:
            print(f"  {c['signal']:8s} {c['symbol']:10s} score={c['score']:5.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

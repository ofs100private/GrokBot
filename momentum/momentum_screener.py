#!/usr/bin/env python3
"""Momentum Minervini/VCP screener — Momentum-HHHGDTJ (EOD).

Merged: user's sector/commodity universe + VCP contraction string + asset-class
breakout rules, plus our EOD gates (NYSE holiday / intraday ban), regime-first
download, and prepare-trade mcp_order_params (absolute stopLossRate).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from nyse_session import in_intraday_ban, nyse_today_is_open
from momentum_qa.audit import AuditLogger, new_run_id
from momentum_qa.event_calendar import is_event_vol_freeze
from momentum_qa.validate import validate_screener_output

# ==========================================
# 1. הגדרות תצורה ורשימות נכסים
# ==========================================
BENCHMARK = "^GSPC"
VIX = "^VIX"

SECTOR_ETFS = ["XLK", "XLE", "XLF", "XLV", "XLY", "XLI", "XLB", "XLU", "XLP", "XLRE", "XLC"]
COMMODITY_ETFS = ["GLD", "SLV", "USO", "CPER", "URA", "DBA"]

YAHOO_TO_ETORO_MAP = {"BRK-B": "BRK.B", "BF-B": "BF.B"}
ETORO_TO_YAHOO_MAP = {v: k for k, v in YAHOO_TO_ETORO_MAP.items()}


# ==========================================
# 2. פונקציות עזר ומשיכת נתונים
# ==========================================
def get_sp500_symbols() -> list[str]:
    """Full S&P 500 universe — NEVER silently shrink to mega-caps.

    pandas.read_html(html_string) on this box treats the string as a *path*
    (FileNotFoundError). Always wrap with io.StringIO. Cache to disk so a
    transient Wikipedia miss still scans ~500 names (incl. NOW/PANW/CRM).
    """
    import io
    from pathlib import Path

    cache = Path("/workspace/sp500_symbols.json")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}

    def _normalize(syms: list) -> list[str]:
        out = []
        seen = set()
        for t in syms:
            s = str(t).replace(".", "-").strip().upper()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        # CRITICAL: StringIO — bare res.text is treated as a filesystem path
        tables = pd.read_html(io.StringIO(res.text))
        syms = _normalize(tables[0]["Symbol"].tolist())
        if len(syms) < 400:
            raise RuntimeError(f"Wikipedia returned only {len(syms)} symbols")
        cache.write_text(
            json.dumps(
                {
                    "asOf": datetime.utcnow().isoformat() + "Z",
                    "count": len(syms),
                    "symbols": syms,
                },
                indent=2,
            )
        )
        print(f"[info] S&P 500 live list: {len(syms)} symbols", file=sys.stderr)
        return syms
    except Exception as e:
        print(f"[WARN] S&P 500 Wikipedia fetch failed: {e}", file=sys.stderr)
        if cache.exists():
            try:
                cached = json.loads(cache.read_text())
                syms = _normalize(cached.get("symbols") or [])
                if len(syms) >= 400:
                    print(
                        f"[info] Using cached S&P 500 list: {len(syms)} "
                        f"(asOf={cached.get('asOf')})",
                        file=sys.stderr,
                    )
                    return syms
            except Exception as ce:
                print(f"[WARN] Cache read failed: {ce}", file=sys.stderr)
        # Hard fail — do NOT fall back to 10 mega-caps (that skipped NOW/PANW/CRM)
        raise RuntimeError(
            "S&P 500 universe unavailable (Wikipedia + cache). "
            "Refusing mega-cap fallback so Momentum cannot silently miss the index."
        ) from e


def to_etoro_symbol(yahoo_ticker: str) -> str:
    return YAHOO_TO_ETORO_MAP.get(yahoo_ticker, yahoo_ticker.replace("-", "."))


def dwm_returns(close: pd.Series) -> tuple[float, float, float] | None:
    """Day / week(~5) / month(~21) % changes from EOD closes."""
    c = close.dropna()
    if len(c) < 22:
        return None
    last = float(c.iloc[-1])
    day = (last / float(c.iloc[-2]) - 1.0) * 100.0
    week = (last / float(c.iloc[-6]) - 1.0) * 100.0
    month = (last / float(c.iloc[-22]) - 1.0) * 100.0
    return day, week, month



def calculate_rs_score(price_series: pd.Series) -> float:
    if len(price_series) < 252:
        return float("nan")
    p = price_series
    return (
        0.4 * ((p.iloc[-1] / p.iloc[-63]) - 1)
        + 0.2 * ((p.iloc[-1] / p.iloc[-126]) - 1)
        + 0.2 * ((p.iloc[-1] / p.iloc[-189]) - 1)
        + 0.2 * ((p.iloc[-1] / p.iloc[-252]) - 1)
    )


def check_vcp(df: pd.DataFrame, window: int = 50) -> tuple[bool, str]:
    if len(df) < window:
        return False, "N/A"
    recent = df.iloc[-window:]
    v_sma50 = float(df["Volume"].rolling(50).mean().iloc[-1])
    d1 = (
        (recent.iloc[0:25]["High"].max() - recent.iloc[0:25]["Low"].min())
        / recent.iloc[0:25]["High"].max()
    ) * 100
    d2 = (
        (recent.iloc[25:40]["High"].max() - recent.iloc[25:40]["Low"].min())
        / recent.iloc[25:40]["High"].max()
    ) * 100
    d3 = (
        (recent.iloc[40:]["High"].max() - recent.iloc[40:]["Low"].min())
        / recent.iloc[40:]["High"].max()
    ) * 100
    vol_dry = float(recent.iloc[40:]["Volume"].mean()) < v_sma50
    is_vcp = ((d1 > d2 > d3 and d3 <= 8.5) or (d1 > d3 and d3 <= 6.0)) and vol_dry
    return bool(is_vcp), f"{d1:.1f}% -> {d2:.1f}% -> {d3:.1f}%"


def _extract_ohlcv(raw: pd.DataFrame, sym: str) -> pd.DataFrame | None:
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if sym not in set(raw.columns.get_level_values(0)):
                return None
            df = raw[sym].copy()
        else:
            if "Close" not in raw.columns:
                return None
            df = raw.copy()
        need = {"Open", "High", "Low", "Close", "Volume"}
        if not need.issubset(set(df.columns)):
            return None
        df = df.dropna(subset=["Close", "Volume"])
        return df if len(df) else None
    except Exception:
        return None


def _download(syms: list[str], start: str) -> pd.DataFrame:
    return yf.download(
        syms,
        start=start,
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=True,
    )


# ==========================================
# 3. ליבת הסורק
# ==========================================
SECTOR_ETF_SET = set(SECTOR_ETFS)
WATCH_NEAR = ("NOW", "PANW", "CRM")


def _regime_state(spx_close: float, spx_sma50: float, vix_close: float) -> dict:
    """Split regime (2026-09-16 full fix).

    - vix_hard / hard_spx (>2% below SMA50): HARD HALT for new buys (still scan)
    - soft_spx (under SMA50 but within 2%): STOCK BUY only if MOMENTUM_BREAKOUT
      + RVOL>=2.5 + RS>=90 + DWM green; soft VCP/VOLUME_BREAKOUT → REGIME_SOFT_VCP_BLOCK;
      ETF/COMMODITY → REGIME_SOFT_ETF_BLOCK
    - healthy: both sleeves OK under pack rules
    """
    vix_hard = vix_close >= 25.0
    hard_spx = spx_close < spx_sma50 * 0.98
    soft_spx = (spx_close < spx_sma50) and (spx_close >= spx_sma50 * 0.98)
    healthy = (spx_close >= spx_sma50) and (vix_close < 25.0)
    hard_halt = vix_hard or hard_spx
    if hard_halt:
        mode = "HARD_HALT"
    elif soft_spx and not vix_hard:
        mode = "SOFT"
    else:
        mode = "HEALTHY"
    spx_pct = ((spx_close / spx_sma50) - 1.0) * 100.0 if spx_sma50 else 0.0
    return {
        "mode": mode,
        "hard_halt": hard_halt,
        "soft": mode == "SOFT",
        "healthy": healthy and mode == "HEALTHY",
        "vix_hard": vix_hard,
        "hard_spx": hard_spx,
        "soft_spx": soft_spx and not vix_hard,
        "spx_close": round(spx_close, 2),
        "spx_sma50": round(spx_sma50, 2),
        "vix_close": round(vix_close, 2),
        "spx_pct_vs_sma50": round(spx_pct, 3),
        "spx_above_sma50": spx_close >= spx_sma50,
        "vix_ok": vix_close < 25.0,
    }


def _pack_picks(
    buys: list[dict],
    skips: list[dict],
    *,
    max_stock_picks: int = 3,
    max_sector_etf: int = 1,
    max_breakout_stocks: int = 2,
) -> list[dict]:
    """Pack: up to 2 MOMENTUM_BREAKOUT stocks, fill to 3 with VCP/volume, then 1 ETF.

    Stock slots prefer breakout sleeve (reason=MOMENTUM_BREAKOUT) by RS desc (cap 2).
    Remaining stock slots filled from VCP_SETUP / VOLUME_BREAKOUT by
    (VOLUME_BREAKOUT first, then RS). Then 1 sector ETF if present (HEALTHY only
    in practice — soft/hard already SKIP ETF buys). Commodity only if no sector ETF.
    """
    stock_buys = [x for x in buys if x.get("asset_class") == "STOCK"]
    sector_buys = [
        x
        for x in buys
        if x.get("asset_class") == "ETF"
        and (x.get("yahoo_symbol") or x.get("symbol")) in SECTOR_ETF_SET
    ]
    commodity_buys = [x for x in buys if x.get("asset_class") == "COMMODITY"]

    breakout_buys = [x for x in stock_buys if x.get("reason") == "MOMENTUM_BREAKOUT"]
    vcp_buys = [
        x for x in stock_buys if x.get("reason") in ("VCP_SETUP", "VOLUME_BREAKOUT")
    ]
    breakout_buys.sort(key=lambda x: x.get("rs_rating") or 0, reverse=True)
    # Within VCP list: VOLUME_BREAKOUT (breakout-flag) before quiet VCP, then RS
    vcp_buys.sort(
        key=lambda x: (x.get("reason") == "VOLUME_BREAKOUT", x.get("rs_rating") or 0),
        reverse=True,
    )
    sector_buys.sort(
        key=lambda x: (
            x.get("setup_type") == "BREAKOUT",
            x.get("rs_rating") or 0,
        ),
        reverse=True,
    )
    commodity_buys.sort(
        key=lambda x: (
            x.get("setup_type") == "BREAKOUT",
            x.get("rs_rating") or 0,
        ),
        reverse=True,
    )
    skips.sort(key=lambda x: x.get("rs_rating") or 0, reverse=True)

    picked: list[dict] = []
    picked_syms: set[str] = set()

    for x in breakout_buys[:max_breakout_stocks]:
        sym = x.get("symbol") or x.get("etoro_symbol")
        picked.append(x)
        if sym:
            picked_syms.add(sym)

    slots_left = max_stock_picks - len(picked)
    for x in vcp_buys:
        if slots_left <= 0:
            break
        sym = x.get("symbol") or x.get("etoro_symbol")
        if sym and sym in picked_syms:
            continue
        picked.append(x)
        if sym:
            picked_syms.add(sym)
        slots_left -= 1

    etf_taken = False
    if max_sector_etf > 0 and sector_buys:
        picked.extend(sector_buys[:max_sector_etf])
        etf_taken = True
    # Commodity only if no sector ETF taken and room remains under pack cap
    if (
        not etf_taken
        and len(picked) < (max_stock_picks + max_sector_etf)
        and commodity_buys
    ):
        picked.append(commodity_buys[0])

    # Keep top 5 DWM/regime skips for audit
    return picked + skips[:5]


def _write_near_misses(near_misses: list[dict], day: str | None = None) -> str:
    from pathlib import Path as _P

    day = day or datetime.now().strftime("%Y-%m-%d")
    path = _P("/workspace/momentum_audit") / f"near-miss-{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Prefer WATCH_NEAR symbols if present, then top by RS; cap 25
    by_sym = {m["symbol"]: m for m in near_misses}
    ordered: list[dict] = []
    for w in WATCH_NEAR:
        if w in by_sym:
            ordered.append(by_sym.pop(w))
    rest = sorted(by_sym.values(), key=lambda m: m.get("rs") or 0, reverse=True)
    ordered.extend(rest)
    top = ordered[:25]
    path.write_text(json.dumps({"asOf": day, "count": len(top), "near_misses": top}, indent=2))
    return str(path)


def run_screener(
    allocation_usd: float = 1000,
    max_stock_picks: int = 3,
    max_sector_etf: int = 1,
    max_picks: int | None = None,  # legacy alias → total pack size hint
    _trace: list | None = None,
):
    """Scan + rank. Always scans when session open (even on HARD/SOFT regime)."""
    traces: list = _trace if _trace is not None else []

    def T(msg: str, **details):
        traces.append({"msg": msg, "details": details})
        print(f"[TRACE] {msg} {details if details else ''}", file=sys.stderr)

    if not nyse_today_is_open():
        return [{"action": "SKIP", "reason": "NYSE_HOLIDAY_OR_CLOSED", "mcp_order_params": None}]
    if in_intraday_ban():
        return [{"action": "SKIP", "reason": "INTRADAY_BAN", "mcp_order_params": None}]

    if max_picks is not None and max_picks > 0:
        # Back-compat: old callers passed max_picks=3 meaning total buys
        max_stock_picks = min(max_stock_picks, 3)
        max_sector_etf = min(max_sector_etf, 1)

    start_date = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")

    # Regime FIRST (cheap) — but DO NOT early-return HALT without scanning
    try:
        regime_raw = _download([BENCHMARK, VIX], start_date)
        spx_df = _extract_ohlcv(regime_raw, BENCHMARK)
        vix_df = _extract_ohlcv(regime_raw, VIX)
        if spx_df is None or vix_df is None:
            raise RuntimeError("missing SPX or VIX frame")

        spx_close = float(spx_df["Close"].iloc[-1])
        spx_sma50 = float(spx_df["Close"].rolling(50).mean().iloc[-1])
        vix_close = float(vix_df["Close"].iloc[-1])
        regime = _regime_state(spx_close, spx_sma50, vix_close)
    except Exception as e:
        print(f"[ERROR] Market Regime Check Failed: {e}", file=sys.stderr)
        raise RuntimeError(f"regime check failed: {e}") from e

    T(
        "regime",
        mode=regime["mode"],
        spx_close=regime["spx_close"],
        spx_sma50=regime["spx_sma50"],
        spx_pct=regime["spx_pct_vs_sma50"],
        vix=regime["vix_close"],
        hard_halt=regime["hard_halt"],
        soft=regime["soft"],
    )

    sp500_tickers = get_sp500_symbols()
    if len(sp500_tickers) < 400:
        raise RuntimeError(
            f"S&P 500 universe too small ({len(sp500_tickers)}); expected ~500"
        )
    universe = {sym: "STOCK" for sym in sp500_tickers}
    universe.update({sym: "ETF" for sym in SECTOR_ETFS})
    universe.update({sym: "COMMODITY" for sym in COMMODITY_ETFS})

    in_watch = {s: (s in universe) for s in WATCH_NEAR}
    T(
        "universe",
        universe_n=len(universe),
        sp500_n=len(sp500_tickers),
        watch=in_watch,
    )

    print(
        f"[info] regime={regime['mode']} — scanning {len(universe)} names "
        f"(S&P {len(sp500_tickers)} + {len(SECTOR_ETFS)} sector + "
        f"{len(COMMODITY_ETFS)} commodity ETFs; NOW/PANW/CRM in-universe="
        f"{all(in_watch.values())})…",
        file=sys.stderr,
    )
    raw = _download(list(universe.keys()), start_date)

    valid_dfs: dict[str, pd.DataFrame] = {}
    raw_rs: dict[str, float] = {}
    drop_short = 0
    for sym in universe:
        try:
            df = _extract_ohlcv(raw, sym)
            if df is None or len(df) < 252:
                drop_short += 1
                continue
            score = calculate_rs_score(df["Close"])
            if not np.isnan(score):
                raw_rs[sym] = score
                valid_dfs[sym] = df
        except Exception:
            drop_short += 1
            continue

    T("download_ok", valid_n=len(valid_dfs), drop_short_or_nan=drop_short)
    if not raw_rs:
        raise RuntimeError("empty universe after download (no valid RS series)")

    rs_ratings = (pd.Series(raw_rs).rank(pct=True) * 99).astype(int)
    candidates = []
    near_misses: list[dict] = []
    drop_counts = {
        "minervini": 0,
        "rs": 0,
        "setup": 0,
        "dwm_data": 0,
        "dwm_fail": 0,
        "regime_hard": 0,
        "regime_soft_etf": 0,
        "regime_soft_rs": 0,
        "regime_soft_vcp": 0,
        "event_freeze": 0,
    }

    def _nm(sym, asset_class, rs_val, blocked_by, dwm=None, extra=None):
        row = {
            "symbol": sym,
            "asset_class": asset_class,
            "rs": int(rs_val) if rs_val is not None else None,
            "blocked_by": blocked_by,
        }
        if dwm is not None:
            row["day"] = round(dwm[0], 2)
            row["week"] = round(dwm[1], 2)
            row["month"] = round(dwm[2], 2)
        if extra:
            row.update(extra)
        near_misses.append(row)

    def _stock_sleeves(df, curr_price, rs_val, rvol, day_pct, week_pct, month_pct):
        """Return (sleeve_reason, setup_type, is_vcp, vcp_pattern) or (None,...).

        BREAKOUT (preferred): RS>=90, RVOL>=2.0, close-based 20d high,
        upper-third close, day/week/month >= 0.
        VCP secondary: VCP_SETUP or volume breakout RVOL>=1.5, RS>=80, DWM w/m green.
        """
        is_vcp, vcp_pattern = check_vcp(df)
        # Close-based 20-session high (prior 20 bars excluding today)
        prior_closes = df["Close"].iloc[-21:-1]
        high20_close = float(prior_closes.max()) if len(prior_closes) >= 20 else float("nan")
        new_20d_high = (not (high20_close != high20_close)) and (curr_price >= high20_close)

        hi = float(df["High"].iloc[-1])
        lo = float(df["Low"].iloc[-1])
        if hi > lo:
            upper_third = ((curr_price - lo) / (hi - lo)) >= 0.66
        else:
            upper_third = False

        dwm_all_green = day_pct >= 0 and week_pct >= 0 and month_pct >= 0
        dwm_wm_green = week_pct >= 0 and month_pct >= 0

        pivot_high = float(df["High"].iloc[-16:-1].max())
        vol_breakout = (
            (rvol >= 1.5)
            and (curr_price > pivot_high)
            and (curr_price > float(df["Open"].iloc[-1]))
        )

        # Preferred BREAKOUT sleeve
        if (
            rs_val >= 90
            and rvol >= 2.0
            and new_20d_high
            and upper_third
            and dwm_all_green
        ):
            return "MOMENTUM_BREAKOUT", "BREAKOUT", is_vcp, vcp_pattern

        # Secondary VCP / volume path (needs DWM week/month green)
        if dwm_wm_green and rs_val >= 80:
            if is_vcp:
                return "VCP_SETUP", "VCP_READY", is_vcp, vcp_pattern
            if vol_breakout:
                return "VOLUME_BREAKOUT", "BREAKOUT", is_vcp, vcp_pattern

        return None, None, is_vcp, vcp_pattern

    for sym, df in valid_dfs.items():
        try:
            c = df["Close"]
            curr_price = float(c.iloc[-1])
            sma50 = float(c.rolling(50).mean().iloc[-1])
            sma150 = float(c.rolling(150).mean().iloc[-1])
            sma200 = float(c.rolling(200).mean().iloc[-1])
            sma200_prev = float(c.rolling(200).mean().iloc[-22])
            high52 = float(c.iloc[-252:].max())
            low52 = float(c.iloc[-252:].min())
            rs_val = int(rs_ratings[sym])
            asset_class = universe[sym]

            # Core Minervini trend stack (without RS) — used for near-miss eligibility
            trend_ok = (
                curr_price > sma150 > sma200
                and sma200 > sma200_prev
                and sma50 > sma150
                and curr_price > sma50
                and curr_price >= (low52 * 1.30)
                and curr_price >= (high52 * 0.85)
            )
            if not trend_ok:
                drop_counts["minervini"] += 1
                continue

            if rs_val < 80:
                drop_counts["rs"] += 1
                _nm(sym, asset_class, rs_val, "RS")
                continue

            vol_sma50 = float(df["Volume"].rolling(50).mean().iloc[-2])
            curr_vol = float(df["Volume"].iloc[-1])
            rvol = float(curr_vol / vol_sma50) if vol_sma50 > 0 else 0.0
            pivot_high = float(df["High"].iloc[-16:-1].max())

            dwm = dwm_returns(c)
            if dwm is None:
                drop_counts["dwm_data"] += 1
                _nm(sym, asset_class, rs_val, "DWM_DATA")
                continue
            day_pct, week_pct, month_pct = dwm

            is_vcp, vcp_pattern = check_vcp(df)
            reason = None
            setup_type = None

            if asset_class in ("ETF", "COMMODITY"):
                is_breakout = (curr_price > pivot_high) and (
                    curr_price > float(df["Open"].iloc[-1])
                )
                if not (is_breakout or is_vcp):
                    drop_counts["setup"] += 1
                    _nm(sym, asset_class, rs_val, "VCP_BREAKOUT")
                    continue
                reason = "VOLUME_BREAKOUT" if is_breakout else "VCP_SETUP"
                setup_type = "BREAKOUT" if is_breakout else "VCP_READY"
            else:
                reason, setup_type, is_vcp, vcp_pattern = _stock_sleeves(
                    df, curr_price, rs_val, rvol, day_pct, week_pct, month_pct
                )
                if reason is None:
                    drop_counts["setup"] += 1
                    blocked = "NO_BREAKOUT_NO_VCP" if rs_val >= 90 else "VCP_BREAKOUT"
                    _nm(
                        sym,
                        asset_class,
                        rs_val,
                        blocked,
                        dwm=dwm,
                        extra={"rvol": round(rvol, 2)},
                    )
                    continue

            etoro_sym = to_etoro_symbol(sym)
            stop_loss = round(min(pivot_high * 0.95, curr_price * 0.94), 2)
            # DWM hard gate: week/month green for all buys; BREAKOUT also needs day>=0
            if reason == "MOMENTUM_BREAKOUT":
                dwm_fail = day_pct < 0 or week_pct < 0 or month_pct < 0
            else:
                dwm_fail = week_pct < 0 or month_pct < 0

            base = {
                "symbol": etoro_sym,
                "etoro_symbol": etoro_sym,
                "yahoo_symbol": sym,
                "asset_class": asset_class,
                "price": round(curr_price, 2),
                "current_price": round(curr_price, 2),
                "stop_loss": stop_loss,
                "amount_usd": allocation_usd,
                "setup_type": setup_type,
                "rs_rating": rs_val,
                "rvol": round(rvol, 2),
                "vcp_contraction": vcp_pattern,
                "day_pct": round(day_pct, 2),
                "week_pct": round(week_pct, 2),
                "month_pct": round(month_pct, 2),
                "regime_mode": regime["mode"],
                "sleeve": reason,
            }

            if dwm_fail:
                drop_counts["dwm_fail"] += 1
                _nm(sym, asset_class, rs_val, "DWM", dwm=dwm)
                row = dict(base)
                row.update(
                    {
                        "action": "SKIP",
                        "reason": "DWM_STRENGTH_FAIL",
                        "rationale": (
                            f"DWM_STRENGTH_FAIL {etoro_sym}: day {day_pct:.2f}% / "
                            f"week {week_pct:.2f}% / month {month_pct:.2f}% — "
                            f"setup {reason} blocked before place QA"
                        ),
                        "mcp_order_params": None,
                    }
                )
                candidates.append(row)
                continue

            # --- Regime gates on would-be BUYs ---
            if regime["hard_halt"]:
                drop_counts["regime_hard"] += 1
                _nm(sym, asset_class, rs_val, "REGIME_HARD_HALT", dwm=dwm)
                row = dict(base)
                row.update(
                    {
                        "action": "SKIP",
                        "reason": "REGIME_HARD_HALT",
                        "rationale": (
                            f"REGIME_HARD_HALT blocked {etoro_sym} "
                            f"(mode={regime['mode']} spx_pct={regime['spx_pct_vs_sma50']} "
                            f"vix={regime['vix_close']})"
                        ),
                        "mcp_order_params": None,
                    }
                )
                candidates.append(row)
                continue

            if regime["soft"]:
                # ETF/COMMODITY blocked in soft tape (stocks-first)
                if asset_class in ("ETF", "COMMODITY"):
                    drop_counts["regime_soft_etf"] += 1
                    _nm(sym, asset_class, rs_val, "REGIME_SOFT_ETF_BLOCK", dwm=dwm)
                    row = dict(base)
                    row.update(
                        {
                            "action": "SKIP",
                            "reason": "REGIME_SOFT_ETF_BLOCK",
                            "rationale": (
                                f"REGIME_SOFT_ETF_BLOCK {etoro_sym}: soft SPX tape — "
                                "stocks-first; ETF/commodity new buys skipped"
                            ),
                            "mcp_order_params": None,
                        }
                    )
                    candidates.append(row)
                    continue
                # Soft STOCK: only MOMENTUM_BREAKOUT with RVOL>=2.5 + RS>=90 + DWM
                if asset_class == "STOCK":
                    soft_breakout_ok = (
                        reason == "MOMENTUM_BREAKOUT"
                        and rvol >= 2.5
                        and rs_val >= 90
                        and day_pct >= 0
                        and week_pct >= 0
                        and month_pct >= 0
                    )
                    if not soft_breakout_ok:
                        if reason in ("VCP_SETUP", "VOLUME_BREAKOUT") or (
                            reason == "MOMENTUM_BREAKOUT" and rvol < 2.5
                        ):
                            drop_counts["regime_soft_vcp"] += 1
                            skip_reason = "REGIME_SOFT_VCP_BLOCK"
                            blocked = "REGIME_SOFT_VCP_BLOCK"
                        else:
                            drop_counts["regime_soft_rs"] += 1
                            skip_reason = "REGIME_SOFT_RS"
                            blocked = "REGIME_SOFT_RS"
                        _nm(sym, asset_class, rs_val, blocked, dwm=dwm, extra={"rvol": round(rvol, 2), "sleeve": reason})
                        row = dict(base)
                        row.update(
                            {
                                "action": "SKIP",
                                "reason": skip_reason,
                                "rationale": (
                                    f"{skip_reason} {etoro_sym}: soft SPX — STOCK needs "
                                    f"MOMENTUM_BREAKOUT RVOL>=2.5 RS>=90 DWM "
                                    f"(got sleeve={reason} RS={rs_val} RVOL={rvol:.2f})"
                                ),
                                "mcp_order_params": None,
                            }
                        )
                        candidates.append(row)
                        continue

            # Healthy or soft MOMENTUM_BREAKOUT (strict) → BUY
            row = dict(base)
            row.update(
                {
                    "action": "BUY",
                    "reason": reason,
                    "rationale": (
                        f"{reason} on {asset_class} {etoro_sym}: RS={rs_val} "
                        f"DWM d/w/m={day_pct:.2f}/{week_pct:.2f}/{month_pct:.2f} "
                        f"regime={regime['mode']}"
                    ),
                    "mcp_order_params": {
                        "account": "real",
                        "direction": "buy",
                        "symbol": etoro_sym,
                        "orderType": "mkt",
                        "leverage": 1,
                        "amount": allocation_usd,
                        "stopLossRate": stop_loss,
                        "stopLossType": "fixed",
                    },
                }
            )
            candidates.append(row)
        except Exception:
            continue

    # Ensure watch symbols appear in near-miss if downloaded but not already listed
    have_nm = {m["symbol"] for m in near_misses}
    for w in WATCH_NEAR:
        if w in valid_dfs and w not in have_nm:
            rs_w = int(rs_ratings[w]) if w in rs_ratings.index else None
            dwm_w = dwm_returns(valid_dfs[w]["Close"])
            _nm(w, universe.get(w, "STOCK"), rs_w, "NOT_SETUP_OR_TREND", dwm=dwm_w)

    near_path = _write_near_misses(near_misses)
    T("near_misses", count=len(near_misses), path=near_path, drop_counts=drop_counts)

    # Event-vol freeze: convert would-be BUYs → SKIP; still keep scan + near-miss
    freeze, freeze_reason = is_event_vol_freeze()
    T("event_vol_freeze", freeze=freeze, reason=freeze_reason)
    if freeze:
        for row in candidates:
            if row.get("action") == "BUY":
                drop_counts["event_freeze"] += 1
                row["action"] = "SKIP"
                row["reason"] = "EVENT_VOL_FREEZE"
                row["rationale"] = (
                    f"EVENT_VOL_FREEZE blocked {row.get('symbol')}: {freeze_reason}"
                )
                row["mcp_order_params"] = None

    buys = [x for x in candidates if x.get("action") == "BUY"]
    skips = [x for x in candidates if x.get("action") == "SKIP"]
    packed = _pack_picks(
        buys, skips, max_stock_picks=max_stock_picks, max_sector_etf=max_sector_etf
    )

    out: list[dict] = []
    if freeze:
        out.append(
            {
                "action": "HALT",
                "reason": "EVENT_VOL_FREEZE",
                "details": (
                    f"{freeze_reason}. Scan completed for near-misses; zero new BUYs."
                ),
                "regime": regime,
                "near_misses_path": near_path,
                "mcp_order_params": None,
            }
        )
    if regime["hard_halt"]:
        out.append(
            {
                "action": "HALT",
                "reason": "MARKET_REGIME_RISK",
                "details": (
                    f"HARD HALT mode={regime['mode']}: "
                    f"SPX {regime['spx_close']} vs SMA50 {regime['spx_sma50']} "
                    f"({regime['spx_pct_vs_sma50']}%), VIX {regime['vix_close']}. "
                    "Scan completed for near-misses; zero new BUYs."
                ),
                "regime": regime,
                "near_misses_path": near_path,
                "mcp_order_params": None,
            }
        )
    # Attach regime + near_miss path on first actionable/skip for summary consumers
    for row in packed:
        row.setdefault("regime_mode", regime["mode"])
        row.setdefault("near_misses_path", near_path)
        out.append(row)

    # Stash meta for QA wrapper (not part of trade rows)
    out_meta = {
        "regime": regime,
        "universe_n": len(universe),
        "near_misses_path": near_path,
        "near_miss_count": len(near_misses),
        "drop_counts": drop_counts,
        "buy_n_pre_pack": len(buys),
        "buy_n_packed": sum(1 for r in packed if r.get("action") == "BUY"),
        "skip_n": len(skips),
        "hard_halt": regime["hard_halt"],
        "event_vol_freeze": freeze,
        "event_vol_freeze_reason": freeze_reason,
        "traces": traces,
    }
    # Attach as private attr via list subclass isn't available; use module-level stash
    run_screener._last_meta = out_meta  # type: ignore[attr-defined]
    T(
        "pack_done",
        buys_pre=len(buys),
        buys_packed=out_meta["buy_n_packed"],
        skips=len(skips),
        hard_halt=regime["hard_halt"],
    )
    return out


run_screener._last_meta = {}  # type: ignore[attr-defined]


def run_screener_with_qa(
    allocation_usd: float = 1000,
    max_stock_picks: int = 3,
    max_sector_etf: int = 1,
    max_picks: int | None = None,
) -> list:
    """Run screener with TRACE audit, up to 3 attempts, QA gate, run-summary JSON."""
    from pathlib import Path as _P

    run_id = new_run_id("screener")
    log = AuditLogger(run_id, "momentum_screener.py")
    total_cap = (max_stock_picks + max_sector_etf) if max_picks is None else max_picks
    max_attempts = 3
    last_err: Exception | None = None
    signals: list | None = None
    meta: dict = {}

    for attempt in range(1, max_attempts + 1):
        try:
            log.trace(
                f"screener attempt {attempt}/{max_attempts}",
                details={"attempt": attempt, "allocation_usd": allocation_usd},
            )
            traces: list = []
            signals = run_screener(
                allocation_usd=allocation_usd,
                max_stock_picks=max_stock_picks,
                max_sector_etf=max_sector_etf,
                max_picks=max_picks,
                _trace=traces,
            )
            meta = getattr(run_screener, "_last_meta", {}) or {}
            for tr in traces:
                log.trace(tr.get("msg", "trace"), details=tr.get("details") or {})

            # Empty / universe failure → retry
            is_empty = not signals
            only_session_skip = (
                len(signals) == 1
                and signals[0].get("action") == "SKIP"
                and signals[0].get("reason") in ("NYSE_HOLIDAY_OR_CLOSED", "INTRADAY_BAN")
            )
            if is_empty:
                raise RuntimeError("empty screener output")
            if only_session_skip:
                # Not a retry case — session closed
                break

            # Success path (HALT with near-misses / buys / skips all OK)
            log.trace(
                f"attempt {attempt} produced {len(signals)} rows",
                details={
                    "attempt": attempt,
                    "universe_n": meta.get("universe_n"),
                    "regime": meta.get("regime"),
                    "near_miss_count": meta.get("near_miss_count"),
                    "drop_counts": meta.get("drop_counts"),
                },
            )
            last_err = None
            break
        except Exception as e:
            last_err = e
            log.error(
                "run_screener",
                e,
                rationale=f"Screener attempt {attempt}/{max_attempts} failed: {e}",
                details={"attempt": attempt},
            )
            log.trace(
                f"retry after failure attempt={attempt}",
                details={"attempt": attempt, "error": str(e)},
            )
            signals = None
            if attempt == max_attempts:
                break

    if last_err is not None and signals is None:
        err_row = {
            "action": "ERROR",
            "reason": str(last_err),
            "rationale": f"All {max_attempts} screener attempts failed: {last_err}",
            "mcp_order_params": None,
        }
        log.action(
            "ERROR",
            rationale=err_row["rationale"],
            details={"attempts": max_attempts},
        )
        summary = {
            "run_id": run_id,
            "ok": False,
            "regime": meta.get("regime"),
            "universe_n": meta.get("universe_n"),
            "near_misses_path": meta.get("near_misses_path"),
            "buys": [],
            "skips": [],
            "halt": False,
            "error": str(last_err),
        }
        _P("/workspace/momentum_audit").mkdir(parents=True, exist_ok=True)
        (_P("/workspace/momentum_audit") / f"screener-run-{run_id}.json").write_text(
            json.dumps(summary, indent=2, default=str)
        )
        log.end("FAILED after retries", details=summary)
        return [err_row]

    assert signals is not None
    annotated, pack = validate_screener_output(
        signals, allocation_usd=allocation_usd, max_picks=total_cap
    )

    for row in annotated:
        action = row.get("action")
        rationale = row.get("rationale") or row.get("details") or row.get("reason") or action
        if action == "BUY":
            rationale = (
                f"{row.get('reason')} on {row.get('asset_class')} {row.get('symbol')}: "
                f"RS={row.get('rs_rating')} RVOL={row.get('rvol')} "
                f"VCP={row.get('vcp_contraction')} | {rationale}"
            )
            row["rationale"] = rationale

        qa = row.get("qa") or {}
        intentional_skip = action == "SKIP" and row.get("reason") in (
            "DWM_STRENGTH_FAIL",
            "REGIME_HARD_HALT",
            "REGIME_SOFT_ETF_BLOCK",
            "REGIME_SOFT_RS",
            "REGIME_SOFT_VCP_BLOCK",
            "EVENT_VOL_FREEZE",
        )
        is_dev = (not qa.get("ok", True)) or bool((qa.get("deviations") or []))
        if intentional_skip:
            is_dev = False
        if is_dev:
            for d in qa.get("deviations") or [{"code": "QA_FAIL"}]:
                log.deviation(
                    d.get("code", "QA_FAIL"),
                    rationale=f"QA rejected candidate: {qa.get('reasons')}",
                    symbol=row.get("symbol") or row.get("etoro_symbol"),
                    details={
                        "candidate": {k: row[k] for k in row if k != "mcp_order_params"},
                        "qa": qa,
                    },
                )

        log.action(
            action or "UNKNOWN",
            rationale=str(rationale),
            symbol=row.get("symbol") or row.get("etoro_symbol"),
            details={
                "asset_class": row.get("asset_class"),
                "rs_rating": row.get("rs_rating"),
                "rvol": row.get("rvol"),
                "stop_loss": row.get("stop_loss"),
                "amount_usd": row.get("amount_usd") or allocation_usd,
                "setup": row.get("reason") or row.get("setup_type"),
                "day_pct": row.get("day_pct"),
                "week_pct": row.get("week_pct"),
                "month_pct": row.get("month_pct"),
                "regime_mode": row.get("regime_mode") or (meta.get("regime") or {}).get("mode"),
                "qa_pack_verdict": pack.verdict,
            },
            deviation=is_dev,
            deviation_code=(
                row.get("reason")
                if intentional_skip
                else ((qa.get("deviations") or [{}])[0].get("code") if is_dev else None)
            ),
            qa_verdict=qa.get("verdict"),
            qa_reasons=qa.get("reasons"),
        )

    executable = []
    for row in annotated:
        if row.get("action") == "BUY" and not (row.get("qa") or {}).get("ok"):
            continue
        if row.get("action") == "BUY" and not pack.ok:
            log.deviation(
                "PACK_FAIL_BLOCK_BUY",
                rationale=f"Buy blocked because screener QA pack FAILED: {pack.reasons}",
                symbol=row.get("symbol"),
            )
            continue
        executable.append(row)

    buys_syms = [r.get("symbol") for r in executable if r.get("action") == "BUY"]
    skip_syms = [
        {"symbol": r.get("symbol"), "reason": r.get("reason")}
        for r in executable
        if r.get("action") == "SKIP"
    ]
    halt = any(r.get("action") == "HALT" for r in executable)
    summary = {
        "run_id": run_id,
        "ok": pack.ok,
        "regime": meta.get("regime"),
        "universe_n": meta.get("universe_n"),
        "near_misses_path": meta.get("near_misses_path"),
        "near_miss_count": meta.get("near_miss_count"),
        "drop_counts": meta.get("drop_counts"),
        "buys": buys_syms,
        "skips": skip_syms,
        "halt": halt,
        "pack": pack.to_dict(),
        "executable_n": len(executable),
    }
    _P("/workspace/momentum_audit").mkdir(parents=True, exist_ok=True)
    (_P("/workspace/momentum_audit") / f"screener-run-{run_id}.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    log.trace("run_summary_written", details={"path": f"screener-run-{run_id}.json", **{k: summary[k] for k in ("universe_n", "halt", "buys") if k in summary}})

    log.end(
        f"Screener done: pack={pack.verdict}, rows={len(annotated)}, executable={len(executable)}, halt={halt}",
        details=pack.to_dict(),
    )
    return executable


if __name__ == "__main__":
    print("[info] EOD screener + QA gate…", file=sys.stderr)
    try:
        signals = run_screener_with_qa()
        print(json.dumps(signals, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps([{"action": "ERROR", "reason": str(e), "mcp_order_params": None}], indent=2))
        sys.exit(1)

"""Daily breakout / inflection analysis (closing prices + volume).

Implements skill breakout-technical-analysis logic for automation.
Never places trades.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IDT = ZoneInfo("Asia/Jerusalem")
TIMEFRAME = "1D"


@dataclass
class AnalyzeConfig:
    lookback: int = 60
    consol_window: int = 20
    vol_sma: int = 20
    vol_min_ratio: float = 1.0  # at least average
    vol_confirm_ratio: float = 1.5
    near_r_pct: float = 0.02  # within 2% of R = WATCH
    atr_length: int = 14
    sl_atr_mult: float = 1.5
    tp_r_mult: float = 2.0
    min_touches: int = 2
    touch_tol_pct: float = 0.01


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def analyze_symbol(symbol: str, df: pd.DataFrame, cfg: Optional[AnalyzeConfig] = None) -> dict[str, Any]:
    """Analyze one symbol on daily bars. Requires columns open/high/low/close/volume."""
    cfg = cfg or AnalyzeConfig()
    out: dict[str, Any] = {
        "symbol": symbol.upper(),
        "timeframe": TIMEFRAME,
        "signal": "NONE",
        "do_not_place": True,
    }
    if df is None or len(df) < max(cfg.consol_window + 5, cfg.vol_sma + 5, cfg.atr_length + 5):
        out["error"] = "insufficient_bars"
        return out

    d = df.copy()
    d.columns = [str(c).lower() for c in d.columns]
    if isinstance(df.columns, pd.MultiIndex):
        d.columns = [str(c[0]).lower() for c in df.columns]
    need = ["open", "high", "low", "close", "volume"]
    for c in need:
        if c not in d.columns:
            out["error"] = f"missing_{c}"
            return out
    d = d.dropna(subset=need).tail(cfg.lookback)
    if len(d) < cfg.consol_window + 2:
        out["error"] = "insufficient_bars_after_clean"
        return out

    # Resistance R from prior consol_window closes (exclude last bar)
    prior = d.iloc[-(cfg.consol_window + 1) : -1]
    last = d.iloc[-1]
    prev = d.iloc[-2]

    R = float(prior["close"].max())
    # touches: prior closes within tol of R
    tol = R * cfg.touch_tol_pct
    touches = int((prior["close"] >= R - tol).sum())
    # days since last close above R before yesterday
    above_before = d.iloc[: -1][d.iloc[: -1]["close"] > R + tol]
    if len(above_before) == 0:
        age_bars = len(d) - 1
    else:
        age_bars = int(len(d) - 1 - d.index.get_loc(above_before.index[-1]))

    vol_sma = float(d["volume"].iloc[-(cfg.vol_sma + 1) : -1].mean())
    vol = float(last["volume"])
    vol_ratio = (vol / vol_sma) if vol_sma > 0 else 0.0

    close = float(last["close"])
    open_ = float(last["open"])
    high = float(last["high"])
    low = float(last["low"])
    rng = high - low if high > low else 1e-9
    upper_third = close >= (low + 2.0 / 3.0 * rng)
    body = abs(close - open_)

    atr_s = _atr(d, cfg.atr_length)
    atr_v = float(atr_s.iloc[-1]) if pd.notna(atr_s.iloc[-1]) else None

    consol_low = float(prior["close"].min())
    range_height = R - consol_low

    # wick pierce then close back
    wick_above = high > R and close < R
    close_break = close >= R
    # failed: yesterday closed above, today back below — or today wick above close below
    failed = bool(wick_above) or (float(prev["close"]) >= R and close < R and vol_ratio < cfg.vol_confirm_ratio)

    near = (R - close) / R <= cfg.near_r_pct and close < R

    signal = "NONE"
    if failed and (wick_above or close < R):
        if wick_above or (float(prev["high"]) > R and close < R):
            signal = "FAILED_BREAKOUT"
    if close_break and touches >= 1:
        if vol_ratio >= cfg.vol_confirm_ratio and upper_third:
            signal = "BREAKOUT_CONFIRMED"
        elif vol_ratio >= cfg.vol_min_ratio:
            signal = "BREAKOUT_CONFIRMED" if upper_third or vol_ratio >= cfg.vol_confirm_ratio else "WATCH"
        else:
            signal = "WATCH"  # close above R but weak volume
    elif near and touches >= cfg.min_touches:
        signal = "WATCH"

    # entry/stop/target only when confirmed (or watch with levels as plan)
    entry = close if signal == "BREAKOUT_CONFIRMED" else None
    stop = None
    target = None
    risk_r = None
    if signal in ("BREAKOUT_CONFIRMED", "WATCH") and atr_v and atr_v > 0:
        e = close if signal == "BREAKOUT_CONFIRMED" else R  # plan entry at R for WATCH
        struct_stop = min(low, consol_low) if signal == "BREAKOUT_CONFIRMED" else consol_low
        atr_stop = e - cfg.sl_atr_mult * atr_v
        stop = max(struct_stop, atr_stop) if signal == "BREAKOUT_CONFIRMED" else atr_stop
        # prefer stop below R for confirmed
        if signal == "BREAKOUT_CONFIRMED":
            stop = min(float(stop), R - 0.01 * R, low)
        risk = e - stop if stop and e > stop else None
        if risk and risk > 0:
            target_r = e + cfg.tp_r_mult * risk
            target_mm = R + range_height if range_height > 0 else target_r
            target = min(target_r, target_mm) if range_height > 0 else target_r
            risk_r = cfg.tp_r_mult
            entry = e

    out.update(
        {
            "asOfBar": str(d.index[-1]),
            "question": f"Close vs resistance R={R:.4f} — status-quo change?",
            "structure": {
                "type": "horiz_close_resistance",
                "resistance_R": round(R, 4),
                "how_measured": f"max close of prior {cfg.consol_window} daily bars",
                "touches_near_R": touches,
                "bars_since_close_above_R": age_bars,
                "consol_low": round(consol_low, 4),
                "range_height": round(range_height, 4),
            },
            "signal": signal,
            "volume": {
                "breakout_vol": vol,
                "avg_vol": round(vol_sma, 2),
                "ratio": round(vol_ratio, 3),
                "note": "need >= avg; prefer >= 1.5x for conviction",
            },
            "bar": {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "upper_third_close": upper_third,
                "body": round(body, 4),
            },
            "levels": {
                "entry": round(entry, 4) if entry else None,
                "stop": round(stop, 4) if stop else None,
                "target": round(target, 4) if target else None,
                "atr": round(atr_v, 4) if atr_v else None,
                "risk_R_plan": risk_r,
                "price_source": "yahoo_daily",
            },
            "invalidation": f"Daily close back below R={R:.4f}",
            "patience_note": "Only trade ripe inflection; green candle alone is NONE",
            "do_not_place": True,
        }
    )
    return out

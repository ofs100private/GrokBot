"""RSI four-level zone signals for Classic (confirmed bars only, long-only remap).

Zones (defaults):
  Over Buy 79.90 | Resistance 67.90 | Support 34.90 | Over Sold 19.90

State machine: one fire per zone visit; reset when RSI leaves that zone.
Strength labels 80 (extreme touch) / 70 (zone + strong candle) are rule tags,
NOT measured win rates.

Confirmed bars only: drop the last (forming) bar unless confirmed=True is passed
with already-closed series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RSILevels:
    over_buy: float = 79.90
    resistance: float = 67.90
    support: float = 34.90
    over_sold: float = 19.90
    length: int = 14


@dataclass(frozen=True)
class StrongCandleConfig:
    body_sma_lookback: int = 20
    body_mult: float = 1.2


ZONE_OVER_BUY = "OVER_BUY"
ZONE_RESISTANCE = "RESISTANCE"
ZONE_SUPPORT = "SUPPORT"
ZONE_OVER_SOLD = "OVER_SOLD"
ZONE_NEUTRAL = "NEUTRAL"

TAG_EXTREME_80 = "EXTREME_80"
TAG_ZONE_70 = "ZONE_70"

RAW_SELL_80 = "SELL_80"
RAW_SELL_70 = "SELL_70"
RAW_BUY_80 = "BUY_80"
RAW_BUY_70 = "BUY_70"


def compute_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder RSI on close."""
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss == 0 and avg_gain > 0 → RSI 100
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi


def _body(df: pd.DataFrame) -> pd.Series:
    return (df["close"].astype(float) - df["open"].astype(float)).abs()


def strong_candle_mask(
    df: pd.DataFrame, cfg: Optional[StrongCandleConfig] = None
) -> pd.Series:
    cfg = cfg or StrongCandleConfig()
    body = _body(df)
    sma = body.rolling(cfg.body_sma_lookback, min_periods=cfg.body_sma_lookback).mean()
    return body >= (cfg.body_mult * sma)


def zone_of(rsi: float, levels: RSILevels) -> str:
    if not np.isfinite(rsi):
        return ZONE_NEUTRAL
    if rsi >= levels.over_buy:
        return ZONE_OVER_BUY
    if rsi >= levels.resistance:
        return ZONE_RESISTANCE
    if rsi <= levels.over_sold:
        return ZONE_OVER_SOLD
    if rsi <= levels.support:
        return ZONE_SUPPORT
    return ZONE_NEUTRAL


def zone_labels(levels: Optional[RSILevels] = None) -> dict[str, float]:
    levels = levels or RSILevels()
    return {
        "over_buy": levels.over_buy,
        "resistance": levels.resistance,
        "support": levels.support,
        "over_sold": levels.over_sold,
        "rsi_length": levels.length,
    }


def long_only_remap(raw_signal: Optional[str]) -> dict[str, Any]:
    """Map raw Buy/Sell triangles to Classic actions (never short).

    Buy → candidate long timing
    Sell → RISK_OFF only (no short, no add/chase)
    """
    if not raw_signal:
        return {
            "raw": None,
            "action": "NONE",
            "side": None,
            "strength_tag": None,
            "note": None,
        }
    raw = raw_signal.upper()
    if raw == RAW_BUY_80:
        return {
            "raw": raw,
            "action": "CANDIDATE_LONG",
            "side": "BUY",
            "strength_tag": TAG_EXTREME_80,
            "note": "Over Sold touch — candidate long entry/add timing after mandate gates",
        }
    if raw == RAW_BUY_70:
        return {
            "raw": raw,
            "action": "CANDIDATE_LONG",
            "side": "BUY",
            "strength_tag": TAG_ZONE_70,
            "note": "Support + strong bullish candle — weaker long timing",
        }
    if raw == RAW_SELL_80:
        return {
            "raw": raw,
            "action": "RISK_OFF",
            "side": None,
            "strength_tag": TAG_EXTREME_80,
            "note": "Over Buy touch — risk-off only: no short, prefer no new adds / skip chase",
        }
    if raw == RAW_SELL_70:
        return {
            "raw": raw,
            "action": "RISK_OFF",
            "side": None,
            "strength_tag": TAG_ZONE_70,
            "note": "Resistance + strong bearish — pause adds / no chase (not a short)",
        }
    return {
        "raw": raw,
        "action": "NONE",
        "side": None,
        "strength_tag": None,
        "note": f"Unrecognized raw signal {raw}",
    }


def _ensure_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for need in ("open", "high", "low", "close"):
        if need in df.columns:
            continue
        if need in cols:
            rename[cols[need]] = need
        else:
            raise KeyError(f"OHLC frame missing column {need}")
    out = df.rename(columns=rename) if rename else df.copy()
    return out


def drop_forming_bar(df: pd.DataFrame, confirmed_only: bool = True) -> pd.DataFrame:
    """Exclude the last (still-forming) bar for automation."""
    if not confirmed_only or len(df) == 0:
        return df
    return df.iloc[:-1].copy()


def compute_signals(
    df: pd.DataFrame,
    levels: Optional[RSILevels] = None,
    strong_cfg: Optional[StrongCandleConfig] = None,
    confirmed_only: bool = True,
) -> pd.DataFrame:
    """Compute RSI zones + raw signals on confirmed bars.

    Returns DataFrame indexed like input (minus forming bar if confirmed_only)
    with columns: rsi, zone, strong, strong_bull, strong_bear, raw_signal,
    action, side, strength_tag, remap_note.
    """
    levels = levels or RSILevels()
    strong_cfg = strong_cfg or StrongCandleConfig()
    base = _ensure_ohlc(df)
    if confirmed_only:
        base = drop_forming_bar(base, confirmed_only=True)

    out = base.copy()
    out["rsi"] = compute_rsi(out["close"], length=levels.length)
    strong = strong_candle_mask(out, strong_cfg)
    body_signed = out["close"].astype(float) - out["open"].astype(float)
    out["strong"] = strong.fillna(False)
    out["strong_bull"] = (out["strong"] & (body_signed > 0)).fillna(False)
    out["strong_bear"] = (out["strong"] & (body_signed < 0)).fillna(False)

    zones = []
    raw_signals = []
    # State: which extreme/zone visits have already fired
    fired = {
        ZONE_OVER_BUY: False,
        ZONE_RESISTANCE: False,
        ZONE_SUPPORT: False,
        ZONE_OVER_SOLD: False,
    }
    prev_zone = ZONE_NEUTRAL

    for i in range(len(out)):
        r = out["rsi"].iloc[i]
        z = zone_of(float(r) if pd.notna(r) else float("nan"), levels)
        zones.append(z)

        # Reset fired flags when leaving a zone
        for zname in list(fired.keys()):
            if prev_zone == zname and z != zname:
                fired[zname] = False

        raw = None
        if pd.notna(r):
            # Extreme touches (80) — fire once per visit on entry into extreme
            if z == ZONE_OVER_SOLD and not fired[ZONE_OVER_SOLD]:
                raw = RAW_BUY_80
                fired[ZONE_OVER_SOLD] = True
            elif z == ZONE_OVER_BUY and not fired[ZONE_OVER_BUY]:
                raw = RAW_SELL_80
                fired[ZONE_OVER_BUY] = True
            # Zone + strong candle (70) — one fire per visit; may wait for candle
            elif z == ZONE_SUPPORT and not fired[ZONE_SUPPORT]:
                if bool(out["strong_bull"].iloc[i]):
                    raw = RAW_BUY_70
                    fired[ZONE_SUPPORT] = True
            elif z == ZONE_RESISTANCE and not fired[ZONE_RESISTANCE]:
                if bool(out["strong_bear"].iloc[i]):
                    raw = RAW_SELL_70
                    fired[ZONE_RESISTANCE] = True

        raw_signals.append(raw)
        prev_zone = z

    out["zone"] = zones
    out["raw_signal"] = raw_signals

    actions, sides, tags, notes = [], [], [], []
    for raw in raw_signals:
        m = long_only_remap(raw)
        actions.append(m["action"])
        sides.append(m["side"])
        tags.append(m["strength_tag"])
        notes.append(m["note"])
    out["action"] = actions
    out["side"] = sides
    out["strength_tag"] = tags
    out["remap_note"] = notes
    return out


def latest_signals(sig_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Non-NONE rows as dicts (for propose / logging)."""
    rows = []
    if sig_df is None or len(sig_df) == 0:
        return rows
    active = sig_df[sig_df["action"].isin(["CANDIDATE_LONG", "RISK_OFF"])]
    for ts, row in active.iterrows():
        rows.append(
            {
                "bar_time": str(ts),
                "close": float(row["close"]),
                "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else None,
                "zone": row["zone"],
                "raw_signal": row["raw_signal"],
                "action": row["action"],
                "side": row["side"],
                "strength_tag": row["strength_tag"],
                "note": row["remap_note"],
            }
        )
    return rows

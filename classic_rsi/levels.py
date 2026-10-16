"""ATR-based equity SL/TP for Classic (never FX pips).

Defaults (long-only, 1H ATR(14)):
  SL = entry - 1.5 * ATR
  TP = entry + 2.0 * ATR
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any  # noqa: F401
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LevelsConfig:
    atr_length: int = 14
    sl_mult: float = 1.5
    tp_mult: float = 2.0


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Wilder ATR on OHLC columns high/low/close."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder / RMA smoothing
    return tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def atr_long_levels(
    entry: float,
    atr_value: float,
    cfg: Optional[LevelsConfig] = None,
) -> dict[str, float]:
    """Return entry / stop / take for a long using ATR multiples (price units)."""
    cfg = cfg or LevelsConfig()
    if entry <= 0 or atr_value is None or not np.isfinite(atr_value) or atr_value <= 0:
        raise ValueError("entry and atr_value must be positive finite numbers")
    sl = float(entry - cfg.sl_mult * atr_value)
    tp = float(entry + cfg.tp_mult * atr_value)
    if sl <= 0:
        # Floor stop just above zero for penny edge cases; caller should skip
        sl = max(sl, entry * 0.01)
    risk = entry - sl
    reward = tp - entry
    r_multiple = (reward / risk) if risk > 0 else float("nan")
    return {
        "entry": float(entry),
        "stop_loss": sl,
        "take_profit": tp,
        "atr": float(atr_value),
        "sl_mult": float(cfg.sl_mult),
        "tp_mult": float(cfg.tp_mult),
        "risk_per_share": float(risk),
        "reward_per_share": float(reward),
        "r_multiple": float(r_multiple),
        "units": "price",  # never pips
    }


# Crypto majors SL rule (QA 2026-10-16): SL distance = max(2.5 x ATR(1H), 4% of entry), capped at
# 20% of entry; TP distance = 1.5 x SL distance (reward:risk 1.5 >= MIN_REWARD_RISK 1.25). The cost
# gate (expected gain >= 2x round-trip cost, crypto spread floor 1%/side) still has to pass.
CRYPTO_SL_ATR_MULT = 2.5
CRYPTO_SL_MIN_PCT = 0.04
CRYPTO_SL_MAX_PCT = 0.20
CRYPTO_TP_R = 1.5


def crypto_sl_distance(entry: float, atr_value: float) -> float:
    return min(max(CRYPTO_SL_ATR_MULT * atr_value, CRYPTO_SL_MIN_PCT * entry), CRYPTO_SL_MAX_PCT * entry)


def crypto_long_levels(entry: float, atr_value: float) -> dict[str, Any]:
    if entry <= 0 or atr_value is None or not np.isfinite(atr_value) or atr_value <= 0:
        raise ValueError("entry and atr_value must be positive finite numbers")
    d = crypto_sl_distance(entry, atr_value)
    sl, tp = entry - d, entry + CRYPTO_TP_R * d
    return {"entry": float(entry), "stop_loss": float(sl), "take_profit": float(tp), "atr": float(atr_value),
            "sl_rule": "crypto: max(2.5*ATR1h, 4%) capped 20%; TP = 1.5R", "asset_class": "crypto",
            "risk_per_share": float(d), "reward_per_share": float(CRYPTO_TP_R * d), "r_multiple": CRYPTO_TP_R,
            "units": "price"}


def levels_from_bar(
    row: Mapping[str, Any],
    entry_col: str = "close",
    atr_col: str = "atr",
    cfg: Optional[LevelsConfig] = None,
) -> dict[str, float]:
    """Build ATR long levels from a confirmed bar row."""
    return atr_long_levels(float(row[entry_col]), float(row[atr_col]), cfg=cfg)


def levels_to_dict(levels: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-safe copy of a levels mapping."""
    out: dict[str, Any] = {}
    for k, v in levels.items():
        if isinstance(v, (np.floating, float)):
            out[k] = float(v)
        elif isinstance(v, (np.integer, int)):
            out[k] = int(v)
        else:
            out[k] = v
    return out


def attach_atr(df: pd.DataFrame, cfg: Optional[LevelsConfig] = None) -> pd.DataFrame:
    """Return copy with atr column."""
    cfg = cfg or LevelsConfig()
    out = df.copy()
    out["atr"] = atr(out, length=cfg.atr_length)
    return out

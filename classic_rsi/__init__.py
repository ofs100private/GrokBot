"""Classic RSI four-level entries for OfersClaw5-PRIYN (long-only, 1H).

Timing overlay only. Does not place trades. Mandate gates (Fear, cash floor,
weekend, ×1, no crypto, QA PASS) remain with Trader_Classic.
"""

from .audit import append_audit, attach_run_id_to_packs, new_run_id
from .levels import LevelsConfig, atr, atr_long_levels, levels_to_dict
from .signals import (
    RSILevels,
    StrongCandleConfig,
    compute_rsi,
    compute_signals,
    long_only_remap,
    zone_labels,
)
from .universe import (
    MIN_ADV_USD,
    MIN_PRICE,
    RISING_MULT,
    TOP_N,
    build_screened_universe,
    screen_universe,
)

__all__ = [
    "MIN_ADV_USD",
    "MIN_PRICE",
    "RISING_MULT",
    "TOP_N",
    "append_audit",
    "attach_run_id_to_packs",
    "build_screened_universe",
    "new_run_id",
    "LevelsConfig",
    "RSILevels",
    "StrongCandleConfig",
    "atr",
    "atr_long_levels",
    "compute_rsi",
    "compute_signals",
    "levels_to_dict",
    "long_only_remap",
    "screen_universe",
    "zone_labels",
]

__version__ = "1.1.0"

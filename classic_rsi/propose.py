"""Propose Classic RSI candidate BUY packs + RISK_OFF notes (never shorts).

Trader_Classic flow:
  1. propose.propose_from_symbols([...])  → packs / risk_off
  2. Hand BUY packs to classic-real-money-order-qa-gate (QA Bot)
  3. Place ONLY after QA PASS + mandate gates (Fear, cash ≥~$2.5k, weekend, ×1, no crypto)
  4. This module never places and never SendToUser
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from .backtest import DEFAULT_SYMBOLS, fetch_1h, _normalize_ohlc
from .levels import LevelsConfig, atr, atr_long_levels, levels_to_dict
from .audit import append_audit, attach_run_id_to_packs, new_run_id
from .signals import RSILevels, StrongCandleConfig, compute_signals, long_only_remap

IDT = ZoneInfo("Asia/Jerusalem")
TIMEFRAME = "1H"
PORTFOLIO = "OfersClaw5-PRIYN"
MIRROR_ID = 11368142
QA_GATE = "classic-real-money-order-qa-gate"


def _bars_from_frame(df: pd.DataFrame) -> pd.DataFrame:
    return _normalize_ohlc(df)


def propose_from_bars(
    symbol: str,
    df: pd.DataFrame,
    *,
    levels: Optional[RSILevels] = None,
    strong_cfg: Optional[StrongCandleConfig] = None,
    lvl_cfg: Optional[LevelsConfig] = None,
    lookback_signals: int = 5,
    suggested_notional_usd: Optional[float] = None,
) -> dict[str, Any]:
    """Emit latest CANDIDATE_LONG pack(s) and RISK_OFF notes for one symbol.

    Uses confirmed bars only. Never emits shorts.
    """
    levels = levels or RSILevels()
    strong_cfg = strong_cfg or StrongCandleConfig()
    lvl_cfg = lvl_cfg or LevelsConfig()

    ohlc = _bars_from_frame(df)
    sig = compute_signals(ohlc, levels=levels, strong_cfg=strong_cfg, confirmed_only=True)
    if sig.empty:
        return {
            "symbol": symbol,
            "timeframe": TIMEFRAME,
            "buy_packs": [],
            "risk_off": [],
            "error": "no_confirmed_bars",
        }

    sig = sig.copy()
    sig["atr"] = atr(sig, length=lvl_cfg.atr_length)

    buys: list[dict[str, Any]] = []
    risk_off: list[dict[str, Any]] = []

    # Consider recent fired signals (last N non-NONE), but pack "live" only if last bar is a buy
    active = sig[sig["action"].isin(["CANDIDATE_LONG", "RISK_OFF"])].tail(lookback_signals)

    last = sig.iloc[-1]
    last_ts = str(sig.index[-1])

    if last["action"] == "CANDIDATE_LONG":
        atr_v = last["atr"]
        if pd.notna(atr_v) and float(atr_v) > 0:
            lv = atr_long_levels(float(last["close"]), float(atr_v), cfg=lvl_cfg)
            pack = _buy_pack(
                symbol=symbol,
                bar_time=last_ts,
                row=last,
                levels=lv,
                suggested_notional_usd=suggested_notional_usd,
            )
            buys.append(pack)

    if last["action"] == "RISK_OFF":
        risk_off.append(_risk_off_note(symbol, last_ts, last))

    # Historical recent for audit (not actionable unless last bar)
    recent = []
    for ts, row in active.iterrows():
        recent.append(
            {
                "bar_time": str(ts),
                "action": row["action"],
                "raw_signal": row["raw_signal"],
                "strength_tag": row["strength_tag"],
                "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else None,
                "zone": row["zone"],
                "close": float(row["close"]),
                "is_latest_bar": str(ts) == last_ts,
            }
        )

    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "confirmed_only": True,
        "last_bar_time": last_ts,
        "last_close": float(last["close"]),
        "last_rsi": float(last["rsi"]) if pd.notna(last["rsi"]) else None,
        "last_zone": last["zone"],
        "buy_packs": buys,
        "risk_off": risk_off,
        "recent_signals": recent,
        "qa_gate": QA_GATE,
        "place": False,
        "notes": [
            "Never emit shorts; Sell tags → RISK_OFF only.",
            "Trader_Classic must still clear Fear/cash/weekend/×1/no-crypto before QA.",
            "QA Bot must PASS before any place.",
        ],
    }


def _buy_pack(
    symbol: str,
    bar_time: str,
    row: pd.Series,
    levels: dict[str, float],
    suggested_notional_usd: Optional[float],
) -> dict[str, Any]:
    """classic-real-money-order-qa-gate style candidate pack (pre-prepare)."""
    remap = long_only_remap(row["raw_signal"])
    thesis = (
        f"Classic RSI four-level {remap['strength_tag']} on {TIMEFRAME} confirmed bar: "
        f"{remap['note']}. ATR SL/TP (not pips). Timing overlay only."
    )
    pack: dict[str, Any] = {
        "gate": QA_GATE,
        "portfolio": PORTFOLIO,
        "mirrorId": MIRROR_ID,
        "route": "REAL",
        "side": "buy",
        "action": "CANDIDATE_LONG",
        "instrument": {"symbol": symbol, "assetClass": "equity_or_etf"},
        "leverage": 1,
        "timeframe": TIMEFRAME,
        "bar_confirmed": True,
        "bar_time": bar_time,
        "rsi_rule": {
            "raw_signal": row["raw_signal"],
            "strength_tag": row["strength_tag"],
            "zone": row["zone"],
            "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else None,
            "label_note": "80/70 are rule labels, not win rates",
        },
        "levels": levels_to_dict(levels),
        "sizing": {
            "suggested_notional_usd": suggested_notional_usd,
            "note": "Trader_Classic sets size; cash floor ≥~$2.5k after fill; ×1 only",
        },
        "thesis": thesis,
        "mandate_reminders": [
            "long-only ×1",
            "no crypto",
            "cash floor ≥ ~$2.5k after add",
            "weekend: no new opens unless Ofer overrides",
            "Fear / regime gates unchanged — still apply",
            "QA PASS required before place",
        ],
        "fee_estimate": None,  # fill via getCost / prepare before QA
        "overnight_financing_estimate": None,
        "prepared_order": None,
        "status": "PROPOSE_ONLY",
        "do_not_place": True,
    }
    return pack


def _risk_off_note(symbol: str, bar_time: str, row: pd.Series) -> dict[str, Any]:
    remap = long_only_remap(row["raw_signal"])
    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "bar_time": bar_time,
        "action": "RISK_OFF",
        "raw_signal": row["raw_signal"],
        "strength_tag": row["strength_tag"],
        "zone": row["zone"],
        "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else None,
        "close": float(row["close"]),
        "note": remap["note"],
        "never_short": True,
        "suggested": "no new adds / skip chase on this name; optional tighten trail on existing long",
    }


def propose_from_symbols(
    symbols: Optional[list[str]] = None,
    *,
    period: str = "60d",
    bars_by_symbol: Optional[dict[str, pd.DataFrame]] = None,
    levels: Optional[RSILevels] = None,
    strong_cfg: Optional[StrongCandleConfig] = None,
    lvl_cfg: Optional[LevelsConfig] = None,
    suggested_notional_usd: Optional[float] = None,
) -> dict[str, Any]:
    """Batch propose for a symbol list (Yahoo 1H or caller-supplied frames)."""
    symbols = symbols or list(DEFAULT_SYMBOLS)
    levels = levels or RSILevels()
    strong_cfg = strong_cfg or StrongCandleConfig()
    lvl_cfg = lvl_cfg or LevelsConfig()

    results = []
    buy_packs = []
    risk_off = []
    for sym in symbols:
        try:
            if bars_by_symbol and sym in bars_by_symbol:
                df = bars_by_symbol[sym]
            else:
                df = fetch_1h(sym, period=period)
            one = propose_from_bars(
                sym,
                df,
                levels=levels,
                strong_cfg=strong_cfg,
                lvl_cfg=lvl_cfg,
                suggested_notional_usd=suggested_notional_usd,
            )
        except Exception as exc:  # noqa: BLE001
            one = {
                "symbol": sym,
                "timeframe": TIMEFRAME,
                "buy_packs": [],
                "risk_off": [],
                "error": str(exc),
            }
        results.append(one)
        buy_packs.extend(one.get("buy_packs") or [])
        risk_off.extend(one.get("risk_off") or [])

    now = datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")
    rid = new_run_id("propose")
    params = {
        "rsi_levels": levels,
        "strong_candle": strong_cfg,
        "atr_levels": lvl_cfg,
        "period": period,
        "symbols": list(symbols),
        "suggested_notional_usd": suggested_notional_usd,
        "confirmed_only": True,
    }
    payload = {
        "asOfIDT": now,
        "portfolio": PORTFOLIO,
        "mirrorId": MIRROR_ID,
        "timeframe": TIMEFRAME,
        "long_only": True,
        "qa_gate": QA_GATE,
        "do_not_place": True,
        "symbols": list(symbols),
        "invocation": {
            "next": [
                "Attach fee_estimate + overnight_financing_estimate via prepare/getCost",
                "Set size respecting cash floor ≥~$2.5k and sleeve caps",
                "Submit each buy_pack to QA Bot (classic-real-money-order-qa-gate) citing run_id",
                "Place only after QA PASS + mandate gates clear",
            ],
            "never": [
                "Do not short from RISK_OFF / Sell triangles",
                "Do not bypass QA",
                "Do not use FX pip SL/TP",
                "Do not touch Momentum from this module",
            ],
        },
        "buy_packs": buy_packs,
        "risk_off": risk_off,
        "per_symbol": results,
    }
    payload = attach_run_id_to_packs(payload, rid)
    meta = append_audit("propose", payload, run_id=rid, params=params)
    payload["audit"] = meta
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Propose Classic RSI 1H packs (no place)")
    p.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    p.add_argument("--period", default="60d")
    p.add_argument("--out", default="")
    p.add_argument("--notional", type=float, default=None)
    args = p.parse_args(argv)
    payload = propose_from_symbols(
        symbols=list(args.symbols),
        period=args.period,
        suggested_notional_usd=args.notional,
    )
    text = json.dumps(payload, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    print(
        f"TF={TIMEFRAME} buy_packs={len(payload['buy_packs'])} "
        f"risk_off={len(payload['risk_off'])} (do_not_place=True)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

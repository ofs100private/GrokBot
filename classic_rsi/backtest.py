"""1H RSI four-level long-only backtest for Classic universe (Yahoo).

TF = 1H only. ATR SL/TP. Confirmed bars. No shorts.
Does not place live orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .levels import LevelsConfig, atr, atr_long_levels
from .signals import RSILevels, StrongCandleConfig, compute_signals
from .audit import append_audit, new_run_id

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "QQQ", "SMH", "XLV", "JNJ"]
TIMEFRAME = "1H"
IDT = ZoneInfo("Asia/Jerusalem")


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    # yfinance MultiIndex columns sometimes
    if isinstance(df.columns, pd.MultiIndex):
        out.columns = [str(c[0]).lower() for c in df.columns]
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in out.columns]
    out = out[keep].dropna(subset=["open", "high", "low", "close"])
    out.index = pd.to_datetime(out.index, utc=True)
    out = out.sort_index()
    return out


def fetch_1h(symbol: str, period: str = "60d") -> pd.DataFrame:
    """Fetch 1H bars from Yahoo via yfinance. period max ~60d for 1h."""
    import yfinance as yf

    t = yf.Ticker(symbol)
    # interval 1h; Yahoo caps history for intraday
    raw = t.history(period=period, interval="1h", auto_adjust=True)
    return _normalize_ohlc(raw)


def _simulate_symbol(
    symbol: str,
    df: pd.DataFrame,
    levels: RSILevels,
    strong_cfg: StrongCandleConfig,
    lvl_cfg: LevelsConfig,
    risk_pct: float = 0.01,
    initial_equity: float = 10_000.0,
) -> dict[str, Any]:
    if df is None or len(df) < 80:
        return {
            "symbol": symbol,
            "error": "insufficient_bars",
            "bars": 0 if df is None else len(df),
            "trades": [],
            "metrics": {},
        }

    sig = compute_signals(df, levels=levels, strong_cfg=strong_cfg, confirmed_only=True)
    sig = sig.copy()
    sig["atr"] = atr(sig, length=lvl_cfg.atr_length)

    trades: list[dict[str, Any]] = []
    equity = initial_equity
    equity_curve = [equity]
    position: Optional[dict[str, Any]] = None

    for i in range(len(sig)):
        row = sig.iloc[i]
        ts = sig.index[i]
        hi = float(row["high"])
        lo = float(row["low"])
        cl = float(row["close"])

        # Manage open long: SL/TP hit intrabar (conservative: SL first if both)
        if position is not None:
            hit_sl = lo <= position["stop_loss"]
            hit_tp = hi >= position["take_profit"]
            exit_px = None
            exit_reason = None
            if hit_sl and hit_tp:
                exit_px = position["stop_loss"]
                exit_reason = "SL_AND_TP_SAME_BAR_SL_FIRST"
            elif hit_sl:
                exit_px = position["stop_loss"]
                exit_reason = "SL"
            elif hit_tp:
                exit_px = position["take_profit"]
                exit_reason = "TP"
            # Optional: risk-off extreme can flatten early at close
            elif row["action"] == "RISK_OFF" and row["strength_tag"] == "EXTREME_80":
                exit_px = cl
                exit_reason = "RISK_OFF_EXTREME"

            if exit_px is not None:
                pnl = (exit_px - position["entry"]) * position["shares"]
                equity += pnl
                trades.append(
                    {
                        **{k: position[k] for k in (
                            "symbol", "entry_time", "entry", "stop_loss",
                            "take_profit", "atr", "shares", "strength_tag", "raw_signal",
                        )},
                        "exit_time": str(ts),
                        "exit": float(exit_px),
                        "exit_reason": exit_reason,
                        "pnl": float(pnl),
                        "return_pct": float(pnl / (position["entry"] * position["shares"]) * 100.0)
                        if position["shares"]
                        else 0.0,
                        "r_result": float(
                            (exit_px - position["entry"]) / position["risk_per_share"]
                        )
                        if position["risk_per_share"] > 0
                        else float("nan"),
                    }
                )
                position = None

        equity_curve.append(equity)

        # New entries only when flat; CANDIDATE_LONG on confirmed bar
        if position is None and row["action"] == "CANDIDATE_LONG":
            atr_v = row["atr"]
            if pd.isna(atr_v) or float(atr_v) <= 0:
                continue
            try:
                lv = atr_long_levels(cl, float(atr_v), cfg=lvl_cfg)
            except ValueError:
                continue
            risk_budget = equity * risk_pct
            rps = lv["risk_per_share"]
            if rps <= 0:
                continue
            shares = risk_budget / rps
            if shares <= 0:
                continue
            position = {
                "symbol": symbol,
                "entry_time": str(ts),
                "entry": lv["entry"],
                "stop_loss": lv["stop_loss"],
                "take_profit": lv["take_profit"],
                "atr": lv["atr"],
                "risk_per_share": lv["risk_per_share"],
                "shares": float(shares),
                "strength_tag": row["strength_tag"],
                "raw_signal": row["raw_signal"],
            }

    # Force close at last bar if still open
    if position is not None:
        last_ts = sig.index[-1]
        last_cl = float(sig["close"].iloc[-1])
        pnl = (last_cl - position["entry"]) * position["shares"]
        equity += pnl
        trades.append(
            {
                **{k: position[k] for k in (
                    "symbol", "entry_time", "entry", "stop_loss",
                    "take_profit", "atr", "shares", "strength_tag", "raw_signal",
                )},
                "exit_time": str(last_ts),
                "exit": last_cl,
                "exit_reason": "EOD_FORCE",
                "pnl": float(pnl),
                "return_pct": float(pnl / (position["entry"] * position["shares"]) * 100.0)
                if position["shares"]
                else 0.0,
                "r_result": float(
                    (last_cl - position["entry"]) / position["risk_per_share"]
                )
                if position["risk_per_share"] > 0
                else float("nan"),
            }
        )
        equity_curve.append(equity)

    metrics = _metrics(trades, equity_curve, initial_equity)
    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "bars": int(len(sig)),
        "bar_start": str(sig.index[0]) if len(sig) else None,
        "bar_end": str(sig.index[-1]) if len(sig) else None,
        "trades": trades,
        "metrics": metrics,
        "final_equity": float(equity),
    }


def _metrics(
    trades: list[dict[str, Any]], equity_curve: list[float], initial_equity: float
) -> dict[str, Any]:
    n = len(trades)
    if n == 0:
        return {
            "n_trades": 0,
            "win_rate": None,
            "expectancy_pnl": None,
            "expectancy_R": None,
            "avg_pnl": None,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": None,
        }
    pnls = np.array([t["pnl"] for t in trades], dtype=float)
    rs = np.array([t["r_result"] for t in trades], dtype=float)
    wins = pnls > 0
    win_rate = float(wins.mean())
    avg_pnl = float(pnls.mean())
    avg_r = float(np.nanmean(rs))
    gross_win = float(pnls[wins].sum()) if wins.any() else 0.0
    gross_loss = float((-pnls[~wins]).sum()) if (~wins).any() else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (None if gross_win == 0 else float("inf"))

    eq = np.array(equity_curve, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / np.where(peak == 0, np.nan, peak)
    max_dd = float(np.nanmin(dd) * 100.0) if len(dd) else 0.0

    return {
        "n_trades": n,
        "wins": int(wins.sum()),
        "losses": int((~wins).sum()),
        "win_rate": win_rate,
        "expectancy_pnl": avg_pnl,
        "expectancy_R": avg_r,
        "avg_pnl": avg_pnl,
        "total_pnl": float(pnls.sum()),
        "max_drawdown_pct": max_dd,
        "profit_factor": pf if pf != float("inf") else None,
        "profit_factor_inf": pf == float("inf"),
        "return_pct": float((eq[-1] / initial_equity - 1.0) * 100.0) if len(eq) else 0.0,
    }


def run_backtest(
    symbols: Optional[list[str]] = None,
    period: str = "60d",
    levels: Optional[RSILevels] = None,
    strong_cfg: Optional[StrongCandleConfig] = None,
    lvl_cfg: Optional[LevelsConfig] = None,
    initial_equity: float = 10_000.0,
    risk_pct: float = 0.01,
) -> dict[str, Any]:
    symbols = symbols or list(DEFAULT_SYMBOLS)
    levels = levels or RSILevels()
    strong_cfg = strong_cfg or StrongCandleConfig()
    lvl_cfg = lvl_cfg or LevelsConfig()

    per_symbol = []
    all_trades: list[dict[str, Any]] = []
    for sym in symbols:
        try:
            df = fetch_1h(sym, period=period)
            result = _simulate_symbol(
                sym, df, levels, strong_cfg, lvl_cfg, risk_pct, initial_equity
            )
        except Exception as exc:  # noqa: BLE001 — smoke must continue
            result = {
                "symbol": sym,
                "error": str(exc),
                "trades": [],
                "metrics": {},
                "timeframe": TIMEFRAME,
            }
        per_symbol.append(result)
        all_trades.extend(result.get("trades") or [])

    # Aggregate metrics across symbols (equal start equity each — report combined trades)
    # Rebuild a simple combined equity path by summing per-symbol final / using all trades
    combined_curve = [initial_equity * len(symbols)]
    # Approximate combined DD from concatenating trade PnLs in time order
    timed = sorted(all_trades, key=lambda t: t.get("exit_time") or "")
    eq = initial_equity * max(len(symbols), 1)
    curve = [eq]
    for t in timed:
        eq += t["pnl"]
        curve.append(eq)
    agg = _metrics(timed, curve, initial_equity * max(len(symbols), 1))

    now_idt = datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")
    return {
        "strategy": "classic_rsi_four_level",
        "portfolio": "OfersClaw5-PRIYN",
        "timeframe": TIMEFRAME,
        "confirmed_bars_only": True,
        "long_only": True,
        "period": period,
        "symbols": symbols,
        "levels": {
            "over_buy": levels.over_buy,
            "resistance": levels.resistance,
            "support": levels.support,
            "over_sold": levels.over_sold,
            "rsi_length": levels.length,
        },
        "atr": {
            "length": lvl_cfg.atr_length,
            "sl_mult": lvl_cfg.sl_mult,
            "tp_mult": lvl_cfg.tp_mult,
            "units": "price_not_pips",
        },
        "strong_candle": {
            "body_sma_lookback": strong_cfg.body_sma_lookback,
            "body_mult": strong_cfg.body_mult,
        },
        "risk_pct_per_trade": risk_pct,
        "initial_equity_per_symbol": initial_equity,
        "asOfIDT": now_idt,
        "per_symbol": [
            {
                "symbol": r["symbol"],
                "timeframe": TIMEFRAME,
                "bars": r.get("bars"),
                "bar_start": r.get("bar_start"),
                "bar_end": r.get("bar_end"),
                "error": r.get("error"),
                "n_trades": r.get("metrics", {}).get("n_trades", 0),
                "metrics": r.get("metrics", {}),
                "final_equity": r.get("final_equity"),
            }
            for r in per_symbol
        ],
        "aggregate": agg,
        "trades": timed,
        "notes": [
            "TF=1H only (same as live Classic RSI timing).",
            "Sell triangles remapped to RISK_OFF (no shorts).",
            "Mandate gates (Fear/cash/weekend) NOT simulated here.",
            "Strength tags 80/70 are rule labels, not win rates.",
        ],
    }


def save_summary(result: dict[str, Any], path: Path) -> None:
    # Slim trades for summary file (keep headline + per_symbol + trade count)
    slim_trades = [
        {
            "symbol": t["symbol"],
            "entry_time": t["entry_time"],
            "exit_time": t["exit_time"],
            "entry": t["entry"],
            "exit": t["exit"],
            "pnl": t["pnl"],
            "r_result": t["r_result"],
            "exit_reason": t["exit_reason"],
            "strength_tag": t["strength_tag"],
            "raw_signal": t["raw_signal"],
        }
        for t in result.get("trades", [])
    ]
    payload = {**result, "trades": slim_trades}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Classic RSI 1H backtest smoke")
    p.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    p.add_argument("--period", default="60d")
    p.add_argument(
        "--out",
        default="/workspace/classic_rsi/backtest-summary-1h.json",
    )
    args = p.parse_args(argv)
    result = run_backtest(symbols=list(args.symbols), period=args.period)
    out = Path(args.out)
    save_summary(result, out)
    rid = new_run_id("backtest")
    result = {**result, "run_id": rid}
    params = {
        "symbols": list(args.symbols),
        "period": args.period,
        "timeframe": result.get("timeframe"),
        "levels": result.get("levels"),
        "atr": result.get("atr"),
        "strong_candle": result.get("strong_candle"),
        "risk_pct_per_trade": result.get("risk_pct_per_trade"),
        "initial_equity_per_symbol": result.get("initial_equity_per_symbol"),
    }
    meta = append_audit("backtest", result, run_id=rid, params=params)
    # rewrite summary with run_id
    save_summary(result, out)
    agg = result["aggregate"]
    print(f"TF={result['timeframe']} symbols={result['symbols']} run_id={rid}")
    print(
        f"trades={agg.get('n_trades')} win_rate={agg.get('win_rate')} "
        f"expectancy_R={agg.get('expectancy_R')} maxDD%={agg.get('max_drawdown_pct')}"
    )
    print(f"wrote {out}")
    print(f"audit {meta['path']}")
    return 0


if __name__ == "__main__":
    # Allow `python -m classic_rsi.backtest` from /workspace
    sys.exit(main())

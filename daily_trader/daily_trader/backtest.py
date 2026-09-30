"""Same-day leveraged breakout backtest for Daily Trader (no place).

Daily-bar proxy of same-session trading:
  - BREAKOUT day → enter (open or close per --entry-mode)
  - SL/TP checked intrabar (SL first if both)
  - Stocks/commodities: force flat at same-bar close if still open
  - Crypto: may hold overnight until SL/TP

Writes JSON + short markdown under /workspace/daily_trader/audit/
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import (
    DEFAULT_EQUITY,
    DEFAULT_RISK_PCT,
    __agent_id__,
    __version__,
)
from .scan import LOOKBACK_BARS, atr_series, fetch_daily, score_breakout
from .universe import allows_overnight, classify, clamp_leverage, default_leverage, is_etf

IDT = ZoneInfo("Asia/Jerusalem")
PKG_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = PKG_ROOT / "audit"

SL_ATR_MULT = 1.25
TP_R = 2.5
ENTRY_MODE_DEFAULT = "close"


def _now_idt_str() -> str:
    return datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _metrics(trades: list[dict[str, Any]], equity_curve: list[float], equity0: float) -> dict[str, Any]:
    if not trades:
        return {
            "n_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "avg_r": None,
            "expectancy_r": None,
            "total_pnl_margin": 0.0,
            "avg_pnl_margin": 0.0,
            "max_drawdown_pct": 0.0,
            "final_equity": equity0,
            "return_pct": 0.0,
        }
    pnls = [float(t["pnl_margin"]) for t in trades]
    rs = [float(t["r_result"]) for t in trades if t.get("r_result") is not None]
    wins = sum(1 for p in pnls if p > 0)
    n = len(pnls)
    win_rate = wins / n
    avg_r = float(np.mean(rs)) if rs else None
    total_pnl = float(sum(pnls))

    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak)

    final_eq = equity_curve[-1] if equity_curve else equity0
    return {
        "n_trades": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": round(win_rate, 4),
        "avg_r": round(avg_r, 4) if avg_r is not None else None,
        "expectancy_r": round(avg_r, 4) if avg_r is not None else None,
        "total_pnl_margin": round(total_pnl, 2),
        "avg_pnl_margin": round(total_pnl / n, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 3),
        "final_equity": round(final_eq, 2),
        "return_pct": round((final_eq / equity0 - 1.0) * 100.0, 3) if equity0 else 0.0,
    }


def _close_position(
    position: dict[str, Any],
    exit_px: float,
    exit_time: str,
    exit_reason: str,
    symbol: str,
    cls: str,
) -> dict[str, Any]:
    move_pct = (exit_px - position["entry"]) / position["entry"]
    pnl_on_margin = position["margin"] * move_pct * position["leverage"]
    r_result = (
        (exit_px - position["entry"]) / position["risk_per_unit"]
        if position["risk_per_unit"] > 0
        else float("nan")
    )
    return {
        "symbol": symbol,
        "asset_class": cls,
        "entry_time": position["entry_time"],
        "exit_time": exit_time,
        "entry": position["entry"],
        "exit": float(exit_px),
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "leverage": position["leverage"],
        "margin": position["margin"],
        "notional": position["notional"],
        "units": position["units"],
        "exit_reason": exit_reason,
        "pnl_margin": float(pnl_on_margin),
        "pnl_notional": float((exit_px - position["entry"]) * position["units"]),
        "r_result": float(r_result) if r_result == r_result else None,
        "return_on_margin_pct": float(move_pct * position["leverage"] * 100.0),
    }


def _size_position(equity: float, risk_pct: float, entry: float, sl: float, lev: int) -> dict[str, float]:
    risk_per_unit = entry - sl
    if risk_per_unit <= 0 or entry <= 0:
        return {"units": 0.0, "notional": 0.0, "margin": 0.0, "risk_per_unit": 0.0}
    risk_budget = equity * risk_pct
    units = risk_budget / risk_per_unit
    notional = units * entry
    margin = notional / lev
    if margin > equity * 0.4:
        margin = equity * 0.4
        notional = margin * lev
        units = notional / entry
    return {
        "units": float(units),
        "notional": float(notional),
        "margin": float(margin),
        "risk_per_unit": float(risk_per_unit),
    }


def _simulate_symbol(
    symbol: str,
    df: pd.DataFrame,
    equity0: float = DEFAULT_EQUITY,
    risk_pct: float = DEFAULT_RISK_PCT,
    entry_mode: str = ENTRY_MODE_DEFAULT,
    lev_override: Optional[int] = None,
) -> dict[str, Any]:
    cls = classify(symbol)
    if is_etf(symbol) or cls == "etf":
        return {"symbol": symbol, "error": "ETF_REJECT", "trades": [], "metrics": {}}
    if df is None or len(df) < LOOKBACK_BARS + 20:
        return {
            "symbol": symbol,
            "error": "insufficient_bars",
            "bars": 0 if df is None else len(df),
            "trades": [],
            "metrics": {},
        }

    d = df.copy()
    d["atr"] = atr_series(d)
    overnight_ok = allows_overnight(symbol)
    lev = clamp_leverage(symbol, lev_override or default_leverage(symbol))

    trades: list[dict[str, Any]] = []
    equity = float(equity0)
    equity_curve = [equity]
    position: Optional[dict[str, Any]] = None

    for i in range(LOOKBACK_BARS + 15, len(d)):
        row = d.iloc[i]
        ts = d.index[i]
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        atr_v = float(row["atr"]) if not pd.isna(row["atr"]) else 0.0
        window = d.iloc[: i + 1]

        # --- manage open (crypto overnight carry) ---
        if position is not None:
            hit_sl = l <= position["stop_loss"]
            hit_tp = h >= position["take_profit"]
            closed = None
            if hit_sl and hit_tp:
                closed = _close_position(position, position["stop_loss"], str(ts), "SL_AND_TP_SAME_BAR_SL_FIRST", symbol, cls)
            elif hit_sl:
                closed = _close_position(position, position["stop_loss"], str(ts), "SL", symbol, cls)
            elif hit_tp:
                closed = _close_position(position, position["take_profit"], str(ts), "TP", symbol, cls)
            elif not overnight_ok:
                closed = _close_position(position, c, str(ts), "FORCE_FLAT_EOD", symbol, cls)

            if closed is not None:
                equity += closed["pnl_margin"]
                trades.append(closed)
                position = None

        equity_curve.append(equity)

        if position is not None:
            continue

        # --- signal on this bar ---
        scored = score_breakout(symbol, window)
        if scored.get("signal") != "BREAKOUT" or atr_v <= 0:
            continue

        if entry_mode == "open":
            entry = o
            # SL structure from bar low; ATR from entry
            struct_sl = l
        else:
            # close entry: use signal levels; same-bar SL after close is N/A —
            # for non-crypto we still model intrabar path via open-entry extremes
            # when entry_mode=close on daily: treat as enter near breakout, exit EOD
            entry = c
            struct_sl = l

        atr_sl = entry - SL_ATR_MULT * atr_v
        sl = float(min(struct_sl, atr_sl))
        if sl >= entry:
            sl = entry * 0.98
        tp = entry + TP_R * (entry - sl)
        sized = _size_position(equity, risk_pct, entry, sl, lev)
        if sized["units"] <= 0 or sized["margin"] <= 0:
            continue

        # Same-bar resolution for day trades
        if entry_mode == "open" or not overnight_ok:
            # Intrabar vs SL/TP from entry; for close-entry use bar extremes as proxy
            hit_sl = l <= sl
            hit_tp = h >= tp
            if entry_mode == "close":
                # Entered at close → cannot hit SL/TP after; EOD = entry (scratch) for same-day mandate
                # Better proxy: assume breakout triggered intraday → entry≈open or mid, EOD=close
                entry_px = o  # assume traded the breakout day from open once signal conditions met
                atr_sl2 = entry_px - SL_ATR_MULT * atr_v
                sl2 = float(min(l, atr_sl2)) if l < entry_px else float(min(entry_px * 0.98, atr_sl2))
                if sl2 >= entry_px:
                    sl2 = entry_px * 0.98
                tp2 = entry_px + TP_R * (entry_px - sl2)
                sized = _size_position(equity, risk_pct, entry_px, sl2, lev)
                if sized["units"] <= 0:
                    continue
                hit_sl = l <= sl2
                hit_tp = h >= tp2
                if hit_sl and hit_tp:
                    closed = _close_position(
                        {
                            "entry_time": str(ts),
                            "entry": entry_px,
                            "stop_loss": sl2,
                            "take_profit": tp2,
                            **sized,
                            "leverage": lev,
                        },
                        sl2,
                        str(ts),
                        "SL_AND_TP_SAME_BAR_SL_FIRST",
                        symbol,
                        cls,
                    )
                elif hit_sl:
                    closed = _close_position(
                        {
                            "entry_time": str(ts),
                            "entry": entry_px,
                            "stop_loss": sl2,
                            "take_profit": tp2,
                            **sized,
                            "leverage": lev,
                        },
                        sl2,
                        str(ts),
                        "SL",
                        symbol,
                        cls,
                    )
                elif hit_tp:
                    closed = _close_position(
                        {
                            "entry_time": str(ts),
                            "entry": entry_px,
                            "stop_loss": sl2,
                            "take_profit": tp2,
                            **sized,
                            "leverage": lev,
                        },
                        tp2,
                        str(ts),
                        "TP",
                        symbol,
                        cls,
                    )
                else:
                    closed = _close_position(
                        {
                            "entry_time": str(ts),
                            "entry": entry_px,
                            "stop_loss": sl2,
                            "take_profit": tp2,
                            **sized,
                            "leverage": lev,
                        },
                        c,
                        str(ts),
                        "FORCE_FLAT_EOD",
                        symbol,
                        cls,
                    )
                equity += closed["pnl_margin"]
                trades.append(closed)
                equity_curve.append(equity)
                continue

            # entry_mode == open path
            pos = {
                "entry_time": str(ts),
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                **sized,
                "leverage": lev,
            }
            if hit_sl and hit_tp:
                closed = _close_position(pos, sl, str(ts), "SL_AND_TP_SAME_BAR_SL_FIRST", symbol, cls)
            elif hit_sl:
                closed = _close_position(pos, sl, str(ts), "SL", symbol, cls)
            elif hit_tp:
                closed = _close_position(pos, tp, str(ts), "TP", symbol, cls)
            else:
                closed = _close_position(pos, c, str(ts), "FORCE_FLAT_EOD", symbol, cls)
            equity += closed["pnl_margin"]
            trades.append(closed)
            equity_curve.append(equity)
            continue

        # Crypto overnight: open position at close, manage on future bars
        position = {
            "entry_time": str(ts),
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
            **sized,
            "leverage": lev,
        }

    if position is not None:
        last = d.iloc[-1]
        closed = _close_position(
            position,
            float(last["close"]),
            str(d.index[-1]),
            "END_OF_DATA",
            symbol,
            cls,
        )
        equity += closed["pnl_margin"]
        trades.append(closed)
        equity_curve.append(equity)

    metrics = _metrics(trades, equity_curve, equity0)
    return {
        "symbol": symbol,
        "asset_class": cls,
        "leverage": lev,
        "allows_overnight": overnight_ok,
        "bars": len(d),
        "n_trades": len(trades),
        "trades": trades,
        "metrics": metrics,
        "final_equity": equity,
    }


def run_backtest(
    symbols: list[str],
    period: str = "6mo",
    equity: float = DEFAULT_EQUITY,
    risk_pct: float = DEFAULT_RISK_PCT,
    entry_mode: str = ENTRY_MODE_DEFAULT,
    use_cache: bool = True,
) -> dict[str, Any]:
    syms = [s for s in symbols if not is_etf(s)]
    frames = fetch_daily(syms, period=period, use_cache=use_cache)
    per_symbol: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []

    for sym in syms:
        df = frames.get(sym)
        res = _simulate_symbol(sym, df, equity0=equity, risk_pct=risk_pct, entry_mode=entry_mode)
        summary = {k: res[k] for k in res if k != "trades"}
        summary["trades_sample"] = (res.get("trades") or [])[:3]
        per_symbol.append(summary)
        all_trades.extend(res.get("trades") or [])

    all_trades_sorted = sorted(all_trades, key=lambda t: str(t.get("exit_time") or ""))
    eq = float(equity)
    curve = [eq]
    for t in all_trades_sorted:
        eq += float(t.get("pnl_margin") or 0.0)
        curve.append(eq)
    agg = _metrics(all_trades_sorted, curve, equity)

    run_id = f"daily-trader-bt-{datetime.now(IDT).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "run_id": run_id,
        "bot": "Daily Trader",
        "agent_id": __agent_id__,
        "tooling_version": __version__,
        "asOfIDT": _now_idt_str(),
        "asOfUTC": _now_utc_iso(),
        "do_not_place": True,
        "params": {
            "symbols": syms,
            "period": period,
            "equity": equity,
            "risk_pct": risk_pct,
            "entry_mode": entry_mode,
            "sl_atr_mult": SL_ATR_MULT,
            "tp_r": TP_R,
            "force_flat_non_crypto": True,
        },
        "aggregate": agg,
        "per_symbol": per_symbol,
        "trades": all_trades_sorted,
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = AUDIT_DIR / "latest-backtest.json"
    md_path = AUDIT_DIR / "latest-backtest.md"
    text = json.dumps(payload, indent=2, default=str) + "\n"
    json_path.write_text(text)
    (AUDIT_DIR / f"{run_id}.json").write_text(text)
    md_path.write_text(_markdown_summary(payload))
    with (AUDIT_DIR / "backtest-index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "run_id": run_id,
                    "asOfIDT": payload["asOfIDT"],
                    "n_trades": agg.get("n_trades"),
                    "win_rate": agg.get("win_rate"),
                    "avg_r": agg.get("avg_r"),
                    "max_dd_pct": agg.get("max_drawdown_pct"),
                    "path": str(json_path),
                }
            )
            + "\n"
        )
    payload["_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    return payload


def _markdown_summary(payload: dict[str, Any]) -> str:
    agg = payload.get("aggregate") or {}
    params = payload.get("params") or {}
    lines = [
        "# Daily Trader backtest summary",
        "",
        f"- **asOf:** {payload.get('asOfIDT')}",
        f"- **run_id:** `{payload.get('run_id')}`",
        f"- **symbols:** {', '.join(params.get('symbols') or [])}",
        f"- **period:** {params.get('period')} | equity ${params.get('equity')} | risk {params.get('risk_pct')}",
        f"- **entry:** {params.get('entry_mode')} | TP={params.get('tp_r')}R | SL ATR×{params.get('sl_atr_mult')}",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Trades | {agg.get('n_trades')} |",
        f"| Win rate | {agg.get('win_rate')} |",
        f"| Avg R | {agg.get('avg_r')} |",
        f"| Expectancy R | {agg.get('expectancy_r')} |",
        f"| Total P&L (margin) | ${agg.get('total_pnl_margin')} |",
        f"| Max DD | {agg.get('max_drawdown_pct')}% |",
        f"| Final equity | ${agg.get('final_equity')} |",
        f"| Return | {agg.get('return_pct')}% |",
        "",
        "## Per symbol",
        "",
    ]
    for s in payload.get("per_symbol") or []:
        m = s.get("metrics") or {}
        lines.append(
            f"- **{s.get('symbol')}** ({s.get('asset_class')}, x{s.get('leverage')}): "
            f"n={m.get('n_trades')} win={m.get('win_rate')} avgR={m.get('avg_r')} "
            f"pnl=${m.get('total_pnl_margin')} DD={m.get('max_drawdown_pct')}%"
        )
    lines += ["", "_Tooling only — do not place from this file._", ""]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Daily Trader same-day leveraged backtest (no place)")
    p.add_argument(
        "--symbols",
        nargs="*",
        default=["AAPL", "NVDA", "TSLA", "BTC-USD", "ETH-USD", "CL=F", "GC=F"],
    )
    p.add_argument("--period", default="6mo")
    p.add_argument("--equity", type=float, default=DEFAULT_EQUITY)
    p.add_argument("--risk-pct", type=float, default=DEFAULT_RISK_PCT)
    p.add_argument("--entry-mode", choices=["close", "open"], default=ENTRY_MODE_DEFAULT)
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args(argv)

    payload = run_backtest(
        symbols=args.symbols,
        period=args.period,
        equity=args.equity,
        risk_pct=args.risk_pct,
        entry_mode=args.entry_mode,
        use_cache=not args.no_cache,
    )
    agg = payload["aggregate"]
    print(
        f"[Daily Trader backtest] {payload['asOfIDT']} | trades={agg.get('n_trades')} "
        f"win={agg.get('win_rate')} avgR={agg.get('avg_r')} "
        f"pnl=${agg.get('total_pnl_margin')} maxDD={agg.get('max_drawdown_pct')}% "
        f"→ {payload['_paths']['json']}"
    )
    print(f"  markdown: {payload['_paths']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Automated daily breakout scan (analysis only).

Universe: Classic book + Momentum book + default liquid names.
Writes audit + latest.json. Never places.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from .analyze import AnalyzeConfig, analyze_symbol

IDT = ZoneInfo("Asia/Jerusalem")
AUDIT_DIR = Path("/workspace/breakout_ta/audit")
LATEST = AUDIT_DIR / "latest-auto.json"
DEFAULT_EXTRA = ["AAPL", "MSFT", "NVDA", "INTC", "AMD", "META", "GOOGL", "AMZN", "JNJ", "QQQ", "SMH", "XLV", "SPY"]


def _load_symbols_from_portfolio(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        d = json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return []
    syms = []
    for p in d.get("positions") or []:
        s = p.get("symbol")
        if s:
            syms.append(str(s).upper())
    # momentum sidecar uses summary.symbols
    for s in (d.get("summary") or {}).get("symbols") or []:
        syms.append(str(s).upper())
    return syms


def build_universe(extra: Optional[list[str]] = None) -> list[str]:
    syms: list[str] = []
    syms += _load_symbols_from_portfolio(Path("/workspace/classic-portfolio-for-app.json"))
    syms += _load_symbols_from_portfolio(Path("/workspace/etoroview/public/classic-portfolio.json"))
    syms += _load_symbols_from_portfolio(Path("/workspace/etoroview/public/momentum-portfolio.json"))
    syms += list(DEFAULT_EXTRA)
    if extra:
        syms += [s.upper() for s in extra]
    out, seen = [], set()
    for s in syms:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def fetch_daily(symbol: str, period: str = "6mo") -> Any:
    t = yf.Ticker(symbol)
    raw = t.history(period=period, interval="1d", auto_adjust=True)
    return raw


def new_run_id() -> str:
    stamp = datetime.now(IDT).strftime("%Y%m%d-%H%M%S")
    return f"breakout-auto-{stamp}-{uuid.uuid4().hex[:8]}"


def append_audit(record: dict[str, Any], run_id: str) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"{run_id}.json"
    text = json.dumps(record, indent=2, default=str) + "\n"
    path.write_text(text)
    LATEST.write_text(text)
    (AUDIT_DIR / "latest.json").write_text(text)
    line = {
        "run_id": run_id,
        "asOfIDT": record.get("asOfIDT"),
        "path": str(path),
        "n_symbols": len(record.get("symbols") or []),
        "confirmed": len(record.get("confirmed") or []),
        "watch": len(record.get("watch") or []),
        "failed": len(record.get("failed") or []),
    }
    with (AUDIT_DIR / "index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, default=str) + "\n")
    return path




APP_FEED_NAME = "breakout-ta.json"
APP_ROOTS = [
    Path("/workspace/etoroview/public"),
    Path("/workspace/etoroview/dist"),
    Path("/workspace/GrokBot/app/etoroview/public"),
    Path("/workspace/GrokBot/app/etoroview/dist"),
]


def build_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare Breakout TA vs Classic RSI vs Momentum breakout sleeve (methods, not live PnL)."""
    confirmed = {r["symbol"] for r in payload.get("confirmed") or []}
    watch = {r["symbol"] for r in payload.get("watch") or []}

    classic_syms = set(_load_symbols_from_portfolio(Path("/workspace/etoroview/public/classic-portfolio.json")))
    if not classic_syms:
        classic_syms = set(_load_symbols_from_portfolio(Path("/workspace/classic-portfolio-for-app.json")))
    mom_syms = set(_load_symbols_from_portfolio(Path("/workspace/etoroview/public/momentum-portfolio.json")))

    # Classic RSI latest auto if present
    classic_rsi_buy, classic_rsi_riskoff = set(), set()
    cr_path = Path("/workspace/classic_rsi/audit/latest-auto.json")
    if cr_path.exists():
        try:
            cr = json.loads(cr_path.read_text())
            for p in cr.get("buy_packs") or []:
                s = (p.get("instrument") or {}).get("symbol") or p.get("symbol")
                if s:
                    classic_rsi_buy.add(str(s).upper())
            for p in cr.get("risk_off") or []:
                s = p.get("symbol")
                if s:
                    classic_rsi_riskoff.add(str(s).upper())
        except Exception:  # noqa: BLE001
            pass

    return {
        "methods": [
            {
                "id": "breakout_ta",
                "name": "Breakout TA (inflection)",
                "timeframe": "1D",
                "core": "Close above resistance R + volume; entry/stop/target",
                "place": False,
                "tonight_confirmed": sorted(confirmed),
                "tonight_watch": sorted(watch),
            },
            {
                "id": "classic_rsi",
                "name": "Classic RSI four-level 1H",
                "timeframe": "1H",
                "core": "RSI zones + strong candle; ATR SL/TP; Sell=risk-off; QA before place",
                "place": "after QA PASS (not FULL AUTO)",
                "book_symbols": sorted(classic_syms),
                "latest_rsi_buy_packs": sorted(classic_rsi_buy),
                "latest_rsi_risk_off": sorted(classic_rsi_riskoff),
            },
            {
                "id": "momentum_breakout",
                "name": "Momentum EOD breakout sleeve",
                "timeframe": "1D EOD",
                "core": "RS/RVOL/new 20d high; FULL AUTO after QA PASS",
                "place": "FULL AUTO after QA",
                "book_symbols": sorted(mom_syms),
            },
        ],
        "overlap": {
            "breakout_confirmed_in_classic_book": sorted(confirmed & classic_syms),
            "breakout_confirmed_in_momentum_book": sorted(confirmed & mom_syms),
            "breakout_watch_in_classic_book": sorted(watch & classic_syms),
            "breakout_watch_in_momentum_book": sorted(watch & mom_syms),
            "classic_rsi_buy_also_breakout_confirmed": sorted(classic_rsi_buy & confirmed),
            "classic_rsi_buy_also_breakout_watch": sorted(classic_rsi_buy & watch),
        },
        "diff_notes": [
            "Breakout TA is analysis-only (no place).",
            "Classic times with 1H RSI; Breakout TA uses daily close inflection.",
            "Momentum buys via EOD screener rules (RVOL/RS); Breakout TA does not replace that pack.",
            "Agreement on a symbol does not authorize a place without the book QA gate.",
        ],
    }


def write_app_feed(payload: dict[str, Any]) -> list[str]:
    comparison = build_comparison(payload)
    feed = {
        "schemaVersion": "1.0",
        "asOf": datetime.now(IDT).isoformat(),
        "slot": "nightly_breakout_ta",
        "run_id": payload.get("run_id"),
        "timeframe": "1D",
        "doNotPlaceFromThisUi": True,
        "mandate": {
            "longOnly": True,
            "confirmedCloseOnly": True,
            "volumeRequired": True,
            "qaBeforeAnyPlace": True,
            "reminders": [
                "Nightly Breakout TA — inflection + volume",
                "This tab never places",
                "Compare vs Classic RSI 1H and Momentum EOD breakout sleeve",
            ],
        },
        "summary": {
            "confirmedCount": len(payload.get("confirmed") or []),
            "watchCount": len(payload.get("watch") or []),
            "failedCount": len(payload.get("failed") or []),
            "symbolCount": len(payload.get("symbols") or []),
        },
        "confirmed": payload.get("confirmed") or [],
        "watch": payload.get("watch") or [],
        "failed": payload.get("failed") or [],
        "comparison": comparison,
        "auditPath": payload.get("audit_path"),
        "skill": "breakout-technical-analysis",
    }
    text = json.dumps(feed, indent=2, default=str) + "\n"
    written = []
    for root in APP_ROOTS:
        root.mkdir(parents=True, exist_ok=True)
        dest = root / APP_FEED_NAME
        dest.write_text(text)
        written.append(str(dest))
    # also under breakout_ta
    local = Path("/workspace/breakout_ta") / APP_FEED_NAME
    local.write_text(text)
    written.append(str(local))
    payload["app_feed"] = written
    payload["comparison"] = comparison
    return written


def run_auto(*, symbols: Optional[list[str]] = None, period: str = "6mo") -> dict[str, Any]:
    universe = symbols or build_universe()
    rid = new_run_id()
    cfg = AnalyzeConfig()
    results = []
    for sym in universe:
        try:
            df = fetch_daily(sym, period=period)
            one = analyze_symbol(sym, df, cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            one = {"symbol": sym, "timeframe": "1D", "signal": "NONE", "error": str(exc), "do_not_place": True}
        results.append(one)

    confirmed = [r for r in results if r.get("signal") == "BREAKOUT_CONFIRMED"]
    watch = [r for r in results if r.get("signal") == "WATCH"]
    failed = [r for r in results if r.get("signal") == "FAILED_BREAKOUT"]

    payload = {
        "run_id": rid,
        "kind": "breakout_auto_daily",
        "asOfIDT": datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT"),
        "timeframe": "1D",
        "skill": "breakout-technical-analysis",
        "do_not_place": True,
        "place": False,
        "symbols": universe,
        "params": asdict_cfg(cfg),
        "confirmed": confirmed,
        "watch": watch,
        "failed": failed,
        "none_or_error_count": len(results) - len(confirmed) - len(watch) - len(failed),
        "per_symbol": results,
        "handoff": {
            "note": "Analysis only. Not wired to Classic/Momentum place. Cite run_id if promoting a name manually.",
        },
    }
    path = append_audit(payload, rid)
    payload["audit_path"] = str(path)
    write_app_feed(payload)
    return payload


def asdict_cfg(cfg: AnalyzeConfig) -> dict[str, Any]:
    return {
        "lookback": cfg.lookback,
        "consol_window": cfg.consol_window,
        "vol_sma": cfg.vol_sma,
        "vol_min_ratio": cfg.vol_min_ratio,
        "vol_confirm_ratio": cfg.vol_confirm_ratio,
        "near_r_pct": cfg.near_r_pct,
        "atr_length": cfg.atr_length,
        "sl_atr_mult": cfg.sl_atr_mult,
        "tp_r_mult": cfg.tp_r_mult,
    }


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Daily breakout auto scan (no place)")
    p.add_argument("--symbols", nargs="*", default=None)
    p.add_argument("--period", default="6mo")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    payload = run_auto(symbols=list(args.symbols) if args.symbols else None, period=args.period)
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(f"wrote {args.out}")
    print(
        f"breakout_auto run_id={payload['run_id']} "
        f"confirmed={len(payload['confirmed'])} watch={len(payload['watch'])} "
        f"failed={len(payload['failed'])} do_not_place=True"
    )
    for c in payload["confirmed"][:10]:
        lv = c.get("levels") or {}
        print(
            f"  CONFIRMED {c['symbol']} entry={lv.get('entry')} stop={lv.get('stop')} "
            f"target={lv.get('target')} vol_x={((c.get('volume') or {}).get('ratio'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

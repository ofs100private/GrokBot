"""Classic-only 1H auto runner (OfersClaw5-PRIYN).

On each fire:
  1. Session / weekend gate (no new opens on weekend unless --force)
  2. Build symbol universe via dynamic screener:
       S&P pool → liquid ADV$ → rising 1H volume (top N) ∪ live Classic book
       (never the old fixed 6-name DEFAULT_SYMBOLS as primary universe)
  3. propose_from_symbols (confirmed 1H close, ATR SL/TP, audit run_id)
  4. Soft mandate annotations (cash floor / Fear placeholder / weekend)
  5. Write auto envelope under audit/ + latest-auto.json (includes universe_meta)
  6. NEVER place — Trader_Classic → QA Bot → place only after PASS

Does not touch Momentum. Does not bypass Fear/cash/weekend gates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .audit import DEFAULT_AUDIT_DIR, append_audit, new_run_id
from .propose import propose_from_symbols
from .universe import build_screened_universe

IDT = ZoneInfo("Asia/Jerusalem")
ET = ZoneInfo("America/New_York")
PORTFOLIO = "OfersClaw5-PRIYN"
MIRROR_ID = 11368142
CASH_FLOOR_USD = 2500.0
PORTFOLIO_SNAPSHOT = Path("/workspace/classic-portfolio-for-app.json")
LATEST_AUTO = DEFAULT_AUDIT_DIR / "latest-auto.json"
QA_GATE = "classic-real-money-order-qa-gate"
RUN_QA_GATE = "classic-rsi-1h-run-qa"


def _now_idt() -> datetime:
    return datetime.now(IDT)


def _now_et() -> datetime:
    return datetime.now(ET)


def is_weekend_idt(now: Optional[datetime] = None) -> bool:
    n = now or _now_idt()
    return n.weekday() >= 5  # Sat=5 Sun=6


def is_us_rth(now_et: Optional[datetime] = None) -> bool:
    """Rough NYSE regular session Mon–Fri 09:30–16:00 America/New_York."""
    n = now_et or _now_et()
    if n.weekday() >= 5:
        return False
    minutes = n.hour * 60 + n.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


def load_book_symbols(snapshot: Path = PORTFOLIO_SNAPSHOT) -> tuple[list[str], Optional[float], Optional[dict]]:
    """Return (symbols, available_cash, summary) from Classic App snapshot if present."""
    if not snapshot.exists():
        return [], None, None
    try:
        data = json.loads(snapshot.read_text())
    except Exception:  # noqa: BLE001
        return [], None, None
    syms = []
    for p in data.get("positions") or []:
        s = p.get("symbol")
        if s and s not in syms:
            syms.append(s)
    cash = None
    summary = data.get("summary") or {}
    if "availableCash" in summary:
        try:
            cash = float(summary["availableCash"])
        except (TypeError, ValueError):
            cash = None
    return syms, cash, summary


def build_universe(
    extra: Optional[list[str]] = None,
    *,
    include_book: bool = True,
    include_defaults: bool = False,  # retained for CLI compat; ignored as primary
) -> tuple[list[str], dict[str, Any]]:
    """Dynamic universe: liquid+rising S&P screen ∪ Classic book.

    ``include_defaults`` is accepted for backward compatibility but does **not**
    inject the old fixed DEFAULT_SYMBOLS list as the primary universe.
    Returns (symbols, universe_meta).
    """
    book: list[str] = []
    if include_book:
        book, _, _ = load_book_symbols()
    # include_defaults deliberately unused as primary — see module docstring
    _ = include_defaults
    symbols, meta = build_screened_universe(book_symbols=book, extra=extra)
    return symbols, meta


def mandate_gate(
    *,
    force: bool,
    cash: Optional[float],
) -> dict[str, Any]:
    """Soft gates for the auto envelope (Trader_Classic still re-checks live)."""
    weekend = is_weekend_idt()
    rth = is_us_rth()
    blocks: list[str] = []
    if weekend and not force:
        blocks.append("weekend_no_new_opens")
    if not rth and not force and not weekend:
        blocks.append("outside_us_rth")
    if cash is not None and cash < CASH_FLOOR_USD and not force:
        blocks.append("cash_below_floor")
    return {
        "weekend": weekend,
        "us_rth": rth,
        "available_cash": cash,
        "cash_floor_usd": CASH_FLOOR_USD,
        "blocks": blocks,
        "allow_new_buys": len(blocks) == 0,
        "force": force,
        "note": "Fear / live cash / sleeve caps still enforced by Trader_Classic before QA",
    }


def run_auto_1h(
    *,
    symbols: Optional[list[str]] = None,
    period: str = "60d",
    notional: Optional[float] = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    book_syms, cash, summary = load_book_symbols()
    universe_meta: dict[str, Any]
    if symbols:
        # Manual override for tests — still record meta
        universe = [str(s).upper().strip() for s in symbols if s]
        universe_meta = {
            "override": True,
            "universe_size": len(universe),
            "note": "CLI --symbols override; screener skipped",
            "asOf": _now_idt().strftime("%Y-%m-%d %H:%M:%S IDT"),
        }
    else:
        universe, universe_meta = build_universe()

    gates = mandate_gate(force=force, cash=cash)
    rid = new_run_id("auto")

    propose_payload: Optional[dict[str, Any]] = None
    buy_packs: list[Any] = []
    risk_off: list[Any] = []
    status = "SKIPPED"

    if dry_run:
        status = "DRY_RUN"
    elif not gates["allow_new_buys"] and not force:
        status = "GATED"
        # Still scan for RISK_OFF notes on open book (useful weekend/off-hours)
        scan_syms = book_syms or universe[:3]
        propose_payload = propose_from_symbols(
            symbols=scan_syms or universe,
            period=period,
            suggested_notional_usd=notional,
        )
        risk_off = list(propose_payload.get("risk_off") or [])
        # Strip buy_packs when gated — no new opens
        buy_packs = []
        propose_payload = {
            **propose_payload,
            "buy_packs": [],
            "gated_buy_packs_suppressed": list(propose_payload.get("buy_packs") or []),
            "status": "GATED",
        }
    else:
        status = "PROPOSE"
        propose_payload = propose_from_symbols(
            symbols=universe,
            period=period,
            suggested_notional_usd=notional,
        )
        buy_packs = list(propose_payload.get("buy_packs") or [])
        risk_off = list(propose_payload.get("risk_off") or [])

    envelope: dict[str, Any] = {
        "run_id": rid,
        "kind": "auto",
        "status": status,
        "asOfIDT": _now_idt().strftime("%Y-%m-%d %H:%M:%S IDT"),
        "asOfET": _now_et().strftime("%Y-%m-%d %H:%M:%S ET"),
        "portfolio": PORTFOLIO,
        "mirrorId": MIRROR_ID,
        "timeframe": "1H",
        "confirmed_close": True,
        "long_only": True,
        "qa_gate": QA_GATE,
        "run_qa_gate": RUN_QA_GATE,
        "do_not_place": True,
        "place": False,
        "symbols": universe,
        "universe_meta": universe_meta,
        "book_symbols": book_syms,
        "book_summary": summary,
        "mandate_gates": gates,
        "buy_packs": buy_packs,
        "risk_off": risk_off,
        "propose_run_id": (propose_payload or {}).get("run_id"),
        "propose": propose_payload,
        "handoff": {
            "to": "Trader_Classic",
            "then": (
                "QA Bot (classic-rsi-1h-run-qa) then "
                "classic-real-money-order-qa-gate for packs"
            ),
            "cite": f"run_id={rid}"
            + (f" propose_run_id={(propose_payload or {}).get('run_id')}" if propose_payload else ""),
            "never": ["shorts from Sell tags", "bypass QA", "Momentum", "place from this script"],
        },
    }

    if not dry_run:
        meta = append_audit(
            "auto",
            envelope,
            run_id=rid,
            params={
                "period": period,
                "symbols": universe,
                "universe_meta": universe_meta,
                "force": force,
                "notional": notional,
                "status": status,
            },
        )
        envelope["audit"] = meta
        LATEST_AUTO.write_text(json.dumps(envelope, indent=2, default=str) + "\n")
    else:
        envelope["audit"] = {"skipped": "dry_run"}

    return envelope


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Classic RSI 1H auto (propose only, no place)")
    p.add_argument("--symbols", nargs="*", default=None, help="Override universe (skip screener)")
    p.add_argument("--period", default="60d")
    p.add_argument("--notional", type=float, default=None)
    p.add_argument("--force", action="store_true", help="Ignore weekend/RTH/cash soft gates")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)

    env = run_auto_1h(
        symbols=list(args.symbols) if args.symbols else None,
        period=args.period,
        notional=args.notional,
        force=args.force,
        dry_run=args.dry_run,
    )
    text = json.dumps(env, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        um = env.get("universe_meta") or {}
        print(
            f"auto_1h status={env['status']} run_id={env['run_id']} "
            f"syms={len(env['symbols'])} "
            f"liquid={um.get('liquid_count')} rising={um.get('rising_count')} "
            f"fallback={um.get('used_fallback')} "
            f"buys={len(env['buy_packs'])} risk_off={len(env['risk_off'])} "
            f"gates={env['mandate_gates']['blocks'] or 'clear'} do_not_place=True"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

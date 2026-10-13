"""Final pre-place GO/NO-GO for Classic FULL AUTO (RSI buy packs AND rebalance actions).

v3 (2026-10-12, QA fix2). NEVER calls eToro, NEVER places. Trader_Classic places through the
user-OfersClaw5 MCP only on GO: it calls prepare-trade / prepare-close with `order_payloads`
VERBATIM (sells first), and place-trade / place-close with the token of the prepare whose
response execute_pass verified.

Fixed paths (see classic_rsi/paths.py; NOT overridable in production):
  envelopes   /workspace/classic_rsi/audit/<auto_run_id>.json
  run-QA      /workspace/classic_rsi/audit/qa/qa-verdict-run-<auto_run_id>.json
  order-QA    /workspace/classic_rsi/audit/qa/qa-verdict-order-<pack_sha256[:16]>.json
  locks       /workspace/classic_rsi/audit/placed/
  live book   /workspace/classic-portfolio-for-app.json   (asOf <= 60 s; cash, equity, positions)
  scores      /workspace/classic-rebalance/scores-latest.json

Flow (RSI):
  1. plan     : --bid/--ask/--quote-ts/--mark (live read)  -> pinned payload, anchor = this ask
  2. prepare  : agent calls prepare-trade with the payload; re-run with --prepare-response and
                --anchor-ask/--anchor-bid from step 1 -> ready_for_order_qa + pack_sha256
  3. order-QA : QA Bot writes qa-verdict-order-<sha16>.json with checker "QA Bot", skill, checked_at,
                pack_sha256, qa_ask (= anchor ask) and recomputed_cost_gate {spread, fees, tax_est,
                total_cost, expected_gain, ratio} matching the ANCHOR gate within +/-0.01
  4. GO       : agent re-prepares the same payload (fresh token/quote); re-run with the fresh
                --prepare-response and the same anchors: fresh ask within 0.1% of qa_ask,
                live cost gate recomputed and PASS, all checks -> GO + locks
Rebalance: --rebalance-pack pack.json (static, hashed) + --live live.json (quotes/marks/prepare
responses per leg, same order). No auto-shrink: anything that would change units is NO-GO.

Residual risk (documented for Ofer): on this shared box any agent can write files, including a
verdict file in audit/qa/ that claims checker "QA Bot", the book snapshot, or the score file.
The code cannot authenticate the writer; it binds verdicts to the exact pack/payload/anchor and
QA-recomputed numbers, but a fully forged QA verdict remains possible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from . import cost_gate as CG
from .instruments import guard_symbol, resolve
from .market_hours import ET, us_session
from .paths import order_verdict_path, paths, run_verdict_path
from . import momentum_holdings as MH

IDT = ZoneInfo("Asia/Jerusalem")
VERSION = "execute-pass-v11-fix8b"
CASH_FLOOR_USD = 2500.0
MIN_POSITION_USD = 400.0
NAME_CAP = {"etf": 0.30, "stock": 0.15}
SLEEVE_CAP = 0.45
RISK_EXIT_BUFFER_EQUITY_PCT = 0.01  # fix5: sized risk exits overshoot the floor/cap by 1% of equity
SIZED_RISK_EXITS = ("cash_below_floor", "hard_cap_breach")  # full close only via the <$400 residual rule
UNIT_STEP = 1e-6
# fix6: GO accepts pack units in [required_now, RISK_EXIT_SIZE_BAND * max(required_at_qa, required_now)]
RISK_EXIT_SIZE_BAND = 1.02
RISK_EXIT_PLAN_HEADROOM = 1.01  # planners size packs at ceil(1.01 * required) so small adverse drift stays >= required_now
RISK_EXIT_QA_REQ_MAX_RATIO = 1.05  # a pack-declared required_at_qa above 1.05x required_now is clamped
# fix7 (Ofer 2026-10-12 17:56 IDT): caps are measured against TOTAL EQUITY (holdings + cash).
# Market-value basis: book equity; cost basis: sum of cost + cash. "invested" (fix1-fix6 basis) kept
# only as a selectable fallback for tests.
CAP_DENOMINATOR = "equity"
EQUITY_RECONCILE_TOL = 0.005  # fix7b: |equity - (holdings value + cash)| <= 0.5% of equity
DRIFT_ATR_MULT = 0.5
UNITS_DP = 6
BOOK_MAX_AGE_S = 60
RUN_QA_MAX_AGE_S = 60 * 60
ORDER_QA_MAX_AGE_S = 15 * 60
ANCHOR_TOL = 0.001
VERDICT_TOL = 0.01
QA_CHECKER = "QA Bot"
RUN_QA_SKILL = "classic-rsi-1h-run-qa"
ORDER_QA_SKILL = "classic-real-money-order-qa-gate"
RECOMPUTED_FIELDS = ("spread", "fees", "tax_est", "total_cost", "expected_gain", "ratio")
REALIZED_TOL_USD = 1.0
RECENT_POSITION_H = 24
BOOK_ONLY_RISK_EXITS = ("cash_below_floor", "stop_hit", "hard_cap_breach")
SCORES_MAX_TRADING_DAYS = 0  # enforced in scorer.verify_scores_file (sidecar sha + schema + age)
SL_ATR_BOUNDS = (1.0, 3.5)
TRAIL_BOUNDS = {"etf": (0.075, 0.085), "stock": (0.10, 0.12)}  # fraction below ask (ETF 8% +/-0.5pp)
RSI_PACK_ID_RE = re.compile(r"^(classic-rsi-auto-\d{8}-\d{6}-[0-9a-f]{8})#([A-Z][A-Z.]{0,9})$")
REBAL_PACK_ID_RE = re.compile(r"^classic-rebalance-\d{8}-[a-z0-9][a-z0-9-]{0,80}$")

DEFAULT_SLEEVES = {
    "QQQ": "growth_tech", "SMH": "growth_tech", "XLK": "growth_tech", "XLC": "growth_tech",
    "XLV": "healthcare", "TMO": "healthcare",
    "SPY": "broad_core", "RSP": "broad_core", "DIA": "broad_core",
    "XLE": "energy_hard_assets", "GLD": "energy_hard_assets", "IAU": "energy_hard_assets",
    "SLV": "energy_hard_assets", "XLB": "energy_hard_assets",
    "XLF": "industrials_financials", "XLI": "industrials_financials",
    "T": "communication_defensive", "VZ": "communication_defensive",
    "XLP": "defensive", "XLU": "defensive", "XLY": "consumer",
}


def cap_denominator(vals: dict[str, float], cash: Optional[float] = None, equity: Optional[float] = None) -> float:
    """Single source of the cap denominator for name/sleeve caps (value or cost basis).

    equity mode: `equity` when given (market-value basis: the book's equity), else sum(vals) + cash
    (cost basis: cost of holdings + cash)."""
    inv = sum(vals.values())
    if CAP_DENOMINATOR == "invested":
        return inv
    if CAP_DENOMINATOR == "equity":
        return float(equity) if equity is not None else inv + float(cash or 0.0)
    raise ValueError(f"unknown CAP_DENOMINATOR {CAP_DENOMINATOR!r}")


def _basis_equity(book: dict, basis: str) -> Optional[float]:
    """Book equity for the market-value basis (None => cost basis uses cost + cash)."""
    return _f(book.get("equity")) if basis == "values" else None


def _floor_units(x: float) -> float:
    q = 10 ** UNITS_DP
    return math.floor(max(x, 0.0) * q) / q


_f = CG._f


def _age_s(ts: Any, now: datetime) -> Optional[float]:
    t = CG._parse_ts(str(ts).split(" ")[0] if isinstance(ts, str) else ts)
    return None if t is None else (now - t).total_seconds()


def canonical_sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def et_date(now: datetime) -> str:
    return now.astimezone(ET).date().isoformat()


# ---------------------------------------------------------------- loaders
def load_pack(run_id: str, symbol: str) -> tuple[Optional[dict], dict]:
    path = Path(paths()["audit_dir"]) / f"{run_id}.json"
    ctx: dict[str, Any] = {"audit_path": str(path)}
    if not path.exists():
        ctx["error"] = "audit file missing"
        return None, ctx
    rec = json.loads(path.read_text())
    body = rec.get("payload") or rec
    ctx["envelope_run_id"] = rec.get("run_id")
    ctx["propose_run_id"] = body.get("propose_run_id")
    if rec.get("run_id") != run_id:
        ctx["error"] = "envelope run_id does not match file name"
        return None, ctx
    for p in body.get("buy_packs") or []:
        if ((p.get("instrument") or {}).get("symbol") or "").upper() == symbol:
            return p, ctx
    ctx["error"] = f"no buy pack for {symbol} in {run_id}"
    return None, ctx


def load_book(now: datetime) -> dict[str, Any]:
    bp = Path(paths()["book"])
    if not bp.exists():
        return {"ok": False, "error": f"book missing: {bp}"}
    d = json.loads(bp.read_text())
    summ = d.get("summary") or {}
    cash = _f(summ.get("availableCash", d.get("availableCash", d.get("cash"))))
    equity = _f(d.get("equity", summ.get("totalValue", d.get("totalValue"))))
    vals: dict[str, float] = {}
    cost: dict[str, float] = {}
    cost_missing = []
    for p in d.get("positions") or []:
        s = str(p.get("symbol")).upper()
        vals[s] = vals.get(s, 0.0) + float(p.get("value") or 0.0)
        if p.get("invested") is None:
            cost_missing.append(s)
        cost[s] = cost.get(s, 0.0) + float(p.get("invested") or 0.0)
    return {"ok": True, "path": str(bp), "asOf": d.get("asOf"), "age_s": _age_s(d.get("asOf"), now),
            "cash": cash, "equity": equity, "values": vals, "cost": cost,
            "positions": d.get("positions") or [], "cost_missing": cost_missing}


def load_scores(now: datetime) -> dict[str, Any]:
    """Score file: matching sidecar scores-latest.sha256, typed/ranged rows, units fraction, age 0 sessions (fix4)."""
    from .scorer import verify_scores_file
    v = verify_scores_file(Path(paths()["scores"]), now)
    return {k: v.get(k) for k in ("ok", "error", "data", "path", "sidecar", "sha256", "asOf_bars",
                                  "last_completed_session", "age_trading_days")}


# ---------------------------------------------------------------- prepare responses
_PR_KEYS = {
    "verdict": ("verdict",), "account": ("account",), "instrumentId": ("instrumentId",),
    "direction": ("direction",), "orderType": ("orderType",), "leverage": ("leverage",),
    "units": ("units", "estimatedUnits"), "stopLossRate": ("stopLossRate",),
    "takeProfitRate": ("takeProfitRate",), "ask": ("ask",), "bid": ("bid",),
    "quoteAsOf": ("quoteAsOf", "quoteTime", "asOf"), "positionId": ("positionId",),
    "unitsToDeduct": ("unitsToDeduct",), "minStopLossRate": ("minStopLossRate",),
    "maxStopLossRate": ("maxStopLossRate",),
}


def _strip_tokens(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _strip_tokens(v) for k, v in o.items() if "token" not in k.lower()}
    if isinstance(o, list):
        return [_strip_tokens(v) for v in o]
    return o


def norm_prepare(pr: Any) -> dict[str, Any]:
    """Flatten a prepare-trade / prepare-close response (tokens dropped, never stored)."""
    if not isinstance(pr, dict):
        return {}
    pr = _strip_tokens(pr)
    layers = [pr] + [pr[k] for k in ("preparedOrderSnapshot", "confirmation", "order", "quote", "instrument",
                                     "position") if isinstance(pr.get(k), dict)]
    out: dict[str, Any] = {}
    for key, aliases in _PR_KEYS.items():
        for layer in layers:
            hit = next((layer[a] for a in aliases if a in layer), None)
            if hit is not None:
                out[key] = hit
                break
    if "quoteAsOf" in out and isinstance(out["quoteAsOf"], str):
        out["quoteAsOf"] = out["quoteAsOf"].split(" ")[0]
    return out


def _eq(a: Any, b: Any, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is None and b is None
    fa, fb = _f(a), _f(b)
    return fa is not None and fb is not None and abs(fa - fb) <= tol


def verify_buy_prepare(pr: dict, payload: dict) -> list[str]:
    errs = []
    if str(pr.get("verdict")) != "ready":
        errs.append("PREPARE_NOT_READY")
    if pr.get("account") is not None and pr.get("account") != payload["account"]:
        errs.append("PREPARE_ACCOUNT_MISMATCH")
    if not _eq(pr.get("instrumentId"), payload["instrumentId"], 0):
        errs.append("PREPARE_INSTRUMENT_MISMATCH")
    if pr.get("direction") != "buy":
        errs.append("PREPARE_DIRECTION_NOT_BUY")
    if pr.get("orderType", "mkt") != "mkt":
        errs.append("PREPARE_ORDER_TYPE_NOT_MKT")
    if pr.get("leverage") not in (None, 1):
        errs.append("PREPARE_LEVERAGE_NOT_1")
    if not _eq(pr.get("units"), payload["units"]):
        errs.append("PREPARE_UNITS_MISMATCH")
    if not _eq(pr.get("stopLossRate"), payload["stopLossRate"]):
        errs.append("PREPARE_SL_MISMATCH")
    if not _eq(pr.get("takeProfitRate"), payload["takeProfitRate"]):
        errs.append("PREPARE_TP_MISMATCH")
    sl = _f(payload["stopLossRate"])
    lo, hi = _f(pr.get("minStopLossRate")), _f(pr.get("maxStopLossRate"))
    if sl is not None and ((lo is not None and sl < lo) or (hi is not None and sl > hi)):
        errs.append("SL_OUTSIDE_PREPARE_BOUNDS")
    if _f(pr.get("ask")) is None or CG._parse_ts(pr.get("quoteAsOf")) is None:
        errs.append("PREPARE_QUOTE_MISSING")
    return errs


def verify_close_prepare(pr: dict, payload: dict) -> list[str]:
    errs = []
    if str(pr.get("verdict")) != "ready":
        errs.append("PREPARE_NOT_READY")
    if not _eq(pr.get("positionId"), payload["positionId"], 0):
        errs.append("PREPARE_POSITION_MISMATCH")
    if not _eq(pr.get("unitsToDeduct"), payload["unitsToDeduct"]):
        errs.append("PREPARE_UNITS_TO_DEDUCT_MISMATCH")
    return errs


def buy_echo(pr: dict) -> dict:
    return {k: pr.get(k) for k in ("verdict", "instrumentId", "direction", "orderType", "leverage", "units",
                                   "stopLossRate", "takeProfitRate")}


def close_echo(pr: dict) -> dict:
    return {k: pr.get(k) for k in ("verdict", "positionId", "unitsToDeduct")}


# ---------------------------------------------------------------- verdicts
def check_verdict(path: Path, *, skill: str, max_age_s: float, now: datetime, run_ids: Optional[set] = None,
                  pack_sha256: Optional[str] = None, pack_id: Optional[str] = None, qa_ask: Optional[float] = None,
                  anchor_gate: Optional[dict] = None) -> tuple[bool, str]:
    if not path.exists():
        return False, f"verdict file missing: {path}"
    try:
        v = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        return False, f"verdict unreadable: {exc}"
    if str(v.get("verdict", "")).upper() != "PASS":
        return False, f"verdict is {v.get('verdict')!r}, not PASS"
    if v.get("checker") != QA_CHECKER:
        return False, f"checker {v.get('checker')!r} != {QA_CHECKER!r}"
    if v.get("skill") != skill:
        return False, f"skill {v.get('skill')!r} != {skill!r}"
    age = _age_s(v.get("checked_at"), now)
    if age is None:
        return False, "checked_at missing or not tz-aware ISO"
    if age > max_age_s or age < -60:
        return False, f"verdict age {age:.0f}s > {max_age_s:.0f}s"
    if run_ids is not None:
        cited = {str(v.get(k)) for k in ("run_id", "propose_run_id") if v.get(k)}
        if not cited & {r for r in run_ids if r}:
            return False, f"verdict run_id {sorted(cited)} does not match"
    if pack_id is not None and v.get("pack_id") != pack_id:
        return False, f"verdict pack_id {v.get('pack_id')!r} != {pack_id!r}"
    if pack_sha256 is not None and v.get("pack_sha256") != pack_sha256:
        return False, "pack_sha256 mismatch"
    if qa_ask is not None and not _eq(v.get("qa_ask"), qa_ask, 1e-9):
        return False, f"qa_ask {v.get('qa_ask')!r} != anchor ask {qa_ask}"
    if anchor_gate is not None:
        rc = v.get("recomputed_cost_gate")
        if not isinstance(rc, dict):
            return False, "recomputed_cost_gate missing"
        bad = [k for k in RECOMPUTED_FIELDS if not _eq(rc.get(k), anchor_gate.get(k), VERDICT_TOL)]
        if bad:
            return False, f"recomputed_cost_gate mismatch on {bad}"
    return True, "PASS"


# ---------------------------------------------------------------- checks
class _Ctx:
    def __init__(self, now: datetime):
        self.now = now
        self.checks: list[dict] = []
        self.blockers: list[str] = []

    def check(self, name: str, ok: bool, detail: Any = None, code: Optional[str] = None) -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            self.blockers.append(code or name.upper())
        return bool(ok)


def _common_gates(c: _Ctx, hold: bool, book: dict) -> Optional[float]:
    s = us_session(c.now)
    c.check("us_regular_session", s["open"], s, s.get("reason") or "MARKET_CLOSED")
    c.check("no_hold", not hold, "explicit Ofer/CoS hold" if hold else None, "HOLD")
    if not c.check("book_loaded", book.get("ok"), book.get("error"), "BOOK_MISSING"):
        return None
    a = book.get("age_s")
    c.check("book_live", a is not None and -5 <= a <= BOOK_MAX_AGE_S,
            {"asOf": book.get("asOf"), "age_s": a, "max_s": BOOK_MAX_AGE_S}, "BOOK_NOT_LIVE")
    cash, eq = book.get("cash"), book.get("equity")
    c.check("cash_sane", cash is not None and eq is not None and 0 <= cash <= eq,
            {"cash": cash, "equity": eq}, "CASH_INSANE")
    hv = sum((book.get("values") or {}).values())
    gap = None if (cash is None or eq is None) else eq - (hv + cash)
    c.check("book_equity_reconciled", gap is not None and eq > 0 and abs(gap) <= EQUITY_RECONCILE_TOL * eq,
            {"equity": eq, "holdings_value": round(hv, 2), "cash": cash, "gap": None if gap is None else round(gap, 2),
             "tol_usd": None if not eq else round(EQUITY_RECONCILE_TOL * eq, 2)}, "BOOK_EQUITY_NOT_RECONCILED")
    c.check("book_cost_basis", not book.get("cost_missing"), book.get("cost_missing"), "COST_BASIS_MISSING")
    return cash


def _guard_leg(c: _Ctx, symbol: str, instrument_id: Any, tag: str) -> Optional[dict]:
    g = guard_symbol(symbol)
    ok = (g["ok"] and isinstance(instrument_id, int) and not isinstance(instrument_id, bool)
          and instrument_id == int(g["instrumentId"] or -1))
    c.check(f"instrument_guard{tag}", ok, {"symbol": symbol, "flag": g["flag"], "resolved": g["instrumentId"],
                                           "given": instrument_id}, g["flag"] or "INSTRUMENT_GUARD")
    return resolve(symbol) if ok else None


def _momentum_go(c: _Ctx, out: dict, momentum_read: Optional[dict]) -> dict:
    """Fix8b R1: verify the executor's OWN live Momentum read for this GO (not the shared file)."""
    v = MH.verify_go_read(momentum_read, c.now)
    out["momentum_read"] = {k: val for k, val in v.items() if not k.startswith("_")}
    return v


def _cross_book(c: _Ctx, tag: str, symbol: str, instrument_id: Any, mv: dict) -> None:
    """Fix8/8b (Ofer 2026-10-13 01:44 IDT): never buy a symbol/instrument held in Momentum-HHHGDTJ
    (mirror 11630170). Buys only. Fails closed on a missing / invalid / empty / stale live read."""
    c.check(f"momentum_live_read{tag}", bool(mv.get("ok")),
            {k: mv.get(k) for k in ("code", "error", "source", "xRequestId", "response_sha256", "captured_at",
                                    "capture_age_s", "server_age_s", "max_s")},
            mv.get("code") or "MOMENTUM_READ_INVALID")
    snap = mv.get("_snap") or {}
    hit = MH.overlaps(snap, symbol, instrument_id) if mv.get("ok") else False
    c.check(f"no_cross_book_overlap{tag}", not hit,
            {"symbol": symbol, "instrumentId": instrument_id, "momentum_symbols": mv.get("symbols"),
             "xRequestId": mv.get("xRequestId")}, MH.REASON)


def _live_quote(c: _Ctx, tag: str, *, bid, ask, quote_ts, mark, pr: dict, anchor_ask: Optional[float]):
    """Live quote: ask/time from the prepare response when given (must equal any typed ask)."""
    if pr:
        if ask is not None and not _eq(ask, pr.get("ask"), 1e-9):
            c.check(f"prepare_ask_matches{tag}", False, {"typed": ask, "prepare": pr.get("ask")}, "PREPARE_ASK_MISMATCH")
        ask, quote_ts = pr.get("ask"), pr.get("quoteAsOf")
        bid = pr.get("bid", bid)
    qe = CG.quote_errors(bid=bid, ask=ask, quote_ts=quote_ts, now=c.now, independent_mark=mark)
    ok = c.check(f"quote_live{tag}", not qe, qe, "QUOTE_INVALID_OR_STALE")
    if ok and anchor_ask is not None:
        d = abs(float(ask) - anchor_ask) / anchor_ask
        ok = c.check(f"ask_within_0.1pct_of_anchor{tag}", d <= ANCHOR_TOL,
                     {"ask": ask, "anchor_ask": anchor_ask, "diff_pct": round(d * 100, 4)}, "ANCHOR_DRIFT")
    return ok, (_f(bid), _f(ask), quote_ts)


def _caps(c: _Ctx, *, symbol, asset_class, ask, fu, book, sleeve, sleeve_map, tag="") -> tuple[float, list, dict]:
    shrink: list[dict] = []
    info: dict[str, Any] = {}
    cap = NAME_CAP.get(str(asset_class or ""))
    smap = {**DEFAULT_SLEEVES, **(sleeve_map or {})}
    if sleeve:
        smap[symbol] = sleeve
    if not c.check(f"asset_class_known{tag}", cap is not None, asset_class, "ASSET_CLASS_UNKNOWN") or not book.get("ok"):
        return fu, shrink, info
    unknown = sorted(s for s in set(book["values"]) | {symbol} if s not in smap)
    sleeves_ok = c.check(f"sleeves_known{tag}", not unknown, {"unknown": unknown}, "SLEEVE_UNKNOWN")
    for basis in ("values", "cost"):
        vals = book[basis]
        inv = cap_denominator(vals, book.get("cash"), _basis_equity(book, basis))
        k = (1 - cap) if CAP_DENOMINATOR == "invested" else 1.0  # buying adds to an invested denominator
        mx = _floor_units(((cap * inv - vals.get(symbol, 0.0)) / k) / ask)
        if fu > mx:
            shrink.append({"reason": f"name_cap_{int(cap * 100)}pct_{basis}", "from_units": fu, "to_units": mx})
            fu = mx
        if sleeves_ok:
            sl = smap[symbol]
            scur = sum(v for s, v in vals.items() if smap.get(s) == sl)
            ks = (1 - SLEEVE_CAP) if CAP_DENOMINATOR == "invested" else 1.0
            mx = _floor_units(((SLEEVE_CAP * inv - scur) / ks) / ask)
            if fu > mx:
                shrink.append({"reason": f"sleeve_cap_45pct_{basis}", "from_units": fu, "to_units": mx})
                fu = mx
    notional = fu * ask
    caps = {}
    for basis in ("values", "cost"):
        vals = book[basis]
        inv_after = cap_denominator(vals, book.get("cash"), _basis_equity(book, basis)) + (notional if CAP_DENOMINATOR == "invested" else 0.0)
        caps[basis] = {"name_pct": round((vals.get(symbol, 0.0) + notional) / inv_after * 100, 2) if inv_after else None}
        if sleeves_ok:
            sl = smap[symbol]
            caps[basis].update(sleeve=sl, sleeve_pct=round((sum(v for s, v in vals.items() if smap.get(s) == sl)
                                                            + notional) / inv_after * 100, 2) if inv_after else None)
    info["caps_after"] = {"market_value": caps["values"], "cost_basis": caps["cost"], "name_cap_pct": cap * 100,
                          "sleeve_cap_pct": SLEEVE_CAP * 100}
    return fu, shrink, info


def _cash_checks(c: _Ctx, tag: str, *, cash, fu, sizing_ask, live_ask, open_fee) -> dict:
    out = {}
    for nm, px in (("anchor", sizing_ask), ("live", live_ask)):
        if px is None:
            continue
        ca = None if cash is None else cash - fu * px - open_fee
        out[nm] = None if ca is None else round(ca, 4)
        c.check(f"cash_after_ge_floor_{nm}{tag}", ca is not None and ca >= CASH_FLOOR_USD,
                {"cash": cash, "units": fu, "price": px, "open_fee": open_fee, "cash_after": out[nm],
                 "floor": CASH_FLOOR_USD}, "CASH_FLOOR")
    return out


def _sl_check(c: _Ctx, tag: str, sl: Any, live_bid: Optional[float]) -> None:
    slf = _f(sl)
    c.check(f"stop_loss_valid{tag}", slf is not None and live_bid is not None and 0 < slf < live_bid,
            {"stopLossRate": slf, "bid": live_bid}, "STOP_LOSS_INVALID")


def _recent_positions(book: dict, iid: int, now: datetime, since: Optional[datetime] = None) -> list:
    out = []
    lim = now - timedelta(hours=RECENT_POSITION_H)
    for p in book.get("positions") or []:
        if p.get("instrumentId") != iid:
            continue
        t = _open_time_utc(p.get("openTime"))
        if t is None or t >= lim or (since is not None and t > since):
            out.append(p.get("positionId"))
    return out


def _open_time_utc(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def lock_key(parts: list) -> str:
    return canonical_sha(parts)[:40]


def _lock_paths(keys: list[str]) -> list[Path]:
    d = Path(paths()["lock_dir"])
    return [d / f"{k}.lock" for k in keys]


def _locks_check(c: _Ctx, pack_key_parts: list, leg_parts: list[list]) -> list[Path]:
    lps = _lock_paths([lock_key(pack_key_parts)] + [lock_key(lp) for lp in leg_parts])
    c.check("not_already_go", not lps[0].exists(), {"lock": str(lps[0]), "key": pack_key_parts}, "ALREADY_GO_LOCKED")
    for lp, parts in zip(lps[1:], leg_parts):
        c.check("no_same_day_same_side_go", not lp.exists(), {"lock": str(lp), "key": parts}, "SAME_DAY_LEG_LOCKED")
    return lps


def _finish(out: dict, c: _Ctx, lps: Optional[list[Path]], write_lock: bool) -> dict:
    P = paths()
    out["paths"] = {k: str(v) for k, v in P.items() if k not in ("test_mode",)}
    out["test_mode"] = P["test_mode"]
    out["checks"] = c.checks
    out["blockers"] = c.blockers
    out.setdefault("ready_for_order_qa", False)
    go = not c.blockers
    if go and lps and write_lock:
        made: list[Path] = []
        try:
            for lp in lps:
                lp.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as fh:
                    json.dump({"pack_id": out.get("pack_id"), "pack_sha256": out.get("pack_sha256"),
                               "go_at": c.now.isoformat()}, fh)
                made.append(lp)
            out["locks"] = [str(p) for p in made]
        except FileExistsError:
            for p in made:
                p.unlink(missing_ok=True)
            c.check("not_already_go", False, {"race": True}, "ALREADY_GO_LOCKED")
            go = False
    out["decision"] = "GO" if go else "NO-GO"
    out["note"] = ("GO = place with the token of the prepare-trade/prepare-close whose response was verified here "
                   "(payloads were prepared verbatim; sells first). This CLI never places."
                   if go else "NO-GO = do not place. Log the skip with the numbers.")
    return out


def _gate_summary(cg: Optional[dict]) -> Optional[dict]:
    return None if cg is None else {k: cg.get(k) for k in ("verdict", "ratio", "expected_gain", "total_cost",
                                                           "errors", "skip_reasons")}


# ---------------------------------------------------------------- RSI
def run_checks(*, pack_id: str, mark: Optional[float], bid: Optional[float] = None, ask: Optional[float] = None,
               quote_ts: Any = None, prepare_response: Optional[dict] = None, anchor_ask: Optional[float] = None,
               anchor_bid: Optional[float] = None, units: Optional[float] = None, amount_usd: Optional[float] = None,
               open_fee_usd: Optional[float] = None, close_fee_usd: Optional[float] = None,
               overnight_usd: Optional[float] = None, spread_usd: Optional[float] = None,
               sleeve: Optional[str] = None, sleeve_map: Optional[dict] = None, now: Optional[datetime] = None,
               hold: bool = False, write_lock: bool = True, momentum_read: Optional[dict] = None) -> dict[str, Any]:
    now = now or datetime.now(IDT)
    c = _Ctx(now)
    P = paths()
    out: dict[str, Any] = {"kind": "execute_pass", "action_kind": "rsi_buy", "version": VERSION,
                           "asOfIDT": now.astimezone(IDT).strftime("%Y-%m-%d %H:%M:%S IDT"), "pack_id": pack_id,
                           "never_calls_etoro": True, "places": False,
                           "inputs": {"bid": bid, "ask": ask, "quote_ts": quote_ts, "mark": mark,
                                      "anchor_ask": anchor_ask, "anchor_bid": anchor_bid, "units": units,
                                      "amount_usd": amount_usd, "open_fee_usd": open_fee_usd,
                                      "close_fee_usd": close_fee_usd, "overnight_usd": overnight_usd,
                                      "spread_usd": spread_usd, "sleeve": sleeve, "hold": hold,
                                      "prepare_response": bool(prepare_response)}}
    m = RSI_PACK_ID_RE.match(pack_id or "")
    if not c.check("pack_id_format", m is not None, pack_id, "BAD_PACK_ID"):
        return _finish(out, c, None, False)
    run_id, symbol = m.group(1), m.group(2)
    out.update(run_id=run_id, symbol=symbol)
    pack, ctx = load_pack(run_id, symbol)
    out["pack_context"] = ctx
    if not c.check("pack_found", pack is not None, ctx.get("error"), "PACK_NOT_FOUND"):
        return _finish(out, c, None, False)
    inst = pack.get("instrument") or {}
    iid = inst.get("instrumentId")
    out.update(instrumentId=iid, etoroSymbol=inst.get("etoroSymbol"))
    run_ids = {run_id, ctx.get("envelope_run_id"), ctx.get("propose_run_id"), pack.get("run_id")}
    book = load_book(now)
    cash = _common_gates(c, hold, book)
    c.check("auto_place_eligible", pack.get("auto_place_eligible") is True, pack.get("auto_place_blockers"),
            "NOT_AUTO_PLACE_ELIGIBLE")
    ok, why = check_verdict(run_verdict_path(run_id), skill=RUN_QA_SKILL, max_age_s=RUN_QA_MAX_AGE_S, now=now,
                            run_ids=run_ids)
    c.check("run_qa_pass", ok, {"why": why, "path": str(run_verdict_path(run_id))}, "RUN_QA_NOT_PASS")
    res = _guard_leg(c, symbol, iid, "")
    _cross_book(c, "", symbol, iid, _momentum_go(c, out, momentum_read))
    c.check("long_only_x1", pack.get("side") == "buy" and pack.get("action") == "CANDIDATE_LONG"
            and pack.get("leverage") == 1, {"side": pack.get("side"), "leverage": pack.get("leverage")}, "NOT_LONG_X1")
    pr = norm_prepare(prepare_response)
    a_ask = _f(anchor_ask)
    qok, (lbid, lask, lts) = _live_quote(c, "", bid=bid, ask=ask, quote_ts=quote_ts, mark=mark, pr=pr,
                                         anchor_ask=a_ask)
    if not qok:
        return _finish(out, c, None, False)
    a_ask = a_ask if a_ask is not None else lask
    a_bid = _f(anchor_bid) if anchor_bid is not None else lbid
    c.check("anchor_quote_sane", a_bid is not None and a_ask is not None and 0 < a_bid < a_ask,
            {"anchor_bid": a_bid, "anchor_ask": a_ask}, "ANCHOR_QUOTE_INVALID")
    out["anchor"] = {"ask": a_ask, "bid": a_bid}
    lv = pack.get("levels") or {}
    try:
        drift, lim = abs(lask - float(lv.get("entry"))), DRIFT_ATR_MULT * float(lv.get("atr"))
        c.check("drift_le_half_atr", drift <= lim, {"drift": round(drift, 4), "limit": round(lim, 4)}, "DRIFT")
    except (TypeError, ValueError):
        c.check("drift_le_half_atr", False, "entry/atr missing", "DRIFT")
    req = _f(units) if units is not None else ((_f(amount_usd) or 0) / a_ask if amount_usd else None)
    if not c.check("size_given", req is not None and req > 0, req, "NO_SIZE"):
        return _finish(out, c, None, False)
    of = _f(open_fee_usd)
    if not c.check("open_fee_given", of is not None and of >= 0, open_fee_usd, "OPEN_FEE_REQUIRED"):
        return _finish(out, c, None, False)
    fu = _floor_units(req)
    shrink: list = []
    if cash is not None:
        mx = _floor_units((cash - CASH_FLOOR_USD - of) / a_ask)
        if fu > mx:
            shrink.append({"reason": "cash_floor", "from_units": fu, "to_units": mx})
            fu = mx
    fu, s2, info = _caps(c, symbol=symbol, asset_class=(res or {}).get("assetClass"), ask=a_ask, fu=fu, book=book,
                         sleeve=sleeve, sleeve_map=sleeve_map)
    shrink += s2
    out.update(info)
    cash_after = _cash_checks(c, "", cash=cash, fu=fu, sizing_ask=a_ask, live_ask=lask, open_fee=of)
    c.check("min_position", fu * a_ask >= MIN_POSITION_USD, {"notional": round(fu * a_ask, 2)}, "BELOW_MIN_POSITION")
    out["sizing"] = {"requested_units": round(req, UNITS_DP), "final_units": fu, "sized_on": "anchor ask",
                     "final_notional_usd": round(fu * a_ask, 2), "shrunk": bool(shrink), "shrink_steps": shrink,
                     "cash_after_usd": cash_after}
    rl = CG.rebase_levels(pack, a_ask)
    out["rebased_levels"] = rl
    payload = {"account": P["account"], "direction": "buy", "instrumentId": iid, "units": fu, "leverage": 1,
               "orderType": "mkt", "stopLossRate": rl.get("stop_loss"), "takeProfitRate": rl.get("take_profit")}
    out["order_payloads"] = [payload]
    _sl_check(c, "", rl.get("stop_loss"), lbid)
    anchor_cg = live_cg = None
    if fu > 0 and rl.get("stop_loss") and rl.get("take_profit"):
        kw = dict(units=fu, open_fee_usd=open_fee_usd, close_fee_usd=close_fee_usd, overnight_usd=overnight_usd,
                  spread_usd=spread_usd, take_profit=rl["take_profit"], stop_loss=rl["stop_loss"], now=now)
        anchor_cg = CG.rsi_gate(pack, bid=a_bid, ask=a_ask, quote_ts=None, stage="anchor", **kw)
        live_cg = CG.rsi_gate(pack, bid=lbid, ask=lask, quote_ts=lts, independent_mark=mark, stage="final", **kw)
    out["cost_gate_anchor"], out["cost_gate"] = anchor_cg, live_cg
    for nm, g in (("anchor_cost_gate", anchor_cg), ("final_cost_gate", live_cg)):
        c.check(nm, g is not None and g.get("verdict") == CG.VERDICT_PASS, _gate_summary(g),
                (g or {}).get("verdict") or "COST_GATE_SKIP")
    if c.check("prepare_response_given", bool(pr), None, "PREPARE_RESPONSE_MISSING"):
        pe = verify_buy_prepare(pr, payload)
        c.check("prepare_matches_payload", not pe, pe, "PREPARE_MISMATCH")
    binding = {"pack_key": ["rsi", run_id, symbol, iid], "pack": pack, "final_units": fu,
               "order_payloads": [payload], "anchor": out["anchor"],
               "fees": {"open": of, "close": _f(close_fee_usd), "overnight": _f(overnight_usd),
                        "spread_usd": _f(spread_usd)}, "prepare_echo": [buy_echo(pr)] if pr else None,
               "test_mode": P["test_mode"]}
    out["pack_sha256"] = canonical_sha(binding)
    out["order_qa_verdict_path"] = str(order_verdict_path(out["pack_sha256"]))
    since = _open_time_utc(pack.get("bar_time"))
    dup = _recent_positions(book, iid, now, since) if book.get("ok") else []
    c.check("no_duplicate_open", not dup, {"positions": dup}, "DUPLICATE_OPEN_POSITION")
    lps = _locks_check(c, ["rsi", run_id, symbol, iid], [["leg", iid, "buy", et_date(now)]])
    pre = list(c.blockers)
    ok, why = check_verdict(order_verdict_path(out["pack_sha256"]), skill=ORDER_QA_SKILL, max_age_s=ORDER_QA_MAX_AGE_S,
                            now=now, run_ids=run_ids, pack_sha256=out["pack_sha256"], qa_ask=a_ask,
                            anchor_gate=anchor_cg)
    exists = order_verdict_path(out["pack_sha256"]).exists()
    c.check("order_qa_pass", ok, why, "ORDER_QA_NOT_PASS" if exists else "ORDER_QA_PENDING")
    out["ready_for_order_qa"] = not pre
    return _finish(out, c, lps, write_lock)


# ---------------------------------------------------------------- rebalance
def _verify_risk_exit(c: _Ctx, reason: Optional[str], *, symbol: str, pos: Optional[dict], book: dict,
                      scores: Optional[dict], live_bid: Optional[float], cash: Optional[float],
                      sleeve_map: Optional[dict]) -> tuple[bool, dict]:
    d: dict[str, Any] = {"reason": reason}
    ok = False
    srow = CG.score_row(scores, symbol) if scores else None
    if reason == "cash_below_floor":
        ok = cash is not None and cash < CASH_FLOOR_USD
        d["cash"] = cash
    elif reason == "stop_hit":
        slr = _f((pos or {}).get("stopLossRate"))
        tr = ((scores or {}).get("trailing_stops") or {}).get(symbol) or {}
        hi, th = _f(tr.get("high_since_entry")), _f(tr.get("threshold"))
        trail = hi * (1 + th) if hi is not None and th is not None else None
        ok = live_bid is not None and ((slr is not None and live_bid <= slr) or (trail is not None and live_bid <= trail))
        d.update(bid=live_bid, position_stop=slr, trailing_level=trail)
    elif reason == "trigger_3_50dma_neg_rs":
        ok = bool(srow) and srow.get("above_50dma") is False and (_f(srow.get("rs_3m")) or 0) < 0
        d.update(above_50dma=(srow or {}).get("above_50dma"), rs_3m=(srow or {}).get("rs_3m"))
    elif reason == "trigger_4_200dma":
        ok = bool(srow) and srow.get("above_200dma") is False
        d.update(above_200dma=(srow or {}).get("above_200dma"))
    elif reason == "hard_cap_breach" and book.get("ok"):
        ac = (resolve(symbol) or {}).get("assetClass")
        cap = NAME_CAP.get(str(ac or ""))
        smap = {**DEFAULT_SLEEVES, **(sleeve_map or {})}
        pcts = {}
        for basis in ("values", "cost"):
            inv = cap_denominator(book[basis], book.get("cash"), _basis_equity(book, basis))
            pcts[f"name_{basis}"] = book[basis].get(symbol, 0.0) / inv if inv else 0.0
            sl = smap.get(symbol)
            pcts[f"sleeve_{basis}"] = (sum(v for s, v in book[basis].items() if smap.get(s) == sl) / inv
                                       if (inv and sl) else 0.0)
        ok = cap is not None and (max(pcts["name_values"], pcts["name_cost"]) > cap
                                  or max(pcts["sleeve_values"], pcts["sleeve_cost"]) > SLEEVE_CAP)
        d.update({k: round(v * 100, 2) for k, v in pcts.items()}, name_cap_pct=(cap or 0) * 100)
    d["verified"] = ok
    c.check("risk_exit_verified", ok, d, "RISK_EXIT_NOT_VERIFIED")
    return ok, d


def _ceil_units(x: float) -> float:
    return math.ceil(round(x / UNIT_STEP, 3)) * UNIT_STEP if x > 0 else 0.0


def _risk_exit_size(reason: str, *, symbol: str, pos: dict, book: dict, cash: Optional[float],
                    bid: float, close_fee: float, sleeve_map: Optional[dict]) -> dict[str, Any]:
    """Fix5: minimum units of `pos` that restore the floor / caps, plus a buffer of 1% of equity.

    cash_below_floor: x*bid - close_fee >= 2500 + B - cash.
    hard_cap_breach : for name and sleeve, on BOTH market value and cost basis,
                      (X - x*u) <= cap*(T - x*u) - B  =>  x >= (X - cap*T + B) / (u*(1-cap)),
                      u = per-unit value (pos value/units) or per-unit cost (pos invested/units).
    Rounded UP to 1e-6 units. If the residual (held - x)*bid < $400, or x >= held, the whole position
    is closed (unitsToDeduct null). B = RISK_EXIT_BUFFER_EQUITY_PCT * equity.
    """
    held = float(pos.get("units") or 0)
    eq = _f(book.get("equity")) or 0.0
    B = RISK_EXIT_BUFFER_EQUITY_PCT * eq
    need: dict[str, float] = {}
    if reason == "cash_below_floor":
        need["cash_floor"] = (CASH_FLOOR_USD + B - (cash or 0.0) + close_fee) / bid
    else:
        ac = (resolve(symbol) or {}).get("assetClass")
        cap = NAME_CAP.get(str(ac or ""), 0.0)
        smap = {**DEFAULT_SLEEVES, **(sleeve_map or {})}
        sl = smap.get(symbol)
        per_unit = {"values": (_f(pos.get("value")) or 0.0) / held if held else 0.0,
                    "cost": (_f(pos.get("invested")) or 0.0) / held if held else 0.0}
        for basis in ("values", "cost"):
            T = cap_denominator(book[basis], book.get("cash"), _basis_equity(book, basis))
            u = per_unit[basis]
            # denominator after selling x: invested => T - x*u ; equity => T - fee + x*(bid - u) (proceeds to cash)
            if CAP_DENOMINATOR == "invested":
                T_eff, dpu = T, -u
            else:
                T_eff, dpu = T - close_fee, bid - u
            if u <= 0:
                continue
            X = book[basis].get(symbol, 0.0)
            if cap:
                need[f"name_{basis}"] = (X - cap * T_eff + B) / (u + cap * dpu)
            if sl:
                S = sum(v for s_, v in book[basis].items() if smap.get(s_) == sl)
                need[f"sleeve_{basis}"] = (S - SLEEVE_CAP * T_eff + B) / (u + SLEEVE_CAP * dpu)
    x = _ceil_units(max([0.0, *need.values()]))
    residual_usd = max(held - x, 0.0) * bid
    full = x >= held - 1e-9 or residual_usd < MIN_POSITION_USD
    units = held if full else x
    plan_x = _ceil_units(x * RISK_EXIT_PLAN_HEADROOM)
    plan_full = plan_x >= held - 1e-9 or max(held - plan_x, 0.0) * bid < MIN_POSITION_USD
    return {"suggested_pack_units": round(held if plan_full else plan_x, 6),
            "suggested_unitsToDeduct": None if plan_full else round(plan_x, 6),
            "suggested_required_at_qa": round(x, 6),"reason": reason, "held_units": held, "buffer_usd": round(B, 2),
            "required_units_by_constraint": {k: round(v, 6) for k, v in need.items()},
            "min_units": round(x, 6), "residual_usd": round(residual_usd, 2), "full_close": full,
            "full_close_reason": ("units >= held" if x >= held - 1e-9 else "residual < $400") if full else None,
            "units": round(units, 6), "unitsToDeduct": None if full else round(units, 6)}


def _risk_exit_band(*, u: Optional[float], held: float, sz: dict, bid: float,
                    required_at_qa: Optional[float]) -> dict[str, Any]:
    """Fix6: one-sided size band at GO (pack units are frozen by pack_sha256 / order-QA).

    required_now = live min units (book + min(anchor, live) bid at GO). PASS when
      required_now <= pack_units <= RISK_EXIT_SIZE_BAND * max(required_at_qa, required_now)
    required_at_qa = the leg's declared `risk_exit_required_units` (sizing at plan/QA; hashed in the pack),
    clamped to RISK_EXIT_QA_REQ_MAX_RATIO * required_now. The <$400 residual full-close rule is
    re-evaluated at GO: a full close passes if the live rule says full close or held is inside the band;
    a partial close must leave a live residual (held - pack_units) * bid >= $400.
    """
    rq_now = float(sz["min_units"])
    rq_qa = _f(required_at_qa)
    rq_qa_eff = None if rq_qa is None or rq_qa <= 0 else min(rq_qa, RISK_EXIT_QA_REQ_MAX_RATIO * max(rq_now, UNIT_STEP))
    ref = max(rq_now, rq_qa_eff or 0.0)
    upper = RISK_EXIT_SIZE_BAND * ref + UNIT_STEP
    d: dict[str, Any] = {"pack_units": u, "held_units": held, "required_now": round(rq_now, 6),
                         "required_at_qa": rq_qa, "required_at_qa_used": None if rq_qa_eff is None else round(rq_qa_eff, 6),
                         "upper": round(upper, 6), "band": RISK_EXIT_SIZE_BAND, "live_full_close": sz["full_close"],
                         "bid": bid}
    if u is None or u <= 0:
        d.update(ok=False, why="no units")
        return d
    if abs(u - held) < 1e-9:
        ok = bool(sz["full_close"]) or held <= upper
        d.update(ok=ok, mode="full", why=None if ok else "full close but live rule is partial and held > band upper")
        return d
    residual = (held - u) * bid
    d["residual_usd"] = round(residual, 2)
    if u < rq_now - 1e-9:
        d.update(ok=False, mode="partial", why="below required_now (does not restore floor/cap at GO)")
    elif u > upper:
        d.update(ok=False, mode="partial", why="above band upper (oversized)")
    elif residual < MIN_POSITION_USD:
        d.update(ok=False, mode="partial", why="residual < $400 at GO => must be a full close")
    else:
        d.update(ok=True, mode="partial", why=None)
    return d


def _cap_pcts(vals: dict[str, float], den: float, smap: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    if den <= 0:
        return out
    for s_, v in vals.items():
        out[f"name:{s_}"] = v / den
    for sl in sorted({smap[s_] for s_ in vals if s_ in smap}):
        out[f"sleeve:{sl}"] = sum(v for s_, v in vals.items() if smap.get(s_) == sl) / den
    return out


def _cap_limit(key: str) -> Optional[float]:
    kind, name = key.split(":", 1)
    if kind == "sleeve":
        return SLEEVE_CAP
    return NAME_CAP.get(str((resolve(name) or {}).get("assetClass") or ""))


def post_trade_caps(book: dict, *, symbol: str, pos: dict, units: float, bid: float, close_fee: float = 0.0,
                    sleeve_map: Optional[dict] = None) -> dict[str, Any]:
    """Fix6: simulate the book after selling `units` of `pos` and check EVERY name cap (ETF 30% / stock 15%)
    and sleeve cap (45%) on market value AND cost basis (denominator = cap_denominator()).

    A cascade = a NEW breach: a bucket at/under its cap before the sale and over it after. Buckets
    already over their cap before (they need their own risk exit) are reported in `worsened_existing`
    but do not block, otherwise one pre-existing breach would block every protective exit. Sold value is removed at the position's per-unit book value / cost;
    proceeds (units*bid - close_fee) go to cash. Equity mode: value-basis equity after = equity - sold value
    + units*bid - close_fee (i.e. equity minus fees and the bid/mark gap); cost basis = cost after + cash after.
    """
    smap = {**DEFAULT_SLEEVES, **(sleeve_map or {})}
    held = float(pos.get("units") or 0.0)
    frac = min(max(units / held, 0.0), 1.0) if held else 0.0
    cash0 = book.get("cash")
    cash1 = None if cash0 is None else cash0 + units * bid - close_fee
    res: dict[str, Any] = {"denominator": CAP_DENOMINATOR, "symbol": symbol, "units": units, "cascade": [],
                           "worsened_existing": [], "after": {}, "before": {}}
    for basis, field in (("values", "value"), ("cost", "invested")):
        before = dict(book[basis])
        after = dict(before)
        after[symbol] = max(after.get(symbol, 0.0) - frac * (_f(pos.get(field)) or 0.0), 0.0)
        if after[symbol] <= 1e-9:
            after.pop(symbol)
        if basis == "values" and CAP_DENOMINATOR == "equity" and _f(book.get("equity")) is not None:
            eq0 = float(book["equity"])
            den0, den1 = eq0, eq0 - (before.get(symbol, 0.0) - after.get(symbol, 0.0)) + units * bid - close_fee
        else:
            den0, den1 = cap_denominator(before, cash0), cap_denominator(after, cash1)
        res.setdefault("denominator_usd", {})[basis] = {"before": round(den0, 2), "after": round(den1, 2)}
        pb, pa = _cap_pcts(before, den0, smap), _cap_pcts(after, den1, smap)
        res["before"][basis] = {k: round(v * 100, 2) for k, v in pb.items()}
        res["after"][basis] = {k: round(v * 100, 2) for k, v in pa.items()}
        for k, v in pa.items():
            lim = _cap_limit(k)
            if lim is None:
                continue
            b = pb.get(k, 0.0)
            if v > lim + 1e-12 and b > lim + 1e-12 and v > b + 1e-12:
                res["worsened_existing"].append({"bucket": k, "basis": basis, "before_pct": round(b * 100, 2),
                                                 "after_pct": round(v * 100, 2), "cap_pct": lim * 100})
            elif v > lim + 1e-12 and b <= lim + 1e-12:
                res["cascade"].append({"bucket": k, "basis": basis, "before_pct": round(pb.get(k, 0.0) * 100, 2),
                                       "after_pct": round(v * 100, 2), "cap_pct": lim * 100})
    res["ok"] = not res["cascade"]
    return res


def _risk_exit_alternatives(reason: str, *, sold_symbol: str, book: dict, cash: Optional[float],
                            sleeve_map: Optional[dict]) -> list[dict]:
    """Fix6: other held legs that would fix the same breach without a post-trade cap cascade (indicative,
    priced at book value/unit; a new pack + order-QA is required — this pass never resizes or swaps legs)."""
    out = []
    for p in book.get("positions") or []:
        s_ = str(p.get("symbol")).upper()
        held = _f(p.get("units")) or 0.0
        if s_ == sold_symbol or held <= 0:
            continue
        if reason == "hard_cap_breach":
            ok_v, _ = _verify_risk_exit(_Ctx(datetime.now(IDT)), reason, symbol=s_, pos=p, book=book, scores=None,
                                        live_bid=None, cash=cash, sleeve_map=sleeve_map)
            if not ok_v:
                continue
        px = (_f(p.get("value")) or 0.0) / held
        if px <= 0:
            continue
        sz = _risk_exit_size(reason, symbol=s_, pos=p, book=book, cash=cash, bid=px, close_fee=0.0, sleeve_map=sleeve_map)
        pt = post_trade_caps(book, symbol=s_, pos=p, units=sz["units"], bid=px, sleeve_map=sleeve_map)
        out.append({"symbol": s_, "positionId": p.get("positionId"), "units": sz["units"],
                    "unitsToDeduct": sz["unitsToDeduct"], "post_trade_ok": pt["ok"], "cascade": pt["cascade"]})
    return [a for a in out if a["post_trade_ok"]]


def _sl_bounds_ok(sl: Optional[float], anchor_ask: float, atr_d: Optional[float], asset_class: Optional[str]) -> dict:
    res: dict[str, Any] = {"stopLossRate": sl, "anchor_ask": anchor_ask, "daily_atr": atr_d}
    if sl is None:
        res["ok"] = False
        return res
    atr_ok = atr_d is not None and anchor_ask - SL_ATR_BOUNDS[1] * atr_d <= sl <= anchor_ask - SL_ATR_BOUNDS[0] * atr_d
    tb = TRAIL_BOUNDS.get(str(asset_class or ""))
    pct_below = (anchor_ask - sl) / anchor_ask
    trail_ok = tb is not None and tb[0] - 1e-9 <= pct_below <= tb[1] + 1e-9
    res.update(atr_rule=atr_ok, trailing_rule=trail_ok, pct_below=round(pct_below * 100, 3), ok=atr_ok or trail_ok)
    return res


def run_rebalance_checks(*, pack: dict[str, Any], live: Optional[dict] = None, sleeve_map: Optional[dict] = None,
                         now: Optional[datetime] = None, hold: bool = False, write_lock: bool = True,
                         momentum_read: Optional[dict] = None) -> dict:
    now = now or datetime.now(IDT)
    c = _Ctx(now)
    P = paths()
    kind = pack.get("kind")
    pack_id = pack.get("pack_id") if isinstance(pack.get("pack_id"), str) else ""
    out: dict[str, Any] = {"kind": "execute_pass", "action_kind": kind, "version": VERSION,
                           "asOfIDT": now.astimezone(IDT).strftime("%Y-%m-%d %H:%M:%S IDT"), "pack_id": pack_id,
                           "never_calls_etoro": True, "places": False, "inputs": {"hold": hold}}
    legs = pack.get("legs") or []
    lives = (live or {}).get("legs") or []
    sells = [i for i, l in enumerate(legs) if l.get("side") == "sell"]
    buys = [i for i, l in enumerate(legs) if l.get("side") == "buy"]
    shape = {"rebalance_add": (0, 1), "trim": (1, 0), "sell": (1, 0), "rotation": (1, 1)}.get(kind)
    c.check("pack_id_format", bool(REBAL_PACK_ID_RE.match(pack_id)), pack_id, "BAD_PACK_ID")
    if not c.check("pack_shape", shape is not None and (len(sells), len(buys)) == shape and len(lives) == len(legs),
                   {"kind": kind, "sells": len(sells), "buys": len(buys), "live_legs": len(lives)}, "BAD_REBALANCE_PACK"):
        return _finish(out, c, None, False)
    book = load_book(now)
    cash = _common_gates(c, hold, book)
    sc = load_scores(now)
    out["scores"] = {k: sc.get(k) for k in ("ok", "error", "asOf_bars", "path", "sha256", "age_trading_days")}
    # fix4: protective exits that read only the book + live quote (cash_below_floor, stop_hit on the
    # position's own stopLossRate, hard_cap_breach) do not require verified scores. Everything else
    # (buys: ATR SL bounds + edge; non-risk sells: edge; trigger_3/4; trailing-stop leg of stop_hit) does.
    book_only_exit = (kind in ("trim", "sell") and bool(pack.get("risk_exit"))
                      and pack.get("risk_exit_reason") in BOOK_ONLY_RISK_EXITS)
    out["scores"]["required"] = not book_only_exit
    if not book_only_exit:
        c.check("scores_verified", bool(sc.get("ok")), out["scores"], "SCORES_UNVERIFIED")
    scores = sc.get("data")  # None unless verified, so the trailing-stop path can never use an unverified file
    payloads: list[dict] = []
    echoes: list[dict] = []
    anchor_legs: dict[int, dict] = {}
    live_legs: dict[int, dict] = {}
    leg_lock_parts: list[list] = []
    risk_ok = False
    mv = _momentum_go(c, out, momentum_read) if buys else None
    for i in sells + buys:  # sells first
        l, lv = legs[i], lives[i]
        side = l["side"]
        tag = f"_{side}{i}"
        sym = str(l.get("symbol") or "").upper()
        iid = l.get("instrumentId")
        res = _guard_leg(c, sym, iid, tag)
        pr = norm_prepare(lv.get("prepare_response"))
        a_ask, a_bid = _f(l.get("anchor_ask")), _f(l.get("anchor_bid"))
        c.check(f"anchor_quote_sane{tag}", a_bid is not None and a_ask is not None and 0 < a_bid < a_ask,
                {"anchor_bid": a_bid, "anchor_ask": a_ask}, "ANCHOR_QUOTE_INVALID")
        if side == "buy":
            qok, (lbid, lask, lts) = _live_quote(c, tag, bid=lv.get("bid"), ask=lv.get("ask"),
                                                 quote_ts=lv.get("quote_ts"), mark=lv.get("independent_mark"),
                                                 pr=pr, anchor_ask=a_ask)
        else:
            qe = CG.quote_errors(bid=lv.get("bid"), ask=lv.get("ask"), quote_ts=lv.get("quote_ts"), now=now,
                                 independent_mark=lv.get("independent_mark"))
            qok = c.check(f"quote_live{tag}", not qe, qe, "QUOTE_INVALID_OR_STALE")
            lbid, lask, lts = _f(lv.get("bid")), _f(lv.get("ask")), lv.get("quote_ts")
            if qok and a_bid:
                d = abs(lbid - a_bid) / a_bid
                qok = c.check(f"bid_within_0.1pct_of_anchor{tag}", d <= ANCHOR_TOL,
                              {"bid": lbid, "anchor_bid": a_bid}, "ANCHOR_DRIFT")
        leg_lock_parts.append(["leg", iid, side, et_date(now)])
        if side == "sell":
            pid = l.get("positionId")
            pid_ok = c.check(f"position_id_int{tag}", isinstance(pid, int) and not isinstance(pid, bool), pid,
                             "POSITION_ID_NOT_INT")
            pos = next((p for p in book.get("positions") or [] if p.get("positionId") == pid
                        and p.get("instrumentId") == iid), None) if pid_ok else None
            u, pu = _f(l.get("units")), _f((pos or {}).get("units"))
            c.check(f"position_held{tag}", pos is not None and u is not None and u > 0 and pu is not None
                    and u <= pu + 1e-9, {"positionId": pid, "units": u, "held_units": pu}, "POSITION_NOT_HELD")
            full = pu is not None and u is not None and abs(u - pu) < 1e-9
            payload = {"account": P["account"], "positionId": pid, "unitsToDeduct": None if full else u}
            orate = _f((pos or {}).get("openRate", (pos or {}).get("avgOpenRate")))
            declared = _f(l.get("realized_pnl_usd"))
            recomputed = (lbid - orate) * u if (orate and lbid and u) else None
            c.check(f"realized_pnl_recomputed{tag}", recomputed is not None and declared is not None
                    and abs(declared - recomputed) <= REALIZED_TOL_USD,
                    {"declared": declared, "recomputed": None if recomputed is None else round(recomputed, 4),
                     "openRate": orate, "bid": lbid, "units": u, "tol_usd": REALIZED_TOL_USD}, "REALIZED_PNL_MISMATCH")
            rp_tax = max(x for x in (declared, recomputed) if x is not None) if (declared is not None
                                                                                 or recomputed is not None) else None
            if pack.get("risk_exit"):
                risk_ok, rd = _verify_risk_exit(c, pack.get("risk_exit_reason"), symbol=sym, pos=pos, book=book,
                                                scores=scores, live_bid=lbid, cash=cash, sleeve_map=sleeve_map)
                out["risk_exit_check"] = rd
                reason = pack.get("risk_exit_reason")
                if risk_ok and reason in SIZED_RISK_EXITS and pos is not None:
                    sz = _risk_exit_size(reason, symbol=sym, pos=pos, book=book, cash=cash,
                                         bid=min(x for x in (a_bid, lbid) if x) if (a_bid or lbid) else 0.0,
                                         close_fee=_f(l.get("close_fee_usd")) or 0.0, sleeve_map=sleeve_map)
                    out["risk_exit_sizing"] = sz
                    sbid = min(x for x in (a_bid, lbid) if x) if (a_bid or lbid) else 0.0
                    band = _risk_exit_band(u=u, held=float(pu or 0.0), sz=sz, bid=sbid,
                                           required_at_qa=l.get("risk_exit_required_units"))
                    band.update(required_units=sz["units"], unitsToDeduct=sz["unitsToDeduct"])
                    out["risk_exit_band"] = band
                    c.check(f"risk_exit_size{tag}", band["ok"], band, "RISK_EXIT_SIZE_MISMATCH")
                    if u is not None and u > 0:
                        pt = post_trade_caps(book, symbol=sym, pos=pos, units=min(u, float(pu or u)), bid=sbid,
                                             close_fee=_f(l.get("close_fee_usd")) or 0.0, sleeve_map=sleeve_map)
                        if not pt["ok"]:
                            pt["alternatives"] = _risk_exit_alternatives(reason, sold_symbol=sym, book=book,
                                                                         cash=cash, sleeve_map=sleeve_map)
                        out["risk_exit_post_trade_caps"] = pt
                        c.check(f"risk_exit_post_trade_caps{tag}", pt["ok"],
                                {"cascade": pt["cascade"], "denominator": pt["denominator"],
                                 "alternatives": pt.get("alternatives")}, "RISK_EXIT_POST_TRADE_CAP_CASCADE")
            base = {"symbol": sym, "units": u, "spread_usd": l.get("spread_usd"), "close_fee_usd": l.get("close_fee_usd"),
                    "overnight_usd": l.get("overnight_usd"), "realized_pnl_usd": rp_tax}
            anchor_legs[i] = {**base, "bid": a_bid, "ask": a_ask}
            # realized for the live gate uses the live bid (same max rule)
            live_legs[i] = {**base, "bid": lbid, "ask": lask, "quote_ts": lts, "independent_mark": lv.get("independent_mark")}
            if c.check(f"prepare_response_given{tag}", bool(pr), None, "PREPARE_RESPONSE_MISSING"):
                pe = verify_close_prepare(pr, payload)
                c.check(f"prepare_matches_payload{tag}", not pe, pe, "PREPARE_MISMATCH")
            payloads.append(payload)
            echoes.append(close_echo(pr) if pr else {})
        else:
            _cross_book(c, tag, sym, iid, mv or {})
            req = _f(l.get("units")) or 0.0
            of = _f(l.get("open_fee_usd"))
            if not c.check(f"open_fee_given{tag}", of is not None and of >= 0, l.get("open_fee_usd"), "OPEN_FEE_REQUIRED"):
                of = 0.0
            fu = _floor_units(req)
            if cash is not None and a_ask:
                fu = min(fu, _floor_units((cash - CASH_FLOOR_USD - of) / a_ask))
            ac = (res or {}).get("assetClass")
            fu, shrink, info = _caps(c, symbol=sym, asset_class=ac, ask=a_ask or 1.0, fu=fu, book=book,
                                     sleeve=l.get("sleeve"), sleeve_map=sleeve_map, tag=tag)
            out.update(info)
            c.check(f"size_within_limits{tag}", fu >= _floor_units(req) and req > 0,
                    {"requested": req, "max_units": fu, "shrink": shrink}, "SIZE_EXCEEDS_LIMITS")
            fu = _floor_units(req)
            out[f"cash_after{tag}"] = _cash_checks(c, tag, cash=cash, fu=fu, sizing_ask=a_ask, live_ask=lask, open_fee=of)
            c.check(f"min_position{tag}", fu * (a_ask or 0) >= MIN_POSITION_USD, {"notional": round(fu * (a_ask or 0), 2)},
                    "BELOW_MIN_POSITION")
            recent = _recent_positions(book, iid, now) if book.get("ok") else []
            c.check(f"no_position_opened_24h{tag}", not recent, {"positions": recent}, "RECENT_POSITION_24H")
            srow = CG.score_row(scores, sym)
            atr_d = _f((srow or {}).get("atr14"))
            slb = _sl_bounds_ok(_f(l.get("stop_loss")), a_ask or 0.0, atr_d, ac)
            c.check(f"sl_bounds{tag}", slb["ok"], slb, "SL_OUT_OF_BOUNDS")
            _sl_check(c, tag, l.get("stop_loss"), lbid)
            if l.get("take_profit") is not None:
                c.check(f"take_profit_valid{tag}", (_f(l.get("take_profit")) or 0) > (a_ask or 0),
                        l.get("take_profit"), "TAKE_PROFIT_INVALID")
            payload = {"account": P["account"], "direction": "buy", "instrumentId": iid, "units": fu, "leverage": 1,
                       "orderType": "mkt", "stopLossRate": _f(l.get("stop_loss")), "takeProfitRate": _f(l.get("take_profit"))}
            base = {"symbol": sym, "units": fu, "spread_usd": l.get("spread_usd"), "open_fee_usd": l.get("open_fee_usd"),
                    "close_fee_usd": l.get("close_fee_usd"), "overnight_usd": l.get("overnight_usd"),
                    "stop_loss": l.get("stop_loss")}
            anchor_legs[i] = {**base, "bid": a_bid, "ask": a_ask}
            live_legs[i] = {**base, "bid": lbid, "ask": lask, "quote_ts": lts, "independent_mark": lv.get("independent_mark")}
            if c.check(f"prepare_response_given{tag}", bool(pr), None, "PREPARE_RESPONSE_MISSING"):
                pe = verify_buy_prepare(pr, payload)
                c.check(f"prepare_matches_payload{tag}", not pe, pe, "PREPARE_MISMATCH")
            payloads.append(payload)
            echoes.append(buy_echo(pr) if pr else {})

    def gate(stage: str, L: dict[int, dict]) -> Optional[dict]:
        try:
            if kind == "rotation":
                return CG.evaluate_rotation(sell=L[sells[0]], buy=L[buys[0]], edge_ref=pack.get("edge_ref"),
                                            scores=scores, stage=stage, now=now)
            leg = L[(buys or sells)[0]]
            px = leg["ask"] if kind == "rebalance_add" else leg["bid"]
            return CG.evaluate(kind=kind, entry=px or 1.0, units=leg["units"], bid=leg["bid"], ask=leg["ask"],
                               quote_ts=leg.get("quote_ts"), independent_mark=leg.get("independent_mark"),
                               spread_usd=leg.get("spread_usd"), open_fee_usd=leg.get("open_fee_usd"),
                               close_fee_usd=leg.get("close_fee_usd"), overnight_usd=leg.get("overnight_usd"),
                               realized_pnl_usd=leg.get("realized_pnl_usd"), edge_ref=pack.get("edge_ref"),
                               scores=scores, symbol=leg["symbol"], stop_loss=leg.get("stop_loss"),
                               risk_exit=bool(pack.get("risk_exit")), risk_exit_reason=pack.get("risk_exit_reason"),
                               risk_exit_verified=risk_ok, stage=stage, now=now)
        except (TypeError, ValueError, KeyError) as exc:
            return {"verdict": CG.VERDICT_INVALID, "errors": [str(exc)]}

    anchor_cg, live_cg = gate("anchor", anchor_legs), gate("final", live_legs)
    out["cost_gate_anchor"], out["cost_gate"] = anchor_cg, live_cg
    okv = (CG.VERDICT_PASS, CG.VERDICT_RISK_EXIT) if (kind in ("trim", "sell") and pack.get("risk_exit")) else (CG.VERDICT_PASS,)
    for nm, g in (("anchor_cost_gate", anchor_cg), ("final_cost_gate", live_cg)):
        c.check(nm, g is not None and g.get("verdict") in okv, _gate_summary(g), (g or {}).get("verdict") or "COST_GATE_SKIP")
    out["order_payloads"] = payloads
    binding = {"pack": pack, "order_payloads": payloads, "prepare_echo": echoes, "test_mode": P["test_mode"]}
    out["pack_sha256"] = canonical_sha(binding)
    out["order_qa_verdict_path"] = str(order_verdict_path(out["pack_sha256"]))
    pk = ["rebal", kind, sorted([[legs[i].get("instrumentId"), legs[i].get("side")] for i in range(len(legs))],
                                key=lambda x: (str(x[0]), str(x[1]))), et_date(now)]
    lps = _locks_check(c, pk, leg_lock_parts)
    pre = list(c.blockers)
    vp = order_verdict_path(out["pack_sha256"])
    ok, why = check_verdict(vp, skill=ORDER_QA_SKILL, max_age_s=ORDER_QA_MAX_AGE_S, now=now, pack_id=pack_id,
                            pack_sha256=out["pack_sha256"], anchor_gate=anchor_cg)
    c.check("order_qa_pass", ok, why, "ORDER_QA_NOT_PASS" if vp.exists() else "ORDER_QA_PENDING")
    out["ready_for_order_qa"] = not pre
    return _finish(out, c, lps, write_lock)


# ---------------------------------------------------------------- CLI
def write_audit(result: dict[str, Any]) -> Path:
    ts = datetime.now(IDT).strftime("%Y%m%d-%H%M%S")
    pid = re.sub(r"[^A-Za-z0-9._-]", "_", str(result.get("pack_id") or "NA"))
    path = Path(paths()["audit_dir"]) / f"execute-pass-{pid}-{ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Classic final pre-place checks (GO/NO-GO). Never calls eToro. "
                                            "Paths are fixed (classic_rsi/paths.py).")
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--pack-id", help="<auto_run_id>#<SYMBOL> (RSI buy pack)")
    m.add_argument("--rebalance-pack", help="JSON rebalance action pack (static, hashed)")
    p.add_argument("--live", help="rebalance: JSON {legs:[{bid, ask, quote_ts, independent_mark, prepare_response}]}")
    p.add_argument("--bid", type=float)
    p.add_argument("--ask", type=float)
    p.add_argument("--quote-ts")
    p.add_argument("--mark", type=float, help="REQUIRED second-source live mark (ask within 0.1%%)")
    p.add_argument("--anchor-ask", type=float)
    p.add_argument("--anchor-bid", type=float)
    p.add_argument("--prepare-response", help="JSON file: the prepare-trade response for the pinned payload")
    p.add_argument("--units", type=float)
    p.add_argument("--amount", type=float)
    p.add_argument("--open-fee", type=float)
    p.add_argument("--close-fee", type=float)
    p.add_argument("--overnight", type=float)
    p.add_argument("--spread-usd", type=float)
    p.add_argument("--sleeve")
    p.add_argument("--sleeve-map")
    p.add_argument("--hold", action="store_true")
    p.add_argument("--momentum-response", help="fix8b: YOUR raw user-Momentum-HHHGDTJ get-my-positions-and-orders "
                                               "response saved for this GO (required for any buy)")
    p.add_argument("--momentum-captured-at", help="ISO time (tz) when you received that response (<= 60 s before GO)")
    p.add_argument("--momentum-source", default=None, help="MCP namespace of the read; must be user-Momentum-HHHGDTJ")
    p.add_argument("--momentum-parent-response", help="optional user-etoro read for the mirror 11630170 cross-check")
    p.add_argument("--no-write", action="store_true", help="skip the audit JSON (GO locks are still written)")
    a = p.parse_args(argv)
    smap = json.loads(Path(a.sleeve_map).read_text()) if a.sleeve_map else None
    mread = None
    if a.momentum_response:
        mread = {"source": a.momentum_source, "captured_at": a.momentum_captured_at,
                 "response": MH.extract_json(Path(a.momentum_response).read_text()),
                 "parent_response": (MH.extract_json(Path(a.momentum_parent_response).read_text())
                                     if a.momentum_parent_response else None)}
    if a.rebalance_pack:
        live = json.loads(Path(a.live).read_text()) if a.live else None
        res = run_rebalance_checks(pack=json.loads(Path(a.rebalance_pack).read_text()), live=live,
                                   sleeve_map=smap, hold=a.hold, momentum_read=mread)
    else:
        pr = json.loads(Path(a.prepare_response).read_text()) if a.prepare_response else None
        res = run_checks(pack_id=a.pack_id, mark=a.mark, bid=a.bid, ask=a.ask, quote_ts=a.quote_ts,
                         prepare_response=pr, anchor_ask=a.anchor_ask, anchor_bid=a.anchor_bid, units=a.units,
                         amount_usd=a.amount, open_fee_usd=a.open_fee, close_fee_usd=a.close_fee,
                         overnight_usd=a.overnight, spread_usd=a.spread_usd, sleeve=a.sleeve, sleeve_map=smap,
                         hold=a.hold, momentum_read=mread)
    if not a.no_write:
        res["audit_path"] = str(write_audit(res))
    print(json.dumps(res, indent=2, default=str))
    print(f"{res['decision']} {res['pack_id']} test_mode={res.get('test_mode')} blockers={res['blockers'] or 'none'}",
          file=sys.stderr)
    return 0 if res["decision"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())

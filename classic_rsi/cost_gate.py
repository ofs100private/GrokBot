"""Cost/benefit gate for Classic (OfersClaw5-PRIYN) — mandatory before every place.

v3 (2026-10-12, QA fix2 for qa-review-classic-full-auto-fix1-20261012.json).

Rule (Ofer 2026-10-11):  PASS iff  total_cost > 0  AND  EV_after_tax >= 2 x total_cost
                          AND  expected_net_gain = EV_after_tax - total_cost > 0
COST_GATE_SKIP = no / not enough evidenced edge. COST_GATE_INVALID = bad or missing inputs.
RISK_EXIT = a hard risk exit VERIFIED from data by execute_pass (never self-declared).

Round-trip cost (USD), all >= 0
    spread     = max(spread_usd, (ask - bid) x units)
    open_fee   = prepare/getCost (buy legs)   — anchor/final: REQUIRED
    close_fee  = prepare/getCost              — anchor/final: REQUIRED
    overnight  = prepare/getCost (0 for x1 long real stock/ETF)
    tax_est    = TAX_RATE x max(realized_pnl, 0) on every SELL leg (realized is recomputed
                 from the book by execute_pass; the larger of declared/recomputed is used)
    total_cost = spread + open_fee + close_fee + overnight + tax_est   (> 0)
Preliminary only: 0.15% spread and $0.75 per order (real Classic fills 2026-10-07).

Expected gain = directional EV, after tax (x (1 - TAX_RATE) when > 0)
    rsi_buy:  EV = units x [p x (TP - ask) - (1 - p) x (ask - SL)]
              p is NEVER typed: p = Wilson 95% lower bound of wins/n from an entry in the
              sha-pinned evidence/p_registry.json, usable only if out_of_sample and n >= 100.
              The only entry today (1H backtest 12/19, in-sample) is not usable -> SKIP.
    rebalance_add / trim / sell / rotation: edge_ref = {evidence_id} pointing into the
              sha-pinned evidence/edge_registry.json (out_of_sample, n >= 30, horizon >= 5 d).
              er_pct = intercept_pct + per_score_pct x score (score is a FRACTION, calibration.score_units='fraction'), with score/ATR read from the fixed
              score file — never typed — and |er| capped at 2 x daily ATR% x sqrt(horizon).
              add: notional x er; trim/sell: -notional x er_held; rotation (ONE gate):
              buy_notional x (er_new - er_held). The registry ships with no entries -> SKIP.

Stages
    preliminary : in-script, assumed costs, never binding.
    anchor      : the quote QA reviews (qa_ask); fees required; no freshness check. Order-QA
                  recomputes these numbers (+/-0.01).
    final       : live quote <= 60 s, mandatory second-source mark within 0.1% of ask.

This module never calls eToro and never places.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .paths import paths

VERSION = "classic-cost-gate-v3-20261012-fix2"
RULE = "total_cost > 0 and EV_after_tax >= 2 x total_cost and EV_after_tax - total_cost > 0"
MULTIPLIER = 2.0

TAX_RATE = 0.25  # conservative: Israeli capital-gains rate 25%
DEFAULT_SPREAD_PCT = 0.0015  # PRELIMINARY ONLY
DEFAULT_FEE_SOURCE = "real Classic fills 2026-10-07 (ADBE/GS/CAT $500 each) charged $0.75 per order on keys"
DEFAULT_OPEN_FEE_USD = 0.75  # PRELIMINARY ONLY
DEFAULT_CLOSE_FEE_USD = 0.75  # PRELIMINARY ONLY
DEFAULT_OVERNIGHT_USD = 0.0
DEFAULT_NOTIONAL_USD = 500.0
DEFAULT_HOLD_DAYS = 20
QUOTE_MAX_AGE_S = 60
MARK_TOL = 0.001  # 0.1%

# Evidence registries (sha pinned; production refuses a modified file).
P_REGISTRY_SHA256 = "a48eac6194fb025b57bfd522ddfb42a9b73b1abf3543cb25cee55f7ad6adc0c3"
EDGE_REGISTRY_SHA256 = "7ccee3ad8ac1235499c3fbc053526b9baeb9d083fdfdacd29a86358f82a349bf"
DEFAULT_P_EVIDENCE_ID = "classic_rsi_1h_bt_20260919"
P_MIN_N = 100
SCORE_UNITS = "fraction"
EDGE_MIN_N = 30
EDGE_MIN_HORIZON_DAYS = 5
EDGE_CAP_ATR_MULT = 2.0
EDGE_METHODS = ("rs_expected_return", "trend_expected_return")

VERDICT_PASS = "PASS"
VERDICT_SKIP = "COST_GATE_SKIP"
VERDICT_INVALID = "COST_GATE_INVALID"
VERDICT_RISK_EXIT = "RISK_EXIT"
KINDS = ("rsi_buy", "rebalance_add", "trim", "sell")
RISK_EXIT_REASONS = ("stop_hit", "trigger_3_50dma_neg_rs", "trigger_4_200dma", "hard_cap_breach",
                     "cash_below_floor")


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _r(x: Optional[float], n: int = 4) -> Optional[float]:
    return None if x is None else round(float(x), n)


def _parse_ts(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        d = ts
    else:
        try:
            d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else None  # naive timestamps are rejected (ambiguous zone)


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    ph = wins / n
    return (ph + z * z / (2 * n) - z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def load_registry(name: str) -> tuple[dict, dict]:
    """name: 'p' or 'edge'. Production enforces the pinned sha; test mode only records it."""
    P = paths()
    path = Path(P["evidence_dir"]) / f"{name}_registry.json"
    pinned = P_REGISTRY_SHA256 if name == "p" else EDGE_REGISTRY_SHA256
    meta = {"path": str(path), "pinned_sha256": pinned, "test_mode": P["test_mode"]}
    if not path.exists():
        meta["error"] = "REGISTRY_MISSING"
        return {"entries": []}, meta
    raw = path.read_bytes()
    meta["sha256"] = hashlib.sha256(raw).hexdigest()
    if meta["sha256"] != pinned and not P["test_mode"]:
        meta["error"] = "REGISTRY_SHA_MISMATCH"
        return {"entries": []}, meta
    return json.loads(raw), meta


def p_from_registry(evidence_id: Optional[str]) -> dict[str, Any]:
    reg, meta = load_registry("p")
    out: dict[str, Any] = {"evidence_id": evidence_id, "registry": meta, "p": None, "skip": [], "errors": []}
    if meta.get("error"):
        out["errors"].append(meta["error"])
        return out
    ent = next((e for e in reg.get("entries") or [] if e.get("id") == evidence_id), None)
    if ent is None:
        out["skip"].append("P_EVIDENCE_NOT_IN_REGISTRY")
        return out
    w, n = int(ent.get("wins") or 0), int(ent.get("n") or 0)
    out.update(wins=w, n=n, out_of_sample=bool(ent.get("out_of_sample")), point=(w / n if n else None),
               p=wilson_lower(w, n), source=ent.get("source"))
    if not ent.get("out_of_sample"):
        out["skip"].append("P_EVIDENCE_NOT_OUT_OF_SAMPLE")
    if n < P_MIN_N:
        out["skip"].append(f"P_EVIDENCE_N_LT_{P_MIN_N}")
    return out


def score_row(scores: Optional[dict], symbol: str) -> Optional[dict]:
    for r in (scores or {}).get("rows") or []:
        if str(r.get("symbol", "")).upper() == symbol.upper():
            return r
    return None


def resolve_edge(edge_ref: Any, *, symbol: Optional[str], held_symbol: Optional[str] = None,
                 scores: Optional[dict] = None, kind: str = "rebalance_add") -> dict[str, Any]:
    """Recompute er from the registry calibration + score file. Typed returns are ignored."""
    out: dict[str, Any] = {"edge_ref": edge_ref, "skip": [], "errors": []}
    if not isinstance(edge_ref, dict) or not edge_ref.get("evidence_id"):
        out["skip"].append("EDGE_MISSING")
        return out
    typed = [k for k in ("expected_return_pct", "held_expected_return_pct") if k in edge_ref]
    if typed:
        out["ignored_typed_fields"] = typed
    reg, meta = load_registry("edge")
    out["registry"] = meta
    if meta.get("error"):
        out["errors"].append(meta["error"])
        return out
    ent = next((e for e in reg.get("entries") or [] if e.get("id") == edge_ref["evidence_id"]), None)
    if ent is None:
        out["skip"].append("EDGE_EVIDENCE_NOT_IN_REGISTRY")
        return out
    h = _f(ent.get("horizon_days")) or 0.0
    if ent.get("method") not in EDGE_METHODS:
        out["skip"].append("EDGE_METHOD_NOT_ALLOWED")
    if not ent.get("out_of_sample"):
        out["skip"].append("EDGE_EVIDENCE_NOT_OUT_OF_SAMPLE")
    if int(ent.get("n") or 0) < EDGE_MIN_N:
        out["skip"].append(f"EDGE_EVIDENCE_N_LT_{EDGE_MIN_N}")
    if h < EDGE_MIN_HORIZON_DAYS:
        out["skip"].append(f"EDGE_HORIZON_LT_{EDGE_MIN_HORIZON_DAYS}D")
    cal = ent.get("calibration") or {}
    ic, sl = _f(cal.get("intercept_pct")), _f(cal.get("per_score_pct"))
    if ic is None or sl is None:
        out["skip"].append("EDGE_CALIBRATION_MISSING")
        return out
    # fix4: units contract — score is a FRACTION (0.05 = +5 pp RS vs SPY) in both registry and score file;
    # er_pct = intercept_pct + per_score_pct x score_fraction.
    if cal.get("score_units") != SCORE_UNITS:
        out["skip"].append("EDGE_SCORE_UNITS_NOT_FRACTION")
        return out
    if scores is not None and scores.get("score_units") != SCORE_UNITS:
        out["skip"].append("SCORE_FILE_UNITS_NOT_FRACTION")
        return out

    def er_for(sym: str, tag: str) -> Optional[float]:
        r = score_row(scores, sym)
        if r is None or _f(r.get("score")) is None or not _f(r.get("atr14")) or not _f(r.get("last_close")):
            out["skip"].append(f"SCORE_DATA_MISSING_{tag}")
            return None
        raw = ic + sl * float(r["score"])
        cap = EDGE_CAP_ATR_MULT * (float(r["atr14"]) / float(r["last_close"]) * 100.0) * math.sqrt(max(h, 0.0))
        er = max(-cap, min(cap, raw))
        out[f"{tag}_score"] = r["score"]
        out[f"{tag}_er_raw_pct"] = round(raw, 4)
        out[f"{tag}_cap_pct"] = round(cap, 4)
        out[f"{tag}_capped"] = abs(raw) > cap
        return er

    out.update(evidence_id=ent["id"], method=ent.get("method"), n=ent.get("n"), horizon_days=h,
               source=ent.get("source"), calibration=cal)
    if kind == "rotation":
        out["expected_return_pct"] = er_for(symbol or "", "new")
        out["held_expected_return_pct"] = er_for(held_symbol or "", "held")
    elif kind == "rebalance_add":
        out["expected_return_pct"] = er_for(symbol or "", "new")
    else:
        out["held_expected_return_pct"] = er_for(symbol or "", "held")
    return out


def quote_errors(*, bid: Any, ask: Any, quote_ts: Any, now: Optional[datetime] = None,
                 independent_mark: Any = None, max_age_s: float = QUOTE_MAX_AGE_S,
                 require_mark: bool = True) -> list[str]:
    """Final-stage live-quote checks. Empty list = OK."""
    errs: list[str] = []
    b, a = _f(bid), _f(ask)
    if b is None or a is None:
        errs.append("QUOTE_MISSING")
        return errs
    if b <= 0 or a <= 0 or b >= a:
        errs.append("QUOTE_BID_GE_ASK_OR_NONPOSITIVE")
    t = _parse_ts(quote_ts)
    now = now or datetime.now(timezone.utc)
    if t is None:
        errs.append("QUOTE_TS_MISSING")
    else:
        age = (now - t).total_seconds()
        if age > max_age_s or age < -5:
            errs.append(f"QUOTE_STALE(age={age:.0f}s>{max_age_s:.0f}s)")
    m = _f(independent_mark)
    if m is None or m <= 0:
        if require_mark:
            errs.append("SECOND_SOURCE_MARK_MISSING")
    elif a and abs(a - m) / m > MARK_TOL:
        errs.append("ASK_VS_MARK_GT_0.1PCT")
    return errs


def _leg_costs(*, side: str, units: float, price: float, bid, ask, spread_usd, open_fee_usd, close_fee_usd,
               overnight_usd, realized_pnl_usd, tax_rate, final: bool, errors: list, assumptions: list,
               src: dict, tag: str = "") -> dict[str, float]:
    """Cost of one leg. side='buy' (round trip: open+close+spread) or 'sell' (close + spread + tax)."""
    k = (lambda s: f"{tag}{s}")
    for nm, v in (("spread_usd", spread_usd), ("open_fee", open_fee_usd), ("close_fee", close_fee_usd),
                  ("overnight", overnight_usd)):
        if v is not None and (_f(v) is None or _f(v) < 0):
            errors.append(f"NEGATIVE_OR_BAD_{k(nm).upper()}")
    b, a = _f(bid), _f(ask)
    live = ((a - b) * units) if (b is not None and a is not None and a > b > 0) else None
    su = _f(spread_usd)
    if su is not None and su >= 0 and live is not None:
        spread = max(su, live)
        src[k("spread")] = "max(getCost spread_usd, live (ask-bid) x units)"
    elif live is not None:
        spread = live
        src[k("spread")] = "live bid/ask"
    elif su is not None and su >= 0:
        spread = su
        src[k("spread")] = "prepare/getCost"
        if final:
            errors.append(f"{k('QUOTE').upper()}_MISSING")
    else:
        spread = units * price * DEFAULT_SPREAD_PCT
        src[k("spread")] = "assumed_default"
        assumptions.append(f"{tag}spread assumed {DEFAULT_SPREAD_PCT * 100:.2f}% of notional")

    def fee(v, default, name):
        fv = _f(v)
        if fv is not None and fv >= 0:
            src[k(name)] = "prepare/getCost"
            return fv
        if fv is None and v is None:
            if final:
                errors.append(f"{k(name).upper()}_REQUIRED")
            src[k(name)] = "assumed_default"
            assumptions.append(f"{tag}{name} assumed ${default:.2f} ({DEFAULT_FEE_SOURCE})")
            return default
        return 0.0  # negative: already an error

    of = fee(open_fee_usd, DEFAULT_OPEN_FEE_USD, "open_fee") if side == "buy" else 0.0
    cf = fee(close_fee_usd, DEFAULT_CLOSE_FEE_USD, "close_fee")
    on = _f(overnight_usd)
    if on is None or on < 0:
        on = DEFAULT_OVERNIGHT_USD
        src.setdefault(k("overnight"), "x1 long real stock: 0")
    rp = _f(realized_pnl_usd) if side == "sell" else None
    if side == "sell" and rp is None:
        errors.append(f"{k('REALIZED_PNL').upper()}_REQUIRED_FOR_SELL")
    tax = tax_rate * max(rp or 0.0, 0.0) if side == "sell" else 0.0
    return {"spread": spread, "open_fee": of, "close_fee": cf, "overnight": on, "tax_est": tax,
            "realized_pnl": rp, "total_cost": spread + of + cf + on + tax}


def _verdict(eg_after: Optional[float], total: float, errors: list, risk_exit: bool) -> tuple[str, Any, Any]:
    net = None if eg_after is None else eg_after - total
    ratio = None if (eg_after is None or total <= 0) else eg_after / total
    if total <= 0 and not risk_exit:
        errors.append("TOTAL_COST_NOT_POSITIVE")
    if errors:
        return VERDICT_INVALID, net, ratio
    if risk_exit:
        return VERDICT_RISK_EXIT, net, ratio
    if eg_after is not None and ratio is not None and eg_after >= MULTIPLIER * total and net > 0:
        return VERDICT_PASS, net, ratio
    return VERDICT_SKIP, net, ratio


def _block(*, stage, kind, inputs, costs, eg_raw, eg_after, net, ratio, method, verdict, assumptions, errors,
           skip_reasons, legs=None):
    b = {
        "version": VERSION, "stage": stage, "binding": stage == "final" and verdict != VERDICT_INVALID,
        "kind": kind, "rule": RULE, "inputs": inputs,
        "costs": {kk: _r(costs[kk]) for kk in ("spread", "open_fee", "close_fee", "overnight", "tax_est",
                                                 "total_cost")},
        "spread": _r(costs["spread"]), "fees": _r(costs["open_fee"] + costs["close_fee"]),
        "overnight": _r(costs["overnight"]), "realized_pnl": costs.get("realized_pnl"),
        "tax_est": _r(costs["tax_est"]), "total_cost": _r(costs["total_cost"]),
        "expected_gain_pre_tax": _r(eg_raw), "expected_gain": _r(eg_after),
        "expected_net_gain": _r(net), "ratio": _r(ratio, 3),
        "method": method, "verdict": verdict, "assumptions": assumptions, "errors": errors,
        "skip_reasons": skip_reasons,
    }
    if legs is not None:
        b["legs"] = legs
    return b


def _quote_stage_errors(stage, *, bid, ask, quote_ts, now, independent_mark) -> list[str]:
    if stage == "final":
        return quote_errors(bid=bid, ask=ask, quote_ts=quote_ts, now=now, independent_mark=independent_mark)
    b, a = _f(bid), _f(ask)
    if stage == "anchor" and (b is None or a is None):
        return ["ANCHOR_QUOTE_MISSING"]
    if b is not None and a is not None and (b <= 0 or a <= 0 or b >= a):
        return ["QUOTE_BID_GE_ASK_OR_NONPOSITIVE"]
    return []


def evaluate(
    *,
    kind: str,
    entry: float,
    units: Optional[float] = None,
    notional_usd: Optional[float] = None,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
    quote_ts: Any = None,
    independent_mark: Optional[float] = None,
    spread_usd: Optional[float] = None,
    open_fee_usd: Optional[float] = None,
    close_fee_usd: Optional[float] = None,
    overnight_usd: Optional[float] = None,
    take_profit: Optional[float] = None,
    stop_loss: Optional[float] = None,
    p_evidence_id: Optional[str] = DEFAULT_P_EVIDENCE_ID,
    edge_ref: Optional[dict] = None,
    scores: Optional[dict] = None,
    symbol: Optional[str] = None,
    realized_pnl_usd: Optional[float] = None,
    risk_exit: bool = False,
    risk_exit_reason: Optional[str] = None,
    risk_exit_verified: bool = False,
    tax_rate: float = TAX_RATE,
    stage: str = "preliminary",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """cost_gate block for one single-leg action. Pure (reads only the pinned registries)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS} (rotation: evaluate_rotation)")
    strict = stage in ("anchor", "final")
    errors: list[str] = []
    skip: list[str] = []
    assumptions: list[str] = []
    src: dict[str, str] = {}
    e = _f(entry)
    if e is None or e <= 0:
        errors.append("ENTRY_NOT_POSITIVE")
        e = 1.0
    u, n = _f(units), _f(notional_usd)
    if (units is not None and (u is None or u <= 0)) or (notional_usd is not None and (n is None or n <= 0)):
        errors.append("UNITS_OR_NOTIONAL_NOT_POSITIVE")
        u = u if (u and u > 0) else None
        n = n if (n and n > 0) else None
    if u is None and n is None:
        if strict:
            errors.append("UNITS_REQUIRED")
        n = DEFAULT_NOTIONAL_USD
        assumptions.append(f"notional assumed ${DEFAULT_NOTIONAL_USD:.0f} (pack unsized)")
        src["notional"] = "assumed_default"
    if u is None:
        u = n / e
    notional = u * e
    errors += _quote_stage_errors(stage, bid=bid, ask=ask, quote_ts=quote_ts, now=now,
                                  independent_mark=independent_mark)
    if not (0.0 <= tax_rate < 1.0):
        errors.append("TAX_RATE_OUT_OF_RANGE")
    side = "buy" if kind in ("rsi_buy", "rebalance_add") else "sell"
    costs = _leg_costs(side=side, units=u, price=e, bid=bid, ask=ask, spread_usd=spread_usd,
                       open_fee_usd=open_fee_usd, close_fee_usd=close_fee_usd, overnight_usd=overnight_usd,
                       realized_pnl_usd=realized_pnl_usd, tax_rate=tax_rate, final=strict and not risk_exit,
                       errors=errors, assumptions=assumptions, src=src)
    if strict and assumptions and not risk_exit:
        errors.append("ASSUMED_INPUTS_AT_" + stage.upper())
    if risk_exit and (risk_exit_reason not in RISK_EXIT_REASONS or not risk_exit_verified):
        errors.append("RISK_EXIT_NOT_VERIFIED")

    eg_raw: Optional[float] = None
    breakeven = None
    p_info: Optional[dict] = None
    edge_info: Optional[dict] = None
    if kind == "rsi_buy":
        tp, sl = _f(take_profit), _f(stop_loss)
        p_info = p_from_registry(p_evidence_id)
        errors += p_info["errors"]
        skip += p_info["skip"]
        pp = p_info.get("p")
        if tp is None or sl is None or not (0 < sl < e < tp):
            errors.append("TP_SL_INVALID(need 0<SL<entry<TP)")
            method = "rsi_ev: TP/SL invalid"
        elif pp is None:
            method = f"rsi_ev: no usable p ({', '.join(p_info['skip'] + p_info['errors'])})"
        else:
            breakeven = (e - sl) / (tp - sl)
            eg_raw = u * (pp * (tp - e) - (1 - pp) * (e - sl))
            method = (f"rsi_ev: units x [p x (TP-ask) - (1-p) x (ask-SL)]; p=Wilson95 lower of "
                      f"{p_info['wins']}/{p_info['n']} = {pp:.4f} (registry {p_evidence_id}, "
                      f"out_of_sample={p_info['out_of_sample']}); break-even p={breakeven:.4f}; x(1-{tax_rate}) if >0")
            if pp <= breakeven + 1e-9:
                skip.append("P_AT_OR_BELOW_BREAKEVEN")
    elif risk_exit:
        method = f"{kind}: verified risk exit ({risk_exit_reason}); gain not required"
    else:
        edge_info = resolve_edge(edge_ref, symbol=symbol, scores=scores, kind=kind)
        errors += edge_info["errors"]
        skip += edge_info["skip"]
        er = edge_info.get("expected_return_pct" if side == "buy" else "held_expected_return_pct")
        if er is None or edge_info["skip"] or edge_info["errors"]:
            method = f"{kind}: evidenced edge required ({', '.join(edge_info['skip'] + edge_info['errors'])})"
        else:
            eg_raw = notional * er / 100.0 if side == "buy" else -notional * er / 100.0
            method = (f"{kind}: registry {edge_info['evidence_id']} ({edge_info['method']}, n={edge_info['n']}, "
                      f"{edge_info['horizon_days']:g}d) er={er:.4f}% from score file (capped 2xATR%xsqrt(h)); "
                      f"x(1-tax) if >0")
    eg_after = None if eg_raw is None else (eg_raw * (1 - tax_rate) if eg_raw > 0 else eg_raw)
    verdict, net, ratio = _verdict(eg_after, costs["total_cost"], errors, risk_exit and not errors)
    if skip and verdict == VERDICT_PASS:
        verdict = VERDICT_SKIP
    inputs = {
        "entry": _r(e), "units": _r(u, 6), "notional_usd": _r(notional, 2), "bid": _f(bid), "ask": _f(ask),
        "quote_ts": None if quote_ts is None else str(quote_ts), "independent_mark": _f(independent_mark),
        "take_profit": _f(take_profit), "stop_loss": _f(stop_loss), "symbol": symbol,
        "p_hit": _r((p_info or {}).get("p")), "p_evidence": p_info, "p_breakeven": _r(breakeven),
        "edge": edge_info, "tax_rate": tax_rate,
        "realized_pnl_usd": costs.get("realized_pnl"), "risk_exit": bool(risk_exit),
        "risk_exit_reason": risk_exit_reason, "risk_exit_verified": bool(risk_exit_verified), "sources": src,
    }
    return _block(stage=stage, kind=kind, inputs=inputs, costs=costs, eg_raw=eg_raw, eg_after=eg_after,
                  net=net, ratio=ratio, method=method, verdict=verdict, assumptions=assumptions,
                  errors=errors, skip_reasons=skip)


def evaluate_rotation(*, sell: dict[str, Any], buy: dict[str, Any], edge_ref: Optional[dict],
                      scores: Optional[dict] = None, tax_rate: float = TAX_RATE, stage: str = "final",
                      now: Optional[datetime] = None) -> dict[str, Any]:
    """ONE combined gate for a rotation (sell held name -> buy replacement).

    sell/buy legs: {symbol, units, bid, ask, quote_ts, independent_mark, spread_usd, open_fee_usd (buy),
    close_fee_usd, realized_pnl_usd (sell, already max(declared, recomputed))}.
    total_cost = sell(spread + close fee + tax) + buy(spread + open + close fee)
    EV = buy_notional x (er_new - er_held)/100 from the registry + score file, x(1-tax) if > 0.
    """
    strict = stage in ("anchor", "final")
    errors: list[str] = []
    skip: list[str] = []
    assumptions: list[str] = []
    src: dict[str, str] = {}
    legs = []
    tot = {"spread": 0.0, "open_fee": 0.0, "close_fee": 0.0, "overnight": 0.0, "tax_est": 0.0,
           "total_cost": 0.0, "realized_pnl": None}
    notional_buy = None
    for side, leg in (("sell", sell), ("buy", buy)):
        u = _f(leg.get("units"))
        px = _f(leg.get("bid" if side == "sell" else "ask"))
        if u is None or u <= 0 or px is None or px <= 0:
            errors.append(f"{side.upper()}_LEG_UNITS_OR_PRICE_INVALID")
            u, px = (u if u and u > 0 else 1.0), (px if px and px > 0 else 1.0)
        errors += [f"{side.upper()}_{x}" for x in _quote_stage_errors(
            stage, bid=leg.get("bid"), ask=leg.get("ask"), quote_ts=leg.get("quote_ts"), now=now,
            independent_mark=leg.get("independent_mark"))]
        c = _leg_costs(side=side, units=u, price=px, bid=leg.get("bid"), ask=leg.get("ask"),
                       spread_usd=leg.get("spread_usd"), open_fee_usd=leg.get("open_fee_usd"),
                       close_fee_usd=leg.get("close_fee_usd"), overnight_usd=leg.get("overnight_usd"),
                       realized_pnl_usd=leg.get("realized_pnl_usd"), tax_rate=tax_rate, final=strict,
                       errors=errors, assumptions=assumptions, src=src, tag=f"{side}_")
        legs.append({"side": side, "symbol": leg.get("symbol"), "units": _r(u, 6), "price": px,
                     "notional_usd": _r(u * px, 2), **{kk: _r(v) for kk, v in c.items() if kk != "realized_pnl"},
                     "realized_pnl": c.get("realized_pnl")})
        for kk in ("spread", "open_fee", "close_fee", "overnight", "tax_est", "total_cost"):
            tot[kk] += c[kk]
        if side == "sell":
            tot["realized_pnl"] = c.get("realized_pnl")
        else:
            notional_buy = u * px
    if strict and assumptions:
        errors.append("ASSUMED_INPUTS_AT_" + stage.upper())
    edge_info = resolve_edge(edge_ref, symbol=buy.get("symbol"), held_symbol=sell.get("symbol"), scores=scores,
                             kind="rotation")
    errors += edge_info["errors"]
    skip += edge_info["skip"]
    eg_raw = None
    ern, erh = edge_info.get("expected_return_pct"), edge_info.get("held_expected_return_pct")
    if ern is None or erh is None or edge_info["skip"] or edge_info["errors"]:
        method = f"rotation: evidenced edge required ({', '.join(edge_info['skip'] + edge_info['errors'])})"
    else:
        eg_raw = (notional_buy or 0.0) * (ern - erh) / 100.0
        method = (f"rotation: registry {edge_info['evidence_id']} buy_notional x (er_new {ern:.4f}% - er_held "
                  f"{erh:.4f}%) from score file; x(1-tax) if >0")
    eg_after = None if eg_raw is None else (eg_raw * (1 - tax_rate) if eg_raw > 0 else eg_raw)
    verdict, net, ratio = _verdict(eg_after, tot["total_cost"], errors, False)
    if skip and verdict == VERDICT_PASS:
        verdict = VERDICT_SKIP
    inputs = {"edge": edge_info, "tax_rate": tax_rate, "sources": src, "sell": sell, "buy": buy}
    return _block(stage=stage, kind="rotation", inputs=inputs, costs=tot, eg_raw=eg_raw, eg_after=eg_after,
                  net=net, ratio=ratio, method=method, verdict=verdict, assumptions=assumptions,
                  errors=errors, skip_reasons=skip, legs=legs)


def preliminary_for_pack(pack: dict[str, Any], *, notional_usd: Optional[float] = None) -> dict[str, Any]:
    """Preliminary (non-binding) gate for an RSI buy pack — assumed spread/fees, registry p."""
    lv = pack.get("levels") or {}
    sz = (pack.get("sizing") or {}).get("suggested_notional_usd")
    n = notional_usd if notional_usd is not None else _f(sz)
    cg = evaluate(kind="rsi_buy", entry=lv.get("entry"), notional_usd=n, take_profit=lv.get("take_profit"),
                  stop_loss=lv.get("stop_loss"), stage="preliminary")
    cg["note"] = ("PRELIMINARY: assumed spread/fees (no live eToro access in-script). Binding gate is "
                  "recomputed by execute_pass at the anchor (QA) quote and at the live quote.")
    return cg


def rebase_levels(pack: dict[str, Any], ask: float) -> dict[str, Any]:
    lv = pack.get("levels") or {}
    atr1h = _f(lv.get("atr"))
    if not atr1h or atr1h <= 0:
        return {"entry": _r(ask), "take_profit": None, "stop_loss": None, "atr_1h": atr1h, "rebased_on": "anchor ask"}
    return {"entry": _r(ask), "take_profit": _r(ask + float(lv.get("tp_mult", 2.0)) * atr1h),
            "stop_loss": _r(ask - float(lv.get("sl_mult", 1.5)) * atr1h), "atr_1h": atr1h,
            "rebased_on": "anchor ask"}


def rsi_gate(pack: dict[str, Any], *, bid: float, ask: float, units: float, quote_ts: Any,
             open_fee_usd: Optional[float], close_fee_usd: Optional[float], take_profit: float, stop_loss: float,
             overnight_usd: Optional[float] = None, spread_usd: Optional[float] = None,
             independent_mark: Optional[float] = None, stage: str = "final",
             now: Optional[datetime] = None) -> dict[str, Any]:
    """RSI gate at a given quote with the pinned (anchor-rebased) SL/TP."""
    return evaluate(kind="rsi_buy", entry=float(ask), units=units, bid=bid, ask=ask, quote_ts=quote_ts,
                    independent_mark=independent_mark, spread_usd=spread_usd, open_fee_usd=open_fee_usd,
                    close_fee_usd=close_fee_usd, overnight_usd=overnight_usd, take_profit=take_profit,
                    stop_loss=stop_loss, symbol=(pack.get("instrument") or {}).get("symbol"), stage=stage, now=now)

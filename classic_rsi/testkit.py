"""Test fixtures for the Classic FULL AUTO gate (test mode only). Never used in production.

Creates a temp root, points CLASSIC_EXEC_TEST_ROOT at it, and writes TEST-ONLY registries,
book, score file, envelopes, verdicts and prepare responses there.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .levels import atr_long_levels
from .paths import TEST_ENV, order_verdict_path, run_verdict_path
from .signals import RAW_BUY_80

IDT = ZoneInfo("Asia/Jerusalem")
MON = datetime(2026, 10, 12, 18, 0, tzinfo=IDT)  # 11:00 ET, regular session
RID = "classic-rsi-auto-20261012-175000-0a1b2c3d"
PRID = "classic-rsi-propose-20261012-175005-0a1b2c3d"
P_TEST = {"id": "classic_rsi_1h_bt_20260919", "wins": 130, "n": 200, "out_of_sample": True,
          "period": "TEST ONLY", "source": "TEST ONLY fixture"}
EDGE_TEST = {"id": "test_rs_oos", "method": "rs_expected_return", "n": 120, "out_of_sample": True,
             "horizon_days": 20, "calibration": {"intercept_pct": 0.0, "per_score_pct": 20.0, "score_units": "fraction"},
             "source": "TEST ONLY fixture"}
POS = [("QQQ", 3006, 830.65, 750.0, 677.9, 1.106357, 644.0),
       ("SMH", 6357, 778.16, 729.27, 564.35, 1.29223, 581.8),
       ("XLV", 3017, 774.44, 709.78, 156.44, 4.537045, 148.62),
       ("SPY", 3000, 705.82, 700.0, 771.62, 0.907182, 709.97),
       ("TMO", 1592, 509.15, 520.0, 520.0, 1.0, 470.0)]
SCORES = {"QQQ": (0.05, 751.27, 8.53, True, True, 0.01), "SMH": (0.08, 603.33, 13.5, True, True, 0.02),
          "XLV": (-0.05, 170.81, 2.75, True, True, -0.01), "XLE": (0.15, 95.0, 1.9, True, True, 0.03), "DIA": (0.15, 95.0, 1.9, True, True, 0.03),
          "TMO": (-0.2, 509.15, 12.0, False, False, -0.08), "SPY": (0.0, 778.57, 7.0, True, True, 0.0)}


def ts(now: datetime, s: float) -> str:
    return (now - timedelta(seconds=s)).isoformat()


@contextlib.contextmanager
def test_root():
    old = os.environ.get(TEST_ENV)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "audit" / "qa").mkdir(parents=True)
        (root / "evidence").mkdir()
        os.environ[TEST_ENV] = str(root)
        write_registries(root)
        write_momentum(root)
        try:
            yield root
        finally:
            if old is None:
                os.environ.pop(TEST_ENV, None)
            else:
                os.environ[TEST_ENV] = old


MOMENTUM_TEST = [("XOM", 1036), ("NTAP", 1796)]  # TEST ONLY; no overlap with the Classic test symbols


def momentum_response(now=MON, age_s=5, holdings=None, orders=None, mirrors=None, warnings=None, **kw):
    """TEST-ONLY raw user-Momentum-HHHGDTJ get-my-positions-and-orders response (fix8b)."""
    h = MOMENTUM_TEST if holdings is None else holdings
    r = {"account": "real", "statusCode": 200, "xRequestId": "test-xrid", "accountCurrency": "USD",
         "timestamp": (now - timedelta(seconds=age_s)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.%f0Z"),
         "direct": {"positions": [{"positionId": 9000 + n, "market": {"instrumentId": i, "symbol": s}, "direction": "long"}
                                  for n, (s, i) in enumerate(h)],
                    "orders": orders or []},
         "mirrors": mirrors or [], "warnings": warnings}
    r.update(kw)
    return r


def momentum_read(now=MON, age_s=5, captured_age_s=None, source="user-Momentum-HHHGDTJ", **kw):
    return {"source": source, "captured_at": ts(now, age_s if captured_age_s is None else captured_age_s),
            "response": momentum_response(now=now, age_s=age_s, **kw)}


def write_momentum(root: Path, now=MON, age_s=5, holdings=None):
    """TEST-ONLY pre-filter snapshot file (fix8/8b)."""
    from .momentum_holdings import build_snapshot, write_snapshot
    snap = build_snapshot(momentum_response(now=now, age_s=age_s, holdings=holdings))
    write_snapshot(snap, root / "momentum.json")
    return snap


def write_registries(root: Path, p_entries=None, edge_entries=None):
    (root / "evidence" / "p_registry.json").write_text(json.dumps({"entries": p_entries if p_entries is not None else [P_TEST]}))
    (root / "evidence" / "edge_registry.json").write_text(json.dumps({"entries": edge_entries if edge_entries is not None else [EDGE_TEST]}))


def make_pack(symbol="SPY", entry=700.0, atr=3.0, notional=None):
    from .propose import _buy_pack
    row = pd.Series({"raw_signal": RAW_BUY_80, "strength_tag": "EXTREME_80", "zone": "OVER_SOLD", "rsi": 18.0,
                     "close": entry})
    return _buy_pack(symbol=symbol, bar_time="2026-10-09 13:30:00+00:00", row=row, levels=atr_long_levels(entry, atr),
                     suggested_notional_usd=notional)


def write_book(root: Path, now=MON, age_s=10, cash=3671.18, equity=7270.38, extra=None, cost_override=None,
               value_override=None):
    pos = [{"symbol": s, "instrumentId": i, "value": (value_override or {}).get(s, v),
            "invested": (cost_override or {}).get(s, c), "openRate": o, "units": u, "stopLossRate": sl,
            "positionId": 1000 + n, "openTime": "2026-07-27T17:45:47.613", "leverage": 1}
           for n, (s, i, v, c, o, u, sl) in enumerate(POS)]
    pos += extra or []
    (root / "book.json").write_text(json.dumps({"asOf": ts(now, age_s), "equity": equity,
                                                "summary": {"availableCash": cash}, "positions": pos}))
    write_history(root, now=now)
    write_prebuy(root, now=now)


def write_prebuy(root: Path, now=MON, age_s=30, pending=None, opened=None, **flags):
    """TEST-ONLY pre_buy state (as written by pre_buy.refresh after good history+rates+orders reads)."""
    st = {"asOf": ts(now, age_s), "history_ok": True, "rates_ok": True, "orders_ok": True,
          "opened_today_position_ids": list(opened or []), "pending_order_keys": list(pending or [])}
    st.update(flags)
    (root / "prebuy-state.json").write_text(json.dumps(st))


def write_history(root: Path, now=MON, age_s=20, items=None):
    """TEST-ONLY saved get-my-trading-history read (today's opened/closed positions)."""
    (root / "history.json").write_text(json.dumps({"asOf": ts(now, age_s), "response": {
        "account": "demo", "statusCode": 200, "hasMore": False, "trades": list(items or [])}}))


def write_scores(root: Path, asof="2026-10-09", overrides=None, sidecar=True):
    rows = []
    for s, (sc, last, atr, a50, a200, rs3) in {**SCORES, **(overrides or {})}.items():
        rows.append({"symbol": s, "score": sc, "last_close": last, "atr14": atr, "above_50dma": a50,
                     "above_200dma": a200, "rs_3m": rs3})
    for r in rows:
        r.setdefault("rs_6m", r["rs_3m"])
    payload = {"schema": "classic-rebalance-scores-v1", "score_units": "fraction", "asOf_bars": asof, "rows": rows,
               "trailing_stops": {"SMH": {"high_since_entry": 639.47, "threshold": -0.08}}}
    if not sidecar:
        (root / "scores.json").write_text(json.dumps(payload))
        return None
    from .scorer import write_atomic
    return write_atomic(payload, root / "scores.json")


def write_envelope(root: Path, packs, run_id=RID):
    from .propose import stamp_auto_place
    rec = {"run_id": run_id, "kind": "auto", "payload": {"run_id": run_id, "propose_run_id": PRID, "flags": [],
           "buy_packs": [dict(stamp_auto_place(p), run_id=PRID) for p in packs]}}
    (root / "audit" / f"{run_id}.json").write_text(json.dumps(rec))


def write_run_qa(now=MON, age_s=60, run_id=RID, **kw):
    v = {"verdict": "PASS", "checker": "QA Bot", "skill": "classic-rsi-1h-run-qa", "checked_at": ts(now, age_s),
         "run_id": run_id, **kw}
    run_verdict_path(run_id).write_text(json.dumps(v))


def write_order_qa(r: dict, now=MON, age_s=60, **kw):
    g = r.get("cost_gate_anchor") or {}
    v = {"verdict": "PASS", "checker": "QA Bot", "skill": "classic-real-money-order-qa-gate",
         "checked_at": ts(now, age_s), "pack_sha256": r["pack_sha256"], "pack_id": r.get("pack_id"),
         "run_id": PRID, "symbol": r.get("symbol"), "qa_ask": (r.get("anchor") or {}).get("ask"),
         "recomputed_cost_gate": {k: g.get(k) for k in ("spread", "fees", "tax_est", "total_cost", "expected_gain", "ratio")}}
    v.update(kw)
    p = order_verdict_path(r["pack_sha256"])
    p.write_text(json.dumps(v))
    return p


def buy_prepare(payload: dict, ask: float, quote_ts: str, **kw) -> dict:
    snap = {"verdict": "ready", "orderType": "mkt", "direction": "buy", "leverage": 1,
            "instrumentId": payload["instrumentId"], "units": payload["units"], "ask": ask, "quoteAsOf": quote_ts,
            "stopLossRate": payload["stopLossRate"], "takeProfitRate": payload["takeProfitRate"]}
    snap.update(kw)
    return {"verdict": snap["verdict"], "confirmationToken": "SECRET-SHOULD-BE-DROPPED", "preparedOrderSnapshot": snap}


def close_prepare(payload: dict, **kw) -> dict:
    d = {"verdict": "ready", "positionId": payload["positionId"], "unitsToDeduct": payload["unitsToDeduct"],
         "confirmationToken": "SECRET"}
    d.update(kw)
    return d

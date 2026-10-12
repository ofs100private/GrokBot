"""Classic rebalance scorer (fix3) — builds scores-latest.json + sidecar scores-latest.sha256.

Run FIRST in the daily rebalance routine (before propose / execute_pass):
    cd /workspace && python3 -m classic_rsi.scorer            # production paths
    CLASSIC_EXEC_TEST_ROOT=<dir> python3 -m classic_rsi.scorer --offline-csv <dir>   # tests

Data: Yahoo daily bars via yfinance (same source as universe.py), period 2y, auto_adjust=False.
  * Returns / RS use Adj Close (dividend-adjusted); DMA, ATR, last_close, highs use raw OHLC
    (same price terms as eToro rates / stopLossRate).
  * Only CONFIRMED daily bars: bars dated after the last completed US session are dropped.
Universe: holdings from the live book + SKILL Step-2 ETF candidates (CANDIDATES). Liquid large
  caps (ADV >= $100M) are NOT auto-included yet; pass --extra SYM ... to add names.

Per row (fractions, not %):
  symbol, role (holding|candidate), instrumentId, assetClass, last_close, dma50, dma200,
  above_50dma, above_200dma, dma50_above_200dma, trend_ok, ret_1m/3m/6m (21/63/126d),
  rs_1m/rs_3m/rs_6m (= ret - SPY ret), score = 0.5*rs_3m + 0.5*rs_6m, atr14 (Wilder, price),
  atr_pct (= atr14/last_close*100), dd_52w, vol_63d (annualised), adv_usd_20d, bars.
  Consumers: cost_gate.resolve_edge (score, atr14, last_close), execute_pass trigger_3
  (above_50dma, rs_3m), trigger_4 (above_200dma), SL bounds (atr14).
trailing_stops (holdings): {high_since_entry: max raw High since openTime date,
  threshold: -0.08 ETF | -max(0.10, 2.5*atr14/last_close) stock}  (SKILL drift trigger 5).

Units (fix4): score, rs_*, ret_* are FRACTIONS (0.05 = +5 pp); payload carries score_units="fraction".
  edge_registry calibration: er_pct = intercept_pct + per_score_pct x score_fraction (per_score_pct = %
  expected return per 1.0 of score, i.e. per +100 pp RS); entries must declare score_units="fraction".

Freshness (fix4): asOf_bars must EQUAL the last completed US session (age 0). The routine runs at
  18:06 IDT = 11:06 ET (session open), so the last completed session is the prior trading day and that
  run passes; after the 16:00 ET close the file goes stale until the scorer is re-run.

Integrity: payload sha256 written to the sidecar /workspace/classic-rebalance/scores-latest.sha256
  (same dir, stem + ".sha256"; content `<hex>  scores-latest.json`). Both files are
written to temp names then os.replace'd (scores first, sidecar second); execute_pass fails closed
on missing sidecar, sha mismatch, bad schema/units/values, or asOf_bars != the last completed
session (age 0 trading days; any older file => SCORES_STALE_<n>_TRADING_DAYS). The sidecar proves integrity since write, NOT authorship (shared box).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .instruments import resolve
from .universe import is_crypto_ticker as is_crypto
from .market_hours import ET, last_completed_session
from .paths import paths

SCHEMA = "classic-rebalance-scores-v1"
VERSION = "scorer-v2-fix5-doc"
SCORE_UNITS = "fraction"  # score/rs/ret are fractions: 0.05 = +5 pp vs SPY (fix4)
CANDIDATES = ["XLK", "XLV", "XLF", "XLI", "XLE", "XLP", "XLU", "XLB", "XLY", "XLC",
              "SPY", "RSP", "QQQ", "SMH", "GLD", "IAU", "SLV"]
ROW_REQUIRED = ("symbol", "score", "last_close", "atr14", "above_50dma", "above_200dma", "rs_3m", "rs_6m")
MIN_BARS = 200


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sidecar_path(p: Path) -> Path:
    return p.with_name(p.stem + ".sha256")


def _wilder_atr(df: pd.DataFrame, n: int = 14) -> float:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean().iloc[-1])


def _ret(s: pd.Series, n: int) -> Optional[float]:
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def _r(x: Optional[float], d: int = 6) -> Optional[float]:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


def normalize_frame(df: pd.DataFrame, asof) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    df = df.dropna(subset=["open", "high", "low", "close", "adj_close"])
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(ET).tz_localize(None) if idx.tz is not None else idx
    return df[df.index.date <= asof]


def score_symbol(df: pd.DataFrame, spy: pd.DataFrame, *, open_date=None) -> dict[str, Any]:
    c, a = df["close"], df["adj_close"]
    sa = spy["adj_close"]
    last = float(c.iloc[-1])
    d50, d200 = float(c.rolling(50).mean().iloc[-1]), float(c.rolling(200).mean().iloc[-1])
    rets = {k: _ret(a, n) for k, n in (("1m", 21), ("3m", 63), ("6m", 126))}
    spr = {k: _ret(sa, n) for k, n in (("1m", 21), ("3m", 63), ("6m", 126))}
    rs = {k: (rets[k] - spr[k]) if rets[k] is not None and spr[k] is not None else None for k in rets}
    atr = _wilder_atr(df)
    row = {"last_close": _r(last, 4), "bar_date": str(df.index[-1].date()), "bars": len(df),
           "dma50": _r(d50, 4), "dma200": _r(d200, 4), "above_50dma": last > d50, "above_200dma": last > d200,
           "dma50_above_200dma": d50 > d200, "trend_ok": last > d50 and last > d200 and d50 > d200,
           **{f"ret_{k}": _r(v) for k, v in rets.items()}, **{f"rs_{k}": _r(v) for k, v in rs.items()},
           "score": _r(0.5 * rs["3m"] + 0.5 * rs["6m"]) if rs["3m"] is not None and rs["6m"] is not None else None,
           "atr14": _r(atr, 4), "atr_pct": _r(atr / last * 100, 4),
           "dd_52w": _r(last / float(c.iloc[-252:].max()) - 1),
           "vol_63d": _r(float(a.pct_change().iloc[-63:].std() * math.sqrt(252))),
           "adv_usd_20d": _r(float((c * df["volume"]).iloc[-20:].mean()), 0) if "volume" in df else None}
    if open_date is not None:
        since = df[df.index.date >= open_date]
        row["high_since_entry"] = _r(float(since["high"].max()), 4) if len(since) else None
    return row


def build_scores(frames: dict[str, pd.DataFrame], book: dict, now: datetime, *, extra=(), source: str) -> dict:
    asof = last_completed_session(now)
    if asof is None:
        raise SystemExit("market calendar unknown")
    holds = {}
    for p in book.get("positions") or []:
        s = str(p.get("symbol", "")).upper()
        if s:
            od = str(p.get("openTime") or "")[:10]
            holds[s] = min(holds.get(s) or od, od) if od else holds.get(s)
    syms = list(dict.fromkeys([*holds, *CANDIDATES, *[e.upper() for e in extra]]))
    fr = {s: normalize_frame(frames[s], asof) for s in syms if s in frames and frames[s] is not None}
    if "SPY" not in fr or len(fr["SPY"]) < MIN_BARS or fr["SPY"].index[-1].date() != asof:
        raise SystemExit(f"SPY daily bars missing or not at last completed session {asof}")
    rows, missing, trailing = [], [], {}
    for s in syms:
        if is_crypto(s):
            missing.append({"symbol": s, "reason": "crypto excluded"})
            continue
        df = fr.get(s)
        if df is None or len(df) < MIN_BARS:
            missing.append({"symbol": s, "reason": f"bars<{MIN_BARS}"})
            continue
        if df.index[-1].date() != asof:
            missing.append({"symbol": s, "reason": f"last bar {df.index[-1].date()} != {asof}"})
            continue
        inst = resolve(s) or {}
        od = datetime.fromisoformat(holds[s]).date() if holds.get(s) else None
        r = {"symbol": s, "role": "holding" if s in holds else "candidate",
             "instrumentId": inst.get("instrumentId"), "assetClass": inst.get("assetClass"),
             **score_symbol(df, fr["SPY"], open_date=od)}
        rows.append(r)
        if s in holds and r.get("high_since_entry"):
            th = -0.08 if inst.get("assetClass") == "etf" else -max(0.10, 2.5 * r["atr14"] / r["last_close"])
            trailing[s] = {"high_since_entry": r["high_since_entry"], "threshold": round(th, 4),
                           "level": round(r["high_since_entry"] * (1 + th), 4), "since": holds[s]}
    return {"schema": SCHEMA, "version": VERSION, "asOf_bars": str(asof), "generated_at": now.isoformat(),
            "source": source, "score_formula": "0.5*rs_3m + 0.5*rs_6m (fractions vs SPY, Adj Close)", "score_units": SCORE_UNITS,
            "book_asOf": book.get("asOf"), "rows": rows, "trailing_stops": trailing, "missing": missing}


def write_atomic(payload: dict, path: Path) -> str:
    """Write scores + sidecar via temp files + os.replace. Returns sha256 of the scores bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    b = (json.dumps(payload, indent=1, sort_keys=True, allow_nan=False) + "\n").encode()
    h = sha256_bytes(b)
    sc = sidecar_path(path)
    t1, t2 = path.with_name(f".{path.name}.tmp{os.getpid()}"), sc.with_name(f".{sc.name}.tmp{os.getpid()}")
    t1.write_bytes(b)
    t2.write_text(f"{h}  {path.name}\n")
    for t in (t1, t2):
        with open(t, "rb") as f:
            os.fsync(f.fileno())
    os.replace(t1, path)
    os.replace(t2, sc)
    return h


SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
# (field, required, lo, hi) — finite real numbers only (bool/str/NaN/inf rejected); None allowed only if not required
NUM_FIELDS = (("score", True, -5.0, 5.0), ("rs_3m", True, -5.0, 5.0), ("rs_6m", True, -5.0, 5.0),
              ("rs_1m", False, -5.0, 5.0), ("ret_1m", False, -0.99, 10.0), ("ret_3m", False, -0.99, 10.0),
              ("ret_6m", False, -0.99, 10.0), ("last_close", True, 1e-4, 1e6), ("atr14", True, 1e-6, 1e5),
              ("dma50", False, 1e-4, 1e6), ("dma200", False, 1e-4, 1e6), ("atr_pct", False, 1e-4, 50.0),
              ("dd_52w", False, -1.0, 0.0), ("vol_63d", False, 0.0, 10.0), ("high_since_entry", False, 1e-4, 1e6))
BOOL_FIELDS = (("above_50dma", True), ("above_200dma", True), ("dma50_above_200dma", False), ("trend_ok", False))


def _num_ok(v: Any, lo: float, hi: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi


def validate_rows(d: dict) -> Optional[str]:
    """Return an error detail string, or None if every row / trailing stop is well-typed and in range."""
    seen: set[str] = set()
    for i, r in enumerate(d["rows"]):
        if not isinstance(r, dict):
            return f"row {i}: not an object"
        sym = r.get("symbol")
        if not isinstance(sym, str) or not SYMBOL_RE.match(sym):
            return f"row {i}: bad symbol {sym!r}"
        if sym in seen:
            return f"duplicate symbol {sym}"
        seen.add(sym)
        for k, req, lo, hi in NUM_FIELDS:
            v = r.get(k)
            if v is None and not req and k not in ROW_REQUIRED:
                continue
            if not _num_ok(v, lo, hi):
                return f"{sym}.{k}={v!r} not a finite number in [{lo}, {hi}]"
        for k, req in BOOL_FIELDS:
            v = r.get(k)
            if (req or v is not None) and not isinstance(v, bool):
                return f"{sym}.{k}={v!r} not a bool"
        if r["atr14"] > 0.5 * r["last_close"]:
            return f"{sym}.atr14 > 50% of last_close"
    for sym, t in d["trailing_stops"].items():
        if not isinstance(sym, str) or not SYMBOL_RE.match(sym) or not isinstance(t, dict):
            return f"trailing_stops: bad entry {sym!r}"
        if not _num_ok(t.get("high_since_entry"), 1e-4, 1e6) or not _num_ok(t.get("threshold"), -0.5, -0.01):
            return f"trailing_stops.{sym}: high/threshold out of range"
    return None


def verify_scores_file(path: Path, now: datetime, max_trading_days: int = 0) -> dict[str, Any]:
    """Fail-closed check used by execute_pass: sidecar sha, schema, typed/ranged rows, unique symbols,
    score_units == 'fraction', and asOf_bars == last completed US session (age 0, fix4)."""
    from .market_hours import trading_days_between
    sc = sidecar_path(path)
    out: dict[str, Any] = {"ok": False, "path": str(path), "sidecar": str(sc), "data": None}
    if not path.exists():
        return {**out, "error": "SCORES_MISSING"}
    if not sc.exists():
        return {**out, "error": "SCORES_SIDECAR_MISSING"}
    b = path.read_bytes()
    h = sha256_bytes(b)
    want = (sc.read_text().split() or [""])[0].lower()
    out["sha256"] = h
    if h != want:
        return {**out, "error": "SCORES_SHA_MISMATCH", "sidecar_sha256": want}
    try:
        d = json.loads(b, parse_constant=lambda c: float('nan'))
        asof = datetime.fromisoformat(str(d["asOf_bars"])).date()
    except (ValueError, KeyError, TypeError):
        return {**out, "error": "SCORES_SCHEMA_INVALID"}
    if d.get("schema") != SCHEMA or not isinstance(d.get("rows"), list) or not isinstance(d.get("trailing_stops"), dict):
        return {**out, "error": "SCORES_SCHEMA_INVALID"}
    for r in d["rows"]:
        if not isinstance(r, dict) or any(k not in r for k in ROW_REQUIRED):
            return {**out, "error": "SCORES_SCHEMA_INVALID", "row": (r or {}).get("symbol") if isinstance(r, dict) else None}
    if d.get("score_units") != SCORE_UNITS:
        return {**out, "error": "SCORES_UNITS_INVALID", "detail": f"score_units={d.get('score_units')!r}, want {SCORE_UNITS!r}"}
    bad = validate_rows(d)
    if bad:
        return {**out, "error": "SCORES_VALUE_INVALID", "detail": bad}
    last = last_completed_session(now)
    if last is None:
        return {**out, "error": "MARKET_CALENDAR_UNKNOWN"}
    age = trading_days_between(asof, last)
    out.update(asOf_bars=str(asof), last_completed_session=str(last), age_trading_days=age)
    if age < 0:
        return {**out, "error": "SCORES_FROM_FUTURE"}
    if age > max_trading_days:
        return {**out, "error": f"SCORES_STALE_{age}_TRADING_DAYS"}
    return {**out, "ok": True, "error": None, "data": d}


def fetch_yahoo(symbols: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    raw = yf.download(symbols, period="2y", interval="1d", group_by="ticker", threads=True,
                      progress=False, auto_adjust=False)
    out = {}
    for s in symbols:
        try:
            df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
            out[s] = df.dropna(how="all")
        except KeyError:
            out[s] = None
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--offline-csv", help="dir of <SYM>.csv daily frames (tests only; requires test mode)")
    a = ap.parse_args(argv)
    P = paths()
    now = datetime.now(ET)
    book = json.loads(Path(P["book"]).read_text())
    syms = list(dict.fromkeys([*(str(p.get("symbol", "")).upper() for p in book.get("positions") or []),
                               *CANDIDATES, *[e.upper() for e in a.extra]]))
    if a.offline_csv:
        if not P["test_mode"]:
            raise SystemExit("--offline-csv is test-mode only")
        frames = {s: pd.read_csv(Path(a.offline_csv) / f"{s}.csv", index_col=0, parse_dates=True)
                  for s in syms if (Path(a.offline_csv) / f"{s}.csv").exists()}
        src = "offline csv (test)"
    else:
        frames = fetch_yahoo(syms)
        src = "Yahoo Finance daily (yfinance, auto_adjust=False; returns on Adj Close)"
    payload = build_scores(frames, book, now, extra=a.extra, source=src)
    h = write_atomic(payload, Path(P["scores"]))
    print(json.dumps({"path": str(P["scores"]), "sha256": h, "asOf_bars": payload["asOf_bars"],
                      "rows": len(payload["rows"]), "missing": payload["missing"], "test_mode": P["test_mode"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

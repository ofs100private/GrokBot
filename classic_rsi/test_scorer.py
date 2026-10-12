"""Tests for scorer.py (fix3): synthetic daily frames, no network."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import scorer as S
from .market_hours import last_completed_session, trading_days_between

IDT = ZoneInfo("Asia/Jerusalem")
MON = datetime(2026, 10, 12, 18, 0, tzinfo=IDT)   # 11:00 ET Monday -> last completed session Fri 10-09


def frame(drift: float, start=100.0, end="2026-10-12", n=300, seed=0):
    idx = pd.bdate_range(end=end, periods=n)
    rng = np.random.default_rng(seed)
    c = start * np.cumprod(1 + drift + rng.normal(0, 0.005, n))
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Adj Close": c,
                         "Volume": 1e6}, index=idx)


def run():
    out = []

    def t(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    t("calendar: last completed session at Mon 11:00 ET = Fri 10-09", str(last_completed_session(MON)) == "2026-10-09")
    t("calendar: after Mon close => Mon", str(last_completed_session(datetime(2026, 10, 12, 23, 30, tzinfo=IDT))) == "2026-10-12")
    t("calendar: Thu->Fri = 1 trading day, Thu->Mon = 2", trading_days_between(pd.Timestamp("2026-10-08").date(),
      pd.Timestamp("2026-10-09").date()) == 1 and trading_days_between(pd.Timestamp("2026-10-08").date(),
      pd.Timestamp("2026-10-12").date()) == 2)
    frames = {s: frame(0.0005, seed=i) for i, s in enumerate(S.CANDIDATES)}
    frames["SPY"] = frame(0.0005, seed=99)
    frames["XLE"] = frame(0.002, seed=5)          # strong uptrend
    frames["TMO"] = frame(-0.002, seed=7)         # downtrend holding (stock)
    book = {"asOf": MON.isoformat(), "positions": [
        {"symbol": "TMO", "openTime": "2026-08-01T15:00:00"}, {"symbol": "XLE", "openTime": "2026-09-01T15:00:00"}]}
    d = S.build_scores(frames, book, MON, source="synthetic")
    rows = {r["symbol"]: r for r in d["rows"]}
    t("asOf_bars = last completed session (today's unconfirmed bar dropped)", d["asOf_bars"] == "2026-10-09"
      and rows["SPY"]["bar_date"] == "2026-10-09", d["asOf_bars"])
    t("required fields present on every row", all(all(k in r for k in S.ROW_REQUIRED) for r in d["rows"]))
    t("extra fields: dma50/200, trend_ok, rs_1m, atr_pct, dd_52w, vol_63d",
      all(k in rows["XLE"] for k in ("dma50", "dma200", "trend_ok", "rs_1m", "atr_pct", "dd_52w", "vol_63d", "adv_usd_20d")))
    t("SPY RS = 0 by construction", abs(rows["SPY"]["rs_3m"]) < 1e-9 and abs(rows["SPY"]["score"]) < 1e-9)
    t("score = 0.5*rs_3m + 0.5*rs_6m", abs(rows["XLE"]["score"] - 0.5 * (rows["XLE"]["rs_3m"] + rows["XLE"]["rs_6m"])) < 1e-6)
    t("uptrend XLE: above 50/200DMA, trend_ok, positive score", rows["XLE"]["trend_ok"] and rows["XLE"]["score"] > 0)
    t("downtrend TMO: below 50/200DMA, rs_3m<0 (feeds trigger 3/4)",
      rows["TMO"]["above_50dma"] is False and rows["TMO"]["above_200dma"] is False and rows["TMO"]["rs_3m"] < 0)
    t("roles: TMO holding, GLD candidate", rows["TMO"]["role"] == "holding" and rows["GLD"]["role"] == "candidate")
    t("atr14 ~ 2% of price for 1%-range bars", 1.5 < rows["XLE"]["atr_pct"] < 2.6, rows["XLE"]["atr_pct"])
    ts_ = d["trailing_stops"]
    t("trailing stop ETF XLE threshold -8%", ts_["XLE"]["threshold"] == -0.08)
    t("trailing stop stock TMO threshold -max(10%, 2.5xATR%)", abs(ts_["TMO"]["threshold"]
      + max(0.10, 2.5 * rows["TMO"]["atr14"] / rows["TMO"]["last_close"])) < 1e-4)
    since = frames["TMO"].loc["2026-08-01":"2026-10-09", "High"].max()
    t("high_since_entry = max High since openTime", abs(ts_["TMO"]["high_since_entry"] - since) < 1e-3)
    fr2 = dict(frames)
    fr2["XLB"] = frame(0.0, n=150)
    fr2["XLU"] = frame(0.0, end="2026-10-07")
    d2 = S.build_scores(fr2, book, MON, source="synthetic")
    miss = {m["symbol"]: m["reason"] for m in d2["missing"]}
    t("short history / stale last bar => listed missing, no row", "XLB" in miss and "XLU" in miss
      and not any(r["symbol"] in ("XLB", "XLU") for r in d2["rows"]), miss)
    try:
        S.build_scores({k: v for k, v in frames.items() if k != "SPY"}, book, MON, source="x")
        t("no SPY => abort", False)
    except SystemExit:
        t("no SPY => abort", True)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "scores-latest.json"
        h = S.write_atomic(d, p)
        sc = Path(td) / "scores-latest.sha256"
        t("sidecar named scores-latest.sha256 with sha of bytes", sc.read_text().split()[0] == h == S.sha256_bytes(p.read_bytes()))
        t("no temp files left", sorted(x.name for x in Path(td).iterdir()) == ["scores-latest.json", "scores-latest.sha256"])
        v = S.verify_scores_file(p, MON)
        t("verify ok at Mon 11:00 ET", v["ok"] and v["age_trading_days"] == 0, v.get("error"))
        t("verify stale on Wed (2 trading days)", S.verify_scores_file(p, datetime(2026, 10, 14, 18, 0, tzinfo=IDT))["error"]
          == "SCORES_STALE_2_TRADING_DAYS")
        t("fix4 payload declares score_units fraction", d["score_units"] == "fraction")
        t("fix4 routine 18:06 IDT Mon (11:06 ET, session open) with Fri bars => age 0 ok",
          S.verify_scores_file(p, datetime(2026, 10, 12, 18, 6, tzinfo=IDT))["ok"])
        t("fix4 Mon after close (23:30 IDT) with Fri bars => SCORES_STALE_1",
          S.verify_scores_file(p, datetime(2026, 10, 12, 23, 30, tzinfo=IDT))["error"] == "SCORES_STALE_1_TRADING_DAYS")
        t("fix4 Tue 10:00 ET with Fri bars (missed Mon session) => SCORES_STALE_1",
          S.verify_scores_file(p, datetime(2026, 10, 13, 17, 0, tzinfo=IDT))["error"] == "SCORES_STALE_1_TRADING_DAYS")
        def bad_row(mut, name, code="SCORES_VALUE_INVALID", top=None):
            dd = json.loads(json.dumps(d))
            if top:
                top(dd)
            else:
                mut(next(r for r in dd["rows"] if r["symbol"] == "XLE"))
            S.write_atomic(dd, p) if top is None or "nan" not in name else None
            res = S.verify_scores_file(p, MON)
            t(name, res["error"] == code, res.get("detail") or res.get("error"))
        bad_row(lambda r: r.update(score="0.1"), "fix4 string score => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(score=True), "fix4 bool as score => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(score=1e9), "fix4 absurd score 1e9 => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(atr14=-1.0), "fix4 negative atr14 => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(atr14=r["last_close"]), "fix4 atr14 = 100% of price => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(last_close=0), "fix4 last_close 0 => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(above_200dma="false"), "fix4 above_200dma 'false' string => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(rs_3m=None), "fix4 rs_3m null => SCORES_VALUE_INVALID")
        bad_row(lambda r: r.update(symbol="xle; rm"), "fix4 bad symbol => SCORES_VALUE_INVALID")
        bad_row(None, "fix4 duplicate symbol rows => SCORES_VALUE_INVALID",
                top=lambda dd: dd["rows"].append(dict(dd["rows"][0])))
        bad_row(None, "fix4 trailing threshold +0.5 => SCORES_VALUE_INVALID",
                top=lambda dd: dd["trailing_stops"]["XLE"].update(threshold=0.5))
        bad_row(None, "fix4 missing score_units => SCORES_UNITS_INVALID", code="SCORES_UNITS_INVALID",
                top=lambda dd: dd.pop("score_units"))
        # NaN written by hand (scorer refuses to serialise NaN)
        dd = json.loads(json.dumps(d))
        b = json.dumps(dd, indent=1, sort_keys=True).replace('"score": ' + json.dumps(next(r for r in dd["rows"] if r["symbol"] == "XLE")["score"]), '"score": NaN', 1).encode()
        p.write_bytes(b)
        sc.write_text(S.sha256_bytes(b) + "  scores-latest.json\n")
        res = S.verify_scores_file(p, MON)
        t("fix4 NaN score (valid sidecar) => SCORES_VALUE_INVALID", res["error"] == "SCORES_VALUE_INVALID", res.get("detail"))
        try:
            S.write_atomic(dict(d, rows=[dict(d["rows"][0], score=float("nan"))]), p)
            t("fix4 scorer refuses to write NaN", False)
        except ValueError:
            t("fix4 scorer refuses to write NaN", True)
        S.write_atomic(d, p)
        t("fix4 clean file still verifies after validation suite", S.verify_scores_file(p, MON)["ok"])
        p.write_text(p.read_text().replace('"asOf_bars"', '"asOf_bars" ', 1))
        t("tamper => SCORES_SHA_MISMATCH", S.verify_scores_file(p, MON)["error"] == "SCORES_SHA_MISMATCH")
        bad = dict(d, rows=[{"symbol": "X"}])
        S.write_atomic(bad, p)
        t("missing row fields => SCORES_SCHEMA_INVALID", S.verify_scores_file(p, MON)["error"] == "SCORES_SCHEMA_INVALID")
        S.write_atomic(dict(d, schema="other"), p)
        t("wrong schema => SCORES_SCHEMA_INVALID", S.verify_scores_file(p, MON)["error"] == "SCORES_SCHEMA_INVALID")
        sc.unlink()
        t("no sidecar => SCORES_SIDECAR_MISSING", S.verify_scores_file(p, MON)["error"] == "SCORES_SIDECAR_MISSING")
        p.unlink()
        t("no file => SCORES_MISSING", S.verify_scores_file(p, MON)["error"] == "SCORES_MISSING")
    return out


def main() -> int:
    res = run()
    for name, ok, detail in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail != "" else ""))
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

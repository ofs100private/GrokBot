"""Offline tests for universe scan miss accounting, retry and SPX_SCAN_PARTIAL (no network).

Run: cd /workspace && ./screener-venv/bin/python -m classic_rsi.test_universe
Uses a fake yf.download, temp cache/reference files and a no-op sleep. Writes no audit runs.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import auto_1h as A
from . import universe as U


def _daily(n=60, px=100.0, vol=5_000_000):
    idx = pd.date_range("2026-07-01", periods=n, freq="B")
    return pd.DataFrame({"Open": px, "High": px, "Low": px, "Close": px, "Volume": float(vol)}, index=idx)


def _hourly(n=70, vol=1_000_000, last_mult=2.0):
    idx = pd.date_range("2026-09-25 09:30", periods=n, freq="h", tz="America/New_York")
    v = np.full(n, float(vol))
    v[-2] = vol * last_mult  # last *confirmed* bar (last row is the forming bar)
    return pd.DataFrame({"Open": 100.0, "High": 100.0, "Low": 100.0, "Close": 100.0, "Volume": v}, index=idx)


class FakeYF:
    """behaviour[sym] -> list of per-call modes: ok|missing|short|bad|raise_chunk; last mode repeats."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls: dict[str, int] = {}

    def __call__(self, symbols, *, period, interval):
        frames = {}
        for sym in symbols:
            k = self.calls.get(sym, 0)
            self.calls[sym] = k + 1
            modes = self.behaviour.get(sym, ["ok"])
            mode = modes[min(k, len(modes) - 1)]
            if mode == "raise_chunk":
                raise RuntimeError("Too Many Requests")
            if mode == "missing":
                continue
            df = _daily() if interval == "1d" else _hourly()
            if mode == "short":
                df = df.tail(5)
            if mode == "bad":
                df = df.astype(object)
                df["Close"] = "x"
            frames[sym] = df
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1, sort=False)


def _screen(fake, pool, tmp, **kw):
    U._yf_download = fake
    return U.screen_universe(pool=pool, book_symbols=["QQQ"], cache_path=tmp / "cache.json",
                             reference_path=tmp / "ref.json", sleep=lambda s: None, **kw)


def run():
    out = []

    def t(name, cond, detail=""):
        out.append((name, bool(cond), detail))

    orig = U._yf_download
    pool = [f"S{i:03d}" for i in range(100)]
    try:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            beh = {"S001": ["missing"], "S002": ["short"], "S003": ["bad"],
                   "S004": ["missing", "ok"], "S005": ["missing", "missing", "ok"]}
            fake = FakeYF(beh)
            r = _screen(fake, pool, tmp)
            m = r["meta"]
            sk = {(x["symbol"], x["stage"]): x for x in m["skipped"]}
            t("missing counted as skipped reason=missing", sk.get(("S001", "daily"), {}).get("reason") == "missing")
            t("short counted as skipped reason=short", sk.get(("S002", "daily"), {}).get("reason") == "short")
            t("exception counted as skipped reason=exception", sk.get(("S003", "daily"), {}).get("reason") == "exception")
            t("skipped_count == 3 and error_count >= 3", m["skipped_count"] == 3 and m["error_count"] >= 3,
              f"{m['skipped_count']} {m['error_count']}")
            t("skipped_by_reason 1/1/1", m["skipped_by_reason"] == {"missing": 1, "short": 1, "exception": 1},
              str(m["skipped_by_reason"]))
            t("persistent miss tried 1+2 times", sk[("S001", "daily")]["attempts"] == 3 and fake.calls["S001"] == 3,
              str(fake.calls.get("S001")))
            t("persistent exception tried 1+2 times", sk[("S003", "daily")]["attempts"] == 3 and fake.calls["S003"] == 3)
            t("short NOT retried (1 attempt, 1 call)", sk[("S002", "daily")]["attempts"] == 1 and fake.calls["S002"] == 1,
              str(fake.calls.get("S002")))
            rec = {x["symbol"] for x in m["recovered_on_retry"] if x["stage"] == "daily"}
            t("flaky S004 recovered on retry 1", "S004" in rec and ("S004", "daily") not in sk)
            t("flaky S005 recovered on retry 2", "S005" in rec and ("S005", "daily") not in sk)
            t("liquid_count = 97", m["liquid_count"] == 97, str(m["liquid_count"]))
            t("run not blocked (no fallback, symbols present)", not r["used_fallback"] and r["symbols"])
            # seed 491 => 97 is far below => soft flag
            t("SPX_SCAN_PARTIAL vs seed 491", m["soft_flags"] == ["SPX_SCAN_PARTIAL"]
              and m["liquid_reference"]["basis"] == "seed" and m["liquid_reference"]["reference"] == 491)
            st = json.loads((tmp / "ref.json").read_text())
            t("partial scan recorded but not full", st["history"][-1]["full"] is False and st["reference"] == 491
              and m["full_scan"] is False)

        # reference from full scans: 100-name full scans become reference; 2% rule
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ref.json").write_text(json.dumps({"seed": 100, "history": []}))
            r = _screen(FakeYF({}), pool, tmp)
            t("full scan at reference: no soft flag", r["meta"]["soft_flags"] == [] and r["meta"]["skipped_count"] == 0)
            st = json.loads((tmp / "ref.json").read_text())
            t("full scan feeds median", st["history"][-1]["full"] is True and st["reference"] == 100.0
              and st["reference_basis"].startswith("median_last_1"))
            r = _screen(FakeYF({"S010": ["missing"], "S011": ["missing"]}), pool, tmp)
            t("98/100 (2.0% drop) not flagged", r["meta"]["liquid_count"] == 98 and r["meta"]["soft_flags"] == [])
            r = _screen(FakeYF({f"S0{i}": ["missing"] for i in range(10, 13)}), pool, tmp)
            t("97/100 (3% drop) flagged SPX_SCAN_PARTIAL", r["meta"]["liquid_count"] == 97
              and r["meta"]["soft_flags"] == ["SPX_SCAN_PARTIAL"])
            st = json.loads((tmp / "ref.json").read_text())
            t("partial scans excluded from median", st["reference"] == 100.0)
            # hourly miss accounting
            r = _screen(FakeYF({"S020": ["ok", "missing"]}), pool, tmp)  # daily ok, hourly missing x3
            hs = [x for x in r["meta"]["skipped"] if x["stage"] == "hourly"]
            t("hourly miss recorded stage=hourly", len(hs) == 1 and hs[0]["symbol"] == "S020"
              and hs[0]["reason"] == "missing", str(hs))
            # short-only scan is still full and updates the median; short stays listed
            r = _screen(FakeYF({"S040": ["short"]}), pool, tmp)
            st = json.loads((tmp / "ref.json").read_text())
            t("short-only scan counts as full", r["meta"]["full_scan"] is True and st["history"][-1]["full"] is True
              and st["history"][-1]["short_skipped"] == 1 and st["history"][-1]["hard_skipped"] == 0)
            t("short still listed in skipped", [(x["symbol"], x["reason"]) for x in r["meta"]["skipped"]] == [("S040", "short")])
            t("short-only scan feeds median (100, 99 -> 99.5)", st["reference"] == 99.5
              and st["reference_basis"] == "median_last_2_full_scans", f"{st['reference']} {st['reference_basis']}")
            # hourly-stage missing makes the scan partial (not full)
            r = _screen(FakeYF({"S041": ["ok", "missing"]}), pool, tmp)
            t("hourly missing => not full", r["meta"]["full_scan"] is False)
            # chunk-level exception => every ticker in chunk counted, then retried
            r = _screen(FakeYF({"S030": ["raise_chunk", "ok"]}), pool, tmp)
            t("chunk exception retried and recovered", r["meta"]["skipped_count"] == 0
              and any(x["symbol"] == "S030" for x in r["meta"]["recovered_on_retry"]))

        # pre-scan crypto filter: exact ticker (+ -USD / =X) only
        t("SOLV included (not crypto)", not U.is_crypto_ticker("SOLV"))
        t("SOL excluded", U.is_crypto_ticker("SOL"))
        t("BTC-USD excluded", U.is_crypto_ticker("BTC-USD"))
        t("ETH=X / DOGE excluded", U.is_crypto_ticker("ETH=X") and U.is_crypto_ticker("doge"))
        t("substring-containing names kept (SOLV, ADAP, DOTX, BTCS, ADBE, ADSK)",
          not any(U.is_crypto_ticker(x) for x in ("SOLV", "ADAP", "DOTX", "BTCS", "ADBE", "ADSK", "CRYPTOX")))
        t("non-crypto -USD / =X suffix kept", not U.is_crypto_ticker("AAPL-USD") and not U.is_crypto_ticker("EURUSD=X"))
        with tempfile.TemporaryDirectory() as d:
            sp = Path(d) / "sp.json"
            sp.write_text(json.dumps({"symbols": ["SOLV", "AAPL", "BRK.B", "SOL", "BTC-USD"]}))
            t("pool includes SOLV, excludes SOL/BTC-USD", U.load_sp500_pool(sp) == ["SOLV", "AAPL", "BRK-B"])
            t("pool_excluded reports SOL/BTC-USD", [x["symbol"] for x in U.pool_exclusions(sp)] == ["SOL", "BTC-USD"])

        # auto_1h envelope surfaces skips + soft flag; existing guards unchanged (dry run, no writes)
        fake_meta = {"liquid_count": 470, "skipped": [{"symbol": "ABC", "stage": "daily", "reason": "missing",
                                                       "detail": "no rows returned", "attempts": 3}],
                     "skipped_count": 1, "skipped_by_reason": {"missing": 1, "short": 0, "exception": 0},
                     "soft_flags": ["SPX_SCAN_PARTIAL"], "liquid_reference": {"reference": 491.0, "partial": True},
                     "error_count": 1}
        o_stale, o_build = A.book_snapshot_staleness, A.build_universe
        A.book_snapshot_staleness = lambda *a, **k: None
        A.build_universe = lambda *a, **k: (["QQQ"], dict(fake_meta))
        try:
            env = A.run_auto_1h(dry_run=True)
        finally:
            A.book_snapshot_staleness, A.build_universe = o_stale, o_build
        t("envelope soft_flags SPX_SCAN_PARTIAL", env["soft_flags"] == ["SPX_SCAN_PARTIAL"])
        t("envelope universe.skipped + skipped_count", env["universe"]["skipped_count"] == 1
          and env["universe"]["skipped"][0]["symbol"] == "ABC")
        t("soft flag does not enter hard flags / status", env["flags"] == [] and env["status"] == "DRY_RUN")
        t("do_not_place / long_only unchanged", env["do_not_place"] is True and env["place"] is False
          and env["long_only"] is True)
        # stale book still fails closed, and universe block tolerates the stale meta
        A.book_snapshot_staleness = lambda *a, **k: {"flag": "BOOK_SNAPSHOT_STALE", "reason": "test"}
        try:
            env = A.run_auto_1h(dry_run=True)
        finally:
            A.book_snapshot_staleness = o_stale
        t("staleness guard v2 still fails closed", env["status"] == "BOOK_SNAPSHOT_STALE"
          and env["flags"] == ["BOOK_SNAPSHOT_STALE"] and env["symbols"] == [] and env["universe"]["skipped_count"] == 0)
    finally:
        U._yf_download = orig
    return out


def main() -> int:
    res = run()
    for name, ok, detail in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok and detail else ""))
    n_fail = sum(1 for _, ok, _ in res if not ok)
    print(f"{len(res) - n_fail}/{len(res)} passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

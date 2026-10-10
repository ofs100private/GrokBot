"""Classic RSI 1H dynamic universe screener (OfersClaw5-PRIYN only).

Pipeline (no fixed mega-cap list as primary universe):
  1. Load candidate pool from /workspace/sp500_symbols.json (dynamic S&P)
  2. Liquidity filter on daily bars: ADV$ (close*volume SMA20) >= MIN_ADV_USD ($100M default),
     last close >= MIN_PRICE
  3. Rising volume on confirmed 1H: last closed 1H vol > SMA20(vol) * RISING_MULT
  4. Rank by volume ratio descending → top TOP_N
  5. Always union live Classic book symbols

Never falls back to the old 6-name DEFAULT_SYMBOLS as the primary universe.
If yfinance flakes, prefer previous cache at audit/universe-latest.json.
Does not place trades. Classic only — never Momentum.

Per-ticker data misses are never silent (QA SPX_SCAN_PARTIAL_SILENT_DROPS):
  * a ticker whose Yahoo data is missing / raises is retried up to RETRY_MAX times
    with backoff (RETRY_BACKOFF_S); 'short' (too few bars, structural) is not retried.
    Final misses count as errors and are listed in meta["skipped"] with reason
    missing|short|exception (+ skipped_count)
  * a scan is "full" when it has 0 missing and 0 exception skips (shorts allowed)
  * liquid_count is compared with a reference (median of recent full scans, seeded
    at LIQUID_REF_SEED) kept in audit/universe-liquid-reference.json; a drop of more
    than LIQUID_DROP_TOL adds the SOFT flag SPX_SCAN_PARTIAL (never blocks the run)
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IDT = ZoneInfo("Asia/Jerusalem")

SP500_PATH = Path("/workspace/sp500_symbols.json")
UNIVERSE_CACHE = Path("/workspace/classic_rsi/audit/universe-latest.json")

# --- Thresholds (documented constants) ---
MIN_ADV_USD = 100_000_000.0  # $100M avg dollar volume (SMA20 of close*volume)
MIN_PRICE = 10.0  # exclude penny / micro-price names
RISING_MULT = 1.2  # last confirmed 1H vol > SMA20(vol) * this
TOP_N = 50  # rising-volume liquid names kept (book always unioned)
ADV_SMA = 20
VOL_SMA = 20
DAILY_CHUNK = 50
HOURLY_CHUNK = 40
DAILY_PERIOD = "3mo"  # ~60 trading days
HOURLY_PERIOD = "10d"  # enough for SMA20 on 1H + buffer

# --- Miss handling / partial-scan detection ---
RETRY_MAX = 2  # retries per missed ticker (after the first attempt)
RETRY_BACKOFF_S = (2.0, 5.0)  # sleep before retry 1, retry 2
RETRY_CHUNK = 20  # smaller chunks on retry (throttling)
LIQUID_REF_PATH = Path("/workspace/classic_rsi/audit/universe-liquid-reference.json")
LIQUID_REF_SEED = 491  # true liquid count ~491 (Oct 2026 full scans)
LIQUID_REF_WINDOW = 10  # median of last N full scans
LIQUID_REF_HISTORY_MAX = 60
LIQUID_DROP_TOL = 0.02  # >2% below reference => SPX_SCAN_PARTIAL (soft)
SOFT_FLAG_PARTIAL = "SPX_SCAN_PARTIAL"
MISS_REASONS = ("missing", "short", "exception")
RETRY_REASONS = frozenset({"missing", "exception"})  # 'short' is structural: no retry
FULL_SCAN_BLOCKING_REASONS = frozenset({"missing", "exception"})  # 'short' keeps a scan full

# Pre-scan crypto filter (belt-and-suspenders; the binding check is the id-based
# instrument guard in instruments.py/propose.py). EXACT ticker match only: a ticker
# is excluded iff it equals a crypto ticker, or a crypto ticker + "-USD" / "=X".
# (Substring matching wrongly dropped e.g. SOLV because it contains "SOL".)
CRYPTO_TICKERS = frozenset(
    {"BTC", "ETH", "USDT", "USDC", "DOGE", "SOL", "XRP", "ADA", "DOT", "AVAX", "CRYPTO"}
)
CRYPTO_SUFFIXES = ("-USD", "=X")


def _now_idt_str() -> str:
    return datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_crypto_ticker(symbol: str) -> bool:
    s = str(symbol).upper().strip()
    if not s:
        return True
    if s in CRYPTO_TICKERS:
        return True
    for suf in CRYPTO_SUFFIXES:
        if s.endswith(suf) and s[: -len(suf)] in CRYPTO_TICKERS:
            return True
    return False


def pool_exclusions(path: Path = SP500_PATH) -> list[dict[str, str]]:
    """Tickers in the S&P file that load_sp500_pool drops (reported, not silent)."""
    try:
        raw = json.loads(path.read_text()).get("symbols") or []
    except Exception:  # noqa: BLE001
        return []
    out = []
    for s in raw:
        u = str(s).upper().strip().replace(".", "-")
        if u and is_crypto_ticker(u):
            out.append({"symbol": u, "reason": "crypto_regex"})
    return out


def load_sp500_pool(path: Path = SP500_PATH) -> list[str]:
    """Load dynamic S&P candidate pool; exclude crypto-looking tickers."""
    if not path.exists():
        raise FileNotFoundError(f"S&P pool missing: {path}")
    data = json.loads(path.read_text())
    raw = data.get("symbols") or []
    out: list[str] = []
    seen: set[str] = set()
    for s in raw:
        u = str(s).upper().strip().replace(".", "-")  # BRK.B → BRK-B for Yahoo
        if not u or u in seen or is_crypto_ticker(u):
            continue
        seen.add(u)
        out.append(u)
    return out


def _chunked(seq: list[str], n: int) -> list[list[str]]:
    return [seq[i : i + n] for i in range(0, len(seq), n)]


def _extract_ticker_frame(raw: pd.DataFrame, sym: str) -> Optional[pd.DataFrame]:
    """Normalize a single-ticker OHLC frame from yf.download multi or single."""
    if raw is None or raw.empty:
        return None
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            # group_by="ticker" → level 0 is ticker
            level0 = raw.columns.get_level_values(0)
            if sym in level0:
                df = raw[sym].copy()
            else:
                # sometimes level 1 is ticker
                level1 = raw.columns.get_level_values(1)
                if sym in level1:
                    df = raw.xs(sym, axis=1, level=1).copy()
                else:
                    return None
        else:
            df = raw.copy()
        df.columns = [str(c).lower() for c in df.columns]
        need = {"close", "volume"}
        if not need.issubset(set(df.columns)):
            return None
        df = df.dropna(subset=["close", "volume"])
        if df.empty:
            return None
        return df
    except Exception:  # noqa: BLE001
        return None


def _yf_download(symbols: list[str], *, period: str, interval: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(
        symbols,
        period=period,
        interval=interval,
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=True,
    )


def _frame_for(raw: Any, sym: str, chunk_len: int) -> Optional[pd.DataFrame]:
    """Single-ticker frame from a yf.download result (None if absent/empty)."""
    if chunk_len == 1 and not isinstance(getattr(raw, "columns", None), pd.MultiIndex):
        if raw is None or raw.empty:
            return None
        df = raw.copy()
        df.columns = [str(c).lower() for c in df.columns]
        if not {"close", "volume"}.issubset(df.columns):
            return None
        df = df.dropna(subset=["close", "volume"])
        return None if df.empty else df
    return _extract_ticker_frame(raw, sym)


def _fetch_pass(
    symbols: list[str], *, period: str, interval: str, chunk_size: int, evaluate
) -> tuple[dict[str, Any], dict[str, tuple[str, str]]]:
    """One download pass. Returns (ok_values, misses{sym: (reason, detail)})."""
    ok: dict[str, Any] = {}
    misses: dict[str, tuple[str, str]] = {}
    for chunk in _chunked(symbols, chunk_size):
        try:
            raw = _yf_download(chunk, period=period, interval=interval)
        except Exception as exc:  # noqa: BLE001
            for sym in chunk:
                misses[sym] = ("exception", f"chunk_download:{exc}"[:200])
            continue
        for sym in chunk:
            try:
                df = _frame_for(raw, sym, len(chunk))
                if df is None:
                    misses[sym] = ("missing", "no rows returned")
                    continue
                status, value = evaluate(df)
                if status == "ok":
                    ok[sym] = value
                else:
                    misses[sym] = (status, str(value))
            except Exception as exc:  # noqa: BLE001
                misses[sym] = ("exception", str(exc)[:200])
    return ok, misses


def fetch_with_retry(
    symbols: list[str],
    *,
    period: str,
    interval: str,
    chunk_size: int,
    evaluate,
    stage: str,
    retries: int = RETRY_MAX,
    backoff: tuple[float, ...] = RETRY_BACKOFF_S,
    sleep=time.sleep,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Download + evaluate with retries for missed tickers.

    Only ``missing`` / ``exception`` misses are retried; ``short`` (structural, e.g. a
    new listing with too few bars) is recorded after the first attempt, no retry.
    Returns (ok_values, skipped, recovered). ``skipped`` rows:
    {symbol, stage, reason (missing|short|exception), detail, attempts}.
    """
    ok, misses = _fetch_pass(symbols, period=period, interval=interval,
                             chunk_size=chunk_size, evaluate=evaluate)
    attempts = {s: 1 for s in symbols}
    recovered: list[str] = []
    for i in range(max(0, retries)):
        again = [sym for sym, why in misses.items() if why[0] in RETRY_REASONS]
        if not again:
            break
        if backoff:
            sleep(float(backoff[min(i, len(backoff) - 1)]))
        ok2, miss2 = _fetch_pass(again, period=period, interval=interval,
                                 chunk_size=min(chunk_size, RETRY_CHUNK), evaluate=evaluate)
        for sym in again:
            attempts[sym] += 1
        for sym, val in ok2.items():
            ok[sym] = val
            misses.pop(sym, None)
            recovered.append(sym)
        for sym, why in miss2.items():
            misses[sym] = why
    skipped = [
        {"symbol": sym, "stage": stage, "reason": why[0], "detail": why[1], "attempts": attempts.get(sym, 1)}
        for sym, why in misses.items()
    ]
    return ok, skipped, recovered


def _eval_daily(df: pd.DataFrame) -> tuple[str, Any]:
    if len(df) < ADV_SMA:
        return "short", f"{len(df)} daily bars < {ADV_SMA}"
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    adv = float((close * vol).tail(ADV_SMA).mean())
    last_px = float(close.iloc[-1])
    if not np.isfinite(adv) or not np.isfinite(last_px):
        return "missing", "non-finite close/volume"
    return "ok", (adv, last_px)


def _eval_hourly(df: pd.DataFrame) -> tuple[str, Any]:
    if "volume" not in df.columns:
        return "missing", "no volume column"
    conf = _confirmed_1h_frame(df)
    if len(conf) < VOL_SMA + 1:
        return "short", f"{len(conf)} confirmed 1H bars < {VOL_SMA + 1}"
    vol = conf["volume"].astype(float)
    sma = float(vol.tail(VOL_SMA).mean())
    last_vol = float(vol.iloc[-1])
    if not np.isfinite(sma) or sma <= 0 or not np.isfinite(last_vol):
        return "missing", "non-finite/zero 1H volume"
    return "ok", (last_vol / sma, last_vol, sma)


def filter_liquid_daily(
    symbols: list[str],
    *,
    min_adv_usd: float = MIN_ADV_USD,
    min_price: float = MIN_PRICE,
    chunk_size: int = DAILY_CHUNK,
    detail: Optional[dict[str, Any]] = None,
    retries: int = RETRY_MAX,
    sleep=time.sleep,
) -> tuple[list[str], dict[str, float], list[str]]:
    """Return (liquid_symbols, adv_map, errors) using daily ADV$ SMA20.

    Every per-ticker data miss (after retries) is an error ``daily_<SYM>:<reason>:<detail>``;
    pass ``detail={}`` to receive {"skipped": [...], "recovered": [...]}.
    """
    ok, skipped, recovered = fetch_with_retry(
        symbols, period=DAILY_PERIOD, interval="1d", chunk_size=chunk_size,
        evaluate=_eval_daily, stage="daily", retries=retries, sleep=sleep,
    )
    liquid: list[str] = []
    adv_map: dict[str, float] = {}
    for sym in symbols:  # preserve pool order
        if sym not in ok:
            continue
        adv, last_px = ok[sym]
        if last_px < min_price or adv < min_adv_usd:
            continue
        liquid.append(sym)
        adv_map[sym] = adv
    errors = [f"daily_{r['symbol']}:{r['reason']}:{r['detail']}" for r in skipped]
    if detail is not None:
        detail["skipped"] = skipped
        detail["recovered"] = recovered
    return liquid, adv_map, errors


def _confirmed_1h_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop forming 1H bar (same convention as classic_rsi.signals)."""
    if df is None or len(df) < 2:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    return df.iloc[:-1].copy()


def filter_rising_1h(
    symbols: list[str],
    *,
    rising_mult: float = RISING_MULT,
    top_n: int = TOP_N,
    chunk_size: int = HOURLY_CHUNK,
    detail: Optional[dict[str, Any]] = None,
    retries: int = RETRY_MAX,
    sleep=time.sleep,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rank liquid names by confirmed 1H volume / SMA20(vol); keep rising ones.

    Returns (ranked_rows, errors). Each row: {symbol, vol_ratio, last_vol, vol_sma}.
    Per-ticker misses (after retries) are errors ``hourly_<SYM>:<reason>:<detail>``.
    """
    ok, skipped, recovered = fetch_with_retry(
        symbols, period=HOURLY_PERIOD, interval="1h", chunk_size=chunk_size,
        evaluate=_eval_hourly, stage="hourly", retries=retries, sleep=sleep,
    )
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        if sym not in ok:
            continue
        ratio, last_vol, sma = ok[sym]
        if ratio < rising_mult:
            continue
        rows.append({"symbol": sym, "vol_ratio": round(ratio, 4), "last_vol": last_vol, "vol_sma20": sma})
    rows.sort(key=lambda r: r["vol_ratio"], reverse=True)
    errors = [f"hourly_{r['symbol']}:{r['reason']}:{r['detail']}" for r in skipped]
    if detail is not None:
        detail["skipped"] = skipped
        detail["recovered"] = recovered
    return rows[:top_n], errors


# --- Liquid-count reference (partial-scan detection) ---

def load_liquid_reference(path: Optional[Path] = LIQUID_REF_PATH) -> dict[str, Any]:
    state: dict[str, Any] = {"seed": LIQUID_REF_SEED, "history": []}
    if path is not None and Path(path).exists():
        try:
            loaded = json.loads(Path(path).read_text())
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:  # noqa: BLE001
            state["load_error"] = "unreadable; using seed"
    return state


def liquid_reference_value(state: dict[str, Any]) -> tuple[float, str]:
    full = [int(h["liquid_count"]) for h in (state.get("history") or [])
            if h.get("full") and h.get("liquid_count") is not None][-LIQUID_REF_WINDOW:]
    if full:
        return float(statistics.median(full)), f"median_last_{len(full)}_full_scans"
    return float(state.get("seed") or LIQUID_REF_SEED), "seed"


def evaluate_liquid_drop(liquid_count: Optional[int], state: dict[str, Any],
                         tol: float = LIQUID_DROP_TOL) -> dict[str, Any]:
    ref, basis = liquid_reference_value(state)
    threshold = ref * (1.0 - tol)
    lc = int(liquid_count or 0)
    drop_pct = round((ref - lc) / ref * 100.0, 2) if ref else None
    return {
        "reference": ref,
        "basis": basis,
        "tolerance_pct": round(tol * 100, 2),
        "threshold": round(threshold, 2),
        "liquid_count": lc,
        "drop_pct": drop_pct,
        "partial": lc < threshold,
    }


def record_liquid_scan(path: Optional[Path], state: dict[str, Any], entry: dict[str, Any]) -> None:
    if path is None:
        return
    hist = list(state.get("history") or [])
    hist.append(entry)
    out = {k: v for k, v in state.items() if k not in ("history", "load_error")}
    out["seed"] = state.get("seed") or LIQUID_REF_SEED
    out["note"] = ("full=True scans (0 missing + 0 exception skips; 'short' skips allowed) "
                   "feed the reference median; partial scans are recorded but excluded")
    out["history"] = hist[-LIQUID_REF_HISTORY_MAX:]
    ref, basis = liquid_reference_value(out)
    out["reference"] = ref
    out["reference_basis"] = basis
    out["updatedAt"] = _now_idt_str()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, indent=2, default=str) + "\n")


def _skip_summary(skipped: list[dict[str, Any]]) -> dict[str, Any]:
    by_reason = {r: 0 for r in MISS_REASONS}
    by_stage: dict[str, int] = {}
    for row in skipped:
        by_reason[row["reason"]] = by_reason.get(row["reason"], 0) + 1
        by_stage[row["stage"]] = by_stage.get(row["stage"], 0) + 1
    return {"skipped": skipped, "skipped_count": len(skipped),
            "skipped_by_reason": by_reason, "skipped_by_stage": by_stage}


def _load_cache(path: Path = UNIVERSE_CACHE) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _write_cache(payload: dict[str, Any], path: Path = UNIVERSE_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def screen_universe(
    *,
    pool: Optional[list[str]] = None,
    book_symbols: Optional[list[str]] = None,
    min_adv_usd: float = MIN_ADV_USD,
    min_price: float = MIN_PRICE,
    rising_mult: float = RISING_MULT,
    top_n: int = TOP_N,
    sp500_path: Path = SP500_PATH,
    cache_path: Path = UNIVERSE_CACHE,
    allow_cache_fallback: bool = True,
    reference_path: Optional[Path] = LIQUID_REF_PATH,
    retries: int = RETRY_MAX,
    sleep=time.sleep,
) -> dict[str, Any]:
    """Screen S&P → liquid ADV$ → rising 1H volume; union book.

    Returns dict with keys: symbols, rising_rows, meta, used_fallback.
    """
    book = [str(s).upper().strip() for s in (book_symbols or []) if s]
    book = [s for s in book if s and not is_crypto_ticker(s)]

    meta_base: dict[str, Any] = {
        "min_adv_usd": min_adv_usd,
        "min_price": min_price,
        "rising_mult": rising_mult,
        "top_n": top_n,
        "adv_sma": ADV_SMA,
        "vol_sma": VOL_SMA,
        "source_path": str(sp500_path),
        "asOf": _now_idt_str(),
        "asOfUTC": _now_utc_iso(),
    }

    errors: list[str] = []
    used_fallback = False
    skipped: list[dict[str, Any]] = []
    recovered: list[dict[str, str]] = []
    live_liquid: Optional[int] = None
    ref_state = load_liquid_reference(reference_path)
    meta_base["retry_policy"] = {"retries": retries, "backoff_s": list(RETRY_BACKOFF_S),
                                 "retry_chunk": RETRY_CHUNK}
    meta_base["pool_excluded"] = pool_exclusions(sp500_path) if pool is None else []

    try:
        pool_syms = list(pool) if pool is not None else load_sp500_pool(sp500_path)
        if len(pool_syms) < 50:
            raise RuntimeError(f"S&P pool too small ({len(pool_syms)})")

        det_d: dict[str, Any] = {}
        liquid, adv_map, err_d = filter_liquid_daily(
            pool_syms, min_adv_usd=min_adv_usd, min_price=min_price,
            detail=det_d, retries=retries, sleep=sleep,
        )
        errors.extend(err_d)
        skipped.extend(det_d.get("skipped") or [])
        recovered.extend({"symbol": x, "stage": "daily"} for x in det_d.get("recovered") or [])
        live_liquid = len(liquid)
        daily_skips = len(det_d.get("skipped") or [])

        if not liquid:
            raise RuntimeError("no liquid names after ADV$/price filter")

        det_h: dict[str, Any] = {}
        rising_rows, err_h = filter_rising_1h(
            liquid, rising_mult=rising_mult, top_n=top_n,
            detail=det_h, retries=retries, sleep=sleep,
        )
        errors.extend(err_h)
        skipped.extend(det_h.get("skipped") or [])
        recovered.extend({"symbol": x, "stage": "hourly"} for x in det_h.get("recovered") or [])
        rising_syms = [r["symbol"] for r in rising_rows]

        # Union: rising first (ranked), then book
        seen: set[str] = set()
        universe: list[str] = []
        for s in rising_syms + book:
            if s not in seen:
                seen.add(s)
                universe.append(s)

        meta = {
            **meta_base,
            "pool_size": len(pool_syms),
            "liquid_count": len(liquid),
            "rising_count": len(rising_syms),
            "book_count": len(book),
            "universe_size": len(universe),
            "used_fallback": False,
            "fallback_reason": None,
            "errors_sample": errors[:8],
            "error_count": len(errors),
        }
        liq_ref = evaluate_liquid_drop(len(liquid), ref_state)
        meta.update(_skip_summary(skipped))
        hard_skips = sum(1 for x in skipped if x["reason"] in FULL_SCAN_BLOCKING_REASONS)
        meta["full_scan"] = hard_skips == 0
        meta["recovered_on_retry"] = recovered
        meta["liquid_reference"] = liq_ref
        meta["soft_flags"] = [SOFT_FLAG_PARTIAL] if liq_ref["partial"] else []
        record_liquid_scan(reference_path, ref_state, {
            "asOf": meta_base["asOf"], "liquid_count": len(liquid), "pool_size": len(pool_syms),
            "daily_skipped": daily_skips,
            "hard_skipped": hard_skips,
            "short_skipped": len(skipped) - hard_skips,
            "full": hard_skips == 0,
            "partial_flag": liq_ref["partial"],
        })

        payload = {
            "symbols": universe,
            "rising_rows": rising_rows,
            "adv_usd_sample": {s: adv_map[s] for s in rising_syms[:15] if s in adv_map},
            "book_symbols": book,
            "meta": meta,
            "used_fallback": False,
        }
        _write_cache(payload, cache_path)
        return payload

    except Exception as exc:  # noqa: BLE001
        errors.append(f"screen_fail:{exc}")
        if allow_cache_fallback:
            cached = _load_cache(cache_path)
            if cached and cached.get("symbols"):
                used_fallback = True
                cached_syms = [str(s).upper() for s in cached["symbols"]]
                seen = set()
                universe = []
                for s in cached_syms + book:
                    if s and s not in seen and not is_crypto_ticker(s):
                        seen.add(s)
                        universe.append(s)
                prev_meta = cached.get("meta") or {}
                meta = {
                    **meta_base,
                    "pool_size": prev_meta.get("pool_size"),
                    "liquid_count": prev_meta.get("liquid_count"),
                    "rising_count": prev_meta.get("rising_count"),
                    "book_count": len(book),
                    "universe_size": len(universe),
                    "used_fallback": True,
                    "fallback_reason": str(exc),
                    "fallback_cache": str(cache_path),
                    "errors_sample": errors[:8],
                    "error_count": len(errors),
                }
                liq_ref = evaluate_liquid_drop(live_liquid, ref_state)
                meta.update(_skip_summary(skipped))
                meta["recovered_on_retry"] = recovered
                meta["live_liquid_count"] = live_liquid
                meta["liquid_reference"] = liq_ref
                meta["soft_flags"] = [SOFT_FLAG_PARTIAL]  # live scan failed => partial by definition
                return {
                    "symbols": universe,
                    "rising_rows": cached.get("rising_rows") or [],
                    "adv_usd_sample": cached.get("adv_usd_sample") or {},
                    "book_symbols": book,
                    "meta": meta,
                    "used_fallback": True,
                }

        # Last resort: book-only (never DEFAULT_SYMBOLS)
        meta = {
            **meta_base,
            "pool_size": 0,
            "liquid_count": 0,
            "rising_count": 0,
            "book_count": len(book),
            "universe_size": len(book),
            "used_fallback": True,
            "fallback_reason": f"book_only:{exc}",
            "errors_sample": errors[:8],
            "error_count": len(errors),
        }
        meta.update(_skip_summary(skipped))
        meta["recovered_on_retry"] = recovered
        meta["live_liquid_count"] = live_liquid
        meta["liquid_reference"] = evaluate_liquid_drop(live_liquid, ref_state)
        meta["soft_flags"] = [SOFT_FLAG_PARTIAL]
        return {
            "symbols": list(book),
            "rising_rows": [],
            "adv_usd_sample": {},
            "book_symbols": book,
            "meta": meta,
            "used_fallback": True,
        }


def build_screened_universe(
    *,
    book_symbols: Optional[list[str]] = None,
    extra: Optional[list[str]] = None,
    **screen_kwargs: Any,
) -> tuple[list[str], dict[str, Any]]:
    """Convenience: (symbols, universe_meta) for auto_1h.build_universe."""
    result = screen_universe(book_symbols=book_symbols, **screen_kwargs)
    syms = list(result["symbols"])
    if extra:
        seen = set(syms)
        for s in extra:
            u = str(s).upper().strip()
            if u and u not in seen and not is_crypto_ticker(u):
                seen.add(u)
                syms.append(u)
    return syms, result["meta"]

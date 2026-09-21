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
"""

from __future__ import annotations

import json
import re
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

# Crypto / non-equity ticker hints (S&P list should be clean; belt-and-suspenders)
_CRYPTO_RE = re.compile(
    r"(BTC|ETH|USDT|USDC|DOGE|SOL|XRP|ADA|DOT|AVAX|CRYPTO|-USD$|=X$)",
    re.IGNORECASE,
)


def _now_idt_str() -> str:
    return datetime.now(IDT).strftime("%Y-%m-%d %H:%M:%S IDT")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_crypto_ticker(symbol: str) -> bool:
    s = str(symbol).upper().strip()
    if not s:
        return True
    return bool(_CRYPTO_RE.search(s))


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


def filter_liquid_daily(
    symbols: list[str],
    *,
    min_adv_usd: float = MIN_ADV_USD,
    min_price: float = MIN_PRICE,
    chunk_size: int = DAILY_CHUNK,
) -> tuple[list[str], dict[str, float], list[str]]:
    """Return (liquid_symbols, adv_map, errors) using daily ADV$ SMA20."""
    liquid: list[str] = []
    adv_map: dict[str, float] = {}
    errors: list[str] = []

    for chunk in _chunked(symbols, chunk_size):
        try:
            raw = _yf_download(chunk, period=DAILY_PERIOD, interval="1d")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"daily_chunk_fail:{chunk[0]}..{exc}")
            continue
        # Single-symbol download may not be MultiIndex
        for sym in chunk:
            try:
                if len(chunk) == 1 and not isinstance(getattr(raw, "columns", None), pd.MultiIndex):
                    df = raw.copy() if raw is not None else None
                    if df is not None and not df.empty:
                        df.columns = [str(c).lower() for c in df.columns]
                else:
                    df = _extract_ticker_frame(raw, sym)
                if df is None or len(df) < ADV_SMA:
                    continue
                close = df["close"].astype(float)
                vol = df["volume"].astype(float)
                dollar = close * vol
                adv = float(dollar.tail(ADV_SMA).mean())
                last_px = float(close.iloc[-1])
                if not np.isfinite(adv) or not np.isfinite(last_px):
                    continue
                if last_px < min_price:
                    continue
                if adv < min_adv_usd:
                    continue
                liquid.append(sym)
                adv_map[sym] = adv
            except Exception as exc:  # noqa: BLE001
                errors.append(f"daily_{sym}:{exc}")
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
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rank liquid names by confirmed 1H volume / SMA20(vol); keep rising ones.

    Returns (ranked_rows, errors). Each row: {symbol, vol_ratio, last_vol, vol_sma}.
    """
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for chunk in _chunked(symbols, chunk_size):
        try:
            raw = _yf_download(chunk, period=HOURLY_PERIOD, interval="1h")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"hourly_chunk_fail:{chunk[0]}..{exc}")
            continue
        for sym in chunk:
            try:
                if len(chunk) == 1 and not isinstance(getattr(raw, "columns", None), pd.MultiIndex):
                    df = raw.copy() if raw is not None else None
                    if df is not None and not df.empty:
                        df.columns = [str(c).lower() for c in df.columns]
                else:
                    df = _extract_ticker_frame(raw, sym)
                if df is None or "volume" not in df.columns:
                    continue
                conf = _confirmed_1h_frame(df)
                if len(conf) < VOL_SMA + 1:
                    continue
                vol = conf["volume"].astype(float)
                sma = float(vol.tail(VOL_SMA).mean())
                last_vol = float(vol.iloc[-1])
                if not np.isfinite(sma) or sma <= 0 or not np.isfinite(last_vol):
                    continue
                ratio = last_vol / sma
                if ratio < rising_mult:
                    continue
                rows.append(
                    {
                        "symbol": sym,
                        "vol_ratio": round(ratio, 4),
                        "last_vol": last_vol,
                        "vol_sma20": sma,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"hourly_{sym}:{exc}")

    rows.sort(key=lambda r: r["vol_ratio"], reverse=True)
    return rows[:top_n], errors


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

    try:
        pool_syms = list(pool) if pool is not None else load_sp500_pool(sp500_path)
        if len(pool_syms) < 50:
            raise RuntimeError(f"S&P pool too small ({len(pool_syms)})")

        liquid, adv_map, err_d = filter_liquid_daily(
            pool_syms, min_adv_usd=min_adv_usd, min_price=min_price
        )
        errors.extend(err_d)

        if not liquid:
            raise RuntimeError("no liquid names after ADV$/price filter")

        rising_rows, err_h = filter_rising_1h(
            liquid, rising_mult=rising_mult, top_n=top_n
        )
        errors.extend(err_h)
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

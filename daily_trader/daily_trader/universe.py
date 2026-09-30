"""Universe helpers for Daily Trader: ETF reject, classify, liquid defaults.

Stocks + crypto + commodities. NO ETFs.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

AssetClass = Literal["stock", "crypto", "commodity", "etf", "unknown"]

# Explicit ETF / index-product reject list (Yahoo tickers)
ETF_REJECT: frozenset[str] = frozenset(
    {
        # Broad index
        "SPY", "QQQ", "IWM", "DIA", "VOO", "IVV", "VTI", "RSP", "MDY", "IJH", "IJR",
        "SPX", "^GSPC", "^IXIC", "^DJI",
        # Sector / industry ETFs (XL* family + peers)
        "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
        "SMH", "SOXX", "XBI", "IBB", "ARKK", "ARKW", "ARKG", "ARKF", "ARKQ",
        "VGT", "VHT", "VDE", "VFH", "VIS", "VNQ", "VOX", "VDC", "VCR", "VAW", "VPU",
        "IYR", "ITB", "XHB", "KRE", "KBE", "XRT", "XOP", "OIH", "TAN", "ICLN",
        "BOTZ", "HACK", "SKYY", "CLOU", "FINX", "BUG",
        # Commodity / metals ETFs (trade futures proxies instead)
        "GLD", "SLV", "IAU", "SGOL", "SIVR", "GDX", "GDXJ", "SIL", "PPLT", "PALL",
        "USO", "UNG", "BNO", "UCO", "SCO", "DBA", "DBC", "GSG", "PDBC", "COMT",
        "WEAT", "CORN", "SOYB", "JO", "NIB", "BAL",
        # Bond / rate / vol / currency / leveraged single-factor
        "TLT", "IEF", "SHY", "LQD", "HYG", "JNK", "AGG", "BND", "TIP", "MUB",
        "TQQQ", "SQQQ", "UPRO", "SPXU", "TNA", "TZA", "SOXL", "SOXS", "TECL", "TECS",
        "UVXY", "VIXY", "SVXY", "VXX",
        "UUP", "FXE", "FXY", "FXB", "FXA", "CYB",
        # International / thematic ETFs often mistaken for names
        "EEM", "EFA", "VEA", "VWO", "IEMG", "VXUS", "ACWI", "VT",
        "EWJ", "EWZ", "FXI", "KWEB", "MCHI", "INDA",
    }
)

# Heuristic patterns for ETF-like tickers
_ETF_PREFIX_RE = re.compile(r"^XL[A-Z]$", re.IGNORECASE)  # XL*
_ETF_SUFFIX_HINTS = ("ETF", "TRUST", "FUND")

# Crypto Yahoo symbols we allow (spot / CFD proxies)
CRYPTO_SYMBOLS: frozenset[str] = frozenset(
    {
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD",
        "AVAX-USD", "DOT-USD", "LINK-USD", "BNB-USD",
        "BTC", "ETH", "SOL", "XRP", "DOGE",  # bare aliases → normalize
    }
)

# Commodity futures proxies (Yahoo)
COMMODITY_SYMBOLS: frozenset[str] = frozenset(
    {
        "CL=F",   # WTI crude
        "GC=F",   # Gold
        "SI=F",   # Silver
        "NG=F",   # Nat gas
        "HG=F",   # Copper
        "ZC=F",   # Corn
        "ZW=F",   # Wheat
        "ZS=F",   # Soybeans
        "PL=F",   # Platinum
        "PA=F",   # Palladium
        "BZ=F",   # Brent
    }
)

# Liquid US mega/large-cap stocks (~70) — no ETFs
DEFAULT_STOCKS: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B",
    "JPM", "V", "MA", "UNH", "XOM", "LLY", "JNJ", "WMT", "PG", "HD", "COST",
    "ABBV", "MRK", "ORCL", "CRM", "BAC", "CVX", "KO", "PEP", "AMD", "ADBE",
    "NFLX", "CSCO", "TMO", "ACN", "MCD", "ABT", "DIS", "WFC", "INTC", "IBM",
    "GE", "CAT", "AMAT", "QCOM", "TXN", "NOW", "UBER", "INTU", "ISRG", "BKNG",
    "AMGN", "PFE", "HON", "BA", "GS", "MS", "BLK", "AXP", "SPGI", "SYK",
    "PLTR", "SHOP", "SNOW", "PANW", "CRWD", "MU", "LRCX", "KLAC", "SNPS", "CDNS",
    "NKE", "SBUX", "TGT", "LOW", "CMG", "DE", "UNP", "RTX", "LMT", "NOC",
]

DEFAULT_CRYPTO: list[str] = ["BTC-USD", "ETH-USD"]

DEFAULT_COMMODITIES: list[str] = ["CL=F", "GC=F", "SI=F"]

LEV_DEFAULTS: dict[str, int] = {
    "stock": 3,
    "crypto": 2,
    "commodity": 3,
}

LEV_CAPS: dict[str, int] = {
    "stock": 5,       # default band ×2–×5; hard cap ×10 elsewhere
    "crypto": 2,
    "commodity": 10,
}


def normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").upper().strip().replace(".", "-")
    # bare crypto → Yahoo pair
    bare = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "XRP": "XRP-USD", "DOGE": "DOGE-USD"}
    return bare.get(s, s)


def is_etf(symbol: str) -> bool:
    """True if ticker is known/heuristic ETF — must reject for Daily Trader."""
    s = normalize_symbol(symbol)
    if not s:
        return False
    if s in ETF_REJECT:
        return True
    if _ETF_PREFIX_RE.match(s):
        return True
    # ARK* thematic
    if s.startswith("ARK") and len(s) <= 5:
        return True
    return False


def classify(symbol: str) -> AssetClass:
    """Classify ticker into stock / crypto / commodity / etf / unknown."""
    s = normalize_symbol(symbol)
    if not s:
        return "unknown"
    if is_etf(s):
        return "etf"
    if s in CRYPTO_SYMBOLS or s.endswith("-USD") and any(
        s.startswith(c + "-") for c in ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "LINK", "BNB")
    ):
        return "crypto"
    if s in COMMODITY_SYMBOLS or s.endswith("=F"):
        return "commodity"
    # US equity heuristic: letters, optional -class, no =F / -USD
    if re.fullmatch(r"[A-Z]{1,5}(-[A-Z])?", s):
        return "stock"
    return "unknown"


def allows_overnight(symbol: str) -> bool:
    return classify(symbol) == "crypto"


def default_leverage(symbol: str) -> int:
    cls = classify(symbol)
    return int(LEV_DEFAULTS.get(cls, 2))


def leverage_cap(symbol: str) -> int:
    cls = classify(symbol)
    return int(LEV_CAPS.get(cls, 10))


def clamp_leverage(symbol: str, lev: Optional[int] = None) -> int:
    """Clamp to [2, min(10, class cap)]."""
    cls = classify(symbol)
    if cls == "etf":
        raise ValueError(f"ETF rejected: {symbol}")
    base = lev if lev is not None else default_leverage(symbol)
    lo, hi = 2, min(10, leverage_cap(symbol))
    return max(lo, min(hi, int(base)))


def build_scan_universe(
    stocks: Optional[list[str]] = None,
    crypto: Optional[list[str]] = None,
    commodities: Optional[list[str]] = None,
    extra: Optional[list[str]] = None,
    max_stocks: int = 80,
) -> list[str]:
    """Build liquid universe; hard-reject ETFs."""
    raw: list[str] = []
    raw += list(stocks if stocks is not None else DEFAULT_STOCKS[:max_stocks])
    raw += list(crypto if crypto is not None else DEFAULT_CRYPTO)
    raw += list(commodities if commodities is not None else DEFAULT_COMMODITIES)
    if extra:
        raw += list(extra)

    out: list[str] = []
    seen: set[str] = set()
    for sym in raw:
        u = normalize_symbol(sym)
        if not u or u in seen:
            continue
        if is_etf(u) or classify(u) == "etf":
            continue
        seen.add(u)
        out.append(u)
    return out


def reject_reason(symbol: str) -> Optional[str]:
    """If symbol must be rejected, return reason; else None."""
    s = normalize_symbol(symbol)
    if is_etf(s):
        return "ETF_REJECT"
    cls = classify(s)
    if cls == "etf":
        return "ETF_REJECT"
    if cls == "unknown":
        return "UNKNOWN_ASSET_CLASS"
    return None

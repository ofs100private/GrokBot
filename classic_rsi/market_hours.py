"""US regular-session check (NYSE 09:30-16:00 America/New_York, Mon-Fri, minus holidays).

Holiday / early-close tables cover 2026-2027 (NYSE published calendar). Outside those years the
check fails closed (MARKET_CALENDAR_UNKNOWN) so it cannot silently pass.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN, CLOSE, EARLY_CLOSE = time(9, 30), time(16, 0), time(13, 0)
KNOWN_YEARS = (2026, 2027)
HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
}
EARLY_CLOSES = {date(2026, 11, 27), date(2026, 12, 24), date(2027, 11, 26)}


def us_session(now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        return {"open": False, "reason": "NAIVE_TIMESTAMP"}
    et = now.astimezone(ET)
    d = et.date()
    base = {"et": et.strftime("%Y-%m-%d %H:%M %Z")}
    if d.year not in KNOWN_YEARS:
        return {**base, "open": False, "reason": "MARKET_CALENDAR_UNKNOWN"}
    if et.weekday() >= 5:
        return {**base, "open": False, "reason": "WEEKEND"}
    if d in HOLIDAYS:
        return {**base, "open": False, "reason": "US_HOLIDAY"}
    close = EARLY_CLOSE if d in EARLY_CLOSES else CLOSE
    if not (OPEN <= et.time() < close):
        return {**base, "open": False, "reason": "OUTSIDE_RTH", "close": close.strftime("%H:%M")}
    return {**base, "open": True, "reason": None, "close": close.strftime("%H:%M")}


# ---------------------------------------------------------------- 24x5 / crypto windows (2026-10-16)
# eToro 24/5 for US stocks/ETFs: Sun 20:05 ET -> Fri 20:00 ET (overnight + pre + RTH + after-hours),
# closed on US market holidays. Not every instrument supports it: the per-instrument live flag
# (isOpen from market-data / prepare-trade rejection) always wins; if it is unknown the caller may
# fall back to RTH. Crypto majors trade 24/7 including weekends.
EXT_SUN_OPEN, EXT_FRI_CLOSE = time(20, 5), time(20, 0)


def extended_session(now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        return {"open": False, "reason": "NAIVE_TIMESTAMP"}
    et = now.astimezone(ET)
    d, t, wd = et.date(), et.time(), et.weekday()
    base = {"et": et.strftime("%Y-%m-%d %H:%M %Z"), "session": "extended_24x5"}
    if d.year not in KNOWN_YEARS:
        return {**base, "open": False, "reason": "MARKET_CALENDAR_UNKNOWN"}
    if wd == 5 or (wd == 6 and t < EXT_SUN_OPEN) or (wd == 4 and t >= EXT_FRI_CLOSE):
        return {**base, "open": False, "reason": "WEEKEND"}
    # trading date the overnight session belongs to (after 20:00 ET -> next day's session)
    sess = d + timedelta(days=1) if t >= time(20, 0) else d
    if sess in HOLIDAYS or (t < time(20, 0) and d in HOLIDAYS):
        return {**base, "open": False, "reason": "US_HOLIDAY"}
    return {**base, "open": True, "reason": None}


def trading_window(asset_class: Optional[str], now: Optional[datetime] = None, *,
                   instrument_is_open: Optional[bool] = None, supports_extended: Optional[bool] = None) -> dict:
    """Open/closed for one asset class (fail-safe).

    crypto  -> 24/7 (an explicit isOpen=False still closes it).
    stock/etf -> calendar window (24x5 if supports_extended is not False, else RTH) AND an explicit
                 live per-instrument isOpen=True. Unknown isOpen (None) => CLOSED. Unknown extended
                 support is therefore only tradable when the live read says the instrument is open now.
    """
    ac = str(asset_class or "").lower()
    if ac == "crypto":
        if instrument_is_open is False:
            return {"open": False, "reason": "INSTRUMENT_CLOSED", "session": "crypto_24x7"}
        return {"open": True, "reason": None, "session": "crypto_24x7"}
    if ac not in ("stock", "etf"):
        return {"open": False, "reason": "ASSET_CLASS_UNKNOWN", "session": None}
    out = ({**us_session(now), "session": "rth_fallback"} if supports_extended is False else extended_session(now))
    if not out["open"]:
        return out
    if instrument_is_open is None:
        return {**out, "open": False, "reason": "INSTRUMENT_OPEN_UNKNOWN"}
    if instrument_is_open is not True:
        return {**out, "open": False, "reason": "INSTRUMENT_CLOSED"}
    return out


# ---------------------------------------------------------------- trading-day helpers (fix3)
def is_trading_day(d: date) -> bool:
    """Weekday, known calendar year, not a US market holiday."""
    return d.year in KNOWN_YEARS and d.weekday() < 5 and d not in HOLIDAYS


def last_completed_session(now: datetime) -> Optional[date]:
    """ET date of the most recent session whose regular close has passed (None if calendar unknown)."""
    et = now.astimezone(ET)
    d = et.date()
    close = EARLY_CLOSE if d in EARLY_CLOSES else CLOSE
    if not (is_trading_day(d) and et.time() >= close):
        d -= timedelta(days=1)
    for _ in range(15):
        if d.year not in KNOWN_YEARS:
            return None
        if is_trading_day(d):
            return d
        d -= timedelta(days=1)
    return None


def trading_days_between(older: date, newer: date) -> int:
    """Number of trading days after `older` up to and including `newer` (0 if same day; <0 if older > newer)."""
    if older > newer:
        return -1
    n, d = 0, older
    while d < newer:
        d += timedelta(days=1)
        if is_trading_day(d):
            n += 1
    return n

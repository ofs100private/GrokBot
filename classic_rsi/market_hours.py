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

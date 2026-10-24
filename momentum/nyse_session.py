"""NYSE session helpers for Momentum EOD bots."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import exchange_calendars as xcals
    _XNYS = xcals.get_calendar("XNYS")
except Exception:  # pragma: no cover
    _XNYS = None

IL = ZoneInfo("Asia/Jerusalem")
NY = ZoneInfo("America/New_York")


def nyse_today_is_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(tz=IL)
    ny_date = now.astimezone(NY).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    d = pd.Timestamp(ny_date)
    if _XNYS is None:
        # Fallback: weekdays only
        return d.weekday() < 5
    return bool(_XNYS.is_session(d))


def in_intraday_ban(now: datetime | None = None) -> bool:
    """First 2h of US RTH on the New York clock: 09:30-11:30 ET (2026-10-24 DST fix).

    = 16:30-18:30 IL when IL and US are on the same DST state; 15:30-17:30 IL on 2026-10-26..30
    (IL already on winter time, US still on EDT). Was a fixed 16:30-18:30 IL window."""
    now = now or datetime.now(tz=IL)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IL)
    t = now.astimezone(NY)
    start = t.replace(hour=9, minute=30, second=0, microsecond=0)
    return start <= t < start + timedelta(hours=2)

"""NYSE session helpers for Momentum EOD bots."""
from __future__ import annotations

from datetime import datetime
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
    """First ~2h of US RTH in Israel clock: 16:30–18:30 (EDT-aligned playbook)."""
    now = now or datetime.now(tz=IL)
    local = now.astimezone(IL)
    mins = local.hour * 60 + local.minute
    return (16 * 60 + 30) <= mins < (18 * 60 + 30)

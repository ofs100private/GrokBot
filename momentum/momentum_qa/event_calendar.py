"""US macro event-vol freeze calendar for Momentum new-buy gate.

Freeze new BUYs when *today* (NYSE date) OR the *next* NYSE session is an
event day. Prior-session freeze: if tomorrow's next open is an event day,
tonight's EOD also freezes.

Sources (document; Ofer may edit lists):
- FOMC decision days: federalreserve.gov/monetarypolicy/fomccalendars.htm
  (2nd day of each 2026 FOMC meeting; statement ~2pm ET).
- NFP / Employment Situation: bls.gov/schedule/news_release/empsit.htm
- CPI: bls.gov/schedule/2026/*_sched_list.htm (Oct–Dec confirmed; Jul–Sep
  approximate from typical BLS mid-month pattern — EDIT if BLS revises).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import exchange_calendars as xcals

    _XNYS = xcals.get_calendar("XNYS")
except Exception:  # pragma: no cover
    _XNYS = None

IL = ZoneInfo("Asia/Jerusalem")
NY = ZoneInfo("America/New_York")

# FOMC *decision* days (meeting day 2) — 2026 + early 2027
FOMC_DECISION_DAYS: list[date] = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),  # Sep 15–16 meeting; decision Wed 16
    date(2026, 10, 28),
    date(2026, 12, 9),
    date(2027, 1, 27),
]

# NFP / Employment Situation — BLS schedule (Q3–Q4 2026 + adjacent)
NFP_DAYS: list[date] = [
    date(2026, 7, 2),
    date(2026, 8, 7),
    date(2026, 9, 4),
    date(2026, 10, 2),
    date(2026, 11, 6),
    date(2026, 12, 4),
]

# CPI — Oct–Dec from BLS 2026 monthly schedules; Jul–Sep approximate (EDITABLE)
CPI_DAYS: list[date] = [
    date(2026, 7, 14),  # approx — verify vs BLS July 2026 schedule
    date(2026, 8, 12),  # approx — verify vs BLS August 2026 schedule
    date(2026, 9, 11),  # approx — verify vs BLS September 2026 schedule
    date(2026, 10, 14),  # BLS: CPI for Sep 2026
    date(2026, 11, 10),  # BLS: CPI for Oct 2026
    date(2026, 12, 10),  # BLS: CPI for Nov 2026
]

EVENT_DAYS: set[date] = set(FOMC_DECISION_DAYS) | set(NFP_DAYS) | set(CPI_DAYS)

EVENT_LABELS: dict[date, str] = {}
for d in FOMC_DECISION_DAYS:
    EVENT_LABELS[d] = "FOMC"
for d in NFP_DAYS:
    EVENT_LABELS[d] = "NFP"
for d in CPI_DAYS:
    EVENT_LABELS.setdefault(d, "CPI")  # FOMC/NFP win if collision


def _ny_date(now_il: datetime) -> date:
    return now_il.astimezone(NY).date()


def next_nyse_session(after: date) -> date | None:
    """Next NYSE session strictly after `after` (calendar date in NY)."""
    if _XNYS is not None:
        # sessions_window / date_to_session helpers vary by version
        start = pd.Timestamp(after + timedelta(days=1))
        end = pd.Timestamp(after + timedelta(days=15))
        try:
            sessions = _XNYS.sessions_in_range(start, end)
            if len(sessions):
                return sessions[0].date()
        except Exception:
            pass
    # Weekday fallback
    d = after + timedelta(days=1)
    for _ in range(10):
        if d.weekday() < 5:
            return d
        d += timedelta(days=1)
    return None


def is_event_vol_freeze(now_il: datetime | None = None) -> tuple[bool, str]:
    """Return (freeze, reason). Freeze if today or next NYSE session is event day."""
    now_il = now_il or datetime.now(tz=IL)
    if now_il.tzinfo is None:
        now_il = now_il.replace(tzinfo=IL)
    today = _ny_date(now_il)
    nxt = next_nyse_session(today)

    if today in EVENT_DAYS:
        label = EVENT_LABELS.get(today, "MACRO")
        return True, f"EVENT_VOL_FREEZE today={today.isoformat()} event={label}"
    if nxt is not None and nxt in EVENT_DAYS:
        label = EVENT_LABELS.get(nxt, "MACRO")
        return (
            True,
            f"EVENT_VOL_FREEZE prior_session today={today.isoformat()} "
            f"next_open={nxt.isoformat()} event={label}",
        )
    return False, f"no_event_freeze today={today.isoformat()} next_open={nxt}"

"""EOD clock: NYSE session/close from the calendar, routine times from the routine schedule.

2026-10-24d (Ofer 2026-10-24 00:53-00:54 IDT): from Mon 2026-10-26 the Momentum EOD routines run at FIXED
Israel times, permanently (PM 21:40, backup 21:42, screener 21:45, watchdog 21:50, feedback 22:05,
CRON_TZ=Asia/Jerusalem). The routine-relative reference times are therefore anchored to the scheduled PM
time, not to the close:
  pm_scheduled       = scheduled PM cron (21:40 IL)          [before 2026-10-26: close-20m, legacy]
  watch_start        = pm_scheduled + 6m  (21:46 IL)          miss checks become active
  late_cron          = pm_scheduled + 7m  (21:47 IL)          "cron ran late" hygiene threshold
  screener_deadline  = pm_scheduled + 10m (21:50 IL)          EOD_SCREENER_MISSED deadline
  eod_window_start   = min(close-2h, pm_scheduled-40m)        evening rows window
In the gap week 2026-10-26..30 (close 22:00 IL) this equals the previous close-derived values exactly
(21:40/21:46/21:47/21:50/20:00). From 2026-11-02 (close 23:00 IL) the times stay 21:40/21:46/21:47/21:50 and
the window starts 21:00, so the 21:50 watchdog sees a PM miss. Days before 2026-10-26 keep the legacy
close-20m rule (historic replays unchanged). EOD_SCHEDULE_OVERRIDES holds one-off cron days (none today;
e.g. early closes, QA D-I1). The NYSE close itself (and so the place_lock buy window) still comes from the calendar.

Previous design (2026-10-24 DST fix, kept for days before 2026-10-26):

Every EOD time used by the Momentum chain is derived from the NYSE regular-session close
(16:00 America/New_York on the session date) and converted to Asia/Jerusalem with zoneinfo,
so the US/Israel DST gaps (IL leaves DST 2026-10-25, US leaves 2026-11-01) are handled
automatically instead of by hardcoded IL clock times.

Normal alignment (IL and US both on summer, or both on winter time): close = 23:00 IL and every
derived time equals the old constant (22:40 / 22:46 / 22:47 / 22:50 / 21:00).
2026-10-26..30: close = 22:00 IL -> 21:40 / 21:46 / 21:47 / 21:50 / 20:00.

Actual session close (DST-M2, 2026-10-24b): the close comes from exchange_calendars XNYS when it is
installed and covers the date (loaded lazily, once); otherwise from the hardcoded NYSE table below
(2026 early closes 11-27 and 12-24 at 13:00 NY; remaining 2026 holidays 11-26 and 12-25; full 2027 table (D-L1); else weekdays).
Early-close days: close 13:00 NY = 20:00 IL. The place guard refuses automatic buys all day (EARLY_CLOSE_DAY,
momentum_qa.place_lock). Since 2026-10-24d the routine times do NOT move with an early close (the crons are fixed
IL times): PM 21:40 runs after the 20:00 close and schedule_alignment flags after_close, unless a one-off
schedule is added to EOD_SCHEDULE_OVERRIDES (QA D-I1, not decided). Legacy days (<2026-10-26) still derive from the close.
Importing this module stays pure stdlib; pandas/exchange_calendars load only on the first lookup.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
NY = ZoneInfo("America/New_York")

RTH_OPEN_NY = time(9, 30)
RTH_CLOSE_NY = time(16, 0)
INTRADAY_BAN = timedelta(hours=2)            # first 2h of RTH: no buys (was 16:30-18:30 IL)

# Offsets before the NYSE close (old IL constants when close = 23:00 IL)
PM_SCHEDULED_BEFORE_CLOSE = timedelta(minutes=20)       # 22:40 primary PM / scheduled EOD window start
WATCH_START_BEFORE_CLOSE = timedelta(minutes=14)        # 22:46 miss checks become active
LATE_CRON_BEFORE_CLOSE = timedelta(minutes=13)          # 22:47 "cron ran late" hygiene threshold
SCREENER_DEADLINE_BEFORE_CLOSE = timedelta(minutes=10)  # 22:50 EOD_SCREENER_MISSED deadline
EOD_WINDOW_BEFORE_CLOSE = timedelta(hours=2)            # 21:00 evening window start (was T21..T23)

# Routine schedule anchor (2026-10-24d). Offsets after the scheduled PM time keep the old relationships
# (watch = PM+6m, late = PM+7m, deadline = PM+10m) in every regime.
EOD_SCHEDULE_FIXED_FROM = date(2026, 10, 26)            # first IL date on the fixed IL crons
EOD_SCHEDULE_IL = {"pm": time(21, 40), "backup": time(21, 42), "screener": time(21, 45),
                   "watchdog": time(21, 50), "feedback": time(22, 5)}
EOD_SCHEDULE_OVERRIDES: dict = {}                       # {date: {"pm": time, ...}} one-off cron days; empty
WATCH_START_AFTER_PM = timedelta(minutes=6)
LATE_CRON_AFTER_PM = timedelta(minutes=7)
SCREENER_DEADLINE_AFTER_PM = timedelta(minutes=10)
EOD_WINDOW_BEFORE_PM = timedelta(minutes=40)
_LEGACY_AFTER_PM = {"pm": timedelta(0), "backup": timedelta(minutes=2), "screener": timedelta(minutes=5),
                    "watchdog": timedelta(minutes=10), "feedback": timedelta(minutes=25)}


# Fallback when exchange_calendars is missing or the date is outside its range (NYSE published calendar).
# 2026: remaining dates from 2026-10-24. 2027 (D-L1, 2026-10-24c): generated from exchange_calendars 4.13.2
# XNYS (start 2026-01-01, end 2027-12-31); matches NYSE's published 2027 holidays and early closes.
EARLY_CLOSES_NY = {date(2026, 11, 27): time(13, 0), date(2026, 12, 24): time(13, 0),
                   date(2027, 11, 26): time(13, 0)}
HOLIDAYS_NY = {date(2026, 11, 26), date(2026, 12, 25),
               date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
               date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24)}
FALLBACK_YEARS = frozenset({2026, 2027})  # years the table above covers (2026 only from 2026-10-24)

_XNYS_UNSET = object()
_xnys_cache = _XNYS_UNSET


def _xnys():
    """exchange_calendars XNYS, loaded on first use; None if the library is unavailable."""
    global _xnys_cache
    if _xnys_cache is _XNYS_UNSET:
        try:
            import exchange_calendars as xcals
            _xnys_cache = xcals.get_calendar("XNYS")
        except Exception:  # pragma: no cover - library missing / broken
            _xnys_cache = None
    return _xnys_cache


def session_info(day) -> dict:
    """NYSE session for NY calendar date `day` (= IL date in the IL evening).
    {"day", "is_session", "close_ny" "HH:MM", "early_close", "source"}; never raises for a valid date."""
    return dict(_session_info(_as_date(day)))


@lru_cache(maxsize=512)
def _session_info(d: date) -> dict:
    cal = _xnys()
    if cal is not None:
        try:
            import pandas as pd
            ts = pd.Timestamp(d.isoformat())
            if not cal.is_session(ts):
                return {"day": d.isoformat(), "is_session": False, "close_ny": None, "early_close": False,
                        "source": "exchange_calendars"}
            c = cal.session_close(ts).tz_convert("America/New_York")
            ct = time(c.hour, c.minute)
            return {"day": d.isoformat(), "is_session": True, "close_ny": ct.strftime("%H:%M"),
                    "early_close": ct < RTH_CLOSE_NY, "source": "exchange_calendars"}
        except Exception:  # out of the calendar's range etc. -> table
            pass
    if d.weekday() >= 5 or d in HOLIDAYS_NY:
        return {"day": d.isoformat(), "is_session": False, "close_ny": None, "early_close": False,
                "source": "hardcoded"}
    ct = EARLY_CLOSES_NY.get(d, RTH_CLOSE_NY)
    return {"day": d.isoformat(), "is_session": True, "close_ny": ct.strftime("%H:%M"),
            "early_close": ct < RTH_CLOSE_NY, "source": "hardcoded"}


def calendar_covers(day) -> bool:
    """D-L1: True if the session data for `day` is trustworthy: exchange_calendars answered, or the
    hardcoded fallback table covers the year. False -> automatic buys must fail closed."""
    d = _as_date(day)
    return session_info(d)["source"] == "exchange_calendars" or d.year in FALLBACK_YEARS


def _close_ny_time(d: date) -> time:
    """Actual close (NY wall clock) for a session; the regular 16:00 on non-session days."""
    info = session_info(d)
    if not info["is_session"] or not info["close_ny"]:
        return RTH_CLOSE_NY
    h, m = map(int, info["close_ny"].split(":"))
    return time(h, m)


def _as_date(day) -> date:
    if isinstance(day, datetime):
        return day.astimezone(IL).date()
    if isinstance(day, date):
        return day
    return date.fromisoformat(str(day)[:10])


def nyse_close_il(day) -> datetime:
    """Actual NYSE close for the session on IL calendar date `day` (early closes included; regular 16:00 NY
    on non-session days), as an IL-aware datetime. The IL evening and the NY afternoon share the date."""
    d = _as_date(day)
    return datetime.combine(d, _close_ny_time(d), tzinfo=NY).astimezone(IL)


def regular_close_il(day) -> datetime:
    """Regular 16:00 NY close, ignoring early closes."""
    d = _as_date(day)
    return datetime.combine(d, RTH_CLOSE_NY, tzinfo=NY).astimezone(IL)


def nyse_open_il(day) -> datetime:
    d = _as_date(day)
    return datetime.combine(d, RTH_OPEN_NY, tzinfo=NY).astimezone(IL)


def schedule_mode(day) -> str:
    d = _as_date(day)
    if d in EOD_SCHEDULE_OVERRIDES:
        return "override"
    return "fixed_il" if d >= EOD_SCHEDULE_FIXED_FROM else "legacy_close_minus_20m"


def routine_schedule_il(day) -> dict:
    """Scheduled IL datetimes of the EOD routines on IL date `day` {pm, backup, screener, watchdog, feedback}."""
    d = _as_date(day)
    mode = schedule_mode(d)
    if mode == "legacy_close_minus_20m":
        pm = nyse_close_il(d) - PM_SCHEDULED_BEFORE_CLOSE
        return {k: pm + off for k, off in _LEGACY_AFTER_PM.items()}
    table = {**EOD_SCHEDULE_IL, **(EOD_SCHEDULE_OVERRIDES.get(d) or {})}
    return {k: datetime.combine(d, t, tzinfo=IL) for k, t in table.items()}


def eod_clock(day) -> dict:
    """All EOD reference times for IL date `day` (IL-aware datetimes). The close comes from the NYSE
    calendar; the routine-relative times are anchored to the scheduled PM cron (see module docstring)."""
    close = nyse_close_il(day)
    d = _as_date(day)
    info = session_info(d)
    sched = routine_schedule_il(d)
    pm = sched["pm"]
    return {
        "day": d.isoformat(),
        "is_session": info["is_session"],
        "early_close": info["early_close"],
        "calendar_source": info["source"],
        "schedule_mode": schedule_mode(d),
        "nyse_open_il": nyse_open_il(d),
        "nyse_close_il": close,
        "eod_window_start": min(close - EOD_WINDOW_BEFORE_CLOSE, pm - EOD_WINDOW_BEFORE_PM),
        "pm_scheduled": pm,
        "watch_start": pm + WATCH_START_AFTER_PM,
        "late_cron": pm + LATE_CRON_AFTER_PM,
        "screener_deadline": pm + SCREENER_DEADLINE_AFTER_PM,
        "routine_schedule_il": {k: hhmm(v) for k, v in sched.items()},
        "day_end": datetime.combine(d, time(23, 59, 59), tzinfo=IL),
        "il_minus_ny_h": round((close.utcoffset() - close.astimezone(NY).utcoffset()).total_seconds() / 3600, 2),
    }


def eod_clock_json(day) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in eod_clock(day).items()}


def parse_il(ts) -> datetime | None:
    """ISO string -> IL-aware datetime (naive = IL); None if unparsable / not a string."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt.replace(tzinfo=IL) if dt.tzinfo is None else dt.astimezone(IL)


def in_eod_window(ts, day=None) -> bool:
    """True if ts falls on IL date `day` (default: its own IL date) at/after the evening window start."""
    dt = parse_il(ts)
    if dt is None:
        return False
    d = _as_date(day) if day is not None else dt.date()
    if dt.date() != d:
        return False
    return dt >= eod_clock(d)["eod_window_start"]


def in_intraday_ban(now: datetime | None = None) -> bool:
    """First 2h of NYSE RTH, evaluated on the New York clock (09:30-11:30 ET).
    16:30-18:30 IL in normal alignment; 15:30-17:30 IL on 2026-10-26..30."""
    now = now or datetime.now(tz=IL)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IL)
    t = now.astimezone(NY)
    start = datetime.combine(t.date(), RTH_OPEN_NY, tzinfo=NY)
    return start <= t < start + INTRADAY_BAN


def hhmm(dt: datetime) -> str:
    return dt.astimezone(IL).strftime("%H:%M")

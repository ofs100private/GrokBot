#!/usr/bin/env python3
"""Detect EOD screener / position_manager misses and optionally require catch-up.

EOD reference times come from momentum_qa.market_clock.eod_clock. Since 2026-10-24d they are anchored to the
fixed IL routine schedule (from 2026-10-26: PM 21:40, backup 21:42, screener 21:45, watchdog 21:50, feedback 22:05):
watch 21:46 (PM+6m), late cron 21:47 (PM+7m), screener deadline 21:50 (PM+10m), window from min(close-2h, PM-40m)
(20:00 IL when the close is 22:00, 21:00 IL when it is 23:00). Days before 2026-10-26 keep the legacy close-20m
anchor (close 23:00: 21:00 / 22:46 / 22:50). Early-close days keep the fixed schedule (the crons don't move;
schedule_alignment flags after_close). NYSE holidays are not misses (reason nyse_closed).

SCHEDULE (DST-M1, 2026-10-24b): night_status["schedule"] flags SCHEDULE_MISALIGNED when tonight's first
position_manager RUN_START is more than 30m before the scheduled PM time (before 21:10 IL on the fixed
schedule) or at/after the NYSE close. Alert only: exit codes are unchanged; feedback_daily maps it to WATCH.

SCREENER MISS = weekday, now >= watch_start (scheduled PM+6m), and no screener ACTION/HALT/BUY/SKIP/ERROR
in tonight's EOD window (>= eod_window_start, same IL date).

PM MISS = weekday, now >= watch_start, and no position_manager ACTION/RUN_END in the EOD window.

Ownership (2026-10-22, QA F1–F4): per-night owner lock + rows. --defer-reason (primary) ->
PRIMARY_PROCEEDS | PRIMARY_DEFERRED; --takeover-reason (backup) -> BACKUP_TAKEOVER;
--screener-gate (scheduled screener cron, PM+5m), --screener-lock (every screener run), --place-watch (watchdog).
Ownership is per run (--run-tag). Exit 3 = do not run, 4 = place-watch alert. See place_flow.md step 0.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
try:
    from momentum_qa import market_clock as MC
except ImportError:  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from momentum_qa import market_clock as MC
AUDIT = Path(os.environ.get("MOMENTUM_AUDIT_DIR", "/workspace/momentum_audit"))


def _parse_ts_il(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _day_rows(day: str) -> list[dict]:
    """All audit rows for the calendar day (IL date in filename)."""
    path = AUDIT / f"{day}.jsonl"
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(r)
    return rows


def _eod_rows(day: str) -> list[dict]:
    """Evening window rows: from NYSE close-2h to the end of the IL day (manual early EOD + scheduled +
    catch-up). = T21–T23 IL in normal alignment, T20–T23 on 2026-10-26..30 (2026-10-24 DST fix).
    Early/manual EOD counts toward 'screener already ran' and the miss gate (QA Bot 2026-09-23).
    """
    return [r for r in _day_rows(day) if MC.in_eod_window(r.get("ts_il"), day)]


def screener_actions_by_deadline(day: str, hour: int | None = None, minute: int | None = None) -> list[dict]:
    """Screener ACTION BUY/HALT/SKIP/ERROR with ts_il ≤ deadline that calendar day.

    Standing gate (2026-09-11 / QA 2026-09-23): EOD_SCREENER_MISSED iff none by the screener deadline
    (scheduled PM+10m: 21:50 IL from 2026-10-26; legacy close-10m before). Early/manual EOD counts. An explicit
    hour/minute (IL) overrides the derived deadline (legacy callers / tests).
    """
    if hour is None and minute is None:
        dl = MC.eod_clock(day)["screener_deadline"]
        deadline_min = dl.hour * 60 + dl.minute
    else:
        deadline_min = (22 if hour is None else hour) * 60 + (50 if minute is None else minute)
    out: list[dict] = []
    for r in _day_rows(day):
        if r.get("script") != "momentum_screener.py":
            continue
        if r.get("event") != "ACTION":
            continue
        if r.get("action") not in ("HALT", "BUY", "SKIP", "ERROR"):
            continue
        dt = _parse_ts_il(r.get("ts_il") or "")
        if dt is None:
            continue
        if dt.strftime("%Y-%m-%d") != day:
            continue
        if dt.hour * 60 + dt.minute <= deadline_min:
            out.append(r)
    return out


def screener_ran_tonight(now: datetime | None = None) -> dict:
    now = now or datetime.now(tz=IL)
    day = now.strftime("%Y-%m-%d")
    hits = [
        r
        for r in _eod_rows(day)
        if r.get("script") == "momentum_screener.py"
        and r.get("event") in ("ACTION", "RUN_END", "RUN_START")
    ]
    eod_actions = [
        h
        for h in hits
        if h.get("event") == "ACTION"
        and h.get("action") in ("HALT", "BUY", "SKIP", "ERROR")
    ]
    return {
        "day": day,
        "now_il": now.isoformat(),
        "has_eod_screener_action": bool(eod_actions),
        "actions": [
            {"ts_il": a.get("ts_il"), "action": a.get("action"), "symbol": a.get("symbol")}
            for a in eod_actions
        ],
        "run_starts": [h.get("ts_il") for h in hits if h.get("event") == "RUN_START"],
    }


def pm_ran_tonight(now: datetime | None = None) -> dict:
    now = now or datetime.now(tz=IL)
    day = now.strftime("%Y-%m-%d")
    hits = [r for r in _eod_rows(day) if r.get("script") == "position_manager.py"]
    actions = [
        h
        for h in hits
        if h.get("event") == "ACTION"
        and h.get("action") in ("HOLD", "CLOSE", "MOVE_SL_BREAKEVEN", "SKIP", "ERROR")
    ]
    starts = [h.get("ts_il") for h in hits if h.get("event") == "RUN_START"]
    ends = [h.get("ts_il") for h in hits if h.get("event") == "RUN_END"]
    return {
        "day": day,
        "now_il": now.isoformat(),
        "has_eod_pm_action": bool(actions) or bool(ends),
        "actions": [
            {"ts_il": a.get("ts_il"), "action": a.get("action"), "symbol": a.get("symbol")}
            for a in actions
        ],
        "run_starts": starts,
        "run_ends": ends,
    }


def _nyse_closed(day: str) -> bool:
    try:
        return not MC.session_info(day)["is_session"]
    except Exception:  # never break the miss check on a calendar problem: treat as a session
        return False


def is_miss(now: datetime | None = None) -> tuple[bool, dict]:
    """Backward-compatible: True only for screener miss (exit code / old callers). """
    now = now or datetime.now(tz=IL)
    status = screener_ran_tonight(now)
    if now.weekday() >= 5:
        return False, {**status, "reason": "weekend"}
    if _nyse_closed(status["day"]):
        return False, {**status, "reason": "nyse_closed"}
    if now < MC.eod_clock(status["day"])["watch_start"]:
        return False, {**status, "reason": "before_watch_window"}
    if status["has_eod_screener_action"]:
        return False, {**status, "reason": "screener_already_ran"}
    return True, {**status, "reason": "EOD_SCREENER_MISSED", "deviation_code": "EOD_SCREENER_MISSED"}


def is_pm_miss(now: datetime | None = None) -> tuple[bool, dict]:
    now = now or datetime.now(tz=IL)
    status = pm_ran_tonight(now)
    if now.weekday() >= 5:
        return False, {**status, "reason": "weekend"}
    if _nyse_closed(status["day"]):
        return False, {**status, "reason": "nyse_closed"}
    if now < MC.eod_clock(status["day"])["watch_start"]:
        return False, {**status, "reason": "before_watch_window"}
    if status["has_eod_pm_action"]:
        return False, {**status, "reason": "pm_already_ran"}
    return True, {**status, "reason": "EOD_PM_MISSED", "deviation_code": "EOD_PM_MISSED"}


SCHEDULE_EARLY_SLACK = timedelta(minutes=30)     # alert when PM RUN_START < pm_scheduled - 30m
SCHEDULE_LOOKBACK = timedelta(hours=4)           # PM RUN_STARTs considered: from close-4h


def schedule_alignment(day: str, rows: list[dict] | None = None) -> dict:
    """DST-M1: is tonight's PM run aligned with the actual NYSE close? Read-only, never raises.
    misaligned when the first position_manager RUN_START in [close-4h, day end] is before
    pm_scheduled-30m [direction early] or at/after the close [direction after_close]."""
    try:
        clk = MC.eod_clock(day)
        rows = _day_rows(day) if rows is None else rows
        lo = clk["nyse_close_il"] - SCHEDULE_LOOKBACK
        starts = sorted(dt for dt in (MC.parse_il(r.get("ts_il")) for r in rows
                                      if r.get("script") == "position_manager.py" and r.get("event") == "RUN_START")
                        if dt is not None and dt.date().isoformat() == day and dt >= lo)
        out = {"day": day, "pm_first_run_start": starts[0].isoformat() if starts else None,
               "pm_scheduled": clk["pm_scheduled"].isoformat(), "nyse_close_il": clk["nyse_close_il"].isoformat(),
               "early_limit": (clk["pm_scheduled"] - SCHEDULE_EARLY_SLACK).isoformat(),
               "early_close": clk.get("early_close", False), "misaligned": False, "alerts": []}
        if not starts or not clk.get("is_session", True):
            return out
        first = starts[0]
        direction = None
        if first < clk["pm_scheduled"] - SCHEDULE_EARLY_SLACK:
            direction = "early"
        elif first >= clk["nyse_close_il"]:
            direction = "after_close"
        if direction:
            mins = round((clk["nyse_close_il"] - first).total_seconds() / 60)
            out["misaligned"] = True
            out["alerts"].append({
                "code": "SCHEDULE_MISALIGNED", "direction": direction, "pm_run_start": first.isoformat(),
                "minutes_before_close": mins,
                "text": (f"PM RUN_START {MC.hhmm(first)} IL is {mins}m before the NYSE close {MC.hhmm(clk['nyse_close_il'])} IL"
                         if direction == "early" else
                         f"PM RUN_START {MC.hhmm(first)} IL is at/after the NYSE close {MC.hhmm(clk['nyse_close_il'])} IL")
                        + f" (expected ~{MC.hhmm(clk['pm_scheduled'])} IL = scheduled PM cron); check the EOD crons / early close."})
        return out
    except Exception as e:  # alert-only helper: never break callers
        return {"day": day, "misaligned": False, "alerts": [], "error": f"{type(e).__name__}: {e}"}


def night_status(now: datetime | None = None) -> dict:
    now = now or datetime.now(tz=IL)
    scr_miss, scr = is_miss(now)
    pm_miss, pm = is_pm_miss(now)
    # If PM missed, next job is PM then screener. If only screener missed, next is screener.
    next_job = "position_manager" if pm_miss else ("screener" if scr_miss else None)
    return {
        "day": now.strftime("%Y-%m-%d"),
        "now_il": now.isoformat(),
        "screener_miss": scr_miss,
        "pm_miss": pm_miss,
        "any_miss": scr_miss or pm_miss,
        "next_job": next_job,
        "eod_clock": MC.eod_clock_json(now.strftime("%Y-%m-%d")),
        "schedule": schedule_alignment(now.strftime("%Y-%m-%d")),
        "chain_owner": chain_owner(now.strftime("%Y-%m-%d"), pm, now),
        "screener": scr,
        "position_manager": pm,
    }


def soft_nudge_after_pm(now: datetime | None = None) -> dict:
    """Soft: PM RUN_END with no screener RUN_START within ~2 minutes (same night)."""
    now = now or datetime.now(tz=IL)
    day = now.strftime("%Y-%m-%d")
    path = AUDIT / f"{day}.jsonl"
    if not path.exists():
        return {"nudge": False, "reason": "no_audit"}
    pm_end = None
    scr_start = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not MC.in_eod_window(r.get("ts_il"), day):  # was T22/T23 only (missed 21:4x PM ends)
            continue
        if r.get("script") == "position_manager.py" and r.get("event") == "RUN_END":
            pm_end = r.get("ts_il")
        if r.get("script") == "momentum_screener.py" and r.get("event") == "RUN_START":
            if scr_start is None or str(r.get("ts_il")) > str(scr_start):
                scr_start = r.get("ts_il")
    if not pm_end:
        return {"nudge": False, "reason": "no_pm_end"}
    if scr_start and str(scr_start) >= str(pm_end):
        return {
            "nudge": False,
            "reason": "screener_started",
            "pm_end": pm_end,
            "scr_start": scr_start,
        }
    try:
        pm_dt = datetime.fromisoformat(pm_end)
        if now - pm_dt >= timedelta(minutes=2) and not scr_start:
            return {"nudge": True, "reason": "NO_SCREENER_START_WITHIN_2M", "pm_end": pm_end}
    except Exception:
        pass
    return {
        "nudge": False,
        "reason": "within_2m_or_parse",
        "pm_end": pm_end,
        "scr_start": scr_start,
    }


def _first_ts(info: dict) -> str | None:
    ts = [a.get("ts_il") for a in (info.get("actions") or []) if a.get("ts_il")]
    ts += [t for t in (info.get("run_starts") or []) if t]
    return min(ts) if ts else None


def audit_row(status: dict, caller: str = "unknown") -> dict:
    """EOD_MISS_CHECK payload (QA Bot 2026-10-20): one row per run."""
    scr, pm = status.get("screener") or {}, status.get("position_manager") or {}
    if status.get("pm_miss") and status.get("screener_miss"):
        verdict = "PM_AND_SCREENER_MISSED"
    elif status.get("pm_miss"):
        verdict = "EOD_PM_MISSED"
    elif status.get("screener_miss"):
        verdict = "EOD_SCREENER_MISSED"
    else:
        verdict = "OK:" + str(scr.get("reason") or "no_miss")
    return {
        "ts": datetime.now(tz=IL).isoformat(),
        "event": "EOD_MISS_CHECK",
        "caller": caller or "unknown",
        "pm_ran": bool(pm.get("has_eod_pm_action")),
        "pm_first_ts": _first_ts(pm),
        "screener_ran": bool(scr.get("has_eod_screener_action")),
        "screener_first_ts": _first_ts(scr),
        "next_job": status.get("next_job"),
        "verdict": verdict,
        "rationale": f"eod_miss_check by {caller or 'unknown'}: {verdict}",
        **({"screener_gate": (status.get("screener_gate") or {}).get("decision"),
            "screener_gate_reason": (status.get("screener_gate") or {}).get("reason")}
           if status.get("screener_gate") else {}),
        **({"schedule_misaligned": True,
            "schedule_alerts": [{k: x.get(k) for k in ("code", "direction", "pm_run_start", "minutes_before_close")}
                                for x in (status.get("schedule") or {}).get("alerts", [])]}
           if (status.get("schedule") or {}).get("misaligned") else {}),
    }


def write_audit(status: dict, caller: str = "unknown", audit_dir: Path | None = None) -> Path:
    try:
        from momentum_qa.audit import append_row, build_record, new_run_id
    except ImportError:  # run as a plain script: python momentum_qa/eod_miss_check.py
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from momentum_qa.audit import append_row, build_record, new_run_id

    rec = build_record(new_run_id("eodmiss"), "momentum_qa/eod_miss_check.py", audit_row(status, caller))
    return append_row(rec, audit_dir or AUDIT)


# ---------------------------------------------------------------------------
# EOD chain ownership (2026-10-22 backup-wins-race incident; QA Bot reviews F1–F4 and N1–N4).
#
# OWNER LOCK  <AUDIT>/locks/eod-owner-YYYYMMDD.lock  — one chain (PM -> screener -> place) per night.
# SCREENER LOCK <AUDIT>/locks/eod-screener-YYYYMMDD.lock — one momentum_screener.py run per night,
#   taken by EVERY screener invocation (primary chain, backup chain, screener cron, watchdog). Separate
#   from the owner lock so a screener-only caller never blocks the PM risk pass.
# Both: created with O_CREAT|O_EXCL; every decide+write runs under fcntl.flock on the sibling .guard.
# Identity is the RUN (run_tag), not the routine name (N1): the first call returns run_tag; only a
#   call passing the same --run-tag refreshes/keeps the lock; any other run (incl. a duplicate wake of
#   the same routine) is refused while the lock is live.
# Live/stale: live while 0 <= now - refreshed_ts <= TTL (180s), or once the guarded script's RUN_START
#   appears at/after acquired_ts (owner lock: live all night; screener lock: while that run is not idle
#   > CHAIN_STALL_S). Stale locks may be stolen (recorded as stale_steal). A lock dated in the future
#   (> CLOCK_SKEW_S ahead) or unparsable is corrupt -> stale (N4).
# Exit codes: 0/2 = proceed (2 = a miss exists, legacy meaning), 3 = do NOT run, 4 = place-watch alert.
# ---------------------------------------------------------------------------
PRIMARY_CALLER = "eod-pm-2240"
BACKUP_CALLER = "eod-pm-2242-backup"
SCREENER_CALLER = "eod-screener-2245"
WATCHDOG_CALLER = "eod-watchdog-2250"
OWNER_TTL_S = 180          # F2: owner's PM RUN_START must appear within ~3 min of the last refresh
OWNER_TTL_MIN_S, OWNER_TTL_MAX_S = 30, 900  # L2 2026-10-23: --owner-ttl outside this range = BAD_ARGS (exit 3)
SCREENER_TTL_S = 180       # N2: screener RUN_START must appear within ~3 min of taking the screener lock
CHAIN_STALL_S = 300        # F3: chain/screener with no new activity for 5 min no longer blocks others
CLOCK_SKEW_S = 5           # N4: lock timestamps further than this in the future = corrupt
PLACE_GRACE_S = 600        # N3: screener RUN_END with BUYs and no place trace after 10 min = alert
RC_STOP = 3
RC_ALERT = 4

TAKEOVER_REASONS = {
    "PRIMARY_NO_RUN_START": "took over tonight's chain: no live owner lock and no position_manager RUN_START tonight",
}
DEFER_REASONS = {
    "BACKUP_OWNS": "primary deferred: another routine's run holds tonight's live owner lock",
    "DUPLICATE_WAKE": "primary deferred: another run of the same routine holds tonight's owner lock",
    "CHAIN_ALREADY_STARTED": "primary deferred: a position_manager RUN_START already exists tonight",
    "OWNER_LOCK_LOST": "primary deferred: its owner lock went stale and was taken by another run",
}
PROCEED_REASONS = {
    "OWNER_LOCK_ACQUIRED": "primary proceeds: acquired tonight's owner lock",
    "STALE_LOCK_STOLEN": "primary proceeds: took over a stale owner lock (no owner PM RUN_START within TTL)",
}
SCREENER_LOCK_REASONS = {
    "SCREENER_LOCK_ACQUIRED": "screener lock taken right before momentum_screener.py",
    "STALE_LOCK_STOLEN": "screener lock taken over: previous holder's screener never started or stalled",
}
PLACE_WATCH_CODES = {
    "OWNER_DIED_BEFORE_PLACE": "screener RUN_END with BUY rows but no place trace (place_audit/pack_skips/postfill/"
                               "place_lock) within the grace period",
    "PLACE_RUN_INCOMPLETE": "PLACE_RUN_START without PLACE_RUN_END within the grace period",
}
# event -> {reason -> description}; imported by feedback_daily for counters/lessons.
OWNERSHIP_CODES = {
    "BACKUP_TAKEOVER": TAKEOVER_REASONS,
    "PRIMARY_DEFERRED": DEFER_REASONS,
    "PRIMARY_PROCEEDS": PROCEED_REASONS,
    "SCREENER_LOCK": SCREENER_LOCK_REASONS,
    "EOD_PLACE_WATCH": PLACE_WATCH_CODES,
}
OWNERSHIP_EVENTS = tuple(OWNERSHIP_CODES)
OWNER_EVENTS = ("BACKUP_TAKEOVER", "PRIMARY_PROCEEDS")
# CLI trigger values (the reason actually written is decided under the lock).
DEFER_TRIGGERS = ("BACKUP_OWNS",)
_KINDS = {
    "owner": {"prefix": "eod-owner", "ttl": OWNER_TTL_S, "script": "position_manager.py"},
    "screener": {"prefix": "eod-screener", "ttl": SCREENER_TTL_S, "script": "momentum_screener.py"},
}


def ownership_code(row: dict) -> str | None:
    """'EVENT:REASON' for an ownership row whose reason is mapped; None otherwise."""
    ev, reason = row.get("event"), row.get("reason")
    if ev in OWNERSHIP_CODES and reason in OWNERSHIP_CODES[ev]:
        return f"{ev}:{reason}"
    return None


def _rows_day(day: str, event: str, caller: str | None = None) -> list[dict]:
    return [r for r in _day_rows(day) if r.get("event") == event and (caller is None or r.get("caller") == caller)]


def caller_last_seen(day: str, caller: str) -> str | None:
    """Latest evening-window audit ts_il of any row written with this caller tonight (or None)."""
    ts = [r.get("ts_il") for r in _eod_rows(day) if r.get("caller") == caller and r.get("ts_il")]
    return max(ts) if ts else None


def lock_dir() -> Path:
    return AUDIT / "locks"


def lock_path(day: str, kind: str = "owner") -> Path:
    return lock_dir() / f"{_KINDS[kind]['prefix']}-{day.replace('-', '')}.lock"


def read_lock(day: str, kind: str = "owner") -> dict | None:
    p = lock_path(day, kind)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"caller": None, "corrupt": True}
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"caller": None, "corrupt": True}


def _script_rows(day: str, script: str) -> list[dict]:
    return [r for r in _eod_rows(day) if r.get("script") == script and r.get("ts_il")]


def _run_starts(day: str, script: str) -> list[str]:
    return sorted(r["ts_il"] for r in _script_rows(day, script) if r.get("event") == "RUN_START")


def _pm_run_starts(day: str) -> list[str]:
    return _run_starts(day, "position_manager.py")


def _age_s(ts: str | None, now: datetime) -> float | None:
    dt = _parse_ts_il(ts or "")
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IL)
    return (now - dt).total_seconds()


def _lock_age_s(ts, now: datetime) -> float | None:
    """L1 2026-10-23: a lock timestamp must be an ISO string WITH a timezone; else None (= corrupt)."""
    if not isinstance(ts, str):
        return None
    dt = _parse_ts_il(ts)
    if dt is None or dt.tzinfo is None:
        return None
    return (now - dt).total_seconds()


def lock_state(day: str, now: datetime, lock: dict | None = None, ttl_s: int | None = None,
               kind: str = "owner", stall_s: int = CHAIN_STALL_S) -> dict:
    """Evaluate tonight's lock of the given kind (read-only)."""
    k = _KINDS[kind]
    ttl_s = k["ttl"] if ttl_s is None else ttl_s
    lock = read_lock(day, kind) if lock is None else lock
    starts = _run_starts(day, k["script"])
    base = {"kind": kind, "exists": bool(lock), "live": False, "holder": None, "holder_run_tag": None,
            "started": bool(starts), "owner_started": False, "owner_started_ts": None, "age_s": None,
            "corrupt": False, "future_dated": False, "lock": lock}
    if not lock:
        return {**base, "pm_started": bool(starts) if kind == "owner" else None, "owner_pm_started": False}
    acq_age = _lock_age_s(lock.get("acquired_ts"), now)
    ref = lock.get("refreshed_ts")
    age = _lock_age_s(lock.get("acquired_ts") if ref is None else ref, now)
    future = any(a is not None and a < -CLOCK_SKEW_S for a in (acq_age, age))
    corrupt = bool(lock.get("corrupt")) or acq_age is None or age is None or future \
        or not isinstance(lock.get("run_tag"), str) or not lock.get("run_tag") \
        or (lock.get("caller") is not None and not isinstance(lock.get("caller"), str))
    owner_started = []
    if not corrupt:
        acq = _parse_ts_il(lock["acquired_ts"])
        owner_started = [t for t in starts if (_parse_ts_il(t) or acq) >= acq - timedelta(seconds=5)]
    live = False
    if not corrupt:
        if owner_started:
            if kind == "owner":
                live = True  # owner's PM started -> owns the night
            else:
                acts = [r["ts_il"] for r in _script_rows(day, k["script"])
                        if (_parse_ts_il(r["ts_il"]) or now) >= _parse_ts_il(owner_started[0])]
                idle = _age_s(max(acts, key=lambda t: _parse_ts_il(t)), now) if acts else None
                live = idle is None or idle <= stall_s
        else:
            live = 0 - CLOCK_SKEW_S <= age <= ttl_s
    out = {**base, "live": live, "holder": lock.get("caller"), "holder_run_tag": lock.get("run_tag"),
           "owner_started": bool(owner_started), "owner_started_ts": owner_started[0] if owner_started else None,
           "age_s": None if age is None else round(age, 1), "corrupt": corrupt, "future_dated": future}
    if kind == "owner":
        out["pm_started"], out["owner_pm_started"] = bool(starts), bool(owner_started)
        out["owner_pm_first_ts"] = out["owner_started_ts"]
    return out


def chain_owner(day: str, pm: dict | None = None, now: datetime | None = None) -> dict:
    """Who owns tonight's EOD chain / screener stage (read-only)."""
    now = now or datetime.now(tz=IL)
    pm = pm or {}
    st = lock_state(day, now)
    sl = lock_state(day, now, kind="screener")
    pm_started = bool(pm.get("run_starts")) or bool(pm.get("has_eod_pm_action")) or bool(pm.get("actions")) \
        or st["pm_started"]
    return {
        "owned": pm_started or st["live"],
        "pm_started": pm_started,
        "lock_exists": st["exists"],
        "lock_live": st["live"],
        "lock_holder": st["holder"],
        "lock_run_tag": st["holder_run_tag"],
        "lock_age_s": st["age_s"],
        "lock_corrupt": st["corrupt"],
        "owner_pm_started": st["owner_pm_started"],
        "lock_path": str(lock_path(day)),
        "screener_lock": {"exists": sl["exists"], "live": sl["live"], "holder": sl["holder"],
                          "run_tag": sl["holder_run_tag"], "age_s": sl["age_s"], "corrupt": sl["corrupt"],
                          "path": str(lock_path(day, "screener"))},
    }


class _Guard:
    """Cross-process critical section: fcntl.flock on locks/<prefix>-YYYYMMDD.guard."""

    def __init__(self, day: str, kind: str = "owner"):
        self.path = lock_dir() / f"{_KINDS[kind]['prefix']}-{day.replace('-', '')}.guard"

    def __enter__(self):
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+")
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl
        try:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        finally:
            self.fh.close()


def _run_tag(caller: str, now: datetime) -> str:
    import uuid
    return f"{caller}-{now.strftime('%H%M%S')}-p{os.getpid()}-{uuid.uuid4().hex[:6]}"


def _lock_body(caller: str, day: str, now: datetime, ttl_s: int, stolen_from: dict | None = None,
               run_tag: str | None = None, kind: str = "owner") -> dict:
    return {"kind": kind, "caller": caller, "date": day, "acquired_ts": now.isoformat(),
            "refreshed_ts": now.isoformat(), "run_tag": run_tag or _run_tag(caller, now), "ttl_s": ttl_s,
            "stolen_from": stolen_from}


def _create_lock_excl(day: str, body: dict, kind: str = "owner") -> bool:
    """O_CREAT|O_EXCL create; False if the file already exists."""
    p = lock_path(day, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False))
    return True


def _replace_lock(day: str, body: dict, kind: str = "owner") -> None:
    p = lock_path(day, kind)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _stale_info(st: dict) -> dict:
    lk = st.get("lock") or {}
    return {"from_caller": lk.get("caller"), "from_run_tag": lk.get("run_tag"), "acquired_ts": lk.get("acquired_ts"),
            "refreshed_ts": lk.get("refreshed_ts"), "age_s": st.get("age_s"), "corrupt": bool(st.get("corrupt")),
            "future_dated": bool(st.get("future_dated"))}


def _is_mine(st: dict, caller: str, run_tag: str | None) -> bool:
    lk = st.get("lock") or {}
    return bool(run_tag) and st["exists"] and not st["corrupt"] and lk.get("run_tag") == run_tag \
        and lk.get("caller") == caller


def claim_owner(caller: str, day: str, now: datetime, ttl_s: int = OWNER_TTL_S, run_tag: str | None = None) -> dict:
    """Atomic acquire/refresh/steal decision for one RUN. Must be called under _Guard(day).

    result: ACQUIRED | REFRESHED | STOLE_STALE           (this run owns the chain)
            HELD_BY_OTHER | CHAIN_ALREADY_STARTED          (this run must not run)
            LOCK_LOST                                      (tagged re-check, lock no longer this run's)
    Only the run whose --run-tag matches the lock refreshes it (N1); after its own PM RUN_START even
    that run gets CHAIN_ALREADY_STARTED (a re-run after PM never starts a second chain).
    M2 2026-10-23: a call WITH --run-tag is a verify-only re-check right before PM: it never acquires or
    steals. If the lock is gone, stolen (stale takeover victim) or anyone else's, it gets LOCK_LOST -> exit 3.
    """
    st = lock_state(day, now, ttl_s=ttl_s)
    if _is_mine(st, caller, run_tag):
        if st["owner_pm_started"]:
            return {"result": "CHAIN_ALREADY_STARTED", "owner": False, "mine": True, "state": st}
        lk = dict(st["lock"])
        lk["refreshed_ts"] = now.isoformat()
        _replace_lock(day, lk)
        return {"result": "REFRESHED", "owner": True, "mine": True, "lock": lk, "state": st}
    if st["pm_started"]:
        return {"result": "HELD_BY_OTHER" if st["owner_pm_started"] else "CHAIN_ALREADY_STARTED",
                "owner": False, "state": st}
    if run_tag:  # M2: verify-only re-check that is not (any longer) the holder
        return {"result": "LOCK_LOST", "owner": False, "state": st}
    if st["exists"] and st["live"]:
        return {"result": "HELD_BY_OTHER", "owner": False, "state": st}
    if st["exists"]:  # stale / corrupt / future-dated -> steal, recorded
        body = _lock_body(caller, day, now, ttl_s, stolen_from=_stale_info(st), run_tag=run_tag)
        _replace_lock(day, body)
        return {"result": "STOLE_STALE", "owner": True, "lock": body, "state": st, "stale_steal": body["stolen_from"]}
    body = _lock_body(caller, day, now, ttl_s, run_tag=run_tag)
    if not _create_lock_excl(day, body):  # should not happen under the guard; fail closed
        return {"result": "HELD_BY_OTHER", "owner": False, "state": lock_state(day, now, ttl_s=ttl_s)}
    return {"result": "ACQUIRED", "owner": True, "lock": body, "state": st}


def _write_payload(payload: dict, prefix: str, now: datetime, audit_dir: Path | None = None) -> Path:
    """Append one row to <AUDIT>/<date of now>.jsonl with ts_il = now (deterministic in tests)."""
    try:
        from momentum_qa.audit import build_record, new_run_id
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from momentum_qa.audit import build_record, new_run_id
    from datetime import timezone
    rec = build_record(new_run_id(prefix), "momentum_qa/eod_miss_check.py", payload)
    rec["ts_il"] = now.isoformat()
    rec["ts_utc"] = now.astimezone(timezone.utc).isoformat()
    d = Path(audit_dir or AUDIT)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{now.strftime('%Y-%m-%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return path


def _lock_summary(c: dict, kind: str = "owner") -> dict:
    lk = c.get("lock") or (c.get("state") or {}).get("lock") or {}
    return {"holder": lk.get("caller"), "run_tag": lk.get("run_tag"), "acquired_ts": lk.get("acquired_ts"),
            "refreshed_ts": lk.get("refreshed_ts"),
            "path": str(lock_path(lk["date"], kind)) if lk.get("date") else None}


def backup_takeover(status: dict, caller: str, reason: str, primary_caller: str = PRIMARY_CALLER,
                    now: datetime | None = None, write: bool = True, ttl_s: int = OWNER_TTL_S,
                    run_tag: str | None = None) -> dict:
    """Backup: atomically take tonight's owner lock for THIS run and record BACKUP_TAKEOVER.

    TAKEOVER_RECORDED (new owner) / ALREADY_RECORDED (same --run-tag; refresh) -> proceed.
    TAKEOVER_REFUSED_LOCK_HELD (any other run, incl. a duplicate backup) /
    TAKEOVER_LOCK_LOST (M2: --run-tag re-check, but the lock was stolen/lost: do NOT start PM) /
    TAKEOVER_REFUSED_PM_ALREADY_STARTED -> exit 3, no row.
    """
    now = now or datetime.now(tz=IL)
    day = status.get("day") or now.strftime("%Y-%m-%d")
    pm = status.get("position_manager") or {}
    if reason not in TAKEOVER_REASONS:
        return {"ok": False, "result": "UNMAPPED_REASON", "reason": reason, "written": False, "proceed": False}
    with _Guard(day):
        c = claim_owner(caller, day, now, ttl_s, run_tag)
        st = c["state"]
        if not c["owner"]:
            res = "TAKEOVER_REFUSED_PM_ALREADY_STARTED" if st["pm_started"] else \
                ("TAKEOVER_LOCK_LOST" if c["result"] == "LOCK_LOST" else "TAKEOVER_REFUSED_LOCK_HELD")
            return {"ok": False, "result": res, "proceed": False, "written": False, "run_tag": None,
                    "lock_holder": st["holder"], "lock_holder_run_tag": st["holder_run_tag"],
                    "lock_age_s": st["age_s"], "pm_first_ts": _first_ts(pm) or (_pm_run_starts(day) or [None])[0]}
        tag = c["lock"]["run_tag"]
        prior = [r for r in _rows_day(day, "BACKUP_TAKEOVER", caller) if r.get("lock_run_tag") == tag]
        if prior and c["result"] == "REFRESHED":
            return {"ok": True, "result": "ALREADY_RECORDED", "row": prior[-1], "written": False, "proceed": True,
                    "run_tag": tag, "lock": _lock_summary(c)}
        row = {
            "ts": now.isoformat(),
            "date": day,
            "event": "BACKUP_TAKEOVER",
            "caller": caller,
            "reason": reason,
            "run_tag": tag,
            "primary_caller": primary_caller,
            "primary_last_seen": caller_last_seen(day, primary_caller),
            "pm_first_ts": _first_ts(pm),
            "screener_first_ts": _first_ts(status.get("screener") or {}),
            "lock_result": c["result"],
            "lock_run_tag": tag,
            "stale_steal": c.get("stale_steal"),
            "rationale": f"{caller}: {TAKEOVER_REASONS[reason]}"
                         + (f" (stale lock of {c['stale_steal']['from_caller']} taken)" if c.get("stale_steal") else ""),
        }
        if write:
            _write_payload(row, "takeover", now)
        return {"ok": True, "result": "TAKEOVER_RECORDED", "row": row, "written": write, "proceed": True,
                "run_tag": tag, "lock": _lock_summary(c)}


def primary_claim(status: dict, caller: str, backup_caller: str = BACKUP_CALLER,
                  now: datetime | None = None, write: bool = True, ttl_s: int = OWNER_TTL_S,
                  run_tag: str | None = None) -> dict:
    """Primary: atomic acquire+decide for THIS run. Exactly one ownership row per wake.

    First call (no --run-tag): PRIMARY_PROCEEDS (OWNER_LOCK_ACQUIRED | STALE_LOCK_STOLEN) + run_tag -> 0/2,
      or PRIMARY_DEFERRED (BACKUP_OWNS | DUPLICATE_WAKE | CHAIN_ALREADY_STARTED) -> 3.
    Re-run before PM with --run-tag <tag>: ALREADY_RECORDED (refresh, no row) -> 0/2, or
      PRIMARY_DEFERRED OWNER_LOCK_LOST / CHAIN_ALREADY_STARTED -> 3.
    """
    now = now or datetime.now(tz=IL)
    day = status.get("day") or now.strftime("%Y-%m-%d")
    pm = status.get("position_manager") or {}
    with _Guard(day):
        c = claim_owner(caller, day, now, ttl_s, run_tag)
        st = c["state"]
        mine_rows = [r for r in _rows_day(day, "PRIMARY_PROCEEDS", caller)
                     if run_tag and r.get("lock_run_tag") == run_tag]
        if c["owner"]:
            tag = c["lock"]["run_tag"]
            if c["result"] == "REFRESHED" and mine_rows:
                return {"ok": True, "result": "ALREADY_RECORDED", "defer": False, "proceed": True, "written": False,
                        "run_tag": tag, "row": mine_rows[-1], "lock": _lock_summary(c)}
            event = "PRIMARY_PROCEEDS"
            reason = "STALE_LOCK_STOLEN" if c["result"] == "STOLE_STALE" else "OWNER_LOCK_ACQUIRED"
        else:
            tag = None
            event = "PRIMARY_DEFERRED"
            if c.get("mine"):
                reason = "CHAIN_ALREADY_STARTED"  # this run's own PM already started; never a 2nd chain
            elif mine_rows:
                reason = "OWNER_LOCK_LOST"
            elif st.get("holder") == caller:
                reason = "DUPLICATE_WAKE"
            elif c["result"] == "CHAIN_ALREADY_STARTED":
                reason = "CHAIN_ALREADY_STARTED"
            elif c["result"] == "LOCK_LOST" and not (st.get("exists") and st.get("live")):
                reason = "OWNER_LOCK_LOST"  # M2: tagged re-check, lock gone / not this run's
            else:
                reason = "BACKUP_OWNS"
            if run_tag:  # same run re-asking: one row per run/reason
                prior = [r for r in _rows_day(day, event, caller)
                         if r.get("requested_run_tag") == run_tag and r.get("reason") == reason]
                if prior:
                    return {"ok": True, "result": "ALREADY_RECORDED", "defer": True, "proceed": False,
                            "written": False, "run_tag": None, "row": prior[-1], "lock": _lock_summary(c)}
        lk = c.get("lock") or st.get("lock") or {}
        takeovers = _rows_day(day, "BACKUP_TAKEOVER")
        row = {
            "ts": now.isoformat(),
            "date": day,
            "event": event,
            "caller": caller,
            "reason": reason,
            "run_tag": tag,
            "requested_run_tag": run_tag,
            "lock_result": c["result"],
            "lock_holder": lk.get("caller"),
            "lock_run_tag": lk.get("run_tag"),
            "owner_caller": None if c["owner"] else (st.get("holder") or (takeovers[-1].get("caller") if takeovers else None)),
            "owner_takeover_ts": takeovers[-1].get("ts_il") if takeovers else None,
            "backup_last_seen": caller_last_seen(day, backup_caller),
            "pm_first_ts": _first_ts(pm) or (_pm_run_starts(day) or [None])[0],
            "stale_steal": c.get("stale_steal"),
            "rationale": f"{caller}: {OWNERSHIP_CODES[event][reason]}",
        }
        if write:
            _write_payload(row, "primaryown", now)
        res = "PROCEEDS_RECORDED" if c["owner"] else "DEFERRED_RECORDED"
        return {"ok": True, "result": res, "defer": not c["owner"], "proceed": c["owner"], "row": row,
                "written": write, "run_tag": tag, "lock": _lock_summary(c)}


# Backward-compatible name (pre-F1 callers / tests).
def primary_deferred(status: dict, caller: str, reason: str = "BACKUP_OWNS", backup_caller: str = BACKUP_CALLER,
                     now: datetime | None = None, write: bool = True) -> dict:
    return primary_claim(status, caller, backup_caller, now, write)


def screener_lock(status: dict, caller: str, now: datetime | None = None, write: bool = True,
                  ttl_s: int = SCREENER_TTL_S, run_tag: str | None = None, stall_s: int = CHAIN_STALL_S) -> dict:
    """N2: per-night screener-stage lock, taken right before momentum_screener.py by every caller.

    SCREENER_LOCK_ACQUIRED / STALE_LOCK_STOLEN (row) / ALREADY_HELD (same --run-tag, refresh) -> 0/2 run it.
    SCREENER_ALREADY_RAN | SCREENER_LOCK_HELD | SCREENER_IN_PROGRESS -> 3: skip screener AND place.
    """
    now = now or datetime.now(tz=IL)
    day = status.get("day") or now.strftime("%Y-%m-%d")
    scr = status.get("screener") or {}
    with _Guard(day, "screener"):
        if scr.get("has_eod_screener_action"):
            return {"ok": True, "result": "SCREENER_ALREADY_RAN", "proceed": False, "written": False, "run_tag": None}
        st = lock_state(day, now, ttl_s=ttl_s, kind="screener", stall_s=stall_s)
        lk = st.get("lock") or {}
        refused = {"ok": True, "proceed": False, "written": False, "run_tag": None, "lock_holder": st["holder"],
                   "lock_holder_run_tag": st["holder_run_tag"], "lock_age_s": st["age_s"]}
        if st["exists"] and not st["corrupt"] and run_tag and lk.get("run_tag") == run_tag:
            if st["owner_started"]:
                return {**refused, "result": "SCREENER_ALREADY_STARTED"}
            lk = dict(lk)
            lk["refreshed_ts"] = now.isoformat()
            _replace_lock(day, lk, "screener")
            return {"ok": True, "result": "ALREADY_HELD", "proceed": True, "written": False, "run_tag": run_tag,
                    "lock": _lock_summary({"lock": lk}, "screener")}
        if st["exists"] and st["live"]:
            return {**refused, "result": "SCREENER_LOCK_HELD"}
        # lock-less screener run in progress (e.g. legacy caller): block while it is not idle
        recent = [r["ts_il"] for r in _script_rows(day, "momentum_screener.py")
                  if (a := _age_s(r["ts_il"], now)) is not None and a <= stall_s]
        if recent and not (st["exists"] and st["owner_started"]):
            return {**refused, "result": "SCREENER_IN_PROGRESS"}
        tag = run_tag or _run_tag(caller, now)
        if st["exists"]:
            body = _lock_body(caller, day, now, ttl_s, stolen_from=_stale_info(st), run_tag=tag, kind="screener")
            _replace_lock(day, body, "screener")
            reason, steal = "STALE_LOCK_STOLEN", body["stolen_from"]
        else:
            body = _lock_body(caller, day, now, ttl_s, run_tag=tag, kind="screener")
            if not _create_lock_excl(day, body, "screener"):
                return {**refused, "result": "SCREENER_LOCK_HELD"}
            reason, steal = "SCREENER_LOCK_ACQUIRED", None
        row = {"ts": now.isoformat(), "date": day, "event": "SCREENER_LOCK", "caller": caller, "reason": reason,
               "run_tag": tag, "owner_run_tag": run_tag, "stale_steal": steal,
               "rationale": f"{caller}: {SCREENER_LOCK_REASONS[reason]}"}
        if write:
            _write_payload(row, "scrlock", now)
        return {"ok": True, "result": reason, "proceed": True, "written": write, "run_tag": tag, "row": row,
                "lock": _lock_summary({"lock": body}, "screener")}


def place_watch(rows: list[dict], now: datetime, grace_s: int = PLACE_GRACE_S,
                place_lock_dir: Path | None = None) -> dict:
    """N3: screener RUN_END with BUY rows but no place trace within grace_s -> OWNER_DIED_BEFORE_PLACE;
    PLACE_RUN_START without PLACE_RUN_END within grace_s -> PLACE_RUN_INCOMPLETE. Read-only."""
    try:
        from momentum_qa.audit import row_screener_run_id
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from momentum_qa.audit import row_screener_run_id
    ev_rows = [r for r in rows if MC.in_eod_window(r.get("ts_il"))]  # NYSE close-2h.. (was T21-T23)
    ends = [r for r in ev_rows if r.get("script") == "momentum_screener.py" and r.get("event") == "RUN_END"]
    lock_mtimes = []
    if place_lock_dir and Path(place_lock_dir).exists():
        lock_mtimes = [datetime.fromtimestamp(p.stat().st_mtime, tz=IL) for p in Path(place_lock_dir).glob("*.lock")]
    runs, alerts = [], []
    for e in ends:
        rid = e.get("run_id")
        end_dt = _parse_ts_il(e.get("ts_il") or "")
        buys = sorted({r.get("symbol") for r in ev_rows if r.get("run_id") == rid and r.get("event") == "ACTION"
                       and r.get("action") == "BUY" and r.get("script") == "momentum_screener.py"})
        if not buys or end_dt is None:
            runs.append({"screener_run_id": rid, "buys": buys, "status": "NO_BUYS"})
            continue
        place = [r for r in ev_rows if r.get("event") in ("PLACE_RUN_START", "FILL", "SKIP", "PLACE_RUN_END", "FILL_AMEND")
                 and row_screener_run_id(r) == rid]
        later = [r for r in ev_rows if r.get("event") in ("POSTFILL_CHECK", "PLACE_LOCK")
                 and (_parse_ts_il(r.get("ts_il") or "") or end_dt) > end_dt]
        locks_after = [m for m in lock_mtimes if m > end_dt]
        started = any(r.get("event") == "PLACE_RUN_START" for r in place)
        ended = any(r.get("event") == "PLACE_RUN_END" for r in place)
        age = (now - end_dt).total_seconds()
        info = {"screener_run_id": rid, "screener_end_ts": e.get("ts_il"), "buys": buys, "age_s": round(age, 1),
                "place_rows": len(place), "postfill_rows": len(later), "place_locks_after": len(locks_after),
                "place_run_start": started, "place_run_end": ended}
        code = None
        if not place and not later and not locks_after:
            code = "OWNER_DIED_BEFORE_PLACE" if age > grace_s else None
            info["status"] = "ALERT" if code else "WAITING"
        elif started and not ended and age > grace_s:
            code, info["status"] = "PLACE_RUN_INCOMPLETE", "ALERT"
        else:
            info["status"] = "OK"
        runs.append(info)
        if code:
            alerts.append({"code": code, **info})
    return {"alert": bool(alerts), "alerts": alerts, "runs": runs, "grace_s": grace_s, "now_il": now.isoformat()}


def place_watch_cli(caller: str, now: datetime, grace_s: int, write: bool = True) -> dict:
    day = now.strftime("%Y-%m-%d")
    res = place_watch(_day_rows(day), now, grace_s, AUDIT / "place_locks")
    written = []
    for a in res["alerts"]:
        prior = [r for r in _rows_day(day, "EOD_PLACE_WATCH")
                 if r.get("reason") == a["code"] and r.get("screener_run_id") == a["screener_run_id"]]
        if prior or not write:
            continue
        row = {"ts": now.isoformat(), "date": day, "event": "EOD_PLACE_WATCH", "caller": caller, "reason": a["code"],
               "screener_run_id": a["screener_run_id"], "buys": a["buys"], "screener_end_ts": a["screener_end_ts"],
               "age_s": a["age_s"], "rationale": f"{caller}: {PLACE_WATCH_CODES[a['code']]}"}
        _write_payload(row, "placewatch", now)
        written.append(a["code"])
    res["rows_written"] = written
    return res


def screener_gate(status: dict, now: datetime | None = None, ttl_s: int = OWNER_TTL_S,
                  stall_s: int = CHAIN_STALL_S) -> dict:
    """Scheduled screener cron gate (PM+5m: 21:45 IL fixed schedule; F3, read-only).

    STOP_ALREADY_RAN     screener EOD ACTION exists tonight            -> exit 3
    STOP_OWNER_ACTIVE    live owner lock / PM started, chain not stalled, or live screener lock -> exit 3
    PROCEED              no live owner, or owner chain stalled > stall_s -> exit 0/2
                         (then still take --screener-lock right before momentum_screener.py)
    """
    now = now or datetime.now(tz=IL)
    day = status.get("day") or now.strftime("%Y-%m-%d")
    scr = status.get("screener") or {}
    if scr.get("has_eod_screener_action"):
        return {"decision": "STOP_ALREADY_RAN", "proceed": False, "reason": "SCREENER_ALREADY_ACTED"}
    st = lock_state(day, now, ttl_s=ttl_s)
    sl = lock_state(day, now, kind="screener", stall_s=stall_s)
    chain = [r for r in _eod_rows(day) if r.get("script") in ("position_manager.py", "momentum_screener.py")]
    acts = [r.get("ts_il") for r in chain if r.get("ts_il")]
    if st["exists"] and not st["corrupt"]:
        acts.append((st["lock"] or {}).get("refreshed_ts"))
    acts = [a for a in acts if a and _parse_ts_il(a)]
    last = max(acts, key=lambda t: _parse_ts_il(t)) if acts else None
    idle = _age_s(last, now)
    base = {"lock_holder": st["holder"], "lock_live": st["live"], "pm_started": st["pm_started"],
            "screener_lock_live": sl["live"], "last_chain_activity": last,
            "idle_s": None if idle is None else round(idle, 1)}
    if sl["live"]:
        return {"decision": "STOP_OWNER_ACTIVE", "proceed": False, "reason": "SCREENER_LOCK_HELD", **base}
    if not st["live"] and not st["pm_started"]:
        return {"decision": "PROCEED", "proceed": True, "reason": "NO_LIVE_OWNER", **base}
    if idle is not None and idle > stall_s:
        return {"decision": "PROCEED", "proceed": True, "reason": "OWNER_CHAIN_STALLED", **base}
    return {"decision": "STOP_OWNER_ACTIVE", "proceed": False, "reason": "OWNER_CHAIN_IN_PROGRESS", **base}


RC_BAD_ARGS = RC_STOP  # argument/parse errors fail closed (argparse's default 2 would read as "miss, proceed")


def _arg_parser_cls():
    import argparse

    class _FailClosedParser(argparse.ArgumentParser):
        """argparse exits 2 on bad/missing args; 2 means "miss, proceed" here, so exit 3 (do NOT run) instead."""

        def error(self, message):  # noqa: D401 - argparse hook
            self.print_usage(sys.stderr)
            print(f"{self.prog}: error: {message}", file=sys.stderr)
            print(json.dumps({"result": "BAD_ARGS", "proceed": False, "error": message, "rc": RC_BAD_ARGS}))
            raise SystemExit(RC_BAD_ARGS)

    return _FailClosedParser


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    """Fail-closed wrapper (L1 2026-10-23): any uncaught exception -> {"result": "INTERNAL_ERROR", "proceed":
    false} on stdout and exit 3 (4 under --place-watch). Bad args stay BAD_ARGS exit 3; --help exits 0."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _main(args, now)
    except Exception as e:  # noqa: BLE001 - fail closed on anything unexpected
        watch = any(x == "--place-watch" for x in args)
        rc = RC_ALERT if watch else RC_STOP
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"result": "INTERNAL_ERROR", "proceed": False, "error": f"{type(e).__name__}: {e}",
                          "rc": rc}))
        return rc


def _main(argv: list[str], now: datetime | None = None) -> int:
    """Exit codes: 0 no miss, 2 miss (unchanged). Ownership/lock modes: 3 = do NOT run; 0/2 = proceed.
    --place-watch: 4 = alert (OWNER_DIED_BEFORE_PLACE / PLACE_RUN_INCOMPLETE).
    Bad/missing/unknown arguments or bad values: 3 (fail closed; JSON {"result": "BAD_ARGS"} on stdout)."""
    ap = _arg_parser_cls()(prog="momentum_qa.eod_miss_check", description="EOD screener/PM miss check")
    ap.add_argument("--caller", required=True,
                    help="routine name logged in audit rows (eod-pm-2240 | eod-pm-2242-backup | eod-screener-2245 | "
                         "eod-watchdog-2250 | ...)")
    ap.add_argument("--no-audit", action="store_true",
                    help="do not append EOD_MISS_CHECK audit row (ownership rows still follow their own flags)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--takeover-reason", choices=sorted(TAKEOVER_REASONS),
                   help="backup: atomically take the owner lock for this run + BACKUP_TAKEOVER row; exit 3 if refused")
    g.add_argument("--defer-reason", choices=DEFER_TRIGGERS,
                   help="primary: atomic acquire+decide; one PRIMARY_PROCEEDS or PRIMARY_DEFERRED row; exit 3 = defer")
    g.add_argument("--screener-gate", action="store_true",
                   help="screener cron: exit 3 if screener already acted or tonight's chain has a live owner")
    g.add_argument("--screener-lock", action="store_true",
                   help="every screener run, right before momentum_screener.py: take the per-night screener lock; "
                        "exit 3 = skip screener and place")
    g.add_argument("--place-watch", action="store_true",
                   help="watchdog: exit 4 if a screener pack with BUYs has no place trace (OWNER_DIED_BEFORE_PLACE)")
    ap.add_argument("--run-tag", default=None,
                    help="run_tag returned by this run's first ownership call (re-run before PM / screener lock)")
    ap.add_argument("--primary-caller", default=PRIMARY_CALLER, help="caller name of the primary (primary_last_seen)")
    ap.add_argument("--backup-caller", default=BACKUP_CALLER, help="caller name of the backup (backup_last_seen)")
    ap.add_argument("--owner-ttl", type=int, default=OWNER_TTL_S, help="owner/screener lock TTL seconds (default 180)")
    ap.add_argument("--place-grace-min", type=float, default=PLACE_GRACE_S / 60,
                    help="--place-watch grace minutes after screener RUN_END (default 10)")
    a = ap.parse_args(argv)
    if not a.caller.strip() or a.caller.strip().lower() == "unknown":
        ap.error("--caller must name the routine (not empty / 'unknown')")
    if a.run_tag is not None and not a.run_tag.strip():
        ap.error("--run-tag must not be empty")
    if not (OWNER_TTL_MIN_S <= a.owner_ttl <= OWNER_TTL_MAX_S):
        ap.error(f"--owner-ttl must be {OWNER_TTL_MIN_S}..{OWNER_TTL_MAX_S} seconds")
    if not (0 <= a.place_grace_min <= 24 * 60):  # also rejects nan / inf
        ap.error("--place-grace-min must be between 0 and 1440")
    now = now or datetime.now(tz=IL)
    status = night_status(now)
    rc = 2 if status["any_miss"] else 0
    if a.screener_gate:
        status["screener_gate"] = screener_gate(status, now, a.owner_ttl)
        if not status["screener_gate"]["proceed"]:
            rc = RC_STOP
    if not a.no_audit:
        try:
            write_audit(status, a.caller)
        except Exception as e:  # never break the check on audit I/O
            print(f"audit write failed: {e}", file=sys.stderr)
    try:
        if a.takeover_reason:
            status["ownership"] = backup_takeover(status, a.caller, a.takeover_reason, a.primary_caller, now,
                                                  ttl_s=a.owner_ttl, run_tag=a.run_tag)
        elif a.defer_reason:
            status["ownership"] = primary_claim(status, a.caller, a.backup_caller, now, ttl_s=a.owner_ttl,
                                                run_tag=a.run_tag)
        elif a.screener_lock:
            status["screener_lock"] = screener_lock(status, a.caller, now, ttl_s=a.owner_ttl, run_tag=a.run_tag)
        elif a.place_watch:
            status["place_watch"] = place_watch_cli(a.caller, now, int(a.place_grace_min * 60))
            if status["place_watch"]["alert"]:
                rc = RC_ALERT
        for key in ("ownership", "screener_lock"):
            if key in status and not status[key].get("proceed"):
                rc = RC_STOP
    except Exception as e:  # fail closed: no ownership -> do not run
        print(f"ownership step failed: {e}", file=sys.stderr)
        key = "place_watch" if a.place_watch else ("screener_lock" if a.screener_lock else "ownership")
        status[key] = {"ok": False, "result": "WRITE_FAILED", "error": str(e), "written": False,
                       "proceed": False, "defer": True}
        rc = RC_ALERT if a.place_watch else RC_STOP
    if a.takeover_reason or a.defer_reason or a.screener_gate or a.screener_lock:
        status["chain_owner"] = chain_owner(status["day"], status.get("position_manager"), now)
    if "ownership" in status:
        status["run_tag"] = status["ownership"].get("run_tag")
    elif "screener_lock" in status:
        status["run_tag"] = status["screener_lock"].get("run_tag")
    print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())

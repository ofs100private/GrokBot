#!/usr/bin/env python3
"""Detect EOD screener / position_manager misses and optionally require catch-up.

SCREENER MISS = NYSE session day, after 22:46 IL, and no screener ACTION/HALT/BUY/SKIP
in audit with ts_il hour>=22 after 22:40 (excluding morning smoke).

PM MISS = NYSE session day, after 22:46 IL, and no position_manager RUN_START/ACTION/RUN_END
in the EOD window (T22/T23 IL).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
AUDIT = Path("/workspace/momentum_audit")


def _eod_rows(day: str) -> list[dict]:
    path = AUDIT / f"{day}.jsonl"
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = r.get("ts_il") or ""
        if "T22:" not in ts and "T23:" not in ts:
            continue
        rows.append(r)
    return rows


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


def is_miss(now: datetime | None = None) -> tuple[bool, dict]:
    """Backward-compatible: True only for screener miss (exit code / old callers). """
    now = now or datetime.now(tz=IL)
    status = screener_ran_tonight(now)
    if now.weekday() >= 5:
        return False, {**status, "reason": "weekend"}
    mins = now.hour * 60 + now.minute
    if mins < 22 * 60 + 46:
        return False, {**status, "reason": "before_watch_window"}
    if status["has_eod_screener_action"]:
        return False, {**status, "reason": "screener_already_ran"}
    return True, {**status, "reason": "EOD_SCREENER_MISSED", "deviation_code": "EOD_SCREENER_MISSED"}


def is_pm_miss(now: datetime | None = None) -> tuple[bool, dict]:
    now = now or datetime.now(tz=IL)
    status = pm_ran_tonight(now)
    if now.weekday() >= 5:
        return False, {**status, "reason": "weekend"}
    mins = now.hour * 60 + now.minute
    if mins < 22 * 60 + 46:
        return False, {**status, "reason": "before_watch_window"}
    if status["has_eod_pm_action"]:
        return False, {**status, "reason": "pm_already_ran"}
    return True, {**status, "reason": "EOD_PM_MISSED", "deviation_code": "EOD_PM_MISSED"}


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
        ts = r.get("ts_il") or ""
        if "T22:" not in ts and "T23:" not in ts:
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


if __name__ == "__main__":
    status = night_status()
    # Keep exit 2 if either miss (watchdog should catch up)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    sys.exit(2 if status["any_miss"] else 0)

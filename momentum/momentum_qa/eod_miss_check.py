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
    """Evening window rows: T21–T23 IL (manual early EOD + scheduled + catch-up).

    T21 included so early/manual EOD (e.g. ~21:52) counts toward operational
    'screener already ran' and toward the ≤22:50 miss gate (QA Bot 2026-09-23).
    """
    rows: list[dict] = []
    for r in _day_rows(day):
        ts = r.get("ts_il") or ""
        if "T21:" in ts or "T22:" in ts or "T23:" in ts:
            rows.append(r)
    return rows


def screener_actions_by_deadline(day: str, hour: int = 22, minute: int = 50) -> list[dict]:
    """Screener ACTION BUY/HALT/SKIP/ERROR with ts_il ≤ deadline that calendar day.

    Standing gate (2026-09-11 / QA 2026-09-23): EOD_SCREENER_MISSED iff none by 22:50 IL.
    Early/manual EOD counts.
    """
    deadline_min = hour * 60 + minute
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
    }


def write_audit(status: dict, caller: str = "unknown", audit_dir: Path | None = None) -> Path:
    try:
        from momentum_qa.audit import append_row, build_record, new_run_id
    except ImportError:  # run as a plain script: python momentum_qa/eod_miss_check.py
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from momentum_qa.audit import append_row, build_record, new_run_id

    rec = build_record(new_run_id("eodmiss"), "momentum_qa/eod_miss_check.py", audit_row(status, caller))
    return append_row(rec, audit_dir or AUDIT)


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="momentum_qa.eod_miss_check", description="EOD screener/PM miss check")
    ap.add_argument("--caller", default="unknown", help="who ran this check (logged in audit row)")
    ap.add_argument("--no-audit", action="store_true", help="do not append EOD_MISS_CHECK audit row")
    a = ap.parse_args(argv)
    status = night_status(now)
    if not a.no_audit:
        try:
            write_audit(status, a.caller)
        except Exception as e:  # never break the check on audit I/O
            print(f"audit write failed: {e}", file=sys.stderr)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    # Keep exit 2 if either miss (watchdog should catch up)
    return 2 if status["any_miss"] else 0


if __name__ == "__main__":
    sys.exit(main())

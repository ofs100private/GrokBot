"""Daily NEW-trade counter (Ofer 2026-10-16 01:27 IDT): max 4 new opens per IDT calendar day.

QA fix (2026-10-16):
  * atomic: every read-modify-write runs under an exclusive fcntl.flock on <counter>.lock and
    writes via a unique mkstemp tmp file + os.replace (atomic rename).
  * check+reserve is ONE locked step (reserve()); execute_pass reserves a slot at GO time, the
    placer then mark()s it with the positionId on success or release()s it on failure. Reserved
    (unmarked, unreleased) slots count toward the cap and never expire (fail closed).
  * path pinned: production always uses /workspace/classic_rsi/state/daily_new_trades.json.
    CLASSIC_TRADE_COUNTER is honoured ONLY in test mode (CLASSIC_EXEC_TEST_ROOT set); if it is set
    in production every status/reserve fails closed (COUNTER_ENV_OVERRIDE_IN_PRODUCTION).
  * count = unmarked reservations + |placed positionIds ∪ positionIds opened today in the open book
    and the validated trading history (incl. opened-and-closed same day)| — a union, not max().
  * release_stale(): unmarked reservations older than 30 min are released by pre_buy_refresh, only
    after it has re-read trading history (a placed-but-unmarked fill still counts via its positionId).
SL edits and protective/risk exits do NOT count.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional
from zoneinfo import ZoneInfo

from .paths import TEST_ENV

IDT = ZoneInfo("Asia/Jerusalem")
MAX_NEW_TRADES_PER_DAY = 4
PROD_COUNTER_PATH = Path("/workspace/classic_rsi/state/daily_new_trades.json")
ENV_OVERRIDE = "CLASSIC_TRADE_COUNTER"
COUNTED = ("reserved", "placed")


def counter_path() -> tuple[Path, Optional[str]]:
    """(path, error). Env override only in test mode; set in production => error (fail closed)."""
    test_root = os.environ.get(TEST_ENV)
    ov = os.environ.get(ENV_OVERRIDE)
    if test_root:
        return (Path(ov) if ov else Path(test_root) / "state" / "daily_new_trades.json"), None
    if ov:
        return PROD_COUNTER_PATH, "COUNTER_ENV_OVERRIDE_IN_PRODUCTION"
    return PROD_COUNTER_PATH, None


def _day(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(IDT)).astimezone(IDT).strftime("%Y-%m-%d")


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a+") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _read(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _write(path: Path, d: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(d, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _pid(x: Any) -> Optional[str]:
    return None if x in (None, "") else str(x).strip()


def _summ(d: dict[str, Any], day: str, external: Any, path: Path) -> dict[str, Any]:
    """count = unmarked reservations + |placed positionIds ∪ external (book+history) positionIds|.
    Placed slots without a positionId count individually (fail closed)."""
    slots = list((d.get(day) or {}).get("slots") or [])
    live = [s for s in slots if s.get("state") in COUNTED]
    reserved = [s for s in live if s["state"] == "reserved"]
    placed = [s for s in live if s["state"] == "placed"]
    ext = {_pid(x) for x in (external or [])} - {None}
    placed_ids = {_pid(s.get("positionId")) for s in placed} - {None}
    placed_noid = sum(1 for s in placed if _pid(s.get("positionId")) is None)
    union = placed_ids | ext
    count = len(reserved) + placed_noid + len(union)
    rem = max(0, MAX_NEW_TRADES_PER_DAY - count)
    return {"day": day, "count": count, "reserved": len(reserved), "placed": len(placed),
            "external_position_ids": sorted(ext), "history_only_opens": len(ext - placed_ids),
            "union_position_ids": sorted(union), "max": MAX_NEW_TRADES_PER_DAY, "remaining": rem,
            "ok": rem > 0, "path": str(path)}


def _fail(day: str, path: Path, err: str) -> dict[str, Any]:
    return {"day": day, "count": None, "max": MAX_NEW_TRADES_PER_DAY, "remaining": 0, "ok": False,
            "error": err, "path": str(path)}


def status(now: Optional[datetime] = None, external_position_ids: Any = ()) -> dict[str, Any]:
    path, err = counter_path()
    day = _day(now)
    if err:
        return _fail(day, path, err)
    with _locked(path):
        d = _read(path)
    if d is None:
        return _fail(day, path, f"COUNTER_UNREADABLE: {path}")
    return _summ(d, day, external_position_ids, path)


def reserve(key: str, symbol: str, *, now: Optional[datetime] = None, external_position_ids: Any = (),
            instrument_id: Any = None) -> dict[str, Any]:
    """Atomic check+reserve. Idempotent per (day, key): a live reservation for key is returned again."""
    path, err = counter_path()
    n = now or datetime.now(IDT)
    day = _day(n)
    if err:
        return {**_fail(day, path, err), "reservation": None}
    with _locked(path):
        d = _read(path)
        if d is None:
            return {**_fail(day, path, f"COUNTER_UNREADABLE: {path}"), "reservation": None}
        slots = d.setdefault(day, {}).setdefault("slots", [])
        for s in slots:
            if s.get("key") == key and s.get("state") in COUNTED:
                return {**_summ(d, day, external_position_ids, path), "ok": True, "reservation": s["id"],
                        "idempotent": True}
        st = _summ(d, day, external_position_ids, path)
        if not st["ok"]:
            return {**st, "reservation": None}
        rid = f"tc-{day}-{uuid.uuid4().hex[:12]}"
        slots.append({"id": rid, "key": key, "symbol": symbol, "instrumentId": instrument_id, "state": "reserved",
                      "reserved_at": n.astimezone(IDT).isoformat(timespec="seconds")})
        _write(path, d)
        return {**_summ(d, day, external_position_ids, path), "ok": True, "reservation": rid}


def _transition(rid: str, new_state: str, **extra: Any) -> dict[str, Any]:
    path, err = counter_path()
    if err:
        raise RuntimeError(err)
    with _locked(path):
        d = _read(path)
        if d is None:
            raise RuntimeError(f"COUNTER_UNREADABLE: {path}")
        for day, v in d.items():
            for s in (v or {}).get("slots") or []:
                if s.get("id") == rid:
                    if s["state"] != "reserved":
                        raise RuntimeError(f"reservation {rid} already {s['state']}")
                    s["state"] = new_state
                    s.update({k: v2 for k, v2 in extra.items() if v2 is not None})
                    s[f"{new_state}_at"] = datetime.now(IDT).isoformat(timespec="seconds")
                    _write(path, d)
                    return {"id": rid, "state": new_state, "day": day}
    raise RuntimeError(f"reservation {rid} not found")


def mark(rid: str, *, position_id: Any = None) -> dict[str, Any]:
    """Place succeeded: reserved -> placed (still counts)."""
    return _transition(rid, "placed", positionId=position_id)


def release(rid: str, *, reason: str = "") -> dict[str, Any]:
    """Place failed / not attempted: reserved -> released (frees the slot)."""
    return _transition(rid, "released", release_reason=reason or None)


def release_stale(max_age_min: float = 30.0, now: Optional[datetime] = None,
                  blocker: Optional[Any] = None) -> list[dict[str, Any]]:
    """Release reservations still 'reserved' (never marked) older than max_age_min. Returns released slots.
    Only safe because the pre-buy refresh first re-reads trading history/book: a fill that was placed but
    not marked still counts through its positionId there."""
    path, err = counter_path()
    if err:
        raise RuntimeError(err)
    n = now or datetime.now(IDT)
    out: list[dict[str, Any]] = []
    changed = False
    with _locked(path):
        d = _read(path)
        if d is None:
            raise RuntimeError(f"COUNTER_UNREADABLE: {path}")
        for v in d.values():
            for s_ in (v or {}).get("slots") or []:
                if s_.get("state") != "reserved":
                    continue
                try:
                    t = datetime.fromisoformat(s_["reserved_at"])
                except (KeyError, ValueError):
                    continue  # unparseable => keep counting (fail closed)
                if (n - t).total_seconds() > max_age_min * 60:
                    why = blocker(s_, t) if blocker is not None else "NO_ORDERS_READ"
                    if why:  # pending order / new position for this instrument (or no read) => keep counting
                        s_["release_blocked"] = why
                        s_["release_blocked_at"] = n.astimezone(IDT).isoformat(timespec="seconds")
                        changed = True
                        continue
                    s_["state"] = "released"
                    s_["release_reason"] = f"stale unmarked > {max_age_min:g} min (pre_buy_refresh)"
                    s_["released_at"] = n.astimezone(IDT).isoformat(timespec="seconds")
                    out.append(dict(s_))
        if out or changed:
            _write(path, d)
    return out


def count_opens_today(now: datetime, *, positions: Optional[list] = None, history: Optional[list] = None) -> set:
    """Distinct positionIds whose openTime falls on today's IDT date — open book AND trading history
    (covers positions opened and closed the same day)."""
    day = _day(now)
    ids: set = set()
    for p in list(positions or []) + list(history or []):
        if not isinstance(p, dict):
            continue
        ot = p.get("openTime") or p.get("openDateTime") or p.get("openDate") or p.get("openTimestamp")
        if not ot:
            continue
        try:
            t = datetime.fromisoformat(str(ot).replace("Z", "+00:00").replace(" ", "T"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=ZoneInfo("UTC"))
        if t.astimezone(IDT).strftime("%Y-%m-%d") == day:
            ids.add(str(p.get("positionId") or p.get("positionID") or f"{p.get('instrumentId')}@{ot}"))
    return ids


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Classic daily new-trade counter (max 4/IDT day)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    m = sub.add_parser("mark", help="after a confirmed NEW buy fill")
    m.add_argument("--reservation", required=True)
    m.add_argument("--position-id", required=True)
    r = sub.add_parser("release", help="place failed / not attempted")
    r.add_argument("--reservation", required=True)
    r.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        out = status()
    elif a.cmd == "mark":
        out = mark(a.reservation, position_id=a.position_id)
    else:
        out = release(a.reservation, reason=a.reason)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

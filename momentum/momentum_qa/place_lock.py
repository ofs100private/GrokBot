"""Single-use QA-verdict idempotency lock (incident 2026-10-15: VTRS/STLD duplicated).

BOTH the EOD routine and the parent chat MUST call `acquire` before ANY place-trade
on Momentum-HHHGDTJ, and `mark` after.

Lock key = sha256(verdict file bytes)[:12] + SYMBOL, created atomically with
os.open(O_CREAT|O_EXCL) under /workspace/momentum_audit/place_locks/.
The same verdict sha NEVER re-places a symbol. A FAILED/EXPIRED lock may only be
retried with retry_after_fail=True AND a *different* (fresh) verdict file sha.

CLI:
  python -m momentum_qa.place_lock acquire --verdict V.json --symbol VTRS --caller eod-routine \
        --positions-json live_positions.json   (or '-' for stdin)  [--allow-held] [--retry-after-fail]
        [--instrument-id N]   (held = id match OR base-ticker match; A.US/A.RTH == A;
                              an id known as another ticker -> ID_SYMBOL_MISMATCH exit 5, no lock)
  python -m momentum_qa.place_lock mark --lock <path> --status PLACED --order-id 123 --position-id 456
Exit codes: 0 OK, 2 LOCK_HELD, 3 ALREADY_HELD, 4 RETRY_NOT_ALLOWED / POSITIONS_STALE / bad input /
            MANUAL_REF_REQUIRED / MANUAL_FROM_ROUTINE_REFUSED / AUDIT_WRITE_FAILED, 5 ID_SYMBOL_MISMATCH,
            6 buy guard, no lock written: SCHEDULE_MISALIGNED / EARLY_CLOSE_DAY (automatic) or
              MARKET_CLOSED / INTRADAY_BAN (manual).

Buy schedule guard (DST-M1 / DST-M2, 2026-10-24b). A BUY = an acquire without --allow-held (PM
trail/close and the open-gap CLOSE pass --allow-held and are never blocked). Against the actual NYSE
close of the current NY session (momentum_qa.market_clock, exchange_calendars or the 2026 table):
  * NYSE closed today                      -> SCHEDULE_MISALIGNED (exit 6)
  * early-close session (13:00 NY)         -> EARLY_CLOSE_DAY     (exit 6), all day
  * now < close-90m or now >= close-1m     -> SCHEDULE_MISALIGNED (exit 6)
  2026-10-24d (Ofer 2026-10-24 00:53 IDT: routines stay at 21:40-21:58 IL permanently; widen so the 21:40 run can
  buy): window close-90m..close-1m (was -60m). Close 22:00 IL (gap weeks): 20:30:00-21:58:59 IL; close 23:00 IL
  (from 2026-11-02): 21:30:00-22:58:59 IL. The window (>= 14:30 NY) never overlaps the 09:30-11:30 NY INTRADAY_BAN.
  So a missed / early DST cron move can no longer place buys ~1h early or after the close.

Manual path (Ofer 2026-10-24 00:24 IDT: "Block only the automatic EOD buys outside the last hour; my own
requested buys can go any time (still QA-gated, never in the first 2 hours)"):
  acquire ... --manual-request <ref>   ref = Ofer's chat message (required, non-empty; e.g. "slack:<ts>" or quoted text)
  Skips only the close-90m..close-1m window and EARLY_CLOSE_DAY. Still refuses (exit 6, no lock):
    MARKET_CLOSED  no NYSE session today, or outside the regular session open..actual close (early close 13:00 NY)
    INTRADAY_BAN   first 2h of RTH, 09:30-11:30 New York time
  and every other check (fresh positions, held, ID match, lock/verdict single-use) as before. QA Bot place-QA
  is still required by the flow. Empty / blank ref -> MANUAL_REF_REQUIRED (exit 4). The ref is stored in the
  lock (manual_request, buy_path=manual) and in one PLACE_LOCK_MANUAL audit row (acquired or refused);
  if that audit row cannot be written the lock is marked FAILED and the acquire fails (exit 4).
  AUTOMATIC ROUTINES MUST NEVER PASS --manual-request (tests assert no routine paste file contains it).
  2026-10-24c: --manual-request with a routine caller (--caller starting with "eod-") is refused fail closed:
  MANUAL_FROM_ROUTINE_REFUSED (exit 4, no lock, PLACE_LOCK_MANUAL REFUSED audit row). An exit 6 inside a
  routine is final (place_flow.md step 6): no retry, no manual path.

Clock (D-M1, 2026-10-24c): the guards use the real clock only (_guard_now = datetime.now). There is NO
environment-variable or config override; tests inject time via acquire(now=...) or monkeypatch _guard_now.

Calendar (D-L1, 2026-10-24c): if exchange_calendars is unavailable and the NY year has no fallback table
(market_clock.FALLBACK_YEARS), automatic buys are refused: SCHEDULE_MISALIGNED, reason_code
CALENDAR_UNAVAILABLE (exit 6). Every buy lock records schedule_guard.calendar_source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from momentum_qa import market_clock as MC
from momentum_qa.instrument_map import base_symbol, id_symbol_mismatch, instrument_id as mapped_instrument_id, is_held

LOCK_DIR = Path("/workspace/momentum_audit/place_locks")
DEFAULT_ACCOUNT = "Momentum-HHHGDTJ"
STATUSES = ("ACQUIRED", "PLACED", "FAILED", "EXPIRED")
EXIT_OK, EXIT_LOCK_HELD, EXIT_ALREADY_HELD, EXIT_RETRY_NOT_ALLOWED = 0, 2, 3, 4
EXIT_ID_SYMBOL_MISMATCH = 5  # --instrument-id is a different instrument than the symbol: never acquire
POSITIONS_MAX_AGE_S = 120  # live get-my-positions-and-orders must be this fresh
EXIT_SCHEDULE = 6          # SCHEDULE_MISALIGNED / EARLY_CLOSE_DAY: buy refused, no lock written
BUY_OPEN_BEFORE_CLOSE = timedelta(minutes=90)  # buys allowed from close-90m (2026-10-24d; was 60m) ...
BUY_STOP_BEFORE_CLOSE = timedelta(minutes=1)   # ... until (excluding) close-1m
ROUTINE_CALLER_PREFIX = "eod-"  # every EOD routine caller (eod-pm-2240, eod-pm-2242-backup, eod-screener-*, ...)


class PlaceLockError(Exception):
    def __init__(self, code: str, exit_code: int, msg: str, lock_path: str | None = None):
        super().__init__(f"{code}: {msg}")
        self.code, self.exit_code, self.msg, self.lock_path = code, exit_code, msg, lock_path


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _norm(sym: str) -> str:
    """Base ticker: eToro 'A.US' / 'X.RTH' -> 'A' / 'X' (QA Bot 2026-10-21 SYMBOL_MAP_A)."""
    return base_symbol(sym)


def held_index(positions_obj) -> tuple[set[str], set[int]]:
    """(base symbols, instrumentIds) held in a get-my-positions-and-orders JSON."""
    syms: set[str] = set()
    ids: set[int] = set()

    def walk(o, in_positions=False, iid=None):
        if isinstance(o, dict):
            if in_positions:
                v_iid = o.get("instrumentId", iid)
                try:
                    if v_iid not in (None, ""):
                        ids.add(int(v_iid))
                        iid = int(v_iid)
                except (TypeError, ValueError):
                    pass
                for k in ("symbol", "symbolFull", "instrumentSymbol", "ticker", "internalSymbolFull"):
                    v = o.get(k)
                    if isinstance(v, str) and v.strip():
                        mk = o.get("market") if isinstance(o.get("market"), dict) else {}
                        syms.add(base_symbol(v, o.get("instrumentId", mk.get("instrumentId", iid))))
                        break
            for k, v in o.items():
                kl = k.lower()
                walk(v, in_positions or kl in ("positions", "openpositions", "clientportfolio_positions"), iid)
        elif isinstance(o, list):
            for v in o:
                walk(v, in_positions, None)

    walk(positions_obj)
    return syms, ids


def held_symbols(positions_obj) -> set[str]:
    """Extract held symbols (base tickers) from a get-my-positions-and-orders JSON (tolerant of shapes)."""
    out: set[str] = set()

    def walk(o, in_positions=False):
        if isinstance(o, dict):
            if in_positions:
                for k in ("symbol", "symbolFull", "instrumentSymbol", "ticker", "internalSymbolFull"):
                    v = o.get(k)
                    if isinstance(v, str) and v.strip():
                        mk = o.get("market") if isinstance(o.get("market"), dict) else {}
                        out.add(base_symbol(v, o.get("instrumentId", mk.get("instrumentId"))))
                        break
            for k, v in o.items():
                kl = k.lower()
                walk(v, in_positions or kl in ("positions", "openpositions", "clientportfolio_positions"))
        elif isinstance(o, list):
            for v in o:
                walk(v, in_positions)

    walk(positions_obj)
    return out


def _load_positions(src):
    if src is None:
        return None
    if isinstance(src, (dict, list)):
        return src
    if src == "-":
        return json.load(sys.stdin)
    if isinstance(src, str) and src.startswith("@"):
        src = src[1:]
    try:
        return json.loads(Path(src).read_text())
    except json.JSONDecodeError:
        # raw MCP write_to_file output may carry wrapper text; reuse precheck's tolerant loader
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from momentum_qa.precheck import load_json_file, _unwrap
        return _unwrap(load_json_file(src))


def _parse_ts(ts: str) -> datetime:
    """Parse eToro/ISO timestamps (tolerates >6 fractional digits and Z)."""
    s = str(ts).replace("Z", "+00:00")
    if "." in s:
        head, rest = s.split(".", 1)
        frac = "".join(ch for ch in rest if ch.isdigit())
        tz = rest[len(frac):]
        s = f"{head}.{frac[:6]}{tz}"
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def positions_timestamp(positions_obj):
    """Top-level timestamp or asOf from get-my-positions-and-orders (or None)."""
    if not isinstance(positions_obj, dict):
        return None
    ts = positions_obj.get("timestamp")
    if ts is None:
        ts = positions_obj.get("asOf")
    if ts is None or (isinstance(ts, str) and not ts.strip()):
        return None
    return ts


def require_fresh_positions(positions_obj, *, now: datetime | None = None,
                            max_age_s: float = POSITIONS_MAX_AGE_S) -> float:
    """Return age seconds, or raise PlaceLockError POSITIONS_STALE (exit 4)."""
    raw = positions_timestamp(positions_obj)
    if raw is None:
        raise PlaceLockError(
            "POSITIONS_STALE", EXIT_RETRY_NOT_ALLOWED,
            "positions JSON missing top-level timestamp/asOf (refuse stale/unknown age)",
        )
    try:
        ts = _parse_ts(raw)
    except Exception as e:
        raise PlaceLockError(
            "POSITIONS_STALE", EXIT_RETRY_NOT_ALLOWED,
            f"positions timestamp unparsable: {raw!r} ({e})",
        )
    now = now or datetime.now(timezone.utc)
    age = (now - ts).total_seconds()
    if age < -5 or age > max_age_s:
        raise PlaceLockError(
            "POSITIONS_STALE", EXIT_RETRY_NOT_ALLOWED,
            f"positions age {age:.0f}s > {max_age_s:.0f}s (timestamp={raw})",
        )
    return age


def _guard_now() -> datetime:
    """Real clock only (D-M1). No env/config override; tests pass now= or monkeypatch this function."""
    return datetime.now(tz=MC.IL)


def is_routine_caller(caller) -> bool:
    return isinstance(caller, str) and caller.strip().lower().startswith(ROUTINE_CALLER_PREFIX)


def manual_buy_guard(now: datetime | None = None) -> dict:
    """Manual (Ofer-requested) buy guard: regular session open and not in the first 2h. Read-only."""
    now = now or _guard_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=MC.IL)
    now = now.astimezone(MC.IL)
    ny_day = now.astimezone(MC.NY).date()
    info = MC.session_info(ny_day)
    out = {"now_il": now.isoformat(), "ny_day": ny_day.isoformat(), "session": info,
           "calendar_source": info.get("source")}
    if not info["is_session"]:
        return {**out, "ok": False, "code": "MARKET_CLOSED", "reason": f"no NYSE session on {ny_day} (NY date)"}
    open_, close = MC.nyse_open_il(ny_day), MC.nyse_close_il(ny_day)
    out.update(open_il=open_.isoformat(), close_il=close.isoformat())
    if not (open_ <= now < close):
        return {**out, "ok": False, "code": "MARKET_CLOSED",
                "reason": f"{MC.hhmm(now)} IL is outside the regular session {MC.hhmm(open_)}-{MC.hhmm(close)} IL"}
    if MC.in_intraday_ban(now):
        return {**out, "ok": False, "code": "INTRADAY_BAN",
                "reason": f"{MC.hhmm(now)} IL is in the first 2h of NYSE trading (09:30-11:30 New York time)"}
    return {**out, "ok": True, "code": "OK", "reason": "manual buy: regular session open, after the first 2h"}


def _audit_manual(row: dict, audit_dir) -> None:
    from momentum_qa.audit import append_row, build_record, new_run_id
    append_row(build_record(new_run_id("placelock"), "momentum_qa/place_lock.py", row), audit_dir)


def buy_schedule_guard(now: datetime | None = None) -> dict:
    """DST-M1/M2 buy guard. {"ok", "code", "reason", "now_il", "close_il", "window_il", ...}. Read-only."""
    now = now or _guard_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=MC.IL)
    now = now.astimezone(MC.IL)
    ny_day = now.astimezone(MC.NY).date()
    info = MC.session_info(ny_day)
    out = {"now_il": now.isoformat(), "ny_day": ny_day.isoformat(), "session": info,
           "calendar_source": info.get("source")}
    if not MC.calendar_covers(ny_day):  # D-L1: no exchange_calendars and no fallback table for this year
        return {**out, "ok": False, "code": "SCHEDULE_MISALIGNED", "reason_code": "CALENDAR_UNAVAILABLE",
                "reason": (f"CALENDAR_UNAVAILABLE: exchange_calendars unavailable and no NYSE fallback table for "
                           f"{ny_day.year}; automatic buys refused")}
    if not info["is_session"]:
        return {**out, "ok": False, "code": "SCHEDULE_MISALIGNED",
                "reason": f"no NYSE session on {ny_day} (NY date); buys only in the last hour before the close"}
    close = MC.nyse_close_il(ny_day)
    lo, hi = close - BUY_OPEN_BEFORE_CLOSE, close - BUY_STOP_BEFORE_CLOSE
    out.update(close_il=close.isoformat(), window_il=[lo.isoformat(), hi.isoformat()])
    if info["early_close"]:
        return {**out, "ok": False, "code": "EARLY_CLOSE_DAY",
                "reason": f"NYSE early close {info['close_ny']} NY ({MC.hhmm(close)} IL) on {ny_day}: no buys today"}
    if now < lo or now >= hi:
        return {**out, "ok": False, "code": "SCHEDULE_MISALIGNED",
                "reason": (f"buy at {MC.hhmm(now)} IL outside {MC.hhmm(lo)}-{MC.hhmm(hi)} IL "
                           f"(NYSE close {MC.hhmm(close)} IL -90m .. -1m); check the EOD cron schedule")}
    return {**out, "ok": True, "code": "OK", "reason": "inside the pre-close buy window"}


def lock_path_for(sha: str, symbol: str, lock_dir: Path | None = None) -> Path:
    return Path(lock_dir or LOCK_DIR) / f"{sha[:12]}-{_norm(symbol)}.lock"


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"status": "UNREADABLE"}


def _same_symbol_locks(symbol: str, lock_dir: Path) -> list[tuple[Path, dict]]:
    return [(p, _read(p)) for p in sorted(lock_dir.glob(f"*-{_norm(symbol)}.lock"))]


def acquire(verdict_path, symbol, account: str = DEFAULT_ACCOUNT, *, caller: str = "unknown",
            positions=None, allow_held: bool = False, retry_after_fail: bool = False,
            lock_dir: Path | None = None, instrument_id: int | None = None, now: datetime | None = None,
            manual_request: str | None = None, audit_dir: Path | None = None) -> dict:
    """Atomically take the single-use lock for (verdict sha, symbol). Raises PlaceLockError.
    Automatic buys (allow_held=False, no manual_request) must pass buy_schedule_guard(now); manual buys
    (manual_request=<Ofer's message ref>) pass manual_buy_guard(now) instead (exit 6, no lock written)."""
    manual = manual_request is not None
    if manual and is_routine_caller(caller):  # 2026-10-24c: routines never use the manual path; fail closed first
        reason = (f"--manual-request refused for routine caller {caller!r}: an exit 6 inside a routine is final "
                  f"(no retry, no manual path); the manual path is only for a buy Ofer requested in chat")
        _audit_manual_safe({"event": "PLACE_LOCK_MANUAL", "result": "REFUSED", "code": "MANUAL_FROM_ROUTINE_REFUSED",
                            "symbol": str(symbol).strip().upper(), "caller": caller,
                            "manual_request": str(manual_request).strip(), "allow_held": bool(allow_held),
                            "reason": reason, "now_il": (now or _guard_now()).isoformat()}, audit_dir)
        raise PlaceLockError("MANUAL_FROM_ROUTINE_REFUSED", EXIT_RETRY_NOT_ALLOWED, reason)
    if manual and (not isinstance(manual_request, str) or not manual_request.strip()):
        raise PlaceLockError("MANUAL_REF_REQUIRED", EXIT_RETRY_NOT_ALLOWED,
                             "--manual-request needs a non-empty reference to Ofer's chat message")
    manual_ref = manual_request.strip() if manual else None
    lock_dir = Path(lock_dir or LOCK_DIR)
    lock_dir.mkdir(parents=True, exist_ok=True)
    sym = _norm(symbol)
    if not sym:
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "empty symbol")
    mm = id_symbol_mismatch(sym, instrument_id)
    if mm:  # QA 2026-10-21 HIGH: a mismatched id never overrides the symbol -> refuse, no lock
        raise PlaceLockError("ID_SYMBOL_MISMATCH", EXIT_ID_SYMBOL_MISMATCH, mm)
    guard = None
    if not allow_held:  # DST-M1/M2: automatic buys only in the last hour before the actual close
        guard = manual_buy_guard(now) if manual else buy_schedule_guard(now)
        if not guard["ok"]:
            if manual:
                _audit_manual_safe({"event": "PLACE_LOCK_MANUAL", "result": "REFUSED", "code": guard["code"],
                                    "symbol": sym, "caller": caller, "manual_request": manual_ref,
                                    "reason": guard["reason"], "now_il": guard["now_il"]}, audit_dir)
            raise PlaceLockError(guard["code"], EXIT_SCHEDULE, guard["reason"])
    sha = sha256_file(verdict_path)
    lp = lock_path_for(sha, sym, lock_dir)

    # 1) live-positions check (buys only; PM trail/close pass allow_held)
    pos = _load_positions(positions)
    if pos is None and not allow_held:
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "live positions JSON required (or --allow-held for PM actions)")
    # Freshness: any provided positions JSON must carry timestamp/asOf <120s (missing = refuse)
    if pos is not None:
        require_fresh_positions(pos)
    if pos is not None and not allow_held:
        h_syms, h_ids = held_index(pos)
        h_syms |= held_symbols(pos)
        iid = instrument_id if instrument_id is not None else mapped_instrument_id(sym)
        if is_held(sym, h_syms, h_ids, iid):
            raise PlaceLockError("ALREADY_HELD", EXIT_ALREADY_HELD, f"{sym} already held on {account}")

    # 2) other locks for this symbol under different verdicts
    for p, d in _same_symbol_locks(sym, lock_dir):
        if p == lp:
            continue
        st = d.get("status")
        if st in ("ACQUIRED", "PLACED", "UNREADABLE"):
            raise PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD, f"{sym} has {st} lock {p.name}", str(p))
        if st in ("FAILED", "EXPIRED") and not retry_after_fail:
            raise PlaceLockError("RETRY_NOT_ALLOWED", EXIT_RETRY_NOT_ALLOWED,
                                 f"{sym} prior lock {p.name} is {st}; pass --retry-after-fail with a fresh verdict", str(p))

    # 3) atomic create; same sha never re-places, whatever its status
    rec = {"ts": _now(), "pid": os.getpid(), "caller": caller, "account": account,
           "verdict_path": str(Path(verdict_path).resolve()), "verdict_sha256": sha,
           "symbol": sym, "status": "ACQUIRED", "retry_after_fail": bool(retry_after_fail),
           "allow_held": bool(allow_held)}
    if guard is not None:
        rec["schedule_guard"] = {k: guard.get(k) for k in ("code", "close_il", "window_il", "open_il", "calendar_source")
                                 if k in guard}
        rec["buy_path"] = "manual" if manual else "auto"
    if manual:
        rec["manual_request"] = manual_ref
    try:
        fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        d = _read(lp)
        raise PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD,
                             f"verdict sha {sha[:12]} already used for {sym} (status={d.get('status')}, caller={d.get('caller')})", str(lp))
    with os.fdopen(fd, "w") as f:
        json.dump(rec, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    rec["lock_path"] = str(lp)
    if manual:  # fail closed: a manual lock without its audit row is unusable
        try:
            _audit_manual({"event": "PLACE_LOCK_MANUAL", "result": "ACQUIRED", "symbol": sym, "caller": caller,
                           "manual_request": manual_ref, "allow_held": bool(allow_held), "lock_path": str(lp),
                           "verdict_sha256": sha, "now_il": (guard or {}).get("now_il")}, audit_dir)
        except Exception as e:
            mark(lp, "FAILED", note=f"manual audit row not written: {e}")
            raise PlaceLockError("AUDIT_WRITE_FAILED", EXIT_RETRY_NOT_ALLOWED,
                                 f"manual lock not usable, audit row failed: {e}", str(lp))
    return rec


def _audit_manual_safe(row: dict, audit_dir) -> None:
    try:
        _audit_manual(row, audit_dir)
    except Exception as e:  # the refusal stands either way
        print(f"place_lock: manual refusal audit row failed: {e}", file=sys.stderr)


def mark(lock, status: str, *, order_id=None, position_id=None, note: str | None = None) -> dict:
    """Record the outcome on an acquired lock. The lock file is never deleted (single-use)."""
    status = status.upper()
    if status not in ("PLACED", "FAILED", "EXPIRED"):
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, f"bad status {status}")
    lp = Path(lock)
    d = _read(lp)
    if d.get("status") == "PLACED" and status != "PLACED":
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "cannot downgrade a PLACED lock")
    d.setdefault("history", []).append({"ts": _now(), "status": status, "pid": os.getpid()})
    d.update(status=status, marked_ts=_now())
    if order_id is not None:
        d["orderId"] = order_id
    if position_id is not None:
        d["positionId"] = position_id
    if note:
        d["note"] = note
    tmp = lp.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, lp)
    return d


release = mark  # alias: release(lock, status=...)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="place_lock")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("--verdict", required=True)
    a.add_argument("--symbol", required=True)
    a.add_argument("--account", default=DEFAULT_ACCOUNT)
    a.add_argument("--caller", default="cli")
    a.add_argument("--positions-json", help="file path or '-' for stdin")
    a.add_argument("--allow-held", action="store_true",
                   help="PM / risk actions only (trail/close); without it the acquire is a BUY and passes the schedule guard")
    a.add_argument("--retry-after-fail", action="store_true")
    a.add_argument("--manual-request", metavar="REF",
                   help="ONLY for a buy Ofer requested in chat: REF names his message (required, non-empty). "
                        "Skips the close-90m..-1m window; still needs RTH open and not 09:30-11:30 NY. "
                        "Automatic routines must never pass this; refused (exit 4) when --caller starts with 'eod-'.")
    a.add_argument("--instrument-id", type=int, help="eToro instrumentId of the buy (held = id OR symbol match; an id of another ticker -> exit 5)")
    a.add_argument("--lock-dir")
    m = sub.add_parser("mark")
    m.add_argument("--lock", required=True)
    m.add_argument("--status", required=True, choices=["PLACED", "FAILED", "EXPIRED"])
    m.add_argument("--order-id")
    m.add_argument("--position-id")
    m.add_argument("--note")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "acquire":
            r = acquire(args.verdict, args.symbol, args.account, caller=args.caller,
                        positions=args.positions_json, allow_held=args.allow_held,
                        retry_after_fail=args.retry_after_fail,
                        lock_dir=Path(args.lock_dir) if args.lock_dir else None,
                        instrument_id=args.instrument_id, manual_request=args.manual_request)
        else:
            r = mark(args.lock, args.status, order_id=args.order_id, position_id=args.position_id, note=args.note)
        print(json.dumps({"ok": True, **r}))
        return EXIT_OK
    except PlaceLockError as e:
        print(json.dumps({"ok": False, "code": e.code, "reason": e.msg, "lock_path": e.lock_path}))
        print(e.code, file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())

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
  python -m momentum_qa.place_lock mark --lock <path> --status PLACED --order-id 123 --position-id 456
Exit codes: 0 OK, 2 LOCK_HELD, 3 ALREADY_HELD, 4 RETRY_NOT_ALLOWED / POSITIONS_STALE / bad input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path("/workspace/momentum_audit/place_locks")
DEFAULT_ACCOUNT = "Momentum-HHHGDTJ"
STATUSES = ("ACQUIRED", "PLACED", "FAILED", "EXPIRED")
EXIT_OK, EXIT_LOCK_HELD, EXIT_ALREADY_HELD, EXIT_RETRY_NOT_ALLOWED = 0, 2, 3, 4
POSITIONS_MAX_AGE_S = 120  # live get-my-positions-and-orders must be this fresh


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
    return str(sym or "").strip().upper()


def held_symbols(positions_obj) -> set[str]:
    """Extract held symbols from a get-my-positions-and-orders JSON (tolerant of shapes)."""
    out: set[str] = set()

    def walk(o, in_positions=False):
        if isinstance(o, dict):
            if in_positions:
                for k in ("symbol", "symbolFull", "instrumentSymbol", "ticker", "internalSymbolFull"):
                    v = o.get(k)
                    if isinstance(v, str) and v.strip():
                        out.add(_norm(v))
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
            lock_dir: Path | None = None) -> dict:
    """Atomically take the single-use lock for (verdict sha, symbol). Raises PlaceLockError."""
    lock_dir = Path(lock_dir or LOCK_DIR)
    lock_dir.mkdir(parents=True, exist_ok=True)
    sym = _norm(symbol)
    if not sym:
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "empty symbol")
    sha = sha256_file(verdict_path)
    lp = lock_path_for(sha, sym, lock_dir)

    # 1) live-positions check (buys only; PM trail/close pass allow_held)
    pos = _load_positions(positions)
    if pos is None and not allow_held:
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "live positions JSON required (or --allow-held for PM actions)")
    # Freshness: any provided positions JSON must carry timestamp/asOf <120s (missing = refuse)
    if pos is not None:
        require_fresh_positions(pos)
    if pos is not None and not allow_held and sym in held_symbols(pos):
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
    return rec


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
    a.add_argument("--allow-held", action="store_true", help="PM actions only (trail/close)")
    a.add_argument("--retry-after-fail", action="store_true")
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
                        lock_dir=Path(args.lock_dir) if args.lock_dir else None)
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

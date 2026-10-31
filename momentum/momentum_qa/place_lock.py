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
        [--action TRAIL_SL|MOVE_SL_BREAKEVEN|CLOSE]  (risk actions, with --allow-held; default: read from the verdict)
        [--run-id <caller run id>]                   (stored in the lock and in every refusal audit row)
  python -m momentum_qa.place_lock mark --lock <path> --status PLACED --order-id 123 --position-id 456 \
        [--verify-live-sl 171.89 | --verify-closed] [--run-id <id>]   (post-read, risk locks)

Action-scoped risk locks (2026-10-30a, QA Bot ruling 1; incident XOM 2026-10-26..28: the PLACED 10-23 TRAIL_SL
lock e611cd183fe7-XOM.lock returned LOCK_HELD for a NEW QA-passed MOVE_SL_BREAKEVEN, so the stop move was
silently dropped). An acquire WITH --allow-held is a RISK action. Its lock key = verdict sha + symbol + action:
  file <sha12>-<SYM>~<ACTION>.lock (action known)  |  <sha12>-<SYM>.lock (action UNKNOWN = legacy name)
  action = --action, else the verdict's row for the symbol (PM list rows / {"action": ..}), else UNKNOWN.
  Same verdict sha + same symbol + same action -> LOCK_HELD (single use; a legacy <sha12>-<SYM>.lock of the same
  sha also counts). Locks of OTHER verdicts for the symbol block a risk action only when:
    * ACQUIRED / UNREADABLE and younger than INFLIGHT_TTL_S (900 s): another run is mid-place -> LOCK_HELD;
    * PLACED or ACQUIRED with the SAME action on the SAME IL day (duplicate wake / re-run) -> LOCK_HELD
      (reason DUPLICATE_ACTION_SAME_DAY); a request whose action is UNKNOWN is blocked by any same-day
      risk lock (fail closed for the night, never across days);
    * FAILED / EXPIRED with the SAME action on the SAME IL day -> RETRY_NOT_ALLOWED unless --retry-after-fail.
  Everything else (PLACED locks of earlier days, PLACED buy locks, a different action, stale ACQUIRED
  locks) does NOT block; the skipped locks are listed in the new lock's "ignored_locks".
  LEGACY lock files (no "action" field): action = the "~ACTION" filename suffix, else the row for the symbol in the
  lock's verdict_path (only if that file still has the lock's verdict sha), else the first token of "note" if it
  is a risk action, else BUY for allow_held=false locks and UNKNOWN otherwise. A legacy PLACED lock whose action
  is UNKNOWN or different never blocks a new protective action (it records a finished action); only a same-day
  same-action (or in-flight ACQUIRED) legacy lock does.
BUYS (no --allow-held) are unchanged: any ACQUIRED / PLACED / UNREADABLE lock for the symbol -> LOCK_HELD,
  FAILED / EXPIRED -> RETRY_NOT_ALLOWED without --retry-after-fail (DUPLICATE_PLACE protection).

Refusal audit (2026-10-30a, QA Bot ruling 2): EVERY acquire refusal (exit 2/3/4/5/6) appends one
PLACE_LOCK_REFUSED row to momentum_audit/<IL date>.jsonl: symbol, action, exit_code, code, reason, lock_path,
run_id (= --run-id, else a new placelock-* id), caller, allow_held, verdict_sha256. A failed row write never
turns a refusal into a pass (stderr note). mark() on a RISK lock appends one PLACE_LOCK_MARK row (status,
action, orderId, positionId, verify_live_sl / verify_closed post-read, expected_sl) — feedback_daily uses it
as the PLACE_ACK of the protective action.
2026-10-30b (QA Bot FAIL 1 on 30a, qa-review-staged-20261030a.json QA-02..QA-05, QA-10):
  * Symbol (QA-10): the stripped upper-case --symbol must match ^[A-Z0-9.]{1,10}$, must not contain "..", and must
    not start or end with "." -> else BAD_INPUT (reason_code BAD_SYMBOL, exit 4, audited). No '~', '/', '-', spaces.
  * --action (QA-04): only TRAIL_SL | MOVE_SL_BREAKEVEN | CLOSE (RISK_ACTIONS) with --allow-held; anything else ->
    BAD_INPUT reason_code ACTION_NOT_ALLOWED (exit 4, audited). If the verdict has a risk row for the symbol and
    --action is not one of its actions -> BAD_INPUT reason_code ACTION_VERDICT_MISMATCH (exit 4, audited).
    The in-flight rule (ACQUIRED / UNREADABLE < INFLIGHT_TTL_S) now also applies to locks of the SAME verdict.
  * Per-symbol mutex (QA-03): fcntl.flock(LOCK_EX) on <lock_dir>/.<SYM>.mutex around the NOOP check, the lock scan
    and the O_EXCL create (buys and risk actions). Not obtained within MUTEX_TIMEOUT_S -> LOCK_HELD (reason_code
    MUTEX_BUSY, exit 2, audited). The .mutex file is never a lock (it does not end in .lock).
  * Idempotent no-op (QA-02): a risk acquire with a fresh positions JSON (<120 s, --positions-json) whose position(s)
    for the symbol already carry the verdict's new_stop_loss (|live SL - target| <= SL_TOL, every matched position)
    for TRAIL_SL / MOVE_SL_BREAKEVEN, or (CLOSE) whose positions list is present and does not hold the symbol, returns
    exit 0 with result NO_OP_ALREADY_APPLIED, no_order true, NO lock file, and appends one PLACE_LOCK_NOOP audit row
    (verify_live_sl / verify_closed, expected_sl, action_run_id). The routine must NOT place / mark on that result.
    If the NOOP row cannot be written -> AUDIT_WRITE_FAILED (exit 4): never an un-audited no-op.
  * Any other exception inside acquire (missing / bad verdict or positions file, OSError, ...) (QA-05) ->
    PlaceLockError INTERNAL_ERROR (exit 4) + PLACE_LOCK_REFUSED row; never a lock, never exit 0. CLI argument
    errors -> BAD_ARGS (exit 4, audited) instead of argparse's exit 2.
  * Action row tie (QA-07): a risk acquire looks up the latest ACTION row (position_manager.py /
    momentum_qa/open_gap_check.py) of the same symbol + action in today's audit file and stores its run_id / ts_il
    as action_run_id / action_ts_il in the lock and in every PLACE_LOCK_MARK / PLACE_LOCK_NOOP / PLACE_LOCK_REFUSED
    row; feedback_daily ties the ACK to the ACTION row through it.
2026-10-30c (QA Bot FAIL 2 on 30b, qa-review-staged-20261030b.json QA30B-01 / QA30B-03):
  * CLOSE reads (QA30B-01): every risk acquire with --action CLOSE and a positions JSON first runs keys_read_check():
    the read must be a standard Momentum keys get-my-positions-and-orders read: a JSON object, no error body,
    statusCode == 200 (int, present), account == "real" (present), no non-empty mirrors / copiedTraders, a
    direct.positions list, no other top-level positions list, and EVERY item resolvable (int positionId + int
    instrumentId in market.instrumentId or instrumentId). Anything else -> POSITIONS_UNTRUSTED (exit 4, audited,
    reason_code READ_NOT_OBJECT / READ_ERROR / READ_NOT_200 / READ_NOT_REAL_ACCOUNT / READ_MIRROR_SHAPE /
    READ_SCHEMA_UNKNOWN / READ_ITEM_UNRESOLVED), never NO_OP, never a lock.
    A CLOSE NO_OP_ALREADY_APPLIED then also needs: (a) today's ACTION row for the symbol + CLOSE (else
    POSITIONS_UNTRUSTED / NOOP_NO_ACTION_ROW); (b) the symbol, its instrumentId and the ACTION row's
    details.positionId all absent from the read, and every item named (market.symbol, else the local id map;
    an unnamed item -> POSITIONS_UNTRUSTED / READ_ITEM_UNRESOLVED); (c) book fingerprint: if the ACTION row's run listed other
    positions (rows of the same run_id: positionIds / symbols), at least one of them is in the read, else
    POSITIONS_UNTRUSTED / READ_OTHER_BOOK (another account's book). An SL no-op needs a read that passes
    keys_read_check too; an SL acquire with any other read simply gets no no-op (ACQUIRED, the edit is harmless).
  * --action (QA30B-03): the verdict must hold a row with the explicit symbol, action == --action (a risk action)
    and a QA verdict PASS (row qa.verdict, else qa_verdict, else verdict; qa.ok false = FAIL; none = refuse).
    A HOLD / SKIP row, a FAIL row, a row without a QA verdict or no row for the symbol -> BAD_INPUT reason_code
    ACTION_VERDICT_MISMATCH (exit 4, audited). The verdict bytes are read once (sha and rows from the same bytes).
    Without --action: routine callers (eod-* and open_gap_check) are refused (BAD_INPUT reason_code ACTION_REQUIRED);
    a non-routine caller gets the action inferred only from a single QA-PASS risk row; a verdict that has rows for
    the symbol but no single PASS risk row is refused; a verdict without any row for the symbol and without a
    symbol-less risk row stays the pre-2026-10-30a legacy UNKNOWN lock (non-routine callers only).
2026-10-30d (QA Bot FAIL 3 on 30c, qa-review-staged-20261030c.json QA30C-01 / 04 / 05; Ofer t287s1451):
  * --action is REQUIRED on every --allow-held acquire, for every caller (QA ruling 2): no inference, the untyped
    UNKNOWN path is retired (BAD_INPUT reason_code ACTION_REQUIRED, audited).
  * Verdict authorisation (QA30C-04): a row is PASS only if EVERY verdict field it carries (qa.verdict, a string qa,
    qa_verdict, verdict) is PASS, qa.ok is not false, a non-dict non-string qa is FAIL, authorize_place is not
    false. Any other same-symbol same-action row that is not PASS (or a second PASS row with a different
    new_stop_loss) -> ACTION_VERDICT_CONFLICT. A wrapper object ({"rows": [...]} etc.) that carries a verdict field
    or authorize_place must itself be PASS -> else ACTION_VERDICT_MISMATCH / VERDICT_TOP_LEVEL_NOT_PASS.
    Routine callers = any caller starting with "eod" or containing "gap" (after lower-case, '-' -> '_').
  * Open-gap close verdict (QA ruling 1): a caller containing "gap", or a verdict with schema
    momentum.open_gap_close_qa.v1, needs EXACTLY one JSON object
    {"schema": "momentum.open_gap_close_qa.v1", "symbol", "positionId", "action": "CLOSE", "verdict": "PASS",
     "open_gap_run_id"} (optional informational keys: reviewer, reviewed_at_il, note, reason, qa_ref; nothing else),
    symbol == --symbol, --action CLOSE, open_gap_run_id == --run-id, and today's open_gap_check ACTION CLOSE row of
    that run for the symbol with details.positionId == positionId. Else BAD_INPUT reason_code OPEN_GAP_VERDICT_SCHEMA.
  * CLOSE no-op (QA30C-01, QA ruling 3): positive book identity by positionId only. The CLOSE ACTION row must carry
    the target positionId(s) (details.positionId / details.positionIds; position_manager rows carry them from 30d),
    else NOOP_NO_TARGET_POSITION_ID. An empty direct.positions read, or a run that listed no other positionId
    (single-position book), -> POSITIONS_UNTRUSTED READ_EMPTY_BOOK_NEEDS_SIGNOFF (no NO_OP, no lock, audited; QA Bot
    confirms the close from trade history and tells Ofer). Otherwise at least max(1, ceil(n/2)) of the run's n other
    positionIds must be in the read, else READ_OTHER_BOOK. Symbols are no longer part of the fingerprint.
  * keys read (QA30C-05): under "direct" only positions / orders / positionCount may be lists / objects (any other
    list or object -> READ_SCHEMA_UNKNOWN); positionCount, when present, must equal len(direct.positions). An item
    counts as held when market.symbol, the mapped instrumentId, the local id map (cache_symbol_for_id) or the target
    positionId matches.
2026-10-30e (QA Bot FAIL 4 on 30d, qa-review-staged-20261030d.json QA30D-01..06 + open-point rulings 1-4):
  * NOOP receipt (QA30D-01): every NO_OP_ALREADY_APPLIED writes, O_EXCL, a receipt file
    <lock_dir>/<sha12>-<SYM>~<ACTION>.<noop_id>.noop plus a byte copy of the positions read it used
    (<...>.<noop_id>.read.json). The PLACE_LOCK_NOOP row names noop_id, receipt_path, receipt_sha256, read_path and
    positions_sha256; feedback_daily re-verifies the receipt and re-runs the no-op check on the saved read. A NOOP
    row without a matching receipt (hand-written, copied, edited) never scores APPLIED.
  * action_run_book (QA30D-01b): the book fingerprint counts only ACTION rows of the protective scripts
    (position_manager.py, momentum_qa/open_gap_check.py) and of the SAME script as the target ACTION row.
  * SL no-op (open-point ruling 4): the matched lots must include every target positionId of the ACTION row (PM rows
    carry them); an SL ACTION row without positionId never no-ops (the edit proceeds: ACQUIRED).
  * mark (QA30D-02): a marked RISK lock (allow_held; buy locks unchanged) is terminal: FAILED / EXPIRED / PLACED can never be re-marked (BAD_INPUT
    reason_code MARK_TERMINAL; a FAILED close needs a new acquire with --retry-after-fail and a fresh verdict). Each
    mark writes a mark_id into the lock and the PLACE_LOCK_MARK row; feedback counts a lock's MARK once.
  * QA30D-03: a CLOSE whose ACTION row is an open_gap_check row needs the v1 open-gap verdict whatever the caller.
  * QA30D-07 (INFO): a risk verdict with a repeated JSON key -> BAD_INPUT VERDICT_DUPLICATE_KEYS; authorize_place
    that is not the bool true (false, "false", 0 ...) authorises nothing; a wrapper "status" that is not PASS / OK
    makes the wrapper non-PASS (VERDICT_TOP_LEVEL_NOT_PASS). Lowercase "pass" stays accepted (unchanged).
Exit codes: 0 OK (result ACQUIRED or NO_OP_ALREADY_APPLIED), 2 LOCK_HELD, 3 ALREADY_HELD,
            4 RETRY_NOT_ALLOWED / POSITIONS_STALE / POSITIONS_UNTRUSTED / BAD_INPUT / BAD_ARGS / INTERNAL_ERROR /
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
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from momentum_qa import market_clock as MC
from momentum_qa.instrument_map import base_symbol, id_symbol_mismatch, instrument_id as mapped_instrument_id, is_held
from momentum_qa.instrument_map import cache_symbol_for_id

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
RISK_ACTIONS = ("CLOSE", "MOVE_SL_BREAKEVEN", "TRAIL_SL")  # PM / open-gap protective actions (2026-10-30a)
UNKNOWN_ACTION = "UNKNOWN"
BUY_ACTION = "BUY"
INFLIGHT_TTL_S = 900  # an un-marked ACQUIRED / unreadable risk lock of ANOTHER verdict blocks only this long
ACTION_SEP = "~"      # <sha12>-<SYM>~<ACTION>.lock
SYMBOL_RE = re.compile(r"^[A-Z0-9.]{1,10}$")  # 2026-10-30b QA-10 (Ofer's rule; stricter than QA's suggestion)
SL_TOL = 0.01          # live SL == target within 1 cent -> NO_OP_ALREADY_APPLIED (same tolerance as feedback_daily)
MUTEX_TIMEOUT_S = 10.0  # per-symbol flock wait (QA-03)
PROTECTIVE_SCRIPTS = ("position_manager.py", "momentum_qa/open_gap_check.py")
SL_ACTIONS = ("MOVE_SL_BREAKEVEN", "TRAIL_SL")
LOCK_SCHEME = "2026-10-30e"
RISK_ROUTINE_CALLERS = ("open_gap_check",)  # + every eod* / *gap* caller (is_routine_caller, 2026-10-30d)
OPEN_GAP_VERDICT_SCHEMA = "momentum.open_gap_close_qa.v1"  # QA ruling 1 (2026-10-30d)
OPEN_GAP_VERDICT_KEYS = ("schema", "symbol", "positionId", "action", "verdict", "open_gap_run_id")
OPEN_GAP_VERDICT_INFO_KEYS = ("reviewer", "reviewed_at_il", "note", "reason", "qa_ref")
KEYS_DIRECT_ALLOWED = ("positions", "orders", "positionCount")
NOOP_RECEIPT_SUFFIX = ".noop"     # 2026-10-30e QA30D-01: <sha12>-<SYM>~<ACTION>.<noop_id>.noop
NOOP_READ_SUFFIX = ".read.json"   # byte copy of the positions read the no-op was decided on
OPEN_GAP_SCRIPT = "momentum_qa/open_gap_check.py"  # QA30C-05: the only containers under "direct"


class PlaceLockError(Exception):
    def __init__(self, code: str, exit_code: int, msg: str, lock_path: str | None = None,
                 reason_code: str | None = None):
        super().__init__(f"{code}: {msg}")
        self.code, self.exit_code, self.msg, self.lock_path = code, exit_code, msg, lock_path
        self.reason_code = reason_code


def validate_symbol(symbol) -> str:
    """QA-10: stripped upper-case symbol matching ^[A-Z0-9.]{1,10}$, no '..', no leading/trailing '.'."""
    s = str(symbol if symbol is not None else "").strip().upper()
    if not SYMBOL_RE.match(s) or ".." in s or s.startswith(".") or s.endswith("."):
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                             f"bad --symbol {str(symbol)[:40]!r}: must match ^[A-Z0-9.]{{1,10}}$ (no '..', '~', '/')",
                             reason_code="BAD_SYMBOL")
    return s


@contextlib.contextmanager
def _symbol_mutex(lock_dir: Path, sym: str, timeout_s: float | None = None):
    """QA-03: serialise check + create per symbol across processes (flock on <lock_dir>/.<SYM>.mutex)."""
    p = Path(lock_dir) / f".{sym}.mutex"
    fd = os.open(str(p), os.O_CREAT | os.O_RDWR, 0o644)
    deadline = time.monotonic() + (MUTEX_TIMEOUT_S if timeout_s is None else timeout_s)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD,
                                         f"{sym}: another place_lock run holds {p.name} (> {MUTEX_TIMEOUT_S:.0f}s)",
                                         str(p), reason_code="MUTEX_BUSY")
                time.sleep(0.02)
        yield p
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


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


POSITION_LIST_KEYS = ("positions", "openpositions", "clientportfolio_positions", "pm_positions")
SL_KEYS = ("stopLossRate", "stop_loss", "stopLoss", "sl")


def position_entries(positions_obj) -> tuple[bool, list[dict]]:
    """(a positions list was found, [{symbol, instrumentId, positionId, sl, has_sl}]) from a keys
    get-my-positions-and-orders JSON or a precheck summary (pm_positions). Read-only."""
    found = False
    out: list[dict] = []

    def walk(o, inpos=False):
        nonlocal found
        if isinstance(o, dict):
            if inpos and any(k in o for k in ("positionId", "positionID", "instrumentId", "symbol", "market")):
                mk = o.get("market") if isinstance(o.get("market"), dict) else {}
                iid = o.get("instrumentId", mk.get("instrumentId"))
                try:
                    iid = int(iid) if iid not in (None, "") else None
                except (TypeError, ValueError):
                    iid = None
                raw = next((o.get(k) or mk.get(k) for k in ("symbol", "symbolFull", "instrumentSymbol", "ticker")
                            if isinstance(o.get(k) or mk.get(k), str) and (o.get(k) or mk.get(k)).strip()), None)
                sl_key = next((k for k in SL_KEYS if k in o), None)
                out.append({"symbol": base_symbol(raw, iid) if raw else None, "instrumentId": iid,
                            "positionId": o.get("positionId", o.get("positionID")),
                            "sl": o.get(sl_key) if sl_key else None, "has_sl": sl_key is not None})
                return
            for k, v in o.items():
                kl = k.lower()
                if kl in POSITION_LIST_KEYS and isinstance(v, list):
                    found = True
                walk(v, inpos or kl in POSITION_LIST_KEYS)
        elif isinstance(o, list):
            for v in o:
                walk(v, inpos)
    walk(positions_obj)
    return found, out


def _int_id(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(f):  # 2026-10-30e QA30D-04: inf / nan / 1e400 are no positionId (never a crash)
        return None
    return int(f) if f == int(f) else None


KEYS_FOREIGN_LISTS = ("positions", "openPositions", "clientPortfolio", "pm_positions", "aggregatedPositions")


def keys_read_check(obj) -> dict:
    """QA30B-01: is this a standard Momentum keys get-my-positions-and-orders read we can trust for a no-op?
    -> {"ok", "code", "reason", "positions": [{positionId, instrumentId, symbol, sl, has_sl}]}. Read-only."""
    def bad(code, why):
        return {"ok": False, "code": code, "reason": why, "positions": []}
    if not isinstance(obj, dict):
        return bad("READ_NOT_OBJECT", f"positions JSON is a {type(obj).__name__}, not a keys read object")
    if obj.get("error") or obj.get("errors"):
        return bad("READ_ERROR", f"error body: {str(obj.get('error') or obj.get('errors'))[:160]}")
    sc = obj.get("statusCode")
    if isinstance(sc, bool) or sc != 200:
        return bad("READ_NOT_200", f"statusCode={sc!r} (a standard keys read has statusCode 200)")
    if obj.get("account") != "real":
        return bad("READ_NOT_REAL_ACCOUNT", f"account={obj.get('account')!r} (must be 'real')")
    if obj.get("mirrors") or obj.get("copiedTraders"):
        return bad("READ_MIRROR_SHAPE", "mirrors / copiedTraders present: parent / copy shape, not the Momentum keys read")
    if "mirrors" in obj and not isinstance(obj.get("mirrors"), list):
        return bad("READ_SCHEMA_UNKNOWN", "mirrors is not a list")
    d = obj.get("direct")
    if not isinstance(d, dict) or not isinstance(d.get("positions"), list):
        return bad("READ_SCHEMA_UNKNOWN", "no direct.positions list")
    foreign = [k for k in KEYS_FOREIGN_LISTS if k in obj]
    if foreign:
        return bad("READ_SCHEMA_UNKNOWN", f"unexpected top-level position list(s) {foreign}")
    extra = sorted(k for k, v in d.items() if k not in KEYS_DIRECT_ALLOWED and isinstance(v, (list, dict)))
    if extra:  # 2026-10-30d QA30C-05: no other list / object under direct
        return bad("READ_SCHEMA_UNKNOWN", f"unexpected list / object under direct: {extra}")
    if "positionCount" in d:
        pc = d.get("positionCount")
        if isinstance(pc, bool) or not isinstance(pc, int) or pc != len(d["positions"]):
            return bad("READ_SCHEMA_UNKNOWN", f"direct.positionCount={pc!r} != len(direct.positions)="
                                              f"{len(d['positions'])}")
    items = []
    for i, p in enumerate(d["positions"]):
        if not isinstance(p, dict):
            return bad("READ_ITEM_UNRESOLVED", f"direct.positions[{i}] is not an object")
        mk = p.get("market") if isinstance(p.get("market"), dict) else {}
        pid = _int_id(p.get("positionId"))
        iid = _int_id(mk.get("instrumentId", p.get("instrumentId")))
        if pid is None or iid is None:
            return bad("READ_ITEM_UNRESOLVED", f"direct.positions[{i}] has no int positionId + instrumentId "
                                               f"(keys {sorted(p)[:8]})")
        raw = mk.get("symbol") if isinstance(mk.get("symbol"), str) and mk.get("symbol").strip() else p.get("symbol")
        sym = base_symbol(raw, iid) if isinstance(raw, str) and raw.strip() else None
        try:  # 2026-10-30d QA30C-05: the local id map is a second, independent name for the item
            id_sym = cache_symbol_for_id(iid)
        except Exception:  # noqa: BLE001 - an unknown id stays unresolved
            id_sym = None
        if sym is None:  # keys reads carry no symbol: resolve the id from the local map (read-only)
            sym = id_sym
        sl_key = next((k for k in SL_KEYS if k in p), None)
        items.append({"positionId": pid, "instrumentId": iid, "symbol": sym, "id_symbol": id_sym,
                      "sl": p.get(sl_key) if sl_key else None, "has_sl": sl_key is not None})
    return {"ok": True, "code": "OK", "reason": "standard keys read (statusCode 200, account real, direct.positions)",
            "positions": items}


def _row_position_ids(r: dict) -> set[int]:
    """positionId(s) an ACTION row names: details.positionId, details.positionIds[], top-level positionId(s)."""
    out: set[int] = set()
    d = r.get("details") if isinstance(r.get("details"), dict) else {}
    for src in (d, r):
        pid = _int_id(src.get("positionId"))
        if pid is not None:
            out.add(pid)
        lst = src.get("positionIds")
        if isinstance(lst, list):
            out |= {x for x in (_int_id(v) for v in lst) if x is not None}
    return out


def action_run_book(day: str, arow: dict | None, audit_dir=None) -> dict:
    """QA30C-01 book fingerprint, by positionId only: the target positionIds (rows of the ACTION row's symbol in its
    run, plus the ACTION row itself) and the OTHER positionIds of every ACTION row (any action) of that run."""
    out = {"run_id": None, "positionIds": set(), "target_positionIds": set()}
    if not arow or not arow.get("run_id"):
        return out
    out["run_id"] = arow.get("run_id")
    try:
        from momentum_qa import audit as AU
        tsym = AU.base_symbol_of(arow.get("symbol"))
        d = Path(audit_dir or AU.AUDIT_DIR)
        days = {day, datetime.now(tz=MC.IL).date().isoformat()}
        for dd in sorted(days):
            for r in AU.read_rows(d / f"{dd}.jsonl"):
                if r.get("event") != "ACTION" or r.get("run_id") != arow.get("run_id"):
                    continue
                sc = str(r.get("script") or "")  # 2026-10-30e QA30D-01b: protective rows of the target's script only
                if sc not in PROTECTIVE_SCRIPTS or sc != str(arow.get("script") or ""):
                    continue
                ids = _row_position_ids(r)
                if AU.base_symbol_of(r.get("symbol")) == tsym:
                    out["target_positionIds"] |= ids
                else:
                    out["positionIds"] |= ids
    except Exception:
        pass
    out["target_positionIds"] |= _row_position_ids(arow)
    out["positionIds"] -= out["target_positionIds"]
    return out


def _untrusted(sym, why, code):
    return PlaceLockError("POSITIONS_UNTRUSTED", EXIT_RETRY_NOT_ALLOWED, f"{sym} CLOSE no-op refused: {why}",
                          reason_code=code)


def close_noop_check(kr: dict, sym: str, instrument_id, arow: dict | None, book: dict) -> dict | None:
    """QA30B-01 / QA30C-01: CLOSE no-op evidence from a read that passed keys_read_check, else None (= held: the
    normal ACQUIRED path). Raises POSITIONS_UNTRUSTED whenever 'not held' cannot be tied to THIS book by positionId."""
    iid = instrument_id if instrument_id is not None else mapped_instrument_id(sym)
    tp = set(book.get("target_positionIds") or ())
    held = [e for e in kr["positions"] if e["symbol"] == sym or e.get("id_symbol") == sym
            or (iid is not None and e["instrumentId"] == iid) or e["positionId"] in tp]
    if held:
        return None
    unres = [e["positionId"] for e in kr["positions"] if not e["symbol"]]
    if unres:  # an item we cannot name could be the target: never prove 'not held' around it
        raise _untrusted(sym, f"{len(unres)} position(s) in the read resolve to no symbol (positionIds {unres[:5]})",
                         "READ_ITEM_UNRESOLVED")
    if arow is None:
        raise _untrusted(sym, f"no ACTION row for {sym} CLOSE today to tie the no-op to", "NOOP_NO_ACTION_ROW")
    if not tp:
        raise _untrusted(sym, f"the CLOSE ACTION row of run {book.get('run_id')} names no positionId",
                         "NOOP_NO_TARGET_POSITION_ID")
    if not kr["positions"]:
        raise _untrusted(sym, "the read's direct.positions is empty: an empty book needs QA Bot sign-off "
                              "(trade-history check) and Ofer is told", "READ_EMPTY_BOOK_NEEDS_SIGNOFF")
    others = set(book.get("positionIds") or ())
    if not others:
        raise _untrusted(sym, f"run {book.get('run_id')} listed no other positionId (single-position book): "
                              "the read cannot be tied to this account; needs QA Bot sign-off",
                         "READ_EMPTY_BOOK_NEEDS_SIGNOFF")
    read_p = {e["positionId"] for e in kr["positions"]}
    need = max(1, -(-len(others) // 2))
    matched = len(others & read_p)
    if matched < need:
        raise _untrusted(sym, f"only {matched} of the {len(others)} other positionId(s) of run {book.get('run_id')} "
                              f"are in the read (need {need}): another account's book?", "READ_OTHER_BOOK")
    return {"verify_closed": True, "positions_seen": len(kr["positions"]), "read_check": kr["code"],
            "book_fingerprint": {"run_id": book.get("run_id"), "by": "positionId", "other_positions": len(others),
                                 "matched": matched, "required": need},
            "target_positionIds": sorted(tp)}


def noop_check(positions_obj, sym: str, action: str, target_sl, instrument_id=None, target_pids=None) -> dict | None:
    """QA-02: evidence that the protective action is already applied on the live book, else None.
    SL actions: every matched position has a numeric SL within SL_TOL of target_sl (target required).
    CLOSE: a positions list is present and no entry matches the symbol / instrumentId.
    2026-10-30c: only from a read that passes keys_read_check (else None = no no-op); a CLOSE acquire with
    positions goes through keys_read_check + close_noop_check in _acquire first (refusal, never NO_OP)."""
    if positions_obj is None or action not in RISK_ACTIONS:
        return None
    kr = keys_read_check(positions_obj)  # 2026-10-30c QA30B-01: a no-op only from a standard keys read
    if not kr["ok"]:
        return None
    found, entries = position_entries(positions_obj)
    iid = instrument_id if instrument_id is not None else mapped_instrument_id(sym)
    mine = [e for e in entries if e["symbol"] == sym or (iid is not None and e["instrumentId"] == iid)]
    if action == "CLOSE":
        h_syms, h_ids = held_index(positions_obj)
        h_syms |= held_symbols(positions_obj)
        if found and not mine and not is_held(sym, h_syms, h_ids, iid):
            return {"verify_closed": True, "positions_seen": len(entries)}
        return None
    try:
        tgt = float(target_sl)
    except (TypeError, ValueError):
        return None
    if not mine:
        return None
    if target_pids is not None:  # 2026-10-30e open-point ruling 4: the matched lots include the ACTION row's lots
        tp = {int(x) for x in target_pids}
        if not tp or not tp <= {e["positionId"] for e in mine}:
            return None
    sls = []
    for e in mine:
        try:
            sls.append(float(e["sl"]))
        except (TypeError, ValueError):
            return None
    if all(abs(v - tgt) <= SL_TOL + 1e-9 for v in sls):
        worst = max(sls, key=lambda v: abs(v - tgt))
        return {"verify_live_sl": worst, "expected_sl": tgt, "live_sls": sls, "read_check": kr["code"],
                "positionIds": [e["positionId"] for e in mine]}
    return None


def find_action_row(day: str, sym: str, action: str, audit_dir=None) -> dict | None:
    """Latest protective ACTION row (PM / open-gap) for sym + action in <audit_dir>/<day>.jsonl (and the real
    IL-today file). Used to tie ACK / NOOP / MARK rows to the ACTION row (QA-07). Read-only, never raises."""
    try:
        from momentum_qa import audit as AU
        d = Path(audit_dir or AU.AUDIT_DIR)
        days = {day, datetime.now(tz=MC.IL).date().isoformat()}
        best = None
        for dd in sorted(days):
            for r in AU.read_rows(d / f"{dd}.jsonl"):
                if (r.get("event") == "ACTION" and str(r.get("script") or "") in PROTECTIVE_SCRIPTS
                        and AU.base_symbol_of(r.get("symbol")) == sym
                        and str(r.get("action") or "").strip().upper() == action):
                    if best is None or str(r.get("ts_il") or "") >= str(best.get("ts_il") or ""):
                        best = r
        return best
    except Exception:
        return None


def _guard_now() -> datetime:
    """Real clock only (D-M1). No env/config override; tests pass now= or monkeypatch this function."""
    return datetime.now(tz=MC.IL)


def _caller_norm(caller) -> str:
    return str(caller or "").strip().lower().replace("-", "_")


def is_open_gap_caller(caller) -> bool:
    """2026-10-30d QA30C-04: any spelling of the open-gap routine (open_gap_check, open-gap-check, OPEN_GAP...)."""
    return "gap" in _caller_norm(caller)


def is_routine_caller(caller) -> bool:
    """eod-* routines (2026-10-24c) and, from 2026-10-30d, any caller starting with 'eod' or containing 'gap'."""
    c = _caller_norm(caller)
    return isinstance(caller, str) and (c.startswith("eod") or "gap" in c)


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


def lock_path_for(sha: str, symbol: str, lock_dir: Path | None = None, action: str | None = None) -> Path:
    """<sha12>-<SYM>.lock (buys, UNKNOWN risk action, legacy) or <sha12>-<SYM>~<ACTION>.lock (known risk action)."""
    a = norm_action(action)
    suffix = f"{ACTION_SEP}{a}" if a not in (None, UNKNOWN_ACTION, BUY_ACTION) else ""
    return Path(lock_dir or LOCK_DIR) / f"{sha[:12]}-{_norm(symbol)}{suffix}.lock"


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"status": "UNREADABLE"}


def _same_symbol_locks(symbol: str, lock_dir: Path) -> list[tuple[Path, dict]]:
    sym = _norm(symbol)
    paths = set(lock_dir.glob(f"*-{sym}.lock")) | set(lock_dir.glob(f"*-{sym}{ACTION_SEP}*.lock"))
    return [(p, _read(p)) for p in sorted(paths) if _lock_name_parts(p)[1] == sym]


def _lock_name_parts(p: Path) -> tuple[str, str, str | None]:
    """'e611cd183fe7-XOM.lock' -> ('e611cd183fe7', 'XOM', None); 'abc-XOM~TRAIL_SL.lock' -> (.., 'XOM', 'TRAIL_SL')."""
    stem = p.name[:-len(".lock")] if p.name.endswith(".lock") else p.name
    sha, _, rest = stem.partition("-")
    sym, sep, act = rest.partition(ACTION_SEP)
    return sha, sym, (act if sep else None)


def norm_action(action) -> str | None:
    """Upper-case action token or None. Raises BAD_INPUT for a malformed token."""
    if action is None:
        return None
    a = str(action).strip().upper()
    if not a:
        return None
    if not (a[0].isalpha() and len(a) <= 40 and all(ch.isalnum() or ch == "_" for ch in a)):
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, f"bad --action {action!r}")
    return a


def _verdict_rows(obj) -> list[dict]:
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    if isinstance(obj, dict):
        for k in ("rows", "actions", "decisions", "positions", "pm_rows"):
            if isinstance(obj.get(k), list):
                return [r for r in obj[k] if isinstance(r, dict)]
        return [obj]
    return []


def verdict_risk_actions(verdict_path, symbol) -> dict[str, dict]:
    """{risk action: first row} for SYMBOL in a PM / QA verdict file ({} if none / unreadable). Only RISK_ACTIONS."""
    try:
        obj = json.loads(Path(verdict_path).read_text())
    except Exception:
        return {}
    sym = _norm(symbol)
    found: dict[str, dict] = {}
    for r in _verdict_rows(obj):
        rs = r.get("symbol")
        if rs is not None and _norm(str(rs)) != sym:
            continue
        a = r.get("action")
        try:
            a = norm_action(a)
        except PlaceLockError:
            continue
        if a in RISK_ACTIONS:
            found.setdefault(a, r)
    return found


VERDICT_FIELDS = ("qa_verdict", "verdict")


def _verdict_values(r: dict) -> list[str] | None:
    """Every verdict value a dict carries, upper-cased; None = it carries a FAIL by construction."""
    vals: list[str] = []
    if "qa" in r and r.get("qa") is not None:
        q = r.get("qa")
        if isinstance(q, dict):
            if q.get("ok") is False:
                return None
            if q.get("verdict") is not None:
                if isinstance(q.get("verdict"), (dict, list)):
                    return None
                vals.append(str(q.get("verdict")).strip().upper())
        elif isinstance(q, str):
            vals.append(q.strip().upper())
        else:
            return None
    for k in VERDICT_FIELDS:
        if r.get(k) is not None:
            if isinstance(r.get(k), (dict, list)):
                return None
            vals.append(str(r.get(k)).strip().upper())
    if r.get("authorize_place") is not None and r.get("authorize_place") is not True:
        return None  # 2026-10-30e QA30D-07: false or any non-bool ("false", 0, "yes") authorises nothing
    return vals


def row_qa_verdict(r: dict) -> str | None:
    """QA30B-03 / QA30C-04: PASS only if every verdict field of the row is PASS (qa.verdict, a string qa, qa_verdict,
    verdict), qa.ok is not false and authorize_place is not false; 'FAIL' (or the first non-PASS value) otherwise;
    None when the row carries no verdict at all."""
    vals = _verdict_values(r)
    if vals is None:
        return "FAIL"
    if not vals:
        return None
    bad = [v for v in vals if v != "PASS"]
    return bad[0] if bad else "PASS"


def verdict_top_level(obj) -> str | None:
    """QA30C-04: the wrapper's own verdict when rows sit under a list key ({"verdict": "FAIL", "rows": [...]});
    None = no wrapper or a wrapper without verdict fields."""
    if not isinstance(obj, dict):
        return None
    if not any(isinstance(obj.get(k), list) for k in ("rows", "actions", "decisions", "positions", "pm_rows")):
        return None
    w = {k: v for k, v in obj.items() if k in ("qa", "authorize_place") + VERDICT_FIELDS}
    st = obj.get("status")  # 2026-10-30e QA30D-07: a wrapper status that is not PASS / OK is a non-PASS wrapper
    if st is not None and (not isinstance(st, str) or st.strip().upper() not in ("PASS", "OK")):
        return "FAIL" if not isinstance(st, str) else (st.strip().upper() or "FAIL")
    if not w:
        return None
    return row_qa_verdict(w) or "FAIL"


def _no_duplicate_keys(pairs):
    """2026-10-30e QA30D-07: json object_pairs_hook - a verdict object with a repeated key is refused."""
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise DuplicateKeyError(k)
        seen.add(k)
    return dict(pairs)


class DuplicateKeyError(ValueError):
    pass


def verdict_authorisation(obj, sym: str) -> dict:
    """QA30B-03 / QA30C-04: {"rows": rows with the explicit symbol, "passing": {risk action: row with QA PASS},
    "conflicts": {risk action: why}, "symbolless_risk": {...}, "top_level": wrapper verdict, "desc": "..."}."""
    rows, passing, symless, conflicts, desc = [], {}, {}, {}, []
    by_act: dict[str, list] = {}
    for r in _verdict_rows(obj):
        a = r.get("action")
        try:
            a = norm_action(a) if isinstance(a, str) else None
        except PlaceLockError:
            a = None
        rs = r.get("symbol")
        if rs is None:
            if a in RISK_ACTIONS:
                symless.setdefault(a, r)
            continue
        try:
            if _norm(str(rs)) != sym:
                continue
        except Exception:
            continue
        rows.append(r)
        qv = row_qa_verdict(r)
        desc.append(f"{a or r.get('action')!s}/{qv or 'NO_QA'}")
        if a in RISK_ACTIONS:
            by_act.setdefault(a, []).append((r, qv))
    for a, lst in by_act.items():
        verdicts = [qv for _, qv in lst]
        if all(v == "PASS" for v in verdicts):
            stops = {json.dumps(r.get("new_stop_loss")) for r, _ in lst}
            if len(stops) > 1:
                conflicts[a] = f"{len(lst)} PASS rows with different new_stop_loss {sorted(stops)}"
            else:
                passing[a] = lst[0][0]
        elif "PASS" in verdicts:
            conflicts[a] = f"PASS and non-PASS rows for {sym} {a}: {verdicts}"
    return {"rows": rows, "passing": passing, "conflicts": conflicts, "symbolless_risk": symless,
            "top_level": verdict_top_level(obj), "desc": ", ".join(desc) or "no row"}


def _open_gap_action_row(day: str, sym: str, og_run_id: str, position_id: int, audit_dir=None) -> dict | None:
    """Today's open_gap_check ACTION CLOSE row of run og_run_id for sym naming position_id, or None. Read-only."""
    try:
        from momentum_qa import audit as AU
        d = Path(audit_dir or AU.AUDIT_DIR)
        best = None
        for dd in sorted({day, datetime.now(tz=MC.IL).date().isoformat()}):
            for r in AU.read_rows(d / f"{dd}.jsonl"):
                if (r.get("event") == "ACTION" and str(r.get("script") or "") == "momentum_qa/open_gap_check.py"
                        and r.get("run_id") == og_run_id and AU.base_symbol_of(r.get("symbol")) == sym
                        and str(r.get("action") or "").strip().upper() == "CLOSE"
                        and position_id in _row_position_ids(r)):
                    if best is None or str(r.get("ts_il") or "") >= str(best.get("ts_il") or ""):
                        best = r
        return best
    except Exception:
        return None


def validate_open_gap_verdict(obj, sym: str, action: str | None, run_id: str | None) -> dict:
    """QA ruling 1 (2026-10-30d): exactly one momentum.open_gap_close_qa.v1 object for this close. Raises BAD_INPUT
    reason_code OPEN_GAP_VERDICT_SCHEMA; returns {"positionId", "open_gap_run_id"}."""
    def bad(why):
        return PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, f"OPEN_GAP_VERDICT_SCHEMA: {why}",
                              reason_code="OPEN_GAP_VERDICT_SCHEMA")
    if not isinstance(obj, dict):
        raise bad(f"the open-gap close verdict must be ONE JSON object, got {type(obj).__name__}")
    if obj.get("schema") != OPEN_GAP_VERDICT_SCHEMA:
        raise bad(f"schema={obj.get('schema')!r}, need {OPEN_GAP_VERDICT_SCHEMA!r}")
    missing = [k for k in OPEN_GAP_VERDICT_KEYS if k not in obj]
    extra = sorted(k for k in obj if k not in OPEN_GAP_VERDICT_KEYS + OPEN_GAP_VERDICT_INFO_KEYS)
    if missing or extra:
        raise bad(f"missing keys {missing}, unexpected keys {extra}")
    bad_info = [k for k in OPEN_GAP_VERDICT_INFO_KEYS if k in obj and not isinstance(obj[k], (str, type(None)))]
    if bad_info:
        raise bad(f"informational keys must be strings: {bad_info}")
    if not isinstance(obj["symbol"], str) or _norm(obj["symbol"]) != sym:
        raise bad(f"symbol={obj['symbol']!r} is not --symbol {sym}")
    if obj["action"] != "CLOSE" or action != "CLOSE":
        raise bad(f"action={obj['action']!r} / --action {action}: an open-gap close verdict is CLOSE only")
    if obj["verdict"] != "PASS":
        raise bad(f"verdict={obj['verdict']!r} (must be exactly \"PASS\")")
    pid = obj["positionId"]
    if isinstance(pid, bool) or not isinstance(pid, int):
        raise bad(f"positionId={pid!r} is not an int")
    og = obj["open_gap_run_id"]
    if not isinstance(og, str) or not og.strip():
        raise bad("open_gap_run_id is empty")
    if not run_id or run_id != og:
        raise bad(f"open_gap_run_id {og!r} != --run-id {run_id!r}")
    return {"positionId": pid, "open_gap_run_id": og}


def verdict_action(verdict_path, symbol) -> tuple[str | None, dict | None]:
    """(risk action, row) for SYMBOL in a PM / QA verdict file, or (None, None). Only RISK_ACTIONS count
    (2026-10-30b: no CLOSE_* prefix); two different risk actions for one symbol -> None (ambiguous, pass --action)."""
    found = verdict_risk_actions(verdict_path, symbol)
    if len(found) == 1:
        a, row = next(iter(found.items()))
        return a, row
    return None, None


def lock_action(p: Path, d: dict) -> str:
    """Action recorded by a lock file (new or legacy). See the module docstring (legacy rule)."""
    try:
        a = norm_action(d.get("action"))
    except PlaceLockError:
        a = None
    if a:
        return a
    act_from_name = _lock_name_parts(p)[2]
    if act_from_name:
        return act_from_name.upper()
    if d.get("status") == "UNREADABLE":
        return UNKNOWN_ACTION
    if not d.get("allow_held"):
        return BUY_ACTION
    vp = d.get("verdict_path")
    if vp and Path(vp).exists():
        try:
            if sha256_file(vp) == d.get("verdict_sha256"):
                a, _ = verdict_action(vp, d.get("symbol") or _lock_name_parts(p)[1])
                if a:
                    return a
        except OSError:
            pass
    tok = str(d.get("note") or "").strip().split(" ")[0].upper()
    if tok in RISK_ACTIONS or (tok.startswith("CLOSE") and tok.replace("_", "").isalpha()):
        return tok
    return UNKNOWN_ACTION


def _il_day(ts) -> str | None:
    try:
        return _parse_ts(ts).astimezone(MC.IL).date().isoformat()
    except Exception:
        return None


def lock_day(p: Path, d: dict) -> str | None:
    """IL day of a lock: day_il (new locks, guard clock) else the IL date of ts, else the file mtime."""
    if d.get("day_il"):
        return str(d["day_il"])
    day = _il_day(d.get("ts")) if d.get("ts") else None
    if day:
        return day
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=MC.IL).date().isoformat()
    except OSError:
        return None


def lock_age_s(p: Path, d: dict) -> float | None:
    """Seconds since the lock was taken (real clock): ts, else file mtime."""
    try:
        if d.get("ts"):
            return (datetime.now(timezone.utc) - _parse_ts(d["ts"])).total_seconds()
        return datetime.now(timezone.utc).timestamp() - p.stat().st_mtime
    except Exception:
        return None


def _risk_lock_conflict(p: Path, d: dict, action: str, today: str, retry_after_fail: bool):
    """For a RISK acquire: (PlaceLockError | None, ignored-entry | None) for one lock of ANOTHER verdict."""
    st = d.get("status")
    o_act = lock_action(p, d)
    o_day = lock_day(p, d)
    age = lock_age_s(p, d)
    same_day = o_day == today
    same_act = action != UNKNOWN_ACTION and o_act == action
    info = {"lock": p.name, "status": st, "action": o_act, "day_il": o_day,
            "age_s": None if age is None else round(age)}
    if st in ("ACQUIRED", "UNREADABLE") and age is not None and 0 <= age < INFLIGHT_TTL_S:
        return PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD,
                              f"{d.get('symbol') or _lock_name_parts(p)[1]} has in-flight {st} lock {p.name} "
                              f"({o_act}, age {age:.0f}s < {INFLIGHT_TTL_S}s)", str(p)), None
    if st in ("ACQUIRED", "PLACED", "UNREADABLE") and same_day and o_act != BUY_ACTION and (
            same_act or action == UNKNOWN_ACTION):
        return PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD,
                              f"DUPLICATE_ACTION_SAME_DAY: {p.name} is {st} {o_act} on {o_day} "
                              f"(request {action}); same action never re-applies the same night", str(p),
                              reason_code="DUPLICATE_ACTION_SAME_DAY"), None
    if st in ("FAILED", "EXPIRED") and same_day and (same_act or action == UNKNOWN_ACTION) and not retry_after_fail:
        return PlaceLockError("RETRY_NOT_ALLOWED", EXIT_RETRY_NOT_ALLOWED,
                              f"{p.name} is {st} {o_act} today; pass --retry-after-fail with a fresh verdict", str(p)), None
    return None, info


def _audit_refusal(err: "PlaceLockError", ctx: dict, audit_dir) -> None:
    """QA Bot ruling 2 (2026-10-30a): one PLACE_LOCK_REFUSED row per refusal; never raises."""
    try:
        from momentum_qa.audit import append_row, build_record, new_run_id
        run_id = ctx.get("run_id") or new_run_id("placelock")
        row = {"event": "PLACE_LOCK_REFUSED", "result": "REFUSED", "code": err.code, "exit_code": err.exit_code,
               "reason_code": getattr(err, "reason_code", None),
               "reason": err.msg, "lock_path": err.lock_path or ctx.get("lock_path"),
               "action_run_id": ctx.get("action_run_id"), "action_ts_il": ctx.get("action_ts_il"),
               "symbol": ctx.get("symbol"), "action": ctx.get("action"), "action_source": ctx.get("action_source"),
               "caller": ctx.get("caller"), "caller_run_id": ctx.get("run_id"), "account": ctx.get("account"),
               "allow_held": ctx.get("allow_held"), "verdict_path": ctx.get("verdict_path"),
               "verdict_sha256": ctx.get("verdict_sha256"), "read_check": ctx.get("read_check"),
               "rationale": f"place_lock refused {ctx.get('symbol')} {ctx.get('action')}: {err.code} (exit {err.exit_code})"}
        append_row(build_record(run_id, "momentum_qa/place_lock.py", row), audit_dir)
    except Exception as e:  # the refusal stands either way
        print(f"place_lock: refusal audit row failed: {e}", file=sys.stderr)


def acquire(verdict_path, symbol, account: str = DEFAULT_ACCOUNT, *, caller: str = "unknown",
            positions=None, allow_held: bool = False, retry_after_fail: bool = False,
            lock_dir: Path | None = None, instrument_id: int | None = None, now: datetime | None = None,
            manual_request: str | None = None, audit_dir: Path | None = None,
            action: str | None = None, run_id: str | None = None) -> dict:
    """Atomically take the single-use lock for (verdict sha, symbol[, risk action]). Raises PlaceLockError.
    Automatic buys (allow_held=False, no manual_request) must pass buy_schedule_guard(now); manual buys
    (manual_request=<Ofer's message ref>) pass manual_buy_guard(now) instead (exit 6, no lock written).
    Every refusal writes one PLACE_LOCK_REFUSED audit row (2026-10-30a)."""
    ctx = {"symbol": str(symbol).strip().upper(), "action": None, "caller": caller, "run_id": run_id,
           "account": account, "allow_held": bool(allow_held), "verdict_path": str(verdict_path)}
    try:
        return _acquire(verdict_path, symbol, account, caller=caller, positions=positions, allow_held=allow_held,
                        retry_after_fail=retry_after_fail, lock_dir=lock_dir, instrument_id=instrument_id, now=now,
                        manual_request=manual_request, audit_dir=audit_dir, action=action, run_id=run_id, ctx=ctx)
    except PlaceLockError as e:
        _audit_refusal(e, ctx, audit_dir)
        raise
    except Exception as e:  # 2026-10-30b QA-05: fail closed AND audited, never a crash without a row
        err = PlaceLockError("INTERNAL_ERROR", EXIT_RETRY_NOT_ALLOWED, f"{type(e).__name__}: {e}"[:500],
                             ctx.get("lock_path"), reason_code=type(e).__name__)
        _audit_refusal(err, ctx, audit_dir)
        raise err from e


def _acquire(verdict_path, symbol, account: str = DEFAULT_ACCOUNT, *, caller: str = "unknown",
             positions=None, allow_held: bool = False, retry_after_fail: bool = False,
             lock_dir: Path | None = None, instrument_id: int | None = None, now: datetime | None = None,
             manual_request: str | None = None, audit_dir: Path | None = None,
             action: str | None = None, run_id: str | None = None, ctx: dict | None = None) -> dict:
    ctx = ctx if ctx is not None else {}
    sym = validate_symbol(symbol)  # QA-10: BAD_INPUT / BAD_SYMBOL before any path is built
    ctx["symbol"] = sym
    try:
        req_action = norm_action(action)  # BAD_INPUT (exit 4) on a malformed token
    except PlaceLockError as e:
        e.reason_code = "ACTION_NOT_ALLOWED"
        ctx["action"] = str(action)[:40]
        raise
    if allow_held and req_action not in (None, BUY_ACTION) and req_action not in RISK_ACTIONS:
        ctx["action"] = req_action
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                             f"--action {req_action} is not a protective action ({' | '.join(RISK_ACTIONS)})",
                             reason_code="ACTION_NOT_ALLOWED")
    if not allow_held and req_action not in (None, BUY_ACTION):
        ctx["action"] = req_action
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                             f"--action {req_action} is a risk action: pass --allow-held (a buy has no --action)")
    if allow_held and req_action == BUY_ACTION:
        ctx["action"] = req_action
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "--action BUY cannot be used with --allow-held")
    ctx["action"] = BUY_ACTION if not allow_held else (req_action or UNKNOWN_ACTION)
    ctx["action_source"] = "arg" if req_action else ("buy" if not allow_held else None)
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
    sym = _norm(sym)
    if not sym or not SYMBOL_RE.match(sym):
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, f"empty / bad base symbol {sym!r}",
                             reason_code="BAD_SYMBOL")
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
    vbytes = Path(verdict_path).read_bytes()  # 2026-10-30c: sha and rows from the same bytes
    sha = hashlib.sha256(vbytes).hexdigest()
    ctx["verdict_sha256"] = sha
    risk_row = None
    og = None
    if allow_held:  # 2026-10-30a: risk locks are scoped by action; 2026-10-30c QA30B-03: only a QA-PASS risk row
        try:
            vobj = json.loads(vbytes.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
        except DuplicateKeyError as e:  # 2026-10-30e QA30D-07
            raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                 f"ACTION_VERDICT_MISMATCH: the verdict file repeats the key {e.args[0]!r} "
                                 f"(duplicate JSON keys authorise nothing)", reason_code="VERDICT_DUPLICATE_KEYS")
        except Exception:
            vobj = None
        auth = verdict_authorisation(vobj, sym)
        act = req_action
        if act is None:  # 2026-10-30d QA ruling 2: --action on every --allow-held acquire; no inference, no UNKNOWN
            raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                 f"caller {caller!r} must pass --action (CLOSE | MOVE_SL_BREAKEVEN | TRAIL_SL) for a "
                                 f"risk acquire (--allow-held)", reason_code="ACTION_REQUIRED")
        if auth["top_level"] not in (None, "PASS"):
            raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                 f"ACTION_VERDICT_MISMATCH: the verdict's top-level verdict is {auth['top_level']} "
                                 f"(a wrapper that is not PASS authorises nothing)", reason_code="VERDICT_TOP_LEVEL_NOT_PASS")
        if act in auth["conflicts"]:
            raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                 f"ACTION_VERDICT_CONFLICT: {auth['conflicts'][act]}", reason_code="ACTION_VERDICT_CONFLICT")
        og = None
        if is_open_gap_caller(caller) or (isinstance(vobj, dict) and vobj.get("schema") == OPEN_GAP_VERDICT_SCHEMA):
            og = validate_open_gap_verdict(vobj, sym, act, run_id)
            ctx["open_gap_run_id"], ctx["open_gap_position_id"] = og["open_gap_run_id"], og["positionId"]
        if act is not None:
            if act not in auth["passing"]:
                raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                     f"ACTION_VERDICT_MISMATCH: --action {act} needs a QA-PASS {act} row for {sym} in "
                                     f"the verdict; its {sym} row(s): {auth['desc']}",
                                     reason_code="ACTION_VERDICT_MISMATCH")
            risk_row = auth["passing"][act]
        act = act or UNKNOWN_ACTION
        ctx["action"] = act
    else:
        act = BUY_ACTION
    lp = lock_path_for(sha, sym, lock_dir, act if allow_held else None)
    legacy_same_sha = lock_path_for(sha, sym, lock_dir)  # pre-2026-10-30a name of THIS verdict's lock
    ctx["lock_path"] = str(lp)
    today = (now or _guard_now())
    today = (today if today.tzinfo else today.replace(tzinfo=MC.IL)).astimezone(MC.IL).date().isoformat()
    arow = find_action_row(today, sym, act, audit_dir) if allow_held and act in RISK_ACTIONS else None
    if allow_held and og is not None:  # QA ruling 1: tie the verdict to the open_gap_check ACTION row + positionId
        arow = _open_gap_action_row(today, sym, og["open_gap_run_id"], og["positionId"], audit_dir)
        if arow is None:
            raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                                 f"OPEN_GAP_VERDICT_SCHEMA: no open_gap_check ACTION CLOSE row today for {sym} in run "
                                 f"{og['open_gap_run_id']} with positionId {og['positionId']}",
                                 reason_code="OPEN_GAP_VERDICT_SCHEMA")
    if (allow_held and og is None and act == "CLOSE" and arow is not None
            and str(arow.get("script") or "") == OPEN_GAP_SCRIPT):  # 2026-10-30e QA30D-03: whatever the caller
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                             f"OPEN_GAP_VERDICT_SCHEMA: today's {sym} CLOSE ACTION row is an open_gap_check row (run "
                             f"{arow.get('run_id')}): the verdict must be the {OPEN_GAP_VERDICT_SCHEMA} object, "
                             f"caller {caller!r}", reason_code="OPEN_GAP_VERDICT_SCHEMA")
    if arow is not None:
        ctx["action_run_id"], ctx["action_ts_il"] = arow.get("run_id"), arow.get("ts_il")

    # 1) live-positions check (buys only; PM trail/close pass allow_held)
    pos = _load_positions(positions)
    if pos is None and not allow_held:
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, "live positions JSON required (or --allow-held for PM actions)")
    # Freshness: any provided positions JSON must carry timestamp/asOf <120s (missing = refuse)
    if pos is not None:
        require_fresh_positions(pos)
    kread = None
    if allow_held and pos is not None and act == "CLOSE":  # 2026-10-30c QA30B-01: a CLOSE trusts only a keys read
        kread = keys_read_check(pos)
        ctx["read_check"] = kread["code"]
        if not kread["ok"]:
            raise PlaceLockError("POSITIONS_UNTRUSTED", EXIT_RETRY_NOT_ALLOWED,
                                 f"{sym} CLOSE: positions JSON is not a standard keys read: {kread['reason']}",
                                 reason_code=kread["code"])
    if pos is not None and not allow_held:
        h_syms, h_ids = held_index(pos)
        h_syms |= held_symbols(pos)
        iid = instrument_id if instrument_id is not None else mapped_instrument_id(sym)
        if is_held(sym, h_syms, h_ids, iid):
            raise PlaceLockError("ALREADY_HELD", EXIT_ALREADY_HELD, f"{sym} already held on {account}")

    with _symbol_mutex(lock_dir, sym):  # QA-03: NOOP check + scan + create are one critical section per symbol
        return _acquire_locked(verdict_path, sym, account, caller=caller, pos=pos, allow_held=allow_held,
                               retry_after_fail=retry_after_fail, lock_dir=lock_dir, instrument_id=instrument_id,
                               manual=manual, manual_ref=manual_ref, guard=guard, audit_dir=audit_dir, run_id=run_id,
                               ctx=ctx, sha=sha, act=act, risk_row=risk_row, lp=lp, legacy_same_sha=legacy_same_sha,
                               today=today, kread=kread, arow=arow)


NOOP_RECEIPT_KEYS = ("noop_id", "symbol", "action", "action_run_id", "verdict_sha256", "positions_sha256", "read_path",
                     "book_fingerprint", "target_positionIds", "expected_sl", "verify_live_sl", "verify_closed",
                     "read_check", "positionIds", "ts")


def noop_receipt_name(sha: str, sym: str, act: str, noop_id: str) -> str:
    return f"{sha[:12]}-{sym}{ACTION_SEP}{act}.{noop_id}{NOOP_RECEIPT_SUFFIX}"


def write_noop_receipt(lock_dir: Path, sha: str, sym: str, act: str, pos, row: dict) -> dict:
    """QA30D-01: write (O_EXCL) the positions read copy and the NOOP receipt; return the row fields naming them."""
    import uuid
    noop_id = uuid.uuid4().hex[:16]
    lock_dir = Path(lock_dir)
    base = noop_receipt_name(sha, sym, act, noop_id)[:-len(NOOP_RECEIPT_SUFFIX)]
    rp = lock_dir / f"{base}{NOOP_READ_SUFFIX}"
    raw = json.dumps(pos, sort_keys=True).encode("utf-8")
    fdr = os.open(str(rp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fdr, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    rec = {k: row.get(k) for k in NOOP_RECEIPT_KEYS}
    rec.update(noop_id=noop_id, symbol=sym, action=act, verdict_sha256=sha, ts=_now(), read_path=str(rp),
               positions_sha256=hashlib.sha256(raw).hexdigest(), lock_scheme=LOCK_SCHEME)
    cp = lock_dir / noop_receipt_name(sha, sym, act, noop_id)
    body = json.dumps(rec, indent=2, sort_keys=True).encode("utf-8")
    fdc = os.open(str(cp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fdc, "wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    return {"noop_id": noop_id, "receipt_path": str(cp), "receipt_sha256": hashlib.sha256(body).hexdigest(),
            "read_path": str(rp), "positions_sha256": rec["positions_sha256"], "receipt_ts": rec["ts"]}


def _acquire_locked(verdict_path, sym, account, *, caller, pos, allow_held, retry_after_fail, lock_dir, instrument_id,
                    manual, manual_ref, guard, audit_dir, run_id, ctx, sha, act, risk_row, lp, legacy_same_sha,
                    today, kread=None, arow=None) -> dict:
    # 1b) QA-02 idempotent no-op: the live book already shows the protective action
    if allow_held and pos is not None and act in RISK_ACTIONS:
        tgt = (risk_row or {}).get("new_stop_loss")
        if act == "CLOSE":  # 2026-10-30c QA30B-01: keys read + ACTION row + book fingerprint
            ev = close_noop_check(kread or keys_read_check(pos), sym, instrument_id, arow,
                                  action_run_book(today, arow, audit_dir))
        else:  # 2026-10-30e ruling 4: SL no-op only on the ACTION row's own lots
            ev = noop_check(pos, sym, act, tgt, instrument_id,
                            target_pids=sorted(action_run_book(today, arow, audit_dir)["target_positionIds"]))
        if ev is not None:
            row = {"event": "PLACE_LOCK_NOOP", "result": "NO_OP_ALREADY_APPLIED", "status": "NO_OP_ALREADY_APPLIED",
                   "symbol": sym, "action": act, "caller": caller, "caller_run_id": run_id, "account": account,
                   "action_run_id": ctx.get("action_run_id"), "action_ts_il": ctx.get("action_ts_il"),
                   "verdict_path": str(Path(verdict_path).resolve()), "verdict_sha256": sha, "day_il": today,
                   "expected_sl": ev.get("expected_sl"), "verify_live_sl": ev.get("verify_live_sl"),
                   "verify_closed": ev.get("verify_closed"), "live_sls": ev.get("live_sls"),
                   "positionIds": ev.get("positionIds"), "positions_timestamp": positions_timestamp(pos),
                   "read_check": ev.get("read_check") or ctx.get("read_check"),
                   "book_fingerprint": ev.get("book_fingerprint"),
                   "target_positionIds": ev.get("target_positionIds"),
                   "open_gap_run_id": ctx.get("open_gap_run_id"),
                   "rationale": (f"{sym} {act} already applied on the live book "
                                 + (f"(live SL {ev.get('verify_live_sl')} == target {ev.get('expected_sl')})"
                                    if act != "CLOSE" else "(position no longer held)") + ": no order, no lock")}
            try:  # 2026-10-30e QA30D-01: the receipt + saved read are the NOOP's artefact (as the lock is a MARK's)
                row.update(write_noop_receipt(lock_dir, sha, sym, act, pos, row))
            except Exception as e:
                raise PlaceLockError("AUDIT_WRITE_FAILED", EXIT_RETRY_NOT_ALLOWED,
                                     f"NO_OP_ALREADY_APPLIED not usable, NOOP receipt not written: {e}")
            try:
                from momentum_qa.audit import append_row, build_record, new_run_id
                append_row(build_record(run_id or new_run_id("placelock"), "momentum_qa/place_lock.py", row), audit_dir)
            except Exception as e:  # never an un-audited no-op
                raise PlaceLockError("AUDIT_WRITE_FAILED", EXIT_RETRY_NOT_ALLOWED,
                                     f"NO_OP_ALREADY_APPLIED not usable, PLACE_LOCK_NOOP row failed: {e}")
            return {**row, "ok": True, "no_order": True, "lock_path": None}

    # 2) other locks for this symbol under different verdicts
    ignored = []
    if allow_held and lp != legacy_same_sha and legacy_same_sha.exists():  # same verdict, pre-upgrade lock name
        d = _read(legacy_same_sha)
        raise PlaceLockError("LOCK_HELD", EXIT_LOCK_HELD,
                             f"verdict sha {sha[:12]} already used for {sym} (legacy lock {legacy_same_sha.name}, "
                             f"status={d.get('status')}, caller={d.get('caller')})", str(legacy_same_sha))
    for p, d in _same_symbol_locks(sym, lock_dir):
        if p == lp:
            continue
        if allow_held:  # RISK action: QA Bot ruling 1 (2026-10-30a); 30b QA-04: same-verdict locks are checked too
            err, info = _risk_lock_conflict(p, d, act, today, retry_after_fail)
            if err:
                raise err
            if info:
                ignored.append(info)
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
           "allow_held": bool(allow_held), "action": act, "day_il": today, "run_id": run_id,
           "lock_scheme": LOCK_SCHEME}
    if allow_held:
        rec["action_source"] = ctx.get("action_source")
        rec["action_run_id"], rec["action_ts_il"] = ctx.get("action_run_id"), ctx.get("action_ts_il")
        if risk_row is not None:
            for k in ("new_stop_loss", "prior_stop_loss", "reason"):
                if risk_row.get(k) is not None:
                    rec[k] = risk_row.get(k)
        if ignored:
            rec["ignored_locks"] = ignored
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
    rec["result"] = "ACQUIRED"
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


def mark(lock, status: str, *, order_id=None, position_id=None, note: str | None = None,
         verify_live_sl=None, verify_closed: bool | None = None, run_id: str | None = None,
         audit_dir: Path | None = None) -> dict:
    """Record the outcome on an acquired lock. The lock file is never deleted (single-use).
    On a RISK lock (allow_held) also append one PLACE_LOCK_MARK audit row = the PLACE_ACK feedback_daily needs
    (with the post-read: verify_live_sl for SL actions, verify_closed for CLOSE). 2026-10-30a."""
    status = status.upper()
    if status not in ("PLACED", "FAILED", "EXPIRED"):
        raise PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED, f"bad status {status}")
    lp = Path(lock)
    d = _read(lp)
    if d.get("allow_held") and d.get("status") in ("PLACED", "FAILED", "EXPIRED"):  # 2026-10-30e QA30D-02: a
        # marked RISK lock is terminal (buy locks keep their unchanged mark behaviour)
        err = PlaceLockError("BAD_INPUT", EXIT_RETRY_NOT_ALLOWED,
                             f"lock {lp.name} is already {d.get('status')}: a marked lock is terminal (a FAILED / "
                             f"EXPIRED action needs a new acquire with --retry-after-fail and a fresh verdict)",
                             str(lp), reason_code="MARK_TERMINAL")
        _audit_refusal(err, {"symbol": d.get("symbol"), "action": d.get("action"), "allow_held": True,
                             "lock_path": str(lp), "action_run_id": d.get("action_run_id"),
                             "action_ts_il": d.get("action_ts_il"), "run_id": run_id,
                             "verdict_sha256": d.get("verdict_sha256"), "verdict_path": d.get("verdict_path"),
                             "caller": "mark"}, audit_dir)  # every refusal writes one row
        raise err
    import uuid
    mark_id = uuid.uuid4().hex[:16]
    ts = _now()
    d.setdefault("history", []).append({"ts": ts, "status": status, "pid": os.getpid(), "mark_id": mark_id})
    d.update(status=status, marked_ts=ts, mark_id=mark_id)
    if order_id is not None:
        d["orderId"] = order_id
    if position_id is not None:
        d["positionId"] = position_id
    if note:
        d["note"] = note
    if verify_live_sl is not None:
        d["verify_live_sl"] = float(verify_live_sl)
    if verify_closed is not None:
        d["verify_closed"] = bool(verify_closed)
    tmp = lp.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, lp)
    if d.get("allow_held"):
        _audit_mark(lp, d, run_id, audit_dir)
    return d


def _audit_mark(lp: Path, d: dict, run_id, audit_dir) -> None:
    try:
        from momentum_qa.audit import append_row, build_record, new_run_id
        row = {"event": "PLACE_LOCK_MARK", "status": d.get("status"), "symbol": d.get("symbol"),
               "action": lock_action(lp, d), "lock_path": str(lp), "caller": d.get("caller"),
               "lock_run_id": d.get("run_id"), "action_run_id": d.get("action_run_id"),
               "action_ts_il": d.get("action_ts_il"), "day_il": d.get("day_il"),
               "verdict_path": d.get("verdict_path"), "orderId": d.get("orderId"), "positionId": d.get("positionId"),
               "expected_sl": d.get("new_stop_loss"), "verify_live_sl": d.get("verify_live_sl"),
               "verify_closed": d.get("verify_closed"), "verdict_sha256": d.get("verdict_sha256"),
               "note": d.get("note"), "mark_id": d.get("mark_id"), "marked_ts": d.get("marked_ts"),
               "rationale": f"place_lock mark {d.get('status')} {d.get('symbol')} {lock_action(lp, d)}"}
        append_row(build_record(run_id or d.get("run_id") or new_run_id("placelock"), "momentum_qa/place_lock.py",
                                row), audit_dir)
    except Exception as e:  # the mark stands; feedback_daily then reports the action as not acknowledged
        print(f"place_lock: mark audit row failed: {e}", file=sys.stderr)


release = mark  # alias: release(lock, status=...)


class _Parser(argparse.ArgumentParser):
    """argparse errors -> BAD_ARGS exit 4 (QA-05), never argparse's exit 2 (= LOCK_HELD)."""
    def error(self, message):
        raise PlaceLockError("BAD_ARGS", EXIT_RETRY_NOT_ALLOWED, message, reason_code="BAD_ARGS")


def main(argv=None) -> int:
    try:
        return _main(argv)
    except PlaceLockError as e:  # BAD_ARGS
        _audit_refusal(e, {"caller": "cli", "run_id": None, "symbol": None,
                           "argv": None if argv is None else list(argv)}, None)
        print(json.dumps({"ok": False, "code": e.code, "reason_code": e.reason_code, "reason": e.msg,
                          "lock_path": None}))
        print(e.code, file=sys.stderr)
        return e.exit_code


def _main(argv=None) -> int:
    ap = _Parser(prog="place_lock")
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
    a.add_argument("--action", help="REQUIRED with --allow-held (2026-10-30d ruling 2): TRAIL_SL | MOVE_SL_BREAKEVEN | "
                                    "CLOSE; it must match a QA-PASS row for the symbol in the verdict (no default, "
                                    "no inference); never used for a buy")
    a.add_argument("--run-id", help="caller run id (stored in the lock and in refusal audit rows)")
    m = sub.add_parser("mark")
    m.add_argument("--lock", required=True)
    m.add_argument("--status", required=True, choices=["PLACED", "FAILED", "EXPIRED"])
    m.add_argument("--order-id")
    m.add_argument("--position-id")
    m.add_argument("--note")
    m.add_argument("--verify-live-sl", type=float, help="post-read: live SL after the edit (SL actions)")
    m.add_argument("--verify-closed", action="store_true", default=None, help="post-read: position verified closed")
    m.add_argument("--run-id")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "acquire":
            r = acquire(args.verdict, args.symbol, args.account, caller=args.caller,
                        positions=args.positions_json, allow_held=args.allow_held,
                        retry_after_fail=args.retry_after_fail,
                        lock_dir=Path(args.lock_dir) if args.lock_dir else None,
                        instrument_id=args.instrument_id, manual_request=args.manual_request,
                        action=args.action, run_id=args.run_id)
        else:
            r = mark(args.lock, args.status, order_id=args.order_id, position_id=args.position_id, note=args.note,
                     verify_live_sl=args.verify_live_sl, verify_closed=args.verify_closed, run_id=args.run_id)
        print(json.dumps({"ok": True, **r}))
        return EXIT_OK
    except PlaceLockError as e:
        print(json.dumps({"ok": False, "code": e.code, "reason_code": e.reason_code, "reason": e.msg,
                          "lock_path": e.lock_path}))
        print(e.code, file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())

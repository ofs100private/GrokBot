#!/usr/bin/env python3
"""Daily feedback loop: what matched strategy vs clear deviations.

2026-10-30a (QA Bot rulings 3 + 4):
  PROTECTIVE_ACTION_NOT_APPLIED (HIGH, hard FAIL): a QA-PASS protective action (position_manager / open_gap_check
    ACTION CLOSE / MOVE_SL_BREAKEVEN / TRAIL_SL) counts as APPLIED only with a successful PLACE_ACK row
    (hand-written PLACE_ACK or place_lock's PLACE_LOCK_MARK status PLACED) AND a matching post-read
    (verify_live_sl == new_stop_loss within SL_TOL for SL actions; verify_closed for CLOSE). No ACK, a
    PLACE_LOCK_REFUSED row for it (unless a verified ACK exists), a failed ACK, a missing post-read or a post-read
    mismatch = NOT_APPLIED. KEEP for a protective action is decided from the audit row + post-read only, never
    from the PM verdict alone. Days before ACK_STRICT_FROM only: a PLACED place_lock file of that IL day for the
    symbol/action without an audit ACK = APPLIED_LOCK_ONLY (WATCH PROTECTIVE_ACK_LOCK_ONLY, MEDIUM).
  CONNECTOR_AUTH_BLOCKED (HIGH, category ops, never a trading FAIL): see momentum_qa.connector_auth.

2026-10-30b (QA Bot FAIL 1 on 30a: QA-01, QA-02, QA-06, QA-07, QA-08, QA-11):
  * Scope (QA-01): position_manager.py ACTION rows with qa_verdict PASS, plus EVERY momentum_qa/open_gap_check.py
    CLOSE row (it logs qa_verdict=None; its QA is details.qa.expected_action / details.qa.verdict). The item's
    qa_source says which.
  * ACK matching (QA-07): only PLACE_ACK / PLACE_LOCK_MARK / PLACE_LOCK_NOOP rows of the same symbol AND the same
    action (an ACK without an action matches nothing), at or after the ACTION row's ts_il; on days >=
    ACK_STRICT_FROM also tied to the ACTION row (ACK action_run_id / lock_run_id / caller_run_id / run_id == the
    ACTION row's run_id, or the same verdict sha). The LATEST candidate decides. An SL action without an
    expected SL (ACTION new_stop_loss, else the place_lock expected_sl) is POST_READ_MISSING, never APPLIED.
  * PLACE_LOCK_NOOP (QA-02): place_lock's NO_OP_ALREADY_APPLIED row (live SL already == target, or position already
    closed) counts as ACK + post-read -> APPLIED (sub_reason NO_OP_ALREADY_APPLIED).
  * ACK_STRICT_FROM (QA-06): read from AUDIT_DIR/feedback_config.json {"ack_strict_from": "<install IL day>"}; missing
    or invalid -> today's IL day (fail closed). protective_actions.ack_strict_from_source reports where it came from.
  * Auth (QA-08): only eToro connector signals count (connector_auth.ETORO_CONNECTORS); RUNTIME_ERROR is suppressed
    only for a row whose own text is an eToro auth refusal, or a connector-read script row on an auth-blocked night.
  * Alert (QA-11): the feedback run never records the alert as sent; the 22:05 routine runs
    `python -m momentum_qa.connector_auth mark-alert-sent --day <D>` only after SendToUser succeeded.

2026-10-30d (QA Bot FAIL 3 on 30c, QA30C-02; Ofer t287s1451): on days >= ACK_STRICT_FROM only a provenance-checked
  place_lock row scores APPLIED. A PLACE_LOCK_MARK counts only if its script is momentum_qa/place_lock.py, its
  action_run_id is the ACTION row's run_id, its lock file exists under the <sha12>-<SYM>~<ACTION>.lock name of its
  verdict sha, and that lock file says the same status / symbol / action / verdict sha / action_run_id and carries
  the same post-read (verify_closed / verify_live_sl). A PLACE_LOCK_NOOP counts only from place_lock.py, tied, with
  read_check OK and (CLOSE) target positionIds + a book fingerprint that met its required matches. A hand-written
  PLACE_ACK, or any row failing provenance, is listed as excluded (HANDWRITTEN_ACK_IGNORED_STRICT /
  PROVENANCE_*) and can only DOWNGRADE (a failed ACK counts as a failure). Every PLACE_LOCK_REFUSED (risk) and every
  failed MARK at or after the ACTION row is a failure event; the LATEST event decides, so a refusal or MARK FAILED
  newer than the latest place_lock success -> NOT_APPLIED. Legacy days (< ACK_STRICT_FROM) keep the 30c scoring.
2026-10-30e (QA Bot FAIL 4 on 30d, QA30D-01 / QA30D-02, open-point ruling 1):
  * PLACE_LOCK_NOOP (QA30D-01) counts only with its place_lock receipt: receipt_path named
    <sha12>-<SYM>~<ACTION>.<noop_id>.noop, receipt_sha256 == sha256(receipt), the receipt's noop_id / symbol / action
    / action_run_id / verdict sha / positions sha agree with the row, the saved read (read_path) hashes to
    positions_sha256 and is <= 125 s older than the receipt, and the no-op RE-CHECKED on that saved read passes:
    keys_read_check OK and close_noop_check (CLOSE, book recomputed from today's protective ACTION rows) or
    noop_check on the ACTION row's lots and new_stop_loss (SL). Else PROVENANCE_NOOP_* (excluded).
  * PLACE_LOCK_MARK (QA30D-02) needs the lock's mark_id == the row's mark_id, a lock history without FAILED /
    EXPIRED, and a verdict_path that exists and re-hashes to verdict_sha256 (also for NOOPs). Each mark_id / noop_id
    counts ONCE (its first row); a replayed copy is excluded as PROVENANCE_REPLAYED.
  * Ruling 1: the DUPLICATE_ACTION_SAME_DAY "benign refusal" exception is removed: every risk refusal at or after
    the ACTION row is a failure event.
2026-10-30c (QA Bot FAIL 2 on 30b: QA30B-02, QA30B-04, QA30B-06, QA30B-08):
  * ACK_STRICT_FROM (QA30B-02): a config value later than today's IL day is refused and today is used
    (source "future:<path> (<value>) -> today (fail closed)"). Only a valid YYYY-MM-DD <= today is used as is.
  * Expected SL (QA30B-08): taken only from the ACTION row (details.new_stop_loss) or from a place_lock row
    (PLACE_LOCK_MARK / PLACE_LOCK_NOOP expected_sl, copied from the verdict); a hand-written PLACE_ACK's
    expected_sl / sl_new is never trusted (a self-consistent hand-written ack cannot score APPLIED).
  * Hand-written PLACE_ACK after a place_lock row (QA30B-04): once a PLACE_LOCK_MARK / PLACE_LOCK_NOOP candidate
    exists for the item, a later hand-written PLACE_ACK that is a success WITHOUT any post-read field is ignored
    (listed in excluded_acks, why PLACE_ACK_WITHOUT_POST_READ_AFTER_PLACE_LOCK_ROW); a failed one, or one with a
    post-read, still counts (fail closed). The v8 open-gap prompt no longer writes such a row.
  * RUNTIME_ERROR suppression by script (QA30B-06): not for a row whose text names a non-eToro service
    (connector_auth.NON_ETORO_SERVICES, e.g. a Yahoo HTTP 401) - that stays an AVOID.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from momentum_qa.eod_miss_check import (OWNER_EVENTS, OWNERSHIP_CODES, OWNERSHIP_EVENTS, is_miss, ownership_code,
                                        schedule_alignment,
                                        place_watch, screener_actions_by_deadline)
from momentum_qa import market_clock as MC
from momentum_qa.audit import PROTECTIVE_REJECT_CODES, base_symbol_of, classify_skip_code, placed_symbols, row_screener_run_id
from momentum_qa import connector_auth as CA
from momentum_qa import place_lock as PL

# QA Bot 2026-10-21: from this IL date every pack BUY name needs a FILL/placed row or a SKIP
# row for its screener run; gate_ok_codes / protective_reject counts come from SKIP rows.
SKIP_ROWS_FROM = "2026-10-21"  # QA Bot 2026-10-21: moved from 10-22 so backfilled rows count

IL = ZoneInfo("Asia/Jerusalem")
AUDIT_DIR = Path("/workspace/momentum_audit")
OUT_DIR = Path("/workspace/trading-lessons/momentum")


def load_day(day: str) -> list[dict]:
    path = AUDIT_DIR / f"{day}.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# QA Bot 2026-10-13: protective gate rejects → KEEP/GATE_OK (never playbook AVOID)
GATE_OK_CODES = {
    "ETF_BACKFILL_BLOCKED": "ETF backfill blocked by gate (protective)",
    "DUPLICATE_HOLD_BUY": "buy rejected: symbol already held/pending on keys book",
    "ETF_FLOOR_ALREADY_MET": "ETF floor already met — no extra ETF buy",
    "CROSS_BOOK_HELD": "buy rejected: symbol held in Classic book (Ofer rule 2026-10-13)",
    # QA Bot 2026-10-15: stale cross-book fail-closed is protective -> GATE_OK, never deviation
    "STALE_CROSSBOOK_FAIL_CLOSED": "no pack: Classic snapshot stale and refresh failed (fail closed)",
    "CROSS_BOOK_READ_MISSING_OR_STALE": "buy blocked: Classic snapshot missing/stale (fail closed)",
}

# QA Bot 2026-10-15: HIGH deviation + day hard FAIL. Ofer KEEP on such positions is a
# position decision only and never clears the deviation.
HARD_FAIL_CODES = {
    "DUPLICATE_PLACE": "same QA verdict placed twice / duplicate position for one name",
    "AMOUNT_GT_1000_PER_NAME": "exposure > $1000 per name",
    # QA Bot ruling 3 (2026-10-30a; XOM MOVE_SL_BREAKEVEN 171.01->171.89 dropped by LOCK_HELD 10-26..28)
    "PROTECTIVE_ACTION_NOT_APPLIED": "QA-PASS SL / TRAIL / close without PLACE_ACK + matching post-read",
}
PLACE_QA_DIR = AUDIT_DIR / "place_qa"

PROTECTIVE_ACTIONS = ("CLOSE", "MOVE_SL_BREAKEVEN", "TRAIL_SL")
PROTECTIVE_SCRIPTS = ("position_manager.py", "momentum_qa/open_gap_check.py")
OPEN_GAP_SCRIPT = "momentum_qa/open_gap_check.py"
ACK_EVENTS = ("PLACE_ACK", "PLACE_LOCK_MARK", "PLACE_LOCK_NOOP")
SL_TOL = 0.01                   # post-read SL must equal the QA-passed new stop within 1 cent
_BAD_ACK_WORDS = ("FAIL", "BLOCK", "PENDING", "REJECT", "ERROR", "REFUSED")
CONNECTOR_AUTH_STATE: Path | None = None   # default AUDIT_DIR / connector_auth_state.json (resolved at call time)
FULL_RISK_RECHECK_FLAG: Path | None = None  # default AUDIT_DIR / FULL_RISK_RECHECK_REQUIRED.json
FEEDBACK_CONFIG: Path | None = None         # default AUDIT_DIR / feedback_config.json (QA-06)


def _state_path() -> Path:
    return Path(CONNECTOR_AUTH_STATE or Path(AUDIT_DIR) / "connector_auth_state.json")


def _flag_path() -> Path:
    return Path(FULL_RISK_RECHECK_FLAG or Path(AUDIT_DIR) / "FULL_RISK_RECHECK_REQUIRED.json")


def _config_path() -> Path:
    return Path(FEEDBACK_CONFIG or Path(AUDIT_DIR) / "feedback_config.json")


def _today_il() -> str:
    return datetime.now(tz=IL).date().isoformat()


def ack_strict_from() -> tuple[str, str]:
    """QA-06: (ACK_STRICT_FROM IL day, source). From feedback_config.json {"ack_strict_from": "YYYY-MM-DD"} written by
    the install step (= install IL day). Missing / unreadable / invalid -> fail closed to today's IL day."""
    p = _config_path()
    try:
        v = json.loads(p.read_text()).get("ack_strict_from")
        if not isinstance(v, str) or date.fromisoformat(v).isoformat() != v:
            raise ValueError(f"ack_strict_from={v!r} is not YYYY-MM-DD")
        today = _today_il()
        if v > today:  # QA30B-02: a future value would turn strictness off; refuse it
            return today, f"future:{p} ({v}) -> today (fail closed)"
        return v, f"config:{p}"
    except FileNotFoundError:
        return _today_il(), f"missing:{p} -> today (fail closed)"
    except Exception as e:  # noqa: BLE001
        return _today_il(), f"invalid:{p} ({type(e).__name__}: {e}) -> today (fail closed)"


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _act(x) -> str:
    return str(x or "").strip().upper()


def _ts(x):
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=IL)
    except Exception:
        return None


def protective_qa(r: dict) -> tuple[bool, str | None]:
    """QA-01: (in scope, qa_source). Top-level qa_verdict PASS (position_manager), or ANY open_gap_check CLOSE row:
    open_gap_check logs qa_verdict=None and keeps its QA under details.qa (expected_action / verdict)."""
    a = _act(r.get("action"))
    if r.get("event") != "ACTION" or str(r.get("script") or "") not in PROTECTIVE_SCRIPTS:
        return False, None
    if not (a in PROTECTIVE_ACTIONS or a.startswith("CLOSE")):
        return False, None
    if r.get("qa_verdict") == "PASS":
        return True, "qa_verdict"
    if str(r.get("script")) == OPEN_GAP_SCRIPT and a.startswith("CLOSE"):
        q = (r.get("details") or {}).get("qa") or {}
        if _act(q.get("verdict")) == "PASS":
            return True, "details.qa.verdict"
        if _act(q.get("expected_action")) == a:
            return True, "details.qa.expected_action"
        return True, "open_gap_close"  # every open-gap CLOSE is in scope (QA Bot ruling C)
    return False, None


def is_protective_row(r: dict) -> bool:
    return protective_qa(r)[0]


def _ack_action(r: dict) -> str:
    return _act(r.get("action") or (r.get("details") or {}).get("action"))


def _ack_ok(r: dict) -> tuple[bool, str]:
    if r.get("event") == "PLACE_LOCK_MARK":
        st = _act(r.get("status"))
        return st == "PLACED", st or "?"
    if r.get("event") == "PLACE_LOCK_NOOP":
        st = _act(r.get("result") or r.get("status"))
        return st == "NO_OP_ALREADY_APPLIED", st or "?"
    st = " ".join(_act(r.get(k)) for k in ("status", "ack") if r.get(k) is not None) or "?"
    code = r.get("statusCode")
    if code is not None and not (200 <= int(_f(code) or 0) < 300):
        return False, f"{st} statusCode={code}"
    return not any(w in st for w in _BAD_ACK_WORDS), st


PLACE_LOCK_ACK_EVENTS = ("PLACE_LOCK_MARK", "PLACE_LOCK_NOOP")
POST_READ_KEYS = ("verify_closed", "post_read_closed", "verify_live_sl", "post_read_sl")


def _has_post_read(r: dict) -> bool:
    d = r.get("details") or {}
    return any(r.get(k) is not None or d.get(k) is not None for k in POST_READ_KEYS) or any(
        k in _act(r.get("status")) for k in ("CLOSED_VERIFIED", "CLOSE_VERIFIED"))


def _post_read(r: dict, action: str, expected_sl) -> tuple[str, dict]:
    """('OK' | 'MISSING' | 'MISMATCH', detail). QA-07: an SL action without an expected SL is MISSING.
    QA30B-08: the expected SL comes from the ACTION row, else from a place_lock row only (never a PLACE_ACK)."""
    d = r.get("details") or {}
    if action.startswith("CLOSE"):
        v = next((x for x in (r.get("verify_closed"), r.get("post_read_closed"), d.get("verify_closed")) if x is not None), None)
        if v is None and any(k in _act(r.get("status")) for k in ("CLOSED_VERIFIED", "CLOSE_VERIFIED")):
            v = True
        if v is None:
            return "MISSING", {}
        return ("OK" if v is True else "MISMATCH"), {"verify_closed": v}
    v = next((_f(x) for x in (r.get("verify_live_sl"), r.get("post_read_sl"), d.get("verify_live_sl")) if _f(x) is not None), None)
    exp = _f(expected_sl)
    if exp is None and r.get("event") in PLACE_LOCK_ACK_EVENTS:
        exp = _f(r.get("expected_sl"))
    if exp is None:
        return "MISSING", {"verify_live_sl": v, "expected_sl": None, "expected_sl_missing": True}
    if v is None:
        return "MISSING", {"expected_sl": exp}
    if abs(v - exp) > SL_TOL + 1e-9:
        return "MISMATCH", {"verify_live_sl": v, "expected_sl": exp}
    return "OK", {"verify_live_sl": v, "expected_sl": exp}


def _lock_action_run_id(a: dict) -> str | None:
    """action_run_id recorded in the place_lock file an ACK row points at (place_lock / lock_path), if readable."""
    lp = a.get("place_lock") or a.get("lock_path")
    if not lp:
        return None
    try:
        return json.loads(Path(lp).read_text()).get("action_run_id")
    except Exception:
        return None


def _ack_tied(a: dict, action_row: dict) -> bool:
    """QA-07: the ACK belongs to THIS ACTION row: same run_id (action_run_id from place_lock, or the lock / caller /
    row run id), or the same verdict sha when the ACTION row carries one."""
    rid = action_row.get("run_id")
    if rid and rid in {a.get("action_run_id"), a.get("lock_run_id"), a.get("caller_run_id"), a.get("run_id"),
                       _lock_action_run_id(a)}:
        return True
    vs = action_row.get("verdict_sha256") or (action_row.get("details") or {}).get("verdict_sha256")
    return bool(vs) and a.get("verdict_sha256") == vs


def _lock_only_evidence(day: str, sym: str, action: str, lock_dir: Path) -> dict | None:
    try:
        for p, d in PL._same_symbol_locks(sym, Path(lock_dir)):
            if d.get("status") != "PLACED" or not d.get("allow_held"):
                continue
            la = PL.lock_action(p, d)
            if PL.lock_day(p, d) == day and la in (action, PL.UNKNOWN_ACTION):
                return {"lock": p.name, "lock_action": la, "orderId": d.get("orderId"), "note": d.get("note")}
    except Exception:
        return None
    return None


PLACE_LOCK_SCRIPT = "momentum_qa/place_lock.py"
_SHA_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


def _read_json(p) -> dict | None:
    try:
        d = json.loads(Path(p).read_text())
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _sha_file(p) -> str | None:
    try:
        import hashlib
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except Exception:
        return None


NOOP_READ_MAX_SKEW_S = 125  # the saved read must be at most this much older than the receipt (place_lock: < 120 s)


def _noop_recheck(a: dict, sym: str, action: str, action_row: dict) -> tuple[bool, str]:
    """QA30D-01: the receipt + saved read of a PLACE_LOCK_NOOP, re-verified. (ok, why)."""
    rp, rs = a.get("receipt_path"), str(a.get("receipt_sha256") or "")
    nid, vs = str(a.get("noop_id") or ""), str(a.get("verdict_sha256") or "")
    if not rp or not _SHA_RE.match(rs) or not re.fullmatch(r"[0-9a-f]{16}", nid):
        return False, "PROVENANCE_NOOP_NO_RECEIPT"
    if Path(rp).name != PL.noop_receipt_name(vs, sym, action, nid):
        return False, "PROVENANCE_NOOP_RECEIPT_NAME"
    if _sha_file(rp) != rs:
        return False, "PROVENANCE_NOOP_RECEIPT_MISSING_OR_CHANGED"
    rc = _read_json(rp) or {}
    for k in ("noop_id", "action_run_id", "verdict_sha256", "positions_sha256", "read_path"):
        if rc.get(k) != a.get(k):
            return False, "PROVENANCE_NOOP_RECEIPT_MISMATCH"
    if base_symbol_of(rc.get("symbol")) != sym or _act(rc.get("action")) != action:
        return False, "PROVENANCE_NOOP_RECEIPT_MISMATCH"
    if a.get("receipt_ts") is not None and a.get("receipt_ts") != rc.get("ts"):
        return False, "PROVENANCE_NOOP_RECEIPT_MISMATCH"
    read_p = rc.get("read_path")
    if not read_p or _sha_file(read_p) != rc.get("positions_sha256"):
        return False, "PROVENANCE_NOOP_READ_MISSING_OR_CHANGED"
    try:
        raw = json.loads(Path(read_p).read_text())
        age = (PL._parse_ts(rc.get("ts")) - PL._parse_ts(PL.positions_timestamp(raw))).total_seconds()
    except Exception:
        return False, "PROVENANCE_NOOP_READ_UNPARSEABLE"
    if not (-5 <= age <= NOOP_READ_MAX_SKEW_S):
        return False, "PROVENANCE_NOOP_READ_STALE"
    kr = PL.keys_read_check(raw)
    if not kr["ok"]:
        return False, "PROVENANCE_NOOP_RECHECK_READ_NOT_OK"
    day = str(action_row.get("ts_il") or a.get("ts_il") or "")[:10]
    book = PL.action_run_book(day, action_row, Path(AUDIT_DIR))
    if action == "CLOSE":
        try:
            ev = PL.close_noop_check(kr, sym, None, action_row, book)
        except PL.PlaceLockError as e:
            return False, f"PROVENANCE_NOOP_RECHECK_{e.reason_code}"
        if ev is None:
            return False, "PROVENANCE_NOOP_RECHECK_STILL_HELD"
        return True, "OK"
    d = action_row.get("details") or {}
    exp = d.get("new_stop_loss", action_row.get("new_stop_loss"))
    ev = PL.noop_check(raw, sym, action, exp, None, target_pids=sorted(book["target_positionIds"]))
    if ev is None:
        return False, "PROVENANCE_NOOP_RECHECK_SL_NOT_AT_TARGET"
    return True, "OK"


def place_lock_provenance(a: dict, sym: str, action: str, action_row: dict) -> tuple[bool, str]:
    """QA30C-02 / QA30D-01 / QA30D-02: (ok, why) - is this ACK row a genuine place_lock MARK / NOOP for THIS ACTION
    row? A MARK is checked against its lock file, a NOOP against its receipt + saved read (re-checked)."""
    ev = a.get("event")
    if ev not in PLACE_LOCK_ACK_EVENTS:
        return False, "HANDWRITTEN_ACK_IGNORED_STRICT"
    if str(a.get("script") or "") != PLACE_LOCK_SCRIPT:
        return False, "PROVENANCE_NOT_PLACE_LOCK_SCRIPT"
    rid = action_row.get("run_id")
    if not action_row.get("from_refusal") and (not rid or a.get("action_run_id") != rid):
        return False, "PROVENANCE_NOT_TIED_TO_ACTION_ROW"
    vs = str(a.get("verdict_sha256") or "")
    if not _SHA_RE.match(vs):
        return False, "PROVENANCE_NO_VERDICT_SHA"
    vp = a.get("verdict_path")
    if not vp or not Path(vp).exists():  # 2026-10-30e: the verdict file is required (re-hashed)
        return False, "PROVENANCE_VERDICT_MISSING"
    if _sha_file(vp) != vs:
        return False, "PROVENANCE_VERDICT_SHA_MISMATCH"
    if ev == "PLACE_LOCK_NOOP":
        if a.get("read_check") != "OK":
            return False, "PROVENANCE_NOOP_READ_NOT_OK"
        if action == "CLOSE":
            bf = a.get("book_fingerprint") if isinstance(a.get("book_fingerprint"), dict) else {}
            if not a.get("target_positionIds") or bf.get("by") != "positionId" or not isinstance(
                    bf.get("required"), int) or bf.get("required") < 1 or (bf.get("matched") or 0) < bf["required"]:
                return False, "PROVENANCE_NOOP_UNVERIFIED_BOOK"
        return _noop_recheck(a, sym, action, action_row)
    lp = a.get("lock_path")
    if not lp:
        return False, "PROVENANCE_NO_LOCK_PATH"
    if Path(lp).name != f"{vs[:12]}-{sym}{PL.ACTION_SEP}{action}.lock":
        return False, "PROVENANCE_LOCK_NAME"
    d = _read_json(lp)
    if d is None:
        return False, "PROVENANCE_LOCK_MISSING"
    if (_act(d.get("status")) != _act(a.get("status")) or base_symbol_of(d.get("symbol")) != sym
            or _act(d.get("action")) != action or d.get("verdict_sha256") != vs
            or d.get("action_run_id") != a.get("action_run_id") or not d.get("allow_held")):
        return False, "PROVENANCE_LOCK_MISMATCH"
    if not a.get("mark_id") or d.get("mark_id") != a.get("mark_id"):  # 2026-10-30e QA30D-02
        return False, "PROVENANCE_MARK_ID_MISMATCH"
    hist = [h for h in (d.get("history") or []) if isinstance(h, dict)]
    if _act(a.get("status")) == "PLACED" and any(_act(h.get("status")) in ("FAILED", "EXPIRED") for h in hist):
        return False, "PROVENANCE_LOCK_HAD_FAILED"
    if _act(a.get("status")) == "PLACED":
        if action == "CLOSE" and not (d.get("verify_closed") is True and a.get("verify_closed") is True):
            return False, "PROVENANCE_LOCK_POST_READ"
        if action != "CLOSE" and (_f(d.get("verify_live_sl")) is None
                                  or _f(d.get("verify_live_sl")) != _f(a.get("verify_live_sl"))):
            return False, "PROVENANCE_LOCK_POST_READ"
    return True, "OK"


def _strict_decide(sym: str, action: str, r: dict, same: list, refs: list, exp, t0) -> tuple[str, str | None, dict]:
    """QA30C-02 strict scoring: the latest event among provenance-checked place_lock ACKs, failed ACKs of any origin,
    and risk refusals decides. Only a provenance-checked place_lock row with an OK post-read is APPLIED."""
    events, excluded, ack_list = [], [], []
    seen_ids: set = set()
    for a in same:
        ta = _ts(a.get("ts_il"))
        if ta is None or t0 is None or ta < t0:
            excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"), "why": "BEFORE_ACTION_OR_NO_TS"})
            continue
        uid = a.get("mark_id") if a.get("event") == "PLACE_LOCK_MARK" else (
            a.get("noop_id") if a.get("event") == "PLACE_LOCK_NOOP" else None)
        if uid and uid in seen_ids:  # 2026-10-30e QA30D-02: a mark / no-op counts once (its first row)
            excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"), "why": "PROVENANCE_REPLAYED"})
            continue
        if uid:
            seen_ids.add(uid)
        good, st = _ack_ok(a)
        prov, why = place_lock_provenance(a, sym, action, r)
        if not good:  # a failure downgrades whatever its origin
            ent = {"event": a.get("event"), "ts_il": a.get("ts_il"), "run_id": a.get("run_id"), "status": st,
                   "ok": False, "post_read": "ACK_FAILED", "provenance": why}
            ack_list.append(ent)
            events.append((ta, "ack", ent))
            continue
        pr, det = _post_read(a, action, exp)
        if not prov:
            if pr == "MISMATCH":  # a non-place_lock ACK may downgrade (its own post-read disagrees), never upgrade
                ent = {"event": a.get("event"), "ts_il": a.get("ts_il"), "run_id": a.get("run_id"), "status": st,
                       "ok": True, "post_read": "MISMATCH", "tied": False, "provenance": why, **det}
                ack_list.append(ent)
                events.append((ta, "ack", ent))
                continue
            excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"), "script": a.get("script"), "why": why})
            continue
        ent = {"event": a.get("event"), "ts_il": a.get("ts_il"), "run_id": a.get("run_id"), "status": st,
               "ok": True, "post_read": pr, "tied": True, "provenance": "OK", **det}
        ack_list.append(ent)
        events.append((ta, "ack", ent))
    for x in refs:  # 2026-10-30e ruling 1: no benign-duplicate exception - every risk refusal is a failure event
        tx = _ts(x.get("ts_il"))
        if tx is None or (t0 is not None and tx < t0):
            continue
        events.append((tx, "refusal", x))
    events.sort(key=lambda e: e[0])
    ev = {"acks": ack_list, "excluded_acks": excluded, "failed_acks": [x["status"] for x in ack_list if not x["ok"]],
          "scoring": "strict-provenance (QA30C-02 / QA30D-01)"}
    if not events:
        if any(e["why"] == "HANDWRITTEN_ACK_IGNORED_STRICT" for e in excluded):
            return "NOT_APPLIED", "HANDWRITTEN_ACK_IGNORED_STRICT", ev
        if excluded:
            return "NOT_APPLIED", f"ACK_{excluded[-1]['why']}", ev
        return "NOT_APPLIED", "NO_PLACE_ACK", ev
    _, kind, last = events[-1]
    if kind == "refusal":
        return "NOT_APPLIED", f"LOCK_REFUSED:{last.get('code')}", ev
    if not last["ok"]:
        return "NOT_APPLIED", f"ACK_FAILED:{last['status']}", ev
    if last["post_read"] == "OK":
        return "APPLIED", ("NO_OP_ALREADY_APPLIED" if last["event"] == "PLACE_LOCK_NOOP" else None), ev
    if last["post_read"] == "MISMATCH":
        return "NOT_APPLIED", "POST_READ_MISMATCH", ev
    return "NOT_APPLIED", "POST_READ_MISSING", ev


def protective_report(day: str, rows: list[dict], lock_dir: Path | None = None) -> dict:
    """QA Bot ruling 3 + 30b QA-01/02/06/07: APPLIED / NOT_APPLIED per in-scope protective action.
    Candidate ACKs = PLACE_ACK / PLACE_LOCK_MARK / PLACE_LOCK_NOOP rows of the same symbol AND the same action
    (an ACK without an action matches nothing), at or after the ACTION row's ts_il, and (days >= ACK_STRICT_FROM)
    tied to the ACTION row (run_id / verdict sha). The LATEST candidate decides (a later mismatch beats an earlier OK)."""
    lock_dir = Path(lock_dir or Path(AUDIT_DIR) / "place_locks")
    strict_from, strict_src = ack_strict_from()
    strict = day >= strict_from
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        ok, src = protective_qa(r)
        if ok:
            k = (base_symbol_of(r.get("symbol")), _act(r.get("action")))
            if k not in latest or str(r.get("ts_il") or "") >= str(latest[k].get("ts_il") or ""):
                latest[k] = {**r, "_qa_source": src}
    acks = [r for r in rows if r.get("event") in ACK_EVENTS and r.get("symbol")]
    refusals = [r for r in rows if r.get("event") == "PLACE_LOCK_REFUSED" and r.get("allow_held")]
    for r in refusals:  # a refused risk action with no in-scope ACTION row is still a protective action not applied
        k = (base_symbol_of(r.get("symbol")), _act(r.get("action")) or PL.UNKNOWN_ACTION)
        if not any(k[0] == s and (k[1] == a or k[1] == PL.UNKNOWN_ACTION) for s, a in latest):
            latest.setdefault(k, {"symbol": r.get("symbol"), "action": k[1], "ts_il": r.get("ts_il"),
                                  "run_id": r.get("action_run_id"), "script": "momentum_qa/place_lock.py",
                                  "details": {}, "from_refusal": True, "_qa_source": "refusal"})
    items = []
    for (sym, action), r in sorted(latest.items()):
        d = r.get("details") or {}
        exp = d.get("new_stop_loss", r.get("new_stop_loss"))
        t0 = _ts(r.get("ts_il"))
        same = [a for a in acks if base_symbol_of(a.get("symbol")) == sym and _ack_action(a) == action]
        if strict:  # 2026-10-30d QA30C-02
            refs_s = [x for x in refusals if base_symbol_of(x.get("symbol")) == sym
                      and _act(x.get("action")) in (action, PL.UNKNOWN_ACTION, "")]
            status, sub, evidence = _strict_decide(sym, action, r, same, refs_s, exp, t0)
            evidence["refusals"] = [{"ts_il": x.get("ts_il"), "code": x.get("code"), "exit_code": x.get("exit_code"),
                                     "reason_code": x.get("reason_code"), "lock_path": x.get("lock_path"),
                                     "run_id": x.get("run_id")} for x in refs_s
                                    if t0 is None or (_ts(x.get("ts_il")) or t0) >= t0]
            items.append({"symbol": r.get("symbol") or sym, "action": action, "status": status, "sub_reason": sub,
                          "ts_il": r.get("ts_il"), "run_id": r.get("run_id"), "script": r.get("script"),
                          "qa_source": r.get("_qa_source"), "expected_sl": exp,
                          "prior_sl": d.get("prior_stop_loss"), "from_refusal": bool(r.get("from_refusal")),
                          "evidence": evidence})
            continue
        excluded = []
        cands = []
        for a in same:
            ta = _ts(a.get("ts_il"))
            if ta is None or t0 is None or ta < t0:
                excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"), "why": "BEFORE_ACTION_OR_NO_TS"})
                continue
            tied = r.get("from_refusal") or _ack_tied(a, r)
            if strict and not tied:
                excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"), "why": "NOT_TIED_TO_ACTION_ROW"})
                continue
            cands.append((ta, a, tied))
        cands.sort(key=lambda x: x[0])
        kept, seen_pl = [], False  # QA30B-04: a success PLACE_ACK without post-read never overrides a place_lock row
        for ta, a, tied in cands:
            if a.get("event") in PLACE_LOCK_ACK_EVENTS:
                seen_pl = True
            elif seen_pl and a.get("event") == "PLACE_ACK" and _ack_ok(a)[0] and not _has_post_read(a):
                excluded.append({"ts_il": a.get("ts_il"), "event": a.get("event"),
                                 "why": "PLACE_ACK_WITHOUT_POST_READ_AFTER_PLACE_LOCK_ROW"})
                continue
            kept.append((ta, a, tied))
        cands = kept
        refs = [x for x in refusals if base_symbol_of(x.get("symbol")) == sym
                and _act(x.get("action")) in (action, PL.UNKNOWN_ACTION, "")
                and (t0 is None or (_ts(x.get("ts_il")) or t0) >= t0)]
        ack_list = []
        for ta, a, tied in cands:
            good, st = _ack_ok(a)
            pr, det = _post_read(a, action, exp) if good else ("ACK_FAILED", {})
            ack_list.append({"event": a.get("event"), "ts_il": a.get("ts_il"), "run_id": a.get("run_id"),
                             "status": st, "ok": good, "post_read": pr, "tied": bool(tied), **det})
        evidence = {"acks": ack_list, "excluded_acks": excluded,
                    "failed_acks": [x["status"] for x in ack_list if not x["ok"]],
                    "refusals": [{"ts_il": x.get("ts_il"), "code": x.get("code"), "exit_code": x.get("exit_code"),
                                  "reason_code": x.get("reason_code"), "lock_path": x.get("lock_path"),
                                  "run_id": x.get("run_id")} for x in refs]}
        if ack_list:
            last = ack_list[-1]  # QA-07: the latest ACK decides
            if not last["ok"]:
                status, sub = "NOT_APPLIED", f"ACK_FAILED:{last['status']}"
            elif last["post_read"] == "OK":
                status, sub = "APPLIED", ("NO_OP_ALREADY_APPLIED" if last["event"] == "PLACE_LOCK_NOOP" else None)
            elif last["post_read"] == "MISMATCH":
                status, sub = "NOT_APPLIED", "POST_READ_MISMATCH"
            else:
                status, sub = "NOT_APPLIED", "POST_READ_MISSING"
        elif refs:
            status, sub = "NOT_APPLIED", f"LOCK_REFUSED:{refs[-1].get('code')}"
        elif excluded:
            status, sub = "NOT_APPLIED", f"ACK_{excluded[-1]['why']}"
        else:
            lo = _lock_only_evidence(day, sym, action, lock_dir) if not strict else None
            if lo:
                status, sub = "APPLIED_LOCK_ONLY", "NO_AUDIT_ACK_LEGACY_LOCK"
                evidence["lock_only"] = lo
            else:
                status, sub = "NOT_APPLIED", "NO_PLACE_ACK"
        items.append({"symbol": r.get("symbol") or sym, "action": action, "status": status, "sub_reason": sub,
                      "ts_il": r.get("ts_il"), "run_id": r.get("run_id"), "script": r.get("script"),
                      "qa_source": r.get("_qa_source"), "expected_sl": exp,
                      "prior_sl": d.get("prior_stop_loss"), "from_refusal": bool(r.get("from_refusal")),
                      "evidence": evidence})
    counts = Counter(i["status"] for i in items)
    return {"items": items, "applied": counts.get("APPLIED", 0), "not_applied": counts.get("NOT_APPLIED", 0),
            "lock_only": counts.get("APPLIED_LOCK_ONLY", 0), "ack_strict_from": strict_from,
            "ack_strict_from_source": strict_src, "strict": strict,
            "rule": (("APPLIED iff the LATEST event at or after the ACTION row (provenance-checked place_lock MARK / NOOP, "
                      "a failed ACK of any origin, or a risk PLACE_LOCK_REFUSED) is a place_lock success with a matching "
                      "post-read; hand-written PLACE_ACK rows never upgrade (QA30C-02)") if strict else
                     ("APPLIED iff the LATEST same-action ACK (PLACE_ACK / PLACE_LOCK_MARK PLACED / PLACE_LOCK_NOOP) at or "
                      "after the ACTION row has a matching post-read; never from the PM verdict alone"))}


def apply_protective(report: dict, prot: dict) -> None:
    """Rewrite KEEP entries of protective actions from evidence; add HIGH AVOID / WATCH rows."""
    by_key = {(base_symbol_of(i["symbol"]), i["action"]): i for i in prot["items"]}
    keep = []
    for k in report["strategy_aligned"]:
        i = by_key.get((base_symbol_of(k.get("symbol")), _act(k.get("action"))))
        if i is None or k.get("gate"):
            keep.append(k)
            continue
        if i["status"] == "NOT_APPLIED":
            continue  # never KEEP from the PM verdict alone
        ev = i["evidence"]
        if i["status"] == "APPLIED":
            a = ev["acks"][-1]
            tag = f"APPLIED: {a['event']} {a['status']} post-read " + (
                f"SL {a.get('verify_live_sl')}" if "verify_live_sl" in a else f"closed={a.get('verify_closed')}")
        else:
            tag = f"APPLIED_LOCK_ONLY: {ev['lock_only']['lock']} (no audit ACK row)"
        keep.append({**k, "applied": i["status"], "rationale": f"{k.get('rationale')} [{tag}]"})
    report["strategy_aligned"] = keep
    for i in prot["items"]:
        rng = f" {i['prior_sl']}->{i['expected_sl']}" if i.get("expected_sl") is not None else ""
        if i["status"] == "NOT_APPLIED":
            report["deviations_clear"].append({
                "tag": "AVOID", "action": i["action"], "symbol": i["symbol"],
                "deviation_code": "PROTECTIVE_ACTION_NOT_APPLIED", "severity": "HIGH", "hard_fail": True,
                "sub_reason": i["sub_reason"],
                "rationale": (f"QA-PASS {i['action']} {i['symbol']}{rng} NOT applied: {i['sub_reason']} "
                              f"(acks={len(i['evidence']['acks'])}, refusals={len(i['evidence']['refusals'])}, "
                              f"failed_acks={len(i['evidence']['failed_acks'])}). Re-run the protective action now "
                              "(fresh QA) and fix the cause; never score it KEEP from the PM verdict.")})
        elif i["status"] == "APPLIED_LOCK_ONLY":
            report["deviations_clear"].append({
                "tag": "WATCH", "action": i["action"], "symbol": i["symbol"],
                "deviation_code": "PROTECTIVE_ACK_LOCK_ONLY", "severity": "MEDIUM",
                "rationale": (f"{i['action']} {i['symbol']}{rng}: only a PLACED place_lock file "
                              f"({i['evidence']['lock_only']['lock']}) shows it; no PLACE_ACK / post-read audit row "
                              f"(legacy day < {prot.get('ack_strict_from')}).")})
    if prot["not_applied"]:
        report["lessons"].append({"tag": "AVOID", "text": (
            "PROTECTIVE_ACTION_NOT_APPLIED: " + ", ".join(
                f"{i['action']}:{i['symbol']}({i['sub_reason']})" for i in prot["items"] if i["status"] == "NOT_APPLIED")
            + " — a QA-passed stop/close that is not acknowledged + post-read verified is a hard FAIL.")})


def connector_auth_report(day: str, rows: list[dict], precheck_rows: list[dict] | None = None,
                          state: dict | None = None) -> dict:
    """QA Bot ruling 4: CONNECTOR_AUTH_BLOCKED detection + alert dedupe decision (read-only)."""
    pre = precheck_rows if precheck_rows is not None else CA.load_jsonl(Path(AUDIT_DIR) / f"precheck-{day}.jsonl")
    sigs = CA.auth_signals(rows, "audit") + CA.auth_signals(pre, "precheck")  # eToro connectors only (QA-08)
    ignored = CA.auth_signals(rows, "audit", etoro_only=False) + CA.auth_signals(pre, "precheck", etoro_only=False)
    ignored = [x for x in ignored if not CA.is_etoro(x.get("connectors"))]
    clk = MC.eod_clock(day)
    lo, hi = clk["eod_window_start"], clk["day_end"]

    def _in_night(ts):
        t = CA._parse(ts)
        return t is not None and lo <= t <= hi
    night = [x for x in sigs if _in_night(x.get("ts_il"))]
    goods = CA.good_reads(rows, pre)
    _t0 = datetime(1970, 1, 1, tzinfo=IL)
    last_sig = max((CA._parse(x.get("ts_il")) or _t0 for x in sigs), default=_t0)
    last_good = max((CA._parse(t) or _t0 for t in goods), default=_t0)
    blocked_now = bool(sigs) and not (goods and last_good > last_sig)
    recovered = bool(goods) and (not sigs or last_good > last_sig)
    st = state if state is not None else CA.read_json(_state_path(), {})
    ev = CA.evaluate(day, blocked_now, recovered, st)
    connectors = sorted({c for x in sigs for c in x.get("connectors", []) if c != "unknown"})
    return {"code": CA.CODE, "blocked": bool(sigs), "blocked_at_end_of_day": blocked_now, "night_blocked": bool(night),
            "signals": sigs, "connectors": connectors, "good_reads": goods, "recovered_today": recovered,
            "still_blocked": ev["still_blocked"], "alert_ofer": ev["alert_ofer"],
            "alert_already_sent_today": ev["alert_already_sent_today"], "next_state": ev["next_state"],
            "state_path": str(_state_path()), "flag_path": str(_flag_path()),
            "night_window": [lo.isoformat(), hi.isoformat()], "suppressed": [],
            "ignored_non_etoro_signals": ignored, "alert_sent_day": st.get("last_alert_day")}


def _auth_suppress(auth: dict, r: dict) -> bool:
    """QA-08: RUNTIME_ERROR is suppressed (listed, not AVOID) only when the eToro auth block is real (auth.blocked)
    AND either the row's own text is an eToro auth refusal, or the row is a connector-read script
    (CA.CONNECTOR_READ_SCRIPTS) inside an auth-blocked night window."""
    if str(r.get("deviation_code") or "") != "RUNTIME_ERROR" or not auth.get("blocked"):
        return False
    if CA.is_auth_refusal(CA._row_text(r)) and CA.is_etoro(CA.connectors_in(r)):
        return True
    if str(r.get("script") or "") not in CA.CONNECTOR_READ_SCRIPTS:
        return False
    if CA._RE_NON_ETORO.search(CA._row_text(r).lower()):  # QA30B-06: e.g. a Yahoo 401 stays an AVOID
        return False
    t = CA._parse(r.get("ts_il"))
    lo, hi = (CA._parse(x) for x in auth["night_window"])
    return bool(auth.get("night_blocked")) and t is not None and lo <= t <= hi


def qa_verdict_hard_fails(day: str, qa_dir: Path | None = None) -> list[dict]:
    """HIGH AVOID rows from QA Bot FAIL verdict files for the day carrying HARD_FAIL_CODES."""
    import re
    out, seen = [], set()
    ymd = day.replace("-", "")
    for f in sorted(Path(qa_dir or PLACE_QA_DIR).glob(f"qa-verdict-*{ymd}*.json")):
        try:
            v = json.loads(f.read_text())
        except Exception:
            continue
        if str(v.get("verdict", "")).upper() != "FAIL":
            continue
        codes = [c for c in (v.get("codes") or []) if c in HARD_FAIL_CODES]
        live = str(v.get("live") or "")
        syms = v.get("symbols") or re.findall(r"\b([A-Z]{1,6}) \d{6,}\+\d{6,}", live)
        for c in codes:
            for sym in (syms or [None]):
                if (c, sym) in seen:
                    continue
                seen.add((c, sym))
                out.append({"tag": "AVOID", "action": "PLACE", "symbol": sym, "deviation_code": c,
                            "severity": "HIGH", "hard_fail": True, "source": str(f),
                            "rationale": f"{c}: {HARD_FAIL_CODES[c]} (QA Bot {v.get('phase') or ''} FAIL {f.name}: {live})"
                                         + (" | Ofer KEEP = position decision only; deviation stands" if c == "DUPLICATE_PLACE" else "")})
    return out


def _row_codes(r: dict) -> set[str]:
    d = r.get("details") or {}
    out = {r.get("deviation_code"), d.get("reason_code"), d.get("reason"), r.get("reason")}
    for q in (r.get("qa_reasons") or []):
        out.add(q)
    return {str(c) for c in out if c}


def is_protective_reject(r: dict) -> bool:
    """QA Bot 2026-10-21 re-review: ONLY true protective refusals (instrument guard refusal,
    ID_SYMBOL_MISMATCH, stale cross-book fail-closed). GATE_OK codes are NOT protective."""
    return protective_code(r) is not None


def protective_code(r: dict) -> str | None:
    for c in _row_codes(r):
        for k in PROTECTIVE_REJECT_CODES:
            if c.upper() == k or c.upper().startswith(k):
                return k
    return None


def is_gate_ok_reject(r: dict) -> bool:
    """QA Bot 2026-10-20: INSUFFICIENT_CASH / GATE_OK / any GATE_OK code -> gate said no (KEEP),
    never a QA FAIL headline, never protective_reject."""
    codes = _row_codes(r)
    known = "INSUFFICIENT_CASH" in codes or gate_ok_code(r) is not None or any(
        classify_skip_code(c) == "GATE_OK" for c in codes if str(c).upper() != "GATE_OK")
    return not is_protective_reject(r) and known   # a bare self-declared 'GATE_OK' label is not enough


def gate_only_code(r: dict) -> str | None:
    """gate_ok_code minus true protective codes (those count in protective_reject instead)."""
    return None if is_protective_reject(r) else gate_ok_code(r)


RVOL_BUCKETS = ("<0.7", "0.7-1.0", ">1.0", "unknown")


def rvol_bucket(v) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "unknown"
    return "<0.7" if x < 0.7 else ("0.7-1.0" if x <= 1.0 else ">1.0")


def _all_rows(audit_dir: Path | None = None) -> list[dict]:
    rows = []
    for f in sorted(Path(audit_dir or AUDIT_DIR).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _pnl(r: dict):
    for k in ("netProfit", "pnl", "realized_pnl", "pnl_est"):
        v = r.get(k, (r.get("details") or {}).get(k))
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def rvol_outcome_scoring(day_rows: list[dict], history: list[dict] | None = None) -> dict:
    """Aggregate-only outcome scoring of the day's VCP fills by entry RVOL bucket (no gate).

    Entry RVOL = FILL.rvol_at_entry, else same-day screener BUY pack row details.rvol.
    Outcome = later close FILL/ACTION rows (same positionId) netProfit, if any.
    """
    pack_rvol = {}
    for r in day_rows:
        if r.get("script") == "momentum_screener.py" and r.get("event") == "ACTION" and r.get("action") == "BUY":
            d = r.get("details") or {}
            pack_rvol[r.get("symbol")] = (d.get("rvol"), d.get("setup"))
    closes = {}
    for r in history or []:
        pid = r.get("positionId") or (r.get("details") or {}).get("positionId")
        is_close = (r.get("type") == "FILL" and r.get("job") in ("close", "stop_loss", "take_profit")) or (
            r.get("event") in ("ACTION", "FILL") and str(r.get("action") or "").startswith("CLOSE"))
        p = _pnl(r)
        if pid and is_close and p is not None:
            closes[str(pid)] = closes.get(str(pid), 0.0) + p
    out = {b: {"fills": 0, "symbols": [], "closed": 0, "wins": 0, "losses": 0, "net_pnl": 0.0} for b in RVOL_BUCKETS}
    for r in day_rows:
        if not (r.get("event") == "FILL" and (r.get("action") or "BUY") == "BUY"):
            continue
        d = r.get("details") or {}
        rv = r.get("rvol_at_entry", d.get("rvol_at_entry"))
        setup = d.get("setup")
        if rv is None or setup is None:
            prv, pset = pack_rvol.get(r.get("symbol"), (None, None))
            rv = prv if rv is None else rv
            setup = setup or pset
        if setup and setup != "VCP_SETUP":
            continue
        if setup is None and "VCP" not in str(r.get("rationale") or ""):
            continue
        b = out[rvol_bucket(rv)]
        b["fills"] += 1
        b["symbols"].append(r.get("symbol"))
        pid = d.get("positionId") or r.get("positionId")
        if pid is not None and str(pid) in closes:
            p = closes[str(pid)]
            b["closed"] += 1
            b["wins" if p > 0 else "losses"] += 1
            b["net_pnl"] = round(b["net_pnl"] + p, 2)
    for b in out.values():
        b["win_rate"] = round(b["wins"] / b["closed"], 4) if b["closed"] else None
    return {"buckets": out, "note": "aggregate only; no gate (QA Bot 2026-10-20)"}


def gate_ok_code(r: dict) -> str | None:
    for c in _row_codes(r):
        for k in GATE_OK_CODES:
            if c == k or c.startswith(k):
                return k
    return None


def is_rebalance_dry_run(r: dict) -> bool:
    d = r.get("details") or {}
    src = d.get("source") or r.get("source")
    if src != "rebalance" and r.get("script") != "momentum_rebalance.py":
        return False
    mode = d.get("mode")
    return bool(d.get("dry_run")) or mode in (None, "dryrun")


def skip_row_audit(rows: list[dict]) -> dict:
    """SKIP-row accounting (QA Bot 2026-10-21). Returns gate_ok counts, protective count,
    KEEP entries, AVOID entries (MISSING_SKIP_ROW + ungated SKIPs)."""
    packs: dict[str, list[str]] = {}
    for r in rows:
        if r.get("script") == "momentum_screener.py" and r.get("event") == "ACTION" and r.get("action") == "BUY":
            lst = packs.setdefault(r.get("run_id"), [])
            if r.get("symbol") and r["symbol"] not in lst:
                lst.append(r["symbol"])
    skips = [r for r in rows if r.get("event") == "SKIP"]
    skip_keys = {(row_screener_run_id(r), base_symbol_of(r.get("symbol"))) for r in skips}
    placed = placed_symbols(rows)  # base tickers
    gate_ok, protective, keep, avoid, seen = Counter(), 0, [], [], set()
    for r in skips:
        code = str(r.get("reason_code") or (r.get("details") or {}).get("reason_code") or "").upper()
        # QA fixes3: only the reason code decides; a self-declared gate label on an unknown
        # code never counts (-> SKIP_UNGATED)
        cls = classify_skip_code(code)
        key = (row_screener_run_id(r), base_symbol_of(r.get("symbol")))
        if key in seen:
            continue
        seen.add(key)
        if cls == "GATE_OK":
            gate_ok[code] += 1
        elif cls == "PROTECTIVE_REJECT":  # QA 2026-10-21: separate from GATE_OK, never double-counted
            protective += 1
        if cls in ("GATE_OK", "PROTECTIVE_REJECT", "INTENTIONAL_SKIP"):
            keep.append({"tag": "KEEP", "action": "SKIP", "symbol": r.get("symbol"), "rationale": r.get("rationale"),
                         "deviation_code": code, "gate": cls, "run_id": r.get("run_id")})
        else:
            avoid.append({"tag": "AVOID", "action": "SKIP", "symbol": r.get("symbol"), "deviation_code": "SKIP_UNGATED",
                          "severity": "MEDIUM", "run_id": r.get("run_id"),
                          "rationale": f"SKIP {r.get('symbol')} reason {code or '?'} is not a known GATE_OK / protective / intentional code: "
                                       f"{r.get('rationale')}"})
    missing = []
    for rid, syms in packs.items():
        for s in syms:
            if base_symbol_of(s) in placed or (rid, base_symbol_of(s)) in skip_keys:
                continue
            missing.append({"run_id": rid, "symbol": s})
            avoid.append({"tag": "AVOID", "action": "PACK_BUY", "symbol": s, "deviation_code": "MISSING_SKIP_ROW",
                          "severity": "MEDIUM", "run_id": rid,
                          "rationale": f"pack BUY {s} (run {rid}) has neither a FILL/placed row nor a SKIP row"})
    return {"gate_ok_codes": dict(gate_ok), "protective_reject": protective, "keep": keep, "avoid": avoid,
            "missing": missing, "skip_rows": len(skips), "packs": packs}


def eod_ownership_report(rows: list[dict], report: dict) -> dict:
    """BACKUP_TAKEOVER / PRIMARY_DEFERRED rows (2026-10-22) -> counts + WATCH lesson.

    Codes are 'EVENT:REASON' from eod_miss_check.OWNERSHIP_CODES. A legitimate failover is not a
    deviation (no AVOID, no change to day_verdict); a row with an unmapped reason is counted under
    'EVENT:UNMAPPED_REASON' and flagged WATCH, never folded into UNSPECIFIED.
    """
    own = [r for r in rows if r.get("event") in OWNERSHIP_EVENTS]
    codes: Counter = Counter()
    unmapped = []
    for r in own:
        c = ownership_code(r)
        if c is None:
            c = f"{r.get('event')}:UNMAPPED_REASON"
            unmapped.append({"ts_il": r.get("ts_il"), "event": r.get("event"), "reason": r.get("reason"),
                             "caller": r.get("caller")})
        codes[c] += 1
    takeovers = [r for r in own if r.get("event") == "BACKUP_TAKEOVER"]
    deferred = [r for r in own if r.get("event") == "PRIMARY_DEFERRED"]
    proceeds = [r for r in own if r.get("event") == "PRIMARY_PROCEEDS"]
    steals = [r for r in own if r.get("stale_steal")]
    # Owner rows = rows whose writer went on to run the chain. With the owner lock (QA F1) a second
    # owner row is only legitimate when it records a stale-lock steal (F2); anything else = conflict.
    owner_rows = sorted((r for r in own if r.get("event") in OWNER_EVENTS), key=lambda r: str(r.get("ts_il") or ""))
    conflicts = [r for r in owner_rows[1:] if not r.get("stale_steal")]
    # N1: rows carry run_tag, so a double proceed by the SAME routine is a conflict too.
    scr_rows = sorted((r for r in own if r.get("event") == "SCREENER_LOCK"), key=lambda r: str(r.get("ts_il") or ""))
    scr_conflicts = [r for r in scr_rows[1:] if not r.get("stale_steal")]
    # N3: owner died before place — recorded watchdog rows + recomputed from tonight's rows.
    pw_rows = [r for r in own if r.get("event") == "EOD_PLACE_WATCH"]
    try:
        day = next((str(r.get("ts_il"))[:10] for r in rows if r.get("ts_il")), None)
        today = datetime.now(tz=IL)
        eval_now = today if day == today.strftime("%Y-%m-%d") else (
            MC.eod_clock(day)["day_end"] if day else today)  # IL end of day (was fixed +03:00)
        pw = place_watch(rows, eval_now, place_lock_dir=AUDIT_DIR / "place_locks")
    except Exception as e:  # never break feedback
        pw = {"alert": False, "alerts": [], "error": str(e)}
    pw_alerts = {(a["code"], a["screener_run_id"]) for a in pw.get("alerts", [])}
    pw_alerts |= {(r.get("reason"), r.get("screener_run_id")) for r in pw_rows}
    report["counts"]["eod_ownership_codes"] = dict(codes)
    report["counts"]["backup_takeover"] = len(takeovers)
    report["counts"]["primary_deferred"] = len(deferred)
    report["counts"]["primary_proceeds"] = len(proceeds)
    report["counts"]["eod_owner_stale_steals"] = len(steals)
    report["counts"]["eod_owner_conflicts"] = len(conflicts)
    report["counts"]["screener_locks"] = len(scr_rows)
    report["counts"]["screener_lock_conflicts"] = len(scr_conflicts)
    report["counts"]["eod_place_watch_alerts"] = len(pw_alerts)
    report["eod_ownership"] = {
        "rows": [{k: r.get(k) for k in ("ts_il", "event", "caller", "reason", "lock_result", "primary_last_seen",
                                        "owner_caller", "pm_first_ts", "stale_steal") if k in r} for r in own],
        "codes": dict(codes),
        "unmapped": unmapped,
        "stale_steals": [{"ts_il": r.get("ts_il"), "caller": r.get("caller"), **(r.get("stale_steal") or {})}
                         for r in steals],
        "conflicts": [{"ts_il": r.get("ts_il"), "event": r.get("event"), "caller": r.get("caller"),
                       "run_tag": r.get("run_tag")} for r in conflicts],
        "screener_lock_conflicts": [{"ts_il": r.get("ts_il"), "caller": r.get("caller"), "run_tag": r.get("run_tag")}
                                    for r in scr_conflicts],
        "place_watch": {"alerts": sorted([{"code": c, "screener_run_id": rid} for c, rid in pw_alerts],
                                         key=lambda x: (str(x["code"]), str(x["screener_run_id"]))),
                        "runs": pw.get("runs", []), "error": pw.get("error")},
        "known_codes": sorted(f"{e}:{c}" for e, m in OWNERSHIP_CODES.items() for c in m),
    }
    for r in steals:
        ss = r.get("stale_steal") or {}
        report["lessons"].append({"tag": "WATCH", "text": (
            f"EOD_OWNER_STALE_STEAL: {r.get('caller')} took the owner lock of {ss.get('from_caller')} at "
            f"{r.get('ts_il')} (no owner PM RUN_START within TTL; lock age {ss.get('age_s')}s).")})
    if scr_conflicts:
        report["lessons"].append({"tag": "WATCH", "text": (
            f"SCREENER_LOCK_CONFLICT: {len(scr_rows)} screener-lock takers tonight without a recorded stale steal — "
            "check for a double screener run.")})
    for code, rid in sorted(pw_alerts, key=lambda x: (str(x[0]), str(x[1]))):
        report["lessons"].append({"tag": "WATCH", "text": (
            f"{code}: screener run {rid} — {OWNERSHIP_CODES['EOD_PLACE_WATCH'].get(code, 'unmapped')}. "
            "Alert Ofer + QA Bot; never re-place without a fresh QA Bot place-QA.")})
    if conflicts:
        report["lessons"].append({"tag": "WATCH", "text": (
            f"EOD_OWNER_CONFLICT: {len(conflicts) + 1} owner rows tonight without a recorded stale steal ("
            + ", ".join(f"{r.get('event')}:{r.get('caller')}" for r in owner_rows) + ") — check for a double chain.")})
    if takeovers:
        t = takeovers[0]
        report["lessons"].append({
            "tag": "WATCH",
            "text": (f"BACKUP_TAKEOVER:{t.get('reason')} by {t.get('caller')} at {t.get('ts_il')} "
                     f"(primary_last_seen={t.get('primary_last_seen')}) — the primary (scheduled PM cron) had not started PM; "
                     "check scheduler lateness. Failover, not a deviation."),
        })
    if unmapped:
        report["lessons"].append({"tag": "WATCH", "text": f"{len(unmapped)} EOD ownership row(s) with unmapped reason: "
                                  + ", ".join(sorted({str(u['reason']) for u in unmapped}))})
    return report["eod_ownership"]


def schedule_report(day: str, rows: list[dict], report: dict) -> dict:
    """DST-M1 (2026-10-24b): eod_miss_check.schedule_alignment -> WATCH (MEDIUM, never a hard fail)."""
    sa = schedule_alignment(day, rows)
    report["schedule_alignment"] = sa
    report["counts"]["schedule_misaligned"] = len(sa.get("alerts", []))
    for a in sa.get("alerts", []):
        if any(x.get("deviation_code") == "SCHEDULE_MISALIGNED" for x in report["deviations_clear"]):
            break
        report["deviations_clear"].append({
            "tag": "WATCH", "action": "SCHEDULE_MISALIGNED", "deviation_code": "SCHEDULE_MISALIGNED",
            "severity": "MEDIUM", "direction": a.get("direction"), "rationale": a.get("text")})
        report["lessons"].append({"tag": "WATCH", "text": (
            f"SCHEDULE_MISALIGNED ({a.get('direction')}): {a.get('text')} Buys outside close-90m..close-1m are "
            "refused by place_lock (exit 6).")})
    report["counts"]["deviations"] = len(report["deviations_clear"])
    return sa


def build_report(day: str) -> dict:
    rows = load_day(day)
    auth = connector_auth_report(day, rows)
    all_actions = [r for r in rows if r.get("event") == "ACTION"]
    rebalance_dry = [r for r in all_actions if is_rebalance_dry_run(r)]
    actions = [r for r in all_actions if not is_rebalance_dry_run(r)]
    gate_ok_counts = Counter()
    deviations = [r for r in rows if r.get("event") == "DEVIATION" or r.get("deviation")]
    errors = [r for r in rows if r.get("event") == "ERROR"]
    protective = [r for r in actions if r.get("qa_verdict") == "FAIL" and is_protective_reject(r)]
    qa_fail = [r for r in actions if r.get("qa_verdict") == "FAIL"
               and not is_protective_reject(r) and not is_gate_ok_reject(r)]
    qa_pass = [r for r in actions if r.get("qa_verdict") == "PASS"]

    keep = []
    avoid = []
    gate_ok_seen = set()  # collapse duplicate INSUFFICIENT_CASH SKIP+DEVIATION
    for a in actions:
        code = a.get("deviation_code")
        g = gate_only_code(a)
        if g:
            gate_ok_counts[g] += 1
            key = (g, a.get("symbol"))
            if key not in gate_ok_seen:
                gate_ok_seen.add(key)
                keep.append({"tag": "KEEP", "action": a.get("action") or "SKIP", "symbol": a.get("symbol"),
                             "rationale": a.get("rationale") or GATE_OK_CODES[g], "deviation_code": g, "gate": "GATE_OK"})
            continue
        intentional_dwm_skip = (
            a.get("action") == "SKIP"
            and code == "DWM_STRENGTH_FAIL"
            and a.get("qa_verdict") == "PASS"
        )
        # QA Bot 2026-09-22: INSUFFICIENT_CASH = GATE_OK protective reject, not AVOID
        cash_gate_ok = code == "INSUFFICIENT_CASH" or "INSUFFICIENT_CASH" in _row_codes(a)
        # Intentional DWM SKIP (no place) = KEEP per QA Bot 2026-09-11
        if intentional_dwm_skip or cash_gate_ok or (
            a.get("qa_verdict") == "PASS" and not a.get("deviation")
        ):
            if cash_gate_ok:
                gate_ok_counts["INSUFFICIENT_CASH"] += 1
                key = ("INSUFFICIENT_CASH", a.get("symbol"))
                if key in gate_ok_seen:
                    continue
                gate_ok_seen.add(key)
                keep.append(
                    {
                        "tag": "KEEP",
                        "action": a.get("action") or "SKIP",
                        "symbol": a.get("symbol"),
                        "rationale": a.get("rationale") or "INSUFFICIENT_CASH protective gate on mirror A",
                        "deviation_code": "INSUFFICIENT_CASH",
                        "gate": "GATE_OK",
                    }
                )
                continue
            keep.append(
                {
                    "tag": "KEEP",
                    "action": a.get("action"),
                    "symbol": a.get("symbol"),
                    "rationale": a.get("rationale"),
                    "deviation_code": code,
                }
            )
            continue
        if a.get("deviation") or a.get("qa_verdict") == "FAIL":
            # Do not AVOID intentional DWM SKIP rows mis-flagged as deviation
            if intentional_dwm_skip or cash_gate_ok:
                continue
            if _auth_suppress(auth, a):
                auth["suppressed"].append({"deviation_code": "RUNTIME_ERROR", "ts_il": a.get("ts_il"),
                                           "script": a.get("script"), "rationale": a.get("rationale")})
                continue
            avoid.append(
                {
                    "tag": "AVOID",
                    "action": a.get("action"),
                    "symbol": a.get("symbol"),
                    "rationale": a.get("rationale"),
                    "deviation_code": code,
                    "qa_reasons": a.get("qa_reasons"),
                }
            )

    for d in deviations:
        if is_rebalance_dry_run(d):
            continue
        g = gate_only_code(d)
        if g:
            key = (g, d.get("symbol"))
            if key not in gate_ok_seen:
                gate_ok_seen.add(key); gate_ok_counts[g] += 1
                keep.append({"tag": "KEEP", "action": "DEVIATION", "symbol": d.get("symbol"), "rationale": d.get("rationale"),
                             "deviation_code": g, "gate": "GATE_OK"})
            continue
        if d.get("deviation_code") == "DWM_STRENGTH_FAIL" and (
            "blocked before place" in str(d.get("rationale") or "").lower()
            or "SKIP" in str(d.get("rationale") or "")
        ):
            # Process note only — intentional skip already KEEP via ACTION
            continue
        # QA Bot 2026-09-22: cash gate is protective, not playbook AVOID
        if d.get("deviation_code") == "INSUFFICIENT_CASH":
            key = ("INSUFFICIENT_CASH", d.get("symbol"))
            if key not in gate_ok_seen:
                gate_ok_seen.add(key)
                keep.append(
                    {
                        "tag": "KEEP",
                        "action": "DEVIATION",
                        "symbol": d.get("symbol"),
                        "rationale": d.get("rationale"),
                        "deviation_code": "INSUFFICIENT_CASH",
                        "gate": "GATE_OK",
                    }
                )
            continue
        if _auth_suppress(auth, d):
            auth["suppressed"].append({"deviation_code": "RUNTIME_ERROR", "ts_il": d.get("ts_il"),
                                       "script": d.get("script"), "rationale": d.get("rationale")})
            continue
        avoid.append(
            {
                "tag": "AVOID",
                "action": "DEVIATION",
                "symbol": d.get("symbol"),
                "rationale": d.get("rationale"),
                "deviation_code": d.get("deviation_code"),
                "severity": d.get("severity"),
            }
        )

    skip_mode = day >= SKIP_ROWS_FROM
    skip_info = None
    if skip_mode:
        skip_info = skip_row_audit(rows)
        gate_ok_counts = Counter(skip_info["gate_ok_codes"])
        protective = [None] * skip_info["protective_reject"]
        have_keep = {(k.get("deviation_code"), k.get("symbol")) for k in keep}
        keep.extend(k for k in skip_info["keep"] if (k["deviation_code"], k["symbol"]) not in have_keep)
        avoid.extend(skip_info["avoid"])

    codes = Counter(
        (x.get("deviation_code") or "UNKNOWN")
        for x in avoid
        if x.get("deviation_code")
    )

    report = {
        "schemaVersion": "1.0",
        "portfolio": "Momentum-HHHGDTJ",
        "day": day,
        "asOf": datetime.now(tz=IL).isoformat(),
        "counts": {
            "audit_rows": len(rows),
            "actions": len(actions),
            "rebalance_dry_run_rows": len(rebalance_dry),
            "gate_ok_codes": dict(gate_ok_counts),
            "qa_pass_actions": len(qa_pass),
            "qa_fail_actions": len(qa_fail),
            "protective_reject": len(protective),
            "deviations": len(deviations),
            "errors": len(errors),
            "keep": len(keep),
            "avoid": len(avoid),
        },
        "strategy_aligned": keep,
        "deviations_clear": avoid,
        "top_deviation_codes": codes.most_common(10),
        "lessons": [],
        "qa_bot": "498c78db-a027-4f2c-8126-3c2be6f0a4bb",
    }
    report["skip_rows"] = (
        {"mode": "skip_rows", "from": SKIP_ROWS_FROM, "skip_rows": skip_info["skip_rows"],
         "missing_skip_rows": skip_info["missing"], "packs": skip_info["packs"]}
        if skip_mode else {"mode": "legacy_actions", "from": SKIP_ROWS_FROM}
    )
    report["counts"]["missing_skip_rows"] = len(skip_info["missing"]) if skip_mode else 0

    # ≤3 lessons
    if keep:
        report["lessons"].append(
            {
                "tag": "KEEP",
                "text": f"{len(keep)} actions matched playbook with rationale + QA PASS",
            }
        )
    if avoid:
        top = codes.most_common(1)[0][0] if codes else "UNSPECIFIED"
        report["lessons"].append(
            {
                "tag": "AVOID",
                "text": f"{len(avoid)} deviations; top code={top}. Do not repeat without explicit playbook change.",
            }
        )
    if not rows:
        report["lessons"].append(
            {
                "tag": "WATCH",
                "text": "No audit rows today — confirm EOD routines ran or NYSE holiday skip.",
            }
        )
    _now = datetime.now(tz=IL)  # 'tonight' = the report day: live now if today, else that day's IL end
    miss, miss_status = is_miss(_now if day == _now.strftime("%Y-%m-%d") else MC.eod_clock(day)["day_end"])
    # Standing gate (QA Bot 2026-09-11/23): HIGH AVOID iff no screener ACTION ≤ screener deadline
    # (scheduled PM+10m: 21:50 IL from 2026-10-26, any close; legacy close-10m before). Early/manual EOD counts.
    # Catch-up after the deadline never clears a true miss. A late screener cron when an earlier
    # in-deadline ACTION exists → soft SCHEDULED_2245_LATE only (stable code ID; name kept).
    clk = MC.eod_clock(day) if day else MC.eod_clock(datetime.now(tz=IL))  # NYSE-close-derived (DST fix)
    by_2250 = screener_actions_by_deadline(day)  # deadline = scheduled PM+10m (21:50 IL)
    first_by_2250 = None
    for a in by_2250:
        ts = a.get("ts_il")
        if ts and (first_by_2250 is None or ts < first_by_2250):
            first_by_2250 = ts
    # NYSE session of the REPORT day (was: today's real weekday, so a weekend re-run of a weekday report
    # never flagged a miss; 2026-10-24b DST-M2: holidays are not misses either)
    true_miss = len(by_2250) == 0 and bool(clk.get("is_session", datetime.fromisoformat(clk["day"]).weekday() < 5))

    # First evening ACTION (EOD window, close-2h .. day end) for hygiene / soft late flag
    first_action_ts = None
    for a in (miss_status.get("actions") or []):
        ts = a.get("ts_il")
        if not ts:
            continue
        if first_action_ts is None or ts < first_action_ts:
            first_action_ts = ts
    # Also consider by_2250 actions (may be earlier than T22-only miss_status)
    if first_by_2250 and (first_action_ts is None or first_by_2250 < first_action_ts):
        first_action_ts = first_by_2250

    scheduled_2245_late = False
    if first_by_2250 and first_action_ts:
        # Soft: early ACTION existed, but the first scheduled-window (PM+5m) cron action was late —
        # only flag soft if we also saw an ACTION after late_cron (PM+7m; catch-up/cron) AND
        # the in-deadline ACTION was before the scheduled window (scheduled PM; manual early).
        try:
            fa = MC.parse_il(first_by_2250)
            if fa is not None and fa < clk["pm_scheduled"]:  # before the scheduled window (21:40 IL)
                # Manual/early satisfied gate; check if scheduled window also produced ACTION
                post = [
                    a for a in (miss_status.get("actions") or [])
                    if a.get("ts_il") and (MC.parse_il(a["ts_il"]) or fa) >= clk["pm_scheduled"]
                ]
                # Soft hygiene only when cron/catch-up ran at/after late_cron despite an early ACTION
                for a in post:
                    try:
                        dt = MC.parse_il(a["ts_il"])
                        if dt is not None and dt >= clk["late_cron"]:  # 21:47 IL
                            scheduled_2245_late = True
                            break
                    except Exception:
                        pass
        except Exception:
            pass

    report["eod_screener_miss"] = {
        "miss": miss,
        **miss_status,
        "actions_by_2250": [
            {"ts_il": a.get("ts_il"), "action": a.get("action"), "symbol": a.get("symbol")}
            for a in by_2250
        ],
        "true_miss_no_action_by_2250": true_miss,
        "first_action_ts": first_action_ts,
        "scheduled_2245_late": scheduled_2245_late,
        "gate": f"EOD_SCREENER_MISSED iff no screener ACTION ≤{MC.hhmm(clk['screener_deadline'])} IL "
                f"(scheduled PM+10m); early/manual counts",
        "eod_clock": MC.eod_clock_json(clk["day"]),
    }

    already_miss = any(
        x.get("deviation_code") == "EOD_SCREENER_MISSED" for x in report["deviations_clear"]
    )
    already_soft = any(
        x.get("deviation_code") == "SCHEDULED_2245_LATE" for x in report["deviations_clear"]
    )

    if true_miss and not already_miss and auth.get("night_blocked"):
        # QA Bot ruling 4: an auth-blocked night is CONNECTOR_AUTH_BLOCKED (ops), not EOD_SCREENER_MISSED
        auth["suppressed"].append({"deviation_code": "EOD_SCREENER_MISSED", "ts_il": None, "script": None,
                                   "rationale": f"no screener ACTION <= {MC.hhmm(clk['screener_deadline'])} IL "
                                                "on an auth-blocked night"})
        report["eod_screener_miss"]["scheduled_miss_avoid"] = False
        report["eod_screener_miss"]["suppressed_by"] = CA.CODE
    elif true_miss and not already_miss:
        report["deviations_clear"].append(
            {
                "tag": "AVOID",
                "action": "EOD_SCREENER_MISSED",
                "rationale": (
                    f"No momentum_screener ACTION (BUY/HALT/SKIP) by {MC.hhmm(clk['screener_deadline'])} IL (scheduled PM+10m)"
                    + (f" (first later ACTION {first_action_ts})" if first_action_ts else "")
                    + ". Catch-up does not clear this HIGH AVOID."
                ),
                "deviation_code": "EOD_SCREENER_MISSED",
                "severity": "HIGH",
            }
        )
        report["lessons"].append(
            {
                "tag": "AVOID",
                "text": f"EOD_SCREENER_MISSED — no ACTION ≤{MC.hhmm(clk['screener_deadline'])} IL (scheduled PM+10m); catch up immediately; catch-up never clears this AVOID.",
            }
        )
        report["counts"]["deviations"] = report["counts"].get("deviations", 0) + 1
        report["counts"]["avoid"] = len(report["deviations_clear"])
        report["eod_screener_miss"]["scheduled_miss_avoid"] = True
    elif scheduled_2245_late and not already_soft and not true_miss:
        report["deviations_clear"].append(
            {
                "tag": "WATCH",
                "action": "SCHEDULED_2245_LATE",
                "rationale": (
                    f"Screener cron/catch-up ran at/after {MC.hhmm(clk['late_cron'])} IL (scheduled PM+7m) but an earlier "
                    f"ACTION ≤{MC.hhmm(clk['screener_deadline'])} IL already satisfied the miss gate "
                    f"(first in-deadline ACTION: {first_by_2250}). Soft hygiene only."
                ),
                "deviation_code": "SCHEDULED_2245_LATE",
                "severity": "LOW",
            }
        )
        report["lessons"].append(
            {
                "tag": "WATCH",
                "text": (f"SCHEDULED_2245_LATE — screener cron late but an early/manual ACTION "
                         f"≤{MC.hhmm(clk['screener_deadline'])} IL (scheduled PM+10m) already cleared the miss gate."),
            }
        )
        # Soft WATCH does not bump HIGH avoid counts the same way; still list under deviations_clear
        report["eod_screener_miss"]["scheduled_miss_avoid"] = False
        report["counts"]["avoid"] = len(
            [x for x in report["deviations_clear"] if x.get("tag") == "AVOID"]
        )
    else:
        report["eod_screener_miss"]["scheduled_miss_avoid"] = False

    # QA Bot ruling 3 (2026-10-30a): protective actions from ACK rows + post-read
    prot = protective_report(day, rows)
    report["protective_actions"] = prot
    report["counts"]["protective_applied"] = prot["applied"]
    report["counts"]["protective_not_applied"] = prot["not_applied"]
    report["counts"]["protective_lock_only"] = prot["lock_only"]
    apply_protective(report, prot)
    report["counts"]["keep"] = len(report["strategy_aligned"])
    # QA Bot ruling 4 (2026-10-30a): CONNECTOR_AUTH_BLOCKED = ops HIGH, never a trading FAIL
    report["connector_auth"] = {k: v for k, v in auth.items() if k != "next_state"}
    report["alert_ofer"] = bool(auth["alert_ofer"])
    if report["alert_ofer"]:  # one short English line for the 22:05 routine to send verbatim (QA-11)
        report["connector_auth"]["alert_message"] = (
            f"Momentum {day}: eToro connector auth blocked ({', '.join(auth['connectors']) or 'eToro'}); "
            "reads refused, runs failed closed, no orders. Please fix the connector auth (one method per connector). "
            "The next good PM run re-checks every SL/TP.")
    report["counts"]["connector_auth_signals"] = len(auth["signals"])
    report["counts"]["auth_suppressed"] = len(auth["suppressed"])
    if auth["blocked"] or auth["still_blocked"]:
        report["deviations_clear"].append({
            "tag": "OPS", "action": CA.CODE, "symbol": None, "deviation_code": CA.CODE, "severity": "HIGH",
            "category": "ops", "hard_fail": False, "connectors": auth["connectors"],
            "rationale": (f"connector read refused for auth ({len(auth['signals'])} signal(s); connectors "
                          f"{', '.join(auth['connectors']) or 'unknown'}"
                          + ("" if auth["blocked"] else "; still blocked from an earlier day, no good read yet")
                          + "). Runs failed closed; suppressed: "
                          + (", ".join(sorted({s['deviation_code'] for s in auth['suppressed']})) or "none")
                          + ". Not a trading FAIL.")})
        report["lessons"].append({"tag": "WATCH", "text": (
            f"{CA.CODE}: fix the connector auth (one auth method per connector). alert_ofer="
            f"{report['alert_ofer']} (once per day until reads recover)."
            + (" Next good PM run: FULL_RISK_RECHECK_REQUIRED (re-check every SL and TP)." if auth["night_blocked"] else ""))})
    report["connector_auth"]["full_risk_recheck_required"] = bool(auth["night_blocked"]) or CA.recheck_status(_flag_path())["required"]
    if report["connector_auth"]["full_risk_recheck_required"] and not auth["blocked"] and auth["recovered_today"]:
        report["lessons"].append({"tag": "WATCH", "text": (
            "FULL_RISK_RECHECK_PENDING: reads recovered but every SL/TP re-check is not cleared yet "
            "(python -m momentum_qa.connector_auth clear-recheck).")})

    # Hard-fail codes from audit rows + QA verdict files (QA Bot 2026-10-15)
    have = {(x.get("deviation_code"), x.get("symbol")) for x in report["deviations_clear"]}
    for x in report["deviations_clear"]:
        if x.get("deviation_code") in HARD_FAIL_CODES:
            x["severity"], x["hard_fail"] = "HIGH", True
    qa_hf = qa_verdict_hard_fails(day)
    for x in qa_hf:
        if (x["deviation_code"], x["symbol"]) not in have:
            report["deviations_clear"].append(x)
    qa_fail_files = sorted({x["source"] for x in qa_hf})
    report["counts"]["qa_fail_verdicts"] = len(qa_fail_files)
    report["counts"]["qa_fail_actions"] = report["counts"].get("qa_fail_actions", 0) + len(qa_fail_files)
    hard = [x for x in report["deviations_clear"] if x.get("hard_fail")]
    report["hard_fail"] = bool(hard)
    report["day_verdict"] = "FAIL" if hard else "PASS"
    report["counts"]["hard_fail_deviations"] = len(hard)
    if hard:
        report["lessons"] = [L for L in report["lessons"] if L.get("tag") != "KEEP" or "QA PASS" not in L.get("text", "")]
        report["lessons"].insert(0, {"tag": "AVOID", "text": "HARD FAIL: " + ", ".join(sorted({f"{x['deviation_code']}:{x.get('symbol')}" for x in hard}))
                                    + " — never reuse a QA verdict; place_lock acquire before every place-trade. Ofer KEEP is a position decision only."})
        for k in report["strategy_aligned"]:
            if k.get("action") == "BUY" and any(k.get("symbol") == x.get("symbol") for x in hard):
                k["note"] = "first fill KEEP; duplicate fill scored as HIGH deviation"
    from collections import Counter as _Counter
    report["top_deviation_codes"] = _Counter(
        (x.get("deviation_code") or "UNKNOWN")
        for x in report["deviations_clear"]
        if x.get("deviation_code")
    ).most_common(10)
    report["counts"]["avoid"] = len(
        [x for x in report["deviations_clear"] if x.get("tag") == "AVOID"]
    )
    report["counts"]["deviations"] = len(report["deviations_clear"])
    eod_ownership_report(rows, report)
    schedule_report(day, rows, report)
    try:
        report["vcp_rvol_outcomes"] = rvol_outcome_scoring(rows, _all_rows())
    except Exception as e:  # aggregate only; never break feedback
        report["vcp_rvol_outcomes"] = {"error": str(e)}
    return report


def persist_connector_auth(day: str, report: dict) -> None:
    """Alert dedupe state + FULL_RISK_RECHECK_REQUIRED flag (written only by a non --stdout run)."""
    ca = report.get("connector_auth") or {}
    try:
        st = CA.read_json(_state_path(), {})
        ev = CA.evaluate(day, bool(ca.get("blocked_at_end_of_day")), bool(ca.get("recovered_today")), st)
        # QA-11: evaluate() never sets last_alert_day; only `connector_auth mark-alert-sent` (after SendToUser) does
        if ev["next_state"] != st:
            CA.persist_state(ev["next_state"], _state_path())
        if ca.get("night_blocked"):
            CA.set_recheck(day, f"{CA.CODE} on {day}", ca.get("connectors"), _flag_path())
    except Exception as e:  # never break feedback
        report.setdefault("connector_auth", {})["persist_error"] = str(e)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python -m momentum_qa.feedback_daily",
        description="Momentum daily feedback (KEEP vs AVOID) from momentum_audit/<day>.jsonl. "
                    f"From {SKIP_ROWS_FROM} gate_ok_codes / protective_reject come from SKIP rows and a pack "
                    "BUY with neither FILL/placed nor SKIP row is MISSING_SKIP_ROW.")
    ap.add_argument("day", nargs="?", help="IL date YYYY-MM-DD (default: today IL)")
    ap.add_argument("--out-dir", type=Path, default=None, help=f"output root (default {OUT_DIR})")
    ap.add_argument("--stdout", action="store_true", help="print the report JSON only; write no files")
    a = ap.parse_args(argv)
    if a.day:
        try:
            datetime.strptime(a.day, "%Y-%m-%d")
        except ValueError:
            ap.error(f"day must be YYYY-MM-DD, got {a.day!r}")
    return a


def main(day: str | None = None, *, out_root: Path | None = None, stdout_only: bool = False) -> int:
    day = day or datetime.now(tz=IL).strftime("%Y-%m-%d")
    report = build_report(day)
    if stdout_only:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    persist_connector_auth(day, report)
    out_dir = Path(out_root or OUT_DIR) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "daily_feedback.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary
    md = [
        f"# Momentum daily feedback | {day}",
        "",
        f"- Actions: {report['counts']['actions']} | QA PASS: {report['counts']['qa_pass_actions']} | QA FAIL: {report['counts']['qa_fail_actions']} | protective_reject: {report['counts'].get('protective_reject', 0)}",
        f"- Deviations: {report['counts']['deviations']} (HIGH hard-fail: {report['counts'].get('hard_fail_deviations', 0)}) | Errors: {report['counts']['errors']}",
        f"- Day verdict: **{report.get('day_verdict', 'PASS')}**",
        f"- Protective actions: applied {report['counts'].get('protective_applied', 0)} | NOT applied "
        f"{report['counts'].get('protective_not_applied', 0)} | lock-only {report['counts'].get('protective_lock_only', 0)}",
        f"- Connector auth: {'BLOCKED' if (report.get('connector_auth') or {}).get('still_blocked') else 'ok'}"
        f" | alert_ofer: {report.get('alert_ofer', False)}"
        f" | FULL_RISK_RECHECK_REQUIRED: {(report.get('connector_auth') or {}).get('full_risk_recheck_required', False)}",
        "",
        "## KEEP (aligned)",
    ]
    for k in report["strategy_aligned"][:20]:
        md.append(f"- `{k.get('action')}` {k.get('symbol')}: {k.get('rationale')}")
    if not report["strategy_aligned"]:
        md.append("- (none)")
    md.append("")
    md.append("## AVOID (deviations — clear)")
    for a in report["deviations_clear"][:30]:
        md.append(
            f"- **{a.get('deviation_code') or a.get('tag')}** `{a.get('action')}` {a.get('symbol')}: {a.get('rationale')}"
        )
    if not report["deviations_clear"]:
        md.append("- (none)")
    md.append("")
    md.append("## Lessons")
    for L in report["lessons"]:
        md.append(f"- **{L['tag']}**: {L['text']}")

    (out_dir / "daily_feedback.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_path), "counts": report["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    _a = parse_args()
    raise SystemExit(main(_a.day, out_root=_a.out_dir, stdout_only=_a.stdout))

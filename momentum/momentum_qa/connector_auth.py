"""Connector auth-block detection, alert dedupe state and the FULL_RISK_RECHECK_REQUIRED flag (2026-10-30a).

QA Bot ruling 4 (incident 2026-10-29: user-Momentum-HHHGDTJ and user-OfersClaw5 refused every read with
"The MCP request carries BOTH an Authorization header and an x-user-key header" (mixed auth, 422 not sent)).

CONNECTOR_AUTH_BLOCKED  severity HIGH, category ops. NOT a trading FAIL (never sets day_verdict FAIL).
  * Emitted by feedback_daily when any audit / precheck row of the day carries an auth refusal
    (is_auth_refusal: mixed auth, HTTP/status 401, Unauthorized, needs auth / needsAuth / needsGrant,
    not authenticated, authentication required, invalid/missing API or user key).
  * That night it suppresses EOD_SCREENER_MISSED and RUNTIME_ERROR (listed under connector_auth.suppressed,
    never silently dropped).
  * alert_ofer = true once per IL day while blocked, until reads recover (state file STATE_PATH).
  * The first blocked night sets FULL_RISK_RECHECK_REQUIRED (FLAG_PATH): the next good PM run must re-read
    every open position and re-check every SL and TP, then clear the flag with `clear-recheck`.

2026-10-30b (QA Bot FAIL 1 on 30a: QA-08, QA-09, QA-11):
  * Only eToro connectors count (ETORO_CONNECTORS: user-Momentum-HHHGDTJ, user-OfersClaw5, user-etoro). A signal
    needs an auth pattern AND a resolved eToro connector (explicit namespace name, keys/Classic/mirror read context,
    or a connector-read script). The bare word "unauthorized" is no longer a pattern ("Unauthorized instrument"
    never counts); an X / other connector "needsAuth" never counts.
  * recheck-status: a flag file that exists but cannot be parsed = REQUIRED (corrupt: true). Only a missing file is
    "not required".
  * clear-recheck refuses when 0 positions are parsed (NO_POSITIONS_PARSED), unless --confirm-empty-book AND the
    positions JSON explicitly carries an empty positions list.
  * evaluate() never records last_alert_day. `mark-alert-sent --day D` does, and the 22:05 feedback routine runs it
    only after SendToUser succeeded, so a failed send is retried by the next feedback run the same day.

2026-10-30c (QA Bot FAIL 2 on 30b: QA30B-05, QA30B-06, QA30B-07):
  * Attribution (QA30B-06) is tied to eToro connector CALLS only: an explicit namespace (user-Momentum-HHHGDTJ /
    user-OfersClaw5 / user-etoro), a keys / Classic-MCP / mirror read context, or an eToro API call marker in the
    row's own text (ETORO_CALL_MARKERS: "eToro Public API", "x-user-key", "get-my-positions-and-orders", ...).
    The script name alone (precheck / position_manager / open_gap_check / postfill_check) and the precheck slot no
    longer attribute anything: "HTTP 401 from query1.finance.yahoo.com" in position_manager.py or "Slack connector
    needsAuth" in precheck.py is not an eToro signal. A row whose text names a non-eToro service
    (NON_ETORO_SERVICES) and no explicit eToro namespace is never attributed. An eToro call marker in a Momentum
    script (CONNECTOR_READ_SCRIPTS) = user-Momentum-HHHGDTJ; elsewhere = user-etoro.
    (feedback_daily still uses the script only to decide RUNTIME_ERROR suppression on an auth-blocked night.)
  * mark-alert-sent (QA30B-07) accepts only a day <= today (IL). A future --day is never recorded: today is used
    (requested_day + clamped true in the output). last_alert_day never moves backwards.
  * clear-recheck (QA30B-05) needs a standard keys read (place_lock.keys_read_check: statusCode 200, account real,
    direct.positions, every item resolvable), else READ_UNTRUSTED. --confirm-empty-book is accepted only when that
    read is OK AND direct.positions is empty; the FULL_RISK_RECHECK_CLEARED row records confirm_empty_book.
    Routines never pass --confirm-empty-book (QA Bot / Ofer only; the v8 prompts forbid the empty-book override).
  * set-recheck --day must be YYYY-MM-DD and <= today (IL) (exit 4 otherwise).

CLI (read-only except set / clear-recheck / mark-alert-sent):
  python -m momentum_qa.connector_auth recheck-status          exit 0 = not required, 2 = REQUIRED (JSON on stdout)
  python -m momentum_qa.connector_auth set-recheck --day D --reason TEXT
  python -m momentum_qa.connector_auth clear-recheck --positions-json <fresh get-my-positions-and-orders <120s> \\
        --pm-out <position_manager --out json> [--run-id ID]
        exit 0 = cleared (flag renamed to FULL_RISK_RECHECK_REQUIRED.cleared-<ts>.json + FULL_RISK_RECHECK_CLEARED row)
        exit 4 = refused (positions stale, a position without SL > 0, TP not read, or a held symbol without PM row)
  python -m momentum_qa.connector_auth state                   print the alert state
  python -m momentum_qa.connector_auth mark-alert-sent --day D   record that Ofer's alert for IL day D was sent
        (exit 0; exit 4 on a bad day). Run ONLY after the send succeeded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
AUDIT_DIR = Path("/workspace/momentum_audit")
STATE_PATH = AUDIT_DIR / "connector_auth_state.json"
FLAG_PATH = AUDIT_DIR / "FULL_RISK_RECHECK_REQUIRED.json"
CODE = "CONNECTOR_AUTH_BLOCKED"
SUPPRESSES = ("EOD_SCREENER_MISSED", "RUNTIME_ERROR")
CONNECTORS = ("user-Momentum-HHHGDTJ", "user-OfersClaw5")
ETORO_CONNECTORS = ("user-Momentum-HHHGDTJ", "user-OfersClaw5", "user-etoro")
CONNECTOR_READ_SCRIPTS = ("momentum_qa/precheck.py", "momentum_qa/open_gap_check.py", "position_manager.py",
                          "momentum_qa/postfill_check.py")
EXIT_OK, EXIT_REQUIRED, EXIT_REFUSED = 0, 2, 4

AUTH_PATTERNS = [
    re.compile(p, re.I) for p in (
        r"mixed[\s_-]*auth",
        r"both an authorization header and an x-user-key",
        r"status(?:code)?\s*[=:]\s*401\b",
        r"\bhttp\s*401\b",
        r"\b401\s+unauthori[sz]ed\b",
        r"\bneeds[\s_-]?auth\b",
        r"\bneedsgrant\b",
        r"\bnot authenticated\b",
        r"\bauthentication (?:required|failed)\b",
        r"\b(?:invalid|missing|expired)\s+(?:api|user)[\s_-]?key\b",
    )
]


def is_auth_refusal(text) -> bool:
    t = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return any(p.search(t) for p in AUTH_PATTERNS)


def _row_text(r: dict) -> str:
    keep = {k: r.get(k) for k in ("error", "rationale", "reason", "details", "books_errors", "keys_mcp", "ack", "why")
            if r.get(k) is not None}
    return json.dumps(keep, ensure_ascii=False, default=str)


_RE_USER_ETORO = re.compile(r"\buser-etoro(?![\w-])")
_CLASSIC_CTX = ("user-ofersclaw5", "ofersclaw5", "classic mcp", "classic_book", "classic read", "classic_file",
                "classic-raw", "classic_raw")
_MOMENTUM_CTX = ("user-momentum-hhhgdtj", "momentum_keys", "keys_mcp", "keys mcp", "momentum keys")
ETORO_CALL_MARKERS = ("etoro public api", "x-user-key", "x-api-key", "get-my-positions-and-orders",
                      "public-api.etoro", "api.etoro.com", "etoro api", "etoro mcp")
NON_ETORO_SERVICES = ("yahoo", "yfinance", "polygon", "finnhub", "alpha vantage", "alphavantage", "slack", "teams",
                      "x connector", "twitter", "telegram", "whatsapp", "gmail", "google", "github", "atlassian",
                      "jira", "confluence", "databricks", "spinach", "tradingview", "stooq")
_EXPLICIT_NS = ("user-momentum-hhhgdtj", "user-ofersclaw5")
_RE_NON_ETORO = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in NON_ETORO_SERVICES) + r")\b")


def connectors_in(r: dict) -> list[str]:
    """eToro connectors a row refers to. 2026-10-30c QA30B-06: eToro connector CALLS only (explicit namespace,
    keys / Classic / mirror read context, or an eToro API call marker); never the script name alone."""
    t = _row_text(r).lower()
    explicit = any(k in t for k in _EXPLICIT_NS) or bool(_RE_USER_ETORO.search(t))
    if not explicit and _RE_NON_ETORO.search(t):
        return ["unknown"]
    out = []
    if any(k in t for k in _CLASSIC_CTX):
        out.append("user-OfersClaw5")
    if any(k in t for k in _MOMENTUM_CTX):
        out.append("user-Momentum-HHHGDTJ")
    if _RE_USER_ETORO.search(t) or "mirror 11630170" in t:
        out.append("user-etoro")
    if not out and any(k in t for k in ETORO_CALL_MARKERS):
        out.append("user-Momentum-HHHGDTJ" if str(r.get("script") or "") in CONNECTOR_READ_SCRIPTS else "user-etoro")
    return out or ["unknown"]


def is_etoro(connectors) -> bool:
    return any(c in ETORO_CONNECTORS for c in (connectors or []))


def _ts(r: dict) -> str | None:
    return r.get("ts_il") or r.get("at") or r.get("ts")


def _parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=IL)
    except Exception:
        return None


def auth_signals(rows: list[dict], source: str = "audit", etoro_only: bool = True) -> list[dict]:
    """Auth-refusal signals. etoro_only (default): only rows resolved to an eToro connector (QA-08)."""
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        txt = _row_text(r)
        if not is_auth_refusal(txt):
            continue
        if etoro_only and not is_etoro(connectors_in(r)):
            continue
        m = next((p.search(txt) for p in AUTH_PATTERNS if p.search(txt)), None)
        out.append({"ts_il": _ts(r), "source": source, "event": r.get("event") or r.get("slot"),
                    "script": r.get("script"), "connectors": connectors_in(r),
                    "match": m.group(0) if m else None, "deviation_code": r.get("deviation_code")})
    return out


def good_reads(rows: list[dict], precheck_rows: list[dict]) -> list[str]:
    """IL timestamps of reads that clearly succeeded (no auth text): PM / screener RUN_END, open_gap RUN_END exit 0,
    precheck rows without RAW_NOT_USABLE / error."""
    ts = []
    for r in rows:
        if is_auth_refusal(_row_text(r)):
            continue
        sc, ev = str(r.get("script") or ""), r.get("event")
        d = r.get("details") or {}
        if ev == "RUN_END" and sc == "position_manager.py":
            ts.append(_ts(r))
        elif ev == "RUN_END" and sc == "momentum_screener.py" and "FAIL_CLOSED" not in str(r.get("rationale") or ""):
            ts.append(_ts(r))
        elif ev == "RUN_END" and "open_gap" in sc and d.get("exit_code") == 0:
            ts.append(_ts(r))
    for r in precheck_rows:
        if not r.get("error") and "RAW_NOT_USABLE" not in (r.get("reasons") or []) and not is_auth_refusal(_row_text(r)):
            ts.append(_ts(r))
    return sorted(t for t in ts if t)


def load_jsonl(path: Path) -> list[dict]:
    out = []
    if not Path(path).exists():
        return out
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def _write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)


def evaluate(day: str, blocked_today: bool, recovered_today: bool, state: dict) -> dict:
    """Pure: alert decision + next state. still_blocked = blocked today, or blocked before and not recovered."""
    st = dict(state or {})
    still = blocked_today or (bool(st.get("blocked")) and not recovered_today)
    alert = still and st.get("last_alert_day") != day
    nxt = dict(st)
    if still:
        nxt["blocked"] = True
        nxt.setdefault("first_blocked_day", day)
        if not st.get("blocked"):
            nxt["first_blocked_day"] = day
        if blocked_today:
            nxt["last_blocked_day"] = day
        nxt.pop("recovered_day", None)  # QA-11: last_alert_day is set only by mark_alert_sent()
    elif st.get("blocked") and recovered_today:
        nxt["blocked"] = False
        nxt["recovered_day"] = day
    return {"still_blocked": still, "alert_ofer": alert,
            "alert_already_sent_today": still and st.get("last_alert_day") == day, "next_state": nxt}


def persist_state(next_state: dict, path: Path | None = None) -> None:
    _write_json(Path(path or STATE_PATH), next_state)


def _check_day(day) -> str:
    from datetime import date as _date
    if not isinstance(day, str) or _date.fromisoformat(day).isoformat() != day:
        raise ValueError(f"bad --day {day!r} (YYYY-MM-DD)")
    return day


def mark_alert_sent(day: str, path: Path | None = None, now=None) -> dict:
    """QA-11: record that the once-per-IL-day alert for `day` was delivered (run only after a successful send).
    QA30B-07: only a day <= today (IL) is recorded; a future day is replaced by today (clamped). Never backwards."""
    _check_day(day)
    now = now or datetime.now(tz=IL)
    today = now.astimezone(IL).date().isoformat()
    use = day if day <= today else today
    p = Path(path or STATE_PATH)
    st = read_json(p, {})
    st = st if isinstance(st, dict) else {}
    prev = st.get("last_alert_day")
    if not (isinstance(prev, str) and prev > use and prev <= today):
        st["last_alert_day"] = use
    st["last_alert_sent_ts"] = now.isoformat(timespec="seconds")
    st["last_alert_requested_day"] = day
    st["last_alert_clamped"] = use != day
    _write_json(p, st)
    return {**st, "requested_day": day, "recorded_day": st["last_alert_day"], "clamped": use != day}


def set_recheck(day: str, reason: str, connectors=None, path: Path | None = None, now=None) -> dict:
    _check_day(day)
    today = (now or datetime.now(tz=IL)).astimezone(IL).date().isoformat()
    if day > today:
        raise ValueError(f"set-recheck --day {day} is after today {today} (IL)")
    p = Path(path or FLAG_PATH)
    cur = read_json(p, None) or {"flag": "FULL_RISK_RECHECK_REQUIRED", "set_day": day, "nights": [],
                                 "rule": "next good PM run: re-read every open position and re-check every SL and TP, "
                                         "then `python -m momentum_qa.connector_auth clear-recheck`"}
    if day not in cur["nights"]:
        cur["nights"].append(day)
    cur["reason"] = reason
    cur["connectors"] = sorted(set(cur.get("connectors", [])) | set(connectors or []))
    _write_json(p, cur)
    return cur


def recheck_status(path: Path | None = None) -> dict:
    """QA-09: only a MISSING flag file means not required; an existing but unreadable / corrupt one = REQUIRED."""
    p = Path(path or FLAG_PATH)
    if not p.exists() and not p.is_symlink():
        return {"required": False, "flag_path": str(p), "flag": None, "corrupt": False}
    try:
        cur = json.loads(p.read_text())
        corrupt = not isinstance(cur, dict)
    except Exception as e:  # noqa: BLE001
        cur, corrupt = {"unreadable": f"{type(e).__name__}: {e}"}, True
    return {"required": True, "flag_path": str(p), "flag": cur, "corrupt": corrupt}


def _positions(obj) -> list[dict]:
    out = []

    def walk(o, inpos=False):
        if isinstance(o, dict):
            if inpos and any(k in o for k in ("positionId", "positionID", "instrumentId", "symbol")):
                out.append(o)
                return
            for k, v in o.items():
                walk(v, inpos or k.lower() in ("positions", "openpositions", "clientportfolio_positions"))
        elif isinstance(o, list):
            for v in o:
                walk(v, inpos)
    walk(obj)
    return out


def _first(d: dict, keys):
    for k in keys:
        if k in d:
            return True, d[k]
    return False, None


def clear_recheck(positions_obj, pm_rows, *, flag_path: Path | None = None, audit_dir: Path | None = None,
                  run_id: str | None = None, now=None, confirm_empty_book: bool = False) -> dict:
    """Clear the flag only if every open position has SL > 0 and a TP read, and a PM row exists for it.
    QA-09: 0 parsed positions never clears, unless confirm_empty_book and the JSON has an explicit empty list."""
    from momentum_qa import place_lock as pl
    from momentum_qa.instrument_map import base_symbol, cache_symbol_for_id
    st = recheck_status(flag_path)
    if not st["required"]:
        return {"ok": True, "cleared": False, "result": "NOT_REQUIRED", "problems": []}
    problems, checked = [], []
    try:
        pl.require_fresh_positions(positions_obj, now=now)
    except pl.PlaceLockError as e:
        problems.append({"code": e.code, "reason": e.msg})
    kr = pl.keys_read_check(positions_obj)  # 2026-10-30c QA30B-05: only a standard keys read re-checks the book
    if not kr["ok"]:
        problems.append({"code": "READ_UNTRUSTED", "read_check": kr["code"], "reason": kr["reason"]})
    pm_syms = {base_symbol(str(r.get("symbol"))) for r in (pm_rows if isinstance(pm_rows, list) else [])
               if isinstance(r, dict) and r.get("symbol")}
    for p in _positions(positions_obj):
        iid = p.get("instrumentId") or (p.get("market") or {}).get("instrumentId")
        mk = p.get("market") if isinstance(p.get("market"), dict) else {}
        sym = p.get("symbol") or mk.get("symbol") or p.get("symbolFull") or p.get("instrumentSymbol")
        if not sym and iid is not None:
            sym = cache_symbol_for_id(iid)
        sym = base_symbol(str(sym), iid) if sym else None
        has_sl, sl = _first(p, ("stopLossRate", "stop_loss", "stopLoss"))
        has_tp, tp = _first(p, ("takeProfitRate", "take_profit", "takeProfit"))
        pid = p.get("positionId") or p.get("positionID")
        checked.append({"symbol": sym, "positionId": pid, "sl": sl, "tp": tp})
        try:
            sl_ok = has_sl and sl is not None and float(sl) > 0
        except (TypeError, ValueError):
            sl_ok = False
        if not sl_ok:
            problems.append({"code": "SL_MISSING", "symbol": sym, "positionId": pid})
        if not has_tp:
            problems.append({"code": "TP_NOT_READ", "symbol": sym, "positionId": pid})
        if not sym:
            problems.append({"code": "SYMBOL_UNRESOLVED", "positionId": pid, "instrumentId": iid})
        elif sym not in pm_syms:
            problems.append({"code": "NO_PM_ROW", "symbol": sym, "positionId": pid})
    if not checked:
        found, _ = pl.position_entries(positions_obj)
        empty_ok = bool(kr["ok"]) and kr["positions"] == []
        if not (confirm_empty_book and empty_ok):
            problems.append({"code": "NO_POSITIONS_PARSED", "positions_list_found": found,
                             "keys_read_ok": bool(kr["ok"]), "confirm_empty_book": bool(confirm_empty_book),
                             "reason": "0 open positions parsed: refuse to clear (an empty / wrong-shaped read is "
                                       "not a re-check); a truly empty book needs a 200 keys read with an empty "
                                       "direct.positions AND --confirm-empty-book (QA Bot / Ofer only)"})
    if problems:
        return {"ok": False, "cleared": False, "result": "RECHECK_INCOMPLETE", "problems": problems, "checked": checked}
    fp = Path(st["flag_path"])
    stamp = datetime.now(tz=IL).strftime("%Y%m%d-%H%M%S")
    dest = fp.with_name(f"{fp.stem}.cleared-{stamp}.json")
    fp.replace(dest)
    try:
        from momentum_qa.audit import append_row, build_record, new_run_id
        append_row(build_record(run_id or new_run_id("riskrecheck"), "momentum_qa/connector_auth.py", {
            "event": "FULL_RISK_RECHECK_CLEARED", "flag": st["flag"], "checked": checked, "cleared_to": str(dest),
            "confirm_empty_book": bool(confirm_empty_book and not checked), "read_check": kr["code"],
            "rationale": f"every SL/TP re-checked on {len(checked)} open position(s) after an auth-blocked night"}),
            audit_dir)
    except Exception as e:
        print(f"connector_auth: audit row failed: {e}", file=sys.stderr)
    return {"ok": True, "cleared": True, "result": "CLEARED", "cleared_to": str(dest), "checked": checked, "problems": [],
            "confirm_empty_book": bool(confirm_empty_book and not checked)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m momentum_qa.connector_auth")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("recheck-status")
    sub.add_parser("state")
    ms = sub.add_parser("mark-alert-sent")
    ms.add_argument("--day", required=True)
    s = sub.add_parser("set-recheck")
    s.add_argument("--day", required=True)
    s.add_argument("--reason", required=True)
    c = sub.add_parser("clear-recheck")
    c.add_argument("--positions-json", required=True)
    c.add_argument("--pm-out", required=True)
    c.add_argument("--run-id")
    c.add_argument("--confirm-empty-book", action="store_true",
                   help="QA Bot / Ofer only, never a routine: a 200 keys read with an empty direct.positions list")
    a = ap.parse_args(argv)
    if a.cmd == "recheck-status":
        r = recheck_status()
        print(json.dumps(r, ensure_ascii=False))
        return EXIT_REQUIRED if r["required"] else EXIT_OK
    if a.cmd == "state":
        print(json.dumps(read_json(STATE_PATH, {}), ensure_ascii=False))
        return EXIT_OK
    if a.cmd == "mark-alert-sent":
        try:
            print(json.dumps({"ok": True, "state": mark_alert_sent(a.day)}, ensure_ascii=False))
            return EXIT_OK
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"ok": False, "result": "BAD_INPUT", "reason": str(e)}))
            return EXIT_REFUSED
    if a.cmd == "set-recheck":
        try:
            print(json.dumps(set_recheck(a.day, a.reason), ensure_ascii=False))
            return EXIT_OK
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"ok": False, "result": "BAD_INPUT", "reason": str(e)}))
            return EXIT_REFUSED
    from momentum_qa import place_lock as pl
    try:
        pos = pl._load_positions(a.positions_json)
        pm = json.loads(Path(a.pm_out).read_text())
    except Exception as e:
        print(json.dumps({"ok": False, "result": "BAD_INPUT", "reason": str(e)}))
        return EXIT_REFUSED
    r = clear_recheck(pos, pm, run_id=a.run_id, confirm_empty_book=a.confirm_empty_book)
    print(json.dumps(r, ensure_ascii=False, default=str))
    return EXIT_OK if r["ok"] else EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())

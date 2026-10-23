#!/usr/bin/env python3
"""Daily feedback loop: what matched strategy vs clear deviations."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from momentum_qa.eod_miss_check import (OWNER_EVENTS, OWNERSHIP_CODES, OWNERSHIP_EVENTS, is_miss, ownership_code,
                                        place_watch, screener_actions_by_deadline)
from momentum_qa.audit import PROTECTIVE_REJECT_CODES, base_symbol_of, classify_skip_code, placed_symbols, row_screener_run_id

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
}
PLACE_QA_DIR = AUDIT_DIR / "place_qa"


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
            datetime.fromisoformat(f"{day}T23:59:59+03:00") if day else today)
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
                     f"(primary_last_seen={t.get('primary_last_seen')}) — 22:40 primary had not started PM; "
                     "check scheduler lateness. Failover, not a deviation."),
        })
    if unmapped:
        report["lessons"].append({"tag": "WATCH", "text": f"{len(unmapped)} EOD ownership row(s) with unmapped reason: "
                                  + ", ".join(sorted({str(u['reason']) for u in unmapped}))})
    return report["eod_ownership"]


def build_report(day: str) -> dict:
    rows = load_day(day)
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
    miss, miss_status = is_miss()
    # Standing gate (QA Bot 2026-09-11/23): HIGH AVOID iff no screener ACTION ≤22:50 IL.
    # Early/manual EOD counts. Catch-up after 22:50 never clears a true miss.
    # Late 22:45 cron when an earlier ≤22:50 ACTION exists → soft SCHEDULED_2245_LATE only.
    by_2250 = screener_actions_by_deadline(day, 22, 50)
    first_by_2250 = None
    for a in by_2250:
        ts = a.get("ts_il")
        if ts and (first_by_2250 is None or ts < first_by_2250):
            first_by_2250 = ts
    true_miss = len(by_2250) == 0 and datetime.now(tz=IL).weekday() < 5

    # First evening ACTION (T21–T23) for hygiene / soft late flag
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
        # Soft: early ACTION existed, but first T22:45-window cron action was late —
        # only flag soft if we also saw a post-22:46 ACTION (catch-up/cron) AND
        # the ≤22:50 ACTION was before the scheduled window (manual early).
        try:
            fa = datetime.fromisoformat(first_by_2250)
            if fa.hour < 22 or (fa.hour == 22 and fa.minute < 40):
                # Manual/early satisfied gate; check if scheduled window also produced ACTION
                post = [
                    a for a in (miss_status.get("actions") or [])
                    if a.get("ts_il") and (
                        "T22:4" in a["ts_il"] or "T22:5" in a["ts_il"] or "T23:" in a["ts_il"]
                    )
                ]
                # Soft hygiene only when cron/catch-up ran after 22:46 despite early ACTION
                for a in post:
                    try:
                        dt = datetime.fromisoformat(a["ts_il"])
                        if dt.hour == 22 and dt.minute >= 47 or dt.hour >= 23:
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
        "gate": "EOD_SCREENER_MISSED iff no screener ACTION ≤22:50 IL; early/manual counts",
    }

    already_miss = any(
        x.get("deviation_code") == "EOD_SCREENER_MISSED" for x in report["deviations_clear"]
    )
    already_soft = any(
        x.get("deviation_code") == "SCHEDULED_2245_LATE" for x in report["deviations_clear"]
    )

    if true_miss and not already_miss:
        report["deviations_clear"].append(
            {
                "tag": "AVOID",
                "action": "EOD_SCREENER_MISSED",
                "rationale": (
                    "No momentum_screener ACTION (BUY/HALT/SKIP) by 22:50 IL"
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
                "text": "EOD_SCREENER_MISSED — no ACTION ≤22:50 IL; catch up immediately; catch-up never clears this AVOID.",
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
                    "22:45 cron/catch-up ran after 22:46 IL but an earlier ≤22:50 ACTION already "
                    f"satisfied the miss gate (first ≤22:50: {first_by_2250}). Soft hygiene only."
                ),
                "deviation_code": "SCHEDULED_2245_LATE",
                "severity": "LOW",
            }
        )
        report["lessons"].append(
            {
                "tag": "WATCH",
                "text": "SCHEDULED_2245_LATE — cron late but early/manual ACTION ≤22:50 already cleared miss gate.",
            }
        )
        # Soft WATCH does not bump HIGH avoid counts the same way; still list under deviations_clear
        report["eod_screener_miss"]["scheduled_miss_avoid"] = False
        report["counts"]["avoid"] = len(
            [x for x in report["deviations_clear"] if x.get("tag") == "AVOID"]
        )
    else:
        report["eod_screener_miss"]["scheduled_miss_avoid"] = False

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
    try:
        report["vcp_rvol_outcomes"] = rvol_outcome_scoring(rows, _all_rows())
    except Exception as e:  # aggregate only; never break feedback
        report["vcp_rvol_outcomes"] = {"error": str(e)}
    return report


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

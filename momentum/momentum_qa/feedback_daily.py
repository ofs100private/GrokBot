#!/usr/bin/env python3
"""Daily feedback loop: what matched strategy vs clear deviations."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from momentum_qa.eod_miss_check import is_miss, screener_actions_by_deadline

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


def build_report(day: str) -> dict:
    rows = load_day(day)
    all_actions = [r for r in rows if r.get("event") == "ACTION"]
    rebalance_dry = [r for r in all_actions if is_rebalance_dry_run(r)]
    actions = [r for r in all_actions if not is_rebalance_dry_run(r)]
    gate_ok_counts = Counter()
    deviations = [r for r in rows if r.get("event") == "DEVIATION" or r.get("deviation")]
    errors = [r for r in rows if r.get("event") == "ERROR"]
    qa_fail = [r for r in actions if r.get("qa_verdict") == "FAIL"]
    qa_pass = [r for r in actions if r.get("qa_verdict") == "PASS"]

    keep = []
    avoid = []
    gate_ok_seen = set()  # collapse duplicate INSUFFICIENT_CASH SKIP+DEVIATION
    for a in actions:
        code = a.get("deviation_code")
        g = gate_ok_code(a)
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
        cash_gate_ok = code == "INSUFFICIENT_CASH" or (
            a.get("qa_verdict") == "FAIL"
            and "INSUFFICIENT_CASH" in str(a.get("qa_reasons") or "")
        )
        # Intentional DWM SKIP (no place) = KEEP per QA Bot 2026-09-11
        if intentional_dwm_skip or cash_gate_ok or (
            a.get("qa_verdict") == "PASS" and not a.get("deviation")
        ):
            if cash_gate_ok:
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
        g = gate_ok_code(d)
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
    return report


def main(day: str | None = None) -> int:
    day = day or datetime.now(tz=IL).strftime("%Y-%m-%d")
    report = build_report(day)
    out_dir = OUT_DIR / day
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "daily_feedback.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary
    md = [
        f"# Momentum daily feedback | {day}",
        "",
        f"- Actions: {report['counts']['actions']} | QA PASS: {report['counts']['qa_pass_actions']} | QA FAIL: {report['counts']['qa_fail_actions']}",
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
    day = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(day))

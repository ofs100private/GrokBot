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


def build_report(day: str) -> dict:
    rows = load_day(day)
    actions = [r for r in rows if r.get("event") == "ACTION"]
    deviations = [r for r in rows if r.get("event") == "DEVIATION" or r.get("deviation")]
    errors = [r for r in rows if r.get("event") == "ERROR"]
    qa_fail = [r for r in actions if r.get("qa_verdict") == "FAIL"]
    qa_pass = [r for r in actions if r.get("qa_verdict") == "PASS"]

    keep = []
    avoid = []
    gate_ok_seen = set()  # collapse duplicate INSUFFICIENT_CASH SKIP+DEVIATION
    for a in actions:
        code = a.get("deviation_code")
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
        f"- Deviations: {report['counts']['deviations']} | Errors: {report['counts']['errors']}",
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

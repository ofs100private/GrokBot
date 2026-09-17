#!/usr/bin/env python3
"""Daily feedback loop: what matched strategy vs clear deviations."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from momentum_qa.eod_miss_check import is_miss

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
    for a in actions:
        code = a.get("deviation_code")
        intentional_dwm_skip = (
            a.get("action") == "SKIP"
            and code == "DWM_STRENGTH_FAIL"
            and a.get("qa_verdict") == "PASS"
        )
        # Intentional DWM SKIP (no place) = KEEP per QA Bot 2026-09-11
        if intentional_dwm_skip or (
            a.get("qa_verdict") == "PASS" and not a.get("deviation")
        ):
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
            if intentional_dwm_skip:
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
    report["eod_screener_miss"] = {"miss": miss, **miss_status}

    # Scheduled-on-time AVOID: first EOD screener ACTION after 22:46 means cron was late
    # even if catch-up later makes is_miss() false (QA Bot 2026-09-15 soft fix).
    scheduled_late = False
    first_action_ts = None
    for a in (miss_status.get("actions") or []):
        ts = a.get("ts_il")
        if not ts:
            continue
        if first_action_ts is None or ts < first_action_ts:
            first_action_ts = ts
    if first_action_ts and "T22:" in first_action_ts:
        try:
            hhmm = first_action_ts.split("T22:")[1][:5]
            h, m = map(int, hhmm.split(":"))
            if h * 60 + m > 22 * 60 + 46:  # after 22:46
                scheduled_late = True
        except Exception:
            pass
    # Also if no action until after 22:46 window but actions exist later same night
    if first_action_ts and ("T22:5" in first_action_ts or "T22:4" in first_action_ts[11:16] if len(first_action_ts) > 16 else False):
        pass  # handled above
    if first_action_ts:
        # simpler minute check from ISO
        try:
            from datetime import datetime as _dt
            fa = _dt.fromisoformat(first_action_ts)
            if fa.hour == 22 and fa.minute >= 47:
                scheduled_late = True
            if fa.hour >= 23:
                scheduled_late = True
        except Exception:
            pass

    already = any(
        x.get("deviation_code") == "EOD_SCREENER_MISSED" for x in report["deviations_clear"]
    )
    if (miss or scheduled_late) and not already:
        report["deviations_clear"].append(
            {
                "tag": "AVOID",
                "action": "EOD_SCREENER_MISSED",
                "rationale": (
                    "Scheduled 22:45 screener missed or late"
                    + (f" (first EOD ACTION {first_action_ts})" if first_action_ts else "")
                    + ". Catch-up does not clear process AVOID."
                ),
                "deviation_code": "EOD_SCREENER_MISSED",
                "severity": "HIGH",
            }
        )
        report["lessons"].append(
            {
                "tag": "AVOID",
                "text": "EOD_SCREENER_MISSED — catch up immediately; scheduled-on-time failure stays AVOID even after clean catch-up.",
            }
        )
        report["counts"]["deviations"] = report["counts"].get("deviations", 0) + 1
        report["counts"]["avoid"] = len(report["deviations_clear"])
        report["eod_screener_miss"]["scheduled_miss_avoid"] = True
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

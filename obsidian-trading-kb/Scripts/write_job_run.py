#!/usr/bin/env python3
"""
Idempotent writer for Obsidian Job-Runs notes.

Usage:
  python3 Scripts/write_job_run.py --bot Trader_Classic --job classic-rsi-1h-auto \\
      --run-id classic-rsi-auto-20260930-194443-e56a4d55 \\
      --status success --started-at '2026-09-30T19:44:43+03:00' \\
      --finished-at '2026-09-30T19:45:12+03:00' --ledger keys-B \\
      --audit-path /workspace/classic_rsi/audit/...json \\
      --qa-verdict PASS --folder Classic-RSI

  # Or pipe a JSON object (same fields) on stdin:
  echo '{...}' | python3 Scripts/write_job_run.py --stdin

  # Backfill from known audit trees (real files only):
  python3 Scripts/write_job_run.py --backfill [--since YYYYMMDD] [--dry-run]

Fields written to frontmatter (exact status words):
  success | fail | blocked | partial | other
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("OBSIDIAN_KB_ROOT", "/workspace/obsidian-trading-kb"))
JOB_RUNS = ROOT / "Job-Runs"
IMPROVEMENTS = ROOT / "Process" / "Improvements"
IL = timezone(timedelta(hours=3))

VALID_STATUS = {"success", "fail", "blocked", "partial", "other"}
VALID_QA = {"PASS", "FAIL", "n/a"}
VALID_LEDGER = {"mirror-A", "keys-B", "n/a"}

BOT_FOLDER = {
    "Trader_Classic": "Classic-RSI",
    "Breakout_TA": "Breakout-TA",
    "Trader_momentum": "Momentum-EOD",
    "daily_brief": "Daily-Brief",
    "Daily_Trader": "Daily-Trader",
    "Git": "Git-Backup",
    "QA_Bot": "QA-Gates",
    "Chief_of_Staff": "QA-Gates",
}

# Embed full JSON only under this many chars; else key fields + path
MAX_EMBED_CHARS = 28_000

SECRET_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|authorization|cookie|refresh|private[_-]?key|bearer)",
    re.I,
)


def now_il() -> datetime:
    return datetime.now(IL)


def parse_idt_stamp(s: str | None) -> datetime | None:
    """Parse common audit stamps into aware IDT datetime."""
    if not s:
        return None
    s = str(s).strip()
    # "2026-09-30 19:44:46 IDT"
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*IDT", s)
    if m:
        return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}+03:00")
    # ISO
    try:
        ss = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ss)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IL)
        return dt.astimezone(IL)
    except ValueError:
        pass
    # "2026-09-30 19:45:12 IDT" already covered; try without tz
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", s)
    if m:
        return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}+03:00")
    return None


def to_iso_il(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(IL).isoformat(timespec="seconds")


def display_il(dt: datetime | None) -> str:
    if dt is None:
        return "n/a"
    return dt.astimezone(IL).strftime("%Y-%m-%d %H:%M IDT")


def redact(obj: Any) -> Any:
    """Strip secret-looking keys/values from nested structures."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SECRET_KEY_RE.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        # Never keep JWT/cookie-looking blobs; soften auth-channel wording
        if re.search(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]+\.", obj):
            return "[REDACTED_JWT]"
        if SECRET_KEY_RE.search(obj) and re.search(r"[A-Za-z0-9_-]{24,}", obj):
            return "[REDACTED]"
        if re.search(r"\bbearer\b", obj, re.I):
            return re.sub(r"(?i)\bbearer\b", "auth-channel", obj)
    return obj


def fm_escape(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return '""'
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if any(c in s for c in ':#{}[]&*?|>!%@`"\n'):
        return json.dumps(s)
    return s


def frontmatter(fields: dict) -> str:
    order = [
        "tags",
        "bot",
        "job",
        "run_id",
        "started_at",
        "finished_at",
        "status",
        "ledger",
        "audit_path",
        "qa_verdict",
        "improvement_needed",
    ]
    lines = ["---"]
    for k in order:
        v = fields[k]
        if k == "tags":
            lines.append(f"tags: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {fm_escape(v)}")
    lines.append("---")
    return "\n".join(lines)


def note_path(folder: str, run_id: str, started_at: str) -> Path:
    # Prefer date from started_at, else from run_id
    date = ""
    if started_at:
        date = started_at[:10]
    if not date:
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", run_id)
        if m:
            date = m.group(1)
        else:
            m = re.search(r"(20\d{6})", run_id)
            if m:
                raw = m.group(1)
                date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    if not date:
        date = now_il().strftime("%Y-%m-%d")
    safe = re.sub(r"[^\w.\-]+", "_", run_id)[:120]
    return JOB_RUNS / folder / f"{date}-{safe}.md"


def key_fields_summary(audit: dict | None, max_depth_keys: int = 40) -> dict:
    if not audit:
        return {}
    keys_priority = [
        "run_id",
        "kind",
        "status",
        "asOfIDT",
        "asOf",
        "as_of",
        "asOf_il",
        "verdict",
        "overall",
        "do_not_place",
        "place",
        "qa_verdict",
        "deviation_codes",
        "buy_packs_count",
        "risk_off_count",
        "confirmed",
        "watch",
        "failed",
        "none_or_error_count",
        "bot",
        "job",
        "slot",
        "date",
        "mandate_gates",
        "hard_fail",
        "hard_fail_gates",
        "n_candidates",
        "n_breakouts",
        "mirrorId",
        "portfolio",
        "timeframe",
        "event",
        "action",
        "symbol",
        "day",
        "pm_decisions",
        "gate",
        "checks",
        "cos_summary",
        "summaryForCoS",
    ]
    out: dict[str, Any] = {}
    for k in keys_priority:
        if k in audit:
            v = audit[k]
            if isinstance(v, (dict, list)):
                dumped = json.dumps(redact(v), default=str)
                if len(dumped) > 4000:
                    if isinstance(v, list):
                        out[k] = {"_type": "list", "len": len(v), "sample": redact(v[:3])}
                    else:
                        out[k] = {
                            "_type": "dict",
                            "keys": list(v.keys())[:max_depth_keys],
                            "preview": json.loads(dumped[:3500] + '"}')
                            if False
                            else f"(truncated {len(dumped)} chars; keys={list(v.keys())[:20]})",
                        }
                else:
                    out[k] = redact(v)
            else:
                out[k] = v
    # always include top-level key list
    out["_top_keys"] = list(audit.keys())[:60]
    return out


def load_audit(path: str | None) -> tuple[dict | None, str | None]:
    if not path:
        return None, None
    p = Path(path)
    if not p.is_file():
        return None, f"missing file: {path}"
    try:
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".jsonl":
            # last non-empty line
            lines = [ln for ln in text.splitlines() if ln.strip()]
            if not lines:
                return None, "empty jsonl"
            return json.loads(lines[-1]), None
        return json.loads(text), None
    except Exception as e:
        return None, f"parse error: {e}"


def build_body(
    *,
    bot: str,
    job: str,
    run_id: str,
    status: str,
    started: datetime | None,
    finished: datetime | None,
    audit_path: str,
    qa_verdict: str,
    improvement_needed: bool,
    audit: dict | None,
    expected: str,
    actual: str,
    improvement_link: str | None,
    summary_extra: str = "",
) -> str:
    parts: list[str] = []
    parts.append(f"# Job run · `{run_id}`")
    parts.append("")
    parts.append("## Summary")
    parts.append("")
    parts.append(f"- **Bot:** {bot}")
    parts.append(f"- **Job:** {job}")
    parts.append(f"- **Time (Asia/Jerusalem):** {display_il(started)} → {display_il(finished)}")
    parts.append(f"- **Status:** `{status}`")
    parts.append(f"- **QA verdict:** {qa_verdict}")
    if audit_path:
        parts.append(f"- **Audit path:** `{audit_path}`")
    if summary_extra:
        parts.append(f"- {summary_extra}")
    parts.append("")
    parts.append("## Status")
    parts.append("")
    parts.append(f"`{status}` — exact vocabulary: success | fail | blocked | partial | other.")
    parts.append("")
    parts.append("## Full audit")
    parts.append("")
    if audit is not None:
        redacted = redact(audit)
        dumped = json.dumps(redacted, indent=2, default=str, ensure_ascii=False)
        if len(dumped) <= MAX_EMBED_CHARS:
            parts.append("```json")
            parts.append(dumped)
            parts.append("```")
        else:
            parts.append(f"Audit too large to embed ({len(dumped)} chars). Path: `{audit_path}`")
            parts.append("")
            parts.append("Key fields:")
            parts.append("")
            parts.append("```json")
            parts.append(json.dumps(key_fields_summary(audit), indent=2, default=str, ensure_ascii=False))
            parts.append("```")
    elif audit_path:
        parts.append(f"Audit not embedded (unreadable or missing). Path: `{audit_path}`")
    else:
        parts.append("_No audit payload attached._")
    parts.append("")
    parts.append("## Expected vs actual")
    parts.append("")
    parts.append(f"- **Expected:** {expected or 'n/a'}")
    parts.append(f"- **Actual:** {actual or 'n/a'}")
    parts.append("")
    parts.append("## Improvement ticket")
    parts.append("")
    if improvement_needed and improvement_link:
        parts.append(f"See [[{improvement_link}]]")
    elif improvement_needed:
        parts.append("Improvement needed — ticket pending under `Process/Improvements/`.")
    else:
        parts.append("_None — run matched mandate / QA expectations._")
    parts.append("")
    return "\n".join(parts)


def write_improvement_ticket(
    *,
    run_note_rel: str,
    bot: str,
    job: str,
    run_id: str,
    symptom: str,
    evidence: str,
    priority: str = "P2",
    proposed_fix: str = "TBD",
    root_cause: str = "unknown",
) -> Path:
    IMPROVEMENTS.mkdir(parents=True, exist_ok=True)
    day = now_il().strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w]+", "-", f"{job}-{run_id}")[:80].strip("-").lower()
    path = IMPROVEMENTS / f"{day}-{slug}.md"
    if path.exists():
        return path
    body = f"""---
tags: [improvement]
status: open
owner_bot: {bot}
job: {job}
run_id: {run_id}
priority: {priority}
created_at: {to_iso_il(now_il())}
---
# Improvement · {job} · {run_id}

## Symptom
{symptom}

## Evidence
- Job-run note: [[{run_note_rel}]]
- {evidence}

## Root cause
{root_cause}

## Proposed fix
{proposed_fix}

## Owner bot
{bot}

## Priority
{priority}

## Status
open
"""
    path.write_text(body, encoding="utf-8")
    return path


def write_job_run(spec: dict, *, dry_run: bool = False) -> dict:
    bot = spec["bot"]
    job = spec["job"]
    run_id = spec["run_id"]
    status = spec["status"]
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}; want {VALID_STATUS}")
    ledger = spec.get("ledger") or "n/a"
    if ledger not in VALID_LEDGER:
        raise ValueError(f"invalid ledger {ledger!r}")
    qa_verdict = spec.get("qa_verdict") or "n/a"
    if qa_verdict not in VALID_QA:
        raise ValueError(f"invalid qa_verdict {qa_verdict!r}")
    folder = spec.get("folder") or BOT_FOLDER.get(bot)
    if not folder:
        raise ValueError(f"unknown bot {bot!r}; pass folder=")
    audit_path = spec.get("audit_path") or ""
    started = parse_idt_stamp(spec.get("started_at")) or parse_idt_stamp(spec.get("asOfIDT"))
    finished = parse_idt_stamp(spec.get("finished_at")) or started
    improvement_needed = bool(spec.get("improvement_needed"))
    if status == "fail":
        improvement_needed = True

    audit, err = load_audit(audit_path) if audit_path else (spec.get("audit"), None)
    if audit is None and spec.get("audit") is not None:
        audit = spec["audit"]

    # Expand classic wrapper: prefer payload for key fields but keep wrapper as audit root
    expected = spec.get("expected") or "Job completes; QA PASS when gated; mandate respected."
    actual = spec.get("actual") or ""
    if not actual:
        bits = [f"status={status}", f"qa={qa_verdict}"]
        if err:
            bits.append(err)
        if audit:
            inner = audit.get("payload") if isinstance(audit.get("payload"), dict) else audit
            if isinstance(inner, dict):
                if "do_not_place" in inner or "do_not_place" in audit:
                    bits.append(f"do_not_place={inner.get('do_not_place', audit.get('do_not_place'))}")
                if "place" in inner:
                    bits.append(f"place={inner.get('place')}")
                if inner.get("status"):
                    bits.append(f"job_status={inner.get('status')}")
                if audit.get("overall"):
                    bits.append(f"overall={audit.get('overall')}")
                if audit.get("verdict"):
                    bits.append(f"verdict={audit.get('verdict')}")
        actual = "; ".join(str(b) for b in bits)

    path = note_path(folder, run_id, to_iso_il(started))
    rel = str(path.relative_to(ROOT)).replace(".md", "")
    improvement_link = None
    if improvement_needed:
        ticket = write_improvement_ticket(
            run_note_rel=rel,
            bot=bot,
            job=job,
            run_id=run_id,
            symptom=spec.get("symptom") or f"Job {job} ended status={status} qa={qa_verdict}",
            evidence=f"audit: `{audit_path}`" if audit_path else "inline audit",
            priority=spec.get("priority") or ("P1" if status == "fail" else "P2"),
            proposed_fix=spec.get("proposed_fix") or "TBD after owner review",
            root_cause=spec.get("root_cause") or "unknown",
        )
        if not dry_run:
            pass
        improvement_link = str(ticket.relative_to(ROOT)).replace(".md", "")

    fields = {
        "tags": ["job-run"],
        "bot": bot,
        "job": job,
        "run_id": run_id,
        "started_at": to_iso_il(started),
        "finished_at": to_iso_il(finished),
        "status": status,
        "ledger": ledger,
        "audit_path": audit_path,
        "qa_verdict": qa_verdict,
        "improvement_needed": improvement_needed,
    }
    body = build_body(
        bot=bot,
        job=job,
        run_id=run_id,
        status=status,
        started=started,
        finished=finished,
        audit_path=audit_path,
        qa_verdict=qa_verdict,
        improvement_needed=improvement_needed,
        audit=audit,
        expected=expected,
        actual=actual,
        improvement_link=improvement_link,
        summary_extra=spec.get("summary_extra") or "",
    )
    text = frontmatter(fields) + "\n" + body
    if dry_run:
        return {"path": str(path), "wrote": False, "dry_run": True, "status": status, "run_id": run_id}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Idempotent: rewrite same path (deterministic name from run_id)
    path.write_text(text, encoding="utf-8")
    return {
        "path": str(path),
        "wrote": True,
        "status": status,
        "run_id": run_id,
        "improvement_needed": improvement_needed,
        "improvement": improvement_link,
    }


# --------------- status mappers (real files only) ---------------


def map_classic_status(audit: dict, qa: dict | None) -> tuple[str, str, bool]:
    """Return status, qa_verdict, improvement_needed."""
    inner = audit.get("payload") if isinstance(audit.get("payload"), dict) else audit
    dnp = bool(inner.get("do_not_place", audit.get("do_not_place", True)))
    place = bool(inner.get("place", False))
    mg = inner.get("mandate_gates") or {}
    blocks = mg.get("blocks") or []
    allow = mg.get("allow_new_buys", True)
    job_status = inner.get("status") or audit.get("status") or ""

    qa_verdict = "n/a"
    if qa:
        qa_verdict = str(qa.get("verdict") or "n/a").upper()
        if qa_verdict not in VALID_QA:
            qa_verdict = "FAIL" if qa_verdict not in ("PASS",) else qa_verdict

    # Incomplete?
    if not audit.get("run_id") and not inner.get("run_id"):
        return "partial", qa_verdict, True
    if not (audit.get("asOfIDT") or inner.get("asOfIDT")):
        return "partial", qa_verdict, True

    if qa_verdict == "FAIL":
        return "fail", qa_verdict, True

    # Fear / No Buy block with no place
    block_txt = json.dumps(blocks).lower() + json.dumps(mg).lower()
    fear_block = (
        (not allow)
        or any("fear" in str(b).lower() or "no buy" in str(b).lower() or "no_buy" in str(b).lower() for b in blocks)
        or ("no buy" in block_txt and not place)
    )
    if fear_block and dnp and not place:
        # Still a completed propose/scan — blocked for trading
        return "blocked", qa_verdict if qa_verdict != "n/a" else "n/a", False

    if qa_verdict == "PASS":
        return "success", qa_verdict, False

    # Completed auto propose without place is normal success when no QA file
    if job_status in ("PROPOSE", "DONE", "OK", "SUCCESS", "") and dnp and not place:
        return "success", qa_verdict, False
    if place:
        return "success", qa_verdict, False
    return "success", qa_verdict, False


def map_breakout_status(audit: dict) -> tuple[str, str, bool]:
    if not audit.get("run_id") or not audit.get("asOfIDT"):
        return "partial", "n/a", True
    # scan completed; do_not_place is mandatory for Breakout auto
    err_n = audit.get("none_or_error_count")
    if isinstance(err_n, int) and err_n > 0 and not (audit.get("confirmed") or audit.get("watch") or audit.get("failed")):
        return "partial", "n/a", True
    return "success", "n/a", False


def map_daily_brief_status(verdict: dict) -> tuple[str, str, bool]:
    overall = str(verdict.get("overall") or verdict.get("verdict") or "").upper()
    if overall == "PASS":
        return "success", "PASS", False
    if overall == "FAIL":
        return "fail", "FAIL", True
    if not overall:
        return "partial", "n/a", True
    return "other", overall if overall in VALID_QA else "n/a", True


def map_daily_trader_status(audit: dict) -> tuple[str, str, bool]:
    if not audit.get("run_id") or not audit.get("asOfIDT"):
        return "partial", "n/a", True
    failed = audit.get("failed") or []
    if failed:
        return "partial", "n/a", True
    return "success", "n/a", False


def map_momentum_eod_status(audit: dict) -> tuple[str, str, bool]:
    # screener summary or miss check
    has_stamp = bool(
        audit.get("day")
        or audit.get("asOf_il")
        or audit.get("asOfIDT")
        or audit.get("asOf")
        or audit.get("as_of")
        or audit.get("run_id")
        or audit.get("night_status")
    )
    if not has_stamp:
        return "partial", "n/a", True
    # miss / deviation — only hard-true flags (not nested report objects)
    miss_flag = audit.get("miss")
    any_miss = False
    if miss_flag is True:
        any_miss = True
    elif isinstance(miss_flag, dict) and miss_flag.get("any_miss") is True:
        any_miss = True
    ns = audit.get("night_status") or {}
    if isinstance(ns, dict) and ns.get("any_miss") is True:
        any_miss = True
    if audit.get("deviation") is True or any_miss:
        return "fail", str(audit.get("qa_verdict") or "n/a"), True
    qv = audit.get("qa_verdict")
    if qv and str(qv).upper() in ("FAIL", "HARD_FAIL"):
        return "fail", "FAIL", True
    return "success", "n/a" if not qv else ("PASS" if str(qv).upper() in ("PASS", "GATE_OK", "OK") else "n/a"), False


def map_qa_gate_status(audit: dict) -> tuple[str, str, bool]:
    v = str(audit.get("verdict") or audit.get("overall") or "").upper()
    if v == "PASS":
        return "success", "PASS", False
    if v == "FAIL":
        return "fail", "FAIL", True
    return "other", v if v in VALID_QA else "n/a", True


# --------------- backfill ---------------


def backfill(since: str = "20260916", dry_run: bool = False, cap: int = 500) -> dict:
    results: list[dict] = []
    written = 0

    def add(spec: dict):
        nonlocal written
        if written >= cap:
            return
        r = write_job_run(spec, dry_run=dry_run)
        results.append(r)
        written += 1

    # Classic RSI autos (+ attach run-qa when present)
    classic_dir = Path("/workspace/classic_rsi/audit")
    qa_by_run: dict[str, dict] = {}
    if classic_dir.is_dir():
        for qf in classic_dir.glob("classic-rsi-auto-*-run-qa.json"):
            try:
                q = json.loads(qf.read_text())
                qa_by_run[q.get("run_id") or ""] = q
            except Exception:
                continue
        # also latest-run-qa
        lq = classic_dir / "latest-run-qa.json"
        if lq.is_file():
            try:
                q = json.loads(lq.read_text())
                qa_by_run[q.get("run_id") or ""] = q
            except Exception:
                pass

        autos = sorted(
            f
            for f in classic_dir.glob("classic-rsi-auto-*.json")
            if not f.name.endswith("-run-qa.json")
        )
        for f in autos:
            m = re.search(r"classic-rsi-auto-(20\d{6})-", f.name)
            if m and m.group(1) < since:
                continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            run_id = audit.get("run_id") or f.stem
            qa = qa_by_run.get(run_id)
            status, qv, need = map_classic_status(audit, qa)
            started = audit.get("asOfIDT") or (qa or {}).get("timestamp")
            finished = (qa or {}).get("timestamp") or started
            # Prefer QA file as companion evidence in summary; audit_path stays primary audit
            add(
                {
                    "bot": "Trader_Classic",
                    "job": "classic-rsi-1h-auto",
                    "run_id": run_id,
                    "status": status,
                    "started_at": started,
                    "finished_at": finished,
                    "ledger": "keys-B",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Classic-RSI",
                    "expected": "1H auto propose completes; run-QA PASS when present; Fear/No Buy → no place.",
                    "summary_extra": f"run-qa attached={bool(qa)}",
                    "audit": audit,
                }
            )

    # Breakout TA
    bo_dir = Path("/workspace/breakout_ta/audit")
    if bo_dir.is_dir():
        for f in sorted(bo_dir.glob("breakout-auto-*.json")):
            m = re.search(r"breakout-auto-(20\d{6})-", f.name)
            if m and m.group(1) < since:
                continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            status, qv, need = map_breakout_status(audit)
            add(
                {
                    "bot": "Breakout_TA",
                    "job": "breakout-ta-daily-auto",
                    "run_id": audit.get("run_id") or f.stem,
                    "status": status,
                    "started_at": audit.get("asOfIDT"),
                    "finished_at": audit.get("asOfIDT"),
                    "ledger": "keys-B",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Breakout-TA",
                    "expected": "Daily breakout scan completes; do_not_place=true (scan-only).",
                    "audit": audit,
                }
            )

    # Momentum EOD — prefer screener summaries + recent miss checks (not every jsonl line)
    mom_dir = Path("/workspace/momentum_audit")
    if mom_dir.is_dir():
        for f in sorted(mom_dir.glob("eod-*-screener-summary.json")):
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", f.name)
            if m:
                daykey = m.group(1).replace("-", "")
                if daykey < since:
                    continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            day = audit.get("day") or (m.group(1) if m else "unknown")
            run_id = f"momentum-eod-screener-{day}"
            status, qv, need = map_momentum_eod_status(audit)
            add(
                {
                    "bot": "Trader_momentum",
                    "job": "momentum-eod",
                    "run_id": run_id,
                    "status": status,
                    "started_at": audit.get("asOf_il") or audit.get("asOfIDT"),
                    "finished_at": audit.get("asOf_il") or audit.get("asOfIDT"),
                    "ledger": "keys-B",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Momentum-EOD",
                    "expected": "EOD screener/exec summary written; mandate + cash gates respected.",
                    "audit": audit,
                }
            )
        for f in sorted(mom_dir.glob("eod_miss_check_*.json")):
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", f.name)
            if m:
                daykey = m.group(1).replace("-", "")
                if daykey < since:
                    continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            run_id = f"momentum-eod-miss-{f.stem}"
            status, qv, need = map_momentum_eod_status(audit)
            # synthesize IDT stamp from filename day when audit lacks asOf
            day_m = re.search(r"(20\d{2}-\d{2}-\d{2})", f.name)
            synth = f"{day_m.group(1)}T22:45:00+03:00" if day_m else None
            # miss-check files documenting a miss → often fail/partial
            text = json.dumps(audit).lower()
            if "miss" in f.name and ("true" in text[:500] or audit.get("miss") or audit.get("eod_miss")):
                if status == "success":
                    # keep success unless explicit miss flag
                    pass
            add(
                {
                    "bot": "Trader_momentum",
                    "job": "momentum-eod",
                    "run_id": run_id,
                    "status": status,
                    "started_at": audit.get("asOf_il") or audit.get("asOfIDT") or audit.get("ts_il") or audit.get("as_of") or audit.get("checked_at") or synth,
                    "finished_at": audit.get("asOf_il") or audit.get("asOfIDT") or audit.get("ts_il") or audit.get("as_of") or audit.get("checked_at") or synth,
                    "ledger": "keys-B",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Momentum-EOD",
                    "expected": "EOD miss-check documents whether 22:40/22:45 path ran.",
                    "audit": audit,
                }
            )

    # Daily briefs — folders with qa-verdict
    for folder in sorted(Path("/workspace").glob("daily-brief-*-2026-*-*")):
        if not folder.is_dir():
            continue
        m = re.match(r"daily-brief-(0530|1530)-(20\d{2}-\d{2}-\d{2})$", folder.name)
        if not m:
            continue
        slot, day = m.group(1), m.group(2)
        daykey = day.replace("-", "")
        if daykey < since:
            continue
        # prefer recheck verdict if present, else newest mtime
        verdicts = list(folder.glob("qa-verdict-*.json"))
        if not verdicts:
            # still record brief.md presence as partial?
            brief = folder / "brief.md"
            if brief.is_file():
                add(
                    {
                        "bot": "daily_brief",
                        "job": f"daily-brief-{slot}",
                        "run_id": f"daily-brief-{slot}-{day}-no-qa",
                        "status": "partial",
                        "started_at": f"{day}T{'05:30:00' if slot=='0530' else '15:30:00'}+03:00",
                        "finished_at": f"{day}T{'05:30:00' if slot=='0530' else '15:30:00'}+03:00",
                        "ledger": "mirror-A",
                        "audit_path": str(brief),
                        "qa_verdict": "n/a",
                        "improvement_needed": True,
                        "folder": "Daily-Brief",
                        "expected": "Brief + QA verdict present.",
                        "actual": "brief.md present; qa-verdict missing",
                        "symptom": "Daily brief folder missing qa-verdict",
                    }
                )
            continue
        # Prefer final > recheck > newest mtime (final is the authoritative Gate-D close)
        finals = [v for v in verdicts if "final" in v.name.lower()]
        rechecks = [v for v in verdicts if "recheck" in v.name.lower()]
        if finals:
            vf = max(finals, key=lambda x: x.stat().st_mtime)
        elif rechecks:
            vf = max(rechecks, key=lambda x: x.stat().st_mtime)
        else:
            vf = max(verdicts, key=lambda x: x.stat().st_mtime)
        try:
            verdict = json.loads(vf.read_text())
        except Exception:
            continue
        status, qv, need = map_daily_brief_status(verdict)
        asof = verdict.get("asOf_qa") or verdict.get("asOf") or f"{day}T{'05:35:00' if slot=='0530' else '15:35:00'}+03:00"
        add(
            {
                "bot": "daily_brief",
                "job": f"daily-brief-{slot}",
                "run_id": f"daily-brief-{slot}-{day}-{vf.stem}",
                "status": status,
                "started_at": asof,
                "finished_at": asof,
                "ledger": "mirror-A",
                "audit_path": str(vf),
                "qa_verdict": qv,
                "improvement_needed": need,
                "folder": "Daily-Brief",
                "expected": "Brief QA overall PASS; mirror-A figures only.",
                "symptom": f"Daily brief {slot} {day} overall={verdict.get('overall') or verdict.get('verdict')}",
                "priority": "P1" if status == "fail" else "P2",
                "audit": verdict,
            }
        )

    # Daily trader scans
    dt_dir = Path("/workspace/daily_trader/audit")
    if dt_dir.is_dir():
        for f in sorted(dt_dir.glob("daily-trader-scan-*.json")):
            m = re.search(r"daily-trader-scan-(20\d{6})-", f.name)
            if m and m.group(1) < since:
                continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            status, qv, need = map_daily_trader_status(audit)
            add(
                {
                    "bot": "Daily_Trader",
                    "job": "daily-trader-scan",
                    "run_id": audit.get("run_id") or f.stem,
                    "status": status,
                    "started_at": audit.get("asOfIDT") or audit.get("asOfUTC"),
                    "finished_at": audit.get("asOfIDT") or audit.get("asOfUTC"),
                    "ledger": "n/a",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Daily-Trader",
                    "expected": "Scan completes; do_not_place; no invented orders.",
                    "audit": audit,
                }
            )

    # Obsidian KB QA verdict
    kb_verdict = ROOT / "_raw" / "qa-verdict-obsidian-kb.json"
    if kb_verdict.is_file():
        try:
            audit = json.loads(kb_verdict.read_text())
            status, qv, need = map_qa_gate_status(audit)
            add(
                {
                    "bot": "QA_Bot",
                    "job": "qa-gate",
                    "run_id": f"qa-gate-obsidian-kb-{audit.get('as_of','')[:10].replace('-','') or 'unknown'}",
                    "status": status,
                    "started_at": audit.get("as_of"),
                    "finished_at": audit.get("as_of"),
                    "ledger": "mirror-A",
                    "audit_path": str(kb_verdict),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "QA-Gates",
                    "expected": "OBSIDIAN_TRADING_KB_NUMBER_GATE PASS.",
                    "audit": audit,
                }
            )
        except Exception:
            pass

    # Also mirror GrokBot momentum_audit screener-runs if unique
    gb_mom = Path("/workspace/GrokBot/momentum/momentum_audit")
    if gb_mom.is_dir():
        for f in sorted(gb_mom.glob("screener-run-*.json")):
            m = re.search(r"(20\d{6})", f.name)
            if m and m.group(1) < since:
                continue
            try:
                audit = json.loads(f.read_text())
            except Exception:
                continue
            run_id = audit.get("run_id") or f.stem
            # skip if we already have same run_id in results
            if any(r.get("run_id") == run_id for r in results):
                continue
            status, qv, need = map_momentum_eod_status(audit)
            add(
                {
                    "bot": "Trader_momentum",
                    "job": "momentum-eod",
                    "run_id": run_id,
                    "status": status,
                    "started_at": audit.get("asOfIDT") or audit.get("asOf_il"),
                    "finished_at": audit.get("asOfIDT") or audit.get("asOf_il"),
                    "ledger": "keys-B",
                    "audit_path": str(f),
                    "qa_verdict": qv,
                    "improvement_needed": need,
                    "folder": "Momentum-EOD",
                    "expected": "Screener run artifact present.",
                    "audit": audit,
                }
            )

    by_folder: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in results:
        p = Path(r["path"])
        folder = p.parent.name
        by_folder[folder] = by_folder.get(folder, 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    return {
        "count": len(results),
        "by_folder": by_folder,
        "by_status": by_status,
        "sample_paths": [r["path"] for r in results[:8]],
        "improvements": [r.get("improvement") for r in results if r.get("improvement")],
        "dry_run": dry_run,
        "since": since,
        "cap": cap,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write Obsidian Job-Runs markdown notes")
    ap.add_argument("--stdin", action="store_true", help="Read JSON spec from stdin")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--since", default="20260916", help="YYYYMMDD lower bound for backfill")
    ap.add_argument("--cap", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bot")
    ap.add_argument("--job")
    ap.add_argument("--run-id")
    ap.add_argument("--status")
    ap.add_argument("--started-at")
    ap.add_argument("--finished-at")
    ap.add_argument("--ledger", default="n/a")
    ap.add_argument("--audit-path", default="")
    ap.add_argument("--qa-verdict", default="n/a")
    ap.add_argument("--folder")
    ap.add_argument("--improvement-needed", action="store_true")
    ap.add_argument("--expected", default="")
    ap.add_argument("--actual", default="")
    args = ap.parse_args(argv)

    if args.backfill:
        summary = backfill(since=args.since, dry_run=args.dry_run, cap=args.cap)
        print(json.dumps(summary, indent=2))
        return 0

    if args.stdin:
        spec = json.load(sys.stdin)
    else:
        if not all([args.bot, args.job, args.run_id, args.status]):
            ap.error("need --bot --job --run-id --status (or --stdin / --backfill)")
        spec = {
            "bot": args.bot,
            "job": args.job,
            "run_id": args.run_id,
            "status": args.status,
            "started_at": args.started_at,
            "finished_at": args.finished_at,
            "ledger": args.ledger,
            "audit_path": args.audit_path,
            "qa_verdict": args.qa_verdict,
            "folder": args.folder,
            "improvement_needed": args.improvement_needed,
            "expected": args.expected,
            "actual": args.actual,
        }
    result = write_job_run(spec, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

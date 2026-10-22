#!/usr/bin/env python3
"""Place-path audit rows so routines never hand-write JSON (QA Bot 2026-10-21, CRL post-fill).

  ./screener-venv/bin/python -m momentum_qa.place_audit start --screener-run-id <id>
        (--verdict <qa-verdict.json> | --verdict-sha <sha>) --symbols CRL[,..]
  ./screener-venv/bin/python -m momentum_qa.place_audit fill --screener-run-id <id>
        (--verdict ..|--verdict-sha ..) --symbol CRL --position-id N --order-id N --units X
        --open-rate X --amount 1000 --fee 1.5 [--leverage 1] [--direction long] [--sl X] [--rvol-at-entry X]
  ./screener-venv/bin/python -m momentum_qa.place_audit end --screener-run-id <id>
        [--verdict ..|--verdict-sha ..] --placed CRL --skipped ZBRA,A

Common: [--day YYYY-MM-DD] [--backfill] [--audit-dir DIR] [--dry-run] [--caller NAME].
RUN_ID CONVENTION: run_id = screener_run_id on PLACE_RUN_START / FILL / PLACE_RUN_END (same as
SKIP rows from pack_skips); every row also carries top-level screener_run_id (+ verdict_sha256).
Target file = <IL date in the screener run id>.jsonl. fill requires --fee (USD; 0 if none).
fill: rvol_at_entry/setup come from the screener pack row (ACTION BUY of that run+symbol);
--rvol-at-entry only fills a missing pack value (mismatch -> warning in output).
amend-fee --symbol S --position-id N --fee X --source TEXT: appends FILL_AMEND for a FILL
written before --fee existed (never edits rows).
Idempotent: start/end once per screener run (legacy 'place-<id>' rows recognised); FILL once
per positionId. Exit 0 ok (incl. already present), 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from momentum_qa import audit as au

SCRIPT = "momentum_qa/place_audit.py"


def _csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def pack_row_for(rows: list[dict], screener_run_id: str, symbol: str) -> dict | None:
    for r in rows:
        if (r.get("run_id") == screener_run_id and r.get("event") == "ACTION"
                and r.get("action") == "BUY" and au.base_symbol_of(r.get("symbol")) == au.base_symbol_of(symbol)):
            return r
    return None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("start", "fill", "end", "amend-fee"):
        p = sub.add_parser(name)
        p.add_argument("--screener-run-id", required=True)
        p.add_argument("--verdict"); p.add_argument("--verdict-sha")
        p.add_argument("--day"); p.add_argument("--audit-dir")
        p.add_argument("--backfill", action="store_true"); p.add_argument("--dry-run", action="store_true")
        p.add_argument("--caller", default="")
        if name == "start":
            p.add_argument("--symbols", required=True)
        if name == "end":
            p.add_argument("--placed", default=""); p.add_argument("--skipped", default="")
        if name == "amend-fee":
            p.add_argument("--symbol", required=True)
            p.add_argument("--position-id", required=True, type=int)
            p.add_argument("--fee", required=True, type=float)
            p.add_argument("--source", required=True, help="where the fee came from (e.g. orders:lookup xRequestId)")
        if name == "fill":
            p.add_argument("--symbol", required=True)
            p.add_argument("--position-id", required=True, type=int)
            p.add_argument("--order-id", type=int)
            p.add_argument("--units", required=True, type=float)
            p.add_argument("--open-rate", required=True, type=float)
            p.add_argument("--amount", required=True, type=float)
            p.add_argument("--fee", required=True, type=float, help="eToro fee in USD (0 if none)")
            p.add_argument("--leverage", type=int, default=1)
            p.add_argument("--direction", default="long", choices=["long", "short"])
            p.add_argument("--sl", type=float)
            p.add_argument("--rvol-at-entry", type=float)
            p.add_argument("--rationale")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    sha = a.verdict_sha
    if a.verdict:
        try:
            fsha = au.file_sha256(a.verdict)
        except OSError as e:
            print(json.dumps({"ok": False, "error": f"verdict unreadable: {e}"})); return 2
        if sha and sha.lower() != fsha:
            print(json.dumps({"ok": False, "error": "VERDICT_SHA_MISMATCH", "file_sha256": fsha})); return 2
        sha = fsha
    if a.cmd in ("start", "fill", "amend-fee") and not sha:
        print(json.dumps({"ok": False, "error": "--verdict or --verdict-sha required"})); return 2
    run_id = a.screener_run_id  # convention: run_id == screener_run_id
    day = a.day or au.day_from_run_id(a.screener_run_id)
    log = au.AuditLogger(run_id, SCRIPT, write_start=False, day=day, backfill=a.backfill,
                         audit_dir=Path(a.audit_dir) if a.audit_dir else None)
    out: dict = {"ok": True, "cmd": a.cmd, "run_id": run_id, "audit_path": str(log.path), "verdict_sha256": sha,
                 "dry_run": a.dry_run}
    det = {"caller": a.caller} if a.caller else {}
    if a.cmd == "start":
        syms = _csv(a.symbols)
        if a.dry_run:
            out["would_write"] = {"event": "PLACE_RUN_START", "symbols": syms}
        else:
            rec = log.place_run_start(run_id, sha, syms, screener_run_id=a.screener_run_id, details=det)
            out["written"] = rec is not None
    elif a.cmd == "end":
        placed, skipped = _csv(a.placed), _csv(a.skipped)
        if a.dry_run:
            out["would_write"] = {"event": "PLACE_RUN_END", "placed": placed, "skipped": skipped}
        else:
            rec = log.place_run_end(run_id, placed, skipped, screener_run_id=a.screener_run_id,
                                    verdict_sha=sha, details=det)
            out["written"] = rec is not None
    elif a.cmd == "amend-fee":
        # For a FILL row written before --fee existed: append FILL_AMEND (never edits the FILL row).
        rows = log.rows()
        fills = [r for r in rows if r.get("event") == "FILL"
                 and str((r.get("details") or {}).get("positionId")) == str(a.position_id)]
        done = [r for r in rows if r.get("event") == "FILL_AMEND"
                and str((r.get("details") or {}).get("positionId")) == str(a.position_id)]
        if not fills:
            print(json.dumps({"ok": False, "error": "FILL_ROW_NOT_FOUND", "positionId": a.position_id})); return 2
        if a.dry_run:
            out["would_write"] = {"event": "FILL_AMEND", "fee": a.fee}
        elif done:
            out["written"] = False
        else:
            log._write({"event": "FILL_AMEND", "symbol": a.symbol, "screener_run_id": a.screener_run_id,
                        "verdict_sha256": sha, "fee": a.fee, "amends": "FILL",
                        "rationale": f"fee {a.fee} for FILL positionId {a.position_id} ({a.source})",
                        "details": {"positionId": a.position_id, "fee": a.fee, "source": a.source, **det}},
                       run_id=run_id)
            out["written"] = True
    else:
        rows = log.rows()
        pack = pack_row_for(rows, a.screener_run_id, a.symbol)
        if a.fee < 0:
            print(json.dumps({"ok": False, "error": "fee must be >= 0"})); return 2
        pack_rv = au.rvol_from_pack((pack or {}).get("details"))
        warnings = []
        if pack is None:
            warnings.append("PACK_ROW_NOT_FOUND")
        if a.rvol_at_entry is not None and pack_rv is not None and abs(a.rvol_at_entry - pack_rv) > 1e-6:
            warnings.append(f"RVOL_ARG_MISMATCH arg={a.rvol_at_entry} pack={pack_rv} (pack wins)")
        rv = pack_rv if pack_rv is not None else a.rvol_at_entry
        details = {"symbol": a.symbol, "positionId": a.position_id, "orderId": a.order_id, "units": a.units,
                   "openRate": a.open_rate, "amount": a.amount, "fee": a.fee, "leverage": a.leverage,
                   "direction": a.direction,
                   "stopLossRate": a.sl, "rvol_at_entry": rv, "screener_run_id": a.screener_run_id,
                   "verdict_sha256": sha, "verdict_path": str(a.verdict) if a.verdict else None, **det}
        rationale = a.rationale or (f"QA Bot place-QA authorized (verdict sha {sha[:12]}); ${a.amount:g} x{a.leverage} "
                                    f"{a.direction} {a.symbol} @ {a.open_rate} SL {a.sl}")
        pack_for_fill = (pack or {}).get("details") or ({"rvol": rv} if rv is not None else None)
        out["warnings"] = warnings
        if a.dry_run:
            out["would_write"] = {"event": "FILL", "details": details}
        else:
            rec = log.fill(a.symbol, rationale, pack_row=pack_for_fill, details=details, qa_verdict="PASS",
                           screener_run_id=a.screener_run_id, verdict_sha256=sha, fee=a.fee)
            out["written"] = rec is not None
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

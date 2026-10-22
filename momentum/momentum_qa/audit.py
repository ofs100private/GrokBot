"""Append-only audit trail for every Momentum EOD action + rationale."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
AUDIT_DIR = Path(os.environ.get("MOMENTUM_AUDIT_DIR", "/workspace/momentum_audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def new_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(tz=IL).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def build_record(run_id: str, script: str, payload: dict[str, Any], portfolio: str = "Momentum-HHHGDTJ") -> dict[str, Any]:
    """Standard audit row envelope (ts_utc, ts_il, run_id, portfolio, script, **payload)."""
    return {
        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        "ts_il": datetime.now(tz=IL).isoformat(),
        "run_id": run_id,
        "portfolio": portfolio,
        "script": script,
        **payload,
    }


def append_row(rec: dict[str, Any], audit_dir: Path | None = None) -> Path:
    """Append one JSON row to <audit_dir>/<IL date>.jsonl (same format as AuditLogger)."""
    d = Path(audit_dir or AUDIT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{datetime.now(tz=IL).strftime('%Y-%m-%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return path


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Parsed JSONL rows (bad lines skipped); [] if the file is missing."""
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def find_rows(path: Path, **match: Any) -> list[dict[str, Any]]:
    """Rows whose top-level fields equal every given value (event=, run_id=, symbol=...)."""
    return [r for r in read_rows(path) if all(r.get(k) == v for k, v in match.items())]


def base_symbol_of(sym: Any) -> str:
    from momentum_qa.instrument_map import base_symbol
    return base_symbol(sym)


def row_screener_run_id(r: dict[str, Any]) -> str | None:
    """Screener run a SKIP/place row belongs to (handles pre-convention 'place-<id>' rows)."""
    v = r.get("screener_run_id") or (r.get("details") or {}).get("screener_run_id") or r.get("run_id")
    v = str(v) if v else None
    return v[len("place-"):] if v and v.startswith("place-screener-") else v


# QA Bot 2026-10-21: SKIP reason taxonomy (GATE_OK vs protective reject).
# QA Bot 2026-10-21 (re-review MEDIUM): three disjoint classes.
# GATE_OK = a sizing/book gate correctly said "no" (KEEP, counted in gate_ok_codes only).
SKIP_GATE_OK_CODES = {
    "INSUFFICIENT_CASH", "ALREADY_HELD", "DUPLICATE", "DUPLICATE_HOLD_BUY", "DUPLICATE_PLACE",
    "CROSS_BOOK_OVERLAP", "CROSS_BOOK_HELD", "ETF_CAP", "ETF_FLOOR_ALREADY_MET", "ETF_BACKFILL_BLOCKED",
    "AMOUNT_GT_1000_PER_NAME", "BREAKOUT_CAP", "COUNT_CAP",
}
# PROTECTIVE_REJECT = only true protective refusals (QA rulings 2026-10-21 re-review + fixes3):
# instrument guard refusal, id/symbol mismatch, stale cross-book fail-closed, stale positions
# fail-closed, and a prepare-trade rejection by a guard (id mismatch / quote sanity / invalid SL /
# insufficient balance). The only class counted in protective_reject.
PROTECTIVE_REJECT_CODES = {
    "QUOTE_DEVIATION_GT_20PCT", "SYMBOL_MAP_MISMATCH", "QUOTE_GUARD_INPUT_MISSING", "ID_SYMBOL_MISMATCH",
    "INSTRUMENT_ID_REQUIRED", "INSTRUMENT_ID_UNVERIFIED", "INSTRUMENT_ID_UNRESOLVED",
    "STALE_CROSSBOOK_FAIL_CLOSED", "CROSS_BOOK_READ_MISSING_OR_STALE",
    "STALE_POSITIONS", "POSITIONS_STALE", "PREPARE_REJECTED_GUARD", "SL_ABOVE_ASK",
}
# INTENTIONAL_SKIP = explained operational / strategy skips (KEEP, counted in neither):
# lock held, market closed, regime/DWM/freeze, and prepare-trade rejected by the broker
# (market closed / not tradable / min size / transient). A bare legacy 'PREPARE_REJECTED' is
# deliberately unclassified (must be split into _GUARD / _BROKER) -> SKIP_UNGATED.
INTENTIONAL_SKIP_CODES = {
    "STALE_QUOTE", "LOCK_HELD", "PLACE_LOCK_HELD", "RETRY_NOT_ALLOWED", "PREPARE_REJECTED_BROKER",
    "NOT_TRADABLE", "MARKET_CLOSED", "DWM_STRENGTH_FAIL", "EVENT_VOL_FREEZE", "REGIME_HARD_HALT",
}


def classify_skip_code(code: str | None) -> str | None:
    """'GATE_OK' | 'PROTECTIVE_REJECT' | 'INTENTIONAL_SKIP' | None (unexplained skip)."""
    c = str(code or "").upper().split(":")[0].strip()
    # QA fixes4: a reason code that is literally 'GATE_OK' (a label, not a reason) is unclassified
    # -> SKIP_UNGATED, same as the literal 'PROTECTIVE_REJECT'.
    if c in SKIP_GATE_OK_CODES:
        return "GATE_OK"
    if c in PROTECTIVE_REJECT_CODES:
        return "PROTECTIVE_REJECT"
    if c in INTENTIONAL_SKIP_CODES:
        return "INTENTIONAL_SKIP"
    return None


def file_sha256(path: str | Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def day_from_run_id(run_id: str | None) -> str | None:
    """'screener-20261021-224600-xxxx' -> '2026-10-21' (IL date the run was stamped with)."""
    import re
    m = re.search(r"(20\d{2})(\d{2})(\d{2})-\d{6}", str(run_id or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def placed_symbols(rows: list[dict]) -> set[str]:
    """Day-level placement trace (BASE tickers, instrumentId-aware): FILL/PLACE BUY,
    PLACE_RUN_END.placed, POSTFILL found lots."""
    from momentum_qa.instrument_map import base_symbol
    out = set()
    for r in rows:
        ev = r.get("event")
        d = r.get("details") or {}
        if ev in ("FILL", "PLACE") and str(r.get("action") or "BUY").upper() == "BUY" and r.get("symbol"):
            out.add(base_symbol(r["symbol"], d.get("instrumentId") or r.get("instrumentId")))
        elif ev == "PLACE_RUN_END":
            out.update(base_symbol(x) for x in r.get("placed") or [])
        elif ev == "POSTFILL_CHECK":
            for x in (d.get("results") or []):
                if x.get("found") and x.get("symbol"):
                    out.add(base_symbol(x["symbol"], x.get("instrumentId")))
    return out


def rvol_from_pack(pack_row: dict | None) -> float | None:
    """Entry RVOL from a screener pack/BUY row (top-level rvol or details.rvol)."""
    if not pack_row:
        return None
    for v in (pack_row.get("rvol_at_entry"), pack_row.get("rvol"), (pack_row.get("details") or {}).get("rvol")):
        try:
            if v is not None:
                return round(float(v), 4)
        except (TypeError, ValueError):
            continue
    return None


class AuditLogger:
    """Every action must carry rationale. Deviations are explicit events."""

    def __init__(self, run_id: str, script: str, portfolio: str = "Momentum-HHHGDTJ", *,
                 write_start: bool = True, day: str | None = None, audit_dir: Path | None = None,
                 backfill: bool = False):
        """write_start=False: no RUN_START row (CLI helpers). day: target <IL date>.jsonl
        (default today IL). backfill=True: every row carries backfill:true + backfill_ts."""
        self.run_id = run_id
        self.script = script
        self.portfolio = portfolio
        day = day or datetime.now(tz=IL).strftime("%Y-%m-%d")
        d = Path(audit_dir or AUDIT_DIR)
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{day}.jsonl"
        self.backfill_ts = datetime.now(tz=IL).isoformat() if backfill else None
        if write_start:
            self._write(
                {
                    "event": "RUN_START",
                    "rationale": f"Starting {script} for {portfolio}",
                    "script": script,
                }
            )

    def _write(self, payload: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
        rec = build_record(run_id or self.run_id, self.script, payload, self.portfolio)
        bts = getattr(self, "backfill_ts", None)  # subclasses may skip __init__
        if bts:
            rec["backfill"] = True
            rec["backfill_ts"] = bts
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return rec

    def rows(self) -> list[dict[str, Any]]:
        return read_rows(self.path)

    # ---- QA Bot 2026-10-21: SKIP + place rows. RUN_ID CONVENTION (one for all four events):
    #   run_id = screener_run_id of the pack (e.g. screener-20261021-224600-80d463bc) on every
    #   SKIP / PLACE_RUN_START / FILL / PLACE_RUN_END row, and every row ALSO carries a top-level
    #   screener_run_id field. `script` tells writer apart. Legacy rows written before the
    #   convention (run_id "place-<screener_run_id>", FILL with screener_run_id only in details)
    #   are joined via row_screener_run_id().
    def _has_run_row(self, event: str, screener_run_id: str, symbol: str | None = None) -> bool:
        for r in read_rows(self.path):
            if r.get("event") != event or row_screener_run_id(r) != screener_run_id:
                continue
            if symbol is None or base_symbol_of(r.get("symbol")) == base_symbol_of(symbol):
                return True
        return False

    def skip(
        self,
        symbol: str,
        reason_code: str,
        *,
        verdict_sha256: str | None,
        run_id: str | None = None,
        rationale: str | None = None,
        details: dict | None = None,
    ) -> dict[str, Any] | None:
        """SKIP row for a screener pack BUY name that was not placed.

        run_id = the SCREENER run id the pack came from (default: this logger's run_id).
        Idempotent: returns None (writes nothing) if a SKIP row for that run + base symbol exists.
        """
        if not symbol or not reason_code:
            raise ValueError("SKIP needs symbol and reason_code")
        rid = run_id or self.run_id
        if self._has_run_row("SKIP", rid, symbol):
            return None
        code = str(reason_code).upper()
        gate = classify_skip_code(code)
        return self._write(
            {
                "event": "SKIP",
                "action": "SKIP",
                "symbol": symbol,
                "screener_run_id": rid,
                "verdict_sha256": verdict_sha256,
                "reason_code": code,
                "gate": gate,
                "deviation": False,
                **({"skip_ungated": True} if gate is None else {}),
                "rationale": (rationale or f"{symbol} not placed: {code}").strip(),
                "details": details or {},
            },
            run_id=rid,
        )

    def place_run_start(self, run_id: str | None, verdict_sha: str | None, symbols: list[str], *,
                        screener_run_id: str | None = None, details: dict | None = None) -> dict[str, Any] | None:
        """run_id = screener_run_id (convention). Idempotent per screener run."""
        rid = screener_run_id or run_id or self.run_id
        if self._has_run_row("PLACE_RUN_START", rid):
            return None
        return self._write({"event": "PLACE_RUN_START", "screener_run_id": rid,
                            "verdict_sha256": verdict_sha, "symbols": list(symbols or []),
                            "rationale": f"place run start: {','.join(symbols or []) or '(none)'}",
                            "details": details or {}}, run_id=rid)

    def place_run_end(self, run_id: str | None, placed: list[str], skipped: list[str], *,
                      screener_run_id: str | None = None, verdict_sha: str | None = None,
                      details: dict | None = None) -> dict[str, Any] | None:
        rid = screener_run_id or run_id or self.run_id
        if self._has_run_row("PLACE_RUN_END", rid):
            return None
        return self._write({"event": "PLACE_RUN_END", "screener_run_id": rid,
                            "verdict_sha256": verdict_sha, "placed": list(placed or []),
                            "skipped": list(skipped or []),
                            "rationale": f"place run end: placed={','.join(placed or []) or '-'} "
                                         f"skipped={','.join(skipped or []) or '-'}",
                            "details": details or {}}, run_id=rid)

    def action(
        self,
        action: str,
        rationale: str,
        *,
        symbol: str | None = None,
        details: dict | None = None,
        deviation: bool = False,
        deviation_code: str | None = None,
        qa_verdict: str | None = None,
        qa_reasons: list | None = None,
    ) -> None:
        if not rationale or not str(rationale).strip():
            raise ValueError("Every action requires a clear non-empty rationale")
        self._write(
            {
                "event": "ACTION",
                "action": action,
                "symbol": symbol,
                "rationale": rationale.strip(),
                "details": details or {},
                "deviation": bool(deviation),
                "deviation_code": deviation_code,
                "qa_verdict": qa_verdict,
                "qa_reasons": qa_reasons or [],
            }
        )

    def deviation(
        self,
        code: str,
        rationale: str,
        *,
        symbol: str | None = None,
        details: dict | None = None,
        severity: str = "HIGH",
    ) -> None:
        """Explicit strategy breach — always logged clearly."""
        self._write(
            {
                "event": "DEVIATION",
                "deviation": True,
                "deviation_code": code,
                "severity": severity,
                "symbol": symbol,
                "rationale": rationale.strip(),
                "details": details or {},
            }
        )

    def error(self, where: str, err: Exception | str, *, rationale: str, details: dict | None = None) -> None:
        self._write(
            {
                "event": "ERROR",
                "where": where,
                "error": str(err),
                "rationale": rationale.strip(),
                "details": details or {},
                "deviation": True,
                "deviation_code": "RUNTIME_ERROR",
            }
        )


    def fill(
        self,
        symbol: str,
        rationale: str,
        *,
        pack_row: dict | None = None,
        setup: str | None = None,
        action: str = "BUY",
        details: dict | None = None,
        qa_verdict: str | None = None,
        screener_run_id: str | None = None,
        verdict_sha256: str | None = None,
        fee: float | None = None,
    ) -> dict[str, Any] | None:
        """FILL row. Always carries rvol_at_entry from the screener pack row (None if absent).
        With screener_run_id: run_id = screener_run_id (convention) + top-level screener_run_id,
        verdict_sha256 and fee. Idempotent per positionId."""
        det = dict(details or {})
        pid = det.get("positionId")
        if pid is not None and any(str((r.get("details") or {}).get("positionId")) == str(pid)
                                   for r in find_rows(self.path, event="FILL", symbol=symbol)):
            return None  # idempotent: FILL for this positionId already logged
        rv = rvol_from_pack(pack_row)
        if rv is None:
            det.setdefault("rvol_at_entry", None)
        else:
            det["rvol_at_entry"] = det.get("rvol_at_entry") if det.get("rvol_at_entry") is not None else rv
        setup = setup or (pack_row or {}).get("setup") or ((pack_row or {}).get("details") or {}).get("setup")
        if setup:
            det.setdefault("setup", setup)
        payload = {
            "event": "FILL",
            "action": action,
            "symbol": symbol,
            "rationale": rationale.strip(),
            "rvol_at_entry": det["rvol_at_entry"],
            "details": det,
            "qa_verdict": qa_verdict,
        }
        if screener_run_id:
            payload.update(screener_run_id=screener_run_id, verdict_sha256=verdict_sha256, fee=fee)
        return self._write(payload, run_id=screener_run_id)

    def trace(self, message: str, *, details: dict | None = None) -> None:
        """Full-audit TRACE for runtime diagnostics (regime, filters, retries)."""
        self._write(
            {
                "event": "TRACE",
                "rationale": message.strip(),
                "details": details or {},
            }
        )

    def end(self, summary: str, *, details: dict | None = None) -> None:
        self._write(
            {
                "event": "RUN_END",
                "rationale": summary.strip(),
                "details": details or {},
            }
        )

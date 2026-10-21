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

    def __init__(self, run_id: str, script: str, portfolio: str = "Momentum-HHHGDTJ"):
        self.run_id = run_id
        self.script = script
        self.portfolio = portfolio
        day = datetime.now(tz=IL).strftime("%Y-%m-%d")
        self.path = AUDIT_DIR / f"{day}.jsonl"
        self._write(
            {
                "event": "RUN_START",
                "rationale": f"Starting {script} for {portfolio}",
                "script": script,
            }
        )

    def _write(self, payload: dict[str, Any]) -> None:
        rec = build_record(self.run_id, self.script, payload, self.portfolio)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

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
    ) -> None:
        """FILL row. Always carries rvol_at_entry from the screener pack row (None if absent)."""
        det = dict(details or {})
        rv = rvol_from_pack(pack_row)
        det.setdefault("rvol_at_entry", rv)
        setup = setup or (pack_row or {}).get("setup") or ((pack_row or {}).get("details") or {}).get("setup")
        if setup:
            det.setdefault("setup", setup)
        self._write(
            {
                "event": "FILL",
                "action": action,
                "symbol": symbol,
                "rationale": rationale.strip(),
                "rvol_at_entry": det["rvol_at_entry"],
                "details": det,
                "qa_verdict": qa_verdict,
            }
        )

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

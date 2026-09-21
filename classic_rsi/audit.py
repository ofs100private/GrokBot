"""Append-only Classic RSI audit trail (propose + backtest).

Writes under /workspace/classic_rsi/audit/ — never places, never touches Momentum.
Each run gets a run_id QA / Trader_Classic can cite in order packs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

IDT = ZoneInfo("Asia/Jerusalem")
DEFAULT_AUDIT_DIR = Path("/workspace/classic_rsi/audit")
PORTFOLIO = "OfersClaw5-PRIYN"
MIRROR_ID = 11368142
TIMEFRAME = "1H"


def new_run_id(kind: str) -> str:
    """Stamp + short uuid. kind = propose|backtest|auto."""
    stamp = datetime.now(IDT).strftime("%Y%m%d-%H%M%S")
    return f"classic-rsi-{kind}-{stamp}-{uuid.uuid4().hex[:8]}"


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "__dict__") and not isinstance(obj, (str, bytes, dict, list)):
        # RSILevels / StrongCandleConfig style
        try:
            return {k: getattr(obj, k) for k in getattr(obj, "__dataclass_fields__", {})} or dict(
                getattr(obj, "__dict__", {})
            )
        except Exception:  # noqa: BLE001
            return str(obj)
    return obj


def params_fingerprint(params: Mapping[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def append_audit(
    kind: str,
    payload: Mapping[str, Any],
    *,
    audit_dir: Optional[Path] = None,
    run_id: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Append one timestamped JSON file; also update latest.json + index.jsonl.

    Returns the audit record (includes run_id and path).
    """
    if kind not in ("propose", "backtest", "auto"):
        raise ValueError("kind must be propose, backtest, or auto")

    root = Path(audit_dir) if audit_dir else DEFAULT_AUDIT_DIR
    root.mkdir(parents=True, exist_ok=True)

    rid = run_id or new_run_id(kind)
    now = datetime.now(IDT)
    as_of = now.strftime("%Y-%m-%d %H:%M:%S IDT")
    params_dict = {k: _jsonable(v) for k, v in (params or {}).items()}
    fp = params_fingerprint(params_dict) if params_dict else None

    # Slim body for audit: keep packs / risk_off / aggregate; drop huge per-bar dumps if present
    body = dict(payload)
    body.pop("_bars", None)

    record: dict[str, Any] = {
        "run_id": rid,
        "kind": kind,
        "asOfIDT": as_of,
        "portfolio": PORTFOLIO,
        "mirrorId": MIRROR_ID,
        "timeframe": TIMEFRAME,
        "long_only": True,
        "params": params_dict,
        "params_fingerprint": fp,
        "symbols": body.get("symbols")
        or [p.get("instrument", {}).get("symbol") for p in body.get("buy_packs") or [] if isinstance(p, dict)]
        or body.get("symbols"),
        "buy_packs_count": len(body.get("buy_packs") or []),
        "risk_off_count": len(body.get("risk_off") or []),
        "qa_gate": body.get("qa_gate") or "classic-real-money-order-qa-gate",
        "do_not_place": True,
        "payload": body,
        "qa_cite": f"Cite run_id={rid} in Classic RSI order thesis / QA pack.",
    }
    # Prefer explicit symbol list from payload
    if "symbols" in body and isinstance(body["symbols"], list):
        record["symbols"] = list(body["symbols"])
    elif "per_symbol" in body and isinstance(body["per_symbol"], list):
        record["symbols"] = [
            r.get("symbol") for r in body["per_symbol"] if isinstance(r, dict) and r.get("symbol")
        ]

    fname = f"{rid}.json"
    path = root / fname
    text = json.dumps(record, indent=2, default=str) + "\n"
    path.write_text(text)

    # latest pointer for this kind
    (root / f"latest-{kind}.json").write_text(text)
    (root / "latest.json").write_text(text)

    # append-only index (one line per run)
    index_line = {
        "run_id": rid,
        "kind": kind,
        "asOfIDT": as_of,
        "path": str(path),
        "symbols": record.get("symbols"),
        "buy_packs_count": record["buy_packs_count"],
        "risk_off_count": record["risk_off_count"],
        "params_fingerprint": fp,
        "aggregate": (body.get("aggregate") if kind == "backtest" else None),
    }
    with (root / "index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(index_line, default=str) + "\n")

    return {
        "run_id": rid,
        "path": str(path),
        "asOfIDT": as_of,
        "params_fingerprint": fp,
        "kind": kind,
    }


def attach_run_id_to_packs(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Stamp run_id onto top-level and each buy_pack for QA citation."""
    out = dict(payload)
    out["run_id"] = run_id
    out["audit_dir"] = str(DEFAULT_AUDIT_DIR)
    packs = []
    for p in out.get("buy_packs") or []:
        if isinstance(p, dict):
            q = dict(p)
            q["run_id"] = run_id
            packs.append(q)
        else:
            packs.append(p)
    out["buy_packs"] = packs
    return out

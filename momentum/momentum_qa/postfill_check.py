"""Momentum post-fill check (QA Bot ruling 2026-10-19).

Read-only: never calls eToro / MCP, never places. The routine saves ONE keys read
(user-Momentum-HHHGDTJ get-my-positions-and-orders {account:"real"}, write_to_file=true) after the
place step and passes it with the list of authorized fills.

For each expected fill the live lot is found by positionId (strict: a given positionId that is not
live is FILL_MISSING, never a symbol fallback onto an older lot), else by instrumentId / symbol
(most recent lot not already claimed by another expectation).
    filled_usd = max(invested (or amount), units * openRate)
    fill_pct   = filled_usd / authorized_amount
    >= 98%      PASS
    50% - 98%   PARTIAL_FILL  (soft: log, no same-day top-up, reconcile at next EOD)
    <  50% / no live lot  FILL_MISSING (hard: alert; never re-place without a new place-QA)
The place API outcome label (api_outcome / status in --expect) is echoed only; it alone never fails.

Exit: 0 all PASS, 12 any PARTIAL_FILL (and no FILL_MISSING), 13 any FILL_MISSING, 3 bad input.

CLI (run from /workspace):
  ./screener-venv/bin/python -m momentum_qa.postfill_check --raw <keys positions file> \
      --expect '[{"symbol":"TRGP","positionId":3609974058,"authorized_amount":1000}]' \
      --out momentum_audit/postfill/postfill-YYYYMMDD.json [--no-audit]
  --expect is a JSON file path or an inline JSON list. Audit row -> momentum_audit/<IL date>.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from momentum_qa.precheck import _num, _unwrap, load_json_file  # noqa: E402

IDT = ZoneInfo("Asia/Jerusalem")
PASS_MIN, PARTIAL_MIN = 0.98, 0.50
EXIT_PASS, EXIT_PARTIAL, EXIT_MISSING, EXIT_BAD_INPUT = 0, 12, 13, 3
ACTIONS = {
    "PASS": "none",
    "PARTIAL_FILL": "SOFT: log; no same-day top-up; reconcile at next EOD",
    "FILL_MISSING": "HARD: alert; never re-place without a new place-QA",
}


class BadInput(ValueError):
    pass


def audit_dir() -> Path:
    return Path(os.environ.get("MOMENTUM_AUDIT_DIR", "/workspace/momentum_audit"))


def parse_raw(raw: Any) -> dict:
    """Keys positions (direct.positions) or portfolio-summary (holdings[].positions) -> flat lots."""
    d = _unwrap(raw)
    if not isinstance(d, dict):
        raise BadInput("RAW_NOT_OBJECT")
    if d.get("error") or ("statusCode" in d and int(d.get("statusCode") or 0) != 200):
        raise BadInput(f"RAW_NOT_SUCCESS: statusCode={d.get('statusCode')} error={d.get('error')!r}")
    if str(d.get("account", "real")) != "real":
        raise BadInput(f"RAW_NOT_REAL_ACCOUNT: {d.get('account')}")
    rows: list[tuple[dict, dict]] = []
    if isinstance(d.get("direct"), dict):
        rows = [(p, p.get("market") or {}) for p in d["direct"].get("positions") or []]
    elif isinstance(d.get("holdings"), list):
        for h in d["holdings"]:
            m = h.get("market") or {}
            rows += [(p, p.get("market") or m) for p in h.get("positions") or []]
    else:
        raise BadInput("RAW_UNKNOWN_SHAPE: no direct.positions / holdings")
    lots = []
    for p, m in rows:
        lots.append({"positionId": p.get("positionId"), "symbol": str(m.get("symbol") or p.get("symbol") or "").upper(),
                     "instrumentId": m.get("instrumentId") or p.get("instrumentId"), "openTime": p.get("openTime"),
                     "invested": _num(p.get("invested")), "amount": _num(p.get("amount")),
                     "units": _num(p.get("units")), "openRate": _num(p.get("openRate") or p.get("avgOpenRate"))})
    return {"timestamp": d.get("timestamp"), "xRequestId": d.get("xRequestId"), "lots": lots}


def load_expect(arg: str) -> list[dict]:
    s = (arg or "").strip()
    try:
        data = json.loads(s) if s[:1] in ("[", "{") else load_json_file(s)
    except Exception as e:  # noqa: BLE001
        raise BadInput(f"EXPECT_UNREADABLE: {e}") from e
    if isinstance(data, dict):
        data = data.get("expect") or data.get("fills") or [data]
    if not isinstance(data, list) or not data:
        raise BadInput("EXPECT_NOT_A_NONEMPTY_LIST")
    out = []
    for i, e in enumerate(data):
        if not isinstance(e, dict):
            raise BadInput(f"EXPECT[{i}]_NOT_OBJECT")
        pid, sym, iid = e.get("positionId"), e.get("symbol"), e.get("instrumentId")
        if pid in (None, "") and not sym and iid in (None, ""):
            raise BadInput(f"EXPECT[{i}]_NO_SYMBOL_OR_POSITIONID")
        auth = _num(e.get("authorized_amount"))
        if auth is None or auth <= 0:
            raise BadInput(f"EXPECT[{i}]_BAD_AUTHORIZED_AMOUNT: {e.get('authorized_amount')!r}")
        try:
            pid = int(pid) if pid not in (None, "") else None
        except (TypeError, ValueError) as ex:
            raise BadInput(f"EXPECT[{i}]_BAD_POSITIONID: {pid!r}") from ex
        out.append({"symbol": str(sym).upper() if sym else None, "positionId": pid,
                    "instrumentId": iid, "authorized_amount": auth,
                    "api_outcome": e.get("api_outcome", e.get("status"))})
    return out


def filled_usd(lot: dict) -> float:
    inv = lot.get("invested") if lot.get("invested") is not None else lot.get("amount")
    notional = (lot["units"] * lot["openRate"]) if lot.get("units") is not None and lot.get("openRate") is not None else None
    vals = [v for v in (inv, notional) if v is not None]
    return round(max(vals), 2) if vals else 0.0


def classify(pct: Optional[float]) -> str:
    if pct is None or pct < PARTIAL_MIN:
        return "FILL_MISSING"
    return "PASS" if pct >= PASS_MIN else "PARTIAL_FILL"


def check(raw: Any, expect: list[dict]) -> dict:
    live = parse_raw(raw)
    lots = live["lots"]
    by_pid = {int(x["positionId"]): x for x in lots if x.get("positionId") is not None}
    claimed = {e["positionId"] for e in expect if e["positionId"] is not None}
    results = []
    for e in expect:
        lot, how = None, None
        if e["positionId"] is not None:
            lot, how = by_pid.get(e["positionId"]), "positionId"
        else:
            cands = [x for x in lots if x.get("positionId") not in claimed and (
                (e["instrumentId"] not in (None, "") and str(x.get("instrumentId")) == str(e["instrumentId"]))
                or (e["symbol"] and x["symbol"] == e["symbol"]))]
            cands.sort(key=lambda x: str(x.get("openTime") or ""), reverse=True)
            if cands:
                lot, how = cands[0], "instrumentId" if e["instrumentId"] not in (None, "") else "symbol"
                claimed.add(lot.get("positionId"))
        f = filled_usd(lot) if lot else None
        pct = round(f / e["authorized_amount"], 4) if f is not None else None
        v = classify(pct)
        results.append({
            "symbol": (lot or {}).get("symbol") or e["symbol"], "expected_symbol": e["symbol"],
            "positionId": (lot or {}).get("positionId", e["positionId"]), "matched_by": how if lot else None,
            "found": lot is not None, "authorized_amount": e["authorized_amount"], "filled_usd": f,
            "fill_pct": round(pct * 100, 2) if pct is not None else None, "verdict": v,
            "severity": {"PASS": "OK", "PARTIAL_FILL": "SOFT", "FILL_MISSING": "HARD"}[v], "action": ACTIONS[v],
            "invested": (lot or {}).get("invested"), "units": (lot or {}).get("units"),
            "openRate": (lot or {}).get("openRate"), "openTime": (lot or {}).get("openTime"),
            "api_outcome": e["api_outcome"],
            **({"symbol_mismatch": True} if lot and e["symbol"] and lot["symbol"] != e["symbol"] else {}),
        })
    vs = {r["verdict"] for r in results}
    overall = "FILL_MISSING" if "FILL_MISSING" in vs else ("PARTIAL_FILL" if "PARTIAL_FILL" in vs else "PASS")
    return {"overall": overall, "exit_code": {"PASS": EXIT_PASS, "PARTIAL_FILL": EXIT_PARTIAL,
                                              "FILL_MISSING": EXIT_MISSING}[overall],
            "raw": {"timestamp": live["timestamp"], "xRequestId": live["xRequestId"], "n_lots": len(lots)},
            "results": results,
            "note": "API outcome label is informational only; verdict is from live lots."}


def write_audit(rep: dict, now: datetime) -> Path:
    d = audit_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{now.astimezone(IDT).strftime('%Y-%m-%d')}.jsonl"
    row = {"ts_utc": now.astimezone(timezone.utc).isoformat(), "ts_il": now.astimezone(IDT).isoformat(),
           "run_id": f"postfill-{now.astimezone(IDT).strftime('%Y%m%d-%H%M%S')}", "portfolio": "Momentum-HHHGDTJ",
           "script": "momentum_qa/postfill_check.py", "event": "POSTFILL_CHECK", "verdict": rep.get("overall"),
           "deviation": rep.get("overall") != "PASS",
           "deviation_code": None if rep.get("overall") == "PASS" else rep.get("overall"),
           "rationale": "; ".join(f"{r['symbol']} {r['positionId']} {r['verdict']} {r['fill_pct']}%"
                                  for r in rep.get("results") or []) or rep.get("error") or "",
           "details": {k: rep.get(k) for k in ("raw", "results", "error", "exit_code")}}
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    return f


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> int:
    ap = argparse.ArgumentParser(prog="momentum_qa.postfill_check", description="Momentum post-fill check")
    ap.add_argument("--raw", required=True, help="saved keys get-my-positions-and-orders MCP output")
    ap.add_argument("--expect", required=True, help="JSON file or inline list of {symbol|positionId, authorized_amount}")
    ap.add_argument("--out", required=True, help="report JSON path")
    ap.add_argument("--no-audit", action="store_true")
    a = ap.parse_args(argv)
    now = now or datetime.now(IDT)
    try:
        rep = check(load_json_file(a.raw) if Path(a.raw).exists() else _missing(a.raw), load_expect(a.expect))
    except (BadInput, OSError, ValueError) as e:
        rep = {"overall": "BAD_INPUT", "exit_code": EXIT_BAD_INPUT, "error": str(e), "results": []}
    rep = {"schema": "momentum.postfill.v1", "at": now.astimezone(IDT).isoformat(timespec="seconds"),
           "raw_file": a.raw, **rep}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, default=str) + "\n")
    if not a.no_audit:
        rep["audit_file"] = str(write_audit(rep, now))
    print(json.dumps({"overall": rep["overall"], "exit_code": rep["exit_code"], "out": str(out),
                      "results": [f"{r['symbol']} {r['positionId']} {r['verdict']} {r['fill_pct']}%"
                                  for r in rep["results"]], **({"error": rep["error"]} if rep.get("error") else {}),
                      **({"audit_file": rep["audit_file"]} if rep.get("audit_file") else {})}, default=str))
    return rep["exit_code"]


def _missing(p: str):
    raise BadInput(f"RAW_NOT_FOUND: {p}")


if __name__ == "__main__":
    sys.exit(main())

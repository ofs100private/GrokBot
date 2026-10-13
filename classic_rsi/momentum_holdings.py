"""Momentum holdings for the Classic cross-book rule (fix8 / fix8b).

Standing rule (Ofer 2026-10-13 01:44 IDT): Classic must NEVER buy a symbol already held in the Momentum book
(Momentum-HHHGDTJ, mirror 11630170). Sells/exits unaffected.

Source pin (fix8b, QA R3). Only reads from the MCP namespace `user-Momentum-HHHGDTJ` (SOURCE) are accepted.
How mirror 11630170 appears in the responses (worked out from get-my-positions-and-orders):
  * user-etoro (parent Ofer account): direct = Ofer's own positions; mirrors[] = copied agent portfolios,
    one entry per mirrorId (11368142 = Classic OfersClaw5-PRIYN, 11630170 = Momentum-HHHGDTJ).
  * user-Momentum-HHHGDTJ (the agent portfolio's own key connection): the SAME positions as the parent's
    mirrors[mirrorId=11630170] block, reported under `direct`; `mirrors` is [] (agent portfolios do not copy);
    the response carries no mirrorId and get-my-profile-and-scopes returns 403 for this key.
  So the "mirror 11630170 section" in a Momentum-namespace read is its `direct` block. A read is rejected if:
  the declared source is not user-Momentum-HHHGDTJ; statusCode != 200 or error set; `warnings` non-null;
  `mirrors` non-empty (fingerprint of the parent user-etoro response — parent positions are NEVER merged);
  or the 11630170 section has no positions and no pending orders (an empty read fails closed).
  Optional cross-check: a parent user-etoro read may be supplied; then its mirrors[mirrorId=11630170] must
  exist, be non-empty and carry the same instrument ids. Nothing from it is merged.

GO (QA R1): execute_pass takes the agent's OWN live read (raw response + capture time + declared source),
parses it in-process, requires capture age and the response's server timestamp both <= 60 s, and records
the xRequestId and the sha256 of the response in the GO audit. The shared file
/workspace/momentum-holdings-for-classic.json is ONLY a pre-filter for propose / auto_1h.

Producer CLI (read-only; never calls eToro itself):
    python3 -m classic_rsi.momentum_holdings --response <saved Momentum get-my-positions-and-orders JSON>
        [--source user-Momentum-HHHGDTJ] [--parent-response <saved user-etoro response>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .paths import paths

IDT = ZoneInfo("Asia/Jerusalem")
KIND = "momentum-holdings-for-classic-v2"
SOURCE = "user-Momentum-HHHGDTJ"
PARENT_SOURCE = "user-etoro"
PORTFOLIO = "Momentum-HHHGDTJ"
MIRROR_ID = 11630170
MAX_AGE_S = 60
REASON = "CROSS_BOOK_OVERLAP"
TERMINAL_ORDER = ("canceled", "rejected", "expired")


class MomentumReadError(ValueError):
    pass


def norm_symbol(s: Any) -> str:
    """Upper-case, strip, drop a trailing '.US' (eToro US listing suffix)."""
    x = str(s or "").strip().upper()
    return x[:-3] if x.endswith(".US") else x


def _parse_ts(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        head, _, frac = str(s).replace("Z", "").partition(".")
        try:
            t = datetime.fromisoformat(head + ("." + frac[:6] if frac else "") + "+00:00")
        except ValueError:
            return None
    return t if t.tzinfo else None


def extract_json(text: str) -> dict:
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        raise MomentumReadError("no JSON object in response")
    return json.loads(text[i:j + 1])


def response_sha256(resp: dict) -> str:
    return hashlib.sha256(json.dumps(resp, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _items(block: dict, origin: str) -> tuple[list, list]:
    hold, pend = [], []
    for p in block.get("positions") or []:
        m = p.get("market") or {}
        hold.append({"symbol": norm_symbol(m.get("symbol", p.get("symbol"))),
                     "instrumentId": m.get("instrumentId", p.get("instrumentId")),
                     "positionId": p.get("positionId"), "origin": origin})
    for o in block.get("orders") or []:
        if str(o.get("status")) in TERMINAL_ORDER:
            continue
        m = o.get("market") or {}
        pend.append({"symbol": norm_symbol(m.get("symbol", o.get("symbol"))),
                     "instrumentId": m.get("instrumentId", o.get("instrumentId")), "status": o.get("status"),
                     "origin": origin})
    return hold, pend


def parse_read(resp: Any, source: Any, parent_resp: Optional[dict] = None) -> dict[str, Any]:
    """Validate a Momentum get-my-positions-and-orders response (R2/R3). Raises MomentumReadError."""
    if source != SOURCE:
        raise MomentumReadError(f"MOMENTUM_SOURCE_MISMATCH: source {source!r} != {SOURCE!r}")
    if not isinstance(resp, dict):
        raise MomentumReadError("MOMENTUM_READ_INVALID: response is not an object")
    if resp.get("error") or int(resp.get("statusCode") or 0) != 200:
        raise MomentumReadError(f"MOMENTUM_READ_INVALID: statusCode={resp.get('statusCode')} error={resp.get('error')!r}")
    if resp.get("warnings"):
        raise MomentumReadError(f"MOMENTUM_READ_INVALID: warnings set {resp.get('warnings')!r}")
    if str(resp.get("account", "real")) != "real":
        raise MomentumReadError("MOMENTUM_READ_INVALID: account is not real")
    if resp.get("mirrors"):
        raise MomentumReadError("MOMENTUM_SOURCE_MISMATCH: response has mirrors[] (parent user-etoro shape); "
                                "parent positions are never merged")
    ts = _parse_ts(resp.get("timestamp"))
    if ts is None:
        raise MomentumReadError("MOMENTUM_READ_INVALID: response timestamp missing")
    if not resp.get("xRequestId"):
        raise MomentumReadError("MOMENTUM_READ_INVALID: xRequestId missing")
    direct = resp.get("direct")
    if not isinstance(direct, dict):
        raise MomentumReadError(f"MOMENTUM_MIRROR_MISSING: mirror {MIRROR_ID} section (direct) absent")
    hold, pend = _items(direct, f"mirror:{MIRROR_ID}")
    if not hold and not pend:
        raise MomentumReadError(f"MOMENTUM_READ_EMPTY: mirror {MIRROR_ID} section has no positions/orders")
    ids = {int(h["instrumentId"]) for h in hold + pend if h.get("instrumentId") is not None}
    cross = None
    if parent_resp is not None:
        mr = next((m for m in parent_resp.get("mirrors") or [] if int(m.get("mirrorId") or 0) == MIRROR_ID), None)
        if mr is None or not (mr.get("positions") or mr.get("orders")):
            raise MomentumReadError(f"MOMENTUM_MIRROR_MISSING: parent read has no non-empty mirror {MIRROR_ID}")
        ph, pp = _items(mr, f"parent-mirror:{MIRROR_ID}")
        pids = {int(h["instrumentId"]) for h in ph + pp if h.get("instrumentId") is not None}
        if pids != ids:
            raise MomentumReadError(f"MOMENTUM_SOURCE_MISMATCH: parent mirror {MIRROR_ID} ids {sorted(pids)} != {sorted(ids)}")
        cross = {"parent_xRequestId": parent_resp.get("xRequestId"), "match": True}
    return {"source": SOURCE, "mirrorId": MIRROR_ID, "portfolio": PORTFOLIO, "account": "real",
            "server_ts": ts, "asOf": ts.astimezone(IDT).isoformat(timespec="seconds"),
            "xRequestId": resp.get("xRequestId"), "response_sha256": response_sha256(resp),
            "symbols": {h["symbol"] for h in hold + pend if h["symbol"]}, "ids": ids,
            "holdings": hold, "pendingOrders": pend, "parent_cross_check": cross}


def build_snapshot(resp: dict, source: str = SOURCE, parent_resp: Optional[dict] = None) -> dict[str, Any]:
    r = parse_read(resp, source, parent_resp)
    return {"kind": KIND, "source": r["source"], "portfolio": PORTFOLIO, "mirrorId": MIRROR_ID, "account": "real",
            "read_only": True, "role": "PRE-FILTER ONLY (propose/auto_1h); GO requires the executor's own live read",
            "asOf": r["asOf"], "xRequestId": r["xRequestId"], "response_sha256": r["response_sha256"],
            "symbols": sorted(r["symbols"]), "instrumentIds": sorted(r["ids"]),
            "holdings": r["holdings"], "pendingOrders": r["pendingOrders"], "parent_cross_check": r["parent_cross_check"],
            "rule": "Classic never buys a symbol/instrument held in Momentum (Ofer 2026-10-13 01:44 IDT)"}


def snapshot_path() -> Path:
    return Path(paths()["momentum"])


def write_snapshot(snap: dict, path: Optional[Path] = None) -> Path:
    p = Path(path or snapshot_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".momentum-", suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(snap, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, p)
    return p


def load_snapshot(now: Optional[datetime] = None) -> dict[str, Any]:
    """Pre-filter loader. ok=False if missing/invalid/wrong source or mirror/empty."""
    p = snapshot_path()
    out: dict[str, Any] = {"ok": False, "path": str(p), "symbols": set(), "ids": set()}
    if not p.exists():
        out["error"] = "MOMENTUM_SNAPSHOT_MISSING"
        return out
    try:
        d = json.loads(p.read_text())
        ts = _parse_ts(d.get("asOf"))
        if d.get("kind") != KIND or ts is None or not isinstance(d.get("symbols"), list):
            out["error"] = "MOMENTUM_SNAPSHOT_INVALID"
            return out
        if d.get("source") != SOURCE or int(d.get("mirrorId") or 0) != MIRROR_ID:
            out["error"] = "MOMENTUM_SOURCE_MISMATCH"
            return out
        if not d["symbols"] and not d.get("instrumentIds"):
            out["error"] = "MOMENTUM_READ_EMPTY"
            return out
        out.update(symbols={norm_symbol(s) for s in d["symbols"]}, ids={int(i) for i in d.get("instrumentIds") or []},
                   asOf=d.get("asOf"), xRequestId=d.get("xRequestId"))
        if now is not None:
            out["age_s"] = round((now - ts).total_seconds(), 1)
        out["ok"] = True
    except (ValueError, TypeError) as exc:
        out["error"] = f"MOMENTUM_SNAPSHOT_INVALID: {exc}"
    return out


def overlaps(snap: dict, symbol: Any, instrument_id: Any) -> bool:
    s = norm_symbol(symbol)
    try:
        iid = int(instrument_id) if instrument_id is not None else None
    except (TypeError, ValueError):
        iid = None
    return bool(s and s in snap.get("symbols", set())) or (iid is not None and iid in snap.get("ids", set()))


def filter_buy_packs(packs: list[dict], snap: Optional[dict] = None) -> tuple[list[dict], list[dict]]:
    snap = snap if snap is not None else load_snapshot()
    kept, skipped = [], []
    for p in packs:
        inst = p.get("instrument") or {}
        sym, iid = inst.get("symbol") or p.get("symbol"), inst.get("instrumentId", p.get("instrumentId"))
        if not snap.get("ok"):
            skipped.append({"symbol": sym, "instrumentId": iid, "reason": snap.get("error") or "MOMENTUM_SNAPSHOT_MISSING"})
        elif overlaps(snap, sym, iid):
            skipped.append({"symbol": sym, "instrumentId": iid, "reason": REASON,
                            "momentum_asOf": snap.get("asOf"), "momentum_xRequestId": snap.get("xRequestId")})
        else:
            kept.append(p)
    return kept, skipped


def filter_symbols(symbols: list[str], snap: Optional[dict] = None) -> tuple[list[str], list[dict]]:
    snap = snap if snap is not None else load_snapshot()
    kept, skipped = [], []
    for s in symbols:
        if not snap.get("ok"):
            skipped.append({"symbol": s, "reason": snap.get("error") or "MOMENTUM_SNAPSHOT_MISSING"})
        elif overlaps(snap, s, None):
            skipped.append({"symbol": s, "reason": REASON})
        else:
            kept.append(s)
    return kept, skipped


def verify_go_read(read: Optional[dict], now: datetime) -> dict[str, Any]:
    """R1: the executor's own live read for THIS GO.
    read = {"source": "user-Momentum-HHHGDTJ", "captured_at": ISO tz (when the agent got the response),
            "response": raw dict, optional "parent_response": raw user-etoro dict}.
    Returns {ok, code, error, ...audit}; never reads the shared file."""
    out: dict[str, Any] = {"ok": False, "max_s": MAX_AGE_S}
    if not isinstance(read, dict) or read.get("response") is None:
        out.update(code="MOMENTUM_READ_MISSING", error="no live Momentum read passed to GO")
        return out
    out["source"] = read.get("source")
    try:
        r = parse_read(read.get("response"), read.get("source"), read.get("parent_response"))
    except MomentumReadError as exc:
        msg = str(exc)
        code = msg.split(":")[0] if msg.startswith("MOMENTUM_") else "MOMENTUM_READ_INVALID"
        out.update(code=code, error=msg)
        return out
    cap = _parse_ts(read.get("captured_at"))
    cap_age = None if cap is None else (now - cap).total_seconds()
    srv_age = (now - r["server_ts"]).total_seconds()
    out.update(xRequestId=r["xRequestId"], response_sha256=r["response_sha256"], mirrorId=MIRROR_ID,
               captured_at=read.get("captured_at"), capture_age_s=None if cap_age is None else round(cap_age, 1),
               server_asOf=r["asOf"], server_age_s=round(srv_age, 1), symbols=sorted(r["symbols"]),
               instrumentIds=sorted(r["ids"]), pending_orders=len(r["pendingOrders"]),
               parent_cross_check=r["parent_cross_check"], _snap={"ok": True, "symbols": r["symbols"], "ids": r["ids"]})
    if cap_age is None or not (-5 <= cap_age <= MAX_AGE_S) or not (-5 <= srv_age <= MAX_AGE_S):
        out.update(code="MOMENTUM_SNAPSHOT_STALE", error="capture or server timestamp older than 60 s (or missing)")
        return out
    out.update(ok=True, code=None, error=None)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write the read-only Momentum PRE-FILTER snapshot from a saved "
                                             "user-Momentum-HHHGDTJ get-my-positions-and-orders response.")
    ap.add_argument("--response", required=True)
    ap.add_argument("--source", default=SOURCE)
    ap.add_argument("--parent-response")
    a = ap.parse_args(argv)
    parent = extract_json(Path(a.parent_response).read_text()) if a.parent_response else None
    snap = build_snapshot(extract_json(Path(a.response).read_text()), a.source, parent)
    p = write_snapshot(snap)
    print(json.dumps({"path": str(p), "asOf": snap["asOf"], "xRequestId": snap["xRequestId"],
                      "response_sha256": snap["response_sha256"], "symbols": snap["symbols"],
                      "instrumentIds": snap["instrumentIds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

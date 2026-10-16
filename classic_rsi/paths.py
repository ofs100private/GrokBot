"""Fixed production paths for the Classic FULL AUTO gate (fix2).

Production (env CLASSIC_EXEC_TEST_ROOT unset) — hard-coded, not overridable by CLI:
  audit dir      /workspace/classic_rsi/audit
  QA verdicts    /workspace/classic_rsi/audit/qa/
                   run-QA   : qa-verdict-run-<auto_run_id>.json
                   order-QA : qa-verdict-order-<pack_sha256[:16]>.json
  GO locks       /workspace/classic_rsi/audit/placed/
  live book      /workspace/classic-portfolio-for-app.json   (asOf <= 60 s; cash + positions)
  score data     /workspace/classic-rebalance/scores-latest.json
  score sidecar  /workspace/classic-rebalance/scores-latest.sha256  (`<sha256hex>  scores-latest.json`; written
                 atomically by classic_rsi.scorer; test mode: <dir>/scores.sha256)
  momentum       /workspace/momentum-holdings-for-classic.json (fix8; read-only Momentum holdings, <= 60 s at GO)
  evidence       /workspace/classic_rsi/evidence/{p_registry,edge_registry}.json (sha pinned)

Test mode (env CLASSIC_EXEC_TEST_ROOT=<dir>): every path above is re-rooted under <dir>, the
registry sha pins are not enforced, every output carries test_mode=true, and buy/close payloads
use account='demo' so a test-mode GO can never be copied to the real account.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

TEST_ENV = "CLASSIC_EXEC_TEST_ROOT"
PKG = Path(__file__).resolve().parent
PROD = {
    "audit_dir": Path("/workspace/classic_rsi/audit"),
    "qa_dir": Path("/workspace/classic_rsi/audit/qa"),
    "lock_dir": Path("/workspace/classic_rsi/audit/placed"),
    "book": Path("/workspace/classic-portfolio-for-app.json"),
    "scores": Path("/workspace/classic-rebalance/scores-latest.json"),
    "momentum": Path("/workspace/momentum-holdings-for-classic.json"),
    "evidence_dir": PKG / "evidence",
    # 2026-10-16: saved user-OfersClaw5 get-my-trading-history read (today's opened+closed positions)
    "history": Path("/workspace/classic_rsi/state/trading-history-today.json"),
}


def paths() -> dict[str, Any]:
    root = os.environ.get(TEST_ENV)
    if not root:
        return {**PROD, "test_mode": False, "account": "real"}
    r = Path(root)
    return {"audit_dir": r / "audit", "qa_dir": r / "audit" / "qa", "lock_dir": r / "audit" / "placed",
            "book": r / "book.json", "scores": r / "scores.json", "momentum": r / "momentum.json", "evidence_dir": r / "evidence",
            "history": r / "history.json", "test_mode": True, "test_root": str(r), "account": "demo"}


def run_verdict_path(run_id: str) -> Path:
    return paths()["qa_dir"] / f"qa-verdict-run-{run_id}.json"


def order_verdict_path(pack_sha256: str) -> Path:
    return paths()["qa_dir"] / f"qa-verdict-order-{pack_sha256[:16]}.json"

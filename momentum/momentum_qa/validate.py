"""Hard QA gate for Momentum screener + position_manager outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_SECTOR = {"XLK", "XLE", "XLF", "XLV", "XLY", "XLI", "XLB", "XLU", "XLP", "XLRE", "XLC"}
ALLOWED_COMMODITY = {"GLD", "SLV", "USO", "CPER", "URA", "DBA"}
REQUIRED_MCP = {
    "account",
    "direction",
    "symbol",
    "orderType",
    "leverage",
    "amount",
    "stopLossRate",
    "stopLossType",
}
FORBIDDEN_MCP = {"isBuy", "isTakeProfitEnabled"}


@dataclass
class QaVerdict:
    ok: bool
    verdict: str  # PASS | FAIL | HOLD
    reasons: list[str] = field(default_factory=list)
    deviations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "deviations": self.deviations,
        }


def _fail(reasons: list[str], deviations: list[dict] | None = None) -> QaVerdict:
    return QaVerdict(False, "FAIL", reasons, deviations or [])


def validate_candidate(c: dict[str, Any], *, allocation_usd: float = 1000) -> QaVerdict:
    reasons: list[str] = []
    deviations: list[dict] = []

    if c.get("action") in ("HALT", "SKIP"):
        rationale = c.get("details") or c.get("reason") or "regime/session gate"
        return QaVerdict(True, "PASS", [f"Non-buy gate OK: {c.get('action')} — {rationale}"])

    if c.get("action") != "BUY":
        return _fail([f"Unknown action {c.get('action')}"])

    rationale = c.get("rationale") or c.get("reason")
    if not rationale:
        reasons.append("Missing rationale/reason for BUY")
        deviations.append({"code": "NO_RATIONALE", "msg": "Every BUY needs a clear rationale"})

    asset = c.get("asset_class")
    if asset not in ("STOCK", "ETF", "COMMODITY"):
        reasons.append(f"Invalid asset_class={asset}")

    sym = c.get("symbol") or c.get("etoro_symbol")
    if not sym:
        reasons.append("Missing symbol")

    if asset == "ETF" and sym not in ALLOWED_SECTOR:
        reasons.append(f"ETF {sym} not in sector allowlist")
        deviations.append({"code": "UNIVERSE_BREACH", "symbol": sym})
    if asset == "COMMODITY" and sym not in ALLOWED_COMMODITY:
        reasons.append(f"Commodity {sym} not in allowlist")
        deviations.append({"code": "UNIVERSE_BREACH", "symbol": sym})

    rs = c.get("rs_rating")
    if rs is None or int(rs) < 80:
        reasons.append(f"RS rating {rs} < 80")

    mcp = c.get("mcp_order_params") or {}
    missing = REQUIRED_MCP - set(mcp)
    if missing:
        reasons.append(f"mcp_order_params missing fields: {sorted(missing)}")
    bad = FORBIDDEN_MCP & set(mcp)
    if bad:
        reasons.append(f"Forbidden legacy mcp fields: {sorted(bad)}")
        deviations.append({"code": "BAD_MCP_SHAPE", "fields": sorted(bad)})

    if mcp.get("account") != "real":
        reasons.append("account must be real")
        deviations.append({"code": "DEMO_OR_BAD_ACCOUNT"})
    if mcp.get("direction") != "buy":
        reasons.append("direction must be buy (long-only)")
    if mcp.get("leverage") != 1:
        reasons.append("leverage must be 1")
        deviations.append({"code": "LEVERAGE_NE_1"})
    if mcp.get("orderType") != "mkt":
        reasons.append("orderType must be mkt for EOD print")
    if mcp.get("stopLossType") != "fixed":
        reasons.append("stopLossType must be fixed")

    amt = mcp.get("amount")
    if amt is None or float(amt) <= 0 or float(amt) > float(allocation_usd) + 1e-6:
        reasons.append(f"amount {amt} exceeds allocation cap {allocation_usd}")
        deviations.append({"code": "SIZE_CAP"})

    stop = mcp.get("stopLossRate")
    price = c.get("price") or c.get("current_price")
    if stop is None or price is None:
        reasons.append("Missing stopLossRate or price")
    else:
        # Absolute price stop: must be below price for long
        if float(stop) >= float(price):
            reasons.append(f"stopLossRate {stop} not below price {price}")
        # Reject obvious percent mistakes (e.g. stop=6 meaning 6%)
        if float(stop) < 50 and float(price) > 100:
            reasons.append(
                f"stopLossRate {stop} looks like a percent, not absolute price (price={price})"
            )
            deviations.append({"code": "STOP_LOOKS_LIKE_PERCENT"})

    rvol = c.get("rvol")
    reason = c.get("reason") or c.get("setup_type")
    if asset == "STOCK":
        if reason == "MOMENTUM_BREAKOUT":
            if rvol is None or float(rvol) < 2.0:
                reasons.append(f"STOCK MOMENTUM_BREAKOUT requires RVOL>=2.0, got {rvol}")
                deviations.append({"code": "STOCK_RVOL_FAIL"})
            if rs is not None and int(rs) < 90:
                reasons.append(f"MOMENTUM_BREAKOUT requires RS>=90, got {rs}")
                deviations.append({"code": "BREAKOUT_RS_FAIL"})
        elif reason in ("VOLUME_BREAKOUT", "BREAKOUT"):
            if rvol is None or float(rvol) < 1.5:
                reasons.append(f"STOCK breakout requires RVOL>=1.5, got {rvol}")
                deviations.append({"code": "STOCK_RVOL_FAIL"})

    # Soft-regime defense: VCP / quiet VOLUME_BREAKOUT must not PASS as BUY
    regime_mode = (c.get("regime_mode") or "").upper()
    if asset == "STOCK" and regime_mode == "SOFT":
        if reason in ("VCP_SETUP", "VOLUME_BREAKOUT"):
            reasons.append(
                f"SOFT regime blocks VCP/VOLUME_BREAKOUT BUY (got {reason}) — "
                "use REGIME_SOFT_VCP_BLOCK"
            )
            deviations.append({"code": "REGIME_SOFT_VCP_BLOCK", "symbol": sym})
        elif reason == "MOMENTUM_BREAKOUT":
            if rvol is None or float(rvol) < 2.5:
                reasons.append(
                    f"SOFT regime MOMENTUM_BREAKOUT requires RVOL>=2.5, got {rvol}"
                )
                deviations.append({"code": "REGIME_SOFT_RVOL", "symbol": sym})
            if rs is not None and int(rs) < 90:
                reasons.append(f"SOFT regime STOCK needs RS>=90, got {rs}")
                deviations.append({"code": "REGIME_SOFT_RS", "symbol": sym})

    # DWM hard place gate (QA Bot 2026-09-11): week or month red → FAIL, never PASS+BUY
    day_pct = c.get("day_pct")
    week_pct = c.get("week_pct")
    month_pct = c.get("month_pct")
    if day_pct is None or week_pct is None or month_pct is None:
        reasons.append("BUY missing day_pct/week_pct/month_pct (DWM required)")
        deviations.append({"code": "DWM_MISSING", "symbol": sym})
    else:
        if float(week_pct) < 0 or float(month_pct) < 0:
            reasons.append(
                f"DWM_STRENGTH_FAIL: day={float(day_pct):.2f}% week={float(week_pct):.2f}% month={float(month_pct):.2f}%"
            )
            deviations.append({"code": "DWM_STRENGTH_FAIL", "symbol": sym})
        # MOMENTUM_BREAKOUT also requires day green
        if reason == "MOMENTUM_BREAKOUT" and float(day_pct) < 0:
            reasons.append(
                f"MOMENTUM_BREAKOUT requires day_pct>=0, got {float(day_pct):.2f}%"
            )
            deviations.append({"code": "BREAKOUT_DAY_RED", "symbol": sym})

    if reasons:
        return _fail(reasons, deviations)
    return QaVerdict(
        True,
        "PASS",
        [f"PASS {sym}: {rationale} | RS={rs} RVOL={rvol} class={asset}"],
    )


def validate_screener_output(
    signals: list[dict],
    *,
    allocation_usd: float = 1000,
    max_picks: int = 4,
) -> tuple[list[dict], QaVerdict]:
    """Annotate each signal with qa; overall FAIL if any BUY fails or too many picks."""
    if not isinstance(signals, list):
        return [], _fail(["Screener output not a list"])

    annotated: list[dict] = []
    all_reasons: list[str] = []
    all_devs: list[dict] = []
    buy_count = 0
    stock_buys = 0
    etf_buys = 0
    commodity_buys = 0
    breakout_buys = 0

    for c in signals:
        row = dict(c)
        # Defense: never leave a DWM-red BUY as PASS — rewrite to SKIP before pack score
        if row.get("action") == "BUY":
            wp, mp = row.get("week_pct"), row.get("month_pct")
            if wp is not None and mp is not None and (float(wp) < 0 or float(mp) < 0):
                row["action"] = "SKIP"
                row["reason"] = "DWM_STRENGTH_FAIL"
                row["rationale"] = (
                    f"DWM_STRENGTH_FAIL {row.get('symbol')}: week={wp}% month={mp}% — "
                    "rewritten from BUY before place QA"
                )
                row["mcp_order_params"] = None
            # Soft-regime defense: rewrite soft VCP / quiet volume BUYs
            elif (
                (row.get("regime_mode") or "").upper() == "SOFT"
                and row.get("asset_class") == "STOCK"
                and (row.get("reason") in ("VCP_SETUP", "VOLUME_BREAKOUT"))
            ):
                row["action"] = "SKIP"
                row["reason"] = "REGIME_SOFT_VCP_BLOCK"
                row["rationale"] = (
                    f"REGIME_SOFT_VCP_BLOCK {row.get('symbol')}: soft tape — "
                    f"rewritten from BUY ({row.get('reason')}) before place QA"
                )
                row["mcp_order_params"] = None
            elif (
                (row.get("regime_mode") or "").upper() == "SOFT"
                and row.get("asset_class") == "STOCK"
                and row.get("reason") == "MOMENTUM_BREAKOUT"
            ):
                rv = row.get("rvol")
                rs_v = row.get("rs_rating")
                if (rv is None or float(rv) < 2.5) or (rs_v is not None and int(rs_v) < 90):
                    row["action"] = "SKIP"
                    row["reason"] = "REGIME_SOFT_VCP_BLOCK"
                    row["rationale"] = (
                        f"REGIME_SOFT_VCP_BLOCK {row.get('symbol')}: soft BREAKOUT "
                        f"needs RVOL>=2.5 RS>=90 (got RVOL={rv} RS={rs_v}) — rewritten"
                    )
                    row["mcp_order_params"] = None
        v = validate_candidate(row, allocation_usd=allocation_usd)
        row["qa"] = v.to_dict()
        # Ensure rationale field for audit consumers
        if "rationale" not in row:
            row["rationale"] = (
                row.get("details")
                or row.get("reason")
                or row.get("setup_type")
                or row.get("action")
            )
        annotated.append(row)
        if row.get("action") == "BUY":
            buy_count += 1
            ac = row.get("asset_class")
            if ac == "STOCK":
                stock_buys += 1
                if row.get("reason") == "MOMENTUM_BREAKOUT":
                    breakout_buys += 1
            elif ac == "ETF":
                etf_buys += 1
            elif ac == "COMMODITY":
                commodity_buys += 1
        if not v.ok:
            all_reasons.extend(v.reasons)
            all_devs.extend(v.deviations)

    # Pack rules (2026-09-16): max 3 STOCK (prefer ≤2 breakout) + 1 sector ETF; total <= 4
    if stock_buys > 3:
        all_reasons.append(f"Too many STOCK BUYs: {stock_buys} > 3")
        all_devs.append({"code": "MAX_STOCK_PICKS", "stock_buys": stock_buys})
    if breakout_buys > 2:
        all_reasons.append(f"Too many MOMENTUM_BREAKOUT BUYs: {breakout_buys} > 2")
        all_devs.append({"code": "MAX_BREAKOUT_PICKS", "breakout_buys": breakout_buys})
    if etf_buys > 1:
        all_reasons.append(f"Too many ETF BUYs: {etf_buys} > 1")
        all_devs.append({"code": "MAX_ETF_PICKS", "etf_buys": etf_buys})
    if buy_count > max_picks:
        all_reasons.append(f"Too many BUYs: {buy_count} > max_picks {max_picks}")
        all_devs.append({"code": "MAX_PICKS"})

    if all_reasons:
        overall = _fail(all_reasons, all_devs)
    else:
        overall = QaVerdict(
            True,
            "PASS",
            [
                f"Screener pack PASS ({buy_count} buys: stocks={stock_buys} "
                f"breakout={breakout_buys} etf={etf_buys} commodity={commodity_buys}, "
                f"{len(signals)} rows)"
            ],
        )

    for row in annotated:
        row["qa_pack"] = overall.to_dict()
    return annotated, overall


def validate_position_action(action: dict[str, Any]) -> QaVerdict:
    reasons: list[str] = []
    deviations: list[dict] = []
    act = action.get("action")
    sym = action.get("symbol")

    if act in ("SKIP", "HOLD", "ERROR"):
        rationale = action.get("reason") or action.get("details") or act
        if act == "ERROR":
            return _fail([f"ERROR on {sym}: {rationale}"], [{"code": "POS_MGR_ERROR", "symbol": sym}])
        return QaVerdict(True, "PASS", [f"{act} {sym or ''}: {rationale}"])

    rationale = action.get("reason") or action.get("rationale")
    if not rationale:
        reasons.append("Missing rationale for position action")
        deviations.append({"code": "NO_RATIONALE", "symbol": sym})

    if act == "CLOSE":
        if action.get("reason") != "BELOW_SMA50" and "SMA50" not in str(rationale).upper():
            reasons.append("CLOSE must be justified by BELOW_SMA50")
            deviations.append({"code": "CLOSE_WITHOUT_SMA50_RULE", "symbol": sym})
        if action.get("last") is None or action.get("sma50") is None:
            reasons.append("CLOSE missing last/sma50 evidence")
    elif act == "MOVE_SL_BREAKEVEN":
        if action.get("reason") != "HIT_2R" and "2R" not in str(rationale).upper():
            reasons.append("MOVE_SL_BREAKEVEN must cite HIT_2R")
            deviations.append({"code": "BE_WITHOUT_2R", "symbol": sym})
        if action.get("new_stop_loss") is None:
            reasons.append("Missing new_stop_loss")
        rm = action.get("r_multiple")
        if rm is not None and float(rm) < 2.0:
            reasons.append(f"r_multiple {rm} < 2")
            deviations.append({"code": "BE_BEFORE_2R", "symbol": sym})
    elif act == "TRAIL_SL":
        rat_u = str(rationale).upper() + " " + str(action.get("rationale") or "").upper()
        if action.get("reason") not in ("HIT_1R", "TRAIL_1R") and "1R" not in rat_u:
            reasons.append("TRAIL_SL must cite 1R")
            deviations.append({"code": "TRAIL_WITHOUT_1R", "symbol": sym})
        if action.get("new_stop_loss") is None:
            reasons.append("Missing new_stop_loss")
            deviations.append({"code": "TRAIL_NO_STOP", "symbol": sym})
        prior = action.get("prior_stop_loss")
        if prior is None:
            prior = action.get("stop_loss")
        if prior is not None and action.get("new_stop_loss") is not None:
            if float(action["new_stop_loss"]) < float(prior) - 1e-9:
                reasons.append(
                    f"new_stop_loss {action['new_stop_loss']} below prior stop {prior}"
                )
                deviations.append({"code": "TRAIL_LOWERS_STOP", "symbol": sym})
        rm = action.get("r_multiple")
        if rm is not None and float(rm) < 1.0:
            reasons.append(f"r_multiple {rm} < 1 for TRAIL_SL")
            deviations.append({"code": "TRAIL_BEFORE_1R", "symbol": sym})
    else:
        reasons.append(f"Unknown position action {act}")

    if reasons:
        return _fail(reasons, deviations)
    return QaVerdict(True, "PASS", [f"PASS {act} {sym}: {rationale}"])

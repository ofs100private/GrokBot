#!/usr/bin/env python3
"""Unit tests for momentum_qa.validate — run via:
  cd /workspace && /workspace/screener-venv/bin/python momentum_qa/test_validate.py
or:
  /workspace/screener-venv/bin/python -c "import runpy; runpy.run_path('momentum_qa/test_validate.py')"
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Prefer package import; fall back to sibling import when run from momentum_qa/
try:
    from momentum_qa.validate import (
        validate_candidate,
        validate_position_action,
        validate_screener_output,
    )
    from momentum_qa.event_calendar import is_event_vol_freeze, EVENT_DAYS
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate import (  # type: ignore
        validate_candidate,
        validate_position_action,
        validate_screener_output,
    )
    from event_calendar import is_event_vol_freeze, EVENT_DAYS  # type: ignore

IL = ZoneInfo("Asia/Jerusalem")


def _mcp(sym: str, stop: float = 188.0, amount: float = 1000) -> dict:
    return {
        "account": "real",
        "direction": "buy",
        "symbol": sym,
        "orderType": "mkt",
        "leverage": 1,
        "amount": amount,
        "stopLossRate": stop,
        "stopLossType": "fixed",
    }


def _stock_buy(
    sym: str,
    rs: int = 92,
    rvol: float = 2.0,
    reason: str = "VOLUME_BREAKOUT",
    setup_type: str = "BREAKOUT",
) -> dict:
    return {
        "action": "BUY",
        "symbol": sym,
        "asset_class": "STOCK",
        "reason": reason,
        "setup_type": setup_type,
        "rationale": f"{reason} {sym}",
        "price": 200,
        "rs_rating": rs,
        "rvol": rvol,
        "day_pct": 1.0,
        "week_pct": 2.0,
        "month_pct": 3.0,
        "mcp_order_params": _mcp(sym),
    }


def _breakout_buy(sym: str, rs: int = 95, rvol: float = 2.5) -> dict:
    return _stock_buy(
        sym, rs=rs, rvol=rvol, reason="MOMENTUM_BREAKOUT", setup_type="BREAKOUT"
    )


def _vcp_buy(sym: str, rs: int = 85, rvol: float = 0.8) -> dict:
    return _stock_buy(
        sym, rs=rs, rvol=rvol, reason="VCP_SETUP", setup_type="VCP_READY"
    )


def _etf_buy(sym: str = "XLK", rs: int = 88) -> dict:
    return {
        "action": "BUY",
        "symbol": sym,
        "asset_class": "ETF",
        "reason": "VCP_SETUP",
        "setup_type": "VCP_READY",
        "rationale": f"vcp {sym}",
        "price": 200,
        "rs_rating": rs,
        "rvol": 0.8,
        "day_pct": 0.5,
        "week_pct": 1.0,
        "month_pct": 2.0,
        "mcp_order_params": _mcp(sym, stop=190.0),
    }


def test_halt_pass():
    v = validate_candidate({"action": "HALT", "reason": "MARKET_REGIME_RISK", "details": "SPX < SMA50"})
    assert v.ok and v.verdict == "PASS"


def test_buy_bad_mcp_fail():
    c = {
        "action": "BUY",
        "symbol": "AAPL",
        "asset_class": "STOCK",
        "reason": "VOLUME_BREAKOUT",
        "rationale": "breakout",
        "price": 200,
        "rs_rating": 90,
        "rvol": 2.0,
        "day_pct": 1.0,
        "week_pct": 2.0,
        "month_pct": 3.0,
        "mcp_order_params": {
            "symbol": "AAPL",
            "isBuy": True,
            "leverage": 1,
            "amount": 1000,
            "stopLossRate": 188,
            "isTakeProfitEnabled": False,
        },
    }
    v = validate_candidate(c)
    assert not v.ok


def test_buy_good_pass():
    v = validate_candidate(_stock_buy("AAPL"))
    assert v.ok, v.reasons


def test_dwm_fail_on_buy():
    c = _stock_buy("NVDA")
    c["week_pct"] = -5.0
    c["month_pct"] = -1.0
    c["reason"] = "VCP_SETUP"
    c["rvol"] = 0.5
    v = validate_candidate(c)
    assert not v.ok
    assert any(d.get("code") == "DWM_STRENGTH_FAIL" for d in v.deviations)


def test_dwm_skip_pass():
    v = validate_candidate({
        "action": "SKIP",
        "reason": "DWM_STRENGTH_FAIL",
        "details": "week red",
        "rationale": "DWM_STRENGTH_FAIL blocked before place",
    })
    assert v.ok and v.verdict == "PASS"


def test_close_needs_sma50():
    v = validate_position_action({"action": "CLOSE", "symbol": "X", "reason": "WHIM", "rationale": "felt like it"})
    assert not v.ok


def test_close_ok():
    v = validate_position_action({
        "action": "CLOSE", "symbol": "X", "reason": "BELOW_SMA50",
        "rationale": "below SMA50", "last": 10, "sma50": 11
    })
    assert v.ok


# --- 2026-09-15 playbook ---

def test_pack_3_stocks_plus_1_etf_pass():
    signals = [
        _breakout_buy("AAPL", rs=95),
        _breakout_buy("MSFT", rs=93),
        _vcp_buy("NVDA", rs=91),
        _etf_buy("XLK", rs=88),
    ]
    annotated, pack = validate_screener_output(signals, max_picks=4)
    assert pack.ok, pack.reasons
    assert pack.verdict == "PASS"
    buys = [r for r in annotated if r["action"] == "BUY"]
    assert len(buys) == 4
    assert sum(1 for r in buys if r["asset_class"] == "STOCK") == 3
    assert sum(1 for r in buys if r["asset_class"] == "ETF") == 1


def test_pack_4_stocks_fail():
    signals = [
        _stock_buy("AAPL"),
        _stock_buy("MSFT"),
        _stock_buy("NVDA"),
        _stock_buy("AMD"),
    ]
    annotated, pack = validate_screener_output(signals, max_picks=4)
    assert not pack.ok
    assert any("STOCK" in r for r in pack.reasons) or any(
        d.get("code") == "MAX_STOCK_PICKS" for d in pack.deviations
    )


def test_soft_regime_breakout_buy_ok():
    """Soft-regime STOCK MOMENTUM_BREAKOUT with RVOL>=2.5 RS>=90 passes QA."""
    c = _breakout_buy("NOW", rs=91, rvol=2.6)
    c["regime_mode"] = "SOFT"
    c["rationale"] = "MOMENTUM_BREAKOUT soft regime RS>=90 RVOL>=2.5"
    v = validate_candidate(c)
    assert v.ok, v.reasons


def test_hard_halt_vix_skip_pass():
    """HARD halt SKIP rows remain PASS as non-buy gates; HALT action also PASS."""
    v_halt = validate_candidate({
        "action": "HALT",
        "reason": "MARKET_REGIME_RISK",
        "details": "HARD HALT VIX>=25",
        "regime": {"mode": "HARD_HALT", "vix_hard": True, "vix_close": 27.0},
    })
    assert v_halt.ok and v_halt.verdict == "PASS"
    v_skip = validate_candidate({
        "action": "SKIP",
        "reason": "REGIME_HARD_HALT",
        "rationale": "REGIME_HARD_HALT blocked NOW (VIX hard)",
    })
    assert v_skip.ok and v_skip.verdict == "PASS"


# --- 2026-09-16 full fix ---

def test_pack_2_breakout_1_vcp_0_etf_pass():
    """Pack: 2 breakouts + 1 VCP + 0 ETF → PASS."""
    signals = [
        _breakout_buy("AAPL", rs=96, rvol=3.0),
        _breakout_buy("MSFT", rs=94, rvol=2.8),
        _vcp_buy("CRM", rs=88),
    ]
    annotated, pack = validate_screener_output(signals, max_picks=4)
    assert pack.ok, pack.reasons
    buys = [r for r in annotated if r["action"] == "BUY"]
    assert len(buys) == 3
    assert sum(1 for r in buys if r["reason"] == "MOMENTUM_BREAKOUT") == 2
    assert sum(1 for r in buys if r["reason"] == "VCP_SETUP") == 1
    assert sum(1 for r in buys if r["asset_class"] == "ETF") == 0


def test_soft_regime_vcp_buy_rewritten_or_fail():
    """Soft regime VCP BUY must be rewritten to SKIP or FAIL if it slips through."""
    c = _vcp_buy("PANW", rs=92)
    c["regime_mode"] = "SOFT"
    # Direct candidate QA should FAIL
    v = validate_candidate(c)
    assert not v.ok
    assert any(d.get("code") == "REGIME_SOFT_VCP_BLOCK" for d in v.deviations)
    # Pack path should rewrite to SKIP and pack PASS
    annotated, pack = validate_screener_output([c], max_picks=4)
    assert annotated[0]["action"] == "SKIP"
    assert annotated[0]["reason"] == "REGIME_SOFT_VCP_BLOCK"
    assert pack.ok, pack.reasons


def test_event_vol_freeze_skip_pass():
    """EVENT_VOL_FREEZE SKIP/HALT PASS as non-buy."""
    v_skip = validate_candidate({
        "action": "SKIP",
        "reason": "EVENT_VOL_FREEZE",
        "rationale": "EVENT_VOL_FREEZE blocked AAPL: FOMC day",
    })
    assert v_skip.ok and v_skip.verdict == "PASS"
    v_halt = validate_candidate({
        "action": "HALT",
        "reason": "EVENT_VOL_FREEZE",
        "details": "FOMC decision day — zero new BUYs",
    })
    assert v_halt.ok and v_halt.verdict == "PASS"


def test_event_calendar_fomc_2026_09_16():
    """2026-09-16 is FOMC decision day → freeze True."""
    assert date(2026, 9, 16) in EVENT_DAYS
    # Evening IL on Sep 16 (still NY Sep 16)
    now = datetime(2026, 9, 16, 22, 40, tzinfo=IL)
    freeze, reason = is_event_vol_freeze(now)
    assert freeze, reason
    assert "EVENT_VOL_FREEZE" in reason


def test_trail_sl_validate_pass():
    """TRAIL_SL with 1R citation + new_stop_loss PASS."""
    v = validate_position_action({
        "action": "TRAIL_SL",
        "symbol": "AAPL",
        "reason": "HIT_1R",
        "rationale": "Trail SL on AAPL: R=1.40 ≥ 1R — new_stop=190.0",
        "new_stop_loss": 190.0,
        "prior_stop_loss": 188.0,
        "r_multiple": 1.4,
        "last": 205.0,
        "sma50": 195.0,
    })
    assert v.ok, v.reasons


def test_trail_sl_below_prior_fail():
    v = validate_position_action({
        "action": "TRAIL_SL",
        "symbol": "AAPL",
        "reason": "HIT_1R",
        "rationale": "Trail 1R",
        "new_stop_loss": 180.0,
        "prior_stop_loss": 188.0,
        "r_multiple": 1.2,
    })
    assert not v.ok
    assert any(d.get("code") == "TRAIL_LOWERS_STOP" for d in v.deviations)


def test_pack_3_breakouts_fail():
    """More than 2 MOMENTUM_BREAKOUT BUYs → pack FAIL."""
    signals = [
        _breakout_buy("AAPL"),
        _breakout_buy("MSFT"),
        _breakout_buy("NVDA"),
    ]
    annotated, pack = validate_screener_output(signals, max_picks=4)
    assert not pack.ok
    assert any(d.get("code") == "MAX_BREAKOUT_PICKS" for d in pack.deviations)


if __name__ == "__main__":
    test_halt_pass()
    test_buy_bad_mcp_fail()
    test_buy_good_pass()
    test_dwm_fail_on_buy()
    test_dwm_skip_pass()
    test_close_needs_sma50()
    test_close_ok()
    test_pack_3_stocks_plus_1_etf_pass()
    test_pack_4_stocks_fail()
    test_soft_regime_breakout_buy_ok()
    test_hard_halt_vix_skip_pass()
    test_pack_2_breakout_1_vcp_0_etf_pass()
    test_soft_regime_vcp_buy_rewritten_or_fail()
    test_event_vol_freeze_skip_pass()
    test_event_calendar_fomc_2026_09_16()
    test_trail_sl_validate_pass()
    test_trail_sl_below_prior_fail()
    test_pack_3_breakouts_fail()
    print("ALL_TESTS_PASS")

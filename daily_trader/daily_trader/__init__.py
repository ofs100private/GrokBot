"""Daily Trader tooling — same-session leveraged breakout scan + backtest.

Analysis / tooling only. Never places trades.
Bot: Daily Trader (agent id 8064c9a6-a0f7-4e52-8f7d-4cd4288b7256)
Mandate: daily-trader-strategy skill.
"""

__version__ = "1.0.0"
__bot_name__ = "Daily Trader"
__agent_id__ = "8064c9a6-a0f7-4e52-8f7d-4cd4288b7256"

# Book defaults (tools only — do not place)
DEFAULT_EQUITY = 2000.0
DEFAULT_RISK_PCT = 0.015  # 1.5% mid of 1–2% band
DAILY_LOSS_CIRCUIT = -0.03  # −3% equity
LEV_STOCK_DEFAULT = 3
LEV_CRYPTO_DEFAULT = 2
LEV_COMMODITY_DEFAULT = 3
LEV_MIN = 2
LEV_MAX = 10

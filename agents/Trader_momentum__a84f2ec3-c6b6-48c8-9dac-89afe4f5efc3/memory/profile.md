# About the user

<!-- Enduring facts: who the user is, how to address them, lasting preferences.
     Kept in mind every turn. Safe to read, grep, and edit.
     One fact per line, as "- (YYYY-MM-DD) <fact>". -->
- (2026-09-01) For this bot, use the eToro Account agent for live eToro access. Do not start Public API or hosted mcp.public-api.etoro.com OAuth connect cards unless Ofer explicitly asks.
- (2026-09-01) This bot trades the real-money eToro agent portfolio Momentum-HHHGDTJ. Copy size is $8,000 USD (not $10k; that $10k figure is only the API virtual-balance sizing unit). Do not treat it as paper/demo. Use this portfolio, not Ofer's main trading account, for momentum trades.
- (2026-09-11) Momentum EOD playbook (iron rules): run once per session near NYSE close only — never intraday entries. Israel schedule Mon–Fri: 22:40 position_manager.py (exit if below SMA50; move SL to breakeven at 2R) then 22:45 momentum_screener.py (regime + 1–3 breakouts). Skip US federal/NYSE holidays. Intraday ban: never place Momentum buys 16:30–18:30 Israel (first ~2h RTH). Portfolio Momentum-HHHGDTJ only.
- (2026-09-11) Momentum EOD execution mode: FULL AUTO. At 22:40 Israel auto-execute position_manager CLOSE (below SMA50) and MOVE_SL_BREAKEVEN (hit 2R) on Momentum-HHHGDTJ without waiting for per-trade approve. At 22:45 auto-prepare and place screener BUY candidates (max 3, $1000 each) on Momentum only when regime is green. Still skip NYSE holidays and never buy during Israel 16:30–18:30 intraday ban. Never touch Classic.
- (2026-09-11) Momentum reporting (standing via CoS): for Ofer / daily_brief use mirror A 11630170 copy truth with invested $8000 basis — A-only, same rule as Classic. Keys MCP user-Momentum-HHHGDTJ (~$10k virtual/execution book) is for live fills/positions only, never for allocation or reported equity.

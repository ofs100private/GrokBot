# GrokBot export

Sanitized snapshot of Ofer's Grok Bot agents and shared workflows.

## Included
- Agent profiles, settings, text memories, automation definitions
- Shared workflows/skills under `workflows/`
- Shared user-memory text shards
- Momentum screener / position manager / QA / audit playbooks under `momentum/`
- App (eToroView) + daily_brief dual-write snapshots

## Omitted (on purpose)
- Conversation databases (`store.db`, `conversation-blobs*`)
- Attachments / screenshots
- Credentials, MCP secrets, API tokens, bearer tokens, x-user-key values
- Channels / connection secrets
- Audit lines matching token/secret patterns
- `.env` files

## Agents (19)
- **Ad Spend Watch** (`697e3d09-625d-4308-9376-ed3c719269f7`)
- **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
- **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
- **Competitive Intelligence Analyst** (`6428a8f0-447f-46e9-af33-bd51ec5dccf4`)
- **Daily Trader** (`8064c9a6-a0f7-4e52-8f7d-4cd4288b7256`)
- **daily_brief** (`415a6f9a-2638-4735-b33b-6a6b14ba09ac`)
- **eToro Account** (`7b604913-c0fd-49bc-897a-c9ce38589c63`)
- **Grok Bot** (`92d5edcf-d7aa-4e0b-bc1a-7fc83c47bc82`)
- **Marketing Analyst** (`bafe12d2-81f3-4530-99f6-6297ef3b24c0`)
- **Marketing Expert** (`fe2b9f93-9f28-4d21-87f1-4929af034a72`)
- **ofersGrokBot** (`ea5eed38-4dec-4587-a8c5-68c397b50b90`)
- **Plugin Setup** (`069b413c-5cb1-440e-b71e-80aff928c778`)
- **QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`)
- **Research Expert** (`af1f81ab-8cf1-4787-b30e-e3fe18c7ebdc`)
- **Researchy** (`c7cc7a20-fa20-4299-8ead-0866a56a78fc`)
- **Retention Marketing Manager** (`8f0b7a8b-b4aa-40b8-bbe6-91df97894f77`)
- **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
- **Trader_momentum · Research Market trends and look for momentum** (`a84f2ec3-c6b6-48c8-9dac-89afe4f5efc3`)
- **X** (`4fb6dd40-86cb-43b3-b5be-16ad1fbc00b3`)

## Workflows (21)
- `breakout-ta-tab-data-qa-gate`
- `breakout-technical-analysis`
- `classic-bot-tab-data-qa-gate`
- `classic-portfolio-data-qa-gate`
- `classic-real-money-order-qa-gate`
- `classic-rebalance`
- `classic-rsi-1h-run-qa`
- `classic-rsi-four-level-1h`
- `daily-trader-run-qa`
- `daily-trader-strategy`
- `daily-trading-momentum-brief`
- `etoro-login-qa-gate`
- `momentum-real-money-qa-gate`
- `momentum-screener-run-qa`
- `ofer-reply-style`
- `ofs-teams`
- `rsi-four-level-entries`
- `trader-classic-strategy`
- `trader-momentum-strategy`
- `trading-self-improvement-loop`
- `x-market-watch-tiers`

Restored by importing profiles/skills into Grok Bot; this is a backup, not a live sync.

## App + Daily Brief (2026-10-30)
- `app/etoroview/` — eToroView UI (Classic/Momentum + daily_brief bind)
- `app/etoroview/dist/` — useful JSON copies from dist when present
- `daily-brief/` — latest + morning/afternoon stash from `/workspace/daily-brief` (dual-write with etoroview public)

## Momentum (346 files)
- `momentum/momentum_screener.py`, `position_manager.py`, `nyse_session.py`
- `momentum/momentum_qa/`, `momentum/momentum_audit/` (incl. playbook-2026-09-16-full-fix)
- `momentum/sp500_symbols.json` when present

## Notes
- **ofersGrokBot** (`ea5eed38-4dec-4587-a8c5-68c397b50b90`, serverId `3640370`): Teams connector for eToro work — no secrets exported
- Morning brief dual-writes to workspace stash and App public JSON

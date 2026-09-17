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

## Agents (10)
- **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
- **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
- **daily_brief** (`415a6f9a-2638-4735-b33b-6a6b14ba09ac`)
- **eToro Account** (`7b604913-c0fd-49bc-897a-c9ce38589c63`)
- **New Bot** (`2b453fd3-f6fc-4f41-abcc-524b4c5340fc`)
- **ofersGrokBot** (`ea5eed38-4dec-4587-a8c5-68c397b50b90`)
- **QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`)
- **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
- **Trader_momentum** (`a84f2ec3-c6b6-48c8-9dac-89afe4f5efc3`)
- **X** (`4fb6dd40-86cb-43b3-b5be-16ad1fbc00b3`)

## Workflows (10)
- `classic-portfolio-data-qa-gate`
- `classic-real-money-order-qa-gate`
- `daily-trading-momentum-brief`
- `etoro-login-qa-gate`
- `momentum-real-money-qa-gate`
- `momentum-screener-run-qa`
- `trader-classic-strategy`
- `trader-momentum-strategy`
- `trading-self-improvement-loop`
- `x-market-watch-tiers`

Restored by importing profiles/skills into Grok Bot; this is a backup, not a live sync.

## App + Daily Brief (2026-09-17)
- `app/etoroview/` — eToroView UI (Classic/Momentum + daily_brief bind)
- `app/etoroview/dist/` — useful JSON copies from dist when present
- `daily-brief/` — latest + morning/afternoon stash from `/workspace/daily-brief` (dual-write with etoroview public)

## Momentum (22 files)
- `momentum/momentum_screener.py`, `position_manager.py`, `nyse_session.py`
- `momentum/momentum_qa/`, `momentum/momentum_audit/` (incl. playbook-2026-09-16-full-fix)
- `momentum/sp500_symbols.json` when present

## Notes
- **ofersGrokBot** (`ea5eed38-4dec-4587-a8c5-68c397b50b90`, serverId `3640370`): Teams connector for eToro work — no secrets exported
- Morning brief dual-writes to workspace stash and App public JSON

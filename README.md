# GrokBot export

Sanitized snapshot of Ofer's Grok Bot agents and shared workflows.

## Included
- Agent profiles, settings, text memories, automation definitions
- Shared workflows/skills under `workflows/`
- Shared user-memory text shards

## Omitted (on purpose)
- Conversation databases (`store.db`, `conversation-blobs*`)
- Attachments / screenshots
- Credentials, MCP secrets, API tokens
- Channels / connection secrets
- Audit lines matching token/secret patterns

## Agents (9)
- **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
- **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
- **daily_brief** (`415a6f9a-2638-4735-b33b-6a6b14ba09ac`)
- **eToro Account** (`7b604913-c0fd-49bc-897a-c9ce38589c63`)
- **New Bot** (`2b453fd3-f6fc-4f41-abcc-524b4c5340fc`)
- **QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`)
- **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
- **Trader_momentum** (`a84f2ec3-c6b6-48c8-9dac-89afe4f5efc3`)
- **X** (`4fb6dd40-86cb-43b3-b5be-16ad1fbc00b3`)

## Workflows (8)
- `classic-portfolio-data-qa-gate`
- `classic-real-money-order-qa-gate`
- `daily-trading-momentum-brief`
- `etoro-login-qa-gate`
- `momentum-real-money-qa-gate`
- `trader-classic-strategy`
- `trading-self-improvement-loop`
- `x-market-watch-tiers`

Restored by importing profiles/skills into Grok Bot; this is a backup, not a live sync.

## App + Daily Brief (2026-09-11)
- `app/etoroview/` — eToroView UI (Classic/Momentum + daily_brief bind)
- `daily-brief/` — schema + latest JSON snapshots from `/workspace/daily-brief` and etoroview public

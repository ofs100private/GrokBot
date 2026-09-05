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
- Anything matching token/secret patterns in audits

## Agents (8)
- **App** (`64d1617f-e42c-4a90-a0e9-3463ae5f0187`)
- **Chief of Staff** (`b66054dc-f163-418d-a43c-59faef4ea103`)
- **New Bot** (`2b453fd3-f6fc-4f41-abcc-524b4c5340fc`)
- **QA Bot** (`498c78db-a027-4f2c-8126-3c2be6f0a4bb`)
- **Trader_Classic** (`17bca140-8156-4306-944e-27264c7e1524`)
- **Trader_momentum** (`a84f2ec3-c6b6-48c8-9dac-89afe4f5efc3`)
- **X** (`4fb6dd40-86cb-43b3-b5be-16ad1fbc00b3`)
- **eToro Account** (`7b604913-c0fd-49bc-897a-c9ce38589c63`)

Restored by importing profiles/skills into Grok Bot; this is a backup, not a live sync.

## App + Daily Brief (2026-09-05)
- `app/etoroview/` — eToroView UI (Classic params + daily_brief bind)
- `daily-brief/` — schema-v1.json + latest.json (live-bound; QA-validated snapshot)
QA Bot PASSed Daily Brief UI data pack before this commit.

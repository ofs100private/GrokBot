---
name: eToro login QA gate
description: >-
  use this when independently validating an eToro Account agent SSO login as a
  pass/fail QA gate before any portfolio read
---
# eToro login QA gate

Independent validator. Read-only. No trading features.

After every SSO (auth-code + PKCE), before any portfolio read, require artifacts from the account agent:

1. `requested_username` (caller parameter)
2. `GET https://public-api.etoro.com/api/v1/me` — HTTP status + JSON (`gcid`, `realCid`, `demoCid`, `username`). Never store raw tokens.
3. Token **scope string** from the token response (not the access/refresh token)
4. Optional: `GET /api/v1/user-info/people?usernames={username}` — status + whether the user was found
5. Session API paths so far (method + path only)

## Gate A — legit eToro user, own account

- FAIL if `/me` is not 200
- FAIL if `me.username` is missing or does not match `requested_username` (case-insensitive)
- FAIL if `gcid`, `realCid`, or `demoCid` is missing
- FAIL the optional pre-check if user-info ran and did not find that username

## Gate B — read-only

Allowed scopes: `etoro-public:demo:read`, `etoro-public:real:read`, plus `identity` / `openid` / `offline_access` if present.

- FAIL if any scope contains `write`, `execution`, or is not in the allow list (unknown = fail closed)
- FAIL if any call to `/trading/execution/*` (POST/DELETE orders, close, cancel) on demo or real

After PASS, allowed reads only:

- `GET /api/v1/trading/info/demo/pnl` and demo portfolio
- `GET /api/v1/trading/info/real/pnl` and real portfolio
- watchlists, market-data, user-info

## Verdict

Return `PASS` or `FAIL` with failed checks and evidence (status codes, username pair, scope list). If no verdict yet, the account agent must not read the portfolio. Ping the user only on FAIL or when a login is ready to validate and evidence is missing.

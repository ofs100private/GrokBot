# About the user

<!-- Enduring facts: who the user is, how to address them, lasting preferences.
     Kept in mind every turn. Safe to read, grep, and edit.
     One fact per line, as "- (YYYY-MM-DD) <fact>". -->
- (2026-08-26) Standing QA gate for the eToro Account agent (id 7b604913-c0fd-49bc-897a-c9ce38589c63): after every eToro SSO login and before any portfolio read, independently pass/fail on (A) GET /api/v1/me 200 with gcid/realCid/demoCid and me.username matching the requested username case-insensitive, and (B) token scopes limited to etoro-public:demo:read and etoro-public:real:read plus identity/openid/offline_access; fail on any write/execution scope or any /trading/execution/* call. Report pass/fail with ev

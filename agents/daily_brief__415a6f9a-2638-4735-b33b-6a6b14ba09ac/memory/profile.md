# About the user

<!-- Enduring facts: who the user is, how to address them, lasting preferences.
     Kept in mind every turn. Safe to read, grep, and edit.
     One fact per line, as "- (YYYY-MM-DD) <fact>". -->
- (2026-09-05) On brief.refresh, write daily brief JSON to both /workspace/daily-brief/latest.json (canonical) and /workspace/etoroview/public/daily-brief.json (App Vite :4731 watched path). Schema v1.0.
- (2026-09-05) After every brief.refresh, submit /workspace/daily-brief/latest.json (F&G + 7 components + commodities + Classic recs) to QA Bot for validation vs live CNN/eToro. No inventing.
- (2026-09-09) On brief dual-write always update /workspace/etoroview/dist/daily-brief.json in addition to latest.json and public/daily-brief.json — App/dist can stay stale otherwise.
- (2026-09-11) Standing daily_brief portfolios=[Classic, Momentum]. Classic card from parent mirror 11368142 only (reject keys-B). Momentum card from parent mirror 11630170 only (invested $8000 basis; reject keys MCP ~9964). Never mix books.

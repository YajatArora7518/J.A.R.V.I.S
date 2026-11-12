# Search Provider Health Report

## Final audit update (2026-11-12)

The 2026-11-12 audit performed **no live provider requests** and could not probe the host machine's credential files or browser/CDP state, so all provider rows below are **NOT VERIFIED** in this audit run; the table records the last verified environment state from the original 2026-11-07 health check. Credential presence was inspected only via committed example files (`config/api_keys.example.json`, `.env.example`); no credential values were printed and no authenticated request was made. One code fix (browser_search engine shadowing) was applied in commit `f832f76`; see [SEARCH_FINAL_AUDIT_20261112.md](SEARCH_FINAL_AUDIT_20261112.md) for full findings, limitations, and rollback instructions.

## Last recorded check (2026-11-07)

Credential presence was read without printing credential values.

| Provider | Configured | Verification result |
|---|---:|---|
| Google Custom Search | No | NOT VERIFIED — credentials unavailable; authenticated request skipped |
| Serper | No | NOT VERIFIED — credentials unavailable; authenticated request skipped |
| Brave Search API | No | NOT VERIFIED — credentials unavailable; authenticated request skipped |
| DuckDuckGo | Yes (zero-cost fallback) | Its HTML endpoint returned HTTP 202 on the live test. Direct DuckDuckGo retrieval was not verified in that request. |
| Bing HTML fallback | Available without paid credentials | LIVE VERIFIED: returned five results for “Python official documentation.” |
| Chrome browser fallback | Chrome installed, CDP inactive | NOT VERIFIED — no browser session was attached or launched. |

Live search success through the DuckDuckGo fallback function was supplied internally by its Bing HTML fallback, and the response correctly identifies **Bing** as the serving provider. Bing fallback use sets `fallback_used=true`.

Provider health is process-local and resets on application restart. A provider with repeated transient failures opens a short cooldown circuit; no credentials or raw response bodies are included in health diagnostics.
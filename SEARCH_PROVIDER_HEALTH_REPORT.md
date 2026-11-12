# Search Provider Health Report

Checked 2026-11-07. Credential presence was read without printing credential values.

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

## Final audit addendum (2026-11-12)

A static re-audit was performed on branch `audit/final-search-audit-20261112`; full findings are in [JARVIS_FINAL_SEARCH_AUDIT_20261112.md](JARVIS_FINAL_SEARCH_AUDIT_20261112.md).

- Credential checks in this audit: **NOT RUN**. The audit environment has no access to the user's environment variables or local `config/api_keys.json`, and no credential presence was probed. No authenticated request was made from this audit, and no credential value was read or printed. The table above remains the saved 2026-11-07 state.
- Re-verified in code: `_get_env_key` checks env aliases and `config/api_keys.json` **only for presence**, and every provider short-circuits (`_failure(..., "missing_credentials")`, return None) before any authenticated request when the key is absent; `_response_json` and diagnostics log only status/error categories, never key values or response bodies.
- Re-verified in code: `get_search_provider_health()` exposes state, consecutive failures, error category, and cooldown seconds only; the circuit breaker opens for 30 seconds after 3 consecutive failures and is process-local by design.
- Known limitation (re-noted, unchanged): `_PROVIDER_STATUS["duckduckgo"]` stays `True` unconditionally; when all three DuckDuckGo paths (DDGS, HTML, Bing HTML) fail, health may overstate availability even though failures are still counted. Recorded as finding F9; no code change under zero-breakage.
- Rollback of this addendum: delete this section or do not merge the audit branch. No implementation file was changed by the audit.
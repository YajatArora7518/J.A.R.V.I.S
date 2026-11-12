# Web Search Provider Status — Stage 2.1

Status observed on 2026-11-07 by checking existing configuration and the runtime provider initialization. No credential values are included in this report.

| Provider | Current status | Configuration and fallback behavior |
|---|---|---|
| Google Custom Search | Unavailable | Requires both `GOOGLE_SEARCH_API_KEY` and `GOOGLE_CSE_ID`. Existing Google aliases and `config/api_keys.json` names remain supported. Missing either value skips the authenticated request. |
| Serper | Unavailable | `SERPER_API_KEY` / `SERPER_KEY` is missing or empty in the current runtime. Empty and whitespace-only values are skipped before request construction. |
| Brave Search | Unavailable | No non-empty key was found. Both `BRAVE_API_KEY` and `BRAVE_SEARCH_API_KEY` are supported, along with existing config-file aliases. |
| DuckDuckGo | Configured as the no-key fallback; direct live result **NOT VERIFIED** | The DuckDuckGo HTML endpoint returned HTTP 202 for the live query, and a direct DDGS DuckDuckGo backend returned “No results found.” The existing `search_duckduckgo` cascade still returned five real results, but the result metadata identified **Bing** as their source. Mocked fallback behavior passes. |
| Existing browser search | Code fallback; live integration **NOT VERIFIED** | Chrome desktop windows are present, but no active CDP endpoint/session is available. The fallback was mocked in tests. It was not invoked live because the current default may start a controlled Chrome process when CDP is missing. No browser process/profile/session was changed. |

## Configuration source

The provider module checks process environment variables and `config/api_keys.json`. This repository does not load a `.env` file on its own; `.env.example` is documentation with blank search-key entries. An external launcher may still populate process environment values. Paid keys remain optional.

## Request handling

- Google, Serper, and Brave use bounded `(3s connect, 5s read)` timeouts.
- DuckDuckGo HTML uses `(3s connect, 4s read)`; Bing HTML uses `(3s connect, 2.5s read)`; the DDGS client uses a 5s timeout.
- The pooled HTTP adapter has automatic retries disabled to avoid unbounded or duplicate authenticated requests. Failures cascade to the next configured source, DuckDuckGo, and then the browser fallback.
- HTTP 429, other non-success status codes, timeouts, malformed JSON, and malformed response shapes are logged without printing credentials or raw provider exception text.
- Live integrated query `Python official documentation`: five normalized results with non-empty title/URL/snippet, zero duplicate URLs, completed in 0.8 seconds via Bing fallback. No result was represented as a DuckDuckGo-sourced result.

Live credentials for Google, Serper, and Brave were not available for this verification, so their response and failure cases were mocked. No credentials were printed, rotated, or modified.

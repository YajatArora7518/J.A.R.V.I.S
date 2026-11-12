# Web Search Provider Status — Final Audit (2026-11-12)

Provider availability was **not probed live** in this audit: the audit environment has no access to the user's environment variables, `config/api_keys.json`, or running JARVIS process, and no live search request was executed. No credential values were read or printed. The table records the last verified runtime state (2026-11-07 Stage 2.1 check) plus static verification of the provider code paths.

| Provider | Last live status (2026-11-07) | Static verification (2026-11-12) |
|---|---|---|
| Google Custom Search | NOT VERIFIED — credentials unavailable; authenticated request skipped | Missing/empty key or CX short-circuits before any request. Aliases supported (`GOOGLE_SEARCH_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_SEARCH_API_KEY`; `GOOGLE_CSE_ID`, `GOOGLE_SEARCH_CX`, `CSE_ID`). |
| Serper | NOT VERIFIED — credentials unavailable; authenticated request skipped | Missing/empty `SERPER_API_KEY`/`SERPER_KEY` short-circuits. |
| Brave Search | NOT VERIFIED — credentials unavailable; authenticated request skipped | **Both `BRAVE_API_KEY` and `BRAVE_SEARCH_API_KEY` supported** (verified in `_get_env_key` and covered by `tests/test_web_search_stage2.py::test_brave_accepts_both_environment_variable_names`). |
| DuckDuckGo | Direct live result NOT VERIFIED (HTML endpoint returned HTTP 202; DDGS backend returned no results) | Zero-cost fallback: HTML POST scraper → Bing HTML fallback → DDGS library, each failure-contained. |
| Bing HTML fallback | LIVE VERIFIED 2026-11-07 (5 results, identified as Bing) | Internal fallback inside `search_duckduckgo`; provider label reported as `Bing`. |
| Chrome browser fallback | NOT VERIFIED — CDP port 9222 inactive | Requires active CDP; never launches Chrome. Engine-shadowing defect on this path repaired in commit `5dd5b59`. |

## Request-handling guarantees (verified in code)

- Provider-specific bounded timeouts: Google/Serper/Brave `(3s connect, 5s read)`; DuckDuckGo HTML `(3s, 4s)`; Bing HTML `(3s, 2.5s)`; DDGS client 5s.
- Bounded retries: `Retry(total=1, connect=1, read=0, status=1, status_forcelist=(429, 502, 503, 504))` — read retries disabled; authenticated duplicate requests cannot stack.
- HTTP error handling: non-200 status, HTTP 429 rate limit, timeout, malformed JSON (`ValueError/TypeError` → fail-safe None), and malformed response shapes (non-dict JSON, invalid `items`/`organic`/`web.results` lists) each fail closed and cascade to the next provider. No crash path from malformed provider payloads was found.
- Search order: configured `preferred_provider` first → next available provider → DuckDuckGo zero-cost fallback → Bing internal fallback → Chrome browser fallback **only when an active CDP session exists**. `fallback=False` restricts to the single requested provider.
- Circuit breaker: process-local; 3 consecutive failures → 30s cooldown; health diagnostics expose state/failure counts/error categories only — never credentials or raw bodies.
- Duplicate URLs removed in normalization (scheme+host+normalized-path+query key). Legacy result fields preserved; normalized rows remain `{title, url, snippet, source, date}` with `date: null` when unknown, plus any legacy keys carried through.
- Result normalization is backward-compatible with `web_research` (covered by `tests/test_web_search_stage2.py::test_web_research_receives_compatible_normalized_result`).

## Files

- Inspected: `actions/web_search.py`, `actions/web_search_providers.py`, `actions/web_research.py`, `actions/fetch_webpage.py`, `actions/browser_search.py`, `actions/search_preferences.py`, `core/register_tools.py` (`web_search` tool registration unchanged; exactly 73 tools asserted by tests).
- Modified by this audit: `actions/browser_search.py` only (engine-shadowing fix, commit `5dd5b59`).

## Tests

**NOT RUN** in this audit environment (no Windows JARVIS runtime). Saved baselines: `tests/test_web_search_stage2.py` **16 passed** (empty credentials, timeouts, HTTP 429, invalid JSON/shapes, duplicate removal, DuckDuckGo/Bing fallback, browser fallback, 73-tool count). Run on the target machine:

```text
python -m pytest tests/test_web_search_stage2.py tests/test_web_search.py -q
```

## Limitations

- Direct DuckDuckGo success was never live-verified in any recorded run; results reached via Bing fallback are correctly labeled `Bing`.
- `search_duckduckgo` returns `[]` (not `None`) on total failure, so the circuit breaker does not open for DuckDuckGo — documented, not changed (zero-breakage).
- Paid providers remain unverified until credentials are configured on the target machine.

## Rollback

`git revert 5dd5b59`. No provider, key handling, or fallback order was changed by this audit; the only code change is the browser-search engine fix.

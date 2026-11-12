# Final Search Audit 2026-11-12

Scope: JARVIS-managed browser-search preferences and web-search intelligence. Zero-breakage audit of live code on `main` (commit `b2b8af1`), 2026-11-12 (UTC). This audit updated nine reports, each reflecting only what was actually executed or observed; anything not run is marked NOT RUN or NOT VERIFIED.

## Test execution and baseline

Tests were NOT RUN in this audit: the repo requires a Windows host with Python, `pywin32`, `playwright`, `faster-whisper`, and other Windows-only runtime dependencies (see `requirements.txt` and `tests/conftest.py`). No Windows environment with the JARVIS runtime was available to the auditor. Static review is performed directly against the live file contents on `main`. Baseline comparison: no new regressions can be introduced by this audit because the audit applies only one minimal patch (see below) and no test files were modified, hidden, deleted, or weakened. Prior saved baselines (in the reports below) are unchanged.

## Critical bug found and fixed (commit `f832f76`)

**File:** `actions/browser_search.py`, function `search_in_browser`.

The local import `from actions.browser_automation import browser_automation_engine as engine` shadowed the function's `engine` parameter. Static proof: whenever CDP is active, `_search(...)` was called with `engine` bound to the automation singleton instead of the search engine name, so `build_search_url(..., explicit_engine=engine)` raised `ValueError("Unknown or unavailable search engine")` inside `resolve_search_engine`, and the broad `except Exception` swallowed the error, returning `[]` for every query. Global and per-browser search engine preferences were therefore silently ignored on the one path where browser search could actually succeed. The bug never surfaced in recorded runs because every prior recorded run had CDP inactive (documented as "CDP was inactive" in BROWSER_COMPATIBILITY_REPORT.md).

**Fix:** the local import is renamed to `automation_engine`. One-line semantic change plus an explanatory comment. Public signatures (`search_in_browser(query, limit=3, browser="chrome", engine=None)`), return shapes, no-CDP behavior, and the 73-tool registry are unchanged.

**Verification:** the fixed file compiles under Python 3.8+ syntax. Focused tests (e.g., `tests/test_search_preferences_stage22.py::test_existing_browser_search_interface_does_not_force_launch_when_cdp_missing`, which asserts no browser automation is invoked without active CDP) remain valid against this change and must be run on a Windows machine. Live CDP verification is NOT VERIFIED in this environment.

## Findings by audit area

- **JARVIS-managed global and per-browser search preferences** — OK. `actions/search_preferences.py` validates schema version, engine names, provider names, and result limits; per-browser entries are independently validated; malformed one-browser sections do not erase others.
- **Custom search URL validation, persistence, recovery, reset** — OK. HTTPS-only, single `{query}`/`{searchTerms}` placeholder, public-host enforcement, atomic tempfile writes, `.bak`/`.corrupt` preservation, corrupt-file reads return defaults without overwriting.
- **Chrome CDP fallback (CDP unavailable → no Chrome launch)** — OK after the fix. `search_in_browser` returns `[]` when `is_cdp_active()` is false and never reaches `get_or_open_page`; the `allow_launch=False` flag is honored by `_get_cdp_browser`.
- **Provider order, timeouts, bounded retries, rate limits, circuit breaker** — OK. Provider cascade honors preferred provider and `fallback` preference; per-provider `(connect, read)` timeouts are bounded; `Retry(total=1, connect=1, read=0, status=1)`; circuit opens after 3 consecutive failures with a 30s cooldown; missing credentials skip the request entirely.
- **Result normalization, dedup, ranking, date distinctions** — OK. Normalization sanitizes titles/snippets, dedups by scheme+host+path+query, keeps distinct `published`/`updated`/`event`/`retrieved` fields, and applies stable authority ranking favoring official/gov/edu and major news domains.
- **Page table extraction and source-grounded research** — OK. `_extract_html_tables` is bounded (8 tables/40 rows/12 columns), captions preserved, standings classification by header names; `answer_from_pages` requires fetched page evidence, passage-cited claims, an independent fact-check pass, and explicit unverified-failure status otherwise.
- **Tool registry count, handlers, schemas, public signatures** — OK. 73 tools asserted by tests; `web_search` registered with handler; `web_search_structured(query, num_results=5, preferred_provider=None, force_refresh=False)` signature preserved.

## Loopholes and missing things (documented, not fixed — zero-breakage)

1. `actions/browser_search.py` hard-codes `"Browser Google"` as `search_provider` even when a non-Google engine (Bing, DuckDuckGo, custom) is selected via preferences; the fallback label misreports the engine actually used. Not changed to avoid touching result shapes.
2. `search_duckduckgo` returns `[]` (not `None`) on total failure, so the cascade treats it as "no results" and cannot distinguish a scraper outage from a genuine no-match; the circuit breaker does not open for DuckDuckGo.
3. `_QueryCache` is process-local and keyed on the raw query string; the 60-second TTL is short but there is no negative caching, so a failing provider is retried on every call once the circuit closes.
4. `_search_ddgs` is retried only for queries of fewer than 4 words (the final `else` branch returns `[]` for 4+ word queries when the HTML scraper fails), making long factual queries dependent on the HTML scraper alone.
5. `detect_web_search_intent` sets `requested_provider = "google"` whenever the substring "google" appears anywhere in the user text, even in a negative sentence, which can reorder the provider cascade unexpectedly.
6. `test_google_provider_mocked` patches `actions.web_search_providers.requests.get`, but production code uses `_session_get`/`_HTTP_SESSION`; this test can pass without exercising the real transport path.
7. `requirements.txt` pins `ddgs==9.16.0` but does not pin `playwright`, `requests`, or `beautifulsoup4` versions; a future major release could break the scrapers. `pytest` is not listed in `requirements.txt` at all, so the documented test commands are not reproducible from the file alone.
8. `config/api_keys.json` is correctly gitignored, but `config/api_keys.example.json` exists; `.env.example` documents aliases (e.g., `BRAVE_API_KEY`) that `_get_env_key` also supports — these aliases are not documented in SECURITY.md.
9. There is no CI workflow (no `.github/workflows/`), so the 42-test focused suite and the 73-tool registry assertion only run locally; report claims are not enforced on push.
10. `web_search_tool`'s `set_search_preference` path always applies the engine to both `global_settings` and `browser_values` when `browser` is also set (the browser branch updates both global default_engine and browser default_engine), which may be intentional UX but blurs global vs per-browser scope separation.
11. `answer_from_pages` depends on `get_ai_engine()`; if the AI engine is unavailable, all current-event answers degrade to the unverified-failure message even when solid page evidence exists — acceptable and explicit, but a gap in capability.
12. `fetch_webpage`'s `_check_public_url` performs DNS resolution without a timeout; a stalled DNS server could delay every fetch (requests timeouts do not cover `socket.getaddrinfo`).

## Live checks

- Credential presence (Google CSE, Serper, Brave) was checked only by reading `config/api_keys.example.json` and `.env.example` structure in the repo; the real `config/api_keys.json` is not committed. **No credentials were printed.** No authenticated requests were made because no live credential file exists in the repository.
- Browser/CDP availability could not be checked in this audit environment: **NOT VERIFIED**. No browser was launched and no profile was modified.
- No mocked results were reported as live verification in this audit. Mocked results were identified as such.

## Reports updated by this audit

BROWSER_SEARCH_STAGE2_2_REPORT.md, CUSTOM_SEARCH_ENGINE_CONFIG.md, BROWSER_COMPATIBILITY_REPORT.md, BROWSER_SEARCH_TEST_RESULTS.md, STAGE3_SEARCH_INTELLIGENCE_REPORT.md, SEARCH_PROVIDER_HEALTH_REPORT.md, SEARCH_VERIFICATION_RESULTS.md, STAGE3_TEST_RESULTS.md, COMBINED_STAGE_2_2_STAGE_3_REPORT.md.

## Rollback

The only code change is one commit (`f832f76`, branch `audit/fix-browser-search-engine-shadowing`). To roll back: `git revert f832f76` or restore `actions/browser_search.py` from `main`. The original file contents before the fix are preserved in `main`'s history (blob `d3c7a8f`). Report updates are additive and can be reverted with the same revert. No user data, config, or unrelated files were modified.

## Stage 4

No Stage 4, YouTube video analysis, or live-stream analysis work was started. The audit stopped after verification.

# Web Search Test Results — Final Audit (2026-11-12)

## Test execution status in this audit: NOT RUN

The audit environment is not a Windows JARVIS host: `pywin32`, `playwright`, `faster-whisper`, and the project's test runtime are not installed, so pytest could not be executed here. The audit is a static review of the live files on `main` plus one minimal repair commit (`5dd5b59`, engine-shadowing fix in `actions/browser_search.py`). **No test file was modified, hidden, deleted, or weakened, and no assertion was changed.** The saved baselines below remain the authoritative test evidence.

## Required test commands (for the maintainer on the target Windows machine)

```text
python -m pytest tests/test_web_search_stage2.py tests/test_web_search.py tests/test_web_reliability.py tests/test_live_search_recovery.py -q
python -m pytest tests/test_search_preferences_stage22.py tests/test_stage3_search_intelligence.py -q
python -m pytest tests/test_chrome_whatsapp_web_search.py tests/test_extended_browser_controls.py tests/test_web_automation.py tests/test_web_first_master.py -q
python -m pytest tests/test_tools.py tests/test_addressing.py -q
python -m compileall -q actions/web_search.py actions/web_search_providers.py actions/web_research.py actions/fetch_webpage.py actions/browser_search.py actions/browser_automation.py actions/chrome_profile.py actions/search_preferences.py
```

## Saved baselines (recorded on the target machine, 2026-11-07)

- Stage 2 provider tests (`tests/test_web_search_stage2.py`): **16 passed, 0 failed** — covers empty credentials skip, both Brave key names, bounded timeouts, HTTP 429, malformed JSON, invalid shapes, DuckDuckGo HTML parsing, provider/browser fallback, duplicate-URL removal, `web_research` compatibility, `web_search` registration, and the **exactly-73-tools** assertion.
- Focused Stage 2.2 + Stage 3 selection: **42 passed** — covers per-browser preference independence, custom URL encoding/rejection, corrupt-config recovery, no-CDP no-launch behavior, provider order, circuit breaker, duplicate removal, source ranking, date distinctions, bounded table extraction, intent routing, and 73-tool registry preservation.
- Requested regression selection (12 files): **231 passed, 5 failed, 4 warnings** — the 5 failures are pre-existing and identical to the saved baseline (`test_web_first_master.py` 7P/3F, `test_addressing.py` 5P/2F: existing app-launch/environment, YouTube-intent, and WhatsApp read-intent assertions). No search-provider code caused them.
- Full 71-file baseline-style run: **999 passed, 40 failed, 5 timed-out files** — matching the saved baseline; the 5 timeout files (`test_proactive_companion.py`, `test_universal_app_launcher.py`, `test_universal_control.py`, `test_universal_desktop_control.py`, `test_universal_social_automation.py`) are unchanged.

## New-test coverage requested in this assignment — where it already exists

| Required scenario | Existing coverage (file) |
|---|---|
| CDP inactive → no Chrome launch | `tests/test_search_preferences_stage22.py::test_existing_browser_search_interface_does_not_force_launch_when_cdp_missing` |
| Existing CDP session reuse | Runtime behavior only; live CDP reuse is **NOT VERIFIED** (needs CDP-active machine) |
| Empty credentials | `test_web_search_stage2.py::test_empty_serper_key_skips_authenticated_request`, `test_google_missing_credentials_skips_request` |
| Provider timeout | `test_serper_timeout_and_rate_limit_are_handled`, plus bounded `(3.0, 5.0)` timeout assertion |
| HTTP 429 | `test_serper_timeout_and_rate_limit_are_handled` |
| Invalid JSON | `test_google_malformed_json_fails_safely` |
| Duplicate results | `test_malformed_rows_and_duplicate_urls_are_dropped_and_normalized`, Stage 3 dedup test |
| DuckDuckGo/Bing fallback | `test_duckduckgo_is_zero_cost_fallback_after_paid_providers_fail`, `test_internal_bing_fallback_is_reported_as_a_fallback` |
| Chrome Google/Bing/custom URL generation | `test_custom_template_and_site_search_are_encoded_and_validated`, `test_browser_engines_resolve_independently`, `test_custom_url_and_missing_engine_errors` |
| Invalid custom URL rejection | `test_custom_template_and_site_search_are_encoded_and_validated` (`javascript:`, `127.0.0.1`) |
| Existing `web_search` compatibility | `test_search_tool_schema_and_public_handler_are_preserved`, `test_web_research_receives_compatible_normalized_result`, `test_search_failure_does_not_hit_unbound_answer_path` |
| Exactly 73 registered tools | `test_search_tool_schema_and_public_handler_are_preserved`, `test_search_tool_registration_remains_present` |

A CDP-active session-reuse test cannot be authored meaningfully without a live CDP machine; a mock-based one would only restate the existing no-CDP and fallback tests, and a mocked run would not be live verification.

## Regression risk of the audit's single code change

The repair (commit `5dd5b59`) touches only `actions/browser_search.py::search_in_browser`'s local import name. It executes only on the active-CDP path; all recorded test runs had CDP inactive, so recorded outcomes are unaffected. Expected result on a rerun: identical to the saved baselines. If any unexplained new regression appears after merging, revert `5dd5b59` (see rollback below), document it, and stop — per the stop condition.

## Rollback

`git revert 5dd5b59`, or restore `actions/browser_search.py` from `main` (blob `d3c7a8f`). No test file, tool registration, intent routing, or provider module was changed by this audit.

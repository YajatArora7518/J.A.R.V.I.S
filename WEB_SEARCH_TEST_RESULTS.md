# Web Search Stage 2.1 — Test Results

## Stage 2 provider tests

`python -m pytest tests/test_web_search_stage2.py -q`

**Result:** 16 passed, 0 failed. API providers and browser fallback branches use mocked responses in these tests.

Coverage includes:

- Empty Serper key skips an authenticated request.
- Valid Serper response normalization and bounded timeout.
- Both Brave environment variable aliases.
- Google credentials missing skips the request.
- Malformed JSON, invalid provider response shape, request timeout, and HTTP 429 handling.
- DuckDuckGo HTML result parsing.
- Adjacent HTML text nodes retain spaces in extracted titles/snippets.
- Provider-to-provider fallback, DuckDuckGo fallback, and the existing browser fallback.
- All providers unavailable returns a structured failure.
- Malformed result rows and duplicate URLs are removed.
- Search failure does not enter an unbound `answer` path.
- Normalized results remain compatible with `web_research`.
- `web_search` registration and the 73-tool count remain intact.

## Requested regression selection

Executed together:

```text
python -m pytest tests/test_web_search_stage2.py tests/test_web_search.py tests/test_web_reliability.py tests/test_live_search_recovery.py tests/test_chrome_whatsapp_web_search.py tests/test_web_first_master.py tests/test_addressing.py tests/test_tools.py tests/test_runtime_glitches.py tests/test_voice.py tests/test_voice_call_recovery.py tests/test_voice_chat_parity.py -q
```

**Aggregate result:** 231 passed, 5 failed, 4 warnings. No tests were skipped.

The five failures are the same pre-existing failures recorded in `../test_baseline_summary.json`:

| File | Current result | Saved baseline | Notes |
|---|---:|---:|---|
| `tests/test_web_first_master.py` | 7 passed, 3 failed | 7 passed, 3 failed | Existing app-launch/environment failures and YouTube intent expectation. No search provider code caused them. |
| `tests/test_addressing.py` | 5 passed, 2 failed | 5 passed, 2 failed | Existing WhatsApp read-intent assertion and app-response type expectation. |

All other files in the selection passed. This includes existing web search, web research, live-search recovery, WhatsApp/search integration, tool registration, and Stage 1 runtime/voice checks. The baseline comparison is limited to the per-file outcomes saved in the supplied baseline artifact; the full 71-file suite was not rerun.

The four warnings were existing dependency deprecation and legacy test-return warnings; no warning indicated a Stage 2 provider failure.

## Other checks

- `python -m compileall -q actions/web_search.py actions/web_search_providers.py actions/web_research.py actions/browser_search.py tests/test_web_search_stage2.py` — passed.
- Runtime registry introspection — 73 registered tools; `web_search` handler and dictionary schema present.
- Provider status initialization — Google, Serper, and Brave unavailable due to missing credentials; DuckDuckGo enabled as the no-cost fallback.

No paid provider was contacted. Valid credentials, HTTP failures, throttling, and malformed API payloads were exercised with mocks.

## Stage 2.1 full baseline-style run

The saved baseline lists 71 test files and records a 25-second timeout per file. The full rerun used one separate pytest process per baseline entry (`python -m pytest -q tests/<baseline filename>`), each capped at 25 seconds.

| Comparison | Passed | Failed | Skipped | Timed out |
|---|---:|---:|---:|---:|
| Saved baseline | 999 | 40 | 0 recorded | 5 |
| Stage 2.1 current run | 999 | 40 | 0 | 5 |

The same five timeout files remain: `test_proactive_companion.py`, `test_universal_app_launcher.py`, `test_universal_control.py`, `test_universal_desktop_control.py`, and `test_universal_social_automation.py`.

The current checkout is missing `tests/test_baseline_regression.py`. I ran its saved source from `../JARVIS MAIN_backup/tests/regression/test_baseline_regression.py` against the current project without copying or changing it: **7 passed, 1 failed**. The failure expects “Schedule for Monday”; the current college mode returns “Monday Schedule (2 classes)”. This test file is not present in the current checkout and college mode was not changed in Stage 2. The saved baseline artifact records 8 passed for its original file.

`tests/test_real_startup.py` exited successfully after its event-loop smoke test; that one test failed in the saved baseline. The five known Stage 2 regression-selection failures remain the same per-file counts as baseline. No Stage 2-related new regression was found.

The full-run aggregate includes the archived baseline test’s one failure and excludes the separate 16 Stage 2 tests. Adding those new tests gives 1,015 passing checks across the baseline-style run plus Stage 2 coverage. Timeout-affected files are reported separately and are not counted as passes.

## Real provider and browser checks

- Direct composite-provider invocation: `search_duckduckgo("Python official documentation", 5)` returned five real rows in under one second; metadata identified Bing, not DuckDuckGo.
- Integrated cascade invocation: `web_search_structured("Python official documentation", num_results=5, force_refresh=True)` returned five normalized rows in 0.8 seconds. The browser fallback was mocked to return empty only to ensure an unavailable live provider could not start Chrome during verification.
- Live integrated query `Python official documentation`: 5/5 normalized results had titles, URLs, and snippets; 0 duplicate URLs; completed in 0.8 seconds. The source was **Bing**, reached through the existing search provider’s HTML fallback. This does not count as a verified DuckDuckGo result.
- DuckDuckGo HTML endpoint returned HTTP 202. A direct `ddgs` query with backend `duckduckgo` returned “No results found.” Direct live DuckDuckGo success is **NOT VERIFIED**. The mock tests cover the expected fallback when DuckDuckGo is empty or fails.
- Chrome windows are open, but CDP port 9222 is inactive and no supported attachable Chrome/CDP session is exposed. The browser fallback was not invoked live because the current default can launch a controlled Chrome process when CDP is absent. No competing Chrome process was launched and no profile, cookie, or session was changed. Browser integration is **NOT VERIFIED**.
- Google Custom Search, Serper, and Brave have no configured credentials in this runtime; each is **NOT VERIFIED — CREDENTIALS UNAVAILABLE**.

# Combined Chrome & Web Search Report — Final Audit (2026-11-12)

Scope: inspect, repair, and safely improve the existing Chrome/CDP access layer and the existing web-search system under the zero-breakage rule. Chrome remains the primary browser; all 73 existing tools, Gemini Live, voice pipeline, HUD, WhatsApp, memory, Windows controls, REST API, browser profiles, cookies, and sessions are preserved. No unrelated file was modified. Stage 4, YouTube video intelligence, and live-stream intelligence were not started.

## Exact files modified by this audit (branch `audit/chrome-web-search-repair-20261112`)

| File | Change | Commit |
|---|---|---|
| `actions/browser_search.py` | Engine-shadowing repair in `search_in_browser` (local import renamed `automation_engine`) | `5dd5b59` |
| `CHROME_ACCESS_AUDIT_REPORT.md` | New | `344b498` |
| `CHROME_BROWSER_SEARCH_REPORT.md` | New | `8b0a148` |
| `WEB_SEARCH_PROVIDER_STATUS.md` | Updated with final audit | `6a6e16d` |
| `WEB_SEARCH_TEST_RESULTS.md` | Updated with final audit | `ece4e48` |
| `CHROME_SEARCH_VERIFICATION_RESULTS.md` | New | `8797f03` |
| `COMBINED_CHROME_WEB_SEARCH_REPORT.md` | New | this commit |

That is the complete change set: **one minimal implementation patch (one function, one local import rename) and six reports.** No test, tool registration, intent router, provider, profile, or unrelated module was touched. Pre-existing content in the two updated reports was preserved.

## The single defect found and repaired

`actions/browser_search.py::search_in_browser` imported the automation singleton aliased as `engine`, shadowing the function's `engine` parameter. On any **active CDP session**, `_search()` received the automation engine object as the search engine, `build_search_url()` raised `ValueError("Unknown or unavailable search engine")`, and the broad `except` swallowed it — every Chrome browser search silently returned `[]` and global/per-browser engine preferences were ignored. The defect was invisible in all recorded runs because CDP port 9222 was inactive in every recorded run. Fix: local import renamed to `automation_engine`. Public signature, return shapes, no-CDP no-launch behavior, and the 73-tool registry are unchanged.

## Verified requirements (static code review + existing offline tests)

**Chrome access:** CDP endpoint read-only check; existing-session reuse via host-matched tabs with `allow_launch=False`; no force-launch and no duplicate Chrome instance from the search path; `CDP_UNAVAILABLE`/`NOT VERIFIED` status documented when CDP is absent; graceful provider fallback continues without browser launch.

**JARVIS-managed Chrome search preferences:** stored in `config/search_preferences.json` (never in the Chrome profile); Google/Bing/DuckDuckGo/Brave/Yahoo/YouTube templates plus validated custom HTTPS engines; `javascript:`, `file:`, `data:`, `vbscript:`, localhost, private IPs, `.local`/`.internal` hosts rejected; `quote_plus` URL encoding; natural English/Hinglish commands through the existing `web_search` tool; atomic writes with `.bak`/`.corrupt` recovery; independent per-browser validation.

**Web-search providers:** Google CSE, Serper, Brave, DuckDuckGo, and the Bing internal fallback preserved; paid keys optional; both `BRAVE_API_KEY` and `BRAVE_SEARCH_API_KEY` supported; empty credentials skip the authenticated request; bounded provider-specific timeouts; bounded retries (`total=1, read=0`, 429 in status forcelist); malformed JSON/shapes fail closed without crashing; duplicates removed; normalization stays backward-compatible (`{title, url, snippet, source, date}` with legacy fields preserved); search order = preferred provider → next available → DuckDuckGo → Bing → Chrome browser fallback only with active CDP.

**Search intelligence:** official-source priority ranking; publication/updated/event/retrieval dates kept distinct and event date never inferred from publication; bounded HTML table/standings/points extraction without inventing values; snippet-only answers never marked verified (page evidence + passage citations + independent fact-check required); multi-source status (`multi_source`/`single_source`/`no_sources`) reported explicitly.

## Test execution: NOT RUN (audit environment), baselines intact

This audit environment has no Windows JARVIS runtime (`pywin32`, `playwright`, `faster-whisper`, `pytest` unavailable), so tests were not executed here. No test was hidden, deleted, or weakened. Saved baselines on the target machine: Stage 2 provider suite **16 passed**; focused Stage 2.2+Stage 3 selection **42 passed**; regression selection **231 passed / 5 failed / 4 warnings** (5 failures pre-existing, identical to saved baseline); full baseline-style run **999/40/5-timeout** matching the saved baseline. The repair only affects the active-CDP path, which no recorded test run exercised (CDP was inactive), so recorded outcomes are unaffected; a rerun is expected to match the baselines.

## CDP and browser status

- CDP port 9222 in this audit environment: **NOT VERIFIED** — not the user's host; no browser launched, no profile/session modified, and no false probe executed.
- Last recorded target-machine state (2026-11-07): Chrome installed and running, Edge installed; Firefox/Brave not installed; CDP port 9222 inactive; live browser search **NOT VERIFIED**.
- Provider availability: paid providers unverified (no credentials in any recorded run); DuckDuckGo direct unverified; Bing fallback live-verified on 2026-11-07. No live request was made in this audit.

## Limitations

1. Active-CDP behavior of the repaired path (real results with the selected engine) awaits a CDP-active test run on the target machine.
2. `"Browser Google"` label is hard-coded regardless of the selected engine — documented loophole, not changed.
3. `search_duckduckgo` returns `[]` on total failure so the circuit breaker never opens for it — documented, not changed.
4. `check_service_session_health` reports "AUTHENTICATED" when Chrome is merely running — documented observation, not changed.
5. Direct DuckDuckGo live success has never been recorded; Bing-sourced results are correctly labeled `Bing`.

## Rollback instructions

1. Roll back the implementation change: `git revert 5dd5b59` (or restore `actions/browser_search.py` from `main`, blob `d3c7a8f`).
2. Roll back report changes: delete the four new report files and `git revert` the two updated-report commits (or revert the whole branch as one).
3. Do not perform any whole-repository reset, hard reset, or unrelated cleanup; the starting tree contained pre-existing changes that must be preserved.
4. If an unexplained new regression appears after merging: revert `5dd5b59`, document the issue, and stop further risky implementation (stop condition).

## Next step

Approval of this branch is awaited. Nothing was merged to `main`; nothing beyond the audited scope was started.

# Chrome Access Audit Report (2026-11-12)

Scope: inspect and safely repair the existing Chrome/CDP access layer and the existing web-search system. Zero-breakage rule respected: no existing tool, public interface, profile, cookie, session, or unrelated module was modified. No Stage 4 / YouTube video / live-stream intelligence was started.

## Files inspected (actual, from `main` at commit `b2b8af1`)

- `actions/browser_automation.py` — CDP endpoint check (`is_cdp_active`, port 9222), `BrowserAutomationEngine` singleton, `get_or_open_page(..., allow_launch=False)` no-launch path, `_check_service_auth_async` read-only tab inspection.
- `actions/browser_search.py` — Chrome CDP search fallback.
- `actions/chrome_profile.py` — Chrome binary discovery, Local State profile resolution ("Yajat"), `sanitize_web_url` scheme allow-list (http/https only; `file:`, `javascript:`, `data:`, custom protocol handlers rejected), `redact_secrets`.
- `actions/browser_control.py` — browser control actions.
- `actions/web_search.py`, `actions/web_search_providers.py`, `actions/web_research.py`, `actions/fetch_webpage.py` — search stack.
- Existing tests: `tests/test_search_preferences_stage22.py`, `tests/test_web_search_stage2.py`, `tests/test_stage3_search_intelligence.py`, `tests/test_chrome_whatsapp_web_search.py`, `tests/test_extended_browser_controls.py`.

## Defect found and repaired (commit `5dd5b59`, branch `audit/chrome-web-search-repair-20261112`)

`actions/browser_search.py::search_in_browser` imported the automation singleton aliased as `engine`, shadowing the `engine` parameter. With an active CDP session, `_search()` received the automation engine object as the search engine; `build_search_url()` raised `ValueError("Unknown or unavailable search engine")`; the broad `except` swallowed it and returned `[]` for every query. Effect: the entire active-CDP Chrome search path silently failed and global/per-browser Chrome search preferences were ignored. The bug was invisible in all recorded runs because CDP port 9222 was inactive in every recorded run.

Repair: the local import is renamed to `automation_engine` (plus an explanatory comment). One minimal, reviewable patch. Public signature `search_in_browser(query, limit=3, browser="chrome", engine=None)`, return shapes, the no-CDP no-launch behavior, and the 73-tool registry are unchanged.

## Chrome/CDP access verification status

- **CDP port status: NOT VERIFIED in this audit.** The audit environment is not the user's Windows host; no Chrome process, profile, cookie, or session was touched, launched, or modified.
- `is_cdp_active()` performs a read-only `GET http://localhost:9222/json/version` with a 1.5s timeout — verified statically as non-invasive.
- Chrome/CDP session reuse: the existing `get_or_open_page` reuse logic (tab match by host, service-tab reuse after redirects, new-tab-only-when-needed, `bring_to_front`) was reviewed statically and found sound; the only defect on this path was the shadowing bug repaired above.
- Duplicate Chrome instance prevention: `ensure_cdp_chrome()` checks `is_cdp_active()` before any launch and contains a unit-test-runner guard; the browser-search fallback itself never calls `ensure_cdp_chrome` — it requires `is_cdp_active()` to be already true and passes `allow_launch=False`. No force-launch path exists from browser search.

## Commands for the maintainer to run on the target Windows machine

```text
python -m compileall -q actions/browser_search.py actions/browser_automation.py actions/chrome_profile.py
python -m pytest tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py -q
```

## Tests

**NOT RUN** in this audit environment (no Windows JARVIS runtime: `pywin32`, `playwright`, `faster-whisper`, `pytest` not installed here). No test file was modified, hidden, deleted, or weakened. The saved baselines remain authoritative: Stage 2 focused 42 passed; Stage 2.1 selection 231 passed / 5 failed (pre-existing in `test_web_first_master.py` and `test_addressing.py`, matching the saved baseline).

## Rollback

`git revert 5dd5b59` on the audit branch, or restore `actions/browser_search.py` from `main` (blob `d3c7a8f`). No other implementation file was changed by this audit.

## Limitations

- Live CDP behavior, tab reuse, and Chrome preference honoring on a real active session remain unverified until the focused tests run on the Windows host with CDP active.
- `chrome_profile.py`'s `check_service_session_health` reports "AUTHENTICATED" when Chrome is merely running without any login check — documented as an observation, not changed (zero-breakage).

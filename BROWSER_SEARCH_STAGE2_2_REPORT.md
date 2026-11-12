# Browser Search Stage 2.2 Report

## Outcome

Stage 2.2 implementation and offline acceptance checks passed. Browser search preferences are now managed by JARVIS in a versioned local configuration. The feature never edits native browser settings, cookies, profile files, or Windows default-browser settings.

Preference precedence is: explicit command engine → selected browser preference → global JARVIS engine. A global change leaves explicit browser choices intact. A browser can be reset to inherit the global choice.

The existing `web_search` tool handles preference display, engine selection, reset, and custom-engine add/update/remove actions. It remains the same registered tool and handler. Its public web search function signatures are preserved.

## Engines and browser support

Built-in templates are provided for Google, Bing, DuckDuckGo, Brave Search, Yahoo, and YouTube Search. Custom HTTPS templates support `{query}` and may be restricted to browsers. URL schemes and local/private hosts are rejected. Queries are URL encoded.

This installation detects Chrome and Edge. Firefox and Brave were not detected. Chrome is the only browser with an automation adapter. Edge, Firefox, and Brave have independent preference records, but their live browser automation is not implemented in this stage.

Chrome uses the existing CDP session when available. CDP was inactive during this run, so browser navigation and session reuse were not live tested. The fallback now checks CDP and refuses to start Chrome if it is unavailable.

## Persistence and recovery

Preferences are written to `config/search_preferences.json` only when a preference-changing action is used. Writes are atomic. A valid previous configuration is retained as `.json.bak`; malformed input is retained as `.json.corrupt` on the next write, while reads return safe defaults. Invalid individual browser sections do not erase valid sections for other browsers.

## Verification

- New Stage 2.2 and Stage 3 focused coverage plus existing Stage 2 provider tests: **42 passed**.
- Full relevant browser/search/intent regression selection: **138 passed, 5 failed, 1 warning**. The failures are existing app/WhatsApp routing and local window-verification assertions; see [BROWSER_SEARCH_TEST_RESULTS.md](BROWSER_SEARCH_TEST_RESULTS.md).
- Runtime registry: exactly **73 tools**, with dictionary schemas and handlers present. `web_search` remains registered.
- No browser session was opened or modified; CDP status was checked read-only.

## Modified implementation files

- `actions/search_preferences.py` (new)
- `actions/browser_search.py`
- `actions/browser_automation.py`
- `core/intent_router.py`
- `core/register_tools.py`
- `tests/test_search_preferences_stage22.py` (new)

Stage 2.2 acceptance is complete for preference configuration and URL routing. Live browser reuse remains explicitly unverified because no CDP session was active.

## Final audit addendum (2026-11-12)

A static re-audit was performed on branch `audit/final-search-audit-20261112`; full findings are in [JARVIS_FINAL_SEARCH_AUDIT_20261112.md](JARVIS_FINAL_SEARCH_AUDIT_20261112.md).

- Re-verified in code: precedence chain (explicit → browser → global), custom URL validation (exactly one `{query}`/`{searchTerms}`, HTTPS-only, public host, credential/local hosts rejected), atomic `os.replace` persistence with `fsync`, `.json.bak`/`.json.corrupt` recovery, per-browser validation isolation, and read-only browser detection.
- Re-verified in code: `actions/browser_search.py::_search` returns no results unless Chrome CDP is already active and reuses pages via `get_or_open_page(..., allow_launch=False)`; Chrome is never launched by the search fallback. CAPTCHA/login pages return empty without bypass.
- Tests were **NOT RUN** in the 2026-11-12 audit session (no runtime attached to the repository host); the 42/138-5-1 counts above remain the saved 2026-11-07 baseline. Re-run commands are listed in the audit findings file.
- Live browser/session reuse remains **NOT VERIFIED** in the audit environment; no browser was launched and no profile was modified.
- Rollback of this addendum: delete this section or do not merge the audit branch. No implementation file was changed by the audit.
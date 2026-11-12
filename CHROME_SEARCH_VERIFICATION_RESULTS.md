# Chrome Search Verification Results (2026-11-12)

## Live verification status: NOT VERIFIED (audit environment has no Chrome/CDP host)

This audit could not execute a live Chrome search because:

- The audit environment is not the user's Windows machine; there is no Chrome installation, no `LOCALAPPDATA` user data, and no CDP endpoint (port 9222) to probe.
- Per the Chrome rules, no Chrome was force-launched, no duplicate instance was started, and no profile, cookie, or session was modified. A CDP probe from this environment would be meaningless (it would report on the audit host, not the user's machine), so the CDP port status is recorded as **NOT VERIFIED / CDP_UNAVAILABLE** for this audit run rather than probed falsely.

No mocked search result is presented as live verification. All engine-preference behavior below is **statically verified in code** and covered by existing offline tests; the runtime proof on a real active CDP session remains pending.

## Statically verified Chrome search behavior

- **JARVIS-managed preference resolution:** explicit engine → Chrome preference → global default (`actions/search_preferences.py::resolve_search_engine`). Chrome preferences live in `config/search_preferences.json`, never in the Chrome profile.
- **URL generation per engine:** Google/Bing/DuckDuckGo/Brave/Yahoo/YouTube templates plus validated custom engines; queries encoded with `quote_plus`. Example (offline test, real assertion): `build_search_url("hello world & more", browser="chrome", explicit_engine="site_docs")` → `https://docs.example.org/search?q=hello+world+%26+more`.
- **Invalid URL rejection (offline tests, real assertions):** `javascript:alert(1)?q={query}` and `https://127.0.0.1/?q={query}` both raise `ValueError`.
- **No-CDP behavior (offline test, real assertion):** with `is_cdp_active()` patched false, `search_in_browser("harmless query")` returns `[]` and fails the test if browser automation is invoked — Chrome is never launched by search.
- **Active-CDP behavior:** the engine-shadowing defect that made this path always fail was repaired in commit `5dd5b59` (see CHROME_ACCESS_AUDIT_REPORT.md). With the fix, the selected engine resolves through `build_search_url` and the existing CDP tab is reused via `get_or_open_page(..., allow_launch=False)`.

## Commands for live verification on the target Windows machine

```text
:: with a controlled Chrome CDP session already active on port 9222:
python -m pytest tests/test_search_preferences_stage22.py -q
python -c "from actions.browser_search import search_in_browser; print(search_in_browser('Python official documentation'))"
```

The manual check must be run with the user's existing active CDP session; do not start a new Chrome instance just for verification. If port 9222 is inactive, the expected result is `[]` with `CDP_UNAVAILABLE` semantics — that is the documented safe behavior, not a failure.

## Recorded live results from prior runs (not this audit)

- 2026-11-07 (recorded): CDP port 9222 inactive on the user's machine; live browser search was **NOT VERIFIED** then as well. Chrome windows existed but no attachable CDP session was exposed, and no Chrome process was launched for testing.

## Limitations

- Until a CDP-active run happens on the target machine, active-session tab reuse, real Google/Bing result extraction, and per-engine URL navigation remain unverified.
- The `search_provider` label for browser results is hard-coded to `"Browser Google"` even when another engine is selected — documented loophole, not changed (zero-breakage).

## Rollback

`git revert 5dd5b59` restores the pre-fix file; report updates are additive. No Chrome-native setting was ever touched, so no browser-side rollback exists.

# Browser Compatibility Report

## Detected on this machine

| Browser | Installed | JARVIS integration in this stage | Live status |
|---|---:|---|---|
| Google Chrome | Yes | Existing Chrome CDP automation; JARVIS-managed search routing | CDP inactive; live browser navigation NOT VERIFIED |
| Microsoft Edge | Yes | Independent preference and URL-template support | Browser automation NOT IMPLEMENTED |
| Mozilla Firefox | No | Independent preference and URL-template support | Not installed; NOT VERIFIED |
| Brave Browser | No | Independent preference and URL-template support | Not installed; NOT VERIFIED |

Detection checks executable locations and `PATH` without launching a browser. No native search preference, default-browser setting, profile, cookie, or saved session was changed.

## Chrome behavior

The browser search fallback checks the current CDP endpoint before running. When active, it calls the existing page reuse method with `allow_launch=False`; if CDP inactive, it returns no browser results and allows the existing provider fallback. It does not force-launch Chrome or create another profile.

## Limitation

The current adapter only automates Chrome through CDP. Secondary browsers have independent JARVIS preferences and validated search URLs, but do not yet have browser-specific live adapters. Chrome session reuse could not be observed because port 9222 was inactive during verification.

## Final audit addendum (2026-11-12)

A static re-audit was performed on branch `audit/final-search-audit-20261112`; full findings are in [JARVIS_FINAL_SEARCH_AUDIT_20261112.md](JARVIS_FINAL_SEARCH_AUDIT_20261112.md).

- Re-verified in code: `detect_installed_browsers` in `actions/search_preferences.py` is read-only (filesystem + `shutil.which`); it never starts a browser. Chrome is flagged `chrome_cdp` integration; edge/firefox/brave are `preference_only`.
- Re-verified in code: the Chrome-only guard (`browser != "chrome" or not is_cdp_active()` → return empty) means non-Chrome browsers can never trigger automation; `ensure_cdp_chrome()` is only reachable through explicit WhatsApp/browser-control features, not search.
- Browser availability in this audit environment: **NOT VERIFIED** (the audit host is not the user's Windows machine; no executable detection was run). The table above remains the saved 2026-11-07 state.
- CDP status in this audit environment: **NOT VERIFIED**; no browser was launched and no profile was modified.
- Rollback of this addendum: delete this section or do not merge the audit branch. No implementation file was changed by the audit.
# Browser Compatibility Report

## Final audit update (2026-11-12)

This audit could not probe the host machine for installed browsers or CDP status (no Windows JARVIS runtime in the audit environment), so live browser detection and CDP behavior are **NOT VERIFIED** for this audit run; the table below records the last verified machine state from the original Stage 2.2 run. One real bug found in `actions/browser_search.py` (engine shadowing that silently failed every active-CDP browser search) was fixed in commit `f832f76`; see [SEARCH_FINAL_AUDIT_20261112.md](SEARCH_FINAL_AUDIT_20261112.md) for details, test-execution status, and rollback instructions.

## Detected on this machine

| Browser | Installed | JARVIS integration in this stage | Live status |
|---|---:|---|---|
| Google Chrome | Yes | Existing Chrome CDP automation; JARVIS-managed search routing | CDP inactive; live browser navigation NOT VERIFIED |
| Microsoft Edge | Yes | Independent preference and URL-template support | Browser automation NOT IMPLEMENTED |
| Mozilla Firefox | No | Independent preference and URL-template support | Not installed; NOT VERIFIED |
| Brave Browser | No | Independent preference and URL-template support | Not installed; NOT VERIFIED |

Detection checks executable locations and `PATH` without launching a browser. No native search preference, default-browser setting, profile, cookie, or saved session was changed.

## Chrome behavior

The browser search fallback checks the current CDP endpoint before running. When active, it calls the existing page reuse method with `allow_launch=False`; if CDP is inactive, it returns no browser results and allows the existing provider fallback. It does not force-launch Chrome or create another profile.

Note (2026-11-12 audit): until commit `f832f76`, the active-CDP path contained a parameter-shadowing bug that made every browser search silently return `[]`; the fix restores engine resolution so per-browser and global preferences are honored on the CDP path. Live CDP navigation still needs verification on a machine with an active controlled Chrome session.

## Limitation

The current adapter only automates Chrome through CDP. Secondary browsers have independent JARVIS preferences and validated search URLs, but do not yet have browser-specific live adapters. Chrome session reuse could not be observed because port 9222 was inactive during verification.
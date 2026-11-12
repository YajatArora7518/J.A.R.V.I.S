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

The browser search fallback checks the current CDP endpoint before running. When active, it calls the existing page reuse method with `allow_launch=False`; if CDP is inactive, it returns no browser results and allows the existing provider fallback. It does not force-launch Chrome or create another profile.

## Limitation

The current adapter only automates Chrome through CDP. Secondary browsers have independent JARVIS preferences and validated search URLs, but do not yet have browser-specific live adapters. Chrome session reuse could not be observed because port 9222 was inactive during verification.

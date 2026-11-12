# Search Verification Results

## Final audit update (2026-11-12)

The 2026-11-12 audit performed **no live search** and **no browser/CDP operations**; all live-verification claims below are from the prior recorded run (2026-11-07) and remain **NOT VERIFIED** in this audit environment. No mocked result was reported as live verification. Full audit findings, including the fixed `actions/browser_search.py` engine-shadowing bug (commit `f832f76`), documented loopholes, and rollback instructions, are in [SEARCH_FINAL_AUDIT_20261112.md](SEARCH_FINAL_AUDIT_20261112.md).

## Live harmless query (recorded 2026-11-07)

- Query: `Python official documentation`
- Search success: **Yes**
- Provider reported: **Bing** (reached through the zero-cost DuckDuckGo fallback cascade)
- Fallback reported: **Yes**
- Retrieval time: `2026-11-07T06:32:04.651073+00:00` (UTC)
- Results: 5, with valid HTTP(S) URLs and normalized titles/snippets/source/date fields.

First three returned links:

1. [Welcome to Python.org](https://www.python.org/)
2. [Download Python](https://www.python.org/downloads/)
3. [Online Python Compiler — Programiz](https://www.programiz.com/python-programming/online-compiler/)

The live result verifies the current Bing fallback path. It does not verify Google, Serper, Brave API, direct DuckDuckGo HTML, or browser/CDP search. No factual sports ranking was claimed or tested as live verified.

## Browser safety (recorded 2026-11-07)

Chrome was detected, but CDP port 9222 was inactive. Browser fallback was not forced and no browser profile/session was changed.
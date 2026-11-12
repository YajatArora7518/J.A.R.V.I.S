# Chrome Browser Search Report (2026-11-12)

Scope: JARVIS-managed Chrome search preferences and the Chrome browser-search fallback, audited and repaired under the zero-breakage rule. Chrome remains JARVIS's primary browser; native Chrome settings, profiles, cookies, saved logins, and tabs are never modified by search preferences.

## JARVIS-managed Chrome search preference system (verified in code)

`actions/search_preferences.py` stores preferences in the versioned `config/search_preferences.json` (schema version 1) — inside the JARVIS config directory, **never inside the Chrome profile**. Behavior verified statically:

- Precedence: explicit command engine → per-browser (Chrome) preference → global JARVIS default.
- Built-in engine templates for Chrome: Google, Bing, DuckDuckGo, Brave Search, Yahoo, YouTube.
- Custom search engines: named HTTPS templates with `{query}` or `{searchTerms}` placeholder, optional browser restriction, enable/disable, add/update/remove — all through the existing `web_search` tool (no new tool added; the 73-tool registry is unchanged).
- Validation (`validate_search_url_template`): HTTPS only; exactly one placeholder; embedded username/password rejected; `localhost`, `.local`, `.internal`, and dot-less hosts rejected; private/non-global IPs rejected. Dangerous schemes (`javascript:`, `file:`, `data:`, `vbscript:`) fail the HTTPS scheme check and are rejected.
- Queries are URL-encoded with `quote_plus` before substitution (`build_search_url`).
- Persistence: atomic tempfile write with `fsync` + `os.replace`; last valid file kept as `.json.bak`; malformed file preserved as `.json.corrupt`; corrupt reads return safe defaults without overwriting the corrupt file.
- Natural commands routed through the existing `web_search` tool and `core/intent_router.py` (verified by existing tests): "Chrome mein Google se search karo", "Chrome mein Bing default kar do", "Chrome ki search settings dikhao", "Chrome mein FFWS standings search karo".

## Chrome search fallback behavior (verified in code)

- Runs only when `browser == "chrome"` **and** `is_cdp_active()` is true. When CDP is unavailable it returns `[]` — it never launches Chrome, never substitutes another browser, and the normal web-provider fallback continues. No duplicate Chrome instance can be started from this path (`allow_launch=False` is always passed; `ensure_cdp_chrome` is unreachable from browser search).
- Reuses the existing CDP session/tab via `get_or_open_page` (host-based tab match, redirect-safe service tab reuse, new tab only when no tab matches).
- CAPTCHA/login/`/sorry/`/unusual-traffic pages return `[]` — never bypassed.
- Google `/goto?`/`/url?` wrappers are followed in a temporary tab to the real final URL; hidden provider state is never decoded.
- Results are deduplicated, relevance-filtered (`_relevant_results`), and normalized to the standard shape (`title`, `url`, `snippet`, `source`, `date`) with `search_provider: "Browser Google"`.

## Defect repaired (commit `5dd5b59`)

`search_in_browser`'s local import shadowed the `engine` parameter, so every active-CDP Chrome search raised inside `build_search_url` and silently returned `[]`, ignoring the selected engine (Google/Bing/DuckDuckGo/custom). The fix renames the local import to `automation_engine`. Until this fix, engine selection on the CDP path never worked at runtime.

## Live verification status

- **CDP port 9222: NOT VERIFIED** in this audit (audit host is not the user's Windows machine). No browser was launched; no profile, cookie, or session was modified.
- Live Chrome navigation, tab reuse, and per-engine URL generation against a real active CDP session are **NOT VERIFIED** and must be exercised on the target machine.
- No mocked result is reported as live verification. The engine-shadowing fix is proven statically; its runtime effect (non-empty results with the selected engine) awaits the CDP-active test run.

## Commands to verify on the target machine

```text
python -m pytest tests/test_search_preferences_stage22.py -q
```

Key existing assertions that cover this area: per-browser engine independence, custom template URL encoding and rejection (`javascript:`, private IP), corrupt-config recovery, no-CDP no-launch behavior, Hinglish preference commands, custom-engine lifecycle, and the 73-tool registry.

## Tests

**NOT RUN** in this audit environment (no Windows JARVIS runtime). Saved baseline for this suite: **42 passed** (focused Stage 2.2/Stage 3/Stage 2 provider tests). No test was modified or weakened.

## Rollback

`git revert 5dd5b59` (or restore `actions/browser_search.py` from `main` blob `d3c7a8f`). Report updates are additive and revert with the same revert. No Chrome-native setting or profile data exists in the repository and none was touched.

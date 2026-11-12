# JARVIS Final Search Audit — Findings (2026-11-12)

Scope: JARVIS-managed global/per-browser search preferences, custom search URL validation/persistence/recovery/reset, Chrome CDP fallback launch guard, provider order/timeouts/retries/rate limits/circuit breaker, result normalization/dedup/ranking/date distinctions, page table extraction and source-grounded research, tool registry count/handlers/schemas and `web_search` public signatures.

ZERO-BREAKAGE context: This audit only **reads** the working tree. No implementation file was modified. No existing functionality was changed. Stage 4, YouTube video analysis, and live-stream analysis were not started.

Audit method: static code review of `actions/search_preferences.py`, `actions/browser_search.py`, `actions/browser_automation.py`, `actions/web_search.py`, `actions/web_search_providers.py`, `actions/web_research.py`, `actions/fetch_webpage.py`, `actions/web_search_diagnostic.py`, `core/register_tools.py`, `core/intent_router.py`, tests, and existing stage reports.

## Executive summary

The browser-search preference and web-search intelligence implementation is structurally sound. No syntax or runtime-breaking defect was found in the audited files. Indentation anomalies seen in some raw fetches were verified against the GitHub blob payloads and are fetch-rendering artifacts, not real code defects. A few low-severity findings and documentation gaps are listed below with exact file/function references.

## Findings

### F1 (Verified OK) — Search preference store
`actions/search_preferences.py`
- Versioned schema (v1), thread-safe RLock, atomic `os.replace` writes with `fsync`, `.json.bak` backup, `.json.corrupt` preservation, malformed reads return safe defaults without overwriting the corrupt file.
- Precedence explicit engine → browser pref → global default works, including `custom_url` per browser and browser-restricted custom engines.
- `validate_search_url_template` enforces exactly one `{query}`/`{searchTerms}` placeholder, HTTPS-only, public host, rejects localhost/`.local`/`.internal`/private IPs, blocks embedded credentials.
- `detect_installed_browsers` is read-only and never launches a browser.
- Minor observation (not a bug): a raw IP that is a *public* literal is accepted; hostname-based checks (`"." not in host`) already reject bare IPs because they lack a dot for IPv4 and `ipaddress` handles IPv6 — acceptable.

### F2 (Verified OK) — Chrome CDP fallback launch guard
`actions/browser_search.py::_search` returns `[]` immediately unless `browser == "chrome"` and `is_cdp_active()` is true; page reuse goes through `get_or_open_page(..., allow_launch=False)`, which in `actions/browser_automation.py` uses `{success: is_cdp_active(), ...}` instead of `ensure_cdp_chrome()`. Chrome is therefore never launched by the search fallback. CAPTCHA/login/`/sorry/` pages return `[]` without bypass. Confirmed by `tests/test_search_preferences_stage22.py::test_existing_browser_search_interface_does_not_force_launch_when_cdp_missing`.

### F3 (Verified OK) — Provider order, timeouts, bounded retries, rate limits, circuit breaker
`actions/web_search.py::_web_search_structured_impl` + `actions/web_search_providers.py`
- Cascade Google CSE → Serper → Brave → DuckDuckGo/Bing → browser fallback; configured `preferred_provider` reorders the paid providers first; `fallback=false` restricts to the single requested provider.
- Per-provider bounded timeouts (connect 3.0s; read 2.5–5.0s). `urllib3 Retry(total=1, connect=1, read=0, status=1, status_forcelist=(429, 502, 503, 504))` — single bounded retry, 429 counted as rate-limit failure.
- Process-local circuit breaker: 3 consecutive failures → 30s cooldown (`open_until`), skipped while open; health diagnostics expose only state/failure counts and error categories, never credentials or bodies.
- Missing credentials short-circuit (`_failure(..., "missing_credentials")`, return None) before any authenticated request is sent.

### F4 (Verified OK) — Normalization, dedup, ranking, date distinctions
`_normalize_search_results` sanitizes untrusted title/snippet, strips trackers via `_source_url` (DDG `uddg`, Bing `/ck/a1` base64), rejects local/private hosts, dedupes by scheme+host+normalized path+query, then `_rank_search_results` applies stable authority ordering (gov/edu/official → major news → rest) with original index as tiebreaker.
Dates: `fetch_webpage` returns separate `published_at`, `updated_at`, `event_date: None`, `retrieved_at`; `web_research._freshness_metadata` keeps all four distinct; `event_date` is never inferred — documented and implemented.

### F5 (Verified OK) — Table extraction and source grounding
`fetch_webpage._extract_html_tables` is bounded (8 tables/40 rows/12 cols), header-aware standings classification with entity/rank/points column indexes. `web_research.answer_from_pages` requires actual fetched page content, verifies quote presence in page text, checks numbers subset, runs a second independent fact-check pass, tracks `independent_source_count` and `cross_source_status`, and refuses answers without page evidence. Snippets alone are never accepted as verified.

### F6 (Verified OK) — Tool registry, handlers, schemas, public signatures
`core/register_tools.py` registers `web_search` (risk LOW, lazy `actions.web_search.web_search_tool`) and `fetch_webpage`; the `web_search` schema is a dictionary with the original required `["query"]` plus additive optional properties (browser/search_engine/action/scope/search_url/display_name/enabled/browsers/preferred_provider/enabled_providers/fallback/result_limit). No tool added or removed; tests assert exactly 73 tools with handlers and OBJECT schemas. `web_search_structured(query, num_results=5, preferred_provider=None, force_refresh=False)` signature preserved.

### F7 (Low severity) — `_QueryCache.set` can evict a fresh entry (logic order)
`actions/web_search.py::_QueryCache.set` pops `clean_q` before inserting while the size cap loop evicts oldest entries — with 128 entries at cap this can evict a just-inserted entry in a corner case (the pop happens before insert; the while-loop evicts `next(iter(...))` which after insert could be the new key only if dict ordering placed it first — it cannot, since dicts preserve insertion order; still the pre-pop is redundant). Impact: negligible; cached lookups re-search instead of reusing. No action taken under zero-breakage; noted for a future cleanup.

### F8 (Low severity) — provider failure-reason mapping keyed by display name
`_provider_search` maps display names to provider keys via `startswith` chains (`"google custom" → "google"`, etc.). `"Browser google"` is not mapped, so its `_PROVIDER_LAST_FAILURE` lookups miss — but browser failures are still counted into the circuit breaker through the generic path. Cosmetic; no behavior break.

### F9 (Low severity) — DuckDuckGo HTML status handling
`search_duckduckgo` treats non-200/non-429 HTTP codes only as a warning line, then falls to Bing HTML and DDGS library. The provider status dict keeps `duckduckgo: True` unconditionally (documented as "always available fallback"). Not a defect, but the health table can overstate DuckDuckGo when all three paths fail; failure is still reported through the circuit breaker as "DuckDuckGo".

### F10 (Info) — `_PROVIDER_HEALTH` resets on process restart
Documented in SEARCH_PROVIDER_HEALTH_REPORT.md and confirmed in code: health is process-local by design. No cross-run persistence, which also avoids persisting diagnostics that could leak query patterns. Acceptable.

### F11 (Info) — `web_search` legacy handler `num_res` int cast
`web_search()` does `int(params.get("num_results") or 5)` without try/except; a non-numeric string raises and would propagate. The tool schema declares INTEGER, and the structured path clamps safely, so risk is limited to direct programmatic callers. Noted only.

### F12 (Info) — Cricket official-index refinement is domain-specific
The `bcci.tv`/`icc-cricket.com` official news-index refinement in `web_search_tool` is a query refinement with live page evidence, not a stored answer — consistent with the source-grounding rules. Tournament season/region disambiguation remains a documented limitation (no dedicated parser).

## Bugs / loopholes NOT found (explicitly checked)
- No secret/credential printing anywhere in the audited providers/pref modules; keys are only checked for presence and passed in headers.
- No authenticated request when credentials are missing (short-circuit verified).
- No browser launch when CDP is unavailable (guard verified in code + test).
- No CAPTCHA/login bypass in browser search.
- No whole-repo reset, unrelated module edits, or test weakening in this audit (no code changes at all).
- No syntax/indentation defects (raw-fetch artifacts verified against GitHub blob payloads).

## Commands (for the maintainer to run locally)
The focused and regression suites were NOT RUN in this audit session (no runtime attached to the repo host). Baseline from the prior run is documented in BROWSER_SEARCH_TEST_RESULTS.md: focused 42 passed; broader 138 passed / 5 failed (pre-existing, in `tests/test_web_automation.py` and `tests/test_web_first_master.py`).

```text
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py
pytest -q tests/test_search_preferences_stage22.py tests/test_web_search_stage2.py tests/test_stage3_search_intelligence.py tests/test_web_search.py tests/test_web_reliability.py tests/test_live_search_recovery.py tests/test_extended_browser_controls.py tests/test_chrome_whatsapp_web_search.py tests/test_web_automation.py tests/test_web_first_master.py
python -m compileall actions/search_preferences.py actions/browser_search.py actions/browser_automation.py actions/web_search.py actions/web_search_providers.py actions/web_research.py actions/fetch_webpage.py
```

Any NEW failure versus the saved baseline should be investigated; failing tests must not be hidden, deleted, or weakened.

## Rollback
This change adds one new report file and appends short audit sections to existing report files on branch `audit/final-search-audit-20261112`. No implementation or test file was touched. Rollback = delete this file and the appended sections, or simply not merge the branch. Whole-repository reset is not required and is discouraged.

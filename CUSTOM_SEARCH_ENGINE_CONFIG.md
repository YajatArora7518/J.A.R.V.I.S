# Custom Search Engine Configuration

## Storage

JARVIS-managed preferences use the versioned `config/search_preferences.json` file. It is created on the first preference change; it does not migrate or overwrite `config/api_keys.json` or native browser configuration.

Schema version 1 stores:

- `global`: default engine, preferred provider, behavior, result limit, freshness mode, and fallback setting.
- `browsers`: independent Chrome, Edge, Firefox, and Brave settings.
- `custom_engines`: named URL templates with enabled state and optional browser restrictions.

## Supported actions through the existing `web_search` tool

- `show_search_preferences`
- `set_search_preference` with `scope=global` or a `browser`
- `reset_browser_search`
- `add_search_engine`
- `update_search_engine` (including enable/disable)
- `remove_search_engine`

The same controls recognize common English and Hinglish forms such as “Chrome mein Bing default kar do” and “Chrome aur Edge ki search settings dikhao.”

Global settings can also set a preferred provider, fallback policy, and default result limit. These affect JARVIS routing only, not browser-native settings.

## URL rules

Custom templates must use HTTPS, contain exactly one `{query}` or `{searchTerms}` placeholder, and use a public host. `javascript:`, local/private IP addresses, localhost, and local/internal hostnames are rejected. Query text is encoded with `quote_plus` before substitution.

Example:

```json
{
  "name": "Documentation",
  "url": "https://docs.example.org/search?q={query}",
  "enabled": true,
  "browsers": ["chrome"]
}
```

The URL is illustrative; an actual definition must be supplied by the user. Site-specific search uses the same validated template mechanism.

## Safe recovery

Writes go to a temporary file and are atomically replaced. Existing valid settings receive one `.json.bak` backup. A malformed file is preserved as `.json.corrupt` when a write recovers it. Valid browser settings are validated independently, so a malformed Edge entry does not erase Chrome or global preferences. Resetting one browser clears only its explicit engine and custom URL so it inherits global settings.

## Final audit addendum (2026-11-12)

A static re-audit was performed on branch `audit/final-search-audit-20261112`; full findings are in [JARVIS_FINAL_SEARCH_AUDIT_20261112.md](JARVIS_FINAL_SEARCH_AUDIT_20261112.md).

- Re-verified in code: `validate_search_url_template` enforces exactly one placeholder, normalizes `{searchTerms}` to `{query}`, requires a public HTTPS host, rejects embedded username/password, localhost, `.local`/`.internal` suffixes, and private (non-global) IP addresses. Query encoding uses `quote_plus`.
- Re-verified in code: custom engine names must match `[a-z0-9_-]{1,40}` and cannot shadow built-in engines; disabled or browser-restricted engines are excluded from resolution; removing a custom engine resets global/browsers that referenced it back to safe defaults (global → google, browser → inherit).
- Re-verified in code: writes are atomic (`tempfile` + `fsync` + `os.replace`) under a re-entrant lock; `.json.bak` holds the last valid file and `.json.corrupt` preserves malformed input; reads never overwrite a malformed file.
- Tests were **NOT RUN** in the 2026-11-12 audit session; the saved 2026-11-07 baseline for the preference suites remains 42 passed.
- No runtime preference file existed to inspect in this environment; per-file persistence behavior was verified through code review and the existing offline tests only. **NOT VERIFIED live.**
- Rollback of this addendum: delete this section or do not merge the audit branch. No implementation file was changed by the audit.
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

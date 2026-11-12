"""Local, JARVIS-managed browser search preferences (never edits native profiles)."""
from __future__ import annotations

import copy
import json
import ipaddress
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

SCHEMA_VERSION = 1
_LOCK = threading.RLock()
_CONFIG = Path(__file__).resolve().parent.parent / "config" / "search_preferences.json"
_ENGINES = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "brave": "https://search.brave.com/search?q={query}",
    "yahoo": "https://search.yahoo.com/search?p={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
}
_BROWSERS = ("chrome", "edge", "firefox", "brave")


def _default_config():
    return {"schema_version": SCHEMA_VERSION,
            "global": {"default_engine": "google", "behavior": "web", "preferred_provider": "any",
                       "result_limit": 5, "freshness": "automatic", "fallback": True},
            "browsers": {name: {"enabled": True, "default_engine": None, "custom_url": None,
                                 "enabled_providers": [], "behavior": "inherit", "preferences": {}}
                          for name in _BROWSERS},
            "custom_engines": {}}


def validate_search_url_template(template: str) -> str:
    if not isinstance(template, str) or len(template) > 2000 or template.count("{query}") + template.count("{searchTerms}") != 1:
        raise ValueError("Search URL must contain exactly one {query} or {searchTerms} placeholder")
    normalized = template.replace("{searchTerms}", "{query}")
    parts = urlsplit(normalized.replace("{query}", "query"))
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Custom search URLs must use a public HTTPS host")
    host = parts.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or "." not in host or host.endswith((".local", ".internal")):
        raise ValueError("Custom search URL host must be a public domain")
    try:
        if not ipaddress.ip_address(host).is_global: raise ValueError("Custom search URL host must be public")
    except ValueError as exc:
        if "must be public" in str(exc): raise
    return normalized


def _validate(data):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported search preference schema")
    base = _default_config()
    glob = data.get("global") if isinstance(data.get("global"), dict) else {}
    engine = str(glob.get("default_engine", "google")).lower()
    raw_customs = data.get("custom_engines", {})
    custom_names = raw_customs.keys() if isinstance(raw_customs, dict) else ()
    if engine not in (*_ENGINES, *custom_names): engine = "google"
    base["global"].update(glob)
    base["global"]["default_engine"] = engine
    try: base["global"]["result_limit"] = max(1, min(10, int(base["global"].get("result_limit", 5))))
    except (ValueError, TypeError): base["global"]["result_limit"] = 5
    base["global"]["fallback"] = base["global"].get("fallback") is not False
    if base["global"].get("preferred_provider") not in ("any", "google", "serper", "brave", "duckduckgo", "bing"):
        base["global"]["preferred_provider"] = "any"
    customs = data.get("custom_engines", {})
    if isinstance(customs, dict):
        for key, value in customs.items():
            if not re.fullmatch(r"[a-z0-9_-]{1,40}", str(key)) or key in _ENGINES or not isinstance(value, dict): continue
            try: url = validate_search_url_template(value.get("url"))
            except (ValueError, TypeError): continue
            base["custom_engines"][key] = {"name": str(value.get("name") or key)[:80], "url": url,
                                           "enabled": value.get("enabled") is not False,
                                           "browsers": [b for b in value.get("browsers", []) if b in _BROWSERS]}
    browser_data = data.get("browsers", {})
    for browser in _BROWSERS:
        current = browser_data.get(browser) if isinstance(browser_data, dict) else None
        if not isinstance(current, dict): continue
        entry = base["browsers"][browser]
        entry["enabled"] = current.get("enabled") is not False
        candidate = current.get("default_engine")
        if candidate is None or (isinstance(candidate, str) and (candidate in _ENGINES or candidate in base["custom_engines"])):
            entry["default_engine"] = candidate
        custom_url = current.get("custom_url")
        if custom_url:
            try: entry["custom_url"] = validate_search_url_template(custom_url)
            except (ValueError, TypeError): pass
        allowed = current.get("enabled_providers", [])
        entry["enabled_providers"] = [p for p in allowed if p in ("google", "serper", "brave", "duckduckgo", "bing")] if isinstance(allowed, list) else []
        entry["behavior"] = str(current.get("behavior", "inherit"))[:40]
        entry["preferences"] = current.get("preferences", {}) if isinstance(current.get("preferences"), dict) else {}
    return base


def _read():
    if not _CONFIG.exists(): return _default_config()
    try:
        return _validate(json.loads(_CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # Preserve the malformed file for inspection; do not overwrite it just by reading.
        return _default_config()


def get_search_preferences():
    with _LOCK: return copy.deepcopy(_read())


def update_search_preferences(*, global_settings=None, browser_settings=None, custom_engines=None, remove_custom_engines=None):
    """Apply a partial update and atomically persist it, preserving other browser entries."""
    with _LOCK:
        config = _read()
        if isinstance(global_settings, dict): config["global"].update(global_settings)
        if isinstance(browser_settings, dict):
            for browser, values in browser_settings.items():
                if browser not in _BROWSERS or not isinstance(values, dict): raise ValueError("Unsupported browser settings")
                config["browsers"][browser].update(values)
        if isinstance(custom_engines, dict): config["custom_engines"].update(custom_engines)
        for name in remove_custom_engines or []: config["custom_engines"].pop(str(name), None)
        config = _validate(config)
        _CONFIG.parent.mkdir(parents=True, exist_ok=True)
        if _CONFIG.exists():
            try:
                json.loads(_CONFIG.read_text(encoding="utf-8"))
                backup = _CONFIG.with_suffix(".json.bak")
                if not backup.exists(): backup.write_bytes(_CONFIG.read_bytes())
            except (OSError, ValueError):
                corrupt = _CONFIG.with_suffix(".json.corrupt")
                if not corrupt.exists(): corrupt.write_bytes(_CONFIG.read_bytes())
        fd, temp_name = tempfile.mkstemp(prefix=".search_preferences_", suffix=".tmp", dir=str(_CONFIG.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(config, stream, indent=2, ensure_ascii=False)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp_name, _CONFIG)
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)
        return copy.deepcopy(config)


def reset_browser_to_global(browser):
    if browser not in _BROWSERS: raise ValueError("Unsupported browser")
    return update_search_preferences(browser_settings={browser: {"default_engine": None, "custom_url": None}})


def resolve_search_engine(*, browser=None, explicit_engine=None):
    config = get_search_preferences()
    if browser is not None and browser not in _BROWSERS: raise ValueError("Unsupported browser")
    if browser is not None and not config["browsers"][browser].get("enabled", True):
        raise ValueError("Search preferences are disabled for this browser")
    engine = explicit_engine
    if engine is None and browser in _BROWSERS:
        prefs = config["browsers"][browser]
        engine = prefs.get("default_engine")
        if not engine and prefs.get("custom_url"): return "custom", prefs["custom_url"]
    engine = str(engine or config["global"]["default_engine"]).lower()
    if engine in _ENGINES: return engine, _ENGINES[engine]
    definition = config["custom_engines"].get(engine)
    if definition and definition.get("enabled") and (not definition.get("browsers") or browser in definition["browsers"]):
        return engine, definition["url"]
    raise ValueError("Unknown or unavailable search engine")


def build_search_url(query, *, browser=None, explicit_engine=None):
    if not isinstance(query, str) or not query.strip(): raise ValueError("Search query is required")
    _, template = resolve_search_engine(browser=browser, explicit_engine=explicit_engine)
    return template.replace("{query}", quote_plus(query.strip()))


def detect_installed_browsers():
    """Read-only Windows browser presence check; it never starts a browser."""
    import shutil
    candidates = {
        "chrome": [os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google/Chrome/Application/chrome.exe"),
                   os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google/Chrome/Application/chrome.exe")],
        "edge": [os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Microsoft/Edge/Application/msedge.exe")],
        "firefox": [os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Mozilla Firefox/firefox.exe")],
        "brave": [os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "BraveSoftware/Brave-Browser/Application/brave.exe")],
    }
    detected = {}
    for browser, paths in candidates.items():
        executable = next((p for p in paths if os.path.isfile(p)), None) or shutil.which({"chrome":"chrome", "edge":"msedge", "firefox":"firefox", "brave":"brave"}[browser])
        detected[browser] = {"installed": bool(executable), "integration": "chrome_cdp" if browser == "chrome" else "preference_only",
                             "executable": executable}
    return detected

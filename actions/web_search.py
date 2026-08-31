# actions/web_search.py
# Real Web Search System for JARVIS with Provider Fallback, Caching, Intent Detection & Source Tracking

import os
import re
import json
import time
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

from actions.web_search_providers import (
    init_search_providers,
    search_google_custom,
    search_serper,
    search_brave,
    search_duckduckgo,
    _PROVIDER_STATUS,
)
from actions.fetch_webpage import fetch_webpage

# Initialize search providers at import time
init_search_providers()

# ── INTENT DETECTION ENGINE ──
_EXPLICIT_SEARCH_TRIGGERS = [
    # English Triggers
    r"google\s+search", r"search\s+(the\s+)?web", r"search\s+(the\s+)?internet",
    r"look\s+it\s+up", r"look\s+this\s+up", r"check\s+online", r"find\s+online",
    r"verify\s+online", r"search\s+news", r"search\s+for", r"google\s+for",
    r"google\s+this", r"google\s+it", r"google\s+about", r"search\s+this",
    r"\bgoogle\s+[a-zA-Z0-9]", r"\bonline\s+search\b",
    r"search\s+[a-zA-Z0-9_\-]+\s+for", r"search\s+youtube(\s+for)?", r"youtube\s+search",
    r"latest\s+news", r"current\s+price", r"latest\s+price", r"today'?s\s+weather",
    r"\blatest\b", r"\bcurrent\b", r"today", r"\bnews\b", r"\bprice\b",
    r"live\s+score", r"latest\s+update", r"release\s+date", r"official\s+website",
    r"what\s+happened", r"who\s+won", r"best\s+[a-zA-Z0-9_\-\s]+\s+under",

    # Hinglish / Hindi Triggers
    r"google\s+karke", r"google\s+par", r"google\s+se", r"web\s+par",
    r"internet\s+par", r"internet\s+se", r"online\s+check", r"aaj\s+ka",
    r"aaj\s+ki", r"abhi\s+ka", r"latest\s+information", r"khabar\s+batao",
    r"search\s+karo", r"search\s+karke", r"check\s+karo", r"dekh\s+ke\s+batao",
]


def detect_web_search_intent(user_text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Detects if user prompt strongly requests web/internet search.
    Returns: (is_search_required, query_text, requested_provider)
    """
    text = (user_text or "").strip()
    if not text:
        return False, "", None

    lower_text = text.lower()

    # Determine requested provider
    requested_provider = None
    if "google" in lower_text:
        requested_provider = "google"

    # Check against search triggers
    for pattern in _EXPLICIT_SEARCH_TRIGGERS:
        if re.search(pattern, lower_text):
            # Clean up introductory command prefix if present (e.g. "Google search karke batao ...")
            clean_query = text
            prefixes = [
                r"^google\s+search\s+karke\s+(batao|karo)?",
                r"^google\s+par\s+(search\s+)?(karo|batao)?",
                r"^google\s+se\s+check\s+(karo|batao)?",
                r"^web\s+par\s+search\s+(karo|batao)?",
                r"^internet\s+par\s+check\s+(karo|batao)?",
                r"^online\s+check\s+(karo|batao)?",
                r"^search\s+the\s+web\s+for",
                r"^search\s+internet\s+for",
                r"^search\s+for",
                r"^google\s+for",
            ]
            for p in prefixes:
                clean_query = re.sub(p, "", clean_query, flags=re.IGNORECASE).strip()

            if not clean_query:
                clean_query = text

            return True, clean_query, requested_provider

    return False, text, requested_provider


# ── QUERY CACHE SYSTEM ──
class _QueryCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        clean_q = query.strip().lower()
        if self._is_live_query(clean_q):
            print(f"[WEB DEBUG] Bypassing cache for live query: {query!r}")
            return None  # Bypass cache for live/time-sensitive queries
        if clean_q in self._cache:
            entry = self._cache[clean_q]
            if time.time() - entry["timestamp"] < self.ttl:
                print(f"[WEB DEBUG] Cache hit for query: {query!r}")
                return entry["data"]
            del self._cache[clean_q]
        return None

    def set(self, query: str, data: Dict[str, Any]):
        clean_q = query.strip().lower()
        if not self._is_live_query(clean_q):
            self._cache[clean_q] = {
                "timestamp": time.time(),
                "data": data
            }

    def _is_live_query(self, query: str) -> bool:
        live_triggers = [
            "today", "today's", "now", "current", "latest", "recent", "price", "stock",
            "availability", "news", "score", "weather", "cricket", "football", "match",
            "result", "ranking", "live", "2026", "this week"
        ]
        return any(t in query for t in live_triggers)


_search_cache = _QueryCache(ttl_seconds=60)


def web_search_structured(
    query: str,
    num_results: int = 5,
    preferred_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs a real internet search and returns structured result data:
    {
        "success": bool,
        "live_search": bool,
        "query": str,
        "requested_provider": str,
        "provider": str,
        "fallback_used": bool,
        "results": [
            {"title": str, "url": str, "snippet": str, "source": str, "date": str}
        ]
    }
    """
    clean_query = (query or "").strip()
    print(f"[WEB DEBUG] User query: {clean_query!r}")

    if not clean_query:
        return {
            "success": False,
            "live_search": False,
            "query": "",
            "requested_provider": preferred_provider or "any",
            "provider": "none",
            "fallback_used": False,
            "results": [],
            "error": "Empty search query"
        }

    # Check Intent
    is_intent, intent_query, detected_prov = detect_web_search_intent(clean_query)
    requested_prov = preferred_provider or detected_prov or ("google" if "google" in clean_query.lower() else "any")
    print(f"[WEB DEBUG] Search intent detected: {is_intent}")
    print(f"[WEB DEBUG] Requested provider: {requested_prov}")

    # Check Cache
    cached = _search_cache.get(clean_query)
    if cached:
        return cached

    print(f"[WEB DEBUG] Selected provider search starting...")
    results = None
    used_provider = "DuckDuckGo"
    fallback_used = False

    # 1. Google Custom Search (only if provider status is AVAILABLE)
    if _PROVIDER_STATUS.get("google"):
        print(f"[WEB DEBUG] HTTP request started: Google Custom Search API")
        results = search_google_custom(clean_query, num_results)
        if results:
            used_provider = "Google Custom Search"
            print(f"[WEB DEBUG] HTTP status: 200 OK (Google)")

    # 2. Serper API
    if not results and _PROVIDER_STATUS.get("serper"):
        print(f"[WEB DEBUG] HTTP request started: Serper Google Search API")
        results = search_serper(clean_query, num_results)
        if results:
            used_provider = "Serper Google Search"
            print(f"[WEB DEBUG] HTTP status: 200 OK (Serper)")

    # 3. Brave Search API
    if not results and _PROVIDER_STATUS.get("brave"):
        print(f"[WEB DEBUG] HTTP request started: Brave Search API")
        results = search_brave(clean_query, num_results)
        if results:
            used_provider = "Brave Search"
            print(f"[WEB DEBUG] HTTP status: 200 OK (Brave)")

    # 4. DuckDuckGo Fallback
    if not results:
        if requested_prov == "google":
            print(f"[WEB DEBUG] Google unavailable — falling back to DuckDuckGo")
            fallback_used = True
        print(f"[WEB DEBUG] HTTP request started: DuckDuckGo Fallback")
        results = search_duckduckgo(clean_query, num_results)
        used_provider = "DuckDuckGo"
        print(f"[WEB DEBUG] HTTP status: 200 OK (DuckDuckGo)")

    results_count = len(results) if results else 0
    print(f"[WEB DEBUG] Results received: {results_count}")
    if results and results_count > 0:
        print(f"[WEB DEBUG] First result URL: {results[0].get('url')}")

    success = bool(results and results_count > 0)
    print(f"[WEB DEBUG] Search completed: success={success}, live_search={success}")

    response_data = {
        "success": success,
        "live_search": success,
        "query": clean_query,
        "requested_provider": requested_prov,
        "provider": used_provider,
        "fallback_used": fallback_used,
        "results": results or [],
        "error": None if success else "No live search results found across providers"
    }

    if success:
        _search_cache.set(clean_query, response_data)

    return response_data


def format_search_results_with_sources(
    query: str,
    structured_data: Dict[str, Any],
    fetch_top_content: bool = False
) -> str:
    """
    Formats structured search results with title, snippet, source domains, and source URLs.
    """
    success   = structured_data.get("success", False)
    results   = structured_data.get("results", [])
    provider  = structured_data.get("provider", "Web")
    fallback  = structured_data.get("fallback_used", False)
    req_prov  = structured_data.get("requested_provider", "any")

    if not success or not results:
        return f"Live web search is currently unavailable for '{query}', sir."

    lines = []

    if fallback and req_prov == "google":
        lines.append("[WEB NOTICE] Google Search was unavailable, so DuckDuckGo fallback search was used.")

    lines.append(f"Web Search Results for '{query}' (via {provider}):\n")
    sources = []

    for i, r in enumerate(results, 1):
        title   = r.get("title", "")
        snippet = r.get("snippet", "")
        url     = r.get("url", "")
        source  = r.get("source", "")
        date    = r.get("date", "")

        date_str = f" [{date}]" if date else ""
        lines.append(f"[{i}] {title}{date_str}")
        if snippet:
            lines.append(f"    Snippet: {snippet}")
        if source:
            lines.append(f"    Source: {source} ({url})")
        lines.append("")

        if url and source:
            sources.append(f"• {source} — {url}")

    if fetch_top_content and results and results[0].get("url"):
        top_url = results[0]["url"]
        page_data = fetch_webpage(top_url, max_chars=2000)
        if page_data.get("success") and page_data.get("content"):
            lines.append("─" * 40)
            lines.append(f"Detailed Extract from {page_data.get('domain')}:")
            lines.append(page_data["content"])
            lines.append("─" * 40)

    if sources:
        lines.append("\nSources:")
        for s in sources[:5]:
            lines.append(s)

    return "\n".join(lines).strip()


def web_search(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    **kwargs
) -> str:
    """
    Central Web Search Tool handler registered in JARVIS ToolRegistry.
    Accepts query parameters, performs real search, logs Activity Log entries,
    and returns formatted content with sources.
    """
    params = parameters or kwargs or {}
    query  = (params.get("query") or params.get("search_query") or "").strip()
    num_res = int(params.get("num_results") or 5)
    fetch_page = bool(params.get("fetch_page") or False)

    if not query:
        return "Please specify what you would like me to search for on the web, sir."

    # UI Activity Log & State Transition
    if player and hasattr(player, "write_log"):
        player.write_log(f"[WEB] Searching: \"{query}\"")
    if player and hasattr(player, "set_state"):
        try:
            player.set_state("THINKING")
        except Exception:
            pass

    # Execute Real Search
    data = web_search_structured(query, num_results=num_res)
    results = data.get("results", [])
    provider = data.get("provider", "Web")
    req_prov = data.get("requested_provider", "any")

    if player and hasattr(player, "write_log"):
        if req_prov == "google":
            player.write_log(f"[WEB] Requested provider: Google")
        if data.get("fallback_used"):
            player.write_log(f"[WEB] Google unavailable — using DuckDuckGo fallback")
        player.write_log(f"[WEB] Provider used: {provider}")
        player.write_log(f"[WEB] Found {len(results)} results")

        if results and results[0].get("source"):
            player.write_log(f"[WEB] Reading: {results[0]['source']}")
        player.write_log("[WEB] Search complete")

    formatted_output = format_search_results_with_sources(query, data, fetch_top_content=fetch_page)
    return formatted_output
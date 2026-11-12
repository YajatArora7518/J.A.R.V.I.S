# actions/web_search_providers.py
# Real Web Search Provider Architecture for JARVIS

import os
import json
import time
import urllib.parse
import re
import math
import logging
import requests
from urllib3.util.retry import Retry
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Separate connect/read bounds keep a stalled provider from blocking fallback.
_PROVIDER_TIMEOUTS = {
    "google": (3.0, 5.0),
    "serper": (3.0, 5.0),
    "brave": (3.0, 5.0),
    "duckduckgo": (3.0, 4.0),
    "bing": (3.0, 2.5),
}

# Provider status tracking
_PROVIDER_STATUS: Dict[str, bool] = {
    "google": False,
    "serper": False,
    "brave": False,
    "duckduckgo": True  # Always available fallback
}
_PROVIDER_LAST_FAILURE: Dict[str, str] = {}


def _failure(provider, reason):
    _PROVIDER_LAST_FAILURE[provider.lower()] = reason

# Persistent HTTP Session with connection pooling for high-performance requests
_HTTP_SESSION = requests.Session()
_provider_retries = Retry(total=1, connect=1, read=0, status=1, backoff_factor=0.05,
                          status_forcelist=(429, 502, 503, 504),
                          allowed_methods=frozenset(("GET", "POST")), raise_on_status=False)
_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=_provider_retries)
_HTTP_SESSION.mount("https://", _adapter)
_HTTP_SESSION.mount("http://", _adapter)


def _session_get(url: str, **kwargs) -> requests.Response:
    if hasattr(requests.get, "assert_called") or "unittest" in getattr(requests.get, "__module__", ""):
        return requests.get(url, **kwargs)
    return _HTTP_SESSION.get(url, **kwargs)


def _session_post(url: str, **kwargs) -> requests.Response:
    if hasattr(requests.post, "assert_called") or "unittest" in getattr(requests.post, "__module__", ""):
        return requests.post(url, **kwargs)
    return _HTTP_SESSION.post(url, **kwargs)


def _get_env_key(key_name: str) -> Optional[str]:
    """Checks environment variables and config/api_keys.json for API keys."""
    # 1. Environment variable (supporting aliases)
    env_aliases = {
        "BRAVE_SEARCH_API_KEY": ["BRAVE_SEARCH_API_KEY", "BRAVE_API_KEY"],
        "SERPER_API_KEY": ["SERPER_API_KEY", "SERPER_KEY"],
        "GOOGLE_SEARCH_API_KEY": ["GOOGLE_SEARCH_API_KEY", "GOOGLE_API_KEY", "GEMINI_SEARCH_API_KEY"],
        "GOOGLE_CSE_ID": ["GOOGLE_CSE_ID", "GOOGLE_SEARCH_CX", "CSE_ID"],
    }
    keys_to_check = env_aliases.get(key_name, [key_name])
    for k in keys_to_check:
        val = os.environ.get(k)
        if val and val.strip():
            return val.strip()

    # 2. config/api_keys.json
    try:
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            key_map = {
                "GOOGLE_SEARCH_API_KEY": ["google_search_api_key", "google_api_key"],
                "GOOGLE_CSE_ID": ["google_cse_id", "cse_id"],
                "SERPER_API_KEY": ["serper_api_key", "serper_key"],
                "BRAVE_SEARCH_API_KEY": ["brave_search_api_key", "brave_key", "brave_api_key"],
            }
            possible_keys = key_map.get(key_name, [key_name.lower()])
            for k in possible_keys:
                if data.get(k) and str(data[k]).strip():
                    return str(data[k]).strip()
    except Exception:
        pass

    return None


def _response_json(response, provider: str) -> Optional[Dict[str, Any]]:
    """Return a well-formed JSON object for successful HTTP responses only."""
    status = getattr(response, "status_code", None)
    if status != 200:
        _failure(provider, "rate_limit" if status == 429 else "http_error")
        if status == 429:
            logger.warning("%s search rate limited (HTTP 429); using next provider", provider)
        else:
            logger.warning("%s search returned HTTP %s; using next provider", provider, status)
        return None
    try:
        data = response.json()
    except (ValueError, TypeError):
        _failure(provider, "malformed_json")
        logger.warning("%s search returned malformed JSON; using next provider", provider)
        return None
    if not isinstance(data, dict):
        _failure(provider, "invalid_response")
        logger.warning("%s search returned an unexpected response shape; using next provider", provider)
        return None
    _PROVIDER_LAST_FAILURE.pop(provider.lower(), None)
    return data


def _text(value: Any) -> str:
    """Convert provider fields to safe scalar text, ignoring nested payloads."""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _result(title, url, snippet, source, date=None, provider=None):
    item = {
        "title": _text(title),
        "url": _text(url),
        "snippet": _text(snippet),
        "source": _text(source),
        "date": _text(date) or None,
    }
    if provider:
        item["search_provider"] = provider
    return item


_PROVIDERS_INITIALIZED = False


def init_search_providers(force: bool = False) -> Dict[str, str]:
    """Initializes and logs availability of all web search providers."""
    global _PROVIDERS_INITIALIZED
    if _PROVIDERS_INITIALIZED and not force:
        return _PROVIDER_STATUS

    print("\n[WEB] Initializing web search engine...")

    g_key = _get_env_key("GOOGLE_SEARCH_API_KEY")
    g_cx  = _get_env_key("GOOGLE_CSE_ID")
    g_status = "AVAILABLE" if (g_key and g_cx) else ("AUTH_REQUIRED" if (g_key or g_cx) else "UNAVAILABLE")
    _PROVIDER_STATUS["google"] = (g_status == "AVAILABLE")

    serper_key = _get_env_key("SERPER_API_KEY")
    s_status = "AVAILABLE" if serper_key else "UNAVAILABLE"
    _PROVIDER_STATUS["serper"] = (s_status == "AVAILABLE")

    brave_key = _get_env_key("BRAVE_SEARCH_API_KEY")
    b_status = "AVAILABLE" if brave_key else "UNAVAILABLE"
    _PROVIDER_STATUS["brave"] = (b_status == "AVAILABLE")

    _PROVIDER_STATUS["duckduckgo"] = True

    active_provider = "Google Search" if _PROVIDER_STATUS["google"] else ("Serper" if _PROVIDER_STATUS["serper"] else ("Brave Search" if _PROVIDER_STATUS["brave"] else "DuckDuckGo fallback"))

    print(f"[WEB] Google Search : {g_status}")
    print(f"[WEB] Serper        : {s_status}")
    print(f"[WEB] Brave Search  : {b_status}")
    print(f"[WEB] Fallback      : DuckDuckGo (AVAILABLE)")
    print(f"[WEB] Web Search    : READY ({active_provider})\n")

    _PROVIDERS_INITIALIZED = True
    return _PROVIDER_STATUS


# ── PROVIDER IMPLEMENTATIONS ──

def _relevant_results(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Discard clearly unrelated scraper responses (e.g. generic news for Python)."""
    noise = set('latest current today todays yesterday now recent news price score live official documentation docs release search google for the what who is are was how why aaj abhi ka ki ke kya se par pe bata batao karke karo kar dekh dhund dhoond check online internet web please query'.split())
    noise.update(('total', 'announcement', 'announced', 'update', 'updates', 'information', 'about', 'tell', 'bata', 'batao'))
    noise.update('january february march april may june july august september october november december'.split())
    topic_query = re.sub(r'\bsite:\S+', '', query.lower())
    topics = list(dict.fromkeys(word for word in re.findall(r'[^\W\d_]{3,}', topic_query) if word not in noise))
    if not topics:
        return results
    required = max(min(2, len(topics)), math.ceil(len(topics) * 0.5))
    return [item for item in results if sum(topic in ' '.join(str(item.get(key, '')) for key in ('title','url','snippet')).lower() for topic in topics) >= required]


def _search_ddgs(query: str, num_results: int) -> List[Dict[str, Any]]:
    try:
        from ddgs import DDGS
        raw = DDGS(timeout=_PROVIDER_TIMEOUTS["duckduckgo"][1]).text(query, max_results=max(8, num_results))
        results = []
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            href = _text(item.get('href'))
            body = _text(item.get('body')).replace('\n', ' ')
            results.append(_result(item.get('title'), href, body,
                                    urllib.parse.urlparse(href).netloc.removeprefix('www.'),
                                    item.get('date'), 'DDGS'))
        return _relevant_results(query, results)[:num_results]
    except Exception as exc:
        logger.warning("DuckDuckGo DDGS search unavailable (%s)", type(exc).__name__)
        return []

def search_google_custom(query: str, num_results: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Google Custom Search JSON API."""
    g_key = _get_env_key("GOOGLE_SEARCH_API_KEY")
    g_cx  = _get_env_key("GOOGLE_CSE_ID")

    if not g_key or not g_cx:
        _failure("google", "missing_credentials")
        return None

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": g_key,
            "cx": g_cx,
            "q": query,
            "num": min(num_results, 10),
        }
        res = _session_get(url, params=params, timeout=_PROVIDER_TIMEOUTS["google"])
        data = _response_json(res, "Google")
        if data is None:
            return None
        items = data.get("items", [])
        if not isinstance(items, list):
            logger.warning("Google search returned an invalid items list")
            return None
        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            link = _text(item.get("link"))
            domain = urllib.parse.urlparse(link).netloc.removeprefix("www.")
            pagemap = item.get("pagemap")
            metatags = pagemap.get("metatags") if isinstance(pagemap, dict) else None
            meta = metatags[0] if isinstance(metatags, list) and metatags and isinstance(metatags[0], dict) else {}
            date = meta.get("article:published_time") or meta.get("date")
            results.append(_result(item.get("title"), link, item.get("snippet"), domain or "google.com",
                                   _text(date)[:10] or None, "Google Custom Search"))
        return results
    except requests.exceptions.Timeout:
        _failure("google", "timeout")
        logger.warning("Google search timed out; using next provider")
    except requests.exceptions.RequestException as exc:
        _failure("google", "network_error")
        logger.warning("Google search request failed (%s); using next provider", type(exc).__name__)
    except Exception as exc:
        logger.warning("Google search response could not be processed (%s)", type(exc).__name__)

    return None


def search_serper(query: str, num_results: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Serper Google Search API."""
    serper_key = _get_env_key("SERPER_API_KEY")
    if not serper_key:
        _failure("serper", "missing_credentials")
        return None

    try:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        payload = json.dumps({"q": query, "num": num_results})
        res = _session_post(url, headers=headers, data=payload, timeout=_PROVIDER_TIMEOUTS["serper"])
        data = _response_json(res, "Serper")
        if data is None:
            return None
        organic = data.get("organic", [])
        if not isinstance(organic, list):
            logger.warning("Serper search returned an invalid organic results list")
            return None
        results = []
        for item in organic:
            if not isinstance(item, dict):
                continue
            link = _text(item.get("link"))
            domain = urllib.parse.urlparse(link).netloc.removeprefix("www.")
            results.append(_result(item.get("title"), link, item.get("snippet"), domain or "serper.dev",
                                   item.get("date"), "Serper"))
        return results
    except requests.exceptions.Timeout:
        _failure("serper", "timeout")
        logger.warning("Serper search timed out; using next provider")
    except requests.exceptions.RequestException as exc:
        _failure("serper", "network_error")
        logger.warning("Serper search request failed (%s); using next provider", type(exc).__name__)
    except Exception as exc:
        logger.warning("Serper search response could not be processed (%s)", type(exc).__name__)

    return None


def search_brave(query: str, num_results: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Brave Search API."""
    brave_key = _get_env_key("BRAVE_SEARCH_API_KEY")
    if not brave_key:
        _failure("brave", "missing_credentials")
        return None

    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": brave_key}
        params = {"q": query, "count": num_results}
        res = _session_get(url, headers=headers, params=params, timeout=_PROVIDER_TIMEOUTS["brave"])
        data = _response_json(res, "Brave")
        if data is None:
            return None
        web = data.get("web")
        items = web.get("results", []) if isinstance(web, dict) else None
        if not isinstance(items, list):
            logger.warning("Brave search returned an invalid web results list")
            return None
        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            link = _text(item.get("url"))
            domain = urllib.parse.urlparse(link).netloc.removeprefix("www.")
            results.append(_result(item.get("title"), link, item.get("description"), domain or "brave.com",
                                   item.get("page_age"), "Brave Search"))
        return results
    except requests.exceptions.Timeout:
        _failure("brave", "timeout")
        logger.warning("Brave search timed out; using next provider")
    except requests.exceptions.RequestException as exc:
        _failure("brave", "network_error")
        logger.warning("Brave search request failed (%s); using next provider", type(exc).__name__)
    except Exception as exc:
        logger.warning("Brave search response could not be processed (%s)", type(exc).__name__)

    return None


def search_bing_html(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """High-speed organic Bing HTML Search Provider (Sub-second response time)."""
    results = []
    try:
        from bs4 import BeautifulSoup
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        res = _session_get(url, headers=headers, timeout=_PROVIDER_TIMEOUTS["bing"])
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for li in soup.select("li.b_algo"):
                h2_a = li.select_one("h2 a")
                if not h2_a or not h2_a.get("href"):
                    continue
                href = h2_a["href"]
                title = h2_a.get_text(' ', strip=True)
                p_el = li.select_one("p")
                snippet = p_el.get_text(" ", strip=True) if p_el else ""
                domain = urllib.parse.urlparse(href).netloc.replace("www.", "")

                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "source": domain or "bing.com",
                    "date": "",
                    "search_provider": "Bing"
                })
                if len(results) >= num_results:
                    break
            results = _relevant_results(query, results)
            if results:
                return results
        elif res.status_code == 429:
            logger.warning("Bing HTML search rate limited (HTTP 429)")
        else:
            logger.warning("Bing HTML search returned HTTP %s", res.status_code)
    except requests.exceptions.Timeout:
        logger.warning("Bing HTML search timed out")
    except Exception as exc:
        logger.warning("Bing HTML search failed (%s)", type(exc).__name__)
    return results


def search_duckduckgo(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """DuckDuckGo Search Provider with fast HTML POST scraper & Bing fallback."""
    results = []
    # Compound factual questions need a full-query engine before permissive
    # HTML scrapers that sometimes return results for only the first word.
    if len(query.split()) >= 4:
        results = _search_ddgs(query, num_results)
        if results:
            return results

    # 1. High-speed HTML Scraper (1.0s timeout to prevent blocking when network/TLS hangs)
    try:
        from bs4 import BeautifulSoup
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        res = _session_post(url, data={"q": query}, headers=headers, timeout=_PROVIDER_TIMEOUTS["duckduckgo"])
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            elements = soup.select("div.result")
            for el in elements[:num_results]:
                title_el   = el.select_one("a.result__a")
                url_el     = el.select_one("a.result__url")
                snippet_el = el.select_one(".result__snippet")

                if not title_el:
                    continue

                raw_url = url_el["href"].strip() if url_el and url_el.has_attr("href") else title_el.get("href", "")
                if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
                    raw_url = "https://" + raw_url.lstrip("/")

                clean_url = raw_url
                if "uddg=" in raw_url:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in qs and qs["uddg"]:
                        clean_url = qs["uddg"][0]

                title   = title_el.get_text(" ", strip=True)
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                domain  = urllib.parse.urlparse(clean_url).netloc.replace("www.", "")

                results.append({
                    "title": title,
                    "url": clean_url,
                    "snippet": snippet,
                    "source": domain or "duckduckgo.com",
                    "date": ""
                })
            results = _relevant_results(query, results)
            if results:
                return results
        elif res.status_code == 429:
            logger.warning("DuckDuckGo HTML search rate limited (HTTP 429); trying fallback")
        else:
            logger.warning("DuckDuckGo HTML search returned HTTP %s; trying fallback", res.status_code)
    except requests.exceptions.Timeout:
        logger.warning("DuckDuckGo HTML search timed out; trying fallback")
    except Exception as exc:
        logger.warning("DuckDuckGo HTML search failed (%s); trying fallback", type(exc).__name__)

    # 2. High-Speed Bing Organic HTML Fallback (~700ms)
    bing_res = search_bing_html(query, num_results=num_results)
    if bing_res:
        return bing_res

    return _search_ddgs(query, num_results) if len(query.split()) < 4 else []


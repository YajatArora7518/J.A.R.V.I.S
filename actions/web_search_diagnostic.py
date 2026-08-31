# actions/web_search_diagnostic.py
# Real Web Search Diagnostic & Live Network Test Suite for JARVIS

import sys
import urllib.parse
import requests
from typing import Dict, Any

def run_web_search_diagnostic() -> bool:
    """Runs structural diagnostic check."""
    print("\n=============================================")
    print("        JARVIS WEB SEARCH DIAGNOSTIC")
    print("=============================================")

    # 1. Provider initialization
    try:
        from actions.web_search_providers import init_search_providers, _PROVIDER_STATUS
        status = init_search_providers()
        p1 = "PASS"
    except Exception as e:
        p1 = f"FAIL ({e})"

    # 2. Real search execution
    try:
        from actions.web_search import web_search_structured, format_search_results_with_sources
        data = web_search_structured("latest NVIDIA RTX 5070 price India", num_results=3)
        results = data.get("results", [])
        p2 = "PASS" if results else "FAIL (No results returned)"
    except Exception as e:
        data = {}
        results = []
        p2 = f"FAIL ({e})"

    # 3. Result parsing
    try:
        if results and "title" in results[0] and "url" in results[0]:
            p3 = "PASS"
        else:
            p3 = "FAIL (Invalid result schema)"
    except Exception as e:
        p3 = f"FAIL ({e})"

    # 4. Webpage fetching
    try:
        from actions.fetch_webpage import fetch_webpage
        target_urls = [r["url"] for r in results if r.get("url")] + ["https://www.python.org", "https://en.wikipedia.org"]
        page = {}
        for tu in target_urls:
            page = fetch_webpage(tu, max_chars=500)
            if page.get("success") and page.get("content"):
                break
        p4 = "PASS" if page.get("success") and page.get("content") else f"FAIL ({page.get('error')})"
    except Exception as e:
        p4 = f"FAIL ({e})"

    # 5. Tool Registry integration
    try:
        from core.tool_registry import default_tool_registry
        from core.register_tools import initialize_all_tools
        initialize_all_tools()
        has_tool = "web_search" in default_tool_registry._tools and "fetch_webpage" in default_tool_registry._tools
        p5 = "PASS" if has_tool else "FAIL (Tools not in registry)"
    except Exception as e:
        p5 = f"FAIL ({e})"

    # 6. Source extraction
    try:
        formatted = format_search_results_with_sources("latest NVIDIA RTX 5070 price India", data)
        p6 = "PASS" if ("Sources:" in formatted or "via" in formatted) else "FAIL"
    except Exception as e:
        p6 = f"FAIL ({e})"

    print(f"[WEB TEST] Provider initialization ........ {p1}")
    print(f"[WEB TEST] Google/fallback search ........ {p2}")
    print(f"[WEB TEST] Result parsing ................ {p3}")
    print(f"[WEB TEST] Webpage fetching .............. {p4}")
    print(f"[WEB TEST] Tool Registry integration .... {p5}")
    print(f"[WEB TEST] Source extraction ............. {p6}")
    print("=============================================")

    all_ok = (p1 == "PASS" and p2 == "PASS" and p4 == "PASS" and p5 == "PASS")
    if all_ok:
        print(" RESULT: WEB SEARCH ENGINE OPERATIONAL")
    else:
        print(" RESULT: WEB SEARCH ENGINE DIAGNOSTIC ISSUES DETECTED")
    print("=============================================\n")
    return all_ok


def run_web_search_live_test() -> bool:
    """Executes a REAL live network search test for OpenAI official website."""
    print("\n=============================================")
    print("        JARVIS LIVE WEB SEARCH TEST")
    print("=============================================")

    # 1. Internet connectivity check
    try:
        res = requests.get("https://www.google.com", timeout=4)
        t1 = "PASS" if res.status_code == 200 else f"FAIL ({res.status_code})"
    except Exception as e:
        t1 = f"FAIL ({e})"

    # 2. Search Provider check
    try:
        from actions.web_search_providers import init_search_providers
        status = init_search_providers()
        active_prov = [k for k, v in status.items() if v]
        t2 = f"PASS ({', '.join(active_prov)})" if active_prov else "FAIL (No active search provider)"
    except Exception as e:
        t2 = f"FAIL ({e})"

    # 3. Real search request for 'OpenAI official website'
    try:
        from actions.web_search import web_search_structured, format_search_results_with_sources
        query = "OpenAI official website"
        data = web_search_structured(query, num_results=3)
        results = data.get("results", [])
        t3 = f"PASS (Found {len(results)} results via {data.get('provider')})" if results else "FAIL (Zero search results returned)"
    except Exception as e:
        data = {}
        results = []
        t3 = f"FAIL ({e})"

    # 4. Valid URLs check
    try:
        valid_urls = [r["url"] for r in results if r.get("url") and r["url"].startswith("http")]
        t4 = f"PASS (Valid URL: {valid_urls[0]})" if valid_urls else "FAIL (No valid HTTP/HTTPS URLs)"
    except Exception as e:
        t4 = f"FAIL ({e})"

    # 5. Source extraction check
    try:
        formatted = format_search_results_with_sources(query, data)
        t5 = "PASS" if "Sources:" in formatted else "FAIL"
    except Exception as e:
        t5 = f"FAIL ({e})"

    # 6. Webpage fetching test
    try:
        from actions.fetch_webpage import fetch_webpage
        target_url = valid_urls[0] if valid_urls else "https://www.python.org"
        page = fetch_webpage(target_url, max_chars=400)
        t6 = f"PASS (Fetched {page.get('length', 0)} chars from {page.get('domain')})" if page.get("success") else f"FAIL ({page.get('error')})"
    except Exception as e:
        t6 = f"FAIL ({e})"

    # 7. Live search flag check
    try:
        is_live = bool(data.get("live_search")) and bool(data.get("success"))
        t7 = "PASS (live_search=True)" if is_live else "FAIL (live_search=False)"
    except Exception as e:
        t7 = f"FAIL ({e})"

    # 8. Tool Registry integration check
    try:
        from core.tool_registry import default_tool_registry
        from core.register_tools import initialize_all_tools
        initialize_all_tools()
        has_tools = "web_search" in default_tool_registry._tools and "fetch_webpage" in default_tool_registry._tools
        t8 = "PASS" if has_tools else "FAIL"
    except Exception as e:
        t8 = f"FAIL ({e})"

    # 9. Gemini tool declaration check
    try:
        from main import TOOL_DECLARATIONS
        has_decl = any(t.get("name") == "web_search" for t in TOOL_DECLARATIONS)
        t9 = "PASS" if has_decl else "FAIL"
    except Exception as e:
        t9 = f"FAIL ({e})"

    print(f"[TEST] Internet connectivity ........ {t1}")
    print(f"[TEST] Search provider ............... {t2}")
    print(f"[TEST] Real results returned ......... {t3}")
    print(f"[TEST] Valid URLs .................... {t4}")
    print(f"[TEST] Source extraction ............. {t5}")
    print(f"[TEST] Webpage fetching .............. {t6}")
    print(f"[TEST] Live search flag .............. {t7}")
    print(f"[TEST] Tool registration ............ {t8}")
    print(f"[TEST] Gemini tool declaration ...... {t9}")
    print("=============================================")

    all_passed = all(x.startswith("PASS") for x in [t1, t3, t4, t5, t6, t7, t8, t9])
    if all_passed:
        print(" RESULT: REAL WEB SEARCH OPERATIONAL")
    else:
        print(" RESULT: REAL WEB SEARCH TEST FAILED")
    print("=============================================\n")
    return all_passed

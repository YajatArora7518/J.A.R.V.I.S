"""Stage 2 provider failure, fallback, and compatibility checks."""
from unittest.mock import MagicMock, patch

import requests


def _response(status=200, payload=None, text=""):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.text = text
    return response


def test_empty_serper_key_skips_authenticated_request():
    from actions.web_search_providers import search_serper

    with patch("actions.web_search_providers._get_env_key", return_value=None), \
         patch("actions.web_search_providers._session_post") as post:
        assert search_serper("test") is None
    post.assert_not_called()


def test_serper_valid_mock_response_and_timeout_are_bounded():
    from actions.web_search_providers import search_serper

    payload = {"organic": [{"title": "Example", "link": "https://example.org/a",
                            "snippet": "A result", "date": "2026-11-01"}]}
    with patch("actions.web_search_providers._get_env_key", return_value="test-key"), \
         patch("actions.web_search_providers._session_post", return_value=_response(payload=payload)) as post:
        result = search_serper("test")
    assert result[0]["title"] == "Example"
    assert result[0]["date"] == "2026-11-01"
    assert post.call_args.kwargs["timeout"] == (3.0, 5.0)


def test_brave_accepts_both_environment_variable_names():
    import os
    from actions.web_search_providers import _get_env_key

    for name in ("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"):
        with patch.dict(os.environ, {name: "brave-test-key"}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            assert _get_env_key("BRAVE_SEARCH_API_KEY") == "brave-test-key"


def test_google_missing_credentials_skips_request():
    from actions.web_search_providers import search_google_custom

    with patch("actions.web_search_providers._get_env_key", return_value=None), \
         patch("actions.web_search_providers._session_get") as get:
        assert search_google_custom("test") is None
    get.assert_not_called()


def test_google_malformed_json_fails_safely():
    from actions.web_search_providers import search_google_custom

    response = _response()
    response.json.side_effect = ValueError("invalid json")
    with patch("actions.web_search_providers._get_env_key", side_effect=["key", "cx"]), \
         patch("actions.web_search_providers._session_get", return_value=response):
        assert search_google_custom("test") is None


def test_serper_timeout_and_rate_limit_are_handled():
    from actions.web_search_providers import search_serper

    with patch("actions.web_search_providers._get_env_key", return_value="test-key"), \
         patch("actions.web_search_providers._session_post", side_effect=requests.Timeout):
        assert search_serper("test") is None
    with patch("actions.web_search_providers._get_env_key", return_value="test-key"), \
         patch("actions.web_search_providers._session_post", return_value=_response(status=429)):
        assert search_serper("test") is None


def test_invalid_serper_shape_returns_none():
    from actions.web_search_providers import search_serper

    with patch("actions.web_search_providers._get_env_key", return_value="test-key"), \
         patch("actions.web_search_providers._session_post", return_value=_response(payload={"organic": {"bad": "shape"}})):
        assert search_serper("test") is None


def test_duckduckgo_html_result_is_parsed_with_expected_fields():
    from actions.web_search_providers import search_duckduckgo

    html = '''<div class="result"><a class="result__a" href="https://example.org/page">Example <b>result</b></a>
        <a class="result__url" href="https://example.org/page">example.org</a>
        <a class="result__snippet">Useful <b>search</b> snippet</a></div>'''
    with patch("actions.web_search_providers._search_ddgs", return_value=[]), \
         patch("actions.web_search_providers._session_post", return_value=_response(text=html)), \
         patch("actions.web_search_providers.search_bing_html", return_value=[]):
        result = search_duckduckgo("example result", 2)
    assert result and result[0]["url"] == "https://example.org/page"
    assert result[0]["title"] == "Example result"
    assert result[0]["snippet"] == "Useful search snippet"


def test_cascade_continues_after_unavailable_providers_and_browser_fallback():
    from actions.web_search import web_search_structured, _search_cache

    _search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": True, "serper": True,
                                                              "brave": True, "duckduckgo": True}), \
         patch("actions.web_search.search_google_custom", return_value=None), \
         patch("actions.web_search.search_serper", return_value=None), \
         patch("actions.web_search.search_brave", return_value=None), \
         patch("actions.web_search.search_duckduckgo", return_value=[]), \
         patch("actions.browser_search.search_in_browser", return_value=[{
             "title": "Browser result", "url": "https://example.org/page", "snippet": "Text"
         }]):
        result = web_search_structured("provider cascade fixture", force_refresh=True)
    assert result["success"] and result["provider"] == "Browser Google"
    assert result["fallback_used"]


def test_duckduckgo_is_zero_cost_fallback_after_paid_providers_fail():
    from actions.web_search import web_search_structured, _search_cache

    _search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": True, "serper": True,
                                                              "brave": True, "duckduckgo": True}), \
         patch("actions.web_search.search_google_custom", return_value=None), \
         patch("actions.web_search.search_serper", return_value=None), \
         patch("actions.web_search.search_brave", return_value=None), \
         patch("actions.web_search.search_duckduckgo", return_value=[{
             "title": "DDG result", "url": "https://example.org/ddg", "snippet": "Text"
         }]):
        result = web_search_structured("fallback fixture", force_refresh=True)
    assert result["provider"] == "DuckDuckGo" and result["fallback_used"]


def test_requested_google_fallback_is_reported_when_serper_answers():
    from actions.web_search import web_search_structured, _search_cache

    _search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": False, "serper": True,
                                                              "brave": False, "duckduckgo": True}), \
         patch("actions.web_search.search_serper", return_value=[{
             "title": "Serper result", "url": "https://example.org/serper", "snippet": "Text"
         }]):
        result = web_search_structured("google latest fixture", preferred_provider="google", force_refresh=True)
    assert result["provider"] == "Serper Google Search" and result["fallback_used"]


def test_all_search_providers_unavailable_returns_structured_failure():
    from actions.web_search import web_search_structured, _search_cache

    _search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": True, "serper": True,
                                                              "brave": True, "duckduckgo": True}), \
         patch("actions.web_search.search_google_custom", return_value=None), \
         patch("actions.web_search.search_serper", return_value=None), \
         patch("actions.web_search.search_brave", return_value=None), \
         patch("actions.web_search.search_duckduckgo", return_value=[]), \
         patch("actions.browser_search.search_in_browser", return_value=[]):
        result = web_search_structured("all providers unavailable", force_refresh=True)
    assert not result["success"] and result["results"] == []


def test_malformed_rows_and_duplicate_urls_are_dropped_and_normalized():
    from actions.web_search import web_search_structured, _search_cache

    _search_cache._cache.clear()
    rows = ["bad row", {"title": "A", "url": "https://example.org/page#top", "snippet": "Text"},
            {"title": "Duplicate", "url": "https://example.org/page/", "snippet": "Other"}]
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": False, "serper": False,
                                                              "brave": False, "duckduckgo": True}), \
         patch("actions.web_search.search_duckduckgo", return_value=rows):
        result = web_search_structured("normalize fixture", force_refresh=True)
    assert result["success"] and len(result["results"]) == 1
    row = result["results"][0]
    assert set(("title", "url", "snippet", "source", "date")).issubset(row)
    assert row["source"] == "example.org" and row["date"] is None


def test_internal_bing_fallback_is_reported_as_a_fallback():
    from actions.web_search import web_search_structured, _search_cache
    _search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": False, "serper": False,
                                                              "brave": False, "duckduckgo": True}), \
         patch("actions.web_search.search_duckduckgo", return_value=[{
             "title":"Python", "url":"https://www.python.org/", "snippet":"Official", "search_provider":"Bing"}]):
        result = web_search_structured("fallback fixture", force_refresh=True)
    assert result["success"] and result["provider"] == "Bing" and result["fallback_used"]


def test_search_failure_does_not_hit_unbound_answer_path():
    from actions.web_search import web_search_tool

    failure = {"success": False, "results": [], "error": "unavailable"}
    with patch("actions.web_search.web_search_structured", return_value=failure), \
         patch("actions.web_research.answer_from_pages") as answer:
        result = web_search_tool({"query": "latest fixture result"})
    assert not result["success"]
    answer.assert_not_called()


def test_web_research_receives_compatible_normalized_result():
    from actions.web_search import web_search_tool, _search_cache

    _search_cache._cache.clear()
    source = [{"title": "Source title", "url": "https://example.org/source",
               "snippet": "Evidence", "date": None}]
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google": False, "serper": False,
                                                              "brave": False, "duckduckgo": True}), \
         patch("actions.web_search.search_duckduckgo", return_value=source), \
         patch("actions.web_research.answer_from_pages", return_value={"success": True, "verified": True}) as answer:
        result = web_search_tool({"query": "historical source question"})
    assert result["verified"]
    passed = answer.call_args.args[1]["results"][0]
    assert passed["title"] == "Source title" and passed["date"] is None
    assert passed["source"] == "example.org"


def test_search_tool_registration_remains_present():
    from core.register_tools import default_tool_registry

    tool = default_tool_registry.get_tool("web_search")
    assert tool is not None and tool.execute_func is not None
    assert len(default_tool_registry.list_tools()) == 73


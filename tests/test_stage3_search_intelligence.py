"""Offline Stage 3 checks for search ranking, freshness metadata, and evidence extraction."""
import pytest


def test_official_sources_rank_before_secondary_sources_and_keep_metadata():
    from actions.web_search import _normalize_search_results
    rows = _normalize_search_results([
        {"title": "Article", "url": "https://example.net/story", "snippet": "text", "date": "2026-10-01", "legacy": "kept"},
        {"title": "Official", "url": "https://www.icc-cricket.com/news", "snippet": "official"},
    ], 5)
    assert rows[0]["source"] == "icc-cricket.com"
    assert rows[0]["date"] is None
    assert rows[1]["legacy"] == "kept"


def test_duplicate_urls_are_removed_without_dropping_first_result():
    from actions.web_search import _normalize_search_results
    rows = _normalize_search_results([
        {"title": "A", "url": "https://example.org/path#first", "snippet": "one"},
        {"title": "Duplicate", "url": "https://example.org/path#other", "snippet": "two"}], 5)
    assert len(rows) == 1 and rows[0]["title"] == "A"


def test_html_table_extraction_is_bounded_and_keeps_cells():
    from bs4 import BeautifulSoup
    from actions.fetch_webpage import _extract_html_tables
    soup = BeautifulSoup('<table><caption>Standings</caption><tr><th>Rank</th><th>Team</th><th>Points</th></tr>'
                         '<tr><td>1</td><td>Example</td><td>42</td></tr></table>', 'html.parser')
    table = _extract_html_tables(soup)[0]
    assert table["caption"] == "Standings" and table["kind"] == "standings"
    assert table["rank_column"] == 0 and table["entity_column"] == 1 and table["points_column"] == 2
    assert table["rows"] == [["Rank", "Team", "Points"], ["1", "Example", "42"]]


def test_page_metadata_keeps_publication_update_event_and_retrieval_distinct(monkeypatch):
    from actions import fetch_webpage
    from actions.web_research import _freshness_metadata

    class Response:
        status_code = 200
        encoding = "utf-8"
        headers = {}
        def iter_content(self, chunk_size):
            yield (b'<html><head><title>Standings</title><meta property="article:published_time" '
                   b'content="2026-11-02T10:00:00Z"><meta property="article:modified_time" '
                   b'content="2026-11-05T12:00:00Z"></head><body><table><tr><th>Rank</th><th>Team</th>'
                   b'<th>Points</th></tr><tr><td>1</td><td>Example</td><td>42</td></tr></table>'
                   b'<article>Event day was November 1.</article></body></html>')
        def raise_for_status(self): pass
        def close(self): pass
    monkeypatch.setattr(fetch_webpage, "_check_public_url", lambda url: None)
    monkeypatch.setattr(fetch_webpage, "_session_get", lambda *a, **k: Response())
    data = fetch_webpage.fetch_webpage("https://example.org/standings")
    assert data["published_at"] == "2026-11-02T10:00:00Z"
    assert data["updated_at"] == "2026-11-05T12:00:00Z"
    assert data["event_date"] is None and data["retrieved_at"]
    assert data["tables"][0]["rows"][1] == ["1", "Example", "42"]
    assert "1 | Example | 42" in data["content"]
    metadata = _freshness_metadata(data)
    assert metadata["published_date"].startswith("2026-11-02")
    assert metadata["updated_date"].startswith("2026-11-05")
    assert metadata["event_date"] is None and metadata["retrieval_time"] == data["retrieved_at"]


@pytest.mark.parametrize("query", ["Latest FFWS rankings", "FFWS Week 1 Day 1 standings",
                                    "TSG ke points kitne the?", "India ke current cricket results"])
def test_sports_and_esports_lookup_phrasing_routes_to_existing_search_tool(query):
    from core.intent_router import classify_intent
    intent = classify_intent(query)
    assert intent["intent"] == "WEB_SEARCH" and intent["tool"] == "web_search"


def test_provider_health_circuit_is_bounded_and_reports_failure_type(monkeypatch):
    from actions import web_search
    monkeypatch.setattr(web_search, "_PROVIDER_HEALTH", {})
    def broken(*args): raise TimeoutError("private detail not logged")
    for _ in range(web_search._PROVIDER_FAILURE_LIMIT):
        assert web_search._provider_search("fixture-provider", broken, "q", 2) is None
    status = web_search.get_search_provider_health()["fixture-provider"]
    assert status["state"] == "open" and status["cooldown_seconds"] <= web_search._PROVIDER_COOLDOWN_SECONDS
    assert status["last_error"] == "TimeoutError"
    assert web_search._provider_search("fixture-provider", lambda *args: pytest.fail("open circuit called provider"), "q", 2) is None


def test_http_provider_retries_are_bounded_and_read_retries_disabled():
    from actions.web_search_providers import _provider_retries
    assert _provider_retries.total == 1
    assert _provider_retries.connect == 1 and _provider_retries.read == 0 and _provider_retries.status == 1


def test_configured_provider_is_attempted_first(tmp_path, monkeypatch):
    from actions import search_preferences as prefs, web_search
    from unittest.mock import patch
    monkeypatch.setattr(prefs, "_CONFIG", tmp_path / "prefs.json")
    prefs.update_search_preferences(global_settings={"preferred_provider":"brave"})
    web_search._search_cache._cache.clear()
    with patch.dict("actions.web_search._PROVIDER_STATUS", {"google":True,"serper":True,"brave":True,"duckduckgo":True}), \
         patch("actions.web_search.search_brave", return_value=[{"title":"Brave source","url":"https://example.org/a","snippet":"text"}]) as brave, \
         patch("actions.web_search.search_google_custom") as google, patch("actions.web_search.search_serper") as serper:
        result = web_search.web_search_structured("provider preference test", force_refresh=True)
    assert result["provider"] == "Brave Search" and brave.call_count == 1
    google.assert_not_called(); serper.assert_not_called()

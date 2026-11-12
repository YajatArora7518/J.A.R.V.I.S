"""Offline regression tests for JARVIS-managed browser search preferences."""
import json

import pytest


def _store(tmp_path, monkeypatch):
    from actions import search_preferences as prefs
    monkeypatch.setattr(prefs, "_CONFIG", tmp_path / "search_preferences.json")
    return prefs


@pytest.mark.parametrize("browser,engine", [
    ("chrome", "google"), ("edge", "bing"), ("firefox", "duckduckgo"), ("brave", "brave")])
def test_browser_engines_resolve_independently(tmp_path, monkeypatch, browser, engine):
    prefs = _store(tmp_path, monkeypatch)
    prefs.update_search_preferences(browser_settings={browser: {"default_engine": engine}})
    assert prefs.resolve_search_engine(browser=browser)[0] == engine
    assert prefs.resolve_search_engine(browser="chrome")[0] == ("google" if browser != "chrome" else engine)


def test_global_update_does_not_override_explicit_browser_choice(tmp_path, monkeypatch):
    prefs = _store(tmp_path, monkeypatch)
    prefs.update_search_preferences(browser_settings={"chrome": {"default_engine": "bing"}})
    prefs.update_search_preferences(global_settings={"default_engine": "duckduckgo"})
    assert prefs.resolve_search_engine(browser="chrome")[0] == "bing"
    assert prefs.resolve_search_engine(browser="edge")[0] == "duckduckgo"
    prefs.reset_browser_to_global("chrome")
    assert prefs.resolve_search_engine(browser="chrome")[0] == "duckduckgo"


def test_custom_template_and_site_search_are_encoded_and_validated(tmp_path, monkeypatch):
    prefs = _store(tmp_path, monkeypatch)
    prefs.update_search_preferences(custom_engines={"site_docs": {"name": "Docs", "url": "https://docs.example.org/search?q={query}"}})
    assert prefs.build_search_url("hello world & more", browser="chrome", explicit_engine="site_docs") == \
        "https://docs.example.org/search?q=hello+world+%26+more"
    with pytest.raises(ValueError): prefs.validate_search_url_template("javascript:alert(1)?q={query}")
    with pytest.raises(ValueError): prefs.validate_search_url_template("https://127.0.0.1/?q={query}")


def test_custom_url_and_missing_engine_errors(tmp_path, monkeypatch):
    prefs = _store(tmp_path, monkeypatch)
    prefs.update_search_preferences(browser_settings={"edge": {"custom_url": "https://example.org/?q={query}"}})
    assert prefs.build_search_url("x", browser="edge") == "https://example.org/?q=x"
    with pytest.raises(ValueError): prefs.build_search_url("x", browser="edge", explicit_engine="missing")
    with pytest.raises(ValueError): prefs.resolve_search_engine(browser="not-installed")


def test_corrupt_configuration_recovers_defaults_and_preserves_corrupt_file(tmp_path, monkeypatch):
    prefs = _store(tmp_path, monkeypatch)
    prefs._CONFIG.write_text('{bad json', encoding="utf-8")
    assert prefs.resolve_search_engine(browser="chrome")[0] == "google"
    prefs.update_search_preferences(global_settings={"default_engine": "bing"})
    assert prefs._CONFIG.with_suffix(".json.corrupt").read_text(encoding="utf-8") == "{bad json"
    assert json.loads(prefs._CONFIG.read_text(encoding="utf-8"))["global"]["default_engine"] == "bing"


def test_invalid_browser_section_does_not_reset_other_browser_preferences(tmp_path, monkeypatch):
    prefs = _store(tmp_path, monkeypatch)
    prefs._CONFIG.write_text(json.dumps({"schema_version": 1, "global": {"default_engine": "google"},
        "browsers": {"chrome": {"default_engine": "bing"}, "edge": "broken"}}), encoding="utf-8")
    assert prefs.resolve_search_engine(browser="chrome")[0] == "bing"
    assert prefs.resolve_search_engine(browser="edge")[0] == "google"


def test_existing_browser_search_interface_does_not_force_launch_when_cdp_missing(monkeypatch):
    from actions import browser_search
    monkeypatch.setattr("actions.browser_automation.is_cdp_active", lambda: False)
    monkeypatch.setattr("actions.browser_automation.browser_automation_engine.run",
                        lambda *a, **k: pytest.fail("Browser automation must not start without active CDP"))
    assert browser_search.search_in_browser("harmless query") == []


def test_search_tool_schema_and_public_handler_are_preserved():
    import inspect
    from actions.web_search import web_search_tool, web_search_structured
    from core.register_tools import default_tool_registry
    web = default_tool_registry.get_tool("web_search")
    assert web is not None and web.execute_func is not None
    assert callable(web_search_tool) and callable(web_search_structured)
    assert list(inspect.signature(web_search_structured).parameters) == ["query", "num_results", "preferred_provider", "force_refresh"]
    tools = [default_tool_registry.get_tool(name) for name in default_tool_registry.list_tools()]
    assert len(tools) == 73
    assert all(tool.execute_func and isinstance(tool.parameters, dict) and tool.parameters.get("type") == "OBJECT" for tool in tools)


def test_natural_hinglish_browser_preference_and_search_commands(tmp_path, monkeypatch):
    from actions import search_preferences as prefs
    from core.intent_router import classify_intent
    from actions.web_search import web_search_tool
    monkeypatch.setattr(prefs, "_CONFIG", tmp_path / "prefs.json")
    intent = classify_intent("Chrome ka search engine change karo")
    assert intent["intent"] == "WEB_SEARCH" and intent["tool"] == "web_search"
    saved = web_search_tool({"query": "Chrome mein Bing default kar do"})
    assert saved["success"] and prefs.resolve_search_engine(browser="chrome")[0] == "bing"
    shown = web_search_tool({"query": "Chrome aur Edge ki search settings dikhao"})
    assert shown["success"] and "preferences" in shown["data"]


def test_registered_search_tool_can_add_update_and_remove_custom_engines(tmp_path, monkeypatch):
    from actions import search_preferences as prefs
    from actions.web_search import web_search_tool
    monkeypatch.setattr(prefs, "_CONFIG", tmp_path / "prefs.json")
    added = web_search_tool({"action":"add_search_engine", "search_engine":"docs", "display_name":"Docs",
                             "search_url":"https://docs.example.org/search?q={query}"})
    assert added["success"] and "docs" in added["data"]["custom_engines"]
    assert web_search_tool({"action":"set_search_preference", "scope":"global", "search_engine":"docs"})["success"]
    assert web_search_tool({"action":"set_search_preference", "browser":"edge", "search_engine":"docs"})["success"]
    updated = web_search_tool({"action":"update_search_engine", "search_engine":"docs", "enabled":False})
    assert updated["success"] and not updated["data"]["custom_engines"]["docs"]["enabled"]
    assert updated["data"]["global"]["default_engine"] == "google"
    assert prefs.resolve_search_engine(browser="edge")[0] == "google"
    removed = web_search_tool({"action":"remove_search_engine", "search_engine":"docs"})
    assert removed["success"] and "docs" not in removed["data"]["custom_engines"]
    assert prefs._CONFIG.exists()


def test_global_provider_fallback_and_result_limit_preferences(tmp_path, monkeypatch):
    from actions import search_preferences as prefs
    from actions.web_search import web_search_tool
    monkeypatch.setattr(prefs, "_CONFIG", tmp_path / "prefs.json")
    result = web_search_tool({"action":"set_search_preference", "scope":"global", "preferred_provider":"brave",
                              "fallback":False, "result_limit":3})
    assert result["success"]
    assert result["data"]["global"]["preferred_provider"] == "brave"
    assert result["data"]["global"]["fallback"] is False
    assert result["data"]["global"]["result_limit"] == 3

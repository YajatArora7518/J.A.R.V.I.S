def search_in_browser(query, limit=3, browser="chrome", engine=None):
    from actions.browser_automation import browser_automation_engine as automation_engine
    try:
        return automation_engine.run(_search(str(query), max(1, min(3, int(limit))), browser, engine), timeout=55)
    except Exception:
        return []
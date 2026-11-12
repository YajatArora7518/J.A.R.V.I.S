"""Bounded public Google result fallback in the project's own controlled browser."""
from urllib.parse import quote_plus, urljoin, urlsplit


async def _search(query, limit, browser="chrome", engine=None):
    from actions.browser_automation import browser_automation_engine as automation
    from actions.web_search import _source_url
    from actions.web_search_providers import _relevant_results
    from actions.browser_automation import is_cdp_active
    from actions.search_preferences import build_search_url
    if browser != "chrome" or not is_cdp_active():
        return []  # Never launch a browser or substitute another browser silently.
    url = build_search_url(query, browser=browser, explicit_engine=engine)
    host = urlsplit(url).hostname
    page = await automation.get_or_open_page(host, url, allow_launch=False)
    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
    body = (await page.locator('body').inner_text(timeout=5000))[:10000].casefold()
    if '/sorry/' in page.url or 'unusual traffic' in body or 'not a robot' in body:
        return []  # Login/CAPTCHA/security checks are never bypassed.
    headings = page.locator('a h3, li.b_algo h2 a, a.result__a')
    await headings.first.wait_for(state='visible', timeout=12000)
    found, seen = [], set()
    for i in range(min(await headings.count(), 8)):
        heading = headings.nth(i)
        title = (await heading.inner_text()).strip()
        tag = await heading.evaluate('(el) => el.tagName.toLowerCase()')
        link = heading if tag == 'a' else heading.locator('xpath=ancestor::a[1]')
        href = await link.get_attribute('href') or ''
        absolute = urljoin('https://www.google.com', href)
        target = _source_url(absolute)
        host = (urlsplit(absolute).hostname or '').lower()
        if not target or host in ('google.com', 'www.google.com'):
            # Google can use opaque /goto links. Follow normally in a temporary
            # tab and use the real final URL; never decode hidden provider state.
            if host not in ('google.com', 'www.google.com') or not href.startswith(('/goto?', '/url?')):
                continue
            temporary = await page.context.new_page()
            try:
                await temporary.goto(absolute, wait_until='domcontentloaded', timeout=12000)
                target = _source_url(temporary.url)
            except Exception:
                target = ''
            finally:
                await temporary.close()
        if not target or target in seen or not title:
            continue
        target_host = (urlsplit(target).hostname or '').lower()
        if target_host in ('google.com', 'www.google.com', 'accounts.google.com'):
            continue
        seen.add(target)
        found.append({'title':title, 'url':target, 'snippet':'', 'date':'',
                      'source':target_host, 'search_provider':'Browser Google'})
        # Irrelevant early cards must not consume the useful-result budget.
        if len(_relevant_results(query, found)) >= limit:
            break
    return _relevant_results(query, found)[:limit]


def search_in_browser(query, limit=3, browser="chrome", engine=None):
    # The local import is named automation_engine so it can never shadow the
    # `engine` search-engine parameter. The previous shadowing bug made every
    # active-CDP browser search raise inside build_search_url and silently
    # return [] regardless of the selected engine.
    from actions.browser_automation import browser_automation_engine as automation_engine
    try:
        return automation_engine.run(_search(str(query), max(1, min(3, int(limit))), browser, engine), timeout=55)
    except Exception:
        return []  # Source-based answering will explicitly report unavailable evidence.
"""Exercise current selectors in isolated Chrome pages; no account actions."""
import asyncio
import pytest


async def isolated_page(callback):
    from playwright.async_api import async_playwright
    from actions.chrome_profile import get_chrome_executable
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
        try:
            context = await browser.new_context()
            await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body="<body></body>"))
            page = await context.new_page()
            await page.goto("https://web.whatsapp.com/")
            await callback(page)
        finally:
            await browser.close()


def test_modern_whatsapp_search_header_send_tick_read_and_draft():
    from actions.whatsapp_desktop_dom import execute_desktop_page
    async def run(page):
        await page.set_content('''<div id="side"><input aria-label="Search or start a new chat"></div>
        <div id="pane-side"><span title="Fixture">Fixture</span></div>
        <header data-testid="conversation-header"><span id="name">Other</span></header>
        <div data-testid="conversation-panel-messages"></div>
        <div data-testid="conversation-compose-box-input" contenteditable="true" role="textbox"></div>
        <script>
        document.querySelector('[title="Fixture"]').onclick=()=>document.querySelector('#name').textContent='Fixture';
        document.querySelector('[contenteditable]').onkeydown=e=>{if(e.key==='Enter'){
        e.preventDefault();window.sends=(window.sends||0)+1;
        const row=document.createElement('div');row.className='message-out';
        const text=document.createElement('span');text.className='selectable-text';text.textContent=e.target.textContent;
        const tick=document.createElement('span');tick.dataset.icon='msg-dblcheck';row.append(text,tick);
        document.querySelector('[data-testid="conversation-panel-messages"]').append(row);e.target.textContent='';}};
        </script>''')
        result = await execute_desktop_page(page, "send", "Fixture", "नमस्ते exact payload")
        assert result["status"] == "SENT_UI_VERIFIED", result
        assert await page.evaluate("window.sends") == 1
        assert await page.locator('#side input').input_value() == "Fixture"
        assert (await execute_desktop_page(page, "read", "Fixture"))["messages"] == ["नमस्ते exact payload"]
        await page.locator('[contenteditable]').fill("Personal unsent draft")
        assert (await execute_desktop_page(page, "send", "Fixture", "Different text"))["status"] == "EXISTING_DRAFT"
        assert await page.evaluate("window.sends") == 1
        assert await page.locator('[contenteditable]').inner_text() == "Personal unsent draft"
    asyncio.run(isolated_page(run))


@pytest.mark.parametrize("duplicate", [False, True])
def test_instagram_like_has_verified_state_and_no_ambiguous_or_repeat_clicks(duplicate):
    from actions.social_actions import execute_social_page
    async def run(page):
        await page.goto("https://www.instagram.com/p/fixture/")
        await page.set_content('''<button id="like">Like</button><script>
        document.querySelector('#like').onclick=e=>{window.clicks=(window.clicks||0)+1;e.target.textContent='Unlike';};
        </script>''')
        if duplicate:
            await page.evaluate("document.body.appendChild(document.querySelector('button').cloneNode(true))")
            result = await execute_social_page(page, "instagram", "like")
            assert result["status"] == "POST_NOT_RESOLVED"
            assert await page.evaluate("window.clicks || 0") == 0
        else:
            assert (await execute_social_page(page, "instagram", "like"))["status"] == "LIKE_UI_VERIFIED"
            assert (await execute_social_page(page, "instagram", "like"))["status"] == "ALREADY_LIKED"
            assert await page.evaluate("window.clicks") == 1
    asyncio.run(isolated_page(run))


def test_youtube_requests_desired_state_instead_of_toggling_playback():
    from actions.social_actions import execute_social_page
    async def run(page):
        await page.goto("https://www.youtube.com/watch?v=fixture")
        await page.set_content('<video style="width:320px;height:180px"></video>')
        # No media/network is required: the DOM exposes the same player state.
        await page.evaluate('''()=>{const v=document.querySelector('video');v.fixturePaused=true;
        Object.defineProperty(v,'paused',{get:()=>v.fixturePaused});
        v.play=async()=>{v.fixturePaused=false;window.plays=(window.plays||0)+1;};
        v.pause=()=>{v.fixturePaused=true;};}''')
        for _ in range(2):
            assert (await execute_social_page(page, "youtube", "play_media"))["verified"]
        assert await page.evaluate("window.plays") == 1
        assert (await execute_social_page(page, "youtube", "pause_media"))["verified"]
        assert await page.locator('video').evaluate('v=>v.paused') is True
    asyncio.run(isolated_page(run))

"""Real browser tests against isolated synthetic pages, with all URLs intercepted."""
import asyncio
import pytest
from actions.social_chat import execute_social_chat


HTML = '''<!doctype html><html><body>
<h1>Aman</h1>
<a href="/channels/@me/123456">Aman</a>
<div id="messages"><div id="message-content-1">Fixture message</div></div>
<div role="textbox" contenteditable="true" id="composer"></div>
<script>
document.querySelector('#composer').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    window.sendCount = (window.sendCount || 0) + 1;
    const row = document.createElement('div');
    row.id = 'message-content-' + Date.now();
    row.textContent = e.target.textContent;
    document.querySelector('#messages').appendChild(row);
    e.target.textContent = '';
  }
});
</script></body></html>'''


def test_real_dom_send_read_draft_and_recipient_guards():
    from actions.chrome_profile import get_chrome_executable
    from playwright.async_api import async_playwright
    chrome = get_chrome_executable()
    assert chrome, "Installed Chrome is required for the browser smoke test"
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=chrome, headless=True)
            try:
                context = await browser.new_context()
                await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=HTML))
                page = await context.new_page()
                await page.goto("https://discord.com/channels/@me/123456")
                result = await execute_social_chat(page, "discord", "send", "Aman", "नमस्ते 👋 on campus")
                assert result["success"] and result["verified"], result
                assert await page.evaluate("window.sendCount") == 1
                result = await execute_social_chat(page, "discord", "read")
                assert "नमस्ते 👋 on campus" in result["messages"]
                await page.locator("#composer").fill("Unsent personal draft")
                result = await execute_social_chat(page, "discord", "send", "Aman", "hello")
                assert result["status"] == "EXISTING_DRAFT"
                assert await page.locator("#composer").inner_text() == "Unsent personal draft"
                result = await execute_social_chat(page, "discord", "send", message_text="hello", recipient="")
                assert result["status"] == "RECIPIENT_REQUIRED"
                # A unique exact name must be resolved before typing or calling.
                result = await execute_social_chat(page, "discord", "send", "Unknown", "hello")
                assert result["status"] == "RECIPIENT_NOT_RESOLVED"
                await context.close()
            finally:
                await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize("platform", ["discord", "instagram", "whatsapp"])
def test_actual_dom_call_answer_end_and_message_controls(platform):
    from actions.chrome_profile import get_chrome_executable
    from actions.whatsapp_desktop_dom import execute_desktop_page
    from playwright.async_api import async_playwright
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                context = await browser.new_context()
                fixture = '''<div id="side"></div><div id="main"><header><h1>Aman</h1></header>
                <div id="messages"></div><footer><div id="composer" role="textbox" contenteditable="true"></div></footer></div>
                <button id="call">Voice Call</button><button id="answer">Answer</button>
                <script>
                const start=()=>{document.querySelector('#call').remove();document.querySelector('#answer').remove();const b=document.createElement('button');b.textContent='End Call';b.onclick=()=>b.remove();document.body.appendChild(b);window.callCount=(window.callCount||0)+1;};
                document.querySelector('#call').onclick=start;document.querySelector('#answer').onclick=start;
                document.querySelector('#composer').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();window.sendCount=(window.sendCount||0)+1;
                const row=document.createElement('div');row.className='message-out';row.setAttribute('role','row');
                const text=document.createElement('span');text.id='message-content-'+Date.now();text.className='selectable-text';text.textContent=e.target.textContent;row.appendChild(text);
                const tick=document.createElement('span');tick.setAttribute('data-icon','msg-check');row.appendChild(tick);document.querySelector('#messages').appendChild(row);e.target.textContent='';}};
                </script>'''
                await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=fixture))
                page = await context.new_page()
                url = {"discord": "https://discord.com/channels/@me/123", "instagram": "https://www.instagram.com/direct/t/123/", "whatsapp": "https://web.whatsapp.com/"}[platform]
                await page.goto(url)
                async def execute(action, recipient="", message=""):
                    return await execute_desktop_page(page, action, recipient, message) if platform == "whatsapp" else await execute_social_chat(page, platform, action, recipient, message)
                result = await execute("send", "Aman", "Exact unicode नमस्ते 👋")
                assert result["success"] and result["verified"], result
                assert await page.evaluate("window.sendCount") == 1
                result = await execute("read")
                assert "Exact unicode नमस्ते 👋" in result["messages"]
                result = await execute("voice_call" if platform == "whatsapp" else "call", "Aman")
                assert result["success"] and result["verified"], result
                assert await page.evaluate("window.callCount") == 1
                result = await execute("end_call")
                assert result["success"] and result["verified"], result
                # Reset only the synthetic fixture, then exercise incoming answer.
                await page.goto(url)
                result = await execute("answer")
                assert result["success"] and result["verified"], result
                assert await page.evaluate("window.callCount") == 1
                await context.close()
            finally:
                await browser.close()
    asyncio.run(run())


def test_discord_disconnect_and_idempotent_mute_use_real_named_controls():
    from actions.discord_automation import execute_discord_control
    from actions.chrome_profile import get_chrome_executable
    from playwright.async_api import async_playwright
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                context = await browser.new_context()
                fixture = '''<button id="mute">Mute</button><button id="deafen">Deafen</button><button id="disconnect">Disconnect</button>
                <script>for(const [id,on,off] of [['mute','Mute','Unmute'],['deafen','Deafen','Undeafen']])document.getElementById(id).onclick=e=>{window[id+'Count']=(window[id+'Count']||0)+1;e.target.textContent=e.target.textContent===on?off:on;};
                document.getElementById('disconnect').onclick=e=>e.target.remove();</script>'''
                await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=fixture))
                page = await context.new_page()
                await page.goto("https://discord.com/channels/@me")
                for action in ("mute", "deafen"):
                    first = await execute_discord_control(page, action, True)
                    second = await execute_discord_control(page, action, True)
                    assert first["verified"] and second["verified"]
                    assert await page.evaluate(f"window.{action}Count") == 1
                    assert (await execute_discord_control(page, action, False))["verified"]
                assert (await execute_discord_control(page, "disconnect"))["verified"]
                assert await page.get_by_role("button", name="Disconnect").count() == 0
                assert await page.get_by_role("button", name="Deafen", exact=True).count() == 1
                await context.close()
            finally:
                await browser.close()
    asyncio.run(run())

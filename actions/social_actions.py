"""Verified social actions; unsupported operations never fabricate success."""
import asyncio
import re
from urllib.parse import urlparse


def _failure(message, status="UNSUPPORTED"):
    return {"success": False, "verified": False, "status": status, "message": message}


async def execute_social_page(page, platform, action):
    if platform == "instagram" and action == "like":
        if "/accounts/login" in urlparse(page.url).path:
            return _failure("Instagram mein sign in karo.", "LOGIN_REQUIRED")
        likes = page.get_by_role("button", name=re.compile(r"^Like$", re.I)).filter(visible=True)
        unlikes = page.get_by_role("button", name=re.compile(r"^Unlike$", re.I)).filter(visible=True)
        if await unlikes.count() == 1 and await likes.count() == 0:
            return {"success": True, "verified": True, "status": "ALREADY_LIKED", "message": "Visible post pehle se liked hai."}
        if await likes.count() != 1 or await unlikes.count():
            return _failure("Ek exact post khol do; multiple ya unavailable Like controls hain.", "POST_NOT_RESOLVED")
        await likes.click(timeout=3000)
        for _ in range(12):
            if await unlikes.count() == 1 and await likes.count() == 0:
                return {"success": True, "verified": True, "status": "LIKE_UI_VERIFIED", "message": "Post ka Like state verify ho gaya."}
            await asyncio.sleep(.25)
        return _failure("Like attempt hua, state verify nahi hui. Dobara automatically click nahi kiya.", "ACTION_UNVERIFIED")
    if platform == "youtube" and action in ("play_media", "pause_media"):
        videos = page.locator("video").filter(visible=True)
        if await videos.count() != 1:
            return _failure("Ek visible YouTube video player nahi mila.", "PLAYER_NOT_RESOLVED")
        paused = action == "pause_media"
        await videos.evaluate("async (video, paused) => { if (paused) video.pause(); else if (video.paused) await video.play(); }", paused)
        actual = await videos.evaluate("video => video.paused")
        if actual is paused:
            return {"success": True, "verified": True, "status": "PLAYER_STATE_VERIFIED", "message": "Video pause ho gaya." if paused else "Video play ho raha hai."}
        return _failure("Video playback state verify nahi hui.", "ACTION_UNVERIFIED")
    return _failure("Yeh social action implement nahi hai.")


def execute_social_action(platform, action, target="", content=""):
    platform = {"ig": "instagram", "yt": "youtube"}.get((platform or "").lower().strip(), (platform or "").lower().strip())
    action = (action or "").lower().strip()
    if (platform, action) not in (("instagram", "like"), ("youtube", "play_media"), ("youtube", "pause_media")):
        return _failure(f"{platform} par {action} supported nahi hai.")
    from actions.browser_automation import browser_automation_engine
    domain = "instagram.com" if platform == "instagram" else "youtube.com"
    url = f"https://www.{domain}/"
    if target:
        parsed = urlparse(target)
        if parsed.scheme != "https" or parsed.hostname not in (domain, "www." + domain):
            return _failure("Exact post/video ka HTTPS link do, taaki sahi target select ho.", "TARGET_REQUIRED")
        url = target
    async def run():
        page = await browser_automation_engine.get_or_open_page(domain, url)
        if target and page.url != url:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return await execute_social_page(page, platform, action)
    try:
        return browser_automation_engine.run(run(), timeout=25)
    except Exception as exc:
        return _failure(f"Social action complete nahi hua: {type(exc).__name__}", "ACTION_UNVERIFIED")

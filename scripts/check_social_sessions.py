"""Check login controls only; never read conversations or send anything."""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.browser_automation import browser_automation_engine


async def check():
    results = {}
    for platform, url in (("discord", "https://discord.com/channels/@me"), ("instagram", "https://www.instagram.com/direct/inbox/")):
        page = await browser_automation_engine.get_or_open_page(platform + ".com", url)
        await page.wait_for_timeout(1500)
        login_controls = page.get_by_role("button", name=re.compile(r"^(Log In|Login|Sign In)$", re.I)).filter(visible=True)
        requires_login = bool(await login_controls.count()) or any(part in page.url for part in ("/login", "/challenge", "/checkpoint"))
        signed_in_controls = (page.locator('[data-list-id="private-channels"], nav[aria-label="Servers sidebar"]') if platform == "discord"
            else page.get_by_role("heading", name=re.compile(r"^(Messages|Chats)$", re.I)))
        results[platform] = {"login_required": requires_login, "signed_in_ui_verified": bool(not requires_login and await signed_in_controls.count()), "url": page.url}
    return results

results = browser_automation_engine.run(check(), timeout=30)
print(json.dumps(results, indent=2))
(Path(__file__).resolve().parent.parent / "scratch" / "social_sessions.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

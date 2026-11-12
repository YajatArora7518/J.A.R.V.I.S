"""Open the controlled browser login tabs required for personal social automation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.browser_automation import ensure_cdp_chrome, browser_automation_engine

result = ensure_cdp_chrome("https://discord.com/channels/@me")
if not result.get("success"):
    print(result.get("message", "Controlled browser unavailable."))
    sys.exit(1)

async def open_sessions():
    await browser_automation_engine.get_or_open_page("discord.com", "https://discord.com/channels/@me")
    await browser_automation_engine.get_or_open_page("instagram.com", "https://www.instagram.com/direct/inbox/")

browser_automation_engine.run(open_sessions())
print("Discord aur Instagram mein is JARVIS browser window par ek baar sign in karo.")
print("Login ke baad voice se message/read/call commands use kar sakte ho. Password JARVIS ko batane ki zaroorat nahi hai.")

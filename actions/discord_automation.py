"""Discord controls verified against the actual signed-in browser UI."""
import asyncio
import re
from actions.social_platform_resolver import SocialPlatformProvider


async def execute_discord_control(page, action, desired=True, channel="General"):
    from actions.social_chat import _failed
    if "/login" in page.url:
        return _failed("Controlled Discord browser mein sign in karo.", "LOGIN_REQUIRED")
    if action in ("mute", "deafen"):
        current_label, requested_label = (("Mute", "Unmute") if action == "mute" else ("Deafen", "Undeafen"))
        before_label = current_label if desired else requested_label
        after_label = requested_label if desired else current_label
        before = page.get_by_role("button", name=re.compile(rf"^{before_label}(?:\s*\(.*\))?$", re.I)).filter(visible=True)
        after = page.get_by_role("button", name=re.compile(rf"^{after_label}(?:\s*\(.*\))?$", re.I)).filter(visible=True)
        if await after.count() == 1 and await before.count() == 0:
            return {"success": True, "verified": True, "message": f"Discord {action} already {'on' if desired else 'off'} hai."}
        if await before.count() != 1:
            return _failed(f"Discord {action} control exact match nahi mila.", "CONTROL_UNAVAILABLE")
        await before.click()
        try:
            await after.wait_for(state="visible", timeout=3000)
        except Exception:
            return _failed(f"Discord {action} change verify nahi hua.", "STATE_UNVERIFIED")
        return {"success": True, "verified": True, "message": f"Discord {action} {'on' if desired else 'off'} kar diya."}
    disconnect = page.get_by_role("button", name=re.compile(r"^(Disconnect|Disconnect from voice)$", re.I)).filter(visible=True)
    if action == "disconnect":
        if await disconnect.count() == 0:
            return {"success": True, "verified": True, "message": "Discord voice connection active nahi hai."}
        if await disconnect.count() != 1:
            return _failed("Discord disconnect control ambiguous hai.")
        await disconnect.click()
        try:
            await disconnect.wait_for(state="hidden", timeout=3000)
        except Exception:
            return _failed("Discord disconnect verify nahi hua.", "STATE_UNVERIFIED")
        return {"success": True, "verified": True, "message": "Discord voice disconnect kar diya."}
    if action == "join":
        if await disconnect.count():
            return _failed("Discord already voice se connected hai. Channel switch pehle explicitly bolo.", "ALREADY_CONNECTED")
        exact = page.get_by_role("link", name=re.compile(rf"^{re.escape(channel)}(?:,?\s+voice channel)?$", re.I)).filter(visible=True)
        if await exact.count() != 1:
            return _failed("Exact unique visible voice channel nahi mila. Server/channel kholkar naam do.", "CHANNEL_NOT_RESOLVED")
        await exact.click()
        try:
            await disconnect.wait_for(state="visible", timeout=5000)
        except Exception:
            return _failed("Voice channel attempt hua, connection controls verify nahi hue.", "STATE_UNVERIFIED")
        return {"success": True, "verified": True, "message": f"Discord voice channel '{channel}' ke connection controls active hain."}
    return _failed("Unsupported Discord control.")


class DiscordProvider(SocialPlatformProvider):
    def __init__(self):
        super().__init__("Discord")

    def open(self, mode="auto"):
        from actions.open_app import open_app
        result = open_app(app_name="discord", mode=mode)
        if isinstance(result, dict):
            return result
        return {"success": False, "verified": False, "message": str(result)}

    def _control(self, action, desired=True, channel="General"):
        from actions.browser_automation import browser_automation_engine, ensure_cdp_chrome
        from actions.social_chat import _failed
        ready = ensure_cdp_chrome("https://discord.com/channels/@me")
        if not ready.get("success"):
            return _failed(ready.get("message", "Controlled browser unavailable."))
        async def run():
            page = await browser_automation_engine.get_or_open_page("discord.com", "https://discord.com/channels/@me")
            return await execute_discord_control(page, action, desired, channel)
        try:
            return browser_automation_engine.run(run(), timeout=20)
        except Exception as exc:
            return _failed(f"Discord control complete nahi hua: {str(exc)[:120]}")

    def join_voice(self, channel="General"):
        return self._control("join", channel=channel)

    def disconnect_voice(self):
        return self._control("disconnect")

    def mute(self, mute=True):
        return self._control("mute", desired=mute)

    def deafen(self, deafen=True):
        return self._control("deafen", desired=deafen)

    def send_message(self, target, message, force_send=False):
        from actions.social_chat import social_chat
        return social_chat({"platform": "discord", "action": "send", "recipient": target, "message_text": message})

    def read_messages(self, target=""):
        from actions.social_chat import social_chat
        return social_chat({"platform": "discord", "action": "read", "recipient": target})

    def call(self, target, call_type="voice", confirm_call=False):
        if not confirm_call:
            return {"success": False, "verified": False, "requires_confirmation": True, "message": "Exact Discord call instruction confirm karo."}
        from actions.social_chat import social_chat
        return social_chat({"platform": "discord", "action": "call", "recipient": target, "call_type": call_type})


discord_provider = DiscordProvider()

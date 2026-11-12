# actions/social_platform_resolver.py
# Universal Social Platform Provider Interface for JARVIS

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.SocialResolver")


class SocialPlatformProvider:
    """Base interface for all social platform providers (WhatsApp, Discord, Telegram, Instagram, etc.)."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    def open(self, mode: str = "auto") -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Opening {self.platform_name} is not implemented."}

    def search_contact(self, query: str) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Search contact on {self.platform_name} is not implemented."}

    def open_chat(self, contact: str) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Open chat on {self.platform_name} is not implemented."}

    def send_message(self, target: str, message: str, force_send: bool = False) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Send message on {self.platform_name} is not implemented."}

    def reply(self, message: str) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Reply on {self.platform_name} is not implemented."}

    def read_messages(self, target: str = "") -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Read messages on {self.platform_name} is not implemented."}

    def call(self, target: str, call_type: str = "voice", confirm_call: bool = False) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Call on {self.platform_name} is not implemented."}

    def join_voice(self, channel: str = "") -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Join voice on {self.platform_name} is not supported."}

    def disconnect_voice(self) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Disconnect voice on {self.platform_name} is not supported."}

    def mute(self, mute: bool = True) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Mute on {self.platform_name} is not supported."}

    def deafen(self, deafen: bool = True) -> Dict[str, Any]:
        return {"success": False, "status": "UNSUPPORTED_ACTION", "message": f"Deafen on {self.platform_name} is not supported."}


def resolve_social_platform(platform_name: str) -> SocialPlatformProvider:
    """Returns the registered SocialPlatformProvider for the requested platform name."""
    p_name = (platform_name or "").lower().strip()

    if p_name in ["whatsapp", "wa"]:
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        
        class WhatsAppProvider(SocialPlatformProvider):
            def __init__(self):
                super().__init__("WhatsApp")
            def open_chat(self, contact: str) -> Dict[str, Any]:
                from actions.whatsapp_desktop_dom import desktop_action
                return desktop_action("open_chat", contact)
            def send_message(self, target: str, message: str, force_send: bool = False) -> Dict[str, Any]:
                return windows_whatsapp_desktop_executor.execute_send_message(recipient=target, message=message)
            def read_messages(self, target: str = "") -> Dict[str, Any]:
                from actions.whatsapp_desktop_dom import desktop_action
                return desktop_action("read", target)
            def call(self, target: str, call_type: str = "voice", confirm_call: bool = False) -> Dict[str, Any]:
                if not confirm_call:
                    return {"success": False, "verified": False, "requires_confirmation": True, "message": "Exact WhatsApp call instruction confirm karo."}
                if call_type == "video":
                    return windows_whatsapp_desktop_executor.execute_video_call(recipient=target)
                return windows_whatsapp_desktop_executor.execute_voice_call(recipient=target)

        return WhatsAppProvider()

    elif p_name in ["discord", "disc"]:
        from actions.discord_automation import discord_provider
        return discord_provider

    elif p_name in ["instagram", "insta", "ig"]:
        class InstagramProvider(SocialPlatformProvider):
            def __init__(self):
                super().__init__("Instagram")
            def send_message(self, target, message, force_send=False):
                from actions.social_chat import social_chat
                return social_chat({"platform": "instagram", "action": "send", "recipient": target, "message_text": message})
            def read_messages(self, target=""):
                from actions.social_chat import social_chat
                return social_chat({"platform": "instagram", "action": "read", "recipient": target})
            def call(self, target, call_type="voice", confirm_call=False):
                if not confirm_call:
                    return {"success": False, "verified": False, "requires_confirmation": True, "message": "Exact Instagram call instruction confirm karo."}
                from actions.social_chat import social_chat
                return social_chat({"platform": "instagram", "action": "call", "recipient": target, "call_type": call_type})
        return InstagramProvider()

    return SocialPlatformProvider(platform_name)

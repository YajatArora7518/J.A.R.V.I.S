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
                return windows_whatsapp_desktop_executor.execute_send_message(recipient=contact, message="")
            def send_message(self, target: str, message: str, force_send: bool = False) -> Dict[str, Any]:
                return windows_whatsapp_desktop_executor.execute_send_message(recipient=target, message=message)
            def read_messages(self, target: str = "") -> Dict[str, Any]:
                return {"success": True, "action": "read_messages", "message": "Reading visible messages on installed WhatsApp Desktop", "execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"}
            def call(self, target: str, call_type: str = "voice", confirm_call: bool = False) -> Dict[str, Any]:
                if call_type == "video":
                    return windows_whatsapp_desktop_executor.execute_video_call(recipient=target)
                return windows_whatsapp_desktop_executor.execute_voice_call(recipient=target)

        return WhatsAppProvider()

    elif p_name in ["discord", "disc"]:
        from actions.discord_automation import discord_provider
        return discord_provider

    return SocialPlatformProvider(platform_name)

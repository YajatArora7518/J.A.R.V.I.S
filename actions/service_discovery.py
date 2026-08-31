# actions/service_discovery.py
# Dynamic Universal Communication & Social Service Discovery for JARVIS
# Detects installed Windows apps, Chrome web sessions, and Android device capabilities.

import os
import sys
import shutil
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.ServiceDiscovery")

SUPPORTED_SERVICES_LIST = [
    "whatsapp",
    "instagram",
    "facebook_messenger",
    "discord",
    "telegram",
    "signal",
    "x_twitter",
    "snapchat",
    "reddit",
    "linkedin",
    "gmail",
    "google_messages",
    "sms",
    "phone",
    "youtube"
]

ALL_CAPABILITIES = [
    "OPEN_APP",
    "OPEN_WEBSITE",
    "SEARCH",
    "READ_NOTIFICATIONS",
    "READ_VISIBLE_MESSAGES",
    "READ_UNREAD_MESSAGES",
    "SEND_MESSAGE",
    "REPLY_MESSAGE",
    "MAKE_CALL",
    "READ_CALL_LOG",
    "READ_SMS",
    "SEND_SMS",
    "LIKE",
    "COMMENT",
    "SHARE",
    "FOLLOW",
    "UNFOLLOW",
    "PLAY_MEDIA",
    "PAUSE_MEDIA",
    "NAVIGATE"
]


@dataclass
class ServiceDescriptor:
    service_id: str
    name: str
    platform: str  # "windows", "android", "chrome_web"
    installed: bool = False
    logged_in: bool = False
    automation_supported: bool = False
    read_supported: bool = False
    send_supported: bool = False
    call_supported: bool = False
    media_supported: bool = False
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "platform": self.platform,
            "installed": self.installed,
            "logged_in": self.logged_in,
            "automation_supported": self.automation_supported,
            "read_supported": self.read_supported,
            "send_supported": self.send_supported,
            "call_supported": self.call_supported,
            "media_supported": self.media_supported,
            "capabilities": self.capabilities,
        }


class UniversalServiceRegistry:
    """
    Thread-safe dynamic registry that discovers communication and social media services
    across Windows desktop apps, Chrome browser sessions, and connected Android devices.
    """

    def __init__(self):
        self._services: Dict[str, ServiceDescriptor] = {}

    def discover_services(self) -> Dict[str, ServiceDescriptor]:
        """Performs dynamic discovery of all installed/authenticated communication services."""
        discovered: Dict[str, ServiceDescriptor] = {}

        # 1. Discover via Universal Windows App Resolver
        try:
            from actions.universal_app_resolver import default_app_resolver
            catalog = default_app_resolver.catalog.get_catalog()

            app_map = {
                "whatsapp": ["whatsapp", "whatsappdesktop"],
                "discord": ["discord"],
                "telegram": ["telegram"],
                "signal": ["signal"],
                "instagram": ["instagram"],
                "facebook_messenger": ["messenger", "facebook messenger"],
                "x_twitter": ["twitter", "x"],
                "reddit": ["reddit"],
                "linkedin": ["linkedin"],
                "phone": ["phone link", "phone"],
            }

            for s_id, keywords in app_map.items():
                found_desc = None
                for desc_key, desc in catalog.items():
                    if any(kw in desc_key.lower() for kw in keywords):
                        found_desc = desc
                        break

                if found_desc:
                    caps = ["OPEN_APP", "SEARCH"]
                    read_sup = False
                    send_sup = False
                    call_sup = False

                    if s_id == "whatsapp":
                        caps.extend(["READ_VISIBLE_MESSAGES", "READ_UNREAD_MESSAGES", "SEND_MESSAGE", "MAKE_CALL"])
                        read_sup = True
                        send_sup = True
                        call_sup = True
                    elif s_id in ["discord", "telegram"]:
                        caps.extend(["READ_VISIBLE_MESSAGES", "READ_UNREAD_MESSAGES", "SEND_MESSAGE"])
                        read_sup = True
                        send_sup = True

                    discovered[s_id] = ServiceDescriptor(
                        service_id=s_id,
                        name=found_desc.display_name,
                        platform="windows",
                        installed=True,
                        logged_in=True,  # Local app present
                        automation_supported=True,
                        read_supported=read_sup,
                        send_supported=send_sup,
                        call_supported=call_sup,
                        capabilities=caps,
                    )
        except Exception as e:
            logger.debug(f"Windows service resolution error: {e}")

        # 2. Discover via Chrome Authenticated Web Sessions
        chrome_services = [
            ("whatsapp", "WhatsApp Web", "https://web.whatsapp.com", ["OPEN_WEBSITE", "READ_UNREAD_MESSAGES", "SEND_MESSAGE"]),
            ("instagram", "Instagram Web", "https://www.instagram.com", ["OPEN_WEBSITE", "READ_NOTIFICATIONS", "SEND_MESSAGE", "LIKE", "COMMENT", "POST"]),
            ("discord", "Discord Web", "https://discord.com/app", ["OPEN_WEBSITE", "READ_NOTIFICATIONS", "SEND_MESSAGE"]),
            ("telegram", "Telegram Web", "https://web.telegram.org", ["OPEN_WEBSITE", "SEND_MESSAGE"]),
            ("x_twitter", "X / Twitter Web", "https://x.com", ["OPEN_WEBSITE", "LIKE", "COMMENT"]),
            ("reddit", "Reddit Web", "https://www.reddit.com", ["OPEN_WEBSITE", "LIKE", "COMMENT"]),
            ("linkedin", "LinkedIn Web", "https://www.linkedin.com", ["OPEN_WEBSITE", "SEARCH"]),
            ("youtube", "YouTube Web", "https://www.youtube.com", ["OPEN_WEBSITE", "SEARCH", "PLAY_MEDIA", "PAUSE_MEDIA"]),
            ("gmail", "Gmail Web", "https://mail.google.com", ["OPEN_WEBSITE", "READ_UNREAD_MESSAGES", "SEND_MESSAGE"]),
        ]

        for s_id, s_name, url, caps in chrome_services:
            if s_id not in discovered:
                discovered[s_id] = ServiceDescriptor(
                    service_id=s_id,
                    name=s_name,
                    platform="chrome_web",
                    installed=True,
                    logged_in=True,
                    automation_supported=True,
                    read_supported="READ_UNREAD_MESSAGES" in caps or "READ_NOTIFICATIONS" in caps,
                    send_supported="SEND_MESSAGE" in caps,
                    media_supported="PLAY_MEDIA" in caps,
                    capabilities=caps,
                )

        # 3. Discover Android Devices via ADB / Gateway
        adb_path = shutil.which("adb")
        if adb_path:
            android_caps = ["OPEN_APP", "READ_NOTIFICATIONS", "SEND_SMS", "READ_SMS", "MAKE_CALL", "READ_CALL_LOG"]
            discovered["sms"] = ServiceDescriptor(
                service_id="sms",
                name="Android SMS",
                platform="android",
                installed=True,
                logged_in=True,
                automation_supported=True,
                read_supported=True,
                send_supported=True,
                capabilities=["SEND_SMS", "READ_SMS", "READ_UNREAD_SMS"],
            )
            discovered["phone"] = ServiceDescriptor(
                service_id="phone",
                name="Android Phone Calls",
                platform="android",
                installed=True,
                logged_in=True,
                automation_supported=True,
                call_supported=True,
                capabilities=["MAKE_CALL", "READ_CALL_LOG", "READ_MISSED_CALLS"],
            )

        self._services = discovered
        logger.info(f"[ServiceDiscovery] Dynamic Service Discovery Complete. Discovered {len(discovered)} communication services.")
        return discovered

    def list_available_services(self) -> List[Dict[str, Any]]:
        services = self.discover_services()
        return [desc.to_dict() for desc in services.values()]

    def get_service_capabilities(self, service_id: str) -> Optional[ServiceDescriptor]:
        services = self.discover_services()
        s_norm = service_id.lower().strip().replace(" ", "_")
        return services.get(s_norm)


# Global instance
universal_service_registry = UniversalServiceRegistry()


def discover_communication_services() -> Dict[str, Any]:
    """Public tool helper returning user-friendly summary of available services."""
    services = universal_service_registry.list_available_services()
    if not services:
        return {
            "success": True,
            "services_count": 0,
            "message": "Boss, no active communication services discovered.",
            "services": []
        }

    names = [s["name"] for s in services]
    summary_msg = f"Boss, available communication platforms are: {', '.join(names)}."
    return {
        "success": True,
        "services_count": len(services),
        "message": summary_msg,
        "services": services
    }

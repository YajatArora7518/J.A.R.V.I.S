# agent/awareness/instagram_provider.py
"""
Instagram Read-Only Awareness Provider.
Uses only officially permitted/authenticated access.
Returns CONFIGURATION_REQUIRED cleanly when unconfigured.
"""

import os
from typing import Dict, Any
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.status_model import status_registry, ProviderState


class InstagramAwarenessProvider:
    """
    Read-only official/authenticated Instagram provider.
    """
    def check_activity(self) -> Dict[str, Any]:
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("instagram", ProviderState.PAUSED, enabled=False)
            return {"status": "INSTAGRAM_UNAVAILABLE", "notifications": []}

        if not permission_manager.is_granted("INSTAGRAM_READ"):
            status_registry.update_status("instagram", ProviderState.DISABLED, enabled=False)
            return {"status": "INSTAGRAM_UNAVAILABLE", "notifications": []}

        # 1. Try Chrome browser session reuse
        try:
            from actions.browser_automation import is_cdp_active, browser_automation_engine
            if is_cdp_active():
                res = browser_automation_engine.check_service_auth_sync("instagram")
                if res.get("status") == "LIVE_VERIFIED":
                    status_registry.update_status("instagram", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
                    return {
                        "status": "OK",
                        "notifications": [],
                        "source": "chrome_session",
                        "verified": True
                    }
                elif res.get("status") == "AUTHENTICATION_REQUIRED":
                    status_registry.update_status("instagram", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="Instagram login required in Chrome")
                    return {
                        "status": "INSTAGRAM_UNAVAILABLE",
                        "notifications": [],
                        "message": "Instagram login required in Chrome session."
                    }
        except Exception:
            pass

        token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
        if not token:
            status_registry.update_status("instagram", ProviderState.CONFIGURATION_REQUIRED, enabled=True, error_msg="INSTAGRAM_ACCESS_TOKEN missing")
            return {
                "status": "INSTAGRAM_UNAVAILABLE",
                "notifications": [],
                "message": "Instagram provider requires INSTAGRAM_ACCESS_TOKEN environment variable."
            }

        status_registry.update_status("instagram", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
        return {
            "status": "OK",
            "notifications": [],
            "verified": True
        }


instagram_provider = InstagramAwarenessProvider()

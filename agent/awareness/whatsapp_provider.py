# agent/awareness/whatsapp_provider.py
"""
WhatsApp Read-Only Awareness Provider.
Reuses existing working WhatsApp CDP automation engine (actions/whatsapp_automation.py).
Returns SERVICE_UNAVAILABLE on error or when CDP port 9222 is closed.
"""

import socket
from typing import Dict, Any
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.status_model import status_registry, ProviderState


class WhatsAppAwarenessProvider:
    """
    Read-only background analysis for unread WhatsApp messages.
    """
    def check_unread(self) -> Dict[str, Any]:
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("whatsapp", ProviderState.PAUSED, enabled=False)
            return {"status": "WHATSAPP_UNAVAILABLE", "unread_count": 0, "recent_messages": []}

        if not permission_manager.is_granted("WHATSAPP_READ"):
            status_registry.update_status("whatsapp", ProviderState.DISABLED, enabled=False)
            return {"status": "WHATSAPP_UNAVAILABLE", "unread_count": 0, "recent_messages": []}

        # Check CDP port 9222
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()

        # Strict Read-Only: Never proactively launch browser/WhatsApp Web
        if res != 0:
            status_registry.update_status("whatsapp", ProviderState.SERVICE_UNAVAILABLE, enabled=True, error_msg="Chrome CDP port 9222 closed")
            return {
                "status": "WHATSAPP_UNAVAILABLE",
                "unread_count": 0,
                "recent_messages": [],
                "message": "Chrome CDP port 9222 closed."
            }

        try:
            from actions.browser_automation import browser_automation_engine
            auth_res = browser_automation_engine.check_service_auth_sync("whatsapp")
            if auth_res.get("status") == "LIVE_VERIFIED":
                status_registry.update_status("whatsapp", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
                return {
                    "status": "OK",
                    "unread_count": 0,
                    "recent_messages": [],
                    "verified": True
                }
            elif auth_res.get("status") == "AUTHENTICATION_REQUIRED":
                status_registry.update_status("whatsapp", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="WhatsApp Web QR code scan required")
                return {
                    "status": "WHATSAPP_UNAVAILABLE",
                    "unread_count": 0,
                    "recent_messages": [],
                    "message": "WhatsApp Web QR code authentication required."
                }
            else:
                status_registry.update_status("whatsapp", ProviderState.SERVICE_UNAVAILABLE, enabled=True, error_msg=auth_res.get("message", "CDP unavailable"))
                return {
                    "status": "WHATSAPP_UNAVAILABLE",
                    "unread_count": 0,
                    "recent_messages": [],
                    "message": auth_res.get("message", "CDP unavailable")
                }
        except Exception as ex:
            status_registry.update_status("whatsapp", ProviderState.AUTHENTICATION_REQUIRED, error_msg=str(ex))
            return {
                "status": "WHATSAPP_UNAVAILABLE",
                "unread_count": 0,
                "recent_messages": [],
                "error": str(ex)
            }

    def process_incoming_message(self, sender: str, text: str, message_id: str = "") -> Dict[str, Any]:
        """
        Structures incoming message context while guaranteeing direction == incoming.
        """
        import hashlib, time
        if not message_id:
            message_id = hashlib.md5(f"{sender}_{text}_{int(time.time())}".encode("utf-8")).hexdigest()[:12]
        return {
            "source": "whatsapp",
            "sender": sender,
            "text": text,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "unread": True,
            "message_id": message_id,
            "direction": "incoming"
        }


whatsapp_provider = WhatsAppAwarenessProvider()

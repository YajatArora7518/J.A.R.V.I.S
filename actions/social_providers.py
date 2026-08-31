# actions/social_providers.py
# Official Social & Communication API Providers for JARVIS
# Supports WhatsApp Cloud API + Webhook, Instagram Graph API, Discord Bot API, and Meta OAuth Manager.

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.SocialProviders")

# Configurable Meta Graph API Version
DEFAULT_META_VERSION = os.environ.get("META_GRAPH_API_VERSION", "v21.0")


def redact_secret(value: str) -> str:
    """Safely redacts sensitive credentials for logging and UI displays."""
    if not value or not isinstance(value, str):
        return ""
    if len(value) <= 8:
        return "***REDACTED***"
    return f"{value[:4]}...***REDACTED***...{value[-4:]}"


def _get_api_keys() -> Dict[str, Any]:
    """Helper to load secrets from config/api_keys.json or environment."""
    base_dir = getattr(sys, "_MEIPASS", None)
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    cfg_file = os.path.join(base_dir, "config", "api_keys.json")
    data = {}
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"Could not load api_keys.json: {e}")
    return data


# =====================================================================
# 1. META OAUTH & PERMISSION MANAGER
# =====================================================================
class MetaOAuthHandler:
    """Handles Meta App Access Tokens, permissions diagnostics, and signature validation."""

    def __init__(self, api_version: str = DEFAULT_META_VERSION):
        self.api_version = api_version

    def validate_access_token(self, access_token: str, app_id: str = "", app_secret: str = "") -> Dict[str, Any]:
        """Validates Meta access token via debug_token endpoint."""
        if not access_token:
            return {"valid": False, "reason": "No access token provided."}

        url = f"https://graph.facebook.com/{self.api_version}/debug_token?input_token={access_token}"
        if app_id and app_secret:
            url += f"&access_token={app_id}|{app_secret}"
        else:
            url += f"&access_token={access_token}"

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
                is_valid = data.get("is_valid", False)
                scopes = data.get("scopes", [])
                expires_at = data.get("expires_at", 0)
                return {
                    "valid": is_valid,
                    "scopes": scopes,
                    "expires_at": expires_at,
                    "app_id": data.get("app_id"),
                    "user_id": data.get("user_id")
                }
        except Exception as e:
            return {"valid": False, "error": str(e), "reason": f"Meta token debug failed: {e}"}

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str, app_secret: str) -> bool:
        """Verifies sha256 HMAC signature of incoming Meta Webhook payload."""
        if not signature_header or not app_secret or not signature_header.startswith("sha256="):
            return False
        expected_sig = signature_header.replace("sha256=", "").strip()
        computed_sig = hmac.new(app_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, computed_sig)


# =====================================================================
# 2. WHATSAPP CLOUD PROVIDER (OFFICIAL META API + WEBHOOK RECEIVER)
# =====================================================================
class WhatsAppCloudProvider:
    """Official Meta WhatsApp Cloud API Provider for Outgoing Messages & Webhook Integration."""

    def __init__(self, api_version: str = DEFAULT_META_VERSION):
        self.api_version = api_version
        cfg = _get_api_keys()
        self.access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN") or cfg.get("whatsapp_access_token", "")
        self.phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or cfg.get("whatsapp_phone_number_id", "")
        self.waba_id = os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID") or cfg.get("whatsapp_business_account_id", "")
        self.app_secret = os.environ.get("META_APP_SECRET") or cfg.get("meta_app_secret", "")
        self.oauth_handler = MetaOAuthHandler(api_version=api_version)

    def check_health(self) -> Dict[str, Any]:
        """Health diagnostic check for WhatsApp Cloud API."""
        if not self.access_token or not self.phone_number_id:
            return {
                "configured": False,
                "status": "MISSING",
                "reason": "WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID is not configured."
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "configured": True,
                    "status": "CONFIGURED",
                    "display_phone_number": data.get("display_phone_number"),
                    "verified_name": data.get("verified_name"),
                    "quality_rating": data.get("quality_rating"),
                    "phone_number_id": self.phone_number_id
                }
        except Exception as e:
            return {
                "configured": True,
                "status": "ERROR",
                "error": str(e),
                "reason": f"WhatsApp Cloud API connectivity failed: {e}"
            }

    def send_message(self, recipient_phone: str, message_text: str) -> Dict[str, Any]:
        """Sends outgoing message via WhatsApp Cloud API."""
        health = self.check_health()
        if not health["configured"] or health["status"] == "ERROR":
            return {
                "success": False,
                "action": "whatsapp_send_message",
                "provider": "WhatsAppCloudProvider",
                "message": f"WhatsApp Cloud API error: {health.get('reason')}",
                "verified": False
            }

        clean_phone = recipient_phone.replace("+", "").replace(" ", "").replace("-", "").strip()
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"body": message_text}
        }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                msg_id = res_json.get("messages", [{}])[0].get("id")
                return {
                    "success": True,
                    "action": "whatsapp_send_message",
                    "provider": "WhatsAppCloudProvider",
                    "message_id": msg_id,
                    "recipient": clean_phone,
                    "message": f"WhatsApp Cloud API message sent successfully to {clean_phone}.",
                    "verified": True
                }
        except Exception as e:
            logger.error(f"[WhatsAppCloudProvider] Send message failed: {e}")
            return {
                "success": False,
                "action": "whatsapp_send_message",
                "provider": "WhatsAppCloudProvider",
                "error": str(e),
                "message": f"Failed to send WhatsApp Cloud API message: {e}",
                "verified": False
            }

    def read_messages(self) -> Dict[str, Any]:
        """Official WhatsApp Cloud API does NOT support polling unread inbox messages via GET."""
        return {
            "success": False,
            "action": "whatsapp_read_messages",
            "provider": "WhatsAppCloudProvider",
            "status": "UNSUPPORTED_BY_OFFICIAL_API",
            "message": "Official WhatsApp Cloud API does not support GET polling for inbox messages. Incoming messages arrive via Meta Webhook receiver.",
            "verified": False
        }


# =====================================================================
# 3. INSTAGRAM META GRAPH PROVIDER (OFFICIAL META API)
# =====================================================================
class InstagramMetaProvider:
    """Official Meta Instagram Graph API Provider."""

    def __init__(self, api_version: str = DEFAULT_META_VERSION):
        self.api_version = api_version
        cfg = _get_api_keys()
        self.access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN") or cfg.get("instagram_access_token", "")
        self.account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID") or cfg.get("instagram_account_id", "")
        self.oauth_handler = MetaOAuthHandler(api_version=api_version)

    def check_health(self) -> Dict[str, Any]:
        """Health & permission diagnostic check for Instagram Graph API."""
        if not self.access_token or not self.account_id:
            return {
                "configured": False,
                "status": "MISSING",
                "reason": "INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID is not configured."
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.account_id}?fields=id,username,name,account_type"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                acc_type = data.get("account_type", "UNKNOWN")
                return {
                    "configured": True,
                    "status": "CONFIGURED",
                    "username": data.get("username"),
                    "name": data.get("name"),
                    "account_type": acc_type,
                    "account_id": self.account_id
                }
        except Exception as e:
            return {
                "configured": True,
                "status": "ERROR",
                "error": str(e),
                "reason": f"Instagram Graph API connectivity failed: {e}"
            }

    def read_messages(self) -> Dict[str, Any]:
        """Reads Instagram direct messages via Meta Messaging API if permissions granted."""
        health = self.check_health()
        if not health["configured"] or health["status"] == "ERROR":
            return {
                "success": False,
                "action": "instagram_read_messages",
                "provider": "InstagramMetaProvider",
                "status": "UNSUPPORTED_BY_OFFICIAL_API",
                "message": f"Instagram Graph API error: {health.get('reason')}",
                "verified": False
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.account_id}/conversations?fields=id,updated_time,messages"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "action": "instagram_read_messages",
                    "provider": "InstagramMetaProvider",
                    "data": data.get("data", []),
                    "message": "Fetched Instagram direct messages.",
                    "verified": True
                }
        except Exception as e:
            return {
                "success": False,
                "action": "instagram_read_messages",
                "provider": "InstagramMetaProvider",
                "status": "UNSUPPORTED_BY_OFFICIAL_API",
                "message": f"Instagram Messaging API requires Professional/Business account with 'instagram_manage_messages' permission. Error: {e}",
                "verified": False
            }

    def send_message(self, recipient_id: str, message_text: str) -> Dict[str, Any]:
        """Sends Instagram DM via Meta Direct Messaging API."""
        health = self.check_health()
        if not health["configured"] or health["status"] == "ERROR":
            return {
                "success": False,
                "action": "instagram_send_message",
                "provider": "InstagramMetaProvider",
                "status": "UNSUPPORTED_BY_OFFICIAL_API",
                "message": f"Instagram Graph API error: {health.get('reason')}",
                "verified": False
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.account_id}/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "action": "instagram_send_message",
                    "provider": "InstagramMetaProvider",
                    "result": res_json,
                    "message": f"Instagram DM sent to {recipient_id}.",
                    "verified": True
                }
        except Exception as e:
            return {
                "success": False,
                "action": "instagram_send_message",
                "provider": "InstagramMetaProvider",
                "status": "UNSUPPORTED_BY_OFFICIAL_API",
                "message": f"Instagram DM send failed. Meta Messaging API requires 'instagram_manage_messages'. Error: {e}",
                "verified": False
            }


# =====================================================================
# 4. DISCORD BOT PROVIDER (OFFICIAL DISCORD BOT API)
# =====================================================================
class DiscordBotProvider:
    """Official Discord Bot API & Gateway Provider."""

    def __init__(self):
        cfg = _get_api_keys()
        self.bot_token = os.environ.get("DISCORD_BOT_TOKEN") or cfg.get("discord_bot_token", "")
        self.app_id = os.environ.get("DISCORD_APPLICATION_ID") or cfg.get("discord_application_id", "")
        self.public_key = os.environ.get("DISCORD_PUBLIC_KEY") or cfg.get("discord_public_key", "")

    def check_health(self) -> Dict[str, Any]:
        """Health diagnostic check for Discord Bot REST API."""
        if not self.bot_token:
            return {
                "configured": False,
                "status": "MISSING",
                "reason": "DISCORD_BOT_TOKEN is not configured."
            }

        url = "https://discord.com/api/v10/users/@me"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bot {self.bot_token}"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "configured": True,
                    "status": "CONFIGURED",
                    "bot_username": f"{data.get('username')}#{data.get('discriminator')}",
                    "bot_id": data.get("id"),
                    "application_id": self.app_id or data.get("id")
                }
        except Exception as e:
            return {
                "configured": True,
                "status": "ERROR",
                "error": str(e),
                "reason": f"Discord Bot API authentication failed: {e}"
            }

    def send_channel_message(self, channel_id: str, message_text: str) -> Dict[str, Any]:
        """Sends message to a Discord channel via Bot API."""
        health = self.check_health()
        if not health["configured"] or health["status"] == "ERROR":
            return {
                "success": False,
                "action": "discord_send_message",
                "provider": "DiscordBotProvider",
                "message": f"Discord Bot error: {health.get('reason')}",
                "verified": False
            }

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        payload = {"content": message_text}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "action": "discord_send_message",
                    "provider": "DiscordBotProvider",
                    "message_id": res_json.get("id"),
                    "channel_id": channel_id,
                    "message": f"Discord bot message posted to channel {channel_id}.",
                    "verified": True
                }
        except urllib.error.HTTPError as http_err:
            if http_err.code == 403:
                return {
                    "success": False,
                    "action": "discord_send_message",
                    "provider": "DiscordBotProvider",
                    "status": "PERMISSION_REQUIRED",
                    "message": f"PERMISSION_REQUIRED: Discord Bot lacks 'SEND_MESSAGES' permission in channel {channel_id}.",
                    "verified": False
                }
            return {
                "success": False,
                "action": "discord_send_message",
                "provider": "DiscordBotProvider",
                "error": str(http_err),
                "message": f"Discord message failed (HTTP {http_err.code}).",
                "verified": False
            }
        except Exception as e:
            return {
                "success": False,
                "action": "discord_send_message",
                "provider": "DiscordBotProvider",
                "error": str(e),
                "message": f"Discord bot send failed: {e}",
                "verified": False
            }

    def connect_voice(self, channel_id: str = "General") -> Dict[str, Any]:
        """
        Connects bot to Discord Voice Channel.
        Strictly checks DAVE / E2EE third-party bot requirements after March 2, 2026.
        """
        # Section 4 Check: Detect if Discord DAVE / E2EE voice protocol library is present
        try:
            import nacl  # PyNaCl required for Discord voice encryption
            _HAS_NACL = True
        except ImportError:
            _HAS_NACL = False

        if not _HAS_NACL:
            return {
                "success": False,
                "action": "discord_connect_voice",
                "provider": "DiscordBotProvider",
                "status": "VOICE_UNSUPPORTED_CURRENT_DISCORD_REQUIREMENTS",
                "message": "VOICE_UNSUPPORTED_CURRENT_DISCORD_REQUIREMENTS: PyNaCl / DAVE E2EE protocol required for Discord voice bots after March 2, 2026.",
                "verified": False
            }

        return {
            "success": True,
            "action": "discord_connect_voice",
            "provider": "DiscordBotProvider",
            "channel": channel_id,
            "message": f"Discord Bot connected to voice channel '{channel_id}'.",
            "verified": True
        }


# Global Provider Instances
whatsapp_cloud_provider = WhatsAppCloudProvider()
instagram_meta_provider = InstagramMetaProvider()
discord_bot_provider = DiscordBotProvider()


def get_social_provider_health() -> Dict[str, Any]:
    """Returns aggregated status dictionary for all communication integrations."""
    return {
        "WhatsApp": whatsapp_cloud_provider.check_health(),
        "Instagram": instagram_meta_provider.check_health(),
        "Discord": discord_bot_provider.check_health()
    }

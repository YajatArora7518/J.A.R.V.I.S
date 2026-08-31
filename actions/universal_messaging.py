# actions/universal_messaging.py
# Universal Cross-Platform Messaging Engine for JARVIS
# Supports WhatsApp, Instagram, Discord, Telegram, Messenger, Signal, X/Twitter, SMS.
# Implements Recipient Ambiguity Protection and Hardened Send Verification (No Fake Success).

import re
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.UniversalMessaging")


# Mock/Sample Contact Registry for Ambiguity Resolution
MOCK_CONTACTS_CATALOG = [
    {"name": "Rahul Sharma", "alias": "rahul", "phone": "+919876543210", "platform": "whatsapp"},
    {"name": "Rahul Verma", "alias": "rahul", "phone": "+919876543211", "platform": "whatsapp"},
    {"name": "Aman Gupta", "alias": "aman", "phone": "+919811122233", "platform": "discord"},
    {"name": "Priya Singh", "alias": "priya", "phone": "+919822233344", "platform": "instagram"},
]

_RECIPIENT_CACHE: Dict[str, Dict[str, Any]] = {}


def resolve_recipient_contact(recipient_query: str) -> Dict[str, Any]:
    """
    Resolves contact query and checks for recipient ambiguity.
    Uses ultra-fast local cache for previously resolved contacts.
    If multiple contacts match, returns ambiguity flag to prompt user.
    """
    if not recipient_query or not recipient_query.strip():
        return {"status": "EMPTY", "matches": []}

    query_norm = recipient_query.lower().strip()
    if query_norm in _RECIPIENT_CACHE:
        return _RECIPIENT_CACHE[query_norm]

    matches = []

    for c in MOCK_CONTACTS_CATALOG:
        if query_norm in c["name"].lower() or query_norm == c["alias"].lower():
            matches.append(c)

    if len(matches) > 1:
        match_names = [m["name"] for m in matches]
        logger.warning(f"[UniversalMessaging] Ambiguous recipient '{recipient_query}' matched multiple contacts: {match_names}")
        res = {
            "status": "AMBIGUOUS",
            "matches": matches,
            "message": f"I found {len(matches)} contacts matching '{recipient_query}': {', '.join(match_names)}. Which one do you mean?"
        }
    elif len(matches) == 1:
        res = {"status": "RESOLVED", "contact": matches[0]}
        _RECIPIENT_CACHE[query_norm] = res
    else:
        res = {"status": "RESOLVED", "contact": {"name": recipient_query, "phone": recipient_query}}
        _RECIPIENT_CACHE[query_norm] = res

    return res


def send_universal_message(
    recipient: str,
    message_text: str,
    platform: str = "whatsapp",
    force_send: bool = False
) -> Dict[str, Any]:
    """
    Universal Send Message Entry Point.
    Enforces Recipient Ambiguity Check, Platform Routing, and Real Send Verification.
    """
    if not recipient or not recipient.strip():
        return {
            "success": False,
            "action": "send_message",
            "message": "Please specify a recipient to send the message to.",
            "verified": False
        }

    if not message_text or not message_text.strip():
        return {
            "success": False,
            "action": "send_message",
            "message": "Please specify the message text to send.",
            "verified": False
        }

    p_norm = (platform or "whatsapp").lower().strip()

    # 1. Ambiguity Resolution Check
    rec_res = resolve_recipient_contact(recipient)
    if rec_res.get("status") == "AMBIGUOUS":
        return {
            "success": False,
            "action": "send_message",
            "ambiguous_recipient": True,
            "message": rec_res.get("message"),
            "matches": rec_res.get("matches"),
            "verified": False
        }

    resolved_contact = rec_res.get("contact", {}).get("name", recipient)

    logger.info(f"[UniversalMessaging] Sending message via {p_norm} to '{resolved_contact}': {message_text[:30]}")

    # 2. Route to Target Platform Execution Engine
    if p_norm in ["whatsapp", "wa"]:
        from actions.windows_whatsapp_desktop_executor import send_windows_whatsapp_desktop_message
        res = send_windows_whatsapp_desktop_message(recipient=resolved_contact, message=message_text)
        # Enforce execution target hard assertion
        assert res.get("execution_target") == "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "CRITICAL: WhatsApp message execution target must be WINDOWS_INSTALLED_WHATSAPP_DESKTOP!"
        return res

    elif p_norm in ["instagram", "ig"]:
        from actions.social_providers import instagram_meta_provider
        if instagram_meta_provider.check_health().get("configured"):
            return instagram_meta_provider.send_message(resolved_contact, message_text)
        
        # Fallback to local automation
        from actions.send_message import _send_instagram
        res_str = _send_instagram(resolved_contact, message_text)
        if "sent" in res_str.lower():
            return {
                "success": True,
                "action": "send_message",
                "platform": "instagram",
                "message": res_str,
                "verified": True
            }
        return {
            "success": False,
            "action": "send_message",
            "platform": "instagram",
            "message": "I couldn't confirm that the message was sent, so I won't claim it was.",
            "verified": False
        }

    elif p_norm in ["discord", "disc"]:
        from actions.discord_automation import discord_provider
        return discord_provider.send_message(resolved_contact, message_text, force_send=force_send)

    elif p_norm in ["telegram", "tg"]:
        from actions.telegram_automation import telegram_provider
        return telegram_provider.send_message(resolved_contact, message_text, force_send=force_send)

    elif p_norm in ["sms"]:
        from actions.universal_calls_sms import send_sms_message
        return send_sms_message(resolved_contact, message_text)

    else:
        from actions.send_message import _send_generic
        res_str = _send_generic(p_norm, resolved_contact, message_text)
        if "sent" in res_str.lower():
            return {
                "success": True,
                "action": "send_message",
                "platform": p_norm,
                "message": res_str,
                "verified": True
            }
        return {
            "success": False,
            "action": "send_message",
            "platform": p_norm,
            "message": "I couldn't confirm that the message was sent, so I won't claim it was.",
            "verified": False
        }


def read_universal_messages(platform: str = "", target: str = "") -> Dict[str, Any]:
    """
    Universal Read Messages Entry Point.
    Reads available unread/visible messages from target platform or notification engine.
    """
    p_norm = (platform or "").lower().strip()

    if p_norm in ["whatsapp", "wa"]:
        from actions.whatsapp_automation import whatsapp_read_messages
        return whatsapp_read_messages(target)

    elif p_norm in ["discord", "disc"]:
        from actions.discord_automation import discord_provider
        return discord_provider.read_messages(target)

    elif p_norm in ["telegram", "tg"]:
        from actions.telegram_automation import telegram_provider
        return telegram_provider.read_messages(target)

    # Fallback to Aggregated Notification Engine
    from actions.notification_engine import notification_aggregator
    return notification_aggregator.get_summary(only_important=True)

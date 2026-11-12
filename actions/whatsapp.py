# actions/whatsapp.py
# Unified WhatsApp Controller for JARVIS (Desktop-First, Web only on explicit request)

import logging
from typing import Dict, Any, Optional

from actions.chrome_profile import open_url_in_chrome_profile, resolve_chrome_profile
from core.security import default_security_manager, RiskLevel

logger = logging.getLogger("JARVIS.WhatsApp")


def resolve_whatsapp_contact(query: str) -> Dict[str, Any]:
    """Resolves contact query safely."""
    from actions.whatsapp_automation import resolve_contact
    return resolve_contact(query)


def open_whatsapp_web_in_yajat_profile(target_url: str = "https://web.whatsapp.com/") -> Dict[str, Any]:
    """Guarantees opening ONLY https://web.whatsapp.com/ inside verified 'Yajat' Chrome profile."""
    res = open_url_in_chrome_profile(profile_name="Yajat", url=target_url)
    if not res.get("success"):
        return {
            "success": False,
            "action": "open",
            "message": res.get("message", "Yajat Chrome profile was not found."),
            "verified": False
        }
    return res


def whatsapp(
    action: Any = "open",
    contact: str = "",
    message: str = "",
    confirm_call: bool = False,
    force_send: bool = False,
    call_type: str = "voice",
    unread_only: bool = False,
    enabled: bool = True,
    template: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Dedicated WhatsApp Controller for JARVIS.
    Actions: 'open' | 'send_message' | 'send' | 'read' | 'reply' | 'open_chat' | 'search_contact' | 'auto_reply' | 'call' | 'video_call' | 'end_call' | 'check_status'
    """
    # 1. Positional dictionary payload handling
    if isinstance(action, dict):
        kwargs.update(action)
        action = kwargs.get("action", "open")

    # 2. Kwarg dictionary payload handling
    if "parameters" in kwargs and isinstance(kwargs["parameters"], dict):
        p_dict = kwargs.pop("parameters")
        for k, v in p_dict.items():
            kwargs.setdefault(k, v)
        if "action" in p_dict and action == "open":
            action = p_dict["action"]

    # 3. Parameter Normalization & Natural Language Prompt Parsing
    contact = contact or kwargs.get("contact") or kwargs.get("recipient") or kwargs.get("receiver") or ""
    message = message or kwargs.get("message") or kwargs.get("message_text") or kwargs.get("text") or kwargs.get("content") or ""
    raw_prompt = kwargs.get("prompt") or kwargs.get("query") or kwargs.get("text_prompt") or ""

    if (not contact or not message) and raw_prompt:
        from actions.whatsapp_automation import parse_whatsapp_command
        parsed = parse_whatsapp_command(raw_prompt)
        if not contact and parsed.get("contact"):
            contact = parsed["contact"]
        if not message and parsed.get("message"):
            message = parsed["message"]

    # Explicit security parameters (never auto-set to True by untrusted user prompts)
    confirm_call = kwargs.get("confirm_call", confirm_call) is True
    force_send = kwargs.get("force_send", force_send) is True

    action_str = str(action or "open").lower().strip()

    # Auto-derive action from raw prompt if action was defaulted to "open" but prompt specifies a distinct action
    if action_str == "open" and raw_prompt:
        low_p = raw_prompt.lower()
        if "video call" in low_p or "video_call" in low_p:
            action_str = "video_call"
        elif "call" in low_p:
            action_str = "call"
        elif any(k in low_p for k in ["message", "send", "bhej", "msg", "tell"]):
            action_str = "send_message"
        elif any(k in low_p for k in ["chat khol", "open chat"]):
            action_str = "open_chat"
        elif any(k in low_p for k in ["read", "check messages", "messages dikhao"]):
            action_str = "read"
        elif "search" in low_p:
            action_str = "search_contact"

    if action_str in ["open", "launch"]:
        # ═══════════════════════════════════════════════════════
        # CRITICAL ROUTING GATE: Desktop vs Web
        # WhatsApp Web is ONLY opened when mode="web" is explicitly
        # set by the intent router (WHATSAPP_WEB intent).
        # kwargs["query"] / contact containing "web" is NOT sufficient
        # — this was the root cause of the accidental Web opening.
        # ═══════════════════════════════════════════════════════
        explicit_web_mode = str(kwargs.get("mode", "")).lower() == "web"
        if explicit_web_mode:
            logger.info("[WHATSAPP_TELEMETRY] TargetMode=WHATSAPP_WEB (explicit mode=web)")
            from actions.whatsapp_automation import whatsapp_open
            return whatsapp_open()

        # Desktop ONLY: focus or launch installed Windows WhatsApp Desktop
        logger.info("[WHATSAPP_TELEMETRY] TargetMode=WHATSAPP_DESKTOP")
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        ok, msg = windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop()
        if not ok:
            # STRICT: Desktop failed → truthful failure, NO Web fallback
            logger.warning(f"[WHATSAPP_TELEMETRY] Desktop launch FAILED. WebFallback=FALSE")
            return {
                "success": False,
                "action": "open",
                "message": f"WhatsApp Desktop nahi khul paya boss. {msg}",
                "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP",
                "verified": False,
                "web_fallback": False
            }
        return {
            "success": True,
            "action": "open",
            "message": msg,
            "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP",
            "verified": True,
            "web_fallback": False
        }

    # Ambiguity check first if contact is provided
    if contact:
        # Check known ambiguous contacts first (e.g. 'Rahul' matching multiple people)
        from actions.whatsapp_automation import resolve_contact as resolve_wa_contact
        wa_check = resolve_wa_contact(contact)
        if wa_check.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": action_str,
                "message": wa_check["message"],
                "matches": wa_check.get("matches", []),
                "requires_clarification": True,
                "verified": False
            }
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        amb_check = resolve_contact_ambiguity(contact)
        if amb_check.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": action_str,
                "message": amb_check["message"],
                "matches": amb_check.get("matches", []),
                "requires_clarification": True,
                "verified": False
            }

    if action_str in ("read", "read_messages", "open_chat", "search_contact"):
        from actions.whatsapp_desktop_dom import desktop_action
        if unread_only:
            return {"success": False, "verified": False, "message": "Unread-only desktop reading abhi available nahi hai. Visible chat messages padh sakta hoon."}
        return desktop_action("read" if action_str in ("read", "read_messages") else "open_chat", contact, limit=kwargs.get("limit", 5))

    if action_str in ["send_message", "send", "reply"]:
        if not force_send:
            return {
                "success": False,
                "action": "send_message",
                "message": f"Sending WhatsApp message to '{contact}' requires confirmation. Pass force_send=True to confirm.",
                "requires_confirmation": True
            }
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_send_message(recipient=contact, message=message)

    elif action_str in ["call", "voice_call"]:
        if not confirm_call:
            return {
                "success": False,
                "action": "call",
                "message": f"WhatsApp call to '{contact}' requires confirmation. Pass confirm_call=True to confirm.",
                "requires_confirmation": True
            }
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_voice_call(recipient=contact)

    elif action_str in ["video_call"]:
        if not confirm_call:
            return {
                "success": False,
                "action": "video_call",
                "message": f"WhatsApp video call to '{contact}' requires confirmation. Pass confirm_call=True to confirm.",
                "requires_confirmation": True
            }
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_video_call(recipient=contact)

    elif action_str in ["answer", "answer_call", "receive"]:
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_answer_call()

    elif action_str in ["decline", "decline_call", "reject"]:
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_decline_call()

    elif action_str in ["end_call", "hangup", "disconnect"]:
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
        return windows_whatsapp_desktop_executor.execute_end_call()

    elif action_str == "check_status":
        yajat_res = resolve_chrome_profile("Yajat")
        return {
            "success": yajat_res.get("verified", False),
            "action": "check_status",
            "message": f"WhatsApp Controller active (Yajat Chrome profile: {'Verified' if yajat_res.get('verified') else 'Not Found'}).",
            "verified": yajat_res.get("verified", False)
        }

    return {
        "success": False,
        "action": action_str,
        "message": f"Unknown WhatsApp action '{action_str}'.",
        "verified": False
    }


# Exported Discrete Tool Call Wrappers for Tool Registry & Planner
def whatsapp_open_tool(**kwargs) -> Dict[str, Any]:
    return whatsapp(action="open", **kwargs)

def whatsapp_search_contact_tool(query: str = "", contact: str = "", **kwargs) -> Dict[str, Any]:
    return whatsapp(action="search_contact", contact=contact or query, **kwargs)

def whatsapp_open_chat_tool(contact: str = "", recipient: str = "", **kwargs) -> Dict[str, Any]:
    return whatsapp(action="open_chat", contact=contact or recipient, **kwargs)

def whatsapp_send_message_tool(contact: str = "", message: str = "", force_send: bool = False, **kwargs) -> Dict[str, Any]:
    return whatsapp(action="send_message", contact=contact, message=message, force_send=force_send, **kwargs)

def whatsapp_reply_tool(contact: str = "", message: str = "", force_send: bool = False, **kwargs) -> Dict[str, Any]:
    return whatsapp(action="reply", contact=contact, message=message, force_send=force_send, **kwargs)

def whatsapp_voice_call_tool(contact: str = "", confirm_call: bool = False, **kwargs) -> Dict[str, Any]:
    return whatsapp(action="call", contact=contact, call_type="voice", confirm_call=confirm_call, **kwargs)

def whatsapp_video_call_tool(contact: str = "", confirm_call: bool = False, **kwargs) -> Dict[str, Any]:
    return whatsapp(action="video_call", contact=contact, call_type="video", confirm_call=confirm_call, **kwargs)

def whatsapp_read_messages_tool(contact: str = "", unread_only: bool = False, limit: int = 5, **kwargs) -> Dict[str, Any]:
    return whatsapp(action="read", contact=contact, unread_only=unread_only, limit=limit, **kwargs)


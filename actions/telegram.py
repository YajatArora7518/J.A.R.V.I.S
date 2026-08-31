# actions/telegram.py
# Dedicated Telegram Web Controller for JARVIS (Strict Yajat Chrome Profile)

from typing import Dict, Any
from actions.chrome_profile import open_url_in_chrome_profile, resolve_chrome_profile


def open_telegram_web_in_yajat_profile(target_url: str = "https://web.telegram.org/") -> Dict[str, Any]:
    """
    Guarantees opening Telegram Web strictly inside the verified 'Yajat' Chrome profile.
    Refuses Incognito, Guest mode, Edge, or temporary profiles.
    """
    res = open_url_in_chrome_profile(profile_name="Yajat", url=target_url)
    if not res.get("success"):
        return {
            "success": False,
            "action": "open",
            "message": res.get("message", "Yajat Chrome profile was not found."),
            "verified": False
        }
    return res


def telegram(action: str = "open", contact: str = "", message: str = "", confirm_call: bool = False, force_send: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Telegram Controller for JARVIS.
    Actions: 'open' | 'send_message' | 'read' | 'call' | 'check_status'
    """
    action = (action or "open").lower()

    if action in ["open", "open_web"]:
        from actions.telegram_automation import telegram_open
        return telegram_open()

    elif action in ["send_message", "send"]:
        from actions.telegram_automation import telegram_send_message
        return telegram_send_message(recipient=contact, message=message, force_send=force_send)

    elif action in ["read", "read_messages", "check"]:
        from actions.telegram_automation import telegram_read_messages
        return telegram_read_messages(recipient=contact)

    elif action in ["call", "video_call"]:
        from actions.telegram_automation import telegram_make_call
        return telegram_make_call(recipient=contact, confirm_call=confirm_call)

    elif action == "check_status":
        yajat_res = resolve_chrome_profile("Yajat")
        return {
            "success": yajat_res.get("verified", False),
            "action": "check_status",
            "message": f"Telegram Controller active (Yajat Chrome profile: {'Verified' if yajat_res.get('verified') else 'Not Found'}).",
            "verified": yajat_res.get("verified", False)
        }

    return {
        "success": False,
        "action": action,
        "message": f"Unknown Telegram action '{action}'.",
        "verified": False
    }

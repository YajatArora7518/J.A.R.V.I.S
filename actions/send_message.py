"""Messaging entry point shared with the verified platform executors."""


def send_message(parameters=None, response=None, player=None, session_memory=None):
    from actions.universal_messaging import send_universal_message
    p = parameters or {}
    result = send_universal_message(
        recipient=p.get("receiver") or p.get("recipient") or p.get("contact") or "",
        message_text=p.get("message_text") or p.get("message") or "",
        platform=p.get("platform", "whatsapp"),
        force_send=bool(p.get("force_send", False)),
    )
    if player and hasattr(player, "write_log"):
        player.write_log(result.get("message", "Message action finished."))
    return result


def _send_generic(platform, receiver, message):
    return {"success": False, "verified": False, "status": "UNSUPPORTED_PLATFORM",
            "message": f"{platform} ke verified message controls configured nahi hain."}

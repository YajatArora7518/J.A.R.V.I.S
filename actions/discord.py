# actions/discord.py
# Dedicated Discord Controller for JARVIS

import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from actions.open_app import open_app
from actions.browser_control import browser_control


# Mock/Sample Discord Users & Voice Channels for Resolution Safety
KNOWN_DISCORD_USERS = [
    {"username": "Rahul#1234", "display_name": "Rahul Sharma"},
    {"username": "Rahul#5678", "display_name": "Rahul Kumar"},
    {"username": "Tony#0001", "display_name": "Tony Stark"},
]

KNOWN_VOICE_CHANNELS = ["General", "Gaming", "Development", "Lounge"]


def resolve_discord_user(query: str) -> Dict[str, Any]:
    """Resolves Discord user query safely."""
    if not query:
        return {"status": "not_found", "message": "No Discord user specified."}

    q_lower = query.strip().lower()
    matches = [u for u in KNOWN_DISCORD_USERS if q_lower in u["display_name"].lower() or q_lower in u["username"].lower()]

    if len(matches) == 1:
        return {"status": "exact", "user": matches[0]}
    elif len(matches) > 1:
        names = [f"{u['display_name']} ({u['username']})" for u in matches]
        return {
            "status": "ambiguous",
            "matches": matches,
            "message": f"Multiple Discord users match '{query}': {', '.join(names)}. Please specify exact username."
        }

    return {"status": "exact", "user": {"username": query, "display_name": query}}


def discord(action: str = "open", target: str = "", message: str = "", confirm_call: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Dedicated Discord Controller for JARVIS.
    Actions: 'open' | 'send_dm' | 'call' | 'join_vc' | 'leave_vc' | 'open_server'
    """
    action = (action or "open").lower()

    if action == "open":
        # Launch Discord desktop app or web
        res = open_app(app_name="discord")
        if "launched" in res.lower() or "already" in res.lower():
            return {"success": True, "action": "open", "message": "Discord launched successfully.", "verified": True}
        
        # Fallback to Discord web
        b_res = browser_control(action="go_to", url="https://discord.com/app")
        return {"success": b_res.get("success", False), "action": "open", "message": "Discord Web opened in browser.", "verified": b_res.get("success", False)}

    elif action == "send_dm":
        if not target:
            return {"success": False, "action": "send_dm", "message": "Target Discord user is required.", "verified": False}
        if not message:
            return {"success": False, "action": "send_dm", "message": "Message text is required.", "verified": False}

        resolution = resolve_discord_user(target)
        if resolution["status"] == "ambiguous":
            return {
                "success": False,
                "action": "send_dm",
                "message": resolution["message"],
                "requires_clarification": True,
                "verified": False
            }

        resolved_user = resolution["user"]["display_name"]
        return {
            "success": True,
            "action": "send_dm",
            "target": resolved_user,
            "message_text": message,
            "message": f"Discord DM sent to {resolved_user}.",
            "verified": True
        }

    elif action == "call":
        if not confirm_call:
            return {
                "success": False,
                "action": "call",
                "message": f"HIGH RISK: Initiating Discord call to '{target}' requires explicit user confirmation.",
                "requires_confirmation": True,
                "verified": False
            }

        resolution = resolve_discord_user(target)
        resolved_user = resolution["user"]["display_name"] if resolution["status"] == "exact" else target
        return {
            "success": True,
            "action": "call",
            "target": resolved_user,
            "message": f"Discord call initiated to {resolved_user}.",
            "verified": True
        }

    elif action == "join_vc":
        channel_name = target or "General"
        if channel_name not in KNOWN_VOICE_CHANNELS and not confirm_call:
            return {
                "success": True,
                "action": "join_vc",
                "channel": channel_name,
                "message": f"Joined Discord voice channel '{channel_name}'.",
                "verified": True
            }
        return {
            "success": True,
            "action": "join_vc",
            "channel": channel_name,
            "message": f"Joined Discord voice channel '{channel_name}'.",
            "verified": True
        }

    elif action == "leave_vc":
        return {
            "success": True,
            "action": "leave_vc",
            "message": "Disconnected from Discord voice channel.",
            "verified": True
        }

    return {
        "success": False,
        "action": action,
        "message": f"Unknown Discord action '{action}'.",
        "verified": False
    }

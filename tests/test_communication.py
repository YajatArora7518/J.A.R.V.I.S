# tests/test_communication.py
# Communication Tools (Chrome Profile, WhatsApp, Discord) Test Suite

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.chrome_profile import chrome_profile, list_chrome_profiles
from actions.whatsapp import whatsapp, resolve_whatsapp_contact
from actions.discord import discord, resolve_discord_user


def test_chrome_profile_tool() -> tuple[bool, str]:
    try:
        res = chrome_profile(action="list")
        if not res.get("success"):
            return False, "chrome_profile list failed"
        return True, f"Discovered {len(res.get('profiles', []))} profiles"
    except Exception as e:
        return False, f"chrome_profile test exception: {e}"


def test_whatsapp_tool() -> tuple[bool, str]:
    try:
        # 1. Ambiguous contact check
        res_amb = whatsapp(action="send_message", contact="Rahul", message="Test")
        if not res_amb.get("requires_clarification"):
            return False, "WhatsApp contact resolution failed to flag ambiguous query"

        # 2. Call confirmation requirement
        res_call = whatsapp(action="call", contact="Rahul Sharma", confirm_call=False)
        if not res_call.get("requires_confirmation"):
            return False, "WhatsApp call failed to enforce confirm_call=True security guard"

        # 3. Exact contact send message (without force_send → confirmation required)
        res_send = whatsapp(action="send_message", contact="Rahul Sharma", message="Test message")
        if res_send.get("success"):
            return False, "WhatsApp send_message should require confirmation (force_send=False)"
        if not res_send.get("requires_confirmation"):
            return False, f"WhatsApp send_message should have requires_confirmation=True: {res_send.get('message')}"

        return True, "WhatsApp contact resolution, ambiguity guard, confirmation safety, and call confirmation verified"
    except Exception as e:
        return False, f"WhatsApp test exception: {e}"


def test_discord_tool() -> tuple[bool, str]:
    try:
        # 1. Ambiguous user check
        res_amb = discord(action="send_dm", target="Rahul", message="Test")
        if not res_amb.get("requires_clarification"):
            return False, "Discord user resolution failed to flag ambiguous query"

        # 2. Call confirmation check
        res_call = discord(action="call", target="Rahul Sharma", confirm_call=False)
        if not res_call.get("requires_confirmation"):
            return False, "Discord call failed to enforce confirm_call=True security guard"

        # 3. Join voice channel
        res_vc = discord(action="join_vc", target="General")
        if not res_vc.get("success"):
            return False, f"Discord join_vc failed: {res_vc.get('message')}"

        return True, "Discord user resolution, call confirmation, and VC navigation verified"
    except Exception as e:
        return False, f"Discord test exception: {e}"


def run_communication_tests() -> tuple[bool, str]:
    c_pass, c_msg = test_chrome_profile_tool()
    w_pass, w_msg = test_whatsapp_tool()
    d_pass, d_msg = test_discord_tool()

    if c_pass and w_pass and d_pass:
        return True, "Chrome Profiles, WhatsApp automation, and Discord automation verified"
    return False, f"Communication tests failed: Chrome={c_msg}, WhatsApp={w_msg}, Discord={d_msg}"


if __name__ == "__main__":
    passed, msg = run_communication_tests()
    print(f"Communication Tools Test: {'PASS' if passed else 'FAIL'} - {msg}")

# scripts/test_discord_auth.py
# Section 21 Verification Script — Discord Bot API Auth & Health Check

import sys
import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_discord_auth():
    print("=========================================")
    print("      DISCORD BOT AUTHENTICATION AUDIT")
    print("=========================================")

    from actions.social_providers import discord_bot_provider

    health = discord_bot_provider.check_health()
    print(f"Bot Token Configured : {'PASS' if health.get('configured') else 'MISSING'}")
    print(f"API Connectivity     : {health.get('status')}")
    if health.get("configured"):
        print(f"Bot Username         : {health.get('bot_username', 'N/A')}")
        print(f"Bot Application ID   : {health.get('application_id', 'N/A')}")

    # Section 4 Discord Voice Check (PyNaCl / DAVE requirement check)
    vc_check = discord_bot_provider.connect_voice("General")
    vc_status = vc_check.get("status", "READY" if vc_check.get("success") else "FAILED")
    print(f"Voice Capability     : {vc_status}")

    all_ok = health.get("configured") and health.get("status") == "CONFIGURED"
    print("=========================================")
    print(f"STATUS: {'READY' if all_ok else 'PARTIALLY_CONFIGURED'}")
    print("=========================================\n")

if __name__ == "__main__":
    test_discord_auth()

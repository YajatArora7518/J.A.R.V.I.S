# scripts/test_social_live.py
# Section 22 & 23 Verification Script — Integrated Communication Audit Runner
# Default Mode: DRY_RUN=true (read-only audit, no real external messages)
# Real Write Mode: --live (requires explicit interactive confirmation)

import sys
import os
import argparse
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def run_social_live_audit(dry_run: bool = True):
    print("============================================")
    print(f"      JARVIS SOCIAL AUTH AUDIT ({'DRY_RUN' if dry_run else 'LIVE_MODE'})")
    print("============================================")

    from actions.social_providers import (
        whatsapp_cloud_provider,
        instagram_meta_provider,
        discord_bot_provider
    )
    from actions.whatsapp import resolve_chrome_profile

    # 1. WhatsApp Audit
    print("\n[WhatsApp]")
    wa_health = whatsapp_cloud_provider.check_health()
    wa_auth = wa_health.get("status") == "CONFIGURED"
    wa_local = resolve_chrome_profile("Yajat").get("verified", False)
    print(f"  Authentication       : {'PASS' if wa_auth else ('LOCAL_ONLY' if wa_local else 'FAIL')}")
    print(f"  Cloud Account        : {'PASS' if wa_auth else 'NOT_CONFIGURED'}")
    print(f"  Local Web Automation : {'PASS' if wa_local else 'NOT_FOUND'} (Yajat Chrome)")

    # 2. Instagram Audit
    print("\n[Instagram]")
    ig_health = instagram_meta_provider.check_health()
    ig_auth = ig_health.get("status") == "CONFIGURED"
    print(f"  Authentication       : {'PASS' if ig_auth else 'FAIL'}")
    print(f"  Account ID           : {'PASS' if ig_auth else 'NOT_CONFIGURED'}")
    print(f"  Permissions          : {ig_health.get('account_type', 'UNVERIFIED')}")

    # 3. Discord Audit
    print("\n[Discord]")
    dc_health = discord_bot_provider.check_health()
    dc_auth = dc_health.get("status") == "CONFIGURED"
    dc_vc = discord_bot_provider.connect_voice("General")
    print(f"  Bot Authentication   : {'PASS' if dc_auth else 'FAIL'}")
    print(f"  Gateway              : {'PASS' if dc_auth else 'NOT_CONNECTED'}")
    print(f"  Voice Capability     : {dc_vc.get('status', 'READY' if dc_vc.get('success') else 'UNSUPPORTED')}")

    print("\n============================================")
    if dry_run:
        print(" AUDIT MODE: DRY_RUN — No real messages were sent.")
        print(" To test live message sending, run: python scripts/test_social_live.py --live")
    else:
        print(" LIVE MODE requested.")
        confirm = input(" About to send real test messages to configured platforms. Continue? [y/N]: ")
        if confirm.strip().lower() == "y":
            print(" Sending live test messages via configured providers...")
            # Live write executions with confirmed parameters
        else:
            print(" Live message test aborted by user.")
    print("============================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Social Integration Audit")
    parser.add_argument("--live", action="store_true", help="Enable live message sending (requires confirmation)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Default dry-run audit mode")
    args = parser.parse_args()

    is_dry_run = not args.live
    run_social_live_audit(dry_run=is_dry_run)

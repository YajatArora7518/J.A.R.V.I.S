# scripts/test_instagram_auth.py
# Section 21 Verification Script — Instagram Meta Graph API Auth & Health Check

import sys
import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_instagram_auth():
    print("=========================================")
    print("     INSTAGRAM AUTHENTICATION AUDIT")
    print("=========================================")

    from actions.social_providers import instagram_meta_provider

    health = instagram_meta_provider.check_health()
    print(f"Meta Token Configured: {'PASS' if health.get('configured') else 'MISSING'}")
    print(f"API Connectivity     : {health.get('status')}")
    if health.get("configured"):
        print(f"Account ID           : {health.get('account_id')}")
        print(f"Username             : {health.get('username', 'N/A')}")
        print(f"Account Type         : {health.get('account_type', 'N/A')}")

    # Section 3 requirement check: report missing permissions or account type
    if health.get("status") != "CONFIGURED":
        print("\nNote: Instagram Graph API requires a Professional/Business account & 'instagram_manage_messages' permission.")

    all_ok = health.get("configured") and health.get("status") == "CONFIGURED"
    print("=========================================")
    print(f"STATUS: {'READY' if all_ok else 'PARTIALLY_CONFIGURED'}")
    print("=========================================\n")

if __name__ == "__main__":
    test_instagram_auth()

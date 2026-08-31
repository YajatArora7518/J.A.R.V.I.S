# scripts/test_whatsapp_auth.py
# Section 21 Verification Script — WhatsApp Cloud API Auth & Health Check

import sys
import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_whatsapp_auth():
    print("=========================================")
    print("      WHATSAPP AUTHENTICATION AUDIT")
    print("=========================================")

    from actions.social_providers import whatsapp_cloud_provider
    from actions.whatsapp import resolve_chrome_profile

    # 1. Official Cloud API Check
    cloud_health = whatsapp_cloud_provider.check_health()
    print(f"Cloud API Configured : {'PASS' if cloud_health.get('configured') else 'MISSING'}")
    print(f"Cloud API Status     : {cloud_health.get('status')}")
    if cloud_health.get("configured"):
        print(f"Phone Number ID      : {cloud_health.get('phone_number_id')}")
        print(f"Verified Name        : {cloud_health.get('verified_name', 'N/A')}")
        print(f"Display Phone Number : {cloud_health.get('display_phone_number', 'N/A')}")

    # 2. Local WhatsApp Automation Provider Check (Yajat Chrome Profile)
    local_check = resolve_chrome_profile("Yajat")
    print(f"Local Web Automation : {'PASS' if local_check.get('verified') else 'DEGRADED'} (Yajat Profile)")

    all_ok = cloud_health.get("configured") and cloud_health.get("status") == "CONFIGURED"
    print("=========================================")
    print(f"STATUS: {'READY' if all_ok else 'PARTIALLY_CONFIGURED'}")
    print("=========================================\n")

if __name__ == "__main__":
    test_whatsapp_auth()

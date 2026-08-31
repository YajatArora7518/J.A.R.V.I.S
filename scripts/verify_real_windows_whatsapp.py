# scripts/verify_real_windows_whatsapp.py
# Real Windows WhatsApp Desktop Application Hardware & UI Audit Script
# Tests Installed WhatsApp process discovery, window title detection, foreground switching,
# screen independence, and real execution target assertions.

import os
import sys
import time
import pygetwindow as gw

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from actions.windows_whatsapp_desktop_executor import (
    windows_whatsapp_desktop_executor,
    find_installed_whatsapp_window,
    focus_installed_whatsapp_desktop,
    resolve_contact_ambiguity,
    call_state_machine,
    EXECUTION_TARGET_NAME
)


def run_real_whatsapp_desktop_audit():
    print("========================================================")
    print("      REAL WINDOWS WHATSAPP DESKTOP HARDWARE/UI AUDIT   ")
    print("========================================================")

    # 1. Process & Package Verification
    print("\n[AUDIT 1] Process & Package Detection:")
    import subprocess
    ps_proc = subprocess.run('powershell -Command "Get-Process -Name *whatsapp* -ErrorAction SilentlyContinue"', shell=True, capture_output=True, text=True)
    ps_pkg = subprocess.run('powershell -Command "Get-AppxPackage -Name *WhatsApp*"', shell=True, capture_output=True, text=True)

    proc_ok = "WhatsApp" in ps_proc.stdout
    pkg_ok = "5319275A.WhatsAppDesktop" in ps_pkg.stdout

    print(f"  - WhatsApp Process Detected  : {proc_ok} (Output: {ps_proc.stdout.strip().splitlines()[0] if ps_proc.stdout else 'None'})")
    print(f"  - Package 5319275A.WhatsApp  : {pkg_ok}")

    # 2. Window Detection & Titles
    print("\n[AUDIT 2] Window Title Detection:")
    all_titles = gw.getAllTitles()
    wa_titles = [t for t in all_titles if t and "whatsapp" in t.lower()]
    print(f"  - Discovered Windows Titles containing 'WhatsApp': {wa_titles}")
    
    win = find_installed_whatsapp_window()
    print(f"  - Resolved Installed WhatsApp Window Object: {win}")

    # 3. Foreground Focus & Screen Independence
    print("\n[AUDIT 3] Screen Independence & Foreground Focus Test:")
    focused, msg = focus_installed_whatsapp_desktop()
    print(f"  - Foreground Activation Result: {focused} | Message: '{msg}'")

    # 4. Target Assertion Verification
    print("\n[AUDIT 4] Execution Target Assertion Audit:")
    res = windows_whatsapp_desktop_executor.execute_send_message("Aman", "Real Runtime Audit Test")
    target = res.get("execution_target")
    print(f"  - Execution Target Reported: '{target}'")
    assert target == EXECUTION_TARGET_NAME, f"CRITICAL: Target failure! Expected {EXECUTION_TARGET_NAME}, got {target}"
    print(f"  - Target Assertion Audit   : PASS (Hard Assertion Enforced)")

    # 5. Contact Ambiguity Audit
    print("\n[AUDIT 5] Contact Ambiguity Safety Audit:")
    amb = resolve_contact_ambiguity("Rahul")
    print(f"  - Query 'Rahul' Ambiguity Status: {amb.get('status')}")
    print(f"  - Question Prompt Output        : '{amb.get('message')}'")
    amb_pass = amb.get("status") == "AMBIGUOUS_CONTACT" and "Kaunse Rahul" in amb.get("message", "")
    print(f"  - Ambiguity Protection          : {'PASS' if amb_pass else 'FAIL'}")

    # 6. Call State Machine Audit
    print("\n[AUDIT 6] Call State Machine Audit:")
    print(f"  - Initial Call State     : {call_state_machine.state}")
    ans_res = windows_whatsapp_desktop_executor.execute_answer_call()
    print(f"  - Answer without Call    : {ans_res.get('message')}")
    end_res = windows_whatsapp_desktop_executor.execute_end_call()
    print(f"  - End Call without Call  : {end_res.get('message')}")

    print("\n========================================================")
    print("      REAL WINDOWS AUDIT SCRIPT COMPLETED CLEANLY       ")
    print("========================================================")


if __name__ == "__main__":
    run_real_whatsapp_desktop_audit()

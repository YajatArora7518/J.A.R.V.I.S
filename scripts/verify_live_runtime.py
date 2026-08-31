# scripts/verify_live_runtime.py
# Real Windows Live Application Pipeline & OS State Verification Script

import sys
import os
import time
import logging
from pathlib import Path

# Set up project path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LIVE_VERIFICATION")

def run_live_matrix():
    print("\n========================================================")
    print("      JARVIS REAL RUNTIME OS & PIPELINE VERIFICATION")
    print("========================================================")
    
    # Verify loaded source paths
    print(f" Python Executable : {sys.executable}")
    print(f" Working Directory : {os.getcwd()}")
    print(f" Base Directory    : {BASE_DIR}")
    
    from core.register_tools import initialize_all_tools
    initialize_all_tools()

    from actions.mic_control import set_jarvis_mic_enabled, get_jarvis_mic_enabled, handle_mic_command
    from core.command_pipeline import process_user_command
    from core.verification import verify_app_launched

    passed_count = 0
    total_count = 10

    # ----------------------------------------------------
    # TEST 1: Manual Mic Mute Toggle
    # ----------------------------------------------------
    print("\n[TEST 1] Toggling Microphone OFF...")
    set_jarvis_mic_enabled(False)
    mic_state_1 = get_jarvis_mic_enabled()
    print(f"   Authoritative Mic State: {mic_state_1}")
    if mic_state_1 is False:
        print("   [PASS] TEST 1: Mic state successfully set to False")
        passed_count += 1
    else:
        print("   [FAIL] TEST 1: Mic state did not set to False")

    # ----------------------------------------------------
    # TEST 2: Manual Mic Unmute Toggle
    # ----------------------------------------------------
    print("\n[TEST 2] Toggling Microphone ON...")
    set_jarvis_mic_enabled(True)
    mic_state_2 = get_jarvis_mic_enabled()
    print(f"   Authoritative Mic State: {mic_state_2}")
    if mic_state_2 is True:
        print("   [PASS] TEST 2: Mic state successfully restored to True")
        passed_count += 1
    else:
        print("   [FAIL] TEST 2: Mic state did not restore to True")

    # ----------------------------------------------------
    # TEST 3: Real OS Command 'open calculator'
    # ----------------------------------------------------
    print("\n[TEST 3] Executing 'open calculator'...")
    res3 = process_user_command("open calculator", source="chat")
    print(f"   Pipeline Result: {res3}")
    verif3 = verify_app_launched("Calculator", timeout=3.0)
    print(f"   Windows OS Verification: {verif3}")
    if res3.get("success") and res3.get("verified") and verif3.get("verified"):
        print("   [PASS] TEST 3: Calculator process verified running on Windows")
        passed_count += 1
    else:
        print("   [FAIL] TEST 3: Calculator verification failed")

    # ----------------------------------------------------
    # TEST 4: Real OS Command 'open notepad'
    # ----------------------------------------------------
    print("\n[TEST 4] Executing 'open notepad'...")
    res4 = process_user_command("open notepad", source="chat")
    print(f"   Pipeline Result: {res4}")
    verif4 = verify_app_launched("Notepad", timeout=3.0)
    print(f"   Windows OS Verification: {verif4}")
    if res4.get("success") and res4.get("verified") and verif4.get("verified"):
        print("   [PASS] TEST 4: Notepad process verified running on Windows")
        passed_count += 1
    else:
        print("   [FAIL] TEST 4: Notepad verification failed")

    # ----------------------------------------------------
    # TEST 5: Typed Command Execution while Mic is OFF
    # ----------------------------------------------------
    print("\n[TEST 5] Turning Mic OFF and testing typed command 'open calculator'...")
    set_jarvis_mic_enabled(False)
    print(f"   Mic State before command: {get_jarvis_mic_enabled()}")
    res5 = process_user_command("open calculator", source="chat")
    print(f"   Pipeline Result: {res5}")
    if res5.get("success") and res5.get("verified"):
        print("   [PASS] TEST 5: Typed command executed successfully while Mic was OFF")
        passed_count += 1
    else:
        print("   [FAIL] TEST 5: Command failed while Mic was OFF")

    # ----------------------------------------------------
    # TEST 6: Restore Mic via Typed Command 'jarvis mic on'
    # ----------------------------------------------------
    print("\n[TEST 6] Restoring Mic via typed command 'jarvis mic on'...")
    res6 = process_user_command("jarvis mic on", source="chat")
    mic_state_6 = get_jarvis_mic_enabled()
    print(f"   Pipeline Result: {res6}")
    print(f"   Mic State after command: {mic_state_6}")
    if res6.get("success") and mic_state_6 is True:
        print("   [PASS] TEST 6: Mic state restored to True via typed command")
        passed_count += 1
    else:
        print("   [FAIL] TEST 6: Failed to restore mic via typed command")

    # ----------------------------------------------------
    # TEST 7: Telemetry Command 'what is my cpu'
    # ----------------------------------------------------
    print("\n[TEST 7] Executing 'what is my cpu'...")
    res7 = process_user_command("what is my cpu", source="chat")
    print(f"   Pipeline Result: {res7['message']}")
    if res7.get("success") and "CPU:" in res7.get("message", ""):
        print("   [PASS] TEST 7: Real CPU telemetry retrieved")
        passed_count += 1
    else:
        print("   [FAIL] TEST 7: CPU telemetry query failed")

    # ----------------------------------------------------
    # TEST 8: Telemetry Command 'what is my battery'
    # ----------------------------------------------------
    print("\n[TEST 8] Executing 'what is my battery'...")
    res8 = process_user_command("what is my battery", source="chat")
    print(f"   Pipeline Result: {res8['message']}")
    if res8.get("success") and "Battery:" in res8.get("message", ""):
        print("   [PASS] TEST 8: Real battery telemetry retrieved")
        passed_count += 1
    else:
        print("   [FAIL] TEST 8: Battery telemetry query failed")

    # ----------------------------------------------------
    # TEST 9: Conversational Command 'hello jarvis'
    # ----------------------------------------------------
    print("\n[TEST 9] Executing 'hello jarvis'...")
    res9 = process_user_command("hello jarvis", source="chat")
    print(f"   Pipeline Result: {res9['message']}")
    if res9.get("success") and res9.get("message"):
        print("   [PASS] TEST 9: Conversational dialogue fallback working")
        passed_count += 1
    else:
        print("   [FAIL] TEST 9: Conversational command failed")

    # ----------------------------------------------------
    # TEST 10: Voice vs Text 100% Pipeline Parity Check
    # ----------------------------------------------------
    print("\n[TEST 10] Testing Voice vs Text Pipeline Parity for 'open notepad'...")
    res_voice = process_user_command("open notepad", source="voice")
    res_text  = process_user_command("open notepad", source="chat")
    print(f"   Voice Result Action: {res_voice.get('action')}, Message: {res_voice.get('message')}")
    print(f"   Text Result Action : {res_text.get('action')}, Message: {res_text.get('message')}")
    if res_voice.get("action") == res_text.get("action") and res_voice.get("success") and res_text.get("success"):
        print("   [PASS] TEST 10: Voice and Text entered exact same authoritative pipeline")
        passed_count += 1
    else:
        print("   [FAIL] TEST 10: Voice and Text pipeline parity check failed")

    print("\n========================================================")
    print(f"   FINAL MATRIX SCORE: {passed_count} / {total_count} PASSED")
    print("========================================================\n")

if __name__ == "__main__":
    run_live_matrix()

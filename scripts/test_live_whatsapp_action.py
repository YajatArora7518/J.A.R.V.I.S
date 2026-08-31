# scripts/test_live_whatsapp_action.py
# Real Live Hardware/UI WhatsApp Action Execution Script
# Executes live message sending, chat verification, voice call initiation, and latency profiling
# against the installed Windows WhatsApp Desktop Application (5319275A.WhatsAppDesktop / WhatsApp.Root).

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from actions.windows_whatsapp_desktop_executor import (
    windows_whatsapp_desktop_executor,
    send_windows_whatsapp_desktop_message,
    focus_installed_whatsapp_desktop,
    resolve_contact_ambiguity,
    call_state_machine,
    EXECUTION_TARGET_NAME
)


def run_live_whatsapp_action_test():
    print("========================================================")
    print("       JARVIS — REAL LIVE WHATSAPP ACTION VERIFICATION  ")
    print("========================================================")

    # 1. Focus WhatsApp Desktop Window
    print("\n[PHASE 1] Focusing Installed Windows WhatsApp Desktop...")
    t_start = time.time()
    focused, focus_msg = focus_installed_whatsapp_desktop()
    t_focus = time.time() - t_start
    print(f"  - Focus Status   : {focused}")
    print(f"  - Focus Message  : {focus_msg}")
    print(f"  - Focus Latency  : {round(t_focus * 1000, 2)} ms")

    if not focused:
        print("❌ Installed WhatsApp Desktop could not be focused. Aborting live test.")
        return

    # 2. Real Message Send to Safe Contact ('Aman Gupta')
    test_contact = "Aman Gupta"
    test_message = "JARVIS REAL RUNTIME TEST"
    print(f"\n[PHASE 2] Executing Real Message Send to '{test_contact}'...")
    print(f"  - Target Contact : '{test_contact}'")
    print(f"  - Message Text   : '{test_message}'")

    t_msg_start = time.time()
    msg_res = send_windows_whatsapp_desktop_message(test_contact, test_message)
    t_msg_total = time.time() - t_msg_start

    print(f"  - Send Result    : {msg_res.get('success')}")
    print(f"  - Output Message : {msg_res.get('message')}")
    print(f"  - Target Assert  : {msg_res.get('execution_target')}")
    print(f"  - Verified Bubble: {msg_res.get('verified')}")
    print(f"  - Total Latency  : {round(t_msg_total * 1000, 2)} ms")

    assert msg_res.get("execution_target") == EXECUTION_TARGET_NAME, "Target assertion failure!"

    # 3. Real Voice Call Initiation Test
    print(f"\n[PHASE 3] Executing Real Voice Call Initiation to '{test_contact}'...")
    t_call_start = time.time()
    call_res = windows_whatsapp_desktop_executor.execute_voice_call(test_contact)
    t_call_total = time.time() - t_call_start

    print(f"  - Call Result    : {call_res.get('success')}")
    print(f"  - Output Message : {call_res.get('message')}")
    print(f"  - Call State     : {call_res.get('call_state')}")
    print(f"  - Target Assert  : {call_res.get('execution_target')}")
    print(f"  - Total Latency  : {round(t_call_total * 1000, 2)} ms")

    # 4. Clean State Reset
    windows_whatsapp_desktop_executor.execute_end_call()

    print("\n========================================================")
    print("     LIVE WHATSAPP ACTION VERIFICATION COMPLETE         ")
    print("========================================================")


if __name__ == "__main__":
    run_live_whatsapp_action_test()

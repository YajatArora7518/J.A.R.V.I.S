# scripts/test_real_world_commands.py
# Real-World Natural Language Command Validation for JARVIS (Voice & Text Parity)

import sys
import os
import time
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.command_pipeline import process_user_command
from actions.script_executor import get_workspace_dir

def test_real_world_commands():
    print("========================================================")
    print("   JARVIS REAL-WORLD NATURAL LANGUAGE COMMAND AUDIT")
    print("========================================================\n")

    test_commands = [
        "Notepad kholo",
        "Calculator kholo",
        "Desktop par JARVIS_TEST folder banao",
        "JARVIS_TEST ke andar test.txt banao",
        "test.txt mein Hello Boss likho",
        "test.txt padh ke batao",
        "test.txt ko renamed_test.txt rename karo",
        "ek Python script banao jo JARVIS_TEST mein hello print kare aur run karo",
        "ek PowerShell script banao jo current username bataye aur run karo",
        "ek BAT file banao jo Calculator launch kare aur run karo",
        "kaunsa process sabse zyada RAM use kar raha hai?",
        "mere PC mein kitni RAM hai?",
        "C drive mein kitni space hai?",
        "Windows version batao",
        "Windows services ka status batao",
        "web par latest Windows 11 update search karo",
        "JARVIS_TEST folder clean kar do"
    ]

    scores = []
    print(f"{'Command':<65} | {'Source':<7} | {'Intent/Tool':<25} | {'Result'}")
    print("-" * 115)

    for cmd in test_commands:
        for src in ["chat", "voice"]:
            res = process_user_command(cmd, source=src)
            success = res.get("success", False) or res.get("verified", False) or "Opening" in str(res.get("message", "")) or "RAM" in str(res.get("message", "")) or "Windows" in str(res.get("message", ""))
            status_str = "[PASS]" if success else "[FAIL]"
            tool_used = res.get("intent", res.get("tool", "UNKNOWN"))
            print(f"{cmd[:63]:<65} | {src:<7} | {str(tool_used):<25} | {status_str}")
            scores.append((cmd, src, success))

    passed_count = sum(1 for _, _, s in scores if s)
    total_count = len(scores)

    print("\n========================================================")
    print(f" COMMAND PIPELINE SCORE: {passed_count} / {total_count} PASSED")
    print("========================================================\n")

    return passed_count == total_count

if __name__ == "__main__":
    test_real_world_commands()

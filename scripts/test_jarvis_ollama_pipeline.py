# scripts/test_jarvis_ollama_pipeline.py
import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.register_tools import initialize_all_tools
from core.command_pipeline import process_user_command
from core.verification import verify_app_launched

def run_jarvis_tests():
    print("==================================================")
    print("      JARVIS OLLAMA INTEGRATED PIPELINE TEST")
    print("==================================================")
    initialize_all_tools()

    print("\n1. Testing Conversational Input: 'Jarvis, who are you?'...")
    res1 = process_user_command("Jarvis, who are you?", source="chat")
    print(f"   Success    : {res1.get('success')}")
    print(f"   Model/Status: {res1.get('model_used') or res1.get('status')}")
    print(f"   Response   : {res1.get('message')}")

    print("\n2. Testing Harmless Action Input: 'Jarvis, open Notepad.'...")
    res2 = process_user_command("Jarvis, open Notepad.", source="chat")
    print(f"   Success    : {res2.get('success')}")
    print(f"   Action/Tool: {res2.get('action')}")
    print(f"   Response   : {res2.get('message')}")
    print(f"   Verified   : {res2.get('verified')}")

    verif2 = verify_app_launched("Notepad", timeout=3.0)
    print(f"   OS Process Verification: {verif2}")
    print("==================================================")

if __name__ == "__main__":
    run_jarvis_tests()

# scripts/reproduce_open_crash.py
import sys
import os
import traceback
import time

sys.path.insert(0, os.path.abspath("."))

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

print("=== REPRODUCING OPEN_APP CRASH ===")
os.environ["QT_QPA_PLATFORM"] = "offscreen" # Headless Qt

from ui import JarvisUI
from main import JarvisLive
from core.register_tools import initialize_all_tools, default_tool_registry

print("Initializing tool registry...", flush=True)
initialize_all_tools()
print("Tool registry initialized.", flush=True)

print("Creating JarvisUI...", flush=True)
ui = JarvisUI("face.png")
print("JarvisUI created.", flush=True)

print("Creating JarvisLive...", flush=True)
jarvis = JarvisLive(ui)
print("JarvisLive created.", flush=True)

print("\n--- TEST 1: _dispatch_voice_to_pipeline('open Notepad') ---")
try:
    jarvis._dispatch_voice_to_pipeline("open Notepad", "")
    print("Test 1 completed without crashing.")
except Exception as e:
    print(f"TEST 1 CRASHED: {e}")
    traceback.print_exc()

print("\n--- TEST 2: _on_text_command('open Notepad') ---")
try:
    jarvis._on_text_command("open Notepad")
    print("Test 2 completed without crashing.")
except Exception as e:
    print(f"TEST 2 CRASHED: {e}")
    traceback.print_exc()

print("\n--- TEST 3: _execute_tool via Gemini Live ToolCall mock ---")
class MockFC:
    def __init__(self, name, args, fc_id="call_123"):
        self.name = name
        self.args = args
        self.id = fc_id

import asyncio
async def test_tool_call():
    fc = MockFC("open_app", {"app_name": "Notepad"})
    try:
        fr = await jarvis._execute_tool(fc)
        print("Test 3 response:", fr)
        print("Test 3 completed without crashing.")
    except Exception as e:
        print(f"TEST 3 CRASHED: {e}")
        traceback.print_exc()

asyncio.run(test_tool_call())

print("\n--- TEST 4: _dispatch_voice_to_pipeline('Jarvis, open Notepad') ---")
try:
    jarvis._dispatch_voice_to_pipeline("Jarvis, open Notepad", "")
    print("Test 4 completed without crashing.")
except Exception as e:
    print(f"TEST 4 CRASHED: {e}")
    traceback.print_exc()

print("\n--- TEST 5: _on_text_command('Jarvis, open Notepad') ---")
try:
    jarvis._on_text_command("Jarvis, open Notepad")
    print("Test 5 completed without crashing.")
except Exception as e:
    print(f"TEST 5 CRASHED: {e}")
    traceback.print_exc()

print("\n=== REPRODUCTION SCRIPT COMPLETED ===")

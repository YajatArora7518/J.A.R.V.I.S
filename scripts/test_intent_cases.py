# scripts/test_intent_cases.py
import sys, os
sys.path.insert(0, os.path.abspath("."))
from core.intent_router import classify_intent
from core.command_pipeline import process_user_command

test_cmds = [
    'open Notepad',
    'open "Notepad"',
    'open Chrome',
    'open Calculator',
    'open File Explorer',
    'Jarvis, open Notepad',
    'Jarvis open Notepad',
    'please open Notepad',
    'Notepad kholo',
    'Chrome kholo',
    'open SomeApplicationThatDefinitelyDoesNotExist123'
]

print("=== INTENT CLASSIFICATION TEST ===")
for cmd in test_cmds:
    c = classify_intent(cmd)
    print(f"{cmd!r:50} -> intent={c.get('intent', ''):22} target={c.get('target', ''):20} tool={c.get('tool', '')}")

print("\n=== PIPELINE PROCESS TEST ===")
for cmd in test_cmds:
    try:
        res = process_user_command(cmd, source="voice")
        print(f"{cmd!r:50} -> success={str(res.get('success')):5} status={str(res.get('status')):18} msg={str(res.get('message'))[:50]}")
    except Exception as e:
        import traceback
        print(f"{cmd!r:50} -> CRASH: {e}")
        traceback.print_exc()
